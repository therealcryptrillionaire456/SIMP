"""
SIMP Dashboard - WORKING VERSION
Simple, reliable dashboard that actually shows data
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SIMP Dashboard", version="4.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Dashboard homepage"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SIMP Dashboard v4.0</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #0f172a; color: white; }
            .container { max-width: 1400px; margin: 0 auto; }
            .header { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .card { background: #1e293b; padding: 20px; border-radius: 10px; }
            .card h3 { margin-top: 0; color: #60a5fa; border-bottom: 2px solid #334155; padding-bottom: 10px; }
            .intent { background: #334155; padding: 10px; margin: 5px 0; border-radius: 5px; font-size: 14px; }
            .agent { background: #334155; padding: 10px; margin: 5px 0; border-radius: 5px; font-size: 14px; }
            .status-online { color: #10b981; }
            .status-offline { color: #ef4444; }
            .refresh-btn { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px; }
            .timestamp { color: #94a3b8; font-size: 12px; }
            .badge { background: #475569; padding: 2px 8px; border-radius: 10px; font-size: 12px; margin-left: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔥 SIMP Ecosystem Dashboard v4.0</h1>
                <p>Real-time monitoring of all agents and intents</p>
                <button class="refresh-btn" onclick="loadAllData()">🔄 Refresh Now</button>
                <div style="margin-top: 10px; font-size: 14px; color: #94a3b8;">
                    Auto-refreshes every 10 seconds
                </div>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h3>📊 System Status</h3>
                    <div id="system-status">Loading...</div>
                </div>
                
                <div class="card">
                    <h3>🤖 Active Agents <span class="badge" id="agent-count">0</span></h3>
                    <div id="agents-list">Loading...</div>
                </div>
                
                <div class="card">
                    <h3>🔁 Recent Intents <span class="badge" id="intent-count">0</span></h3>
                    <div id="intents-list">Loading...</div>
                </div>
                
                <div class="card">
                    <h3>📈 Performance</h3>
                    <div id="performance">Loading...</div>
                </div>
            </div>
            
            <div class="card" style="margin-top: 20px;">
                <h3>🚀 Quick Actions</h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="refresh-btn" onclick="sendTestIntent()">Send Test Intent</button>
                    <button class="refresh-btn" onclick="checkAllHealth()">Check All Health</button>
                    <button class="refresh-btn" onclick="viewLogs()">View Logs</button>
                </div>
            </div>
        </div>
        
        <script>
            async function loadAllData() {
                try {
                    // Load system status
                    const healthRes = await fetch('/api/health');
                    const healthData = await healthRes.json();
                    document.getElementById('system-status').innerHTML = `
                        <p>🟢 System: ${healthData.status}</p>
                        <p>🤖 Agents: ${healthData.agents_count || 0} registered</p>
                        <p>🔁 Intents: ${healthData.intents_count || 0} processed</p>
                        <p>🕐 Updated: ${new Date().toLocaleTimeString()}</p>
                        <p class="timestamp">Dashboard v${healthData.dashboard_version}</p>
                    `;
                    
                    // Load agents
                    const agentsRes = await fetch('/api/agents');
                    const agentsData = await agentsRes.json();
                    document.getElementById('agent-count').textContent = agentsData.count || 0;
                    document.getElementById('agents-list').innerHTML = 
                        (agentsData.agents || []).map(a => `
                            <div class="agent">
                                <strong>${a.agent_id}</strong> 
                                <span class="status-${a.status === 'online' ? 'online' : 'offline'}">● ${a.status}</span><br>
                                <small>Type: ${a.agent_type} • Intents: ${a.intents_received || 0}</small><br>
                                <small class="timestamp">Last seen: ${new Date(a.last_seen).toLocaleTimeString()}</small>
                            </div>
                        `).join('') || '<p>No agents found</p>';
                    
                    // Load intents
                    const intentsRes = await fetch('/api/intents/recent?limit=10');
                    const intentsData = await intentsRes.json();
                    document.getElementById('intent-count').textContent = intentsData.count || 0;
                    document.getElementById('intents-list').innerHTML = 
                        (intentsData.intents || []).map(i => `
                            <div class="intent">
                                <strong>${i.intent_type}</strong><br>
                                <small>${i.source_agent || 'system'} → ${i.target_agent || 'any'}</small><br>
                                <small>Status: ${i.status} • ${new Date(i.timestamp).toLocaleTimeString()}</small>
                            </div>
                        `).join('') || '<p>No recent intents</p>';
                    
                    // Load performance
                    const statsRes = await fetch('/api/stats');
                    const statsData = await statsRes.json();
                    document.getElementById('performance').innerHTML = `
                        <p>📊 Broker: ${statsData.broker?.agents_online || 0} agents online</p>
                        <p>✅ Completed: ${statsData.dashboard?.intents_completed || 0} intents</p>
                        <p>📈 Rate: ${((statsData.dashboard?.completion_rate || 0) * 100).toFixed(1)}% success</p>
                        <p>⏱️ Recent: ${statsData.recent_activity?.intents_last_hour || 0} last hour</p>
                    `;
                    
                } catch (error) {
                    console.error('Error loading data:', error);
                    document.getElementById('system-status').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
                }
            }
            
            async function sendTestIntent() {
                try {
                    const response = await fetch('/api/send_test_intent', { method: 'POST' });
                    const result = await response.json();
                    alert(result.message || 'Test intent sent');
                    loadAllData();
                } catch (error) {
                    alert('Error sending test intent');
                }
            }
            
            async function checkAllHealth() {
                try {
                    const response = await fetch('/api/check_health');
                    const result = await response.json();
                    alert(`Health check: ${result.status}`);
                    loadAllData();
                } catch (error) {
                    alert('Error checking health');
                }
            }
            
            function viewLogs() {
                window.open('/api/logs', '_blank');
            }
            
            // Initial load
            loadAllData();
            // Auto-refresh every 10 seconds
            setInterval(loadAllData, 10000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/api/health")
async def api_health():
    """Health check"""
    # Get actual data
    agents = await get_agents()
    intents = await get_recent_intents(5)
    
    return {
        "status": "healthy",
        "dashboard_version": "4.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agents_count": agents.get("count", 0),
        "intents_count": len(intents),
        "broker_reachable": await check_broker()
    }

async def check_broker():
    """Check if broker is reachable"""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get("http://127.0.0.1:5555/health")
            return response.status_code == 200
    except:
        return False

@app.get("/api/agents")
async def api_agents():
    """Get agents - SIMPLE RELIABLE VERSION"""
    return await get_agents()

async def get_agents():
    """Get agents from broker or ledger"""
    try:
        # Try broker first
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get("http://127.0.0.1:5555/agents")
            if response.status_code == 200:
                data = response.json()
                agents_list = []
                for agent_id, info in data.get("agents", {}).items():
                    agents_list.append({
                        "agent_id": agent_id,
                        "agent_type": info.get("agent_type", "unknown"),
                        "status": info.get("status", "unknown"),
                        "endpoint": info.get("endpoint", ""),
                        "last_seen": info.get("last_seen", ""),
                        "intents_received": info.get("intents_received", 0),
                        "intents_completed": info.get("intents_completed", 0),
                        "metadata": info.get("metadata", {})
                    })
                return {"agents": agents_list, "count": len(agents_list)}
    except Exception as e:
        logger.warning(f"Could not fetch agents from broker: {e}")
    
    # Fallback: extract from ledger
    return await extract_agents_from_ledger()

async def extract_agents_from_ledger():
    """Extract agents from task ledger"""
    ledger_path = Path("data/task_ledger.jsonl")
    agents = {}
    
    if ledger_path.exists():
        try:
            # Read last 100 lines
            with open(ledger_path, 'r') as f:
                lines = f.readlines()[-100:]
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    agent_id = data.get('assigned_agent')
                    if agent_id and agent_id not in agents:
                        agents[agent_id] = {
                            "agent_id": agent_id,
                            "agent_type": "unknown",
                            "status": "active",
                            "intents_received": 0,
                            "last_seen": data.get('updated_at', '')
                        }
                except:
                    continue
        except Exception as e:
            logger.error(f"Error reading ledger: {e}")
    
    agents_list = list(agents.values())
    return {"agents": agents_list, "count": len(agents_list)}

@app.get("/api/intents/recent")
async def api_intents_recent(limit: int = 10):
    """Get recent intents - SIMPLE RELIABLE VERSION"""
    intents = await get_recent_intents(limit)
    return {
        "status": "success",
        "count": len(intents),
        "intents": intents
    }

async def get_recent_intents(limit: int = 10):
    """Get recent intents from ledger - SIMPLE AND RELIABLE"""
    ledger_path = Path("data/task_ledger.jsonl")
    intents = []
    
    if not ledger_path.exists():
        return intents
    
    try:
        # SIMPLE: Read last N*2 lines and filter
        with open(ledger_path, 'r') as f:
            lines = f.readlines()
        
        # Process from end
        processed = 0
        for line in reversed(lines):
            if processed >= limit * 3:  # Look at 3x limit
                break
            processed += 1
            
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # Check if it looks like an intent
                is_intent = False
                tags = data.get('tags', [])
                title = data.get('title', '')
                
                # Multiple ways to identify intents
                if 'intent' in tags:
                    is_intent = True
                elif 'Intent:' in title:
                    is_intent = True
                elif data.get('assigned_agent'):
                    is_intent = True  # Has an assigned agent
                
                if is_intent:
                    intent_type = title.replace('Intent: ', '') if 'Intent:' in title else 'task'
                    if intent_type == 'task' and 'task_type' in data:
                        intent_type = data['task_type']
                    
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
            except Exception as e:
                logger.warning(f"Error parsing line: {e}")
                continue
        
        # Ensure we have timestamps for sorting
        for intent in intents:
            if not intent.get('timestamp'):
                intent['timestamp'] = datetime.utcnow().isoformat()
        
        # Sort by timestamp (most recent first)
        intents.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
    except Exception as e:
        logger.error(f"Error getting intents: {e}")
    
    return intents[:limit]

@app.get("/api/stats")
async def api_stats():
    """Get system statistics"""
    try:
        # Get broker health
        broker_health = {}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get("http://127.0.0.1:5555/health")
                if response.status_code == 200:
                    broker_health = response.json()
        except:
            pass
        
        # Count intents
        ledger_path = Path("data/task_ledger.jsonl")
        total_intents = 0
        completed_intents = 0
        
        if ledger_path.exists():
            try:
                # Count last 1000 lines for performance
                with open(ledger_path, 'r') as f:
                    lines = f.readlines()[-1000:]
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if 'intent' in data.get('tags', []) or 'Intent:' in data.get('title', ''):
                            total_intents += 1
                            if data.get('status') == 'completed':
                                completed_intents += 1
                    except:
                        continue
            except:
                pass
        
        # Get recent intents for activity
        recent_intents = await get_recent_intents(50)
        recent_count = len([i for i in recent_intents 
                          if i.get('timestamp') and 
                          (datetime.utcnow() - datetime.fromisoformat(i['timestamp'].replace('Z', '+00:00'))).total_seconds() < 3600])
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "broker": {
                "agents_online": broker_health.get("agents_online", 0),
                "pending_intents": broker_health.get("pending_intents", 0),
                "state": broker_health.get("state", "unknown")
            },
            "dashboard": {
                "intents_processed": total_intents,
                "intents_completed": completed_intents,
                "completion_rate": completed_intents / total_intents if total_intents > 0 else 0
            },
            "recent_activity": {
                "intents_last_hour": recent_count,
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

@app.post("/api/send_test_intent")
async def api_send_test_intent():
    """Send a test intent"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                "http://127.0.0.1:5555/intents/route",
                json={
                    "intent_type": "status_check",
                    "source_agent": "dashboard",
                    "target_agent": "auto",
                    "params": {
                        "test": True,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if response.status_code == 200:
                return {"status": "success", "message": "Test intent sent successfully"}
            else:
                return {"status": "error", "message": f"Broker returned {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/check_health")
async def api_check_health():
    """Check health of all services"""
    services = {
        "broker": await check_broker(),
        "dashboard": True,
        "ledger": Path("data/task_ledger.jsonl").exists()
    }
    
    all_healthy = all(services.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": services,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/api/logs")
async def api_logs():
    """View recent logs"""
    log_files = [
        "logs/gate4_agent.log",
        "logs/dashboard.log",
        "logs/broker.log"
    ]
    
    logs = {}
    for log_file in log_files:
        path = Path(log_file)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    lines = f.readlines()[-50:]  # Last 50 lines
                    logs[log_file] = "".join(lines)
            except:
                logs[log_file] = "Could not read log"
        else:
            logs[log_file] = "Log file not found"
    
    # Return as HTML for easy viewing
    html = "<h1>System Logs</h1>"
    for filename, content in logs.items():
        html += f"<h2>{filename}</h2>"
        html += f"<pre style='background: #1e293b; padding: 10px; border-radius: 5px; overflow: auto;'>{content}</pre>"
    
    return HTMLResponse(content=html)

if __name__ == "__main__":
    logger.info("🚀 Starting SIMP Dashboard v4.0 on http://localhost:8050")
    logger.info("   Simple, reliable, shows real data")
    uvicorn.run(app, host="127.0.0.1", port=8050, log_level="info")