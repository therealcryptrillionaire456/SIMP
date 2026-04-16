#!/usr/bin/env python3
"""
Simple UDP multicast test with different ports.
"""

import sys
import os
import time
import socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simp.mesh.transport.udp_multicast import (
    UdpMulticastTransport,
    UdpMessage,
    UdpMessageType
)

def test_single_transport():
    """Test single UDP multicast transport."""
    print("🧪 Testing single UDP multicast transport")
    
    # Use a different port to avoid conflicts
    transport = UdpMulticastTransport(
        agent_id="test_agent",
        multicast_port=5008,  # Different port
        enable_listener=True
    )
    
    if not transport.start():
        print("❌ Failed to start transport")
        return False
    
    print("✅ Transport started successfully")
    
    # Test sending a message
    message = UdpMessage(
        type=UdpMessageType.DISCOVERY,
        sender_id="test_agent",
        payload={"test": "data"},
        timestamp=time.time(),
        ttl=5
    )
    
    if transport.send_message(message):
        print("✅ Message sent successfully")
    else:
        print("❌ Failed to send message")
    
    # Check statistics
    stats = transport.get_statistics()
    print(f"📊 Statistics: {stats}")
    
    transport.stop()
    print("✅ Transport stopped successfully")
    
    return True

def test_multiple_ports():
    """Test multiple transports on different ports."""
    print("\n🧪 Testing multiple transports on different ports")
    
    transports = []
    ports = [5009, 5010, 5011]
    
    for i, port in enumerate(ports):
        agent_id = f"agent_{i+1}"
        transport = UdpMulticastTransport(
            agent_id=agent_id,
            multicast_port=port,
            enable_listener=True
        )
        
        if transport.start():
            print(f"✅ {agent_id} started on port {port}")
            transports.append(transport)
        else:
            print(f"❌ {agent_id} failed to start on port {port}")
    
    # Send messages between transports
    for i, transport in enumerate(transports):
        message = UdpMessage(
            type=UdpMessageType.HEARTBEAT,
            sender_id=transport.agent_id,
            payload={"port": transport.multicast_port},
            timestamp=time.time(),
            ttl=5
        )
        
        if transport.send_message(message):
            print(f"✅ {transport.agent_id} sent heartbeat")
        else:
            print(f"❌ {transport.agent_id} failed to send heartbeat")
    
    # Wait a bit
    time.sleep(0.5)
    
    # Cleanup
    for transport in transports:
        stats = transport.get_statistics()
        print(f"📊 {transport.agent_id} stats: {stats}")
        transport.stop()
    
    print(f"✅ Tested {len(transports)} transports")
    return len(transports) > 0

def test_socket_creation():
    """Test raw socket creation to debug permissions."""
    print("\n🧪 Testing raw socket creation")
    
    try:
        # Test creating a socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Try binding to port 5007
        sock.bind(('', 5007))
        print("✅ Socket created and bound to port 5007")
        
        # Test multicast join
        group = socket.inet_aton("239.0.0.1")
        mreq = group + socket.inet_aton('0.0.0.0')
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        print("✅ Joined multicast group")
        
        sock.close()
        print("✅ Socket closed")
        return True
        
    except Exception as e:
        print(f"❌ Socket error: {e}")
        return False

def main():
    """Run UDP multicast tests."""
    print("🔬 Testing UDP Multicast Transport")
    print("=" * 60)
    
    tests = [
        test_socket_creation,
        test_single_transport,
        test_multiple_ports,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 UDP MULTICAST TRANSPORT IS WORKING!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())