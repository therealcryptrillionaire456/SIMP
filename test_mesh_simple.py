#!/usr/bin/env python3
"""
Simple test for SIMP Mesh components
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
from simp.mesh.bus import get_mesh_bus
from simp.mesh.packet import MeshPacket, MessageType

def test_mesh_bus_basic():
    """Test basic MeshBus functionality"""
    print("🧪 Testing MeshBus Basic Functionality")
    print("=" * 50)
    
    try:
        # Get mesh bus instance
        mesh_bus = get_mesh_bus()
        print("✅ MeshBus instance created")
        
        # Register agents
        mesh_bus.register_agent("test_sender")
        mesh_bus.register_agent("test_receiver")
        print("✅ Agents registered")
        
        # Create a test packet
        test_packet = MeshPacket(
            msg_type=MessageType.EVENT,
            sender_id="test_sender",
            recipient_id="test_receiver",
            payload={"action": "test", "data": "Hello Mesh!", "timestamp": time.time()},
            message_id=f"test_{int(time.time())}"
        )
        print(f"✅ Test packet created: {test_packet.message_id}")
        
        # Send the packet
        success = mesh_bus.send(test_packet)
        print(f"📤 Send result: {'✅ Success' if success else '❌ Failed'}")
        
        # Try to receive
        received = mesh_bus.receive("test_receiver", max_messages=1)
        print(f"📥 Received {len(received)} messages")
        
        if received:
            packet = received[0]
            print("✅ Message received successfully!")
            print(f"   From: {packet.sender_id}")
            print(f"   Type: {packet.msg_type}")
            print(f"   ID: {packet.message_id}")
            print(f"   Payload: {packet.payload}")
        
        # Get statistics
        stats = mesh_bus.get_statistics()
        print(f"\n📊 MeshBus Statistics:")
        print(f"   Agents: {stats.get('agent_count', 0)}")
        print(f"   Messages sent: {stats.get('messages_sent', 0)}")
        print(f"   Messages delivered: {stats.get('messages_delivered', 0)}")
        print(f"   Pending messages: {stats.get('pending_messages', 0)}")
        
        return success and len(received) > 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enhanced_features():
    """Test enhanced mesh features"""
    print("\n" + "=" * 50)
    print("🚀 Testing Enhanced Mesh Features")
    print("=" * 50)
    
    try:
        from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
        
        # Get enhanced mesh bus
        enhanced_bus = get_enhanced_mesh_bus()
        print("✅ EnhancedMeshBus instance created")
        
        # Register agent with enhanced bus
        enhanced_bus.register_agent("enhanced_agent")
        print("✅ Agent registered with enhanced bus")
        
        # Update heartbeat
        enhanced_bus.update_agent_heartbeat("enhanced_agent")
        print("✅ Heartbeat updated")
        
        # Get agent status
        status = enhanced_bus.get_agent_status("enhanced_agent")
        print(f"✅ Agent status: {status}")
        
        # Get statistics
        stats = enhanced_bus.get_statistics()
        print(f"\n📊 EnhancedMeshBus Statistics:")
        print(f"   Agents: {stats.get('agent_count', 0)}")
        print(f"   Offline storage: {stats.get('offline_storage_stats', {}).get('total_messages', 0)}")
        print(f"   Delivery receipts: {stats.get('receipt_stats', {}).get('total_receipts', 0)}")
        
        print("\n✅ Enhanced features are available!")
        return True
        
    except Exception as e:
        print(f"⚠️ Enhanced features test: {e}")
        print("   (This is okay - enhanced features may require additional setup)")
        return False

def main():
    """Run all tests"""
    print("🧪 SIMP Mesh System Test")
    print("=" * 60)
    
    # Test basic mesh bus
    basic_success = test_mesh_bus_basic()
    
    # Test enhanced features
    enhanced_success = test_enhanced_features()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    print(f"MeshBus Core: {'✅ PASS' if basic_success else '❌ FAIL'}")
    print(f"Enhanced Features: {'✅ AVAILABLE' if enhanced_success else '⚠️ LIMITED'}")
    
    if basic_success:
        print("\n🎉 Mesh system core is operational!")
        print("   Next steps:")
        print("   1. Test UDP multicast transport (may require sudo)")
        print("   2. Integrate with SIMP broker")
        print("   3. Set up mesh security layer")
        return 0
    else:
        print("\n⚠️ Core mesh tests failed. Check installation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())