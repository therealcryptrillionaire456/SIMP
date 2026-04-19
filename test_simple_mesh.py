#!/usr/bin/env python3
"""Simple test of mesh routing integration."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test imports
print("Testing imports...")
try:
    from simp.server.mesh_routing import MeshRoutingManager, MeshRoutingMode, init_mesh_routing
    print("✅ Mesh routing imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test creating mesh routing manager
print("\nTesting MeshRoutingManager creation...")
try:
    manager = MeshRoutingManager(broker_id="test_broker")
    print("✅ MeshRoutingManager created")
    
    # Test status
    status = manager.get_status()
    print(f"✅ Status retrieved: {status['mesh_enabled']}")
    
    # Test starting
    manager.start()
    print("✅ Mesh routing started")
    
    # Test agent registration
    manager.register_agent_mesh_capabilities(
        "test_agent", ["cap1", "cap2"], 1000.0
    )
    print("✅ Agent capabilities registered")
    
    # Test getting agents
    agents = manager.get_all_mesh_agents()
    print(f"✅ Mesh agents: {len(agents)}")
    
    # Test capability check
    can_route, reason = manager.can_route_via_mesh(
        "test_agent", "other_agent", "cap1"
    )
    print(f"✅ Capability check: {can_route} (reason: {reason})")
    
    # Test discovery
    discovery = manager.discover_mesh_capabilities()
    print(f"✅ Discovery: {discovery.get('success', False)}")
    
    # Stop
    manager.stop()
    print("✅ Mesh routing stopped")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ All mesh routing tests passed!")