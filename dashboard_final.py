"""
SIMP Dashboard - FINAL VERSION THAT ACTUALLY WORKS
Shows real-time data from ALL sources
"""

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SIMP Dashboard", version="3.0", description="Real-time SIMP Ecosystem Monitor")

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
    """Serve the dashboard HTML"""
    try:
        with open("dashboard/static/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except:
        # Fallback simple HTML
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SIMP Dashboard v3.0</title>
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
                    <h1>🔥 SIMP Ecosystem Dashboard v3.0</h1>
                    <p>Real-time monitoring of all agents and intents</p>
                    <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
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
                            <p>🤖 Agents: ${agentsData.count} active</p>
                            <p>🔁 Intents: ${intentsData.count} recent</p>
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
        """)

@app.get("/api/health")
async def api_health():
    """Health check"""
    return {
        "status": "healthy",
        "dashboard_version": "3.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": {
            "broker": await _check_broker(),
            "database": await _check_database()
        }
    }

async def _check_broker():
    """Check if broker is reachable"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:5555/health")
            return {"reachable": response.status_code == 200, "status": response.json() if response.status_code == 200 else "unreachable"}
    except:
        return {"reachable": False, "status": "unreachable"}

async def _check_database():
    """Check if database files exist"""
    ledger_path = Path("data/task_ledger.jsonl")
    return {
        "ledger_exists": ledger_path.exists(),
        "ledger_size": ledger_path.stat().st_size if ledger_path.exists() else 0
    }

@app.get("/api/agents")
async def api_agents():
    """Get all agents from broker"""
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
                        "endpoint": agent_info.get("endpoint", ""),
                        "last_seen": agent_info.get("last_seen", ""),
                        "intents_received": agent_info.get("intents_received", 0),
                        "intents_completed": agent_info.get("intents_completed", 0),
                        "metadata": agent_info.get("metadata", {})
                    })
                return {"agents": agents_list, "count": len(agents_list)}
    except Exception as e:
        logger.error(f"Failed to fetch agents: {e}")
    
    # Fallback: read from ledger
    return await _get_agents_from_ledger()

async def _get_agents_from_ledger():
    """Extract agent info from task ledger"""
    ledger_path = Path("data/task_ledger.jsonl")
    agents = {}
    
    if ledger_path.exists():
        # Read last 1000 lines
        with open(ledger_path, 'r') as f:
            lines = f.readlines()[-1000:]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                assigned_agent = data.get('assigned_agent')
                if assigned_agent and assigned_agent not in agents:
                    agents[assigned_agent] = {
                        "agent_id": assigned_agent,
                        "agent_type": "unknown",
                        "status": "active",
                        "intents_processed": 0
                    }
            except:
                continue
    
    agents_list = list(agents.values())
    return {"agents": agents_list, "count": len(agents_list)}

@app.get("/api/intents/recent")
async def api_intents_recent(limit: int = 25):
    """Get recent intents - FINAL WORKING VERSION"""
    limit = max(1, min(limit, 100))
    
    # Try to get from broker first
    broker_intents = await _get_intents_from_broker(limit)
    if broker_intents:
        return {
            "status": "success",
            "source": "broker",
            "count": len(broker_intents),
            "intents": broker_intents[:limit]
        }
    
    # Fallback to ledger
    ledger_intents = await _get_intents_from_ledger(limit)
    return {
        "status": "success",
        "source": "ledger",
        "count": len(ledger_intents),
        "intents": ledger_intents[:limit]
    }

