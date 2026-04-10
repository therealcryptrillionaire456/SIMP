"""
SIMP Noise Protocol Identity & Handshake

Implements Noise_XX_25519_ChaChaPoly_SHA256 for authenticated key exchange
between SIMP agents over any transport.

Uses only the `cryptography` library (X25519, ChaCha20Poly1305, HKDF, Ed25519).
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


NOISE_PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_SHA256"
EMPTY_KEY = b"\x00" * 32
MAX_NONCE = 2**64 - 1
REKEY_INTERVAL_SECONDS = 3600  # 1 hour
REKEY_MESSAGE_COUNT = 10000


@dataclass
class AgentIdentity:
    """
    Dual-key identity for a SIMP agent.
    - Curve25519 for X25519 Diffie-Hellman key exchange
    - Ed25519 for signing/authentication
    """
    x25519_private: x25519.X25519PrivateKey = None
    x25519_public: x25519.X25519PublicKey = None
    ed25519_private: ed25519.Ed25519PrivateKey = None
    ed25519_public: ed25519.Ed25519PublicKey = None
    agent_id: str = ""

    @property
    def fingerprint(self) -> str:
        if self.x25519_public is None:
            return ""
        raw = self.x25519_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return hashlib.sha256(raw).hexdigest()[:32]

    @property
    def peer_id(self) -> bytes:
        if not self.agent_id:
            return self.fingerprint[:8].encode() if self.fingerprint else b"\x00" * 8
        return hashlib.sha256(self.agent_id.encode()).digest()[:8]

    @classmethod
    def generate(cls, agent_id: str = "") -> "AgentIdentity":
        """Generate a new dual-key identity."""
        x_priv = x25519.X25519PrivateKey.generate()
        e_priv = ed25519.Ed25519PrivateKey.generate()
        return cls(
            x25519_private=x_priv,
            x25519_public=x_priv.public_key(),
            ed25519_private=e_priv,
            ed25519_public=e_priv.public_key(),
            agent_id=agent_id,
        )

    def save_keystore(self, path: str, password: bytes = b"simp-default") -> None:
        """Save identity to encrypted keystore file."""
        enc = serialization.BestAvailableEncryption(password)
        no_enc = serialization.NoEncryption()

        x_priv_pem = self.x25519_private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            enc,
        )
        e_priv_pem = self.ed25519_private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            enc,
        )
        x_pub_pem = self.x25519_public.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        e_pub_pem = self.ed25519_public.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        data = {
            "agent_id": self.agent_id,
            "x25519_private": x_priv_pem.decode(),
            "x25519_public": x_pub_pem.decode(),
            "ed25519_private": e_priv_pem.decode(),
            "ed25519_public": e_pub_pem.decode(),
        }

        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def from_keystore(cls, path: str, password: bytes = b"simp-default") -> "AgentIdentity":
        """Load identity from encrypted keystore file."""
        with open(path, "r") as f:
            data = json.load(f)

        x_priv = serialization.load_pem_private_key(
            data["x25519_private"].encode(), password=password
        )
        e_priv = serialization.load_pem_private_key(
            data["ed25519_private"].encode(), password=password
        )
        x_pub = serialization.load_pem_public_key(data["x25519_public"].encode())
        e_pub = serialization.load_pem_public_key(data["ed25519_public"].encode())

        return cls(
            x25519_private=x_priv,
            x25519_public=x_pub,
            ed25519_private=e_priv,
            ed25519_public=e_pub,
            agent_id=data.get("agent_id", ""),
        )


def _hmac_hash(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA256."""
    import hmac
    return hmac.new(key, data, hashlib.sha256).digest()


def _hkdf(input_key: bytes, salt: bytes, info: bytes = b"", length: int = 64) -> Tuple[bytes, ...]:
    """HKDF-SHA256 key derivation returning two 32-byte keys."""
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
    ).derive(input_key)
    return (derived[:32], derived[32:64])


def _dh(private_key: x25519.X25519PrivateKey, public_key: x25519.X25519PublicKey) -> bytes:
    """X25519 Diffie-Hellman."""
    return private_key.exchange(public_key)


def _encrypt(key: bytes, nonce: int, ad: bytes, plaintext: bytes) -> bytes:
    """ChaCha20-Poly1305 AEAD encrypt."""
    if key == EMPTY_KEY:
        return plaintext
    cipher = ChaCha20Poly1305(key)
    # Nonce: 4 zero bytes + 8-byte little-endian counter
    nonce_bytes = b"\x00" * 4 + nonce.to_bytes(8, "little")
    return cipher.encrypt(nonce_bytes, plaintext, ad)


