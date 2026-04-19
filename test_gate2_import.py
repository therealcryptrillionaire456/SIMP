#!/usr/bin/env python3.10
"""Test Gate 2 imports."""

import sys
sys.path.insert(0, '.')

try:
    from simp.security.brp_models import BRPObservation, BRPResponse
    print("✅ BRP imports successful")
    
    from simp.organs.quantumarb.arb_detector import ArbitrageSignal, ArbitrageOpportunity, ArbDecision
    print("✅ Arb detector imports successful")
    
    from simp.organs.quantumarb.exchange_connector import create_exchange_connector, ExchangeConnector
    print("✅ Exchange connector imports successful")
    
    from simp.organs.quantumarb.executor import TradeExecutor
    print("✅ Trade executor imports successful")
    
    from simp.organs.quantumarb.pnl_ledger import PNLLedger
    print("✅ P&L ledger imports successful")
    
    print("\n✅ All imports successful!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()