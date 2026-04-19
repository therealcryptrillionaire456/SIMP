"""
PROPER SIMP Dashboard
Compatible with the existing dashboard JavaScript
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SIMP Dashboard", version="1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

# Store for WebSocket connections (simplified)
connected_clients = []

@app.get("/")
async def serve_index():
    """Serve the main dashboard HTML"""
    index_path = Path("dashboard/static/index.html")
    if index_path.exists():
        with open(index_path, 'r') as f:
            return f.read()
    else:
        return "<h1>SIMP Dashboard</h1><p>Static files not found</p>"

@app.get("/api/health")
async def api_health():
    """Health check endpoint"""
    try:
        # Check broker
        broker_health = {}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get("http://127.0.0.1:5555/health")
                if response.status_code == 200:
                    broker_health = response.json()
        except:
            pass
        
        return {
            "status": "healthy",
            "broker_reachable": bool(broker_health),
            "broker_state": broker_health.get("state", "unknown"),
            "agents_registered": broker_health.get("agents_online", 0),
            "dashboard_version": "1.0",
            "uptime_seconds": 0
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "dashboard_version": "1.0"
        }

@app.get("/api/stats")
async def api_stats():
    """System statistics"""
    try:
        # Get broker stats
        broker_stats = {}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get("http://127.0.0.1:5555/health")
                if response.status_code == 200:
                    broker_stats = response.json()
        except:
            pass
        
        # Count intents from ledger
        ledger_path = Path("data/task_ledger.jsonl")
        intent_count = 0
        if ledger_path.exists():
            with open(ledger_path, 'r') as f:
                lines = f.readlines()[-1000:]  # Last 1000 lines
                for line in lines:
                    try:
                        data = json.loads(line.strip())
                        if 'intent' in data.get('tags', []):
                            intent_count += 1
                    except:
                        continue
        
        return {
            "agents_registered": broker_stats.get("agents_online", 0),
            "pending_intents": broker_stats.get("pending_intents", 0),
            "intents_processed": intent_count,
            "broker_state": broker_stats.get("state", "unknown"),
            "broker_status": broker_stats.get("status", "unknown"),
            "dashboard_version": "1.0"
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {
            "agents_registered": 0,
            "pending_intents": 0,
            "intents_processed": 0,
            "broker_state": "unknown",
            "error": str(e)
        }

@app.get("/api/agents")
async def api_agents():
    """Get all agents"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:5555/agents")
            if response.status_code == 200:
                data = response.json()
                agents_list = []
                for agent_id, agent_info in data.get("agents", {}).items():
                    agents_list.append({
                        "agent_id": agent_id,
                        "agent_type": agent_info.get("agent_type", "unknown"),
                        "status": agent_info.get("status", "online"),
                        "endpoint": agent_info.get("endpoint", ""),
                        "last_seen": agent_info.get("last_seen", ""),
                        "intents_received": agent_info.get("intents_received", 0),
                        "intents_completed": agent_info.get("intents_completed", 0),
                        "metadata": agent_info.get("metadata", {})
                    })
                return {"agents": agents_list}
    except Exception as e:
        logger.error(f"Error fetching agents: {e}")
    
    # Fallback
    return {"agents": []}

@app.get("/api/activity")
async def api_activity():
    """Recent activity"""
    try:
        # Get recent intents
        intents = await get_recent_intents(20)
        
        # Process for activity
        activity = []
        for intent in intents:
            activity.append({
                "type": "intent",
                "agent_id": intent.get("target_agent", ""),
                "intent_type": intent.get("intent_type", ""),
                "status": intent.get("status", ""),
                "timestamp": intent.get("timestamp", ""),
                "description": f"{intent.get('intent_type', 'Intent')} → {intent.get('target_agent', 'unknown')}"
            })
        
        return {"activity": activity[:10]}  # Return top 10
    except Exception as e:
        logger.error(f"Activity error: {e}")
        return {"activity": []}

