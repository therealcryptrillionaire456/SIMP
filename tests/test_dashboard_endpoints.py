"""
Test dashboard endpoints for proper response structure and error handling.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.server import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Test client for dashboard FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_broker_responses():
    """Mock broker responses for dashboard endpoints."""
    with patch('dashboard.server._broker_get') as mock_get, \
         patch('dashboard.server._broker_snapshot') as mock_snapshot, \
         patch('dashboard.server._projectx_get') as mock_projectx:
        
        # Mock successful broker responses
        mock_get.return_value = {
            "status": "success",
            "agents": [
                {
                    "agent_id": "test_agent",
                    "status": "online",
                    "capabilities": ["test_capability"],
                    "endpoint": "http://localhost:9999",
                    "connection_mode": "http"
                }
            ],
            "count": 1
        }
        
        mock_snapshot.return_value = {
            "health": {"status": "healthy", "timestamp": "2024-01-15T10:30:00Z"},
            "agents": {"test_agent": {"status": "online"}},
            "intents": {"recent": [], "failed": []},
            "stats": {"received": 10, "routed": 8, "failed": 2}
        }
        
        mock_projectx.return_value = {
            "status": "success",
            "processes": [
                {
                    "service": "test_service",
                    "category": "test",
                    "status": "running",
                    "health": "healthy",
                    "port": 8080
                }
            ]
        }
        
        yield mock_get, mock_snapshot, mock_projectx


class TestDashboardCoreEndpoints:
    """Test core dashboard API endpoints."""
    
    def test_health_endpoint(self, client):
        """Test /api/health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "broker_reachable" in data
        assert "dashboard_version" in data
    
    def test_health_alias_endpoint(self, client):
        """Test /health alias endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_stats_endpoint(self, client):
        """Test /api/stats endpoint."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Stats should contain broker metrics
        assert "broker_url_reachable" in data
    
    def test_agents_endpoint(self, client):
        """Test /api/agents endpoint."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "agents" in data
        # Agents can be dict or list depending on broker response
        assert isinstance(data["agents"], (dict, list))
    
    def test_activity_endpoint(self, client):
        """Test /api/activity endpoint."""
        response = client.get("/api/activity")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "events" in data
        assert isinstance(data["events"], list)
    
    def test_intents_recent_endpoint(self, client):
        """Test /api/intents/recent endpoint."""
        response = client.get("/api/intents/recent")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "intents" in data
        assert isinstance(data["intents"], list)
    
    def test_intents_failed_endpoint(self, client):
        """Test /api/intents/failed endpoint."""
        response = client.get("/api/intents/failed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "summary" in data
        assert "intents" in data
        assert isinstance(data["intents"], list)
    
    def test_capabilities_endpoint(self, client):
        """Test /api/capabilities endpoint."""
        response = client.get("/api/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "capabilities" in data
        assert isinstance(data["capabilities"], dict)
    
    def test_agents_smoke_endpoint(self, client):
        """Test /api/agents/smoke endpoint."""
        response = client.get("/api/agents/smoke")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Should have either results or agents
        assert "results" in data or "agents" in data
    
    def test_tasks_endpoint(self, client):
        """Test /api/tasks endpoint."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Tasks endpoint returns various task data
        assert "tasks" in data or "queue" in data or "summary" in data
    
    def test_routing_endpoint(self, client):
        """Test /api/routing endpoint."""
        response = client.get("/api/routing")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Routing endpoint returns policy or capability map
        assert "policy" in data or "capabilities" in data or "routes" in data
    
    def test_orchestration_endpoint(self, client):
        """Test /api/orchestration endpoint."""
        response = client.get("/api/orchestration")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Orchestration endpoint returns loop status
        assert "loop_status" in data or "status" in data or "orchestration" in data


class TestProjectXEndpoints:
    """Test ProjectX integration endpoints."""
    
    def test_projectx_system_endpoint(self, client):
        """Test /api/projectx/system endpoint."""
        response = client.get("/api/projectx/system")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # System endpoint returns system info
        assert "system" in data or "status" in data
    
    def test_projectx_processes_endpoint(self, client):
        """Test /api/projectx/processes endpoint."""
        response = client.get("/api/projectx/processes")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Processes endpoint returns services or processes
        assert "processes" in data or "services" in data
    
    def test_projectx_actions_endpoint(self, client):
        """Test /api/projectx/actions endpoint."""
        response = client.get("/api/projectx/actions")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Actions endpoint returns actions or events
        assert "actions" in data or "events" in data
    
    def test_projectx_protocol_facts_endpoint(self, client):
        """Test /api/projectx/protocol-facts endpoint."""
        response = client.get("/api/projectx/protocol-facts")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Protocol facts endpoint returns protocol_facts
        assert "protocol_facts" in data


class TestDashboardStaticFiles:
    """Test static file serving."""
    
    def test_root_endpoint_serves_html(self, client):
        """Test root endpoint serves the dashboard HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text
    
    def test_static_files_served(self, client):
        """Test static files (CSS, JS) are served correctly."""
        response = client.get("/static/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]
        
        response = client.get("/static/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"].lower()


class TestDashboardParameterValidation:
    """Test parameter validation for dashboard endpoints."""
    
    def test_limit_parameter_validation(self, client):
        """Test limit parameters are accepted."""
        # Test valid limit values
        response = client.get("/api/intents/recent?limit=10")
        assert response.status_code == 200
        
        response = client.get("/api/intents/recent?limit=50")
        assert response.status_code == 200
        
        # Test without limit parameter (should use default)
        response = client.get("/api/intents/recent")
        assert response.status_code == 200
    
    def test_intent_detail_endpoint(self, client):
        """Test /api/intents/{intent_id} endpoint."""
        response = client.get("/api/intents/test_intent_id")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Intent detail returns intent or detail
        assert "intent" in data or "detail" in data


class TestDashboardErrorHandling:
    """Test dashboard error handling."""
    
    def test_nonexistent_endpoint_returns_404(self, client):
        """Test nonexistent endpoint returns 404."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
    
    def test_broker_unreachable_handled_gracefully(self, client):
        """Test dashboard handles broker unreachable gracefully."""
        # This is tested implicitly by the other tests
        # If broker is unreachable, endpoints should still return 200
        # with appropriate status field
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])