async def _get_intents_from_broker(limit: int):
    """Try to get intents from broker API"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try different endpoints
            endpoints = ["/intents", "/intents/recent", "/stats"]
            for endpoint in endpoints:
                try:
                    response = await client.get(f"http://127.0.0.1:5555{endpoint}")
                    if response.status_code == 200:
                        data = response.json()
                        # Try to extract intents from response
                        if "intents" in data:
                            return data["intents"][:limit]
                        elif "pending_intents" in data:
                            # Broker health endpoint
                            return [{"intent_type": "system", "status": "pending", "count": data.get("pending_intents", 0)}]
                except:
                    continue
    except:
        pass
    return None

async def _get_intents_from_ledger(limit: int):
    """Get intents from task ledger - RELIABLE VERSION"""
    ledger_path = Path("data/task_ledger.jsonl")
    intents = []
    
    if not ledger_path.exists():
        return intents
    
    try:
        # Read file efficiently
        with open(ledger_path, 'r') as f:
            # Get total lines
            f.seek(0, 2)
            file_size = f.tell()
            
            # Read backwards in chunks
            chunk_size = 8192
            buffer = ''
            position = file_size
            found = 0
            
            while position > 0 and found < limit * 3:  # Look for 3x limit
                position = max(0, position - chunk_size)
                f.seek(position)
                chunk = f.read(chunk_size)
                buffer = chunk + buffer
                
                # Process lines
                lines = buffer.split('\n')
                for line in lines[-100:]:  # Process recent lines
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        # Check if it's an intent
                        if 'intent' in data.get('tags', []):
                            title = data.get('title', '')
                            intent_type = title.replace('Intent: ', '') if title.startswith('Intent: ') else 'unknown'
                            
                            # Create intent object
                            intent = {
                                'intent_id': data.get('task_id', str(len(intents))),
                                'intent_type': intent_type,
                                'source_agent': data.get('created_by', 'system'),
                                'target_agent': data.get('assigned_agent', ''),
                                'status': data.get('status', ''),
                                'timestamp': data.get('created_at', ''),
                                'delivery_status': 'delivered' if data.get('status') == 'completed' else 'pending',
                                'created_at': data.get('created_at', ''),
                                'updated_at': data.get('updated_at', ''),
                                'params': data.get('params', {})
                            }
                            intents.append(intent)
                            found += 1
                            
                            if len(intents) >= limit:
                                break
                    except json.JSONDecodeError:
                        continue
                
                if len(intents) >= limit:
                    break
                
                # Keep first line for next iteration
                buffer = lines[0] if lines else ''
        
        # Sort by timestamp (most recent first)
        intents.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return intents[:limit]
        
    except Exception as e:
        logger.error(f"Error reading ledger: {e}")
        return []

@app.get("/api/stats")
async def api_stats():
    """Get comprehensive system statistics"""
    try:
        # Get broker stats
        broker_health = {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://127.0.0.1:5555/health")
                if response.status_code == 200:
                    broker_health = response.json()
        except:
            pass
        
        # Count intents in ledger
        intent_count = 0
        completed_count = 0
        ledger_path = Path("data/task_ledger.jsonl")
        if ledger_path.exists():
            with open(ledger_path, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if 'intent' in data.get('tags', []):
                            intent_count += 1
                            if data.get('status') == 'completed':
                                completed_count += 1
                    except:
                        continue
        
        # Get recent activity
        recent_intents = await _get_intents_from_ledger(10)
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "broker": {
                "agents_online": broker_health.get("agents_online", 0),
                "pending_intents": broker_health.get("pending_intents", 0),
                "state": broker_health.get("state", "unknown"),
                "status": broker_health.get("status", "unknown")
            },
            "dashboard": {
                "version": "3.0",
                "intents_processed": intent_count,
                "intents_completed": completed_count,
                "completion_rate": completed_count / intent_count if intent_count > 0 else 0
            },
            "recent_activity": {
                "intents_last_hour": len([i for i in recent_intents if _is_recent(i.get('timestamp', ''), hours=1)]),
                "agents_active": len(set(i.get('target_agent') for i in recent_intents if i.get('target_agent'))),
                "last_update": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

def _is_recent(timestamp: str, hours: int = 1) -> bool:
    """Check if timestamp is within last N hours"""
    try:
        if not timestamp:
            return False
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return (datetime.utcnow() - dt) < timedelta(hours=hours)
    except:
        return False

@app.get("/api/intents/failed")
async def api_intents_failed(limit: int = 50):
    """Get failed intents"""
    limit = max(1, min(limit, 100))
    
    # Get all intents and filter for failed ones
    all_intents = await _get_intents_from_ledger(limit * 5)  # Get more to find failures
    failed_intents = [
        i for i in all_intents 
        if i.get('status') in ('failed', 'error', 'rejected') or 'fail' in str(i.get('status', '')).lower()
    ][:limit]
    
    return {
        "status": "success",
        "count": len(failed_intents),
        "intents": failed_intents
    }

if __name__ == "__main__":
    logger.info("🚀 Starting SIMP Dashboard v3.0 on http://localhost:8050")
    logger.info("   Real-time monitoring enabled")
    logger.info("   Data sources: Broker API + Task Ledger")
    uvicorn.run(app, host="127.0.0.1", port=8050, log_level="info")