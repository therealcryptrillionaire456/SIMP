#!/usr/bin/env python3
"""
Mother Goose Web Dashboard - Web interface for monitoring flock progress.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import threading

from mother_goose_dashboard import get_mother_goose

app = FastAPI(title="Mother Goose Dashboard", version="1.0.0")

# Get the mother goose instance
mother_goose = get_mother_goose()

# WebSocket connections
connections = []

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the dashboard HTML."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mother Goose Dashboard - Mesh Protocol Flock</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            }
            
            header {
                text-align: center;
                margin-bottom: 40px;
                padding-bottom: 20px;
                border-bottom: 3px solid #667eea;
            }
            
            h1 {
                color: #2d3748;
                font-size: 2.8rem;
                margin-bottom: 10px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            
            .subtitle {
                color: #718096;
                font-size: 1.2rem;
                font-weight: 300;
            }
            
            .overall-progress {
                background: linear-gradient(135deg, #4fd1c5 0%, #319795 100%);
                color: white;
                padding: 25px;
                border-radius: 15px;
                margin-bottom: 30px;
                text-align: center;
            }
            
            .progress-bar {
                height: 30px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 15px;
                margin: 15px 0;
                overflow: hidden;
            }
            
            .progress-fill {
                height: 100%;
                background: white;
                border-radius: 15px;
                transition: width 0.5s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #319795;
                font-weight: bold;
                font-size: 0.9rem;
            }
            
            .layers-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }
            
            .layer-card {
                background: white;
                border-radius: 15px;
                padding: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                border: 2px solid #e2e8f0;
                transition: all 0.3s ease;
            }
            
            .layer-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
                border-color: #667eea;
            }
            
            .layer-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }
            
            .layer-number {
                background: #667eea;
                color: white;
                width: 40px;
                height: 40px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 1.2rem;
            }
            
            .layer-status {
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 600;
                text-transform: uppercase;
            }
            
            .status-not_started { background: #fed7d7; color: #c53030; }
            .status-in_progress { background: #feebc8; color: #dd6b20; }
            .status-completed { background: #c6f6d5; color: #276749; }
            .status-verified { background: #b2f5ea; color: #234e52; }
            
            .layer-name {
                font-size: 1.4rem;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 10px;
            }
            
            .layer-progress-bar {
                height: 10px;
                background: #e2e8f0;
                border-radius: 5px;
                margin: 10px 0;
                overflow: hidden;
            }
            
            .layer-progress-fill {
                height: 100%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 5px;
                transition: width 0.5s ease;
            }
            
            .geese-section {
                background: white;
                border-radius: 15px;
                padding: 25px;
                margin-top: 30px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            }
            
            .geese-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            
            .goose-card {
                background: #f7fafc;
                border-radius: 12px;
                padding: 20px;
                border-left: 5px solid #667eea;
            }
            
            .goose-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            
            .goose-id {
                font-weight: bold;
                color: #2d3748;
                font-size: 1.1rem;
            }
            
            .goose-status {
                padding: 3px 10px;
                border-radius: 15px;
                font-size: 0.75rem;
                font-weight: 600;
            }
            
            .status-working { background: #c6f6d5; color: #276749; }
            .status-stuck { background: #fed7d7; color: #c53030; }
            .status-completed { background: #b2f5ea; color: #234e52; }
            .status-idle { background: #e2e8f0; color: #4a5568; }
            
            .goose-description {
                color: #718096;
                margin-bottom: 15px;
                font-size: 0.9rem;
            }
            
            .goose-progress {
                margin-top: 10px;
            }
            
            .timestamp {
                font-size: 0.8rem;
                color: #a0aec0;
                margin-top: 15px;
                text-align: right;
            }
            
            .stuck-alert {
                background: linear-gradient(135deg, #fc8181 0%, #c53030 100%);
                color: white;
                padding: 20px;
                border-radius: 15px;
                margin-top: 30px;
                animation: pulse 2s infinite;
            }
            
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.8; }
                100% { opacity: 1; }
            }
            
            .alert-header {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 15px;
            }
            
            .alert-icon {
                font-size: 1.5rem;
            }
            
            .websocket-status {
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: #2d3748;
                color: white;
                padding: 10px 20px;
                border-radius: 25px;
                font-size: 0.9rem;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .ws-connected { background: #38a169; }
            .ws-disconnected { background: #e53e3e; }
            
            .ws-dot {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                animation: blink 1s infinite;
            }
            
            @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            .controls {
                display: flex;
                gap: 10px;
                margin-top: 20px;
            }
            
            button {
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                background: #667eea;
                color: white;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            button:hover {
                background: #764ba2;
                transform: translateY(-2px);
            }
            
            button:disabled {
                background: #cbd5e0;
                cursor: not-allowed;
                transform: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Mother Goose Dashboard</h1>
                <div class="subtitle">Mesh Protocol Flock Coordination System</div>
            </header>
            
            <div class="overall-progress">
                <h2>Overall Progress</h2>
                <div class="progress-bar">
                    <div class="progress-fill" id="overall-progress-fill">0%</div>
                </div>
                <div id="overall-stats">Loading...</div>
            </div>
            
            <h2>Mesh Protocol Layers</h2>
            <div class="layers-grid" id="layers-container">
                <!-- Layers will be populated by JavaScript -->
            </div>
            
            <div class="geese-section">
                <h2>Goose Workers</h2>
                <div class="controls">
                    <button onclick="refreshData()">Refresh Data</button>
                    <button onclick="saveSnapshot()">Save Snapshot</button>
                    <button onclick="loadSnapshot()">Load Snapshot</button>
                </div>
                <div id="stuck-alerts"></div>
                <div class="geese-grid" id="geese-container">
                    <!-- Geese will be populated by JavaScript -->
                </div>
            </div>
            
            <div class="timestamp" id="last-update">
                Last updated: Loading...
            </div>
        </div>
        
        <div class="websocket-status" id="ws-status">
            <div class="ws-dot"></div>
            <span>Connecting...</span>
        </div>
        
        <script>
            let ws = null;
            let data = null;
            
            function connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;
                
                ws = new WebSocket(wsUrl);
                
                ws.onopen = () => {
                    console.log('WebSocket connected');
                    updateWsStatus(true);
                };
                
                ws.onmessage = (event) => {
                    const message = JSON.parse(event.data);
                    if (message.type === 'dashboard_update') {
                        data = message.data;
                        updateDashboard();
                    }
                };
                
                ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    updateWsStatus(false);
                    // Try to reconnect after 3 seconds
                    setTimeout(connectWebSocket, 3000);
                };
                
                ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                };
            }
            
            function updateWsStatus(connected) {
                const statusEl = document.getElementById('ws-status');
                const dot = statusEl.querySelector('.ws-dot');
                const text = statusEl.querySelector('span');
                
                if (connected) {
                    statusEl.className = 'websocket-status ws-connected';
                    dot.style.background = '#68d391';
                    text.textContent = 'Live Updates Connected';
                } else {
                    statusEl.className = 'websocket-status ws-disconnected';
                    dot.style.background = '#fc8181';
                    text.textContent = 'Disconnected - Reconnecting...';
                }
            }
            
            function updateDashboard() {
                if (!data) return;
                
                // Update overall progress
                const overallProgress = data.overall_progress * 100;
                const progressFill = document.getElementById('overall-progress-fill');
                progressFill.style.width = `${overallProgress}%`;
                progressFill.textContent = `${overallProgress.toFixed(1)}%`;
                
                document.getElementById('overall-stats').innerHTML = `
                    ${data.layers.filter(l => l.status === 'verified').length} layers verified |
                    ${data.layers.filter(l => l.status === 'completed').length} layers completed |
                    ${data.layers.filter(l => l.status === 'in_progress').length} layers in progress
                `;
                
                // Update layers
                const layersContainer = document.getElementById('layers-container');
                layersContainer.innerHTML = data.layers.map(layer => `
                    <div class="layer-card">
                        <div class="layer-header">
                            <div class="layer-number">${layer.number}</div>
                            <div class="layer-status status-${layer.status}">${layer.status.replace('_', ' ')}</div>
                        </div>
                        <div class="layer-name">${layer.name}</div>
                        <div class="layer-progress-bar">
                            <div class="layer-progress-fill" style="width: ${layer.progress * 100}%"></div>
                        </div>
                        <div style="font-size: 0.9rem; color: #718096;">
                            ${layer.geese_assigned} geese assigned | 
                            ${layer.verification_passed ? '✓ Verified' : 'Not verified'}
                        </div>
                    </div>
                `).join('');
                
                // Update geese
                const geeseContainer = document.getElementById('geese-container');
                geeseContainer.innerHTML = '';
                
                // Add geese by status
                const statusOrder = ['working', 'stuck', 'completed', 'idle'];
                for (const status of statusOrder) {
                    const geese = data.geese_by_status[status] || [];
                    for (const goose of geese) {
                        const gooseCard = document.createElement('div');
                        gooseCard.className = 'goose-card';
                        gooseCard.innerHTML = `
                            <div class="goose-header">
                                <div class="goose-id">${goose.goose_id}</div>
                                <div class="goose-status status-${goose.status}">${goose.status}</div>
                            </div>
                            <div class="goose-description">${goose.description}</div>
                            <div>Layer ${goose.layer} | Progress: ${(goose.progress * 100).toFixed(1)}%</div>
                            <div class="goose-progress">
                                <div class="layer-progress-bar">
                                    <div class="layer-progress-fill" style="width: ${goose.progress * 100}%"></div>
                                </div>
                            </div>
                            <div style="font-size: 0.8rem; color: #a0aec0; margin-top: 10px;">
                                Last update: ${new Date(goose.last_update).toLocaleTimeString()}
                            </div>
                        `;
                        geeseContainer.appendChild(gooseCard);
                    }
                }
                
                // Update stuck alerts
                const stuckAlerts = document.getElementById('stuck-alerts');
                if (data.stuck_geese && data.stuck_geese.length > 0) {
                    stuckAlerts.innerHTML = `
                        <div class="stuck-alert">
                            <div class="alert-header">
                                <div class="alert-icon">⚠️</div>
                                <h3>${data.stuck_geese.length} Goose(s) Stuck!</h3>
                            </div>
                            <div style="margin-left: 30px;">
                                ${data.stuck_geese.map(goose => `
                                    <div style="margin-bottom: 5px;">
                                        <strong>${goose.goose_id}</strong>: ${goose.description}
                                        (Progress: ${(goose.progress * 100).toFixed(1)}%)
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                } else {
                    stuckAlerts.innerHTML = '';
                }
                
                // Update timestamp
                document.getElementById('last-update').textContent = 
                    `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
            }
            
            function refreshData() {
                fetch('/api/dashboard')
                    .then(response => response.json())
                    .then(newData => {
                        data = newData;
                        updateDashboard();
                    })
                    .catch(error => console.error('Error refreshing data:', error));
            }
            
            function saveSnapshot() {
                fetch('/api/save-snapshot', { method: 'POST' })
                    .then(response => response.json())
                    .then(result => {
                        alert(result.message);
                    })
                    .catch(error => console.error('Error saving snapshot:', error));
            }
            
            function loadSnapshot() {
                fetch('/api/load-snapshot', { method: 'POST' })
                    .then(response => response.json())
                    .then(result => {
                        alert(result.message);
                        refreshData();
                    })
                    .catch(error => console.error('Error loading snapshot:', error));
            }
            
            // Initialize
            connectWebSocket();
            refreshData();
            
            // Auto-refresh every 30 seconds as fallback
            setInterval(refreshData, 30000);
        </script>
    </body>
    </html>
    """

@app.get("/api/dashboard")
async def get_dashboard_data():
    """Get current dashboard data."""
    return mother_goose.get_dashboard_data()

@app.post("/api/save-snapshot")
async def save_snapshot():
    """Save current state to disk."""
    mother_goose.save_snapshot()
    return {"message": "Snapshot saved successfully"}

@app.post("/api/load-snapshot")
async def load_snapshot():
    """Load state from disk."""
    success = mother_goose.load_snapshot()
    if success:
        return {"message": "Snapshot loaded successfully"}
    else:
        return {"message": "Failed to load snapshot"}

@app.post("/api/reprompt-goose/{goose_id}")
async def reprompt_goose(goose_id: str, instructions: str):
    """Reprompt a stuck goose."""
    success = mother_goose.reprompt_goose(goose_id, instructions)
    if success:
        return {"message": f"Goose {goose_id} reprompted successfully"}
    else:
        return {"message": f"Failed to reprompt goose {goose_id}"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await manager.connect(websocket)
    try:
        # Send initial data
        data = mother_goose.get_dashboard_data()
        await websocket.send_json({
            "type": "dashboard_update",
            "data": data
        })
        
        # Keep connection alive
        while True:
            await websocket.receive_text()
            # We'll send updates via broadcast from monitoring thread
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def broadcast_updates():
    """Background thread to broadcast updates to all WebSocket clients."""
    while True:
        try:
            data = mother_goose.get_dashboard_data()
            # Run in event loop
            import asyncio
            asyncio.run(manager.broadcast({
                "type": "dashboard_update",
                "data": data
            }))
        except Exception as e:
            print(f"Error broadcasting updates: {e}")
        time.sleep(5)  # Update every 5 seconds

if __name__ == "__main__":
    # Start mother goose monitoring
    mother_goose.start_monitoring()
    
    # Start broadcast thread
    broadcast_thread = threading.Thread(target=broadcast_updates, daemon=True)
    broadcast_thread.start()
    
    # Start web server
    print("Starting Mother Goose Web Dashboard on http://localhost:8775")
    print("Press Ctrl+C to stop")
    
    uvicorn.run(app, host="0.0.0.0", port=8775)