"""
SIMPLE WORKING DASHBOARD
Actually shows a GUI, not raw code
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
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

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard HTML"""
    index_path = Path("dashboard/static/index.html")
    if index_path.exists():
        return FileResponse(index_path)
    else:
        # Fallback simple HTML
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>SIMP Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background: #0f172a; color: white; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
                .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
                .card { background: #1e293b; padding: 20px; border-radius: 10px; }
                .card h3 { margin-top: 0; color: #60a5fa; }
                .intent { background: #334155; padding: 10px; margin: 5px 0; border-radius: 5px; }
                .agent { background: #334155; padding: 10px; margin: 5px 0; border-radius: 5px; }
                .status-online { color: #10b981; }
                .status-offline { color: #ef4444; }
                .refresh-btn { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔥 SIMP Dashboard</h1>
                    <p>Real-time monitoring of all agents and intents</p>
                    <button class="refresh-btn" onclick="loadData()">🔄 Refresh</button>
                </div>
                <div class="grid">
                    <div class="card">
                        <h3>📊 System Status</h3>
                        <div id="system-status">Loading...</div>
                    </div>
                    <div class="card">
                        <h3>🤖 Active Agents</h3>
                        <div id="agents-list">Loading...</div>
                    </div>
                    <div class="card">
                        <h3>🔁 Recent Intents</h3>
                        <div id="intents-list">Loading...</div>
                    </div>
                    <div class="card">
                        <h3>📈 Performance</h3>
                        <div id="performance">Loading...</div>
                    </div>
                </div>
            </div>
            <script>
                async function loadData() {
                    try {
                        // Load agents
                        const agentsRes = await fetch('/api/agents');
                        const agentsData = await agentsRes.json();
                        document.getElementById('agents-list').innerHTML = 
                            agentsData.agents.map(a => `
                                <div class="agent">
                                    <strong>${a.agent_id}</strong> 
                                    <span class="status-${a.status === 'online' ? 'online' : 'offline'}">● ${a.status}</span><br>
                                    <small>${a.agent_type} • ${a.intents_received || 0} intents</small>
                                </div>
                            `).join('');
                        
                        // Load intents
                        const intentsRes = await fetch('/api/intents/recent?limit=10');
                        const intentsData = await intentsRes.json();
                        document.getElementById('intents-list').innerHTML = 
                            intentsData.intents.map(i => `
                                <div class="intent">
                                    <strong>${i.intent_type}</strong><br>
                                    <small>${i.source_agent} → ${i.target_agent}</small><br>
                                    <small>Status: ${i.status} • ${new Date(i.timestamp).toLocaleTimeString()}</small>
                                </div>
                            `).join('');
                        
                        // Update system status
                        document.getElementById('system-status').innerHTML = `
                            <p>🟢 System: Operational</p>
                            <p>🤖 Agents: ${agentsData.agents.length} active</p>
                            <p>🔁 Intents: ${intentsData.intents.length} recent</p>
                            <p>🕐 Updated: ${new Date().toLocaleTimeString()}</p>
                        `;
                    } catch (error) {
                        console.error('Error loading data:', error);
                    }
                }
                
                // Load data on page load
                loadData();
                // Refresh every 10 seconds
                setInterval(loadData, 10000);
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

@app.get("/api/health")
async def api_health():
    """Health check"""
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
                lines = f.readlines()[-1000:]
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

@app.get("/api/intents/recent")
async def api_intents_recent(limit: int = 50):
    """Recent intents"""
    intents = await get_recent_intents(limit)
    return {"intents": intents}

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
            if processed >= limit * 2:
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
    logger.info("🚀 Starting SIMPLE WORKING Dashboard on http://localhost:8050")
    logger.info("   This will actually show a GUI!")
    uvicorn.run(app, host="127.0.0.1", port=8050, log_level="info")