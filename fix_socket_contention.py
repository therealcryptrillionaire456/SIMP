#!/usr/bin/env python3
"""
Fix for multicast socket contention in mesh discovery.
Addresses Errno 48: Address already in use when multiple discovery instances run.
"""

import socket
import struct
import logging

logger = logging.getLogger(__name__)

def create_multicast_socket_fixed(multicast_group: str = "239.0.0.1", 
                                 multicast_port: int = 5007,
                                 reuse_port: bool = True) -> socket.socket:
    """
    Create multicast socket with proper reuse options to avoid contention.
    
    Args:
        multicast_group: Multicast group address
        multicast_port: Multicast port
        reuse_port: Enable SO_REUSEPORT for multiple listeners on same port
    
    Returns:
        Configured socket or None on error
    """
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        # Allow multiple processes to bind to the same address
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # On systems that support it, allow multiple processes to bind to same port
        if reuse_port and hasattr(socket, 'SO_REUSEPORT'):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                logger.debug("SO_REUSEPORT enabled")
            except (AttributeError, OSError) as e:
                logger.debug(f"SO_REUSEPORT not available: {e}")
        
        # Bind to all interfaces on the multicast port
        sock.bind(('', multicast_port))
        
        # Join multicast group
        group = socket.inet_aton(multicast_group)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        # Set timeout for non-blocking receive
        sock.settimeout(1.0)
        
        # Set socket to non-blocking mode
        sock.setblocking(0)
        
        logger.info(f"Multicast socket created on {multicast_group}:{multicast_port}")
        return sock
        
    except OSError as e:
        if e.errno == 48:  # Address already in use
            logger.warning(f"Address already in use. Another process may be listening.")
            logger.warning("Try one of these solutions:")
            logger.warning("1. Ensure only one discovery service per machine")
            logger.warning("2. Use different ports for different services")
            logger.warning("3. Use SO_REUSEPORT if supported by your OS")
        logger.error(f"Failed to create multicast socket: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating multicast socket: {e}")
        return None

def patch_discovery_service():
    """
    Patch the MeshDiscoveryService to use the fixed socket creation.
    """
    import simp.mesh.discovery as discovery_module
    
    # Monkey patch the _create_multicast_socket method
    original_method = discovery_module.MeshDiscoveryService._create_multicast_socket
    
    def patched_create_multicast_socket(self):
        """Patched version with better socket reuse handling."""
        try:
            sock = create_multicast_socket_fixed(
                multicast_group=self.MULTICAST_GROUP,
                multicast_port=self.MULTICAST_PORT,
                reuse_port=True
            )
            return sock
        except Exception as e:
            logger.error(f"Patched socket creation failed: {e}")
            # Fall back to original method
            return original_method(self)
    
    # Apply the patch
    discovery_module.MeshDiscoveryService._create_multicast_socket = patched_create_multicast_socket
    logger.info("MeshDiscoveryService patched with improved socket handling")

def check_socket_usage():
    """
    Check which processes are using the multicast port.
    """
    import subprocess
    import sys
    
    port = 5007  # Default multicast port
    
    print(f"Checking processes using port {port}...")
    
    # macOS/Linux
    if sys.platform == 'darwin' or sys.platform.startswith('linux'):
        try:
            result = subprocess.run(
                ['lsof', '-i', f':{port}'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                print("Processes using port 5007:")
                print(result.stdout)
            else:
                print(f"No processes found using port {port}")
        except FileNotFoundError:
            print("lsof not available. Install with: brew install lsof (macOS) or apt-get install lsof (Linux)")
    
    # Windows
    elif sys.platform == 'win32':
        try:
            result = subprocess.run(
                ['netstat', '-ano', '|', 'findstr', f':{port}'],
                capture_output=True,
                text=True,
                shell=True
            )
            if result.stdout:
                print("Processes using port 5007:")
                print(result.stdout)
            else:
                print(f"No processes found using port {port}")
        except Exception as e:
            print(f"Error checking port usage: {e}")

def create_singleton_discovery_service():
    """
    Create a singleton pattern for discovery service to prevent multiple instances.
    """
    from simp.mesh.discovery import get_mesh_discovery_service
    
    # Global singleton instance
    _discovery_singleton = None
    
    def get_singleton_discovery_service(local_agent_id: str, 
                                       local_endpoint: str,
                                       broker_url: str = "http://127.0.0.1:5555",
                                       enable_multicast: bool = True):
        """Get or create singleton discovery service."""
        nonlocal _discovery_singleton
        
        if _discovery_singleton is None:
            _discovery_singleton = get_mesh_discovery_service(
                local_agent_id=local_agent_id,
                local_endpoint=local_endpoint,
                broker_url=broker_url,
                enable_multicast=enable_multicast
            )
            logger.info(f"Created singleton discovery service for {local_agent_id}")
        elif _discovery_singleton.local_agent_id != local_agent_id:
            logger.warning(f"Discovery service already exists for {_discovery_singleton.local_agent_id}")
            logger.warning(f"Requested for {local_agent_id} - returning existing instance")
        
        return _discovery_singleton
    
    return get_singleton_discovery_service

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("MULTICAST SOCKET CONTENTION FIX")
    print("=" * 60)
    
    print("\n1. Checking current socket usage...")
    check_socket_usage()
    
    print("\n2. Testing fixed socket creation...")
    sock = create_multicast_socket_fixed()
    if sock:
        print("✅ Socket created successfully")
        sock.close()
    else:
        print("❌ Socket creation failed")
    
    print("\n3. Patch options:")
    print("   a) Apply patch automatically: patch_discovery_service()")
    print("   b) Use singleton pattern: get_singleton_discovery_service()")
    print("   c) Manual fix: Update _create_multicast_socket in discovery.py")
    
    print("\n4. Recommended solution:")
    print("   - Use singleton pattern for discovery service")
    print("   - Add SO_REUSEPORT where supported")
    print("   - Ensure proper cleanup in stop() method")
    
    print("\n" + "=" * 60)
    print("QUICK FIX FOR ACTIVE DEVELOPMENT:")
    print("=" * 60)
    print("""
# Add to your activation script:
from fix_socket_contention import patch_discovery_service
patch_discovery_service()

# Or use singleton pattern:
from fix_socket_contention import create_singleton_discovery_service
get_discovery = create_singleton_discovery_service()
discovery = get_discovery("your_agent_id", "http://localhost:port")
    """)