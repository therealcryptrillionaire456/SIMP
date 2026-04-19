"""
Comprehensive tests for the Mesh Security Layer.

Tests the cryptography, fastapi, and uvicorn dependencies that are required
for the security layer to function properly. These tests ensure that the
security layer is actually exercised before building Layer 4 on top of it.
"""

import os
import sys
import pytest
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Add the simp module to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test imports to ensure dependencies are available
def test_dependencies_available():
    """Test that required dependencies are installed."""
    import cryptography
    import fastapi
    import uvicorn
    
    # Verify versions
    print(f"cryptography version: {cryptography.__version__}")
    print(f"fastapi version: {fastapi.__version__}")
    print(f"uvicorn version: {uvicorn.__version__}")
    
    assert cryptography.__version__ is not None
    assert fastapi.__version__ is not None
    assert uvicorn.__version__ is not None


class TestMeshSecurityLayerBasic:
    """Basic tests for MeshSecurityLayer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary directory for test data
        self.temp_dir = tempfile.mkdtemp(prefix="mesh_security_test_")
        self.data_dir = Path(self.temp_dir) / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Save original environment
        self.original_env = os.environ.copy()
        
    def teardown_method(self):
        """Clean up test fixtures."""
        # Restore environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_security_layer_import(self):
        """Test that MeshSecurityLayer can be imported."""
        from simp.mesh.security import MeshSecurityLayer, get_mesh_security_layer
        
        assert MeshSecurityLayer is not None
        assert get_mesh_security_layer is not None
        
        print("✓ MeshSecurityLayer imports successfully")
    
    def test_security_layer_creation(self):
        """Test creating a MeshSecurityLayer instance."""
        from simp.mesh.security import get_mesh_security_layer
        
        # Create directory if it doesn't exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create security layer - pass None to generate new keys
        security = get_mesh_security_layer(
            agent_id="test_agent_1",
            private_key_path=None,
            public_key_path=None
        )
        
        assert security is not None
        assert hasattr(security, 'get_public_key_pem')
        assert hasattr(security, 'encrypt_message')
        assert hasattr(security, 'decrypt_message')
        
        print("✓ MeshSecurityLayer instance created successfully")
    
    def test_public_key_generation(self):
        """Test public key generation."""
        from simp.mesh.security import get_mesh_security_layer
        
        security = get_mesh_security_layer(
            agent_id="test_agent_2",
            private_key_path=None,
            public_key_path=None
        )
        
        public_key = security.get_public_key_pem()
        
        # Public key should be a PEM-formatted string
        assert public_key is not None
        assert isinstance(public_key, str)
        assert "-----BEGIN PUBLIC KEY-----" in public_key
        assert "-----END PUBLIC KEY-----" in public_key
        
        print(f"✓ Public key generated: {len(public_key)} bytes")
    
    def test_encryption_decryption(self):
        """Test message encryption and decryption."""
        from simp.mesh.security import get_mesh_security_layer
        
        security = get_mesh_security_layer(
            agent_id="test_agent_3",
            private_key_path=None,
            public_key_path=None
        )
        
        # Test message
        plaintext = "This is a secret message for testing"
        
        # Encrypt
        ciphertext = security.encrypt_message(plaintext)
        
        assert ciphertext is not None
        assert isinstance(ciphertext, str)
        assert ciphertext != plaintext  # Should be encrypted
        
        # Decrypt
        decrypted = security.decrypt_message(ciphertext)
        
        assert decrypted == plaintext
        
        print(f"✓ Encryption/decryption successful: {len(plaintext)} chars")
    
    def test_message_signing_verification(self):
        """Test message signing and verification."""
        from simp.mesh.security import get_mesh_security_layer
        
        security = get_mesh_security_layer(
            agent_id="test_agent_4",
            private_key_path=None,
            public_key_path=None
        )
        
        # Test message
        message = "This message needs to be signed"
        
        # Sign
        signature = security.sign_message(message)
        
        assert signature is not None
        assert isinstance(signature, str)
        
        # Get public key and register it for verification
        public_key = security.get_public_key_pem()
        security.register_agent_public_key("test_agent_4", public_key)
        
        # Verify
        is_valid = security.verify_signature(
            message=message,
            signature=signature,
            sender_id="test_agent_4"
        )
        
        assert is_valid is True
        
        # Test with wrong sender (should fail - no public key registered)
        is_valid_wrong = security.verify_signature(
            message=message,
            signature=signature,
            sender_id="wrong_agent"
        )
        
        assert is_valid_wrong is False
        
        print(f"✓ Message signing/verification successful")
    
    def test_secure_message_workflow(self):
        """Test the complete secure message workflow."""
        from simp.mesh.security import get_mesh_security_layer
        
        # Create sender security layer
        sender_security = get_mesh_security_layer(
            agent_id="sender_agent",
            private_key_path=None,
            public_key_path=None
        )
        
        # Create receiver security layer  
        receiver_security = get_mesh_security_layer(
            agent_id="receiver_agent",
            private_key_path=None,
            public_key_path=None
        )
        
        # Exchange public keys
        sender_public_key = sender_security.get_public_key_pem()
        receiver_public_key = receiver_security.get_public_key_pem()
        
        # Register keys with each other
        sender_security.register_agent_public_key("receiver_agent", receiver_public_key)
        receiver_security.register_agent_public_key("sender_agent", sender_public_key)
        
        # Create a message to send
        plaintext_message = "Confidential data for receiver"
        
        # Create message dict
        message = {
            "message_id": "test_msg_123",
            "source_agent": "sender_agent",
            "target_agent": "receiver_agent",
            "payload": {"data": plaintext_message},
            "channel": "secure_channel"
        }
        
        # Secure the message
        from simp.mesh.security import SecurityLevel
        secured_message = sender_security.secure_message(
            message=message,
            recipient_id="receiver_agent",
            channel="secure_channel",
            security_level=SecurityLevel.ENCRYPTED
        )
        
        assert secured_message is not None
        assert isinstance(secured_message, dict)
        assert "payload" in secured_message  # Encrypted payload is in 'payload' field
        assert "signature" in secured_message
        assert "security_level" in secured_message
        assert secured_message.get("encrypted") is True
        
        # Verify the message
        is_valid, error_message = receiver_security.verify_message(secured_message)
        
        assert is_valid is True, f"Message verification failed: {error_message}"
        # The decrypted payload should be placed back in the message dict
        assert "payload" in secured_message
        assert isinstance(secured_message["payload"], dict)
        assert secured_message["payload"].get("data") == plaintext_message
        assert secured_message.get("encrypted") is False  # Should be decrypted now
        
        print(f"✓ Complete secure message workflow successful")


class TestMeshSecurityLayerAdvanced:
    """Advanced tests for MeshSecurityLayer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp(prefix="mesh_security_advanced_")
        self.data_dir = Path(self.temp_dir) / "data"
        self.data_dir.mkdir(exist_ok=True)
        
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_policy_management(self):
        """Test security policy creation and management."""
        from simp.mesh.security import get_mesh_security_layer
        
        security = get_mesh_security_layer(
            agent_id="policy_test_agent",
            private_key_path=None,
            public_key_path=None
        )
        
        # Create a policy
        policy_key = security.create_policy(
            agent_id="allowed_agent",
            channel="test_channel",
            can_send=True,
            can_receive=True,
            can_broadcast=False,
            max_message_size=1024,
            allowed_message_types=["event", "system"],
            security_level="high"
        )
        
        assert policy_key is not None
        assert isinstance(policy_key, str)
        
        # Get the policy
        policy = security.get_policy("allowed_agent", "test_channel")
        
        assert policy is not None
        assert policy.agent_id == "allowed_agent"
        assert policy.channel == "test_channel"
        assert policy.can_send is True
        assert policy.can_receive is True
        assert policy.can_broadcast is False
        
        print(f"✓ Policy management successful: {policy_key}")
    
    def test_access_control(self):
        """Test access control checks."""
        from simp.mesh.security import get_mesh_security_layer
        
        security = get_mesh_security_layer(
            agent_id="access_test_agent",
            private_key_path=None,
            public_key_path=None
        )
        
        # Create a policy that allows sending
        security.create_policy(
            agent_id="sender_agent",
            channel="test_channel",
            can_send=True,
            can_receive=True
        )
        
        # Create a policy that denies sending
        security.create_policy(
            agent_id="blocked_agent",
            channel="test_channel",
            can_send=False,
            can_receive=False
        )
        
        # Check access for allowed sender
        can_send_allowed = security.check_access(
            sender_id="sender_agent",
            recipient_id="access_test_agent",
            channel="test_channel",
            operation="send"
        )
        
        assert can_send_allowed is True
        
        # Check access for blocked sender
        can_send_blocked = security.check_access(
            sender_id="blocked_agent",
            recipient_id="access_test_agent",
            channel="test_channel",
            operation="send"
        )
        
        assert can_send_blocked is False
        
        print(f"✓ Access control checks successful")
    
    def test_audit_logging(self):
        """Test audit logging functionality."""
        from simp.mesh.security import get_mesh_security_layer
        
        security = get_mesh_security_layer(
            agent_id="audit_test_agent",
            private_key_path=None,
            public_key_path=None
        )
        
        # Perform some operations that should generate audit logs
        security.encrypt_message("test audit message")
        
        # Get audit log
        audit_log = security.get_audit_log(limit=10)
        
        assert audit_log is not None
        assert isinstance(audit_log, list)
        
        # Should have at least one audit entry
        assert len(audit_log) >= 1
        
        # Check audit entry structure
        entry = audit_log[0]
        assert "timestamp" in entry
        assert "agent_id" in entry
        assert "operation" in entry
        
        print(f"✓ Audit logging successful: {len(audit_log)} entries")
    
    def test_statistics(self):
        """Test statistics collection."""
        from simp.mesh.security import get_mesh_security_layer
        
        security = get_mesh_security_layer(
            agent_id="stats_test_agent",
            private_key_path=None,
            public_key_path=None
        )
        
        # Perform some operations
        security.encrypt_message("message 1")
        security.encrypt_message("message 2")
        security.decrypt_message("dummy_ciphertext")  # Will fail but count
        
        # Get statistics
        stats = security.get_statistics()
        
        assert stats is not None
        assert isinstance(stats, dict)
        
        # Check expected statistics fields
        assert "operations" in stats
        assert "encryption_count" in stats.get("operations", {})
        assert "decryption_count" in stats.get("operations", {})
        
        print(f"✓ Statistics collection successful: {stats}")