@app.get("/api/intents/recent")
async def api_intents_recent(limit: int = 50):
    """Recent intents"""
    intents = await get_recent_intents(limit)
    return {"intents": intents}

@app.get("/api/intents/failed")
async def api_intents_failed(limit: int = 50):
    """Failed intents"""
    all_intents = await get_recent_intents(limit * 3)
    failed = [i for i in all_intents if i.get("status") in ["failed", "error", "rejected"]]
    return {"intents": failed[:limit]}

@app.get("/api/intents/{intent_id}")
async def api_intent_detail(intent_id: str):
    """Get specific intent details"""
    # Simplified - just return basic info
    return {
        "intent_id": intent_id,
        "status": "unknown",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "source_agent": "unknown",
        "target_agent": "unknown",
        "intent_type": "unknown"
    }

@app.get("/api/capabilities")
async def api_capabilities():
    """System capabilities"""
    return {
        "capabilities": [
            {"id": "trade_execution", "name": "Trade Execution", "description": "Execute trades on exchanges"},
            {"id": "market_analysis", "name": "Market Analysis", "description": "Analyze market data"},
            {"id": "arbitrage", "name": "Arbitrage Detection", "description": "Detect arbitrage opportunities"},
            {"id": "risk_management", "name": "Risk Management", "description": "Manage trading risk"},
            {"id": "planning", "name": "Planning", "description": "Strategic planning and analysis"}
        ]
    }

@app.get("/api/tasks/queue")
async def api_tasks_queue():
    """Task queue"""
    return {"tasks": []}

@app.get("/api/projectx/chat")
async def api_projectx_chat():
    """ProjectX chat endpoint"""
    return {"messages": [], "status": "ok"}

@app.get("/ws")
async def websocket_endpoint():
    """WebSocket endpoint (simplified)"""
    # This is a simplified version - real implementation would handle WebSockets
    return {"message": "WebSocket endpoint - use WebSocket client"}

async def get_recent_intents(limit: int = 50):
    """Get recent intents from ledger"""
    ledger_path = Path("data/task_ledger.jsonl")
    intents = []
    
    if not ledger_path.exists():
        return intents
    
    try:
        # Read file
        with open(ledger_path, 'r') as f:
            lines = f.readlines()
        
        # Process from end
        processed = 0
        for line in reversed(lines):
            if processed >= limit * 2:  # Look at 2x limit
                break
            processed += 1
            
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # Check if it's an intent
                is_intent = False
                tags = data.get('tags', [])
                title = data.get('title', '')
                
                if 'intent' in tags:
                    is_intent = True
                elif 'Intent:' in title:
                    is_intent = True
                elif data.get('assigned_agent'):
                    is_intent = True
                
                if is_intent:
                    intent_type = title.replace('Intent: ', '') if 'Intent:' in title else 'task'
                    
                    intent = {
                        'intent_id': data.get('task_id', f"intent_{len(intents)}"),
                        'intent_type': intent_type,
                        'source_agent': data.get('created_by', 'system'),
                        'target_agent': data.get('assigned_agent', ''),
                        'status': data.get('status', 'unknown'),
                        'timestamp': data.get('created_at', ''),
                        'created_at': data.get('created_at', ''),
                        'updated_at': data.get('updated_at', ''),
                        'params': data.get('params', {})
                    }
                    intents.append(intent)
                    
                    if len(intents) >= limit:
                        break
                        
            except json.JSONDecodeError:
                continue
        
        # Sort by timestamp
        intents.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
    except Exception as e:
        logger.error(f"Error getting intents: {e}")
    
    return intents[:limit]

if __name__ == "__main__":
    logger.info("🚀 Starting PROPER SIMP Dashboard on http://localhost:8050")
    logger.info("   Compatible with existing dashboard JavaScript")
    uvicorn.run(app, host="127.0.0.1", port=8050, log_level="info")