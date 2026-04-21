"""
SIMP Agent Mesh Bus - Client API

MeshClient: Simple client for agents to interact with the MeshBus via broker HTTP API.
Provides a clean interface for sending/receiving mesh messages and managing subscriptions.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .packet import (
    MeshPacket,
    MessageType,
    Priority,
    create_event_packet,
    create_system_packet,
    create_heartbeat_packet,
)


logger = logging.getLogger("SIMP.MeshClient")


class MeshClient:
    """
    Client for agent-to-agent mesh communication via broker HTTP API.
    
    This client provides a simple interface for agents to:
      - Send messages to specific agents or channels
      - Receive queued messages
      - Subscribe/unsubscribe from channels
      - Get mesh statistics and status
    
    Usage:
        client = MeshClient(agent_id="my_agent", broker_url="http://localhost:5555", api_key="my_key")
        client.send(recipient_id="other_agent", channel="trading", payload={"signal": "buy"})
        messages = client.poll()
    """
    
    def __init__(
        self,
        agent_id: str,
        broker_url: str = "http://127.0.0.1:5555",
        api_key: Optional[str] = None,
        http_client=None,
    ):
        """
        Initialize MeshClient.
        
        Args:
            agent_id: Unique agent identifier
            broker_url: Base URL of SIMP broker (default: http://127.0.0.1:5555)
            api_key: Optional API key for authentication
            http_client: Optional HTTP client instance (for testing or custom configuration)
        """
        self.agent_id = agent_id
        self.broker_url = broker_url.rstrip("/")
        self.api_key = api_key
        
        # Use provided HTTP client or create default
        if http_client is not None:
            self._http = http_client
            # Determine client type
            if hasattr(http_client, 'post') and hasattr(http_client, 'get'):
                # Looks like httpx or requests
                self._has_httpx = True
            else:
                self._has_httpx = False
        else:
            try:
                import httpx
                self._http = httpx.Client(timeout=30.0)
                self._has_httpx = True
            except ImportError:
                # Fallback to requests or urllib
                self._has_httpx = False
                try:
                    import requests
                    self._http = requests.Session()
                    self._http.timeout = 30.0
                except ImportError:
                    # Use urllib as last resort
                    import urllib.request
                    import urllib.error
                    self._http = None
                    logger.warning("Using urllib fallback for HTTP client")
        
        logger.info(f"MeshClient initialized for agent {agent_id} with broker {broker_url}")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        *,
        log_errors: bool = True,
    ) -> Dict:
        """
        Make HTTP request to broker.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            data: Optional request data
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            Exception: If request fails or returns error
        """
        url = f"{self.broker_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        
        try:
            if self._has_httpx and self._http is not None:
                # Using httpx
                if method.upper() == "GET":
                    response = self._http.get(url, headers=headers, params=data if data else {})
                else:
                    response = self._http.post(url, headers=headers, json=data)
            elif hasattr(self._http, 'request'):
                # Using requests
                if method.upper() == "GET":
                    response = self._http.get(url, headers=headers, params=data if data else {})
                else:
                    response = self._http.post(url, headers=headers, json=data)
            else:
                # Using urllib fallback
                import urllib.request
                import json as json_module
                
                req_data = None
                if data and method.upper() != "GET":
                    req_data = json_module.dumps(data).encode('utf-8')
                
                request = urllib.request.Request(
                    url,
                    data=req_data,
                    headers=headers,
                    method=method.upper()
                )
                
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        response_data = response.read().decode('utf-8')
                        return json_module.loads(response_data)
                except urllib.error.HTTPError as e:
                    error_data = e.read().decode('utf-8') if e.read() else str(e)
                    raise Exception(f"HTTP error {e.code}: {error_data}")
            
            # For httpx and requests
            if response.status_code >= 400:
                raise Exception(f"HTTP error {response.status_code}: {response.text}")
            
            return response.json()
            
        except Exception as e:
            if log_errors:
                logger.error(f"HTTP request failed: {e}")
            raise
    
    # ----------------------------------------------------------------------
    # Core Messaging Methods
    # ----------------------------------------------------------------------
    
    def send(
        self,
        recipient_id: str = "",
        channel: str = "",
        msg_type: str = MessageType.EVENT,
        payload: Dict[str, Any] = None,
        correlation_id: Optional[str] = None,
        priority: str = Priority.NORMAL,
        ttl_seconds: int = 3600,
        ttl_hops: int = 10,
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Send a mesh message.
        
        Args:
            recipient_id: Target agent ID, '*' for broadcast, or empty for channel-only
            channel: Channel name for pub/sub (required if no recipient_id)
            msg_type: Message type (event, command, reply, heartbeat, system)
            payload: Message content as dictionary
            correlation_id: Optional ID for linking replies to requests
            priority: Message priority (low, normal, high)
            ttl_seconds: Time-to-live in seconds
            ttl_hops: Maximum routing hops
            meta: Additional metadata
            
        Returns:
            Message ID of the sent packet
            
        Raises:
            ValueError: If neither recipient_id nor channel is provided
            Exception: If send fails
        """
        if not recipient_id and not channel:
            raise ValueError("Either recipient_id or channel must be provided")
        
        # Create mesh packet
        packet = MeshPacket(
            sender_id=self.agent_id,
            recipient_id=recipient_id or "*",  # Use wildcard if no recipient
            channel=channel,
            msg_type=msg_type,
            payload=payload or {},
            correlation_id=correlation_id,
            priority=priority,
            ttl_seconds=ttl_seconds,
            ttl_hops=ttl_hops,
            meta=meta or {},
        )
        
        # Send via broker API
        response = self._make_request(
            "POST",
            "/mesh/send",
            data=packet.to_dict()
        )
        
        if response.get("status") == "success":
            message_id = response.get("message_id", packet.message_id)
            logger.debug(f"Sent mesh message {message_id} to {recipient_id or channel}")
            return message_id
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Failed to send mesh message: {error}")
    
    def send_to_agent(
        self,
        recipient_id: str,
        payload: Dict[str, Any],
        msg_type: str = MessageType.EVENT,
        **kwargs
    ) -> str:
        """
        Send message directly to a specific agent.
        
        Args:
            recipient_id: Target agent ID
            payload: Message content
            msg_type: Message type
            **kwargs: Additional arguments passed to send()
            
        Returns:
            Message ID
        """
        return self.send(
            recipient_id=recipient_id,
            payload=payload,
            msg_type=msg_type,
            **kwargs
        )
    
    def broadcast_to_channel(
        self,
        channel: str,
        payload: Dict[str, Any],
        msg_type: str = MessageType.EVENT,
        **kwargs
    ) -> str:
        """
        Broadcast message to all subscribers of a channel.
        
        Args:
            channel: Channel name
            payload: Message content
            msg_type: Message type
            **kwargs: Additional arguments passed to send()
            
        Returns:
            Message ID
        """
        return self.send(
            channel=channel,
            payload=payload,
            msg_type=msg_type,
            **kwargs
        )
    
    def send_event(
        self,
        recipient_id: str = "",
        channel: str = "",
        payload: Dict[str, Any] = None,
        **kwargs
    ) -> str:
        """
        Send an event message (convenience method).
        
        Args:
            recipient_id: Target agent ID or empty for channel broadcast
            channel: Channel name
            payload: Event data
            **kwargs: Additional arguments passed to send()
            
        Returns:
            Message ID
        """
        return self.send(
            recipient_id=recipient_id,
            channel=channel,
            msg_type=MessageType.EVENT,
            payload=payload or {},
            **kwargs
        )
    
    def send_system_alert(
        self,
        recipient_id: str,
        alert_type: str,
        severity: str = "info",
        message: str = "",
        details: Optional[Dict] = None,
        **kwargs
    ) -> str:
        """
        Send a system alert message.
        
        Args:
            recipient_id: Target agent ID or '*' for all agents
            alert_type: Type of alert (e.g., "security", "performance", "error")
            severity: Alert severity (info, warning, error, critical)
            message: Human-readable alert message
            details: Additional alert details
            **kwargs: Additional arguments passed to send()
            
        Returns:
            Message ID
        """
        payload = {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "timestamp": time.time(),
            "details": details or {},
        }
        
        return self.send(
            recipient_id=recipient_id,
            channel="system_alerts",
            msg_type=MessageType.SYSTEM,
            payload=payload,
            priority=Priority.HIGH,
            ttl_seconds=300,  # Short TTL for system alerts
            **kwargs
        )
    
    def send_heartbeat(self) -> str:
        """
        Send a heartbeat message.
        
        Returns:
            Message ID
        """
        return self.send(
            recipient_id="*",  # Broadcast to all
            channel="heartbeats",
            msg_type=MessageType.HEARTBEAT,
            payload={
                "agent_id": self.agent_id,
                "timestamp": time.time(),
                "status": "alive",
            },
            priority=Priority.LOW,
            ttl_seconds=60,  # Short TTL for heartbeats
        )
    
    # ----------------------------------------------------------------------
    # Message Receiving
    # ----------------------------------------------------------------------
    
    def poll(self, max_messages: int = 10) -> List[MeshPacket]:
        """
        Poll for incoming mesh messages.
        
        Args:
            max_messages: Maximum number of messages to return
            
        Returns:
            List of MeshPacket objects (may be empty)
            
        Raises:
            Exception: If poll fails
        """
        response = self._make_request(
            "GET",
            "/mesh/poll",
            data={
                "agent_id": self.agent_id,
                "max_messages": max_messages,
            }
        )
        
        if response.get("status") == "success":
            messages_data = response.get("messages", [])
            messages = [MeshPacket.from_dict(msg) for msg in messages_data]
            logger.debug(f"Received {len(messages)} mesh messages")
            return messages
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Failed to poll mesh messages: {error}")
    
    def receive_one(self, timeout: Optional[float] = None) -> Optional[MeshPacket]:
        """
        Receive a single message, optionally with timeout.
        
        Args:
            timeout: Optional timeout in seconds (None for no timeout)
            
        Returns:
            MeshPacket or None if no messages
        """
        import time as time_module
        
        start_time = time_module.time()
        
        while True:
            messages = self.poll(max_messages=1)
            if messages:
                return messages[0]
            
            if timeout is not None and (time_module.time() - start_time) >= timeout:
                return None
            
            # Wait before polling again
            time_module.sleep(0.1)

    def _agent_registered(self) -> bool:
        try:
            response = self._make_request("GET", f"/agents/{self.agent_id}", log_errors=False)
        except Exception:
            return False

        agent = response.get("agent", response) if isinstance(response, dict) else {}
        return str(agent.get("agent_id") or "") == self.agent_id

    def _poll_ready(self) -> bool:
        try:
            response = self._make_request(
                "GET",
                "/mesh/poll",
                data={"agent_id": self.agent_id, "max_messages": 1},
                log_errors=False,
            )
        except Exception:
            return False

        return (
            isinstance(response, dict)
            and str(response.get("agent_id") or "") == self.agent_id
        )
    
    # ----------------------------------------------------------------------
    # Channel Management
    # ----------------------------------------------------------------------
    
    def subscribe(self, channel: str) -> bool:
        """
        Subscribe to a mesh channel.
        
        Args:
            channel: Channel name
            
        Returns:
            True if subscription successful
            
        Raises:
            Exception: If subscription fails
        """
        try:
            response = self._make_request(
                "POST",
                "/mesh/subscribe",
                data={
                    "agent_id": self.agent_id,
                    "channel": channel,
                },
                log_errors=False,
            )
        except Exception as exc:
            if self._agent_registered() or self._poll_ready():
                logger.info(
                    "Subscribe for %s returned non-success but broker already knows %s; continuing",
                    channel,
                    self.agent_id,
                )
                return True
            raise Exception(f"Failed to subscribe to channel {channel}: {exc}") from exc
        
        if response.get("status") == "success":
            logger.info(f"Subscribed to channel {channel}")
            return True
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Failed to subscribe to channel {channel}: {error}")
    
    def unsubscribe(self, channel: str) -> bool:
        """
        Unsubscribe from a mesh channel.
        
        Args:
            channel: Channel name
            
        Returns:
            True if unsubscription successful
            
        Raises:
            Exception: If unsubscription fails
        """
        response = self._make_request(
            "POST",
            "/mesh/unsubscribe",
            data={
                "agent_id": self.agent_id,
                "channel": channel,
            }
        )
        
        if response.get("status") == "success":
            logger.info(f"Unsubscribed from channel {channel}")
            return True
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Failed to unsubscribe from channel {channel}: {error}")
    
    def list_channels(self) -> Dict[str, int]:
        """
        Get list of available channels with subscriber counts.
        
        Returns:
            Dictionary mapping channel names to subscriber counts
            
        Raises:
            Exception: If request fails
        """
        response = self._make_request("GET", "/mesh/channels")
        
        if response.get("status") == "success":
            return response.get("channels", {})
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Failed to list channels: {error}")
    
    # ----------------------------------------------------------------------
    # Statistics and Monitoring
    # ----------------------------------------------------------------------
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get mesh bus statistics.
        
        Returns:
            Dictionary with mesh statistics
            
        Raises:
            Exception: If request fails
        """
        response = self._make_request("GET", "/mesh/stats")
        
        if response.get("status") == "success":
            return response.get("statistics", {})
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Failed to get mesh stats: {error}")
    
    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get mesh status for this agent.
        
        Returns:
            Dictionary with agent mesh status
            
        Raises:
            Exception: If request fails
        """
        response = self._make_request(
            "GET",
            f"/mesh/agent/{self.agent_id}/status"
        )
        
        if response.get("status") == "success":
            return response.get("mesh_status", {})
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Failed to get agent mesh status: {error}")
    
    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent mesh events (for debugging).
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of mesh events
            
        Raises:
            Exception: If request fails
        """
        response = self._make_request(
            "GET",
            "/mesh/events",
            data={"limit": limit}
        )
        
        if response.get("status") == "success":
            return response.get("events", [])
        else:
            error = response.get("error", "Unknown error")
            raise Exception(f"Failed to get mesh events: {error}")
    
    # ----------------------------------------------------------------------
    # Utility Methods
    # ----------------------------------------------------------------------
    
    def ping(self) -> bool:
        """
        Test connectivity to mesh bus.
        
        Returns:
            True if mesh bus is accessible
        """
        try:
            self.get_stats()
            return True
        except Exception:
            return False
    
    def close(self):
        """Close HTTP client connections."""
        if hasattr(self._http, 'close'):
            self._http.close()
        logger.debug(f"MeshClient for agent {self.agent_id} closed")


# Convenience function for creating a mesh client
def create_mesh_client(
    agent_id: str,
    broker_url: str = "http://127.0.0.1:5555",
    api_key: Optional[str] = None
) -> MeshClient:
    """
    Create and return a MeshClient instance.
    
    Args:
        agent_id: Unique agent identifier
        broker_url: Base URL of SIMP broker
        api_key: Optional API key for authentication
        
    Returns:
        MeshClient instance
    """
    return MeshClient(agent_id=agent_id, broker_url=broker_url, api_key=api_key)


# Example usage
if __name__ == "__main__":
    # Example: Create a mesh client and send/receive messages
    client = create_mesh_client(agent_id="example_agent")
    
    # Subscribe to a channel
    client.subscribe("trading_signals")
    
    # Send a message
    message_id = client.send_to_agent(
        recipient_id="quantumarb",
        payload={"signal": "buy", "asset": "BTC", "confidence": 0.85}
    )
    print(f"Sent message: {message_id}")
    
    # Poll for messages
    messages = client.poll()
    for msg in messages:
        print(f"Received: {msg}")
    
    # Get statistics
    stats = client.get_stats()
    print(f"Mesh stats: {stats}")
    
    client.close()
