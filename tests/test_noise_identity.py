"""
Tests for SIMP Noise Identity & Handshake (Sprint 72)
"""

import os
import tempfile
import pytest

from simp.transport.noise_identity import (
    AgentIdentity,
    NoiseHandshakeState,
    NoiseSession,
    _encrypt,
    _decrypt,
    _dh,
    _hkdf,
    EMPTY_KEY,
    REKEY_MESSAGE_COUNT,
)
from simp.crypto import SimpCrypto


class TestAgentIdentity:
    def test_generate(self):
        identity = AgentIdentity.generate("test-agent")
        assert identity.agent_id == "test-agent"
        assert identity.x25519_private is not None
        assert identity.x25519_public is not None
        assert identity.ed25519_private is not None
        assert identity.ed25519_public is not None

    def test_fingerprint(self):
        identity = AgentIdentity.generate("agent-1")
        fp = identity.fingerprint
        assert isinstance(fp, str)
        assert len(fp) == 32

    def test_peer_id(self):
        identity = AgentIdentity.generate("agent-1")
        pid = identity.peer_id
        assert isinstance(pid, bytes)
        assert len(pid) == 8

    def test_save_and_load_keystore(self):
        identity = AgentIdentity.generate("persist-agent")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            identity.save_keystore(path, password=b"test-password")
            loaded = AgentIdentity.from_keystore(path, password=b"test-password")
            assert loaded.agent_id == "persist-agent"
            assert loaded.fingerprint == identity.fingerprint
        finally:
            os.unlink(path)

    def test_different_agents_different_fingerprints(self):
        a = AgentIdentity.generate("alice")
        b = AgentIdentity.generate("bob")
        assert a.fingerprint != b.fingerprint


class TestCryptoExtensions:
    def test_generate_curve25519_keypair(self):
        priv, pub = SimpCrypto.generate_curve25519_keypair()
        assert priv is not None
        assert pub is not None

    def test_curve25519_fingerprint(self):
        _, pub = SimpCrypto.generate_curve25519_keypair()
        fp = SimpCrypto.curve25519_fingerprint(pub)
        assert isinstance(fp, str)
        assert len(fp) == 32


class TestCryptoPrimitives:
    def test_encrypt_decrypt(self):
        key = os.urandom(32)
        plaintext = b"Hello, SIMP!"
        ct = _encrypt(key, 0, b"", plaintext)
        pt = _decrypt(key, 0, b"", ct)
        assert pt == plaintext

    def test_encrypt_with_ad(self):
        key = os.urandom(32)
        plaintext = b"authenticated data"
        ad = b"additional-data"
        ct = _encrypt(key, 0, ad, plaintext)
        pt = _decrypt(key, 0, ad, ct)
        assert pt == plaintext

    def test_empty_key_passthrough(self):
        ct = _encrypt(EMPTY_KEY, 0, b"", b"plaintext")
        assert ct == b"plaintext"
        pt = _decrypt(EMPTY_KEY, 0, b"", b"plaintext")
        assert pt == b"plaintext"

    def test_dh_shared_secret(self):
        from cryptography.hazmat.primitives.asymmetric import x25519
        priv_a = x25519.X25519PrivateKey.generate()
        priv_b = x25519.X25519PrivateKey.generate()
        shared_ab = _dh(priv_a, priv_b.public_key())
        shared_ba = _dh(priv_b, priv_a.public_key())
        assert shared_ab == shared_ba

    def test_hkdf_produces_two_keys(self):
        k1, k2 = _hkdf(os.urandom(32), b"salt")
        assert len(k1) == 32
        assert len(k2) == 32
        assert k1 != k2


