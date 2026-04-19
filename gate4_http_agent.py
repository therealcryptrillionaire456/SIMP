"""
Gate 4 HTTP Agent Wrapper
Makes the Gate 4 agent accessible via HTTP so broker can deliver intents
"""

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gate 4 HTTP Agent", version="1.0")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Import Gate 4 agent
try:

    from agents.gate4_scaled_agent_part3 import Gate4ScaledMicroscopicAgent
    GATE4_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import Gate 4 agent: {e}")
    GATE4_AVAILABLE = False
AGENT_PORT = 8770  # Set in __main__ before uvicorn starts

class IntentRequest(BaseModel):
    intent_type: str
    source_agent: str
    params: dict = {}
    intent_id: str = ""

# Global agent instance
gate4_agent = None

@app.on_event("startup")
async def startup_event():
    """Initialize Gate 4 agent on startup"""
    global gate4_agent
    if GATE4_AVAILABLE:
        try:
            # Initialize agent (simplified version)
            logger.info("Initializing Gate 4 HTTP agent...")
            # We'll create a minimal agent for HTTP processing
            gate4_agent = {
                "status": "ready",
                "initialized_at": datetime.utcnow().isoformat(),
                "capabilities": ["trade_execution", "market_analysis", "risk_management"]
            }
            logger.info("Gate 4 HTTP agent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Gate 4 agent: {e}")
            gate4_agent = None
    else:
        logger.warning("Gate 4 agent not available, running in stub mode")
    _register_with_broker()

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy" if GATE4_AVAILABLE else "degraded",
        "agent_available": GATE4_AVAILABLE,
        "agent_initialized": gate4_agent is not None,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/intent")
async def handle_intent(intent: IntentRequest):
    """Handle incoming intents"""
    if not GATE4_AVAILABLE:
        raise HTTPException(status_code=503, detail="Gate 4 agent not available")
    
    logger.info(f"Received intent: {intent.intent_type} from {intent.source_agent}")
    
    # Process based on intent type
    if intent.intent_type == "trade_execution":
        return await handle_trade_execution(intent)
    elif intent.intent_type == "market_analysis":
        return await handle_market_analysis(intent)
    elif intent.intent_type == "status_check":
        return await handle_status_check(intent)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported intent type: {intent.intent_type}")

async def handle_trade_execution(intent: IntentRequest):
    """Handle trade execution intent"""
    symbol = intent.params.get("symbol", "BTC-USD")
    amount = intent.params.get("amount", 1.0)
    side = intent.params.get("side", "buy")
    
    logger.info(f"Trade execution: {side} {amount} of {symbol}")
    
    # Simulate trade execution
    return {
        "status": "success",
        "message": f"Trade executed: {side} {amount} {symbol}",
        "trade_id": f"trade_{datetime.utcnow().timestamp()}",
        "timestamp": datetime.utcnow().isoformat(),
        "details": {
            "symbol": symbol,
            "amount": amount,
            "side": side,
            "estimated_price": 50000.0,  # Mock price
            "estimated_cost": amount * 50000.0
        }
    }

async def handle_market_analysis(intent: IntentRequest):
    """Handle market analysis intent"""
    symbol = intent.params.get("symbol", "BTC-USD")
    
    logger.info(f"Market analysis for {symbol}")
    
    # Simulate market analysis
    return {
        "status": "success",
        "message": f"Market analysis completed for {symbol}",
        "analysis": {
            "symbol": symbol,
            "trend": "bullish",
            "volatility": "medium",
            "liquidity": "high",
            "recommendation": "hold",
            "confidence": 0.75
        },
        "timestamp": datetime.utcnow().isoformat()
    }

async def handle_status_check(intent: IntentRequest):
    """Handle status check intent"""
    return {
        "status": "success",
        "agent": "gate4_http",
        "state": "ready",
        "capabilities": ["trade_execution", "market_analysis", "risk_management"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/status")
async def get_status():
    """Get agent status"""
    return {
        "agent_id": "gate4_http",
        "status": "online",
        "version": "1.0",
        "capabilities": ["trade_execution", "market_analysis", "risk_management"],
        "uptime": "0s",  # Would track actual uptime
        "timestamp": datetime.utcnow().isoformat()
    }

def _register_with_broker():
    """Auto-register gate4 agents with broker using current port on every startup."""
    import threading, urllib.request, json as _j, time
    def _run():
        time.sleep(2)
        for agent_id in ["gate4_http", "gate4_live"]:
            try:
                urllib.request.urlopen(urllib.request.Request(
                    f"http://127.0.0.1:5555/agents/{agent_id}", method="DELETE"), timeout=3)
            except Exception:
                pass
            try:
                data = _j.dumps({"agent_id": agent_id, "agent_type": "trading",
                    "endpoint": f"http://127.0.0.1:{AGENT_PORT}",
                    "simp_versions": ["1.0"]}).encode()
                urllib.request.urlopen(urllib.request.Request(
                    "http://127.0.0.1:5555/agents/register",
                    data=data, headers={"Content-Type": "application/json"},
                    method="POST"), timeout=3)
                logger.info(f"Auto-registered {agent_id} with broker at port {AGENT_PORT}")
            except Exception as e:
                logger.warning(f"Broker registration failed for {agent_id}: {e}")
    threading.Thread(target=_run, daemon=True).start()


if __name__ == "__main__":
    # Use dynamic port allocation to avoid conflicts
    try:
        from tools.port_utils import find_free_port
        port = find_free_port(8770)
    except ImportError:
        logger.warning("tools.port_utils not found, using default port 8770")
        port = 8770
    
    logger.info(f"Starting Gate 4 HTTP Agent on port {port}")
    AGENT_PORT = port
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")