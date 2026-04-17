"""
SIMP Dashboard - SIMPLE VERSION THAT ACTUALLY WORKS
Shows real-time data from task ledger and broker
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SIMP Dashboard", version="2.0")

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

@app.get("/")
async def root():
    """Serve the dashboard HTML"""
    return FileResponse("dashboard/static/index.html")

@app.get("/api/health")
async def api_health():
    """Health check"""
    return {
        "status": "healthy",
        "dashboard_version": "2.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/api/agents")
async def api_agents():
    """Get agents from broker"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:5555/agents")
            if response.status_code == 200:
                broker_data = response.json()
                agents_list = []
                for agent_id, agent_info in broker_data.get("agents", {}).items():
                    agents_list.append({
                        "agent_id": agent_id,
                        "agent_type": agent_info.get("agent_type", "unknown"),
                        "status": agent_info.get("status", "unknown"),
                        "last_heartbeat": agent_info.get("last_heartbeat", ""),
                        "intents_received": agent_info.get("intents_received", 0),
                        "intents_completed": agent_info.get("intents_completed", 0),
                        "metadata": agent_info.get("metadata", {})
                    })
                return {"agents": agents_list, "count": len(agents_list)}
    except Exception as e:
        logger.warning(f"Failed to fetch agents from broker: {e}")
    
    # Fallback
    return {"agents": [], "count": 0}

@app.get("/api/intents/recent")
async def api_intents_recent(limit: int = 25):
    """Get recent intents from task ledger - SIMPLE VERSION THAT WORKS"""
    limit = max(1, min(limit, 100))
    
    ledger_path = Path("data/task_ledger.jsonl")
    intents = []
    
    if ledger_path.exists():
        # SIMPLE: Read last N lines directly
        with open(ledger_path, 'r') as f:
            lines = f.readlines()
        
        # Process lines from end
        processed = 0
        for line in reversed(lines):
            if processed >= limit * 10:  # Look at last N*10 lines max
                break
            processed += 1
            
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                # Check if it's an intent
                if 'intent' in data.get('tags', []):
                    title = data.get('title', '')
                    intent_type = title.replace('Intent: ', '') if title.startswith('Intent: ') else 'unknown'
                    
                    intents.append({
                        'intent_id': data.get('task_id', ''),
                        'intent_type': intent_type,
                        'source_agent': 'system',
                        'target_agent': data.get('assigned_agent', ''),
                        'status': data.get('status', ''),
                        'timestamp': data.get('created_at', ''),
                        'delivery_status': 'delivered' if data.get('status') == 'completed' else 'pending',
                        'created_at': data.get('created_at', ''),
                        'updated_at': data.get('updated_at', '')
                    })
                    
                    # Stop when we have enough
                    if len(intents) >= limit:
                        break
            except json.JSONDecodeError:
                continue
    
    # Already in reverse chronological order
    return {
        "status": "success",
        "count": len(intents),
        "intents": intents,
    }

@app.get("/api/stats")
async def api_stats():
    """Get system statistics"""
    try:
        # Get broker health
        async with httpx.AsyncClient(timeout=5.0) as client:
            health_response = await client.get("http://127.0.0.1:5555/health")
            health_data = health_response.json() if health_response.status_code == 200 else {}
        
        # Count intents in ledger
        intent_count = 0
        ledger_path = Path("data/task_ledger.jsonl")
        if ledger_path.exists():
            with open(ledger_path, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if 'intent' in data.get('tags', []):
                            intent_count += 1
                    except:
                        continue
        
        return {
            "status": "success",
            "broker": {
                "agents_online": health_data.get("agents_online", 0),
                "pending_intents": health_data.get("pending_intents", 0),
                "state": health_data.get("state", "unknown")
            },
            "dashboard": {
                "intents_processed": intent_count,
                "version": "2.0"
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting SIMPLE SIMP Dashboard on http://localhost:8050")
    uvicorn.run(app, host="127.0.0.1", port=8050, log_level="info")