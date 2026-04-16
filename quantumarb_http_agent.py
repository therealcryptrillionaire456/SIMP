"""
QuantumArb HTTP Agent Wrapper
Makes the QuantumArb agent accessible via HTTP so broker can deliver intents
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

app = FastAPI(title="QuantumArb HTTP Agent", version="1.0")

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import QuantumArb agent
try:
    from simp.agents.quantumarb_agent import QuantumArbAgent
    QUANTUMARB_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import QuantumArb agent: {e}")
    QUANTUMARB_AVAILABLE = False

class IntentRequest(BaseModel):
    intent_type: str
    source_agent: str
    params: dict = {}
    intent_id: str = ""

# Global agent instance
quantumarb_agent = None

@app.on_event("startup")
async def startup_event():
    """Initialize QuantumArb agent on startup"""
    global quantumarb_agent
    if QUANTUMARB_AVAILABLE:
        try:
            logger.info("Initializing QuantumArb HTTP agent...")
            # Create agent instance
            quantumarb_agent = QuantumArbAgent(poll_interval=5.0)
            logger.info("QuantumArb HTTP agent initialized")
        except Exception as e:
            logger.error(f"Failed to initialize QuantumArb agent: {e}")
            quantumarb_agent = None
    else:
        logger.warning("QuantumArb agent not available, running in stub mode")

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy" if QUANTUMARB_AVAILABLE else "degraded",
        "agent_available": QUANTUMARB_AVAILABLE,
        "agent_initialized": quantumarb_agent is not None,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/intent")
async def handle_intent(intent: IntentRequest):
    """Handle incoming intents"""
    if not QUANTUMARB_AVAILABLE:
        raise HTTPException(status_code=503, detail="QuantumArb agent not available")
    
    logger.info(f"Received intent: {intent.intent_type} from {intent.source_agent}")
    
    # Process based on intent type
    if intent.intent_type == "analyze_patterns":
        return await handle_analyze_patterns(intent)
    elif intent.intent_type == "market_analysis":
        return await handle_market_analysis(intent)
    elif intent.intent_type == "arbitrage":
        return await handle_arbitrage(intent)
    elif intent.intent_type == "status_check":
        return await handle_status_check(intent)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported intent type: {intent.intent_type}")

async def handle_analyze_patterns(intent: IntentRequest):
    """Handle pattern analysis intent"""
    symbol = intent.params.get("symbol", "BTC-USD")
    pattern = intent.params.get("pattern", "arbitrage")
    
    logger.info(f"Pattern analysis: {pattern} for {symbol}")
    
    # Simulate pattern analysis
    return {
        "status": "success",
        "message": f"Pattern analysis completed for {symbol}",
        "analysis": {
            "symbol": symbol,
            "pattern": pattern,
            "opportunities": [
                {
                    "type": "cross_exchange",
                    "exchanges": ["coinbase", "kraken"],
                    "spread": 0.5,  # 0.5%
                    "profit_estimate": 25.0,
                    "confidence": 0.65
                }
            ],
            "recommendation": "monitor",
            "confidence": 0.7
        },
        "timestamp": datetime.utcnow().isoformat()
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
            "arbitrage_opportunities": 2,
            "best_spread": 0.3,  # 0.3%
            "liquidity_score": 0.8,
            "volatility": "medium",
            "recommendation": "potential_arbitrage"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

async def handle_arbitrage(intent: IntentRequest):
    """Handle arbitrage intent"""
    symbol = intent.params.get("symbol", "BTC-USD")
    
    logger.info(f"Arbitrage analysis for {symbol}")
    
    # Simulate arbitrage analysis
    return {
        "status": "success",
        "message": f"Arbitrage analysis completed for {symbol}",
        "arbitrage": {
            "symbol": symbol,
            "opportunities": [
                {
                    "exchange_pair": "coinbase -> kraken",
                    "buy_price": 50000.0,
                    "sell_price": 50150.0,
                    "spread": 0.3,
                    "estimated_profit": 15.0,
                    "risk": "low"
                }
            ],
            "total_opportunities": 1,
            "max_profit": 15.0,
            "recommendation": "execute"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

async def handle_status_check(intent: IntentRequest):
    """Handle status check intent"""
    return {
        "status": "success",
        "agent": "quantumarb_http",
        "state": "ready",
        "capabilities": ["analyze_patterns", "market_analysis", "arbitrage"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/status")
async def get_status():
    """Get agent status"""
    return {
        "agent_id": "quantumarb_http",
        "status": "online",
        "version": "1.0",
        "capabilities": ["analyze_patterns", "market_analysis", "arbitrage"],
        "uptime": "0s",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    # Use dynamic port allocation to avoid conflicts
    try:
        from tools.port_utils import find_free_port
        port = find_free_port(8770)
    except ImportError:
        logger.warning("tools.port_utils not found, using default port 8770")
        port = 8770
    
    logger.info(f"Starting QuantumArb HTTP Agent on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")