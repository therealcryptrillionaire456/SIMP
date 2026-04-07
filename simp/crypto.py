from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization, hashes
import hashlib
import hmac
import json
import os
import time
import logging
import warnings

logger = logging.getLogger("SIMP.Crypto")


class SimpCrypto:
    """Cryptographic utilities for SIMP"""

    @staticmethod
    def generate_keypair():
        """Generate a new Ed25519 keypair"""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return private_key, public_key

    @staticmethod
    def private_key_to_pem(private_key, passphrase: bytes = None) -> bytes:
        """Convert private key to PEM format.

        If passphrase is provided, encrypts the key with BestAvailableEncryption.
        If passphrase is None, checks SIMP_KEY_PASSPHRASE env var.
        Falls back to NoEncryption with a warning if no passphrase available.
        """
        if passphrase is None:
            env_passphrase = os.environ.get("SIMP_KEY_PASSPHRASE")
            if env_passphrase:
                passphrase = env_passphrase.encode()

        if passphrase:
            encryption = serialization.BestAvailableEncryption(passphrase)
        else:
            warnings.warn(
                "SIMP_KEY_PASSPHRASE not set: private key will be stored unencrypted. "
                "Set SIMP_KEY_PASSPHRASE environment variable for production use.",
                UserWarning,
                stacklevel=2,
            )
            encryption = serialization.NoEncryption()

        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )

    @staticmethod
    def public_key_to_pem(public_key) -> bytes:
        """Convert public key to PEM format"""
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    @staticmethod
    def load_private_key(pem_data: bytes, passphrase: bytes = None):
        """Load private key from PEM.

        If passphrase is None, checks SIMP_KEY_PASSPHRASE env var.
        """
        if passphrase is None:
            env_passphrase = os.environ.get("SIMP_KEY_PASSPHRASE")
            if env_passphrase:
                passphrase = env_passphrase.encode()
        return serialization.load_pem_private_key(pem_data, password=passphrase)

    @staticmethod
    def load_public_key(pem_data: bytes):
        """Load public key from PEM"""
        return serialization.load_pem_public_key(pem_data)

    @staticmethod
    def _key_fingerprint(public_key) -> str:
        """Compute SHA-256 fingerprint of a public key (hex, first 16 chars)"""
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return hashlib.sha256(pub_bytes).hexdigest()[:16]

    @staticmethod
    def sign_intent(intent_dict: dict, private_key) -> str:
        """Sign an intent (legacy API, kept for backward compatibility).

        Uses double-hashing for backward compat with existing callers.
        New code should use sign_intent_v2.
        """
        # Make a copy without signature
        intent_copy = intent_dict.copy()
        intent_copy.pop("signature", None)

        # Hash it (legacy double-hash kept for backward compatibility)
        intent_json = json.dumps(intent_copy, sort_keys=True)
        intent_bytes = intent_json.encode()
        intent_hash = hashlib.sha256(intent_bytes).digest()

        # Sign
        signature = private_key.sign(intent_hash)
        return signature.hex()

    @staticmethod
    def sign_intent_v2(intent_dict: dict, private_key) -> str:
        """Sign an intent with security metadata (v2).

        - Adds _sig_nonce, _sig_exp, _sig_iat, _sig_kid to the intent
        - Signs the canonical JSON directly (no pre-hash; Ed25519 hashes internally)
        - Returns hex-encoded signature

        Mutates intent_dict in place to add security fields.
        """
        intent_dict.pop("signature", None)

        # Add security metadata
        now = time.time()
        public_key = private_key.public_key()
        intent_dict["_sig_nonce"] = os.urandom(16).hex()
        intent_dict["_sig_exp"] = now + 300  # 5 min expiry
        intent_dict["_sig_iat"] = now
        intent_dict["_sig_kid"] = SimpCrypto._key_fingerprint(public_key)

        # Canonical JSON
        intent_json = json.dumps(intent_dict, sort_keys=True)
        intent_bytes = intent_json.encode()

        # Sign directly — Ed25519 hashes internally
        signature = private_key.sign(intent_bytes)
        return signature.hex()

    @staticmethod
    def verify_signature(intent_dict: dict, public_key) -> bool:
        """Verify an intent's signature (legacy API).

        Uses double-hashing for backward compat.
        """
        try:
            intent_copy = intent_dict.copy()
            signature_hex = intent_copy.pop("signature", "")

            intent_json = json.dumps(intent_copy, sort_keys=True)
            intent_bytes = intent_json.encode()
            intent_hash = hashlib.sha256(intent_bytes).digest()

            signature_bytes = bytes.fromhex(signature_hex)
            public_key.verify(signature_bytes, intent_hash)
            return True
        except Exception:
            return False

    @staticmethod
    def verify_signature_v2(intent_dict: dict, public_key) -> bool:
        """Verify a v2 signed intent's signature.

        Checks expiry and verifies without pre-hash.
        """
        try:
            intent_copy = intent_dict.copy()
            signature_hex = intent_copy.pop("signature", "")

            # Check expiry
            sig_exp = intent_copy.get("_sig_exp")
            if sig_exp is not None and time.time() > sig_exp:
                return False

            intent_json = json.dumps(intent_copy, sort_keys=True)
            intent_bytes = intent_json.encode()

            signature_bytes = bytes.fromhex(signature_hex)

            # Use timing-safe comparison for the verification step
            # Ed25519 verify raises on failure, so we just call it
            public_key.verify(signature_bytes, intent_bytes)
            return True
        except Exception:
            return False

    @staticmethod
    def verify_signature_strict(intent_dict: dict, public_key, seen_nonces: set = None) -> tuple:
        """Strict signature verification with replay protection.

        Returns (bool, reason) tuple.
        Checks: signature validity, expiry, nonce replay, key ID match.
        """
        try:
            intent_copy = intent_dict.copy()
            signature_hex = intent_copy.pop("signature", "")

            if not signature_hex:
                return False, "missing_signature"

            # Check required security fields
            sig_exp = intent_copy.get("_sig_exp")
            sig_iat = intent_copy.get("_sig_iat")
            sig_nonce = intent_copy.get("_sig_nonce")
            sig_kid = intent_copy.get("_sig_kid")

            if sig_exp is None or sig_iat is None or sig_nonce is None:
                return False, "missing_security_fields"

            # Check expiry
            now = time.time()
            if now > sig_exp:
                return False, "signature_expired"

            # Check issued-at is not in the future (with small tolerance)
            if sig_iat > now + 5:
                return False, "issued_in_future"

            # Check nonce replay
            if seen_nonces is not None:
                if sig_nonce in seen_nonces:
                    return False, "nonce_replay"
                seen_nonces.add(sig_nonce)

            # Check key fingerprint if provided
            if sig_kid is not None:
                expected_kid = SimpCrypto._key_fingerprint(public_key)
                if not hmac.compare_digest(sig_kid, expected_kid):
                    return False, "key_id_mismatch"

            # Verify signature (no pre-hash)
            intent_json = json.dumps(intent_copy, sort_keys=True)
            intent_bytes = intent_json.encode()
            signature_bytes = bytes.fromhex(signature_hex)

            public_key.verify(signature_bytes, intent_bytes)
            return True, "valid"

        except Exception as e:
            return False, f"verification_failed: {str(e)}"
