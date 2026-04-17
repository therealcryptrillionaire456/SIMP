"""
Basic security layer tests that verify core functionality works.

These tests focus on the essential security layer features that are needed
for Layer 4 trust graph foundation. They test that:
1. Dependencies are installed (cryptography, fastapi, uvicorn)
2. Basic encryption/decryption works
3. Basic signing/verification works
4. The security layer can be integrated with mesh components
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path

# Add the simp module to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_dependencies_installed():
    """Test that required dependencies are installed."""
    import cryptography
    import fastapi
    import uvicorn
    
    # Just importing them is enough to verify they're available
    assert cryptography.__version__ is not None
    assert fastapi.__version__ is not None
    assert uvicorn.__version__ is not None
    
    print(f"✓ Dependencies installed: cryptography={cryptography.__version__}, "
          f"fastapi={fastapi.__version__}, uvicorn={uvicorn.__version__}")


def test_security_layer_import():
    """Test that MeshSecurityLayer can be imported."""
    from simp.mesh.security import MeshSecurityLayer, get_mesh_security_layer
    
    assert MeshSecurityLayer is not None
    assert get_mesh_security_layer is not None
    
    print("✓ Security layer imports successfully")


def test_basic_encryption_decryption():
    """Test basic encryption and decryption."""
    from simp.mesh.security import get_mesh_security_layer
    
    # Create security layer
    security = get_mesh_security_layer(
        agent_id="test_basic_agent",
        private_key_path=None,
        public_key_path=None
    )
    
    # Test message
    plaintext = "Test message for encryption"
    
    # Encrypt
    ciphertext = security.encrypt_message(plaintext)
    
    assert ciphertext is not None
    assert isinstance(ciphertext, str)
    assert ciphertext != plaintext  # Should be encrypted
    
    # Decrypt
    decrypted = security.decrypt_message(ciphertext)
    
    assert decrypted == plaintext
    
    print(f"✓ Basic encryption/decryption works: {len(plaintext)} chars")


def test_basic_signing_verification():
    """Test basic message signing and verification."""
    from simp.mesh.security import get_mesh_security_layer
    
    security = get_mesh_security_layer(
        agent_id="test_signing_agent",
        private_key_path=None,
        public_key_path=None
    )
    
    # Test message
    message = "Message to sign"
    
    # Sign
    signature = security.sign_message(message)
    
    assert signature is not None
    assert isinstance(signature, str)
    
    # Get public key and register it
    public_key = security.get_public_key_pem()
    security.register_agent_public_key("test_signing_agent", public_key)
    
    # Verify
    is_valid = security.verify_signature(
        message=message,
        signature=signature,
        sender_id="test_signing_agent"
    )
    
    assert is_valid is True
    
    print(f"✓ Basic signing/verification works")


def test_security_layer_with_mesh_packet():
    """Test integrating security layer with MeshPacket."""
    from simp.mesh.security import get_mesh_security_layer
    from simp.mesh.packet import create_event_packet
    import json
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="security_test_"))
    
    try:
        # Create security layer
        security = get_mesh_security_layer(
            agent_id="packet_security_agent",
            private_key_path=None,
            public_key_path=None
        )
        
        # Create a packet
        packet = create_event_packet(
            sender_id="sender_agent",
            recipient_id="receiver_agent",
            channel="test_channel",
            payload={"data": "sensitive information", "count": 42}
        )
        
        # Convert packet payload to string for encryption
        payload_str = json.dumps(packet.payload)
        
        # Encrypt the payload
        ciphertext = security.encrypt_message(payload_str)
        
        # Verify we can decrypt it
        decrypted_str = security.decrypt_message(ciphertext)
        decrypted_payload = json.loads(decrypted_str)
        
        assert decrypted_payload == packet.payload
        
        print(f"✓ Security layer integrates with MeshPacket")
        
    finally:
        # Clean up
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def test_strict_mode_with_security():
    """
    Test that security layer works correctly with SIMP_STRICT_TESTS.
    
    This is the key test - it verifies that security layer tests
    are actually exercised and not silently skipped.
    """
    strict_mode = os.environ.get("SIMP_STRICT_TESTS") == "1"
    
    try:
        # Import security layer
        from simp.mesh.security import MeshSecurityLayer
        
        # If we get here, dependencies are available
        print("✓ Security layer available for strict mode testing")
        
        # Run a basic test
        assert MeshSecurityLayer is not None
        
        # In strict mode, we should also test that exceptions are properly raised
        if strict_mode:
            print("✓ Running in strict mode - exceptions will cause test failures")
            
            # Test that invalid operations raise exceptions
            from simp.mesh.security import get_mesh_security_layer
            security = get_mesh_security_layer(
                agent_id="strict_mode_test_agent",
                private_key_path=None,
                public_key_path=None
            )
            
            # This should raise an exception for invalid ciphertext
            import cryptography.fernet
            with pytest.raises(cryptography.fernet.InvalidToken):
                security.decrypt_message("invalid_ciphertext")
            
            print("✓ Strict mode correctly raises exceptions for invalid operations")
        
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
    print("=" * 60)
    print("Running Basic Security Layer Tests")
    print("=" * 60)
    
    # Run tests
    test_dependencies_installed()
    test_security_layer_import()
    test_basic_encryption_decryption()
    test_basic_signing_verification()
    test_security_layer_with_mesh_packet()
    
    print("=" * 60)
    print("✅ BASIC SECURITY LAYER TESTS PASSED")
    print("=" * 60)
    print("The security layer foundation is working correctly.")
    print("Layer 4 trust graph can be built on top of this foundation.")