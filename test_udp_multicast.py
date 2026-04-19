#!/usr/bin/env python3
"""
Test script for SIMP Mesh UDP Multicast Transport
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import json
from threading import Thread
from simp.mesh.transport.udp_multicast import (
    UdpMulticastTransport,
    UdpMessage,
    UdpMessageType,
    create_udp_multicast_transport
)

def test_basic_udp_transport():
    """Test basic UDP multicast functionality"""
    print("🧪 Testing UDP Multicast Transport")
    print("=" * 50)
    
    # Create two transport instances (simulating two agents)
    transport1 = create_udp_multicast_transport(
        multicast_group="239.255.255.250",
        multicast_port=9999,  # Use a different port to avoid conflicts
        agent_id="agent_alpha"
    )
    
    transport2 = create_udp_multicast_transport(
        multicast_group="239.255.255.250",
        multicast_port=9999,
        agent_id="agent_beta"
    )
    
    received_messages = []
    
    def message_handler(message):
        print(f"📨 Received message: {message.message_type} from {message.sender_id}")
        received_messages.append(message)
    
    # Set up message handlers
    transport1.set_message_callback(message_handler)
    transport2.set_message_callback(message_handler)
    
    try:
        # Start both transports
        print("🚀 Starting transports...")
        if not transport1.start():
            print("❌ Failed to start transport1")
            return False
        if not transport2.start():
            print("❌ Failed to start transport2")
            return False
        
        print("✅ Transports started successfully")
        time.sleep(1)  # Give them time to initialize
        
        # Test 1: Broadcast discovery
        print("\n🔍 Test 1: Broadcasting discovery...")
        transport1.broadcast_discovery(
            endpoint="http://127.0.0.1:5555",
            capabilities=["trading", "analysis"]
        )
        time.sleep(2)
        
        # Test 2: Send mesh packet
        print("\n📦 Test 2: Sending mesh packet...")
        mesh_packet = {
            "type": "intent",
            "sender": "agent_alpha",
            "recipient": "agent_beta",
            "payload": {"action": "ping", "timestamp": time.time()},
            "id": "test_packet_001"
        }
        transport1.broadcast_mesh_packet(mesh_packet)
        time.sleep(2)
        
        # Test 3: Direct message
        print("\n💬 Test 3: Sending direct message...")
        direct_msg = UdpMessage(
            message_type=UdpMessageType.DIRECT_MESSAGE,
            sender_id="agent_alpha",
            recipient_id="agent_beta",
            payload={"text": "Hello from Alpha!"},
            timestamp=time.time()
        )
        transport1.send_message(direct_msg)
        time.sleep(2)
        
        # Check results
        print("\n📊 Test Results:")
        print(f"Total messages received: {len(received_messages)}")
        
        if len(received_messages) > 0:
            print("✅ UDP multicast is working!")
            for i, msg in enumerate(received_messages[:3]):  # Show first 3 messages
                print(f"  {i+1}. {msg.message_type.name} from {msg.sender_id}")
        else:
            print("❌ No messages received - check firewall/multicast settings")
            print("   On macOS/Linux, you may need to run with sudo or adjust firewall")
        
        # Show statistics
        print("\n📈 Transport Statistics:")
        stats1 = transport1.get_statistics()
        stats2 = transport2.get_statistics()
        print(f"Transport 1: {stats1}")
        print(f"Transport 2: {stats2}")
        
        return len(received_messages) > 0
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        transport1.stop()
        transport2.stop()
        time.sleep(0.5)

def test_mesh_integration():
    """Test integration with MeshBus"""
    print("\n" + "=" * 50)
    print("🔗 Testing Mesh Integration")
    print("=" * 50)
    
    try:
        from simp.mesh.bus import get_mesh_bus
        from simp.mesh.packet import MeshPacket, MessageType
        
        print("🚀 Creating MeshBus instance...")
        mesh_bus = get_mesh_bus()
        
        # Register test agents
        print("👥 Registering test agents...")
        mesh_bus.register_agent("test_agent_1")
        mesh_bus.register_agent("test_agent_2")
        
        # Create and send a test packet
        print("📤 Sending test packet...")
        test_packet = MeshPacket(
            packet_type=MessageType.DIRECT,
            sender="test_agent_1",
            recipient="test_agent_2",
            payload={"test": "data", "timestamp": time.time()},
            message_id="test_001"
        )
        
        success = mesh_bus.send(test_packet)
        print(f"📬 Send result: {'✅ Success' if success else '❌ Failed'}")
        
        # Try to receive
        print("📥 Attempting to receive...")
        received = mesh_bus.receive("test_agent_2", max_messages=1)
        print(f"📭 Received {len(received)} messages")
        
        if received:
            print("✅ MeshBus core is working!")
            packet = received[0]
            print(f"   From: {packet.sender}")
            print(f"   Type: {packet.packet_type}")
            print(f"   Payload: {packet.payload}")
        
        # Show statistics
        stats = mesh_bus.get_statistics()
        print(f"\n📊 MeshBus Statistics: {stats}")
        
        return success and len(received) > 0
        
    except Exception as e:
        print(f"❌ Mesh integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧪 SIMP Mesh Transport Test Suite")
    print("=" * 60)
    
    # Test UDP multicast
    udp_success = test_basic_udp_transport()
    
    # Test Mesh integration
    mesh_success = test_mesh_integration()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    print(f"UDP Multicast Transport: {'✅ PASS' if udp_success else '❌ FAIL'}")
    print(f"MeshBus Integration: {'✅ PASS' if mesh_success else '❌ FAIL'}")
    
    if udp_success and mesh_success:
        print("\n🎉 All tests passed! Mesh system is operational.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Check configuration and firewall settings.")
        print("   For UDP multicast on macOS/Linux:")
        print("   - Try running with sudo")
        print("   - Check firewall: sudo ufw allow 1900/udp")
        print("   - Verify multicast routing")
        return 1

if __name__ == "__main__":
    sys.exit(main())