class TestMeshSecurityIntegration:
    """Integration tests for MeshSecurityLayer with other components."""
    
    def test_with_mesh_packet(self):
        """Test integrating security layer with MeshPacket."""
        from simp.mesh.security import get_mesh_security_layer
        from simp.mesh.packet import MeshPacket, MessageType, create_event_packet
        
        # Create security layer
        temp_dir = Path(tempfile.mkdtemp(prefix="mesh_packet_test_"))
        security = get_mesh_security_layer(
            agent_id="packet_test_agent",
            private_key_path=str(temp_dir / "private_key.pem"),
            public_key_path=str(temp_dir / "public_key.pem")
        )
        
        # Create a packet
        packet = create_event_packet(
            sender_id="sender_agent",
            recipient_id="receiver_agent",
            channel="secure_channel",
            payload={"data": "sensitive information"}
        )
        
        # Convert packet payload to string for encryption
        payload_str = json.dumps(packet.payload)
        
        # Encrypt the payload
        ciphertext = security.encrypt_message(payload_str)
        
        # Create secured packet
        secured_packet = MeshPacket(
            msg_type=MessageType.EVENT,
            sender_id=packet.sender_id,
            recipient_id=packet.recipient_id,
            channel=packet.channel,
            payload={"ciphertext": ciphertext, "secured": True},
            correlation_id=packet.correlation_id,
            priority=packet.priority,
            ttl_seconds=packet.ttl_seconds,
            meta={"security": "encrypted"}
        )
        
        assert secured_packet is not None
        assert secured_packet.payload["secured"] is True
        assert "ciphertext" in secured_packet.payload
        
        print(f"✓ MeshPacket integration successful")
    
    def test_with_smart_client(self):
        """Test integrating security layer with SmartMeshClient."""
        from simp.mesh.security import get_mesh_security_layer
        from simp.mesh.smart_client import SmartMeshClient
        from unittest.mock import Mock
        
        # Create security layer
        temp_dir = Path(tempfile.mkdtemp(prefix="mesh_client_test_"))
        security = get_mesh_security_layer(
            agent_id="client_test_agent",
            private_key_path=str(temp_dir / "private_key.pem"),
            public_key_path=str(temp_dir / "public_key.pem")
        )
        
        # Create mock client
        client = SmartMeshClient(
            agent_id="client_test_agent",
            broker_url="http://localhost:5555",
            mesh_bus_url="http://localhost:6666"
        )
        
        # Mock the security layer on the client
        # (In a real implementation, the client would have a security layer attribute)
        client._security_layer = security
        
        assert client._security_layer is not None
        assert hasattr(client._security_layer, 'encrypt_message')
        assert hasattr(client._security_layer, 'decrypt_message')
        
        print(f"✓ SmartMeshClient integration setup successful")