class TestNoiseHandshake:
    def test_full_xx_handshake(self):
        """Test the complete 3-message XX handshake pattern."""
        alice_id = AgentIdentity.generate("alice")
        bob_id = AgentIdentity.generate("bob")

        # Alice is initiator, Bob is responder
        alice_hs = NoiseHandshakeState(alice_id, is_initiator=True)
        bob_hs = NoiseHandshakeState(bob_id, is_initiator=False)

        # Message 1: Alice -> Bob (-> e)
        msg1 = alice_hs.write_message_1(b"")
        bob_hs.read_message_1(msg1)

        # Message 2: Bob -> Alice (<- e, ee, s, es)
        msg2 = bob_hs.write_message_2(b"")
        alice_hs.read_message_2(msg2)

        # Message 3: Alice -> Bob (-> s, se)
        msg3 = alice_hs.write_message_3(b"")
        bob_hs.read_message_3(msg3)

        # Both should be complete
        assert alice_hs.handshake_complete
        assert bob_hs.handshake_complete

        # Keys should be established (send/recv are swapped)
        assert alice_hs.send_key == bob_hs.recv_key
        assert alice_hs.recv_key == bob_hs.send_key

    def test_handshake_with_payload(self):
        """Test handshake carrying payload data."""
        alice = AgentIdentity.generate("alice")
        bob = AgentIdentity.generate("bob")

        alice_hs = NoiseHandshakeState(alice, is_initiator=True)
        bob_hs = NoiseHandshakeState(bob, is_initiator=False)

        msg1 = alice_hs.write_message_1(b"hello from alice")
        p1 = bob_hs.read_message_1(msg1)
        assert p1 == b"hello from alice"

        msg2 = bob_hs.write_message_2(b"hello from bob")
        p2 = alice_hs.read_message_2(msg2)
        assert p2 == b"hello from bob"

        msg3 = alice_hs.write_message_3(b"final payload")
        p3 = bob_hs.read_message_3(msg3)
        assert p3 == b"final payload"


class TestNoiseSession:
    def _create_session_pair(self):
        alice_id = AgentIdentity.generate("alice")
        bob_id = AgentIdentity.generate("bob")

        alice_hs = NoiseHandshakeState(alice_id, is_initiator=True)
        bob_hs = NoiseHandshakeState(bob_id, is_initiator=False)

        msg1 = alice_hs.write_message_1()
        bob_hs.read_message_1(msg1)
        msg2 = bob_hs.write_message_2()
        alice_hs.read_message_2(msg2)
        msg3 = alice_hs.write_message_3()
        bob_hs.read_message_3(msg3)

        alice_session = NoiseSession.from_handshake(alice_hs)
        bob_session = NoiseSession.from_handshake(bob_hs)
        return alice_session, bob_session

    def test_encrypt_decrypt(self):
        alice_s, bob_s = self._create_session_pair()
        ct = alice_s.encrypt(b"secret message")
        pt = bob_s.decrypt(ct)
        assert pt == b"secret message"

    def test_multiple_messages(self):
        alice_s, bob_s = self._create_session_pair()
        for i in range(10):
            msg = f"message-{i}".encode()
            ct = alice_s.encrypt(msg)
            pt = bob_s.decrypt(ct)
            assert pt == msg

    def test_bidirectional(self):
        alice_s, bob_s = self._create_session_pair()
        ct1 = alice_s.encrypt(b"from alice")
        pt1 = bob_s.decrypt(ct1)
        assert pt1 == b"from alice"

        ct2 = bob_s.encrypt(b"from bob")
        pt2 = alice_s.decrypt(ct2)
        assert pt2 == b"from bob"

    def test_rekey(self):
        alice_s, bob_s = self._create_session_pair()
        old_send = alice_s.send_key
        alice_s.rekey()
        bob_s.rekey()
        assert alice_s.send_key != old_send
        assert alice_s.send_nonce == 0

        # Should still work after rekey
        ct = alice_s.encrypt(b"after rekey")
        pt = bob_s.decrypt(ct)
        assert pt == b"after rekey"

    def test_from_incomplete_handshake_raises(self):
        identity = AgentIdentity.generate("test")
        hs = NoiseHandshakeState(identity, is_initiator=True)
        with pytest.raises(ValueError, match="not complete"):
            NoiseSession.from_handshake(hs)