def _decrypt(key: bytes, nonce: int, ad: bytes, ciphertext: bytes) -> bytes:
    """ChaCha20-Poly1305 AEAD decrypt."""
    if key == EMPTY_KEY:
        return ciphertext
    cipher = ChaCha20Poly1305(key)
    nonce_bytes = b"\x00" * 4 + nonce.to_bytes(8, "little")
    return cipher.decrypt(nonce_bytes, ciphertext, ad)


def _get_raw_public(key: x25519.X25519PublicKey) -> bytes:
    """Get raw 32-byte public key."""
    return key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


class NoiseHandshakeState:
    """
    Noise_XX_25519_ChaChaPoly_SHA256 handshake state machine.

    XX pattern (3 messages):
      -> e
      <- e, ee, s, es
      -> s, se
    """

    def __init__(self, identity: AgentIdentity, is_initiator: bool):
        self.identity = identity
        self.is_initiator = is_initiator

        # Symmetric state
        protocol_name = NOISE_PROTOCOL_NAME
        if len(protocol_name) <= 32:
            self.h = protocol_name.ljust(32, b"\x00")
        else:
            self.h = hashlib.sha256(protocol_name).digest()
        self.ck = self.h  # Chaining key

        # Cipher keys
        self.k = EMPTY_KEY
        self.n = 0  # nonce counter

        # Ephemeral keys (generated during handshake)
        self.local_ephemeral_private: Optional[x25519.X25519PrivateKey] = None
        self.local_ephemeral_public: Optional[x25519.X25519PublicKey] = None
        self.remote_ephemeral_public: Optional[x25519.X25519PublicKey] = None
        self.remote_static_public: Optional[x25519.X25519PublicKey] = None

        # Split keys (available after handshake completes)
        self.send_key: Optional[bytes] = None
        self.recv_key: Optional[bytes] = None
        self.handshake_complete = False

    def _mix_hash(self, data: bytes) -> None:
        self.h = hashlib.sha256(self.h + data).digest()

    def _mix_key(self, input_key_material: bytes) -> None:
        self.ck, temp_k = _hkdf(input_key_material, self.ck)
        self.k = temp_k
        self.n = 0

    def _encrypt_and_hash(self, plaintext: bytes) -> bytes:
        ciphertext = _encrypt(self.k, self.n, self.h, plaintext)
        self._mix_hash(ciphertext)
        self.n += 1
        return ciphertext

    def _decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        plaintext = _decrypt(self.k, self.n, self.h, ciphertext)
        self._mix_hash(ciphertext)
        self.n += 1
        return plaintext

    def _split(self) -> Tuple[bytes, bytes]:
        """Split the symmetric state into send/receive keys."""
        k1, k2 = _hkdf(b"", self.ck)
        if self.is_initiator:
            return k1, k2
        else:
            return k2, k1

    # --- XX Pattern: -> e ----------------------------------------------------------------

    def write_message_1(self, payload: bytes = b"") -> bytes:
        """Initiator writes message 1: -> e"""
        self.local_ephemeral_private = x25519.X25519PrivateKey.generate()
        self.local_ephemeral_public = self.local_ephemeral_private.public_key()

        e_pub_raw = _get_raw_public(self.local_ephemeral_public)
        self._mix_hash(e_pub_raw)

        # Payload (unencrypted since no key established yet)
        enc_payload = self._encrypt_and_hash(payload)
        return e_pub_raw + enc_payload

    def read_message_1(self, message: bytes) -> bytes:
        """Responder reads message 1: -> e"""
        re_raw = message[:32]
        self.remote_ephemeral_public = x25519.X25519PublicKey.from_public_bytes(re_raw)
        self._mix_hash(re_raw)

        payload = self._decrypt_and_hash(message[32:])
        return payload

    # --- XX Pattern: <- e, ee, s, es -----------------------------------------------------

    def write_message_2(self, payload: bytes = b"") -> bytes:
        """Responder writes message 2: <- e, ee, s, es"""
        # e
        self.local_ephemeral_private = x25519.X25519PrivateKey.generate()
        self.local_ephemeral_public = self.local_ephemeral_private.public_key()
        e_pub_raw = _get_raw_public(self.local_ephemeral_public)
        self._mix_hash(e_pub_raw)

        # ee
        dh_ee = _dh(self.local_ephemeral_private, self.remote_ephemeral_public)
        self._mix_key(dh_ee)

        # s (encrypted static public key)
        s_pub_raw = _get_raw_public(self.identity.x25519_public)
        enc_s = self._encrypt_and_hash(s_pub_raw)

        # es
        dh_es = _dh(self.identity.x25519_private, self.remote_ephemeral_public)
        self._mix_key(dh_es)

        # Payload
        enc_payload = self._encrypt_and_hash(payload)
        return e_pub_raw + enc_s + enc_payload

    def read_message_2(self, message: bytes) -> bytes:
        """Initiator reads message 2: <- e, ee, s, es"""
        offset = 0

        # e
        re_raw = message[offset:offset + 32]
        offset += 32
        self.remote_ephemeral_public = x25519.X25519PublicKey.from_public_bytes(re_raw)
        self._mix_hash(re_raw)

        # ee
        dh_ee = _dh(self.local_ephemeral_private, self.remote_ephemeral_public)
        self._mix_key(dh_ee)

        # s (encrypted static key: 32 bytes plaintext + 16 bytes tag = 48 bytes)
        enc_s = message[offset:offset + 48]
        offset += 48
        rs_raw = self._decrypt_and_hash(enc_s)
        self.remote_static_public = x25519.X25519PublicKey.from_public_bytes(rs_raw)

        # es
        dh_es = _dh(self.local_ephemeral_private, self.remote_static_public)
        self._mix_key(dh_es)

        # Payload
        payload = self._decrypt_and_hash(message[offset:])
        return payload

    # --- XX Pattern: -> s, se ------------------------------------------------------------

    def write_message_3(self, payload: bytes = b"") -> bytes:
        """Initiator writes message 3: -> s, se"""
        # s (encrypted static public key)
        s_pub_raw = _get_raw_public(self.identity.x25519_public)
        enc_s = self._encrypt_and_hash(s_pub_raw)

        # se
        dh_se = _dh(self.identity.x25519_private, self.remote_ephemeral_public)
        self._mix_key(dh_se)

        # Payload
        enc_payload = self._encrypt_and_hash(payload)

        # Split into transport keys
        self.send_key, self.recv_key = self._split()
        self.handshake_complete = True

        return enc_s + enc_payload

    def read_message_3(self, message: bytes) -> bytes:
        """Responder reads message 3: -> s, se"""
        offset = 0

        # s (encrypted static key: 32 + 16 = 48 bytes)
        enc_s = message[offset:offset + 48]
        offset += 48
        rs_raw = self._decrypt_and_hash(enc_s)
        self.remote_static_public = x25519.X25519PublicKey.from_public_bytes(rs_raw)

        # se
        dh_se = _dh(self.local_ephemeral_private, self.remote_static_public)
        self._mix_key(dh_se)

        # Payload
        payload = self._decrypt_and_hash(message[offset:])

        # Split into transport keys
        self.send_key, self.recv_key = self._split()
        self.handshake_complete = True

        return payload