def test_strict_mode_with_security():
    """
    Test that security layer tests work correctly with SIMP_STRICT_TESTS.
    
    This test demonstrates that security layer tests should not be skipped
    silently when dependencies are missing.
    """
    strict_mode = os.environ.get("SIMP_STRICT_TESTS") == "1"
    
    # In strict mode, missing dependencies should cause test failures
    # In normal mode, they might be skipped with warnings
    
    try:
        # Try to import security layer
        from simp.mesh.security import MeshSecurityLayer
        
        # If we get here, dependencies are available
        print("✓ Security layer dependencies available")
        
        # Run a simple test
        assert MeshSecurityLayer is not None
        
    except ImportError as e:
        error_msg = str(e)
        
        if strict_mode:
            # In strict mode, re-raise the import error
            raise ImportError(f"STRICT MODE: Missing dependency for security layer: {error_msg}")
        else:
            # In normal mode, skip with warning
            pytest.skip(f"Missing dependency for security layer: {error_msg}")


if __name__ == "__main__":
    """Run tests directly."""
    import unittest
    
    # Run basic tests
    print("=" * 60)
    print("Running Mesh Security Layer Tests")
    print("=" * 60)
    
    # Test dependencies first
    try:
        test_dependencies_available()
        print("✓ All dependencies available")
    except ImportError as e:
        print(f"✗ Missing dependencies: {e}")
        print("Please run: pip install cryptography fastapi uvicorn")
        sys.exit(1)
    
    # Run test suites
    suites = [
        unittest.TestLoader().loadTestsFromTestCase(TestMeshSecurityLayerBasic),
        unittest.TestLoader().loadTestsFromTestCase(TestMeshSecurityLayerAdvanced),
    ]
    
    all_passed = True
    for suite in suites:
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        if not result.wasSuccessful():
            all_passed = False
    
    if all_passed:
        print("=" * 60)
        print("✅ ALL MESH SECURITY LAYER TESTS PASSED")
        print("=" * 60)
    else:
        print("=" * 60)
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        sys.exit(1)