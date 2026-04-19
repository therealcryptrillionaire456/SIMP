#!/usr/bin/env python3
"""
Mesh Dashboard Extension

Adds mesh bus visualization to the SIMP dashboard.
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger("MeshDashboard")


class MeshDashboard:
    """Dashboard extension for mesh bus visualization"""
    
    def __init__(self, broker_url: str = "http://localhost:5555"):
        self.broker_url = broker_url
        self.mesh_stats = {}
        self.channel_data = {}
        self.agent_status = {}
        self.last_update = None
        
    def fetch_mesh_stats(self) -> Dict[str, Any]:
        """Fetch mesh statistics from broker"""
        try:
            import requests
            
            response = requests.get(f"{self.broker_url}/mesh/stats", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.mesh_stats = data.get("statistics", {})
                    self.last_update = datetime.now(timezone.utc).isoformat()
                    return self.mesh_stats
            else:
                logger.error(f"Failed to fetch mesh stats: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching mesh stats: {e}")
        
        return {}
    
    def fetch_channel_data(self) -> Dict[str, Any]:
        """Fetch channel data from broker"""
        try:
            import requests
            
            response = requests.get(f"{self.broker_url}/mesh/channels", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.channel_data = data.get("channels", {})
                    return self.channel_data
            else:
                logger.error(f"Failed to fetch channel data: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching channel data: {e}")
        
        return {}
    
    def fetch_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Fetch agent mesh status"""
        try:
            import requests
            
            response = requests.get(f"{self.broker_url}/mesh/agent/{agent_id}/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.agent_status[agent_id] = data.get("agent_status", {})
                    return self.agent_status[agent_id]
            else:
                logger.error(f"Failed to fetch agent status for {agent_id}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching agent status for {agent_id}: {e}")
        
        return {}
    
    def fetch_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent mesh events"""
        try:
            import requests
            
            response = requests.get(f"{self.broker_url}/mesh/events?limit={limit}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return data.get("events", [])
            else:
                logger.error(f"Failed to fetch recent events: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching recent events: {e}")
        
        return []
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all dashboard data for mesh visualization"""
        # Fetch latest data
        stats = self.fetch_mesh_stats()
        channels = self.fetch_channel_data()
        recent_events = self.fetch_recent_events(limit=20)
        
        # Process channel data for visualization
        channel_list = []
        for channel_name, subscriber_count in channels.items():
            channel_list.append({
                "name": channel_name,
                "subscribers": subscriber_count,
                "description": self._get_channel_description(channel_name)
            })
        
        # Process agent data
        agents = []
        for agent_id, queue_size in stats.get("agent_queue_sizes", {}).items():
            agent_status = self.fetch_agent_status(agent_id)
            agents.append({
                "id": agent_id,
                "queue_size": queue_size,
                "status": agent_status.get("status", "unknown"),
                "subscribed_channels": agent_status.get("subscribed_channels", []),
                "last_active": agent_status.get("last_active")
            })
        
        # Process recent events
        processed_events = []
        for event in recent_events:
            processed_events.append({
                "timestamp": event.get("timestamp"),
                "event_type": event.get("event_type"),
                "agent_id": event.get("agent_id"),
                "channel": event.get("channel"),
                "message_id": event.get("message_id"),
                "priority": event.get("priority")
            })
        
        return {
            "stats": {
                "total_agents": stats.get("registered_agents", 0),
                "total_channels": len(channels),
                "total_queued_messages": stats.get("total_queued_messages", 0),
                "total_pending_offline": stats.get("total_pending_offline", 0),
                "last_update": self.last_update
            },
            "channels": channel_list,
            "agents": agents,
            "recent_events": processed_events,
            "core_channels": self._get_core_channels_info()
        }
    
    def _get_channel_description(self, channel_name: str) -> str:
        """Get description for core channels"""
        descriptions = {
            "safety_alerts": "Critical safety and security notifications",
            "trade_updates": "Real-time trading activity updates",
            "system_heartbeats": "Agent health status and heartbeats",
            "maintenance_events": "System maintenance recommendations",
            "dashboard_alerts": "Dashboard notifications and alerts",
            "system": "System-level messages and commands"
        }
        
        return descriptions.get(channel_name, "User-defined channel")
    
    def _get_core_channels_info(self) -> List[Dict[str, Any]]:
        """Get information about core channels"""
        return [
            {
                "name": "safety_alerts",
                "purpose": "Critical safety and security notifications",
                "producers": ["BRP", "ProjectX", "Watchtower", "QuantumArb"],
                "consumers": ["ProjectX", "Dashboard", "Watchtower"],
                "auto_subscribe": True,
                "priority": "high"
            },
            {
                "name": "trade_updates",
                "purpose": "Real-time trading activity",
                "producers": ["QuantumArb", "Execution Engine", "Risk Monitor"],
                "consumers": ["Risk Monitor", "Dashboard", "P&L Ledger"],
                "auto_subscribe": False,
                "priority": "normal"
            },
            {
                "name": "system_heartbeats",
                "purpose": "Agent health status",
                "producers": ["All registered agents"],
                "consumers": ["ProjectX", "Dashboard", "Orchestration Manager"],
                "auto_subscribe": False,
                "priority": "low"
            },
            {
                "name": "maintenance_events",
                "purpose": "System maintenance recommendations",
                "producers": ["ProjectX", "Ops Scripts", "Security Audit"],
                "consumers": ["All agents", "Dashboard", "ProjectX"],
                "auto_subscribe": False,
                "priority": "normal"
            }
        ]
    
    def generate_html_widget(self) -> str:
        """Generate HTML widget for dashboard"""
        data = self.get_dashboard_data()
        
        html = f"""
        <div class="mesh-dashboard">
            <h3>🔄 SIMP Agent Mesh Bus</h3>
            
            <div class="mesh-stats">
                <div class="stat-card">
                    <h4>📊 Statistics</h4>
                    <p>Agents: {data['stats']['total_agents']}</p>
                    <p>Channels: {data['stats']['total_channels']}</p>
                    <p>Queued Messages: {data['stats']['total_queued_messages']}</p>
                    <p>Pending Offline: {data['stats']['total_pending_offline']}</p>
                    <p class="timestamp">Last update: {data['stats']['last_update'] or 'Never'}</p>
                </div>
                
                <div class="channels-card">
                    <h4>📡 Core Channels</h4>
                    <div class="channels-list">
        """
        
        for channel in data['core_channels']:
            html += f"""
                        <div class="channel-item">
                            <strong>{channel['name']}</strong>
                            <span class="channel-purpose">{channel['purpose']}</span>
                            <div class="channel-details">
                                <small>Producers: {', '.join(channel['producers'][:3])}</small>
                                <small>Priority: {channel['priority']}</small>
                                {'<span class="auto-subscribe">Auto-subscribe</span>' if channel['auto_subscribe'] else ''}
                            </div>
                        </div>
            """
        
        html += """
                    </div>
                </div>
            </div>
            
            <div class="active-channels">
                <h4>📶 Active Channels</h4>
                <div class="channels-grid">
        """
        
        for channel in data['channels']:
            html += f"""
                    <div class="channel-active">
                        <div class="channel-header">
                            <span class="channel-name">{channel['name']}</span>
                            <span class="subscriber-count">{channel['subscribers']} subscribers</span>
                        </div>
                        <p class="channel-desc">{channel['description']}</p>
                    </div>
            """
        
        html += """
                </div>
            </div>
            
            <div class="recent-events">
                <h4>📨 Recent Events</h4>
                <div class="events-list">
        """
        
        for event in data['recent_events'][:10]:  # Show last 10 events
            html += f"""
                    <div class="event-item">
                        <span class="event-time">{event['timestamp'] or 'Unknown'}</span>
                        <span class="event-type {event['priority'] or 'normal'}">{event['event_type'] or 'Unknown'}</span>
                        <span class="event-agent">{event['agent_id'] or 'Unknown'}</span>
                        <span class="event-channel">{event['channel'] or 'Unknown'}</span>
                    </div>
            """
        
        html += """
                </div>
            </div>
            
            <div class="mesh-actions">
                <h4>⚡ Quick Actions</h4>
                <div class="action-buttons">
                    <button onclick="refreshMeshStats()">🔄 Refresh</button>
                    <button onclick="sendTestAlert()">🚨 Test Alert</button>
                    <button onclick="viewMeshLogs()">📋 View Logs</button>
                    <button onclick="exportMeshData()">📤 Export Data</button>
                </div>
            </div>
        </div>
        
        <style>
        .mesh-dashboard {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            color: white;
            margin: 20px 0;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .mesh-dashboard h3 {
            margin-top: 0;
            color: white;
            font-size: 24px;
            text-align: center;
            margin-bottom: 25px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .mesh-dashboard h4 {
            color: #f0f0f0;
            margin-top: 0;
            border-bottom: 2px solid rgba(255,255,255,0.2);
            padding-bottom: 8px;
            margin-bottom: 15px;
        }
        
        .mesh-stats {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
            margin-bottom: 25px;
        }
        
        .stat-card, .channels-card {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .stat-card p {
            margin: 8px 0;
            font-size: 16px;
        }
        
        .timestamp {
            font-size: 12px !important;
            color: rgba(255,255,255,0.7);
            margin-top: 15px !important;
        }
        
        .channels-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .channel-item {
            background: rgba(255,255,255,0.05);
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }
        
        .channel-purpose {
            display: block;
            font-size: 14px;
            color: rgba(255,255,255,0.8);
            margin: 5px 0;
        }
        
        .channel-details {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: rgba(255,255,255,0.6);
        }
        
        .auto-subscribe {
            background: #4CAF50;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
        }
        
        .active-channels, .recent-events {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .channels-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
        }
        
        .channel-active {
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .channel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .channel-name {
            font-weight: bold;
            color: #FFD700;
        }
        
        .subscriber-count {
            background: rgba(76, 175, 80, 0.3);
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 12px;
        }
        
        .channel-desc {
            font-size: 14px;
            color: rgba(255,255,255,0.8);
            margin: 0;
        }
        
        .events-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .event-item {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 10px;
            padding: 10px;
            background: rgba(255,255,255,0.05);
            margin-bottom: 8px;
            border-radius: 6px;
            font-size: 14px;
            align-items: center;
        }
        
        .event-item:nth-child(even) {
            background: rgba(255,255,255,0.03);
        }
        
        .event-time {
            font-size: 12px;
            color: rgba(255,255,255,0.7);
        }
        
        .event-type {
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 12px;
            text-align: center;
        }
        
        .event-type.high {
            background: rgba(255, 87, 87, 0.3);
            color: #FF5757;
        }
        
        .event-type.normal {
            background: rgba(76, 175, 80, 0.3);
            color: #4CAF50;
        }
        
        .event-type.low {
            background: rgba(33, 150, 243, 0.3);
            color: #2196F3;
        }
        
        .event-agent {
            color: #FFD700;
        }
        
        .event-channel {
            color: #64B5F6;
        }
        
        .mesh-actions {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .action-buttons {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
        }
        
        .action-buttons button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s ease;
            border: 2px solid rgba(255,255,255,0.3);
        }
        
        .action-buttons button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.3);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255,255,255,0.5);
        }
        </style>
        
        <script>
        function refreshMeshStats() {
            fetch('/api/mesh/stats')
                .then(response => response.json())
                .then(data => {
                    alert('Mesh stats refreshed!');
                    location.reload();
                })
                .catch(error => {
                    console.error('Error refreshing mesh stats:', error);
                    alert('Failed to refresh mesh stats');
                });
        }
        
        function sendTestAlert() {
            fetch('/api/mesh/test-alert', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    channel: 'safety_alerts',
                    message: 'Test alert from dashboard'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Test alert sent successfully!');
                } else {
                    alert('Failed to send test alert: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error sending test alert:', error);
                alert('Failed to send test alert');
            });
        }
        
        function viewMeshLogs() {
            window.open('/api/mesh/events?limit=100', '_blank');
        }
        
        function exportMeshData() {
            fetch('/api/mesh/export')
                .then(response => response.json())
                .then(data => {
                    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'mesh_data_' + new Date().toISOString().split('T')[0] + '.json';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                })
                .catch(error => {
                    console.error('Error exporting mesh data:', error);
                    alert('Failed to export mesh data');
                });
        }
        
        // Auto-refresh every 30 seconds
        setInterval(() => {
            fetch('/api/mesh/stats')
                .then(response => response.json())
                .then(data => {
                    // Update stats dynamically without full page reload
                    console.log('Mesh stats auto-refreshed');
                })
                .catch(error => {
                    console.error('Error auto-refreshing mesh stats:', error);
                });
        }, 30000);
        </script>
        """
        
        return html


def test_mesh_dashboard():
    """Test mesh dashboard functionality"""
    print("Testing Mesh Dashboard...")
    
    dashboard = MeshDashboard()
    
    # Test fetching stats
    print("1. Fetching mesh stats...")
    stats = dashboard.fetch_mesh_stats()
    if stats:
        print(f"✅ Stats fetched: {stats}")
    else:
        print("⚠️  Could not fetch stats (broker may not be available)")
    
    # Test getting dashboard data
    print("\n2. Getting dashboard data...")
    data = dashboard.get_dashboard_data()
    print(f"✅ Dashboard data generated")
    print(f"   Agents: {data['stats']['total_agents']}")
    print(f"   Channels: {data['stats']['total_channels']}")
    print(f"   Core channels: {len(data['core_channels'])}")
    
    # Test HTML generation
    print("\n3. Generating HTML widget...")
    html = dashboard.generate_html_widget()
    print(f"✅ HTML widget generated ({len(html)} characters)")
    
    # Save HTML for inspection
    with open("/tmp/mesh_dashboard_widget.html", "w") as f:
        f.write(html)
    
    print(f"\n✅ Mesh dashboard test complete")
    print(f"   HTML saved to: /tmp/mesh_dashboard_widget.html")
    
    return True


if __name__ == "__main__":
    test_mesh_dashboard()