class NoiseSession:
    """
    Post-handshake encrypted session using symmetric keys from Noise handshake.
    Supports incrementing nonces and rekeying after time/message thresholds.
    """

    def __init__(self, send_key: bytes, recv_key: bytes):
        self.send_key = send_key
        self.recv_key = recv_key
        self.send_nonce = 0
        self.recv_nonce = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.created_at = time.time()
        self.last_rekey = time.time()

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt a message with the send key and incrementing nonce."""
        self._check_rekey()
        ct = _encrypt(self.send_key, self.send_nonce, b"", plaintext)
        self.send_nonce += 1
        self.messages_sent += 1
        return ct

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt a message with the recv key and incrementing nonce."""
        pt = _decrypt(self.recv_key, self.recv_nonce, b"", ciphertext)
        self.recv_nonce += 1
        self.messages_received += 1
        return pt

    def _check_rekey(self) -> None:
        """Rekey if time or message thresholds exceeded."""
        now = time.time()
        should_rekey = (
            (now - self.last_rekey) > REKEY_INTERVAL_SECONDS
            or self.messages_sent >= REKEY_MESSAGE_COUNT
        )
        if should_rekey:
            self.rekey()

    def rekey(self) -> None:
        """Derive new keys from current keys via HKDF.

        Uses a common salt so that both sides derive matching keys:
        alice.send_key == bob.recv_key, so HKDF(alice.send_key, salt) == HKDF(bob.recv_key, salt).
        """
        new_send, _ = _hkdf(self.send_key, b"simp-rekey")
        new_recv, _ = _hkdf(self.recv_key, b"simp-rekey")
        self.send_key = new_send
        self.recv_key = new_recv
        self.send_nonce = 0
        self.recv_nonce = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.last_rekey = time.time()

    @property
    def needs_rekey(self) -> bool:
        now = time.time()
        return (
            (now - self.last_rekey) > REKEY_INTERVAL_SECONDS
            or self.messages_sent >= REKEY_MESSAGE_COUNT
        )

    @classmethod
    def from_handshake(cls, handshake: NoiseHandshakeState) -> "NoiseSession":
        """Create a session from a completed handshake."""
        if not handshake.handshake_complete:
            raise ValueError("Handshake not complete")
        return cls(
            send_key=handshake.send_key,
            recv_key=handshake.recv_key,
        )
