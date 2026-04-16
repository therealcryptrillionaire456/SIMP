"""
SIMP Dashboard - Fixed Version
Properly serves HTML and shows real data from broker
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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

# Mount static files
static_dir = Path(__file__).parent / "dashboard" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Broker URL
BROKER_URL = "http://127.0.0.1:5555"

async def broker_get(path: str):
    """Fetch data from broker"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BROKER_URL}{path}")
            return response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.error(f"Broker request failed: {e}")
        return None

@app.get("/")
async def root():
    """Serve the dashboard HTML"""
    html_path = static_dir / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    else:
        # Fallback HTML
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head><title>SIMP Dashboard</title></head>
        <body>
            <h1>SIMP Dashboard</h1>
            <p>Dashboard is loading...</p>
        </body>
        </html>
        """)

@app.get("/api/health")
async def api_health():
    """Health check"""
    broker_health = await broker_get("/health")
    return {
        "dashboard": "ok",
        "broker": "ok" if broker_health else "unreachable",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/agents")
async def api_agents():
    """Get agents from broker"""
    agents_data = await broker_get("/agents")
    if agents_data and "agents" in agents_data:
        return {"agents": agents_data["agents"]}
    return {"agents": []}

@app.get("/api/intents/recent")
async def api_intents_recent(limit: int = 10):
    """Get recent intents"""
    intents_data = await broker_get(f"/intents?limit={limit}")
    if intents_data and "intents" in intents_data:
        return {"intents": intents_data["intents"]}
    return {"intents": []}

@app.get("/api/stats")
async def api_stats():
    """Get system stats"""
    stats_data = await broker_get("/stats")
    if stats_data:
        return stats_data
    return {"total_intents": 0, "active_agents": 0}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8050, log_level="info")