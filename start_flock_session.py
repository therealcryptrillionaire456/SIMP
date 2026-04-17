#!/usr/bin/env python3
"""
Start the mesh protocol flock session.
Registers geese for each layer and begins coordination.
"""

import json
import time
import requests
from typing import Dict, List, Any
from mother_goose_dashboard import get_mother_goose, GooseStatus

def register_layer1_geese(mother_goose):
    """Register geese for Layer 1 verification."""
    print("Registering geese for Layer 1 (Physical Transport) verification...")
    
    # Goose 1: UDP multicast verification
    mother_goose.register_goose(
        goose_id="goose_udp_verifier",
        layer=1,
        description="Verify UDP multicast implementation and create integration tests",
        files_to_touch=[
            "tests/test_udp_multicast_integration.py",
            "simp/mesh/transport/udp_multicast.py"
        ],
        dependencies=[]
    )
    
    # Goose 2: BLE transport verification
    mother_goose.register_goose(
        goose_id="goose_ble_verifier",
        layer=1,
        description="Verify BLE transport implementation and create integration tests",
        files_to_touch=[
            "tests/test_ble_transport_integration.py",
            "simp/transport/ble_transport.py"
        ],
        dependencies=[]
    )
    
    # Goose 3: Nostr transport verification
    mother_goose.register_goose(
        goose_id="goose_nostr_verifier",
        layer=1,
        description="Verify Nostr transport implementation and create integration tests",
        files_to_touch=[
            "tests/test_nostr_transport_integration.py",
            "simp/transport/nostr_transport.py"
        ],
        dependencies=[]
    )
    
    print("✓ Registered 3 geese for Layer 1 verification")

def register_layer3_geese(mother_goose):
    """Register geese for Layer 3 (Intent Routing Protocol)."""
    print("\nRegistering geese for Layer 3 (Intent Routing Protocol)...")
    
    # Goose 4: IntentMeshRouter implementation
    mother_goose.register_goose(
        goose_id="goose_intent_router",
        layer=3,
        description="Implement IntentMeshRouter for mesh-based intent routing",
        files_to_touch=[
            "simp/mesh/intent_router.py",
            "tests/test_intent_router.py"
        ],
        dependencies=["goose_udp_verifier", "goose_ble_verifier", "goose_nostr_verifier"]
    )
    
    # Goose 5: Capability gossip integration
    mother_goose.register_goose(
        goose_id="goose_capability_gossip",
        layer=3,
        description="Implement capability gossip system for mesh routing",
        files_to_touch=[
            "simp/mesh/capability_gossip.py",
            "tests/test_capability_gossip.py"
        ],
        dependencies=["goose_intent_router"]
    )
    
    # Goose 6: Mesh routing for SIMP intents
    mother_goose.register_goose(
        goose_id="goose_mesh_routing",
        layer=3,
        description="Implement mesh routing for SIMP intents (compatibility layer)",
        files_to_touch=[
            "simp/mesh/simp_routing.py",
            "tests/test_simp_mesh_routing.py"
        ],
        dependencies=["goose_capability_gossip"]
    )
    
    print("✓ Registered 3 geese for Layer 3 implementation")

def register_layer4_geese(mother_goose):
    """Register geese for Layer 4 (Reputation & Trust Graph)."""
    print("\nRegistering geese for Layer 4 (Reputation & Trust Graph)...")
    
    # Goose 7: TrustScorer implementation
    mother_goose.register_goose(
        goose_id="goose_trust_scorer",
        layer=4,
        description="Implement TrustScorer based on payment receipts and delivery history",
        files_to_touch=[
            "simp/mesh/trust_scorer.py",
            "tests/test_trust_scorer.py"
        ],
        dependencies=["goose_mesh_routing"]
    )
    
    # Goose 8: Payment receipt analysis
    mother_goose.register_goose(
        goose_id="goose_receipt_analyzer",
        layer=4,
        description="Analyze payment receipts for trust signal generation",
        files_to_touch=[
            "simp/mesh/receipt_analyzer.py",
            "tests/test_receipt_analyzer.py"
        ],
        dependencies=["goose_trust_scorer"]
    )
    
    # Goose 9: Routing weight integration
    mother_goose.register_goose(
        goose_id="goose_routing_weights",
        layer=4,
        description="Integrate trust scores into mesh routing weights",
        files_to_touch=[
            "simp/mesh/routing_weights.py",
            "tests/test_routing_weights.py"
        ],
        dependencies=["goose_receipt_analyzer"]
    )
    
    print("✓ Registered 3 geese for Layer 4 implementation")

def start_geese_work(mother_goose):
    """Start geese working on their tasks."""
    print("\nStarting geese work...")
    
    # Start Layer 1 geese
    mother_goose.update_goose_progress(
        goose_id="goose_udp_verifier",
        progress=0.1,
        status=GooseStatus.WORKING,
        note="Starting UDP multicast verification"
    )
    
    mother_goose.update_goose_progress(
        goose_id="goose_ble_verifier",
        progress=0.1,
        status=GooseStatus.WORKING,
        note="Starting BLE transport verification"
    )
    
    mother_goose.update_goose_progress(
        goose_id="goose_nostr_verifier",
        progress=0.1,
        status=GooseStatus.WORKING,
        note="Starting Nostr transport verification"
    )
    
    print("✓ Started Layer 1 geese")
    
    # Layer 3 geese will start when dependencies are met
    print("Layer 3 geese waiting for Layer 1 verification...")

def check_dashboard():
    """Check if the web dashboard is accessible."""
    try:
        response = requests.get("http://localhost:8775/api/dashboard", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"\nDashboard accessible! Overall progress: {data['overall_progress']:.1%}")
            print(f"Open http://localhost:8775 in your browser to view the dashboard")
            return True
    except Exception as e:
        print(f"Dashboard not accessible: {e}")
        return False

def main():
    """Main flock session starter."""
    print("=" * 60)
    print("MESH PROTOCOL FLOCK SESSION")
    print("Mother Goose Coordination System")
    print("=" * 60)
    
    # Get mother goose instance
    mother_goose = get_mother_goose()
    
    # Check if dashboard is running
    if not check_dashboard():
        print("\n⚠️  Dashboard not running. Starting it now...")
        print("Run: python3.10 mother_goose_web.py")
        return
    
    # Register geese for all layers
    register_layer1_geese(mother_goose)
    register_layer3_geese(mother_goose)
    register_layer4_geese(mother_goose)
    
    # Start geese working
    start_geese_work(mother_goose)
    
    # Save initial snapshot
    mother_goose.save_snapshot()
    
    print("\n" + "=" * 60)
    print("FLOCK SESSION STARTED!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Open http://localhost:8775 to monitor progress")
    print("2. Geese will work on their assigned layers")
    print("3. Mother Goose will monitor and reprompt stuck geese")
    print("4. Check 'data/mother_goose/' for logs and snapshots")
    
    # Show initial status
    print("\nInitial Status:")
    data = mother_goose.get_dashboard_data()
    print(f"  • Overall Progress: {data['overall_progress']:.1%}")
    print(f"  • Total Geese: {len(mother_goose.geese)}")
    print(f"  • Layers in Progress: {sum(1 for l in data['layers'] if l['status'] == 'in_progress')}")
    
    # Keep checking status
    print("\nMonitoring flock session... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(30)
            data = mother_goose.get_dashboard_data()
            stuck = len(data.get('stuck_geese', []))
            if stuck > 0:
                print(f"\n⚠️  {stuck} goose(s) stuck! Check dashboard for details.")
    except KeyboardInterrupt:
        print("\n\nFlock session monitoring stopped.")
        print("Dashboard continues running at http://localhost:8775")

if __name__ == "__main__":
    main()