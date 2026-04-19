"""
Tests for SIMP Mesh Client.
"""

import json
import time
from unittest.mock import Mock, patch, MagicMock
import pytest

from simp.mesh.client import MeshClient, create_mesh_client
from simp.mesh.packet import MeshPacket, MessageType, Priority


class MockResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
    
    def json(self):
        return self._json_data


class TestMeshClientBasics:
    """Test basic MeshClient functionality."""
    
    def test_client_initialization(self):
        """Test MeshClient initialization."""
        # Test with httpx available
        with patch.dict('sys.modules', {'httpx': MagicMock()}):
            from simp.mesh.client import MeshClient
            client = MeshClient(agent_id="test_agent", broker_url="http://test:5555")
            
            assert client.agent_id == "test_agent"
            assert client.broker_url == "http://test:5555"
            assert client.api_key is None
            assert client._http is not None
    
    def test_create_mesh_client(self):
        """Test create_mesh_client helper function."""
        client = create_mesh_client(
            agent_id="test_agent",
            broker_url="http://test:5555",
            api_key="test_key"
        )
        
        assert isinstance(client, MeshClient)
        assert client.agent_id == "test_agent"
        assert client.broker_url == "http://test:5555"
        assert client.api_key == "test_key"


class TestMeshClientSend:
    """Test message sending functionality."""
    
    def test_send_basic(self):
        """Test basic send operation."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "message_id": "test-message-id"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="sender",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        # Send message
        message_id = client.send(
            recipient_id="receiver",
            payload={"test": "data"}
        )
        
        assert message_id == "test-message-id"
        
        # Verify HTTP call
        mock_http.post.assert_called_once()
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test:5555/mesh/send"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        
        # Verify request data
        request_data = kwargs["json"]
        assert request_data["sender_id"] == "sender"
        assert request_data["recipient_id"] == "receiver"
        assert request_data["payload"] == {"test": "data"}
    
    def test_send_to_agent(self):
        """Test send_to_agent convenience method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "message_id": "test-id"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="sender",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        message_id = client.send_to_agent(
            recipient_id="receiver",
            payload={"action": "test"}
        )
        
        assert message_id == "test-id"
        
        # Verify request
        request_data = mock_http.post.call_args[1]["json"]
        assert request_data["recipient_id"] == "receiver"
        assert request_data["payload"] == {"action": "test"}
    
    def test_broadcast_to_channel(self):
        """Test broadcast_to_channel convenience method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "message_id": "test-id"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="sender",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        message_id = client.broadcast_to_channel(
            channel="announcements",
            payload={"announcement": "test"}
        )
        
        assert message_id == "test-id"
        
        # Verify request
        request_data = mock_http.post.call_args[1]["json"]
        assert request_data["channel"] == "announcements"
        assert request_data["recipient_id"] == "*"  # Wildcard for broadcast
        assert request_data["payload"] == {"announcement": "test"}
    
    def test_send_event(self):
        """Test send_event convenience method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "message_id": "test-id"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="sender",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        message_id = client.send_event(
            recipient_id="receiver",
            payload={"event": "test"}
        )
        
        assert message_id == "test-id"
        
        # Verify request
        request_data = mock_http.post.call_args[1]["json"]
        assert request_data["msg_type"] == "event"
        assert request_data["payload"] == {"event": "test"}
    
    def test_send_system_alert(self):
        """Test send_system_alert method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "message_id": "alert-id"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="monitor",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        message_id = client.send_system_alert(
            recipient_id="*",
            alert_type="security",
            severity="high",
            message="Security breach detected",
            details={"source": "intrusion_detection"}
        )
        
        assert message_id == "alert-id"
        
        # Verify request
        request_data = mock_http.post.call_args[1]["json"]
        assert request_data["msg_type"] == "system"
        assert request_data["channel"] == "system_alerts"
        assert request_data["priority"] == "high"
        assert request_data["ttl_seconds"] == 300
        
        payload = request_data["payload"]
        assert payload["alert_type"] == "security"
        assert payload["severity"] == "high"
        assert payload["message"] == "Security breach detected"
        assert payload["details"] == {"source": "intrusion_detection"}
    
    def test_send_heartbeat(self):
        """Test send_heartbeat method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "message_id": "heartbeat-id"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        message_id = client.send_heartbeat()
        
        assert message_id == "heartbeat-id"
        
        # Verify request
        request_data = mock_http.post.call_args[1]["json"]
        assert request_data["msg_type"] == "heartbeat"
        assert request_data["channel"] == "heartbeats"
        assert request_data["recipient_id"] == "*"
        assert request_data["priority"] == "low"
        assert request_data["ttl_seconds"] == 60
        
        payload = request_data["payload"]
        assert payload["agent_id"] == "agent_a"
        assert "timestamp" in payload
        assert payload["status"] == "alive"
    
    def test_send_error_handling(self):
        """Test error handling in send operations."""
        mock_http = Mock()
        mock_response = MockResponse(400, {
            "status": "error",
            "error": "Invalid packet"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="sender",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        # Should raise exception
        with pytest.raises(Exception, match="HTTP error 400"):
            client.send(recipient_id="receiver", payload={"test": "data"})
    
    def test_send_missing_recipient_and_channel(self):
        """Test send with neither recipient nor channel."""
        client = MeshClient(
            agent_id="sender",
            broker_url="http://test:5555",
            http_client=Mock()
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Either recipient_id or channel must be provided"):
            client.send(payload={"test": "data"})


class TestMeshClientReceive:
    """Test message receiving functionality."""
    
    def test_poll_messages(self):
        """Test poll method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "agent_id": "receiver",
            "messages": [
                {
                    "message_id": "msg1",
                    "sender_id": "sender1",
                    "recipient_id": "receiver",
                    "payload": {"test": "data1"}
                },
                {
                    "message_id": "msg2",
                    "sender_id": "sender2",
                    "recipient_id": "receiver",
                    "payload": {"test": "data2"}
                }
            ],
            "count": 2
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="receiver",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        messages = client.poll(max_messages=10)
        
        assert len(messages) == 2
        assert isinstance(messages[0], MeshPacket)
        assert messages[0].message_id == "msg1"
        assert messages[0].sender_id == "sender1"
        assert messages[0].payload == {"test": "data1"}
        
        assert messages[1].message_id == "msg2"
        assert messages[1].sender_id == "sender2"
        assert messages[1].payload == {"test": "data2"}
        
        # Verify HTTP call
        mock_http.get.assert_called_once()
        args, kwargs = mock_http.get.call_args
        assert args[0] == "http://test:5555/mesh/poll"
        assert kwargs["params"]["agent_id"] == "receiver"
        assert kwargs["params"]["max_messages"] == 10
    
    def test_poll_no_messages(self):
        """Test poll with no messages."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "agent_id": "receiver",
            "messages": [],
            "count": 0
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="receiver",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        messages = client.poll(max_messages=10)
        
        assert len(messages) == 0
    
    def test_poll_error(self):
        """Test poll with error response."""
        mock_http = Mock()
        mock_response = MockResponse(500, {
            "status": "error",
            "error": "Internal server error"
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="receiver",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        with pytest.raises(Exception, match="HTTP error 500"):
            client.poll(max_messages=10)
    
    def test_receive_one_with_timeout(self):
        """Test receive_one with timeout."""
        mock_http = Mock()
        
        # First call returns no messages
        mock_response1 = MockResponse(200, {
            "status": "success",
            "agent_id": "receiver",
            "messages": [],
            "count": 0
        })
        
        # Second call returns a message
        mock_response2 = MockResponse(200, {
            "status": "success",
            "agent_id": "receiver",
            "messages": [{
                "message_id": "msg1",
                "sender_id": "sender",
                "recipient_id": "receiver",
                "payload": {"test": "data"}
            }],
            "count": 1
        })
        
        mock_http.get.side_effect = [mock_response1, mock_response2]
        
        client = MeshClient(
            agent_id="receiver",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        # Mock time to control timeout
        with patch('time.time', side_effect=[0, 0.05, 0.1, 0.15]):
            with patch('time.sleep'):
                message = client.receive_one(timeout=0.2)
        
        assert message is not None
        assert isinstance(message, MeshPacket)
        assert message.message_id == "msg1"
        
        # Should have called poll twice
        assert mock_http.get.call_count == 2
    
    def test_receive_one_timeout_expired(self):
        """Test receive_one with expired timeout."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "agent_id": "receiver",
            "messages": [],
            "count": 0
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="receiver",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        # Mock time to simulate timeout
        with patch('time.time', side_effect=[0, 0.3]):  # Timeout is 0.2
            with patch('time.sleep'):
                message = client.receive_one(timeout=0.2)
        
        assert message is None
        
        # Should have called poll at least once
        assert mock_http.get.call_count >= 1


class TestMeshClientChannelManagement:
    """Test channel management functionality."""
    
    def test_subscribe(self):
        """Test subscribe method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "agent_id": "agent_a",
            "channel": "test_channel",
            "message": "Subscribed to channel test_channel"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        result = client.subscribe("test_channel")
        
        assert result is True
        
        # Verify HTTP call
        mock_http.post.assert_called_once()
        request_data = mock_http.post.call_args[1]["json"]
        assert request_data["agent_id"] == "agent_a"
        assert request_data["channel"] == "test_channel"
    
    def test_subscribe_error(self):
        """Test subscribe with error."""
        mock_http = Mock()
        mock_response = MockResponse(400, {
            "status": "error",
            "error": "Agent not found"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        with pytest.raises(Exception, match="HTTP error 400"):
            client.subscribe("test_channel")
    
    def test_unsubscribe(self):
        """Test unsubscribe method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "agent_id": "agent_a",
            "channel": "test_channel",
            "message": "Unsubscribed from channel test_channel"
        })
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        result = client.unsubscribe("test_channel")
        
        assert result is True
        
        # Verify HTTP call
        mock_http.post.assert_called_once()
        request_data = mock_http.post.call_args[1]["json"]
        assert request_data["agent_id"] == "agent_a"
        assert request_data["channel"] == "test_channel"
    
    def test_list_channels(self):
        """Test list_channels method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "channels": {
                "channel_1": 5,
                "channel_2": 3,
                "channel_3": 1
            },
            "count": 3
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        channels = client.list_channels()
        
        assert channels == {
            "channel_1": 5,
            "channel_2": 3,
            "channel_3": 1
        }
        
        # Verify HTTP call
        mock_http.get.assert_called_once()
        args, kwargs = mock_http.get.call_args
        assert args[0] == "http://test:5555/mesh/channels"


class TestMeshClientStatistics:
    """Test statistics and monitoring functionality."""
    
    def test_get_stats(self):
        """Test get_stats method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "statistics": {
                "registered_agents": 10,
                "total_queued_messages": 25,
                "total_pending_offline": 5,
                "channels": {
                    "test_channel": 3
                }
            }
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        stats = client.get_stats()
        
        assert stats["registered_agents"] == 10
        assert stats["total_queued_messages"] == 25
        assert stats["total_pending_offline"] == 5
        assert stats["channels"]["test_channel"] == 3
    
    def test_get_agent_status(self):
        """Test get_agent_status method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "agent_id": "agent_a",
            "mesh_status": {
                "registered": True,
                "queue_size": 3,
                "pending_offline": 1,
                "subscribed_channels": ["channel_1", "channel_2"]
            }
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        status = client.get_agent_status()
        
        assert status["registered"] is True
        assert status["queue_size"] == 3
        assert status["pending_offline"] == 1
        assert status["subscribed_channels"] == ["channel_1", "channel_2"]
    
    def test_get_events(self):
        """Test get_events method."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "events": [
                {"event_id": "1", "event_type": "MESSAGE_SENT"},
                {"event_id": "2", "event_type": "MESSAGE_DELIVERED"}
            ],
            "count": 2
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        events = client.get_events(limit=50)
        
        assert len(events) == 2
        assert events[0]["event_id"] == "1"
        assert events[1]["event_id"] == "2"
        
        # Verify HTTP call
        mock_http.get.assert_called_once()
        args, kwargs = mock_http.get.call_args
        assert args[0] == "http://test:5555/mesh/events"
        assert kwargs["params"]["limit"] == 50


class TestMeshClientUtilityMethods:
    """Test utility methods."""
    
    def test_ping_success(self):
        """Test ping method with success."""
        mock_http = Mock()
        mock_response = MockResponse(200, {
            "status": "success",
            "statistics": {}
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        assert client.ping() is True
    
    def test_ping_failure(self):
        """Test ping method with failure."""
        mock_http = Mock()
        mock_response = MockResponse(500, {
            "status": "error",
            "error": "Internal error"
        })
        mock_http.get.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        assert client.ping() is False
    
    def test_close(self):
        """Test close method."""
        mock_http = Mock()
        mock_http.close = Mock()
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        client.close()
        
        mock_http.close.assert_called_once()


class TestMeshClientEdgeCases:
    """Test edge cases and error handling."""
    
    def test_make_request_http_error(self):
        """Test _make_request with HTTP error."""
        mock_http = Mock()
        mock_response = MockResponse(404, text="Not Found")
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        with pytest.raises(Exception, match="HTTP error 404"):
            client._make_request("POST", "/test")
    
    def test_make_request_exception(self):
        """Test _make_request with exception."""
        mock_http = Mock()
        mock_http.post.side_effect = Exception("Network error")
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            http_client=mock_http
        )
        
        with pytest.raises(Exception, match="Network error"):
            client._make_request("POST", "/test")
    
    def test_api_key_in_headers(self):
        """Test that API key is included in headers when provided."""
        mock_http = Mock()
        mock_response = MockResponse(200, {"status": "success"})
        mock_http.post.return_value = mock_response
        
        client = MeshClient(
            agent_id="agent_a",
            broker_url="http://test:5555",
            api_key="test-api-key",
            http_client=mock_http
        )
        
        client._make_request("POST", "/test")
        
        # Verify API key in headers
        headers = mock_http.post.call_args[1]["headers"]
        assert headers["X-API-Key"] == "test-api-key"
    
    def test_urllib_fallback(self):
        """Test urllib fallback when httpx and requests are not available."""
        # Mock missing httpx and requests
        with patch.dict('sys.modules', {'httpx': None, 'requests': None}):
            # Re-import to trigger fallback
            import importlib
            import simp.mesh.client
            importlib.reload(simp.mesh.client)
            
            from simp.mesh.client import MeshClient
            
            # Mock urllib
            with patch('urllib.request.urlopen') as mock_urlopen:
                mock_response = Mock()
                mock_response.read.return_value = b'{"status": "success"}'
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                client = MeshClient(agent_id="test_agent")
                
                # Should use urllib fallback
                result = client._make_request("POST", "/test", {"test": "data"})
                assert result == {"status": "success"}
    
    def test_urllib_http_error(self):
        """Test urllib fallback with HTTP error."""
        # Mock missing httpx and requests
        with patch.dict('sys.modules', {'httpx': None, 'requests': None}):
            # Re-import to trigger fallback
            import importlib
            import simp.mesh.client
            importlib.reload(simp.mesh.client)
            
            from simp.mesh.client import MeshClient
            
            # Mock urllib HTTPError
            with patch('urllib.request.urlopen') as mock_urlopen:
                from urllib.error import HTTPError
                mock_error = HTTPError(
                    url="http://test:5555/test",
                    code=500,
                    msg="Internal Error",
                    hdrs={},
                    fp=None
                )
                mock_error.read.return_value = b'{"error": "internal"}'
                mock_urlopen.side_effect = mock_error
                
                client = MeshClient(agent_id="test_agent")
                
                with pytest.raises(Exception, match="HTTP error 500"):
                    client._make_request("POST", "/test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])