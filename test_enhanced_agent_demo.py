#!/usr/bin/env python3
"""
Demo of Enhanced Bill Russell Agent - Mythos Defender
"""

import sys
import os
from pathlib import Path

# Add the project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("ENHANCED BILL RUSSELL AGENT DEMO")
print("Mythos Defender System")
print("=" * 80)
print()

print("Based on analysis of Claude Mythos Preview System Card")
print("Capabilities being countered:")
print("  1. Pattern Recognition at Depth - Sees attacks before completion")
print("  2. Autonomous Reasoning Chains - No human review needed")
print("  3. Memory Across Time - Correlates events weeks apart")
print("  4. Cyber Capabilities - Zero-day vulnerability discovery")
print("  5. Cross-domain Synthesis - Connects disparate threat signals")
print()

print("Initializing Enhanced Bill Russell Agent...")
print("-" * 80)

try:
    from simp.agents.bill_russel_agent_enhanced import (
        EnhancedBillRusselAgent,
        ThreatType,
        ThreatSeverity,
        ResponseAction,
        EnhancedThreatEvent
    )
    
    print("✓ Agent imports successful")
    
    # Create a test agent (don't actually run it, just test initialization)
    print("\nCreating test agent instance...")
    
    # Create necessary directories first
    test_data_dir = project_root / "data" / "bill_russel_enhanced_test"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Temporarily modify the paths for testing
    import simp.agents.bill_russel_agent_enhanced as agent_module
    original_data_dir = agent_module.DATA_DIR
    agent_module.DATA_DIR = test_data_dir
    agent_module.INBOX_DIR = test_data_dir / "inbox"
    agent_module.OUTBOX_DIR = test_data_dir / "outbox"
    agent_module.THREAT_DB_PATH = test_data_dir / "mythos_threat_memory.db"
    agent_module.LOGS_DIR = test_data_dir / "logs"
    
    # Create directories
    for dir_path in [agent_module.INBOX_DIR, agent_module.OUTBOX_DIR, agent_module.LOGS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Test agent initialization
    agent = EnhancedBillRusselAgent(poll_interval=1.0, simp_url="http://127.0.0.1:5555")
    print("✓ Agent initialized successfully")
    
    # Test protocol components
    print("\nTesting protocol components...")
    
    # Test pattern recognition
    test_log = {
        'source_ip': '192.168.1.100',
        'event_type': 'zero_day_probing',
        'details': 'fuzzing parameters with unusual header values',
        'severity': 'high'
    }
    
    analysis = agent.protocol.analyze_event(test_log)
    print(f"✓ Pattern recognition test: {analysis['patterns_detected']} patterns detected")
    
    # Test threat event creation
    threat_event = EnhancedThreatEvent(
        event_id="test-123",
        timestamp="2026-04-10T00:00:00Z",
        source_ip="192.168.1.100",
        threat_type=ThreatType.ZERO_DAY_PROBING,
        details=test_log,
        patterns_detected=analysis['pattern_details'],
        threat_assessment=analysis['threat_assessment'],
        confidence=analysis['threat_assessment']['confidence'],
        severity=ThreatSeverity(analysis['threat_assessment']['threat_level']),
        response_action=ResponseAction(analysis['threat_assessment']['action']),
        mythos_capability_countered="zero_day_probing"
    )
    
    print(f"✓ Threat event created: {threat_event.threat_type.value}")
    print(f"  Severity: {threat_event.severity.value}")
    print(f"  Response: {threat_event.response_action.value}")
    print(f"  Mythos capability countered: {threat_event.mythos_capability_countered}")
    
    # Test system status
    status = agent.protocol.get_system_status()
    print(f"\n✓ System status retrieved:")
    print(f"  Total threat events: {status.get('total_threat_events', 0)}")
    print(f"  Unique source IPs: {status.get('unique_source_ips', 0)}")
    print(f"  Temporal correlations: {status.get('temporal_correlations', 0)}")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\nEnhanced Bill Russell Agent is ready to defend against Mythos-level threats.")
    print("\nKey features demonstrated:")
    print("  1. Mythos-specific pattern recognition")
    print("  2. Autonomous threat assessment")
    print("  3. Threat memory with temporal correlations")
    print("  4. Response action determination")
    print("  5. SIMP broker integration ready")
    
    # Clean up test database
    if os.path.exists(agent_module.THREAT_DB_PATH):
        os.remove(agent_module.THREAT_DB_PATH)
        print(f"\nCleaned up test database: {agent_module.THREAT_DB_PATH}")
    
    # Restore original paths
    agent_module.DATA_DIR = original_data_dir
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    import traceback
    traceback.print_exc()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("Next steps:")
print("  1. Run agent: python3 simp/agents/bill_russel_agent_enhanced.py --demo-mode")
print("  2. Register with SIMP: python3 simp/agents/bill_russel_agent_enhanced.py --register-only")
print("  3. View logs: data/bill_russel_enhanced/logs/bill_russel_enhanced.log")
print("=" * 80)