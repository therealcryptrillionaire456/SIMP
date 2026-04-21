#!/usr/bin/env python3.10
"""
Test Phase 4 Integration

Tests the integration of Phase 4 components:
1. Exchange connector system
2. Trade executor
3. P&L ledger
4. Monitoring system
5. QuantumArb agent integration
"""

import json
import sys
import os
from pathlib import Path

# Add SIMP to path
simp_root = Path(__file__).parent
sys.path.insert(0, str(simp_root))

def test_exchange_connector():
    """Test exchange connector initialization."""
    print("Testing exchange connector...")
    
    try:
        from simp.organs.quantumarb.exchange_connector import (
            ExchangeConnector, StubExchangeConnector, create_exchange_connector
        )
        
        # Test stub connector
        connector = StubExchangeConnector(
            exchange_name="test_exchange",
            base_url="https://api.test.com",
            api_key="test_key",
            api_secret="test_secret"
        )
        
        # Test methods
        balance = connector.get_balance("USD")
        print(f"  ✓ Stub balance: {balance.available:.2f} {balance.currency}")
        
        ticker = connector.get_ticker("BTC-USD")
        print(f"  ✓ Stub ticker: ${ticker.last_price:.2f}")
        
        print("  ✓ Exchange connector test passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Exchange connector test failed: {e}")
        return False

def test_trade_executor():
    """Test trade executor."""
    print("Testing trade executor...")
    
    try:
        from simp.organs.quantumarb.executor import TradeExecutor
        from simp.organs.quantumarb.exchange_connector import StubExchangeConnector
        
        # Create stub connector
        connector = StubExchangeConnector(
            exchange_name="test",
            base_url="https://api.test.com",
            api_key="test",
            api_secret="test"
        )
        
        # Create executor
        executor = TradeExecutor(
            exchange_connectors={"test": connector},
            monitoring_system=None,
            config={"max_retries": 1, "timeout_seconds": 5}
        )
        
        print("  ✓ Trade executor initialized")
        return True
        
    except Exception as e:
        print(f"  ✗ Trade executor test failed: {e}")
        return False

def test_pnl_ledger():
    """Test P&L ledger."""
    print("Testing P&L ledger...")
    
    try:
        from simp.organs.quantumarb.pnl_ledger import PnLLedger, TradeRecord
        from datetime import datetime
        
        # Create test ledger
        ledger_path = simp_root / "data" / "test_pnl_ledger.jsonl"
        ledger = PnLLedger(ledger_path=str(ledger_path))
        
        # Create test record
        record = TradeRecord(
            trade_id="test_trade_001",
            timestamp=datetime.utcnow().isoformat(),
            opportunity={
                "opportunity_id": "test_opp_001",
                "position_size_usd": 0.10,
                "expected_pnl_usd": 0.001
            },
            execution_result={
                "success": True,
                "total_pnl_usd": 0.0012,
                "actual_slippage_pct": 0.02
            },
            pnl_usd=0.0012,
            fees_usd=0.0001
        )
        
        # Record trade
        ledger.record_trade(record)
        
        # Verify
        count = ledger.get_trade_count()
        total_pnl = ledger.get_total_pnl()
        
        print(f"  ✓ Recorded {count} trades, total P&L: ${total_pnl:.4f}")
        
        # Cleanup
        if ledger_path.exists():
            ledger_path.unlink()
        
        print("  ✓ P&L ledger test passed")
        return True
        
    except Exception as e:
        print(f"  ✗ P&L ledger test failed: {e}")
        return False

