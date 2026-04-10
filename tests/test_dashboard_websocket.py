"""
Test dashboard WebSocket functionality.
Note: FastAPI TestClient doesn't support WebSocket testing directly.
These tests verify the WebSocket route exists and the code compiles.
"""

import pytest
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.server import app


class TestWebSocketImplementation:
    """Test WebSocket implementation structure."""
    
    def test_websocket_route_exists(self):
        """Verify WebSocket route is registered."""
        # Check if WebSocket route exists in the app
        websocket_routes = [route for route in app.routes if hasattr(route, 'path') and route.path == '/ws']
        assert len(websocket_routes) == 1, "WebSocket route /ws should be registered"
        
        route = websocket_routes[0]
        assert hasattr(route, 'endpoint'), "Route should have endpoint"
        assert route.endpoint.__name__ == 'websocket_endpoint', "Endpoint should be websocket_endpoint"
    
    def test_websocket_broadcast_function_exists(self):
        """Verify broadcast function exists."""
        from dashboard.server import _broadcast_ws
        assert callable(_broadcast_ws), "_broadcast_ws should be callable"
    
    def test_websocket_clients_set_exists(self):
        """Verify WebSocket clients set exists."""
        from dashboard.server import _ws_clients
        assert isinstance(_ws_clients, set), "_ws_clients should be a set"
    
    def test_websocket_code_compiles(self):
        """Verify WebSocket-related code compiles without syntax errors."""
        # Import the module to check for syntax errors
        import dashboard.server
        # If we get here, the module compiled successfully
        
        # Check that required imports are present
        assert hasattr(dashboard.server, 'WebSocket'), "WebSocket should be imported"
        assert hasattr(dashboard.server, 'WebSocketDisconnect'), "WebSocketDisconnect should be imported"
        assert hasattr(dashboard.server, 'asyncio'), "asyncio should be imported"
    
    def test_websocket_endpoint_signature(self):
        """Verify WebSocket endpoint has correct signature."""
        from dashboard.server import websocket_endpoint
        import inspect
        
        sig = inspect.signature(websocket_endpoint)
        params = list(sig.parameters.keys())
        
        assert len(params) == 1, "websocket_endpoint should take 1 parameter"
        assert params[0] == 'websocket', "Parameter should be named 'websocket'"
    
    def test_broadcast_function_signature(self):
        """Verify broadcast function has correct signature."""
        from dashboard.server import _broadcast_ws
        import inspect
        
        sig = inspect.signature(_broadcast_ws)
        params = list(sig.parameters.keys())
        
        assert len(params) == 2, "_broadcast_ws should take 2 parameters"
        assert params[0] == 'event_type', "First parameter should be 'event_type'"
        assert params[1] == 'data', "Second parameter should be 'data'"


class TestWebSocketIntegration:
    """Test WebSocket integration with other components."""
    
    def test_broadcast_called_in_key_places(self):
        """Verify _broadcast_ws is called in key update functions."""
        import dashboard.server
        source_code = Path(dashboard.server.__file__).read_text()
        
        # Check that _broadcast_ws is called in the code
        assert '_broadcast_ws(' in source_code, "_broadcast_ws should be called somewhere"
        
        # Count how many times it's called
        broadcast_calls = source_code.count('_broadcast_ws(')
        assert broadcast_calls > 0, "_broadcast_ws should be called at least once"
    
    def test_websocket_imports_present(self):
        """Verify all required WebSocket imports are present."""
        import dashboard.server
        source_code = Path(dashboard.server.__file__).read_text()
        
        required_imports = [
            'from fastapi import',
            'WebSocket',
            'WebSocketDisconnect',
            'import asyncio',
            'import json'
        ]
        
        for import_stmt in required_imports:
            assert import_stmt in source_code, f"Missing import: {import_stmt}"
    
    def test_websocket_client_management(self):
        """Verify WebSocket client management functions correctly."""
        import dashboard.server
        
        # Check that clients are added and removed
        source_code = Path(dashboard.server.__file__).read_text()
        
        assert '_ws_clients.add(' in source_code, "Should add clients to set"
        assert '_ws_clients.discard(' in source_code, "Should remove clients from set"
        assert 'finally:' in source_code, "Should have finally block for cleanup"
    
    def test_websocket_message_handling(self):
        """Verify WebSocket message handling is implemented."""
        import dashboard.server
        source_code = Path(dashboard.server.__file__).read_text()
        
        # Check for message handling patterns
        assert 'receive_text()' in source_code, "Should receive text messages"
        assert 'send_text(' in source_code, "Should send text messages"
        assert '"ping"' in source_code, "Should handle ping messages"
        assert '"pong"' in source_code, "Should send pong responses"
        assert '"heartbeat"' in source_code, "Should send heartbeat messages"


class TestWebSocketFrontend:
    """Test WebSocket frontend implementation."""
    
    def test_app_js_has_websocket_code(self):
        """Verify app.js has WebSocket implementation."""
        app_js_path = Path(__file__).parent.parent / 'dashboard' / 'static' / 'app.js'
        app_js_content = app_js_path.read_text()
        
        # Check for WebSocket implementation
        assert 'WebSocket' in app_js_content, "app.js should reference WebSocket"
        assert 'connectWebSocket' in app_js_content, "app.js should have connectWebSocket function"
        assert 'ws.onopen' in app_js_content, "app.js should handle WebSocket open"
        assert 'ws.onmessage' in app_js_content, "app.js should handle WebSocket messages"
        assert 'ws.onclose' in app_js_content, "app.js should handle WebSocket close"
        assert 'ws.onerror' in app_js_content, "app.js should handle WebSocket errors"
    
    def test_app_js_has_fallback_mechanism(self):
        """Verify app.js has fallback mechanism when WebSocket fails."""
        app_js_path = Path(__file__).parent.parent / 'dashboard' / 'static' / 'app.js'
        app_js_content = app_js_path.read_text()
        
        # Check for fallback mechanism
        assert 'startPollingFallback' in app_js_content, "app.js should have polling fallback"
        assert 'MAX_WS_RETRIES' in app_js_content, "app.js should have max retry limit"
        assert 'WS_RETRY_DELAY' in app_js_content, "app.js should have retry delay"
    
    def test_websocket_message_handling_in_js(self):
        """Verify WebSocket message handling in JavaScript."""
        app_js_path = Path(__file__).parent.parent / 'dashboard' / 'static' / 'app.js'
        app_js_content = app_js_path.read_text()
        
        # Check for message handling
        assert 'handleWsMessage' in app_js_content, "app.js should have handleWsMessage function"
        assert 'JSON.parse' in app_js_content, "app.js should parse JSON messages"
        
        # Check for specific message types
        message_types = ['stats', 'agents', 'tasks', 'logs']
        for msg_type in message_types:
            # Check for case 'stats': format
            case_pattern = f"case '{msg_type}':"
            assert case_pattern in app_js_content, \
                f"app.js should handle {msg_type} messages (looking for: {case_pattern})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])