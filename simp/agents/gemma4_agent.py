"""Gemma4 local LLM agent adapter for SIMP protocol.

Wraps a local Gemma4 model (via Ollama, LMStudio, or compatible API)
as a SIMP agent capable of handling research, planning, and code tasks.

Usage:
    agent = Gemma4Agent(
        agent_id="gemma4_local",
        model_endpoint="http://localhost:11434",  # Ollama default
        model_name="gemma4:e2b",
    )
"""

import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class Gemma4Agent:
    """SIMP agent backed by a local Gemma4/Gemma2 model.

    Compatible with Ollama API (POST /api/generate) and OpenAI-compatible
    endpoints (POST /v1/chat/completions).
    """

    SUPPORTED_INTENTS = [
        "research", "planning", "code_task", "code_review",
        "summarization", "docs", "spec", "architecture",
        "ping", "status_check",
    ]

    def __init__(
        self,
        agent_id: str = "gemma4_local",
        model_endpoint: str = "http://localhost:11434",
        model_name: str = "gemma4:e2b",
        api_format: str = "ollama",  # "ollama" or "openai"
        timeout: float = 120.0,
        max_tokens: int = 4096,
    ):
        self.agent_id = agent_id
        self.model_endpoint = model_endpoint.rstrip("/")
        self.model_name = model_name
        self.api_format = api_format
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.intents_handled = 0
        self._client = httpx.Client(timeout=timeout)
        self._last_health_check_at = 0.0
        self._last_health_result: Dict[str, Any] = {
            "status": "starting",
            "agent_id": self.agent_id,
            "model": self.model_name,
            "model_available": False,
            "backend_reachable": False,
            "intents_handled": 0,
        }

    def handle_intent(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a SIMP intent by generating a response from the local model.

        Args:
            intent_data: SIMP intent dict with intent_type and params.

        Returns:
            SIMP response dict.
        """
        intent_type = intent_data.get("intent_type", "")
        params = intent_data.get("params", {})
        start = time.time()

        if intent_type in {"ping", "status_check"}:
            self.intents_handled += 1
            duration_ms = int((time.time() - start) * 1000)
            return {
                "type": "response",
                "intent_id": intent_data.get("intent_id", ""),
                "agent_id": self.agent_id,
                "status": "completed",
                "response": {
                    "content": "ok",
                    "model": self.model_name,
                    "duration_ms": duration_ms,
                    "intent_type": intent_type,
                },
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        # Build prompt from intent
        prompt = self._build_prompt(intent_type, params)

        try:
            response_text = self._generate(prompt)
            self.intents_handled += 1
            duration_ms = int((time.time() - start) * 1000)

            return {
                "type": "response",
                "intent_id": intent_data.get("intent_id", ""),
                "agent_id": self.agent_id,
                "status": "completed",
                "response": {
                    "content": response_text,
                    "model": self.model_name,
                    "duration_ms": duration_ms,
                    "intent_type": intent_type,
                },
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        except Exception as exc:
            logger.error(f"Gemma4 generation failed: {exc}")
            return {
                "type": "response",
                "intent_id": intent_data.get("intent_id", ""),
                "agent_id": self.agent_id,
                "status": "failed",
                "error": str(exc),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

    def _build_prompt(self, intent_type: str, params: Dict[str, Any]) -> str:
        """Build a model prompt from intent type and params."""
        if intent_type == "research":
            query = params.get("query", params.get("topic", ""))
            return f"Research the following topic and provide a detailed analysis:\n\n{query}"
        elif intent_type == "planning":
            goal = params.get("goal", params.get("description", ""))
            return f"Create a detailed plan for the following goal:\n\n{goal}"
        elif intent_type in ("code_task", "code_editing"):
            task = params.get("task", params.get("description", params.get("code", "")))
            return f"Complete the following coding task:\n\n{task}"
        elif intent_type == "code_review":
            code = params.get("code", params.get("diff", ""))
            return f"Review the following code and provide feedback:\n\n{code}"
        elif intent_type == "summarization":
            text = params.get("text", params.get("content", ""))
            return f"Summarize the following:\n\n{text}"
        elif intent_type in ("docs", "spec", "architecture"):
            description = params.get("description", params.get("topic", ""))
            return f"Write {intent_type} documentation for:\n\n{description}"
        else:
            # Generic fallback
            return f"Handle the following {intent_type} request:\n\n{json.dumps(params, indent=2)}"

    def _generate(self, prompt: str) -> str:
        """Call the local model API to generate a response."""
        if self.api_format == "ollama":
            return self._generate_ollama(prompt)
        elif self.api_format == "openai":
            return self._generate_openai(prompt)
        else:
            raise ValueError(f"Unknown API format: {self.api_format}")

    def _generate_ollama(self, prompt: str) -> str:
        """Generate via Ollama API."""
        resp = self._client.post(
            f"{self.model_endpoint}/api/generate",
            json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": self.max_tokens,
                },
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _generate_openai(self, prompt: str) -> str:
        """Generate via OpenAI-compatible API."""
        resp = self._client.post(
            f"{self.model_endpoint}/v1/chat/completions",
            json={
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def health(self) -> Dict[str, Any]:
        """Return health status."""
        now = time.time()
        if now - self._last_health_check_at < 5.0:
            cached = dict(self._last_health_result)
            cached["intents_handled"] = self.intents_handled
            cached["cached"] = True
            return cached

        try:
            # Try to ping the model endpoint
            if self.api_format == "ollama":
                with httpx.Client(timeout=2.0) as health_client:
                    resp = health_client.get(f"{self.model_endpoint}/api/tags")
                model_prefix = self.model_name.split(":")[0].lower()
                model_available = any(
                    m.get("name", "").lower().startswith(model_prefix)
                    for m in resp.json().get("models", [])
                )
            else:
                with httpx.Client(timeout=2.0) as health_client:
                    resp = health_client.get(f"{self.model_endpoint}/v1/models")
                model_available = resp.status_code == 200

            payload = {
                "status": "ok" if model_available else "degraded",
                "agent_id": self.agent_id,
                "model": self.model_name,
                "model_available": model_available,
                "backend_reachable": True,
                "intents_handled": self.intents_handled,
            }
            self._last_health_check_at = now
            self._last_health_result = dict(payload)
            return payload
        except Exception as exc:
            payload = {
                "status": "error",
                "agent_id": self.agent_id,
                "model": self.model_name,
                "model_available": False,
                "backend_reachable": False,
                "intents_handled": self.intents_handled,
                "error": str(exc),
            }
            self._last_health_check_at = now
            self._last_health_result = dict(payload)
            return payload

    def close(self):
        """Close the HTTP client."""
        self._client.close()
