"""
Sprint 66 — Crypto Hardening Tests

Tests for:
- Double-hashing removal in sign_intent_v2
- Security metadata fields (_sig_nonce, _sig_exp, _sig_iat, _sig_kid)
- verify_signature_v2 (no pre-hash, expiry check)
- verify_signature_strict (replay protection, key ID match)
- Backward compatibility of legacy sign_intent / verify_signature
"""

import pytest
import time
import json
from simp.crypto import SimpCrypto


class TestLegacyBackwardCompat:
    """Ensure legacy sign_intent and verify_signature still work unchanged."""

    def test_legacy_sign_intent_returns_hex(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test", "type": "trade", "params": {"amount": 10}}
        sig = SimpCrypto.sign_intent(intent, priv)
        assert isinstance(sig, str)
        assert len(sig) > 0
        # hex-decodable
        bytes.fromhex(sig)

    def test_legacy_sign_and_verify_roundtrip(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test", "type": "trade", "params": {"amount": 10}}
        sig = SimpCrypto.sign_intent(intent, priv)
        intent["signature"] = sig
        assert SimpCrypto.verify_signature(intent, pub) is True

    def test_legacy_verify_rejects_tampered(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test", "type": "trade", "params": {"amount": 10}}
        sig = SimpCrypto.sign_intent(intent, priv)
        intent["signature"] = sig
        intent["params"]["amount"] = 999
        assert SimpCrypto.verify_signature(intent, pub) is False

    def test_legacy_verify_rejects_wrong_key(self):
        priv1, pub1 = SimpCrypto.generate_keypair()
        _, pub2 = SimpCrypto.generate_keypair()
        intent = {"id": "test", "type": "trade"}
        sig = SimpCrypto.sign_intent(intent, priv1)
        intent["signature"] = sig
        assert SimpCrypto.verify_signature(intent, pub2) is False


class TestSignIntentV2:
    """Test the new v2 signing with security metadata."""

    def test_v2_adds_security_fields(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test", "type": "trade"}
        sig = SimpCrypto.sign_intent_v2(intent, priv)
        assert "_sig_nonce" in intent
        assert "_sig_exp" in intent
        assert "_sig_iat" in intent
        assert "_sig_kid" in intent
        assert isinstance(sig, str)
        bytes.fromhex(sig)

    def test_v2_nonce_is_unique(self):
        priv, _ = SimpCrypto.generate_keypair()
        nonces = set()
        for _ in range(20):
            intent = {"id": "test"}
            SimpCrypto.sign_intent_v2(intent, priv)
            nonces.add(intent["_sig_nonce"])
        assert len(nonces) == 20

    def test_v2_exp_is_future(self):
        priv, _ = SimpCrypto.generate_keypair()
        intent = {"id": "test"}
        SimpCrypto.sign_intent_v2(intent, priv)
        assert intent["_sig_exp"] > time.time()
        assert intent["_sig_exp"] <= time.time() + 301

    def test_v2_kid_matches_public_key(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test"}
        SimpCrypto.sign_intent_v2(intent, priv)
        expected_kid = SimpCrypto._key_fingerprint(pub)
        assert intent["_sig_kid"] == expected_kid


class TestVerifySignatureV2:
    """Test v2 verification."""

    def test_v2_verify_roundtrip(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test", "type": "trade"}
        sig = SimpCrypto.sign_intent_v2(intent, priv)
        intent["signature"] = sig
        assert SimpCrypto.verify_signature_v2(intent, pub) is True

    def test_v2_verify_rejects_expired(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test"}
        sig = SimpCrypto.sign_intent_v2(intent, priv)
        # Force expiry into the past
        intent["_sig_exp"] = time.time() - 10
        # Re-sign with the modified expiry
        intent.pop("signature", None)
        canon = json.dumps(intent, sort_keys=True).encode()
        new_sig = priv.sign(canon).hex()
        intent["signature"] = new_sig
        assert SimpCrypto.verify_signature_v2(intent, pub) is False

    def test_v2_verify_rejects_wrong_key(self):
        priv1, pub1 = SimpCrypto.generate_keypair()
        _, pub2 = SimpCrypto.generate_keypair()
        intent = {"id": "test"}
        sig = SimpCrypto.sign_intent_v2(intent, priv1)
        intent["signature"] = sig
        assert SimpCrypto.verify_signature_v2(intent, pub2) is False


class TestVerifySignatureStrict:
    """Test strict verification with replay protection."""

    def _sign_v2(self, intent, priv):
        sig = SimpCrypto.sign_intent_v2(intent, priv)
        intent["signature"] = sig
        return intent

    def test_strict_valid(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = self._sign_v2({"id": "test"}, priv)
        ok, reason = SimpCrypto.verify_signature_strict(intent, pub)
        assert ok is True
        assert reason == "valid"

    def test_strict_rejects_nonce_replay(self):
        priv, pub = SimpCrypto.generate_keypair()
        seen = set()

        intent = self._sign_v2({"id": "test"}, priv)
        ok, reason = SimpCrypto.verify_signature_strict(intent, pub, seen)
        assert ok is True

        # Replay same nonce
        ok2, reason2 = SimpCrypto.verify_signature_strict(intent, pub, seen)
        assert ok2 is False
        assert reason2 == "nonce_replay"

    def test_strict_rejects_missing_signature(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test", "_sig_nonce": "abc", "_sig_exp": time.time() + 300, "_sig_iat": time.time()}
        ok, reason = SimpCrypto.verify_signature_strict(intent, pub)
        assert ok is False
        assert reason == "missing_signature"

    def test_strict_rejects_key_id_mismatch(self):
        priv, pub = SimpCrypto.generate_keypair()
        intent = {"id": "test"}
        sig = SimpCrypto.sign_intent_v2(intent, priv)
        intent["signature"] = sig
        intent["_sig_kid"] = "wrong_fingerprint"

        # Re-sign to make signature valid with modified kid
        intent.pop("signature")
        canon = json.dumps(intent, sort_keys=True).encode()
        intent["signature"] = priv.sign(canon).hex()

        ok, reason = SimpCrypto.verify_signature_strict(intent, pub)
        assert ok is False
        assert reason == "key_id_mismatch"