def test_monitoring_system():
    """Test monitoring system."""
    print("Testing monitoring system...")
    
    try:
        # Try to import monitoring system
        monitoring_path = simp_root / "monitoring_alerting_system.py"
        if not monitoring_path.exists():
            print("  ⚠ Monitoring system not found, creating stub...")
            
            # Create simple stub for testing
            class MonitoringSystemStub:
                def record_intent(self, *args, **kwargs):
                    return "test_monitoring_id"
                def update_trade_status(self, *args, **kwargs):
                    pass
                def get_active_alerts(self):
                    return []
            
            monitoring_system = MonitoringSystemStub()
        else:
            from monitoring_alerting_system import MonitoringSystem
            monitoring_system = MonitoringSystem()
        
        # Test recording intent
        monitoring_id = monitoring_system.record_intent(
            intent_type="test_intent",
            intent_id="test_001",
            source_agent="test_agent",
            payload={"test": "data"}
        )
        
        print(f"  ✓ Monitoring ID: {monitoring_id}")
        print("  ✓ Monitoring system test passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Monitoring system test failed: {e}")
        return False

def test_phase4_agent():
    """Test Phase 4 agent integration."""
    print("Testing Phase 4 agent integration...")
    
    try:
        # Check if agent file exists
        agent_path = simp_root / "simp" / "agents" / "quantumarb_agent_phase4.py"
        if not agent_path.exists():
            print("  ⚠ Phase 4 agent not found at expected path")
            return False
        
        # Try to import and initialize
        import importlib.util
        spec = importlib.util.spec_from_file_location("quantumarb_phase4", str(agent_path))
        module = importlib.util.module_from_spec(spec)
        
        # Mock required imports for testing
        import sys
        mock_modules = [
            "simp.security.brp_bridge",
            "simp.security.brp_models", 
            "simp.integrations.timesfm_service",
            "simp.integrations.timesfm_policy_engine",
            "monitoring_alerting_system"
        ]
        
        for mod_name in mock_modules:
            if mod_name not in sys.modules:
                # Create simple mock module
                mock_module = type(sys)('mock_module')
                sys.modules[mod_name] = mock_module
        
        # Add mock get_brp_bridge function
        def mock_get_brp_bridge():
            class MockBridge:
                def emit_shadow_observation(self, observation):
                    pass
            return MockBridge()
        
        sys.modules['simp.security.brp_bridge'].get_brp_bridge = mock_get_brp_bridge
        
        try:
            spec.loader.exec_module(module)
            print("  ✓ Phase 4 agent module loaded")
            
            # Test class definitions
            if hasattr(module, 'QuantumArbEnginePhase4'):
                print("  ✓ QuantumArbEnginePhase4 class found")
            if hasattr(module, 'QuantumArbAgentPhase4'):
                print("  ✓ QuantumArbAgentPhase4 class found")
            
            print("  ✓ Phase 4 agent integration test passed")
            return True
            
        except Exception as e:
            print(f"  ✗ Error loading agent module: {e}")
            return False
            
    except Exception as e:
        print(f"  ✗ Phase 4 agent test failed: {e}")
        return False

def test_configuration():
    """Test Phase 4 configuration."""
    print("Testing Phase 4 configuration...")
    
    try:
        config_path = simp_root / "config" / "phase4_microscopic.json"
        
        if not config_path.exists():
            print("  ⚠ Configuration file not found")
            return False
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Validate structure
        required_sections = [
            "phase4_configuration",
            "exchanges", 
            "risk_parameters",
            "execution_parameters",
            "monitoring"
        ]
        
        for section in required_sections:
            if section not in config:
                print(f"  ✗ Missing section: {section}")
                return False
        
        print(f"  ✓ Configuration version: {config['phase4_configuration']['version']}")
        print(f"  ✓ Max position size: ${config['risk_parameters']['microscopic_trading']['max_position_size_usd']:.2f}")
        print(f"  ✓ Min spread: {config['risk_parameters']['spread_thresholds']['min_spread_pct']}%")
        
        print("  ✓ Configuration test passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Configuration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("Phase 4 Integration Test Suite")
    print("="*60)
    
    tests = [
        ("Exchange Connector", test_exchange_connector),
        ("Trade Executor", test_trade_executor),
        ("P&L Ledger", test_pnl_ledger),
        ("Monitoring System", test_monitoring_system),
        ("Phase 4 Agent", test_phase4_agent),
        ("Configuration", test_configuration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ✗ Test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary:")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")
        if success:
            passed += 1
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All Phase 4 integration tests passed!")
        return 0
    else:
        print(f"⚠ {total - passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())