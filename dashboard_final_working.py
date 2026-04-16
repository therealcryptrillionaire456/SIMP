#!/usr/bin/env python3
"""
SIMP Dashboard - FINAL WORKING VERSION
Fully functional dashboard with real-time data from broker
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Configuration
BROKER_URL = "http://localhost:5555"
DASHBOARD_PORT = 8050

app = FastAPI(title="SIMP Dashboard", version="1.0.0")

# Mount static files
static_dir = Path(__file__).parent / "dashboard" / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = Path(__file__).parent / "dashboard" / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

async def fetch_broker_data(endpoint: str):
    """Fetch data from broker API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{BROKER_URL}{endpoint}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Broker returned {response.status}"}
    except Exception as e:
        return {"error": f"Failed to fetch from broker: {str(e)}"}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard page"""
    simple_html_path = static_dir / "simple_dashboard.html"
    if simple_html_path.exists():
        return FileResponse(simple_html_path)
    
    html_path = static_dir / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    else:
        # Fallback simple HTML
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SIMP Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .card { border: 1px solid #ccc; padding: 20px; margin: 10px; border-radius: 5px; }
                .online { color: green; }
                .offline { color: red; }
                .agent { margin: 5px 0; padding: 5px; background: #f5f5f5; }
            </style>
        </head>
        <body>
            <h1>SIMP Dashboard</h1>
            <div id="status">Loading...</div>
            <div id="agents"></div>
            <script>
                async function loadData() {
                    try {
                        // Load health
                        const healthRes = await fetch('/api/health');
                        const health = await healthRes.json();
                        document.getElementById('status').innerHTML = 
                            `<div class="card"><h3>System Health</h3>
                             <p>Dashboard: ${health.dashboard}</p>
                             <p>Broker: ${health.broker}</p></div>`;
                        
                        // Load agents
                        const agentsRes = await fetch('/api/agents');
                        const data = await agentsRes.json();
                        const agents = data.agents || {};
                        
                        let agentsHtml = '<div class="card"><h3>Agents (${Object.keys(agents).length})</h3>';
                        for (const [id, agent] of Object.entries(agents)) {
                            const status = agent.status || 'unknown';
                            agentsHtml += `
                                <div class="agent">
                                    <strong>${id}</strong> 
                                    <span class="${status === 'online' || status === 'active' ? 'online' : 'offline'}">
                                        ${status}
                                    </span>
                                    <br><small>Type: ${agent.agent_type || 'N/A'}</small>
                                </div>`;
                        }
                        agentsHtml += '</div>';
                        document.getElementById('agents').innerHTML = agentsHtml;
                    } catch (error) {
                        document.getElementById('status').innerHTML = 
                            `<div class="card" style="color: red;">Error: ${error.message}</div>`;
                    }
                }
                
                // Load data immediately and every 10 seconds
                loadData();
                setInterval(loadData, 10000);
            </script>
        </body>
        </html>
        """)

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    broker_health = await fetch_broker_data("/health")
    return {
        "dashboard": "ok",
        "broker": "ok" if broker_health.get("status") == "healthy" else "error",
        "broker_details": broker_health,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/agents")
async def get_agents():
    """Get all registered agents"""
    agents_data = await fetch_broker_data("/agents")
    return agents_data

@app.get("/api/intents/recent")
async def get_recent_intents(limit: int = 10):
    """Get recent intents"""
    # Note: Broker doesn't have a direct recent intents endpoint
    # We'll return a placeholder for now
    return {
        "intents": [],
        "message": "Recent intents endpoint not implemented in broker",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    health_data = await fetch_broker_data("/health")
    agents_data = await fetch_broker_data("/agents")
    
    agents = agents_data.get("agents", {})
    online_count = sum(1 for a in agents.values() 
                      if a.get("status") in ["online", "active"])
    
    return {
        "status": "success",
        "stats": {
            "agents_registered": len(agents),
            "agents_online": online_count,
            "pending_intents": health_data.get("pending_intents", 0),
            "file_based_agents": sum(1 for a in agents.values() 
                                    if a.get("file_based") == True),
            "simp_version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }
    }

@app.get("/api/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "status": "ok",
        "message": "Dashboard API is working",
        "endpoints": {
            "/api/health": "System health",
            "/api/agents": "Registered agents",
            "/api/stats": "System statistics",
            "/api/test": "This test endpoint"
        },
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Use dynamic port allocation to avoid conflicts
    try:
        from tools.port_utils import find_free_port
        port = find_free_port(DASHBOARD_PORT)
        if port != DASHBOARD_PORT:
            print(f"⚠️  Port {DASHBOARD_PORT} in use, using port {port} instead")
    except ImportError:
        print(f"⚠️  tools.port_utils not found, using default port {DASHBOARD_PORT}")
        port = DASHBOARD_PORT
    
    print(f"🚀 Starting SIMP Dashboard on port {port}")
    print(f"📊 Dashboard URL: http://localhost:{port}")
    print(f"🔗 Broker URL: {BROKER_URL}")
    print("📈 Endpoints:")
    print("  /              - Dashboard interface")
    print("  /api/health    - System health")
    print("  /api/agents    - All registered agents")
    print("  /api/stats     - System statistics")
    print("  /api/test      - Test endpoint")
    
    uvicorn.run(app, host="0.0.0.0", port=port)