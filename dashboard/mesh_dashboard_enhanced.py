"""
Enhanced Mesh Dashboard for SIMP Ecosystem
Features:
- Real-time mesh visualization
- Network topology viewer
- Message flow monitoring
- Security audit viewer
- Performance analytics
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import threading

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class EnhancedMeshDashboard:
    """
    Enhanced dashboard for monitoring SIMP mesh network.
    """
    
    def __init__(
        self,
        broker_url: str = "http://localhost:5555",
        mesh_bus_url: str = "http://localhost:8765",
        dashboard_port: int = 8060,
    ):
        """
        Initialize enhanced mesh dashboard.
        
        Args:
            broker_url: SIMP broker URL
            mesh_bus_url: Mesh bus HTTP endpoint
            dashboard_port: Dashboard port
        """
        self.broker_url = broker_url.rstrip("/")
        self.mesh_bus_url = mesh_bus_url.rstrip("/")
        self.dashboard_port = dashboard_port
        
        # FastAPI app
        self.app = FastAPI(title="SIMP Mesh Dashboard")
        
        # WebSocket connections
        self.active_connections: List[WebSocket] = []
        self.connection_lock = threading.Lock()
        
        # Data cache
        self._cache = {
            "mesh_stats": {},
            "topology": {},
            "message_flow": [],
            "security_events": [],
            "performance_metrics": {},
            "last_update": 0,
        }
        
        # Update interval (seconds)
        self.update_interval = 5
        
        # HTTP client
        self._client = httpx.Client(timeout=10.0)
        
        # Setup routes
        self._setup_routes()
        
        # Start background updater
        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        
        logger.info(f"Enhanced Mesh Dashboard initialized on port {dashboard_port}")
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/")
        async def root():
            """Serve dashboard HTML."""
            html = self._generate_dashboard_html()
            return HTMLResponse(html)
        
        @self.app.get("/api/mesh/stats")
        async def get_mesh_stats():
            """Get mesh statistics."""
            return await self.fetch_mesh_stats()
        
        @self.app.get("/api/mesh/topology")
        async def get_topology():
            """Get network topology."""
            return await self.fetch_topology()
        
        @self.app.get("/api/mesh/messages")
        async def get_recent_messages(limit: int = 50):
            """Get recent messages."""
            return await self.fetch_recent_messages(limit)
        
        @self.app.get("/api/mesh/security")
        async def get_security_events(limit: int = 100):
            """Get security events."""
            return await self.fetch_security_events(limit)
        
        @self.app.get("/api/mesh/performance")
        async def get_performance_metrics():
            """Get performance metrics."""
            return await self.fetch_performance_metrics()
        
        @self.app.get("/api/mesh/agents")
        async def get_mesh_agents():
            """Get mesh agents."""
            return await self.fetch_mesh_agents()
        
        @self.app.get("/api/health")
        async def health():
            """Health check."""
            return {
                "status": "healthy",
                "service": "mesh_dashboard",
                "timestamp": datetime.utcnow().isoformat(),
                "cache_age": time.time() - self._cache["last_update"],
            }
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self._handle_websocket(websocket)
    
    def _generate_dashboard_html(self) -> str:
        """Generate dashboard HTML."""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SIMP Mesh Dashboard</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: #0f172a;
                    color: #e2e8f0;
                }}
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                }}
                .header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid #334155;
                }}
                .header h1 {{
                    margin: 0;
                    color: #60a5fa;
                    font-size: 28px;
                }}
                .header .status {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .status-dot {{
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    background: #10b981;
                }}
                .status-dot.offline {{ background: #ef4444; }}
                .status-dot.warning {{ background: #f59e0b; }}
                .dashboard-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .card {{
                    background: #1e293b;
                    border-radius: 10px;
                    padding: 20px;
                    border: 1px solid #334155;
                }}
                .card h2 {{
                    margin-top: 0;
                    color: #94a3b8;
                    font-size: 16px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
                .card h3 {{
                    margin: 10px 0;
                    color: #e2e8f0;
                    font-size: 24px;
                }}
                .metric-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 15px;
                }}
                .metric {{
                    text-align: center;
                }}
                .metric .value {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #60a5fa;
                }}
                .metric .label {{
                    font-size: 12px;
                    color: #94a3b8;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .topology-container {{
                    grid-column: 1 / -1;
                    height: 500px;
                    background: #0f172a;
                    border-radius: 10px;
                    overflow: hidden;
                    position: relative;
                }}
                #topology-canvas {{
                    width: 100%;
                    height: 100%;
                }}
                .message-list {{
                    max-height: 400px;
                    overflow-y: auto;
                }}
                .message-item {{
                    padding: 10px;
                    margin-bottom: 5px;
                    background: #334155;
                    border-radius: 5px;
                    border-left: 4px solid #60a5fa;
                }}
                .message-item.error {{ border-left-color: #ef4444; }}
                .message-item.warning {{ border-left-color: #f59e0b; }}
                .message-item.success {{ border-left-color: #10b981; }}
                .message-header {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 5px;
                }}
                .message-agent {{
                    font-weight: bold;
                    color: #60a5fa;
                }}
                .message-time {{
                    font-size: 12px;
                    color: #94a3b8;
                }}
                .message-content {{
                    font-size: 14px;
                    color: #cbd5e1;
                }}
                .security-event {{
                    padding: 8px;
                    margin-bottom: 5px;
                    background: #1e293b;
                    border-radius: 5px;
                    border-left: 4px solid;
                    font-size: 12px;
                }}
                .security-event.alert {{ border-left-color: #ef4444; }}
                .security-event.warning {{ border-left-color: #f59e0b; }}
                .security-event.info {{ border-left-color: #60a5fa; }}
                .security-event.success {{ border-left-color: #10b981; }}
                .refresh-btn {{
                    background: #3b82f6;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 14px;
                }}
                .refresh-btn:hover {{
                    background: #2563eb;
                }}
                .auto-refresh {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin-top: 10px;
                }}
                .auto-refresh label {{
                    font-size: 14px;
                    color: #94a3b8;
                }}
            </style>
            <script src="https://d3js.org/d3.v7.min.js"></script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🕸️ SIMP Mesh Dashboard</h1>
                    <div class="status">
                        <div class="status-dot" id="status-dot"></div>
                        <span id="status-text">Connecting...</span>
                        <button class="refresh-btn" onclick="refreshAll()">Refresh</button>
                    </div>
                </div>
                
                <div class="dashboard-grid">
                    <!-- Stats Overview -->
                    <div class="card">
                        <h2>Mesh Overview</h2>
                        <div class="metric-grid" id="overview-metrics">
                            <div class="metric">
                                <div class="value" id="agents-count">0</div>
                                <div class="label">Agents</div>
                            </div>
                            <div class="metric">
                                <div class="value" id="messages-total">0</div>
                                <div class="label">Messages</div>
                            </div>
                            <div class="metric">
                                <div class="value" id="delivery-rate">0%</div>
                                <div class="label">Delivery Rate</div>
                            </div>
                            <div class="metric">
                                <div class="value" id="avg-latency">0ms</div>
                                <div class="label">Avg Latency</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Security Overview -->
                    <div class="card">
                        <h2>Security Status</h2>
                        <div class="metric-grid" id="security-metrics">
                            <div class="metric">
                                <div class="value" id="encrypted-msgs">0</div>
                                <div class="label">Encrypted</div>
                            </div>
                            <div class="metric">
                                <div class="value" id="signed-msgs">0</div>
                                <div class="label">Signed</div>
                            </div>
                            <div class="metric">
                                <div class="value" id="violations">0</div>
                                <div class="label">Violations</div>
                            </div>
                            <div class="metric">
                                <div class="value" id="access-denied">0</div>
                                <div class="label">Access Denied</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Network Topology -->
                    <div class="card topology-container">
                        <h2>Network Topology</h2>
                        <svg id="topology-canvas"></svg>
                    </div>
                    
                    <!-- Recent Messages -->
                    <div class="card">
                        <h2>Recent Messages</h2>
                        <div class="auto-refresh">
                            <label>
                                <input type="checkbox" id="auto-refresh" checked>
                                Auto-refresh (5s)
                            </label>
                        </div>
                        <div class="message-list" id="message-list">
                            <!-- Messages will be inserted here -->
                        </div>
                    </div>
                    
                    <!-- Security Events -->
                    <div class="card">
                        <h2>Security Events</h2>
                        <div id="security-events">
                            <!-- Security events will be inserted here -->
                        </div>
                    </div>
                </div>
            </div>
            
            <script>
                let ws = null;
                let autoRefresh = true;
                let topologyData = {{}};
                
                // Initialize WebSocket
                function connectWebSocket() {{
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = `${{protocol}}//${{window.location.host}}/ws`;
                    
                    ws = new WebSocket(wsUrl);
                    
                    ws.onopen = () => {{
                        console.log('WebSocket connected');
                        document.getElementById('status-dot').className = 'status-dot';
                        document.getElementById('status-text').textContent = 'Connected';
                    }};
                    
                    ws.onmessage = (event) => {{
                        const data = JSON.parse(event.data);
                        updateDashboard(data);
                    }};
                    
                    ws.onclose = () => {{
                        console.log('WebSocket disconnected');
                        document.getElementById('status-dot').className = 'status-dot offline';
                        document.getElementById('status-text').textContent = 'Disconnected';
                        // Reconnect after 3 seconds
                        setTimeout(connectWebSocket, 3000);
                    }};
                    
                    ws.onerror = (error) => {{
                        console.error('WebSocket error:', error);
                        document.getElementById('status-dot').className = 'status-dot warning';
                        document.getElementById('status-text').textContent = 'Error';
                    }};
                }}
                
                // Update dashboard with new data
                function updateDashboard(data) {{
                    if (data.mesh_stats) {{
                        updateOverview(data.mesh_stats);
                    }}
                    if (data.topology) {{
                        topologyData = data.topology;
                        updateTopology();
                    }}
                    if (data.message_flow) {{
                        updateMessageList(data.message_flow);
                    }}
                    if (data.security_events) {{
                        updateSecurityEvents(data.security_events);
                    }}
                    if (data.performance_metrics) {{
                        updatePerformance(data.performance_metrics);
                    }}
                }}
                
                // Update overview metrics
                function updateOverview(stats) {{
                    document.getElementById('agents-count').textContent = stats.agents_count || 0;
                    document.getElementById('messages-total').textContent = stats.messages_total || 0;
                    document.getElementById('delivery-rate').textContent = stats.delivery_rate || '0%';
                    document.getElementById('avg-latency').textContent = `${{stats.avg_latency_ms || 0}}ms`;
                    
                    // Security metrics
                    document.getElementById('encrypted-msgs').textContent = stats.encrypted_messages || 0;
                    document.getElementById('signed-msgs').textContent = stats.signed_messages || 0;
                    document.getElementById('violations').textContent = stats.security_violations || 0;
                    document.getElementById('access-denied').textContent = stats.access_denied || 0;
                }}
                
                // Update network topology visualization
                function updateTopology() {{
                    const svg = d3.select('#topology-canvas');
                    const width = svg.node().getBoundingClientRect().width;
                    const height = svg.node().getBoundingClientRect().height;
                    
                    // Clear previous visualization
                    svg.selectAll('*').remove();
                    
                    if (!topologyData.peers || Object.keys(topologyData.peers).length === 0) {{
                        // Show message when no peers
                        svg.append('text')
                            .attr('x', width / 2)
                            .attr('y', height / 2)
                            .attr('text-anchor', 'middle')
                            .attr('fill', '#94a3b8')
                            .text('No peers discovered yet');
                        return;
                    }}
                    
                    // Create nodes from peers
                    const nodes = [];
                    const links = [];
                    
                    // Add local agent
                    nodes.push({{
                        id: topologyData.local_agent.agent_id,
                        type: 'local',
                        ...topologyData.local_agent
                    }});
                    
                    // Add peers
                    Object.values(topologyData.peers).forEach(peer => {{
                        nodes.push({{
                            id: peer.agent_id,
                            type: 'peer',
                            status: peer.status,
                            ...peer
                        }});
                        
                        // Create link to local agent
                        links.push({{
                            source: topologyData.local_agent.agent_id,
                            target: peer.agent_id,
                            strength: 0.3
                        }});
                    }});
                    
                    // Create force simulation
                    const simulation = d3.forceSimulation(nodes)
                        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
                        .force('charge', d3.forceManyBody().strength(-300))
                        .force('center', d3.forceCenter(width / 2, height / 2))
                        .force('collision', d3.forceCollide().radius(40));
                    
                    // Draw links
                    const link = svg.append('g')
                        .selectAll('line')
                        .data(links)
                        .enter().append('line')
                        .attr('stroke', '#475569')
                        .attr('stroke-width', 1)
                        .attr('stroke-opacity', 0.6);
                    
                    // Draw nodes
                    const node = svg.append('g')
                        .selectAll('g')
                        .data(nodes)
                        .enter().append('g')
                        .call(d3.drag()
                            .on('start', dragstarted)
                            .on('drag', dragged)
                            .on('end', dragended));
                    
                    // Add circles for nodes
                    node.append('circle')
                        .attr('r', d => d.type === 'local' ? 20 : 15)
                        .attr('fill', d => {{
                            if (d.type === 'local') return '#3b82f6';
                            if (d.status === 'online') return '#10b981';
                            if (d.status === 'offline') return '#ef4444';
                            if (d.status === 'unreachable') return '#f59e0b';
                            return '#94a3b8';
                        }})
                        .attr('stroke', '#0f172a')
                        .attr('stroke-width', 2);
                    
                    // Add labels
                    node.append('text')
                        .attr('dx', 0)
                        .attr('dy', d => d.type === 'local' ? 30 : 25)
                        .attr('text-anchor', 'middle')
                        .attr('fill', '#e2e8f0')
                        .attr('font-size', '12px')
                        .text(d => d.id.length > 10 ? d.id.substring(0, 10) + '...' : d.id);
                    
                    // Update positions on simulation tick
                    simulation.on('tick', () => {{
                        link
                            .attr('x1', d => d.source.x)
                            .attr('y1', d => d.source.y)
                            .attr('x2', d => d.target.x)
                            .attr('y2', d => d.target.y);
                        
                        node
                            .attr('transform', d => `translate(${{d.x}},${{d.y}})`);
                    }});
                    
                    // Drag functions
                    function dragstarted(event, d) {{
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x;
                        d.fy = d.y;
                    }}
                    
                    function dragged(event, d) {{
                        d.fx = event.x;
                        d.fy = event.y;
                    }}
                    
                    function dragended(event, d) {{
                        if (!event.active) simulation.alphaTarget(0);
                        d.fx = null;
                        d.fy = null;
                    }}
                }}
                
                // Update message list
                function updateMessageList(messages) {{
                    const container = document.getElementById('message-list');
                    container.innerHTML = '';
                    
                    messages.slice(0, 10).forEach(msg => {{
                        const div = document.createElement('div');
                        div.className = `message-item ${{msg.status || ''}}`;
                        
                        const header = document.createElement('div');
                        header.className = 'message-header';
                        
                        const agent = document.createElement('span');
                        agent.className = 'message-agent';
                        agent.textContent = `${{msg.source_agent}} → ${{msg.target_agent || msg.target_channel || 'broadcast'}}`;
                        
                        const time = document.createElement('span');
                        time.className = 'message-time';
                        time.textContent = new Date(msg.timestamp * 1000).toLocaleTimeString();
                        
                        header.appendChild(agent);
                        header.appendChild(time);
                        
                        const content = document.createElement('div');
                        content.className = 'message-content';
                        content.textContent = msg.message_type || 'Message';
                        
                        div.appendChild(header);
                        div.appendChild(content);
                        container.appendChild(div);
                    }});
                }}
                
                // Update security events
                function updateSecurityEvents(events) {{
                    const container = document.getElementById('security-events');
                    container.innerHTML = '';
                    
                    events.slice(0, 10).forEach(event => {{
                        const div = document.createElement('div');
                        div.className = `security-event ${{event.severity || 'info'}}`;
                        
                        const header = document.createElement('div');
                        header.style.display = 'flex';
                        header.style.justifyContent = 'space-between';
                        header.style.marginBottom = '3px';
                        
                        const type = document.createElement('span');
                        type.style.fontWeight = 'bold';
                        type.textContent = event.event_type;
                        
                        const time = document.createElement('span');
                        time.style.fontSize = '10px';
                        time.style.color = '#94a3b8';
                        time.textContent = new Date(event.timestamp).toLocaleTimeString();
                        
                        header.appendChild(type);
                        header.appendChild(time);
                        
                        const content = document.createElement('div');
                        content.textContent = event.action || '';
                        
                        div.appendChild(header);
                        div.appendChild(content);
                        container.appendChild(div);
                    }});
                }}
                
                // Update performance metrics
                function updatePerformance(metrics) {{
                    // Could add performance charts here
                }}
                
                // Refresh all data
                async function refreshAll() {{
                    try {{
                        const [stats, topology, messages, security, performance] = await Promise.all([
                            fetch('/api/mesh/stats').then(r => r.json()),
                            fetch('/api/mesh/topology').then(r => r.json()),
                            fetch('/api/mesh/messages?limit=10').then(r => r.json()),
                            fetch('/api/mesh/security?limit=10').then(r => r.json()),
                            fetch('/api/mesh/performance').then(r => r.json())
                        ]);
                        
                        updateDashboard({{
                            mesh_stats: stats,
                            topology: topology,
                            message_flow: messages,
                            security_events: security,
                            performance_metrics: performance
                        }});
                    }} catch (error) {{
                        console.error('Refresh failed:', error);
                    }}
                }}
                
                // Auto-refresh toggle
                document.getElementById('auto-refresh').addEventListener('change', (e) => {{
                    autoRefresh = e.target.checked;
                }});
                
                // Initial load
                connectWebSocket();
                refreshAll();
                
                // Auto-refresh interval
                setInterval(() => {{
                    if (autoRefresh && ws && ws.readyState === WebSocket.OPEN) {{
                        ws.send(JSON.stringify({{type: 'refresh'}}));
                    }}
                }}, 5000);
                
                // Handle window resize
                window.addEventListener('resize', updateTopology);
            </script>
        </body>
        </html>
        """
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection."""
        await websocket.accept()
        
        with self.connection_lock:
            self.active_connections.append(websocket)
        
        try:
            # Send initial data
            await self._send_websocket_update(websocket)
            
            # Handle incoming messages
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "refresh":
                    await self._send_websocket_update(websocket)
                
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            with self.connection_lock:
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)
    
    async def _send_websocket_update(self, websocket: WebSocket):
        """Send update to WebSocket client."""
        try:
            data = {
                "mesh_stats": await self.fetch_mesh_stats(),
                "topology": await self.fetch_topology(),
                "message_flow": await self.fetch_recent_messages(10),
                "security_events": await self.fetch_security_events(10),
                "performance_metrics": await self.fetch_performance_metrics(),
                "timestamp": time.time(),
            }
            
            await websocket.send_json(data)
            
        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {e}")
    
    async def _broadcast_update(self):
        """Broadcast update to all WebSocket clients."""
        if not self.active_connections:
            return
        
        data = {
            "mesh_stats": self._cache["mesh_stats"],
            "topology": self._cache["topology"],
            "message_flow": self._cache["message_flow"][:10],
            "security_events": self._cache["security_events"][:10],
            "performance_metrics": self._cache["performance_metrics"],
            "timestamp": time.time(),
        }
        
        with self.connection_lock:
            for connection in self.active_connections:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Failed to broadcast to WebSocket: {e}")
    
    async def fetch_mesh_stats(self) -> Dict[str, Any]:
        """Fetch mesh statistics."""
        try:
            # Try to get stats from mesh bus
            response = self._client.get(f"{self.mesh_bus_url}/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                self._cache["mesh_stats"] = stats
                return stats
            
        except Exception as e:
            logger.error(f"Failed to fetch mesh stats: {e}")
        
        # Return cached data if available
        return self._cache.get("mesh_stats", {})
    
    async def fetch_topology(self) -> Dict[str, Any]:
        """Fetch network topology."""
        try:
            # Try to get topology from discovery service
            response = self._client.get(f"{self.mesh_bus_url}/topology", timeout=5)
            if response.status_code == 200:
                topology = response.json()
                self._cache["topology"] = topology
                return topology
            
        except Exception as e:
            logger.error(f"Failed to fetch topology: {e}")
        
        # Return cached data if available
        return self._cache.get("topology", {})
    
    async def fetch_recent_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent messages."""
        try:
            # Try to get messages from mesh bus
            response = self._client.get(f"{self.mesh_bus_url}/messages?limit={limit}", timeout=5)
            if response.status_code == 200:
                messages = response.json()
                self._cache["message_flow"] = messages
                return messages
            
        except Exception as e:
            logger.error(f"Failed to fetch recent messages: {e}")
        
        # Return cached data if available
        return self._cache.get("message_flow", [])
    
    async def fetch_security_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch security events."""
        try:
            # Try to get security events from mesh bus
            response = self._client.get(f"{self.mesh_bus_url}/security/events?limit={limit}", timeout=5)
            if response.status_code == 200:
                events = response.json()
                self._cache["security_events"] = events
                return events
            
        except Exception as e:
            logger.error(f"Failed to fetch security events: {e}")
        
        # Return cached data if available
        return self._cache.get("security_events", [])
    
    async def fetch_performance_metrics(self) -> Dict[str, Any]:
        """Fetch performance metrics."""
        try:
            # Try to get performance metrics
            response = self._client.get(f"{self.mesh_bus_url}/performance", timeout=5)
            if response.status_code == 200:
                metrics = response.json()
                self._cache["performance_metrics"] = metrics
                return metrics
            
        except Exception as e:
            logger.error(f"Failed to fetch performance metrics: {e}")
        
        # Return cached data if available
        return self._cache.get("performance_metrics", {})
    
    async def fetch_mesh_agents(self) -> List[Dict[str, Any]]:
        """Fetch mesh agents."""
        try:
            # Get agents from broker
            response = self._client.get(f"{self.broker_url}/agents", timeout=5)
            if response.status_code == 200:
                agents_data = response.json()
                agents = agents_data.get("agents", {})
                
                # Convert to list
                agent_list = []
                for agent_id, agent_info in agents.items():
                    agent_list.append({
                        "agent_id": agent_id,
                        "status": agent_info.get("status", "unknown"),
                        "endpoint": agent_info.get("endpoint", ""),
                        "capabilities": agent_info.get("capabilities", []),
                        "last_seen": agent_info.get("last_seen", ""),
                    })
                
                return agent_list
            
        except Exception as e:
            logger.error(f"Failed to fetch mesh agents: {e}")
        
        return []
    
    def _update_loop(self):
        """Background update loop."""
        logger.info("Starting mesh dashboard update loop")
        
        while self._running:
            try:
                # Update all data
                asyncio.run(self._update_all_data())
                
                # Broadcast to WebSocket clients
                asyncio.run(self._broadcast_update())
                
                # Update cache timestamp
                self._cache["last_update"] = time.time()
                
            except Exception as e:
                logger.error(f"Update loop error: {e}")
            
            # Wait for next update
            time.sleep(self.update_interval)
    
    async def _update_all_data(self):
        """Update all dashboard data."""
        try:
            # Fetch all data in parallel
            tasks = [
                self.fetch_mesh_stats(),
                self.fetch_topology(),
                self.fetch_recent_messages(50),
                self.fetch_security_events(100),
                self.fetch_performance_metrics(),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Update cache with successful results
            for i, result in enumerate(results):
                if not isinstance(result, Exception):
                    keys = ["mesh_stats", "topology", "message_flow", "security_events", "performance_metrics"]
                    if i < len(keys):
                        self._cache[keys[i]] = result
            
        except Exception as e:
            logger.error(f"Failed to update all data: {e}")
    
    def run(self):
        """Run the dashboard server."""
        import uvicorn
        
        logger.info(f"Starting Enhanced Mesh Dashboard on port {self.dashboard_port}")
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=self.dashboard_port,
            log_level="info",
        )
    
    def stop(self):
        """Stop the dashboard."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5)
        
        self._client.close()
        logger.info("Enhanced Mesh Dashboard stopped")


def run_enhanced_mesh_dashboard(
    broker_url: str = "http://localhost:5555",
    mesh_bus_url: str = "http://localhost:8765",
    dashboard_port: int = 8060,
):
    """
    Run enhanced mesh dashboard.
    
    Args:
        broker_url: SIMP broker URL
        mesh_bus_url: Mesh bus HTTP endpoint
        dashboard_port: Dashboard port
    """
    dashboard = EnhancedMeshDashboard(
        broker_url=broker_url,
        mesh_bus_url=mesh_bus_url,
        dashboard_port=dashboard_port,
    )
    
    try:
        dashboard.run()
    except KeyboardInterrupt:
        dashboard.stop()
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        dashboard.stop()


if __name__ == "__main__":
    run_enhanced_mesh_dashboard()