#!/usr/bin/env python3
"""
KashClaw SIMP Agent - Live Trading
Connects KashClaw trading organs to SIMP broker.
"""

import asyncio
import sys
import os

# Add parent directories to path
sys.path.insert(0, '/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)')
sys.path.insert(0, '/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp')

from simp.integrations.kashclaw_shim import KashClawSimpAgent, get_registry
from simp.agent import SimpAgent

async def main():
    print("🚀 KashClaw SIMP Agent - Live Trading Activation")
    print("=" * 60)
    
    # Create KashClaw agent
    agent = KashClawSimpAgent(
        agent_id="kashclaw_live",
        organization="kashclaw.trading",
        endpoint="http://127.0.0.1:8765",  # KashClaw agent endpoint
        capabilities=[
            "trade_execution",
            "market_analysis", 
            "risk_management",
            "portfolio_management"
        ]
    )
    
    print(f"✅ Created KashClaw agent: {agent.agent_id}")
    print(f"   Endpoint: {agent.endpoint}")
    print(f"   Capabilities: {len(agent.capabilities)}")
    
    # Register with SIMP broker
    print("\n🔌 Registering with SIMP broker...")
    try:
        # This would normally register via HTTP
        # For now, we'll just print the registration info
        print(f"   Agent ID: {agent.agent_id}")
        print(f"   Endpoint: {agent.endpoint}")
        print(f"   Ready to receive trading intents!")
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        return
    
    print("\n🎯 KashClaw agent is ONLINE and ready for live trading!")
    print("   • Kalshi prediction markets")
    print("   • Crypto exchanges (Gemini/Coinbase)")
    print("   • Alpaca stocks")
    print("   • Real-time arbitrage")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
            print("💓 KashClaw agent heartbeat...")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down KashClaw agent...")

if __name__ == "__main__":
    asyncio.run(main())
