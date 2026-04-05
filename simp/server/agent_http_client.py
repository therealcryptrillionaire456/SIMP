"""
SIMP HTTP Agent Client

HTTP-based client for agents to communicate with the SIMP broker.
Replaces the raw-socket agent_client.py with proper HTTP transport.
"""

import logging
import uuid
import time
from datetime import datetime
from typing import Any, Dict, Optional

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False


class SimpHttpClient:
    """HTTP client for agents to communicate with SIMP broker."""

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        broker_url: str = "http://127.0.0.1:5555",
        timeout: float = 30.0,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.broker_url = broker_url.rstrip("/")
        self.timeout = timeout

        self.logger = logging.getLogger(f"SIMP.HttpClient.{agent_id}")
        self.logger.setLevel(logging.INFO)

        self.intents_sent = 0
        self.responses_received = 0

        self.logger.info(
            f"SIMP HTTP Client initialized: {agent_id} ({agent_type}) "
            f"-> {self.broker_url}"
        )

    def _post(self, path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a POST request to the broker."""
        url = f"{self.broker_url}{path}"
        if _REQUESTS_AVAILABLE:
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                self.logger.error(f"POST {path} failed: {exc}")
                return None
        elif _HTTPX_AVAILABLE:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                self.logger.error(f"POST {path} failed: {exc}")
                return None
        else:
            self.logger.error("Neither requests nor httpx is installed")
            return None

    def _get(self, path: str) -> Optional[Dict[str, Any]]:
        """Make a GET request to the broker."""
        url = f"{self.broker_url}{path}"
        if _REQUESTS_AVAILABLE:
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                self.logger.error(f"GET {path} failed: {exc}")
                return None
        elif _HTTPX_AVAILABLE:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(url)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                self.logger.error(f"GET {path} failed: {exc}")
                return None
        else:
            self.logger.error("Neither requests nor httpx is installed")
            return None

    def register(
        self,
        endpoint: str,
        capabilities: Optional[list] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Register this agent with the broker via POST /agents/register."""
        payload = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "endpoint": endpoint,
            "metadata": {
                **(metadata or {}),
                "capabilities": capabilities or [],
                "name": name or self.agent_id,
            },
        }
        result = self._post("/agents/register", payload)
        if result and result.get("status") == "success":
            self.logger.info(f"Registered with broker as {self.agent_id}")
        return result

    def send_intent(
        self,
        target_agent: str,
        intent_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send an intent to another agent via POST /intents/route."""
        payload = {
            "intent_id": f"intent:{self.agent_id}:{uuid.uuid4()}",
            "source_agent": self.agent_id,
            "target_agent": target_agent,
            "intent_type": intent_type,
            "params": params or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        result = self._post("/intents/route", payload)
        if result:
            self.intents_sent += 1
        return result

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Get broker status via GET /status."""
        return self._get("/status")

    def get_intent_status(self, intent_id: str) -> Optional[Dict[str, Any]]:
        """Get intent status via GET /intents/{id}."""
        return self._get(f"/intents/{intent_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "broker_url": self.broker_url,
            "intents_sent": self.intents_sent,
            "responses_received": self.responses_received,
            "timestamp": datetime.utcnow().isoformat(),
        }
