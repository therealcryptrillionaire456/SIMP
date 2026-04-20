#!/usr/bin/env python3
"""
Quantum Advisory Broadcaster.

Collects QIP recommendations from broker mesh polling or a file inbox and
broadcasts them to relevant agents using mesh delivery for HTTP agents and
file inbox delivery for file-based agents.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


logger = logging.getLogger("quantum_advisory_broadcaster")

BROKER_URL = "http://127.0.0.1:5555"
AGENT_ID = "quantum_advisory_broadcaster"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INBOX = BASE_DIR / "data" / "inboxes" / "quantum_advisory"
DEFAULT_PROCESSED = BASE_DIR / "data" / "processed" / "quantum_advisory"
DEFAULT_RECEIPTS = BASE_DIR / "data" / "quantum_broadcast" / "delivery_receipts.jsonl"
DEFAULT_REGISTRY = BASE_DIR / "data" / "agent_registry.jsonl"


class QuantumAdvisoryBroadcaster:
    def __init__(
        self,
        *,
        broker_url: str = BROKER_URL,
        agent_id: str = AGENT_ID,
        inbox_dir: Path = DEFAULT_INBOX,
        processed_dir: Path = DEFAULT_PROCESSED,
        receipts_path: Path = DEFAULT_RECEIPTS,
        registry_path: Path = DEFAULT_REGISTRY,
        dry_run: bool = False,
        retry_attempts: int = 3,
    ) -> None:
        self.broker_url = broker_url.rstrip("/")
        self.agent_id = agent_id
        self.inbox_dir = inbox_dir
        self.processed_dir = processed_dir
        self.receipts_path = receipts_path
        self.registry_path = registry_path
        self.dry_run = dry_run
        self.retry_attempts = retry_attempts
        self._registered = False

        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.receipts_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_json(self, url: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(url, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.debug("GET %s failed: %s", url, exc)
            return None

    def _post_json(self, url: str, payload: Dict[str, Any], **kwargs: Any) -> Optional[Dict[str, Any]]:
        try:
            response = requests.post(url, json=payload, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.debug("POST %s failed: %s", url, exc)
            return None

    def ensure_registered(self) -> bool:
        if self._registered:
            return True
        payload = {
            "agent_id": self.agent_id,
            "agent_type": "broadcaster",
            "endpoint": "",
            "capabilities": ["quantum_advisory_broadcast", "delivery_receipts"],
            "metadata": {"transport": "file", "broadcast_scope": "advisory"},
        }
        response = self._post_json(f"{self.broker_url}/agents/register", payload)
        if response and response.get("status") == "success":
            self._post_json(
                f"{self.broker_url}/mesh/subscribe",
                {"agent_id": self.agent_id, "channel": "quantum_advisory"},
            )
            self._registered = True
        return self._registered

    def collect_from_broker(self) -> List[Dict[str, Any]]:
        if not self.ensure_registered():
            return []
        response = self._get_json(
            f"{self.broker_url}/mesh/poll",
            params={"agent_id": self.agent_id, "max_messages": 10},
        )
        if not response or response.get("status") != "success":
            return []
        recommendations = []
        for message in response.get("messages", []):
            payload = message.get("payload", {})
            if "recommendation" in payload:
                recommendations.append(payload["recommendation"])
            elif payload.get("intent") == "quantum_advisory":
                recommendations.append(payload)
        return recommendations

    def collect_from_inbox(self) -> List[Dict[str, Any]]:
        recommendations = []
        for path in sorted(self.inbox_dir.glob("*.json")):
            payload = json.loads(path.read_text())
            recommendations.append(payload.get("recommendation", payload))
            shutil.move(str(path), self.processed_dir / path.name)
        return recommendations

    def load_agents(self) -> List[Dict[str, Any]]:
        response = self._get_json(f"{self.broker_url}/agents")
        if response:
            agents = response.get("agents", [])
            if isinstance(agents, dict):
                return [dict(agent_id=agent_id, **agent) for agent_id, agent in agents.items()]
            if isinstance(agents, list):
                return agents
        return self.load_agents_from_registry()

    def load_agents_from_registry(self) -> List[Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        if not self.registry_path.exists():
            return []
        for line in self.registry_path.read_text().splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            agent_id = payload.get("agent_id")
            if not agent_id:
                continue
            current = latest.setdefault(agent_id, {"agent_id": agent_id})
            if payload.get("event") == "registered":
                current.update(payload.get("payload", {}))
            current.update(payload.get("updates", {}))
            for key in ("capabilities", "endpoint", "metadata", "agent_type", "name", "status"):
                if key in payload:
                    current[key] = payload[key]
        return list(latest.values())

    def resolve_targets(self, recommendation: Dict[str, Any], agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        target_ids = recommendation.get("target_agents") or recommendation.get("targets")
        if target_ids:
            return [agent for agent in agents if agent.get("agent_id") in set(target_ids)]

        required_capabilities = set(recommendation.get("target_capabilities") or recommendation.get("capabilities") or [])
        if required_capabilities:
            matched = []
            for agent in agents:
                capabilities = set(agent.get("capabilities", []) or [])
                if capabilities.intersection(required_capabilities):
                    matched.append(agent)
            return matched

        kind = (recommendation.get("kind") or recommendation.get("intent_type") or "").lower()
        if "maintenance" in kind:
            return [agent for agent in agents if agent.get("agent_id") == "projectx_native"]
        if "prediction" in kind:
            return [agent for agent in agents if agent.get("agent_id") == "bullbear_predictor"]
        if "trade" in kind or "arbitrage" in kind:
            return [agent for agent in agents if agent.get("agent_id") in {"gate4_real", "quantumarb_real", "quantumarb_primary"}]

        return [agent for agent in agents if agent.get("agent_id") and agent.get("agent_id") != self.agent_id]

    def write_receipt(self, receipt: Dict[str, Any]) -> None:
        with self.receipts_path.open("a") as handle:
            handle.write(json.dumps(receipt) + "\n")

    def deliver(self, recommendation: Dict[str, Any], agent: Dict[str, Any]) -> Dict[str, Any]:
        delivery_id = f"broadcast-{uuid.uuid4().hex[:12]}"
        agent_id = agent.get("agent_id", "unknown")
        receipt = {
            "delivery_id": delivery_id,
            "agent_id": agent_id,
            "recommendation_id": recommendation.get("recommendation_id", recommendation.get("intent_id", delivery_id)),
            "status": "pending",
            "attempts": 0,
        }

        if self.dry_run:
            receipt["status"] = "dry_run"
            self.write_receipt(receipt)
            return receipt

        metadata = agent.get("metadata", {}) or {}
        transport = metadata.get("transport")
        endpoint = agent.get("endpoint", "")

        for attempt in range(1, self.retry_attempts + 1):
            receipt["attempts"] = attempt
            if transport == "file" or endpoint in {"", "(file-based)"}:
                inbox_path = Path(metadata.get("inbox", BASE_DIR / "data" / "inboxes" / agent_id))
                inbox_path.mkdir(parents=True, exist_ok=True)
                target = inbox_path / f"quantum_advisory_{delivery_id}.json"
                target.write_text(json.dumps({"delivery_id": delivery_id, "recommendation": recommendation}, indent=2))
                receipt["status"] = "delivered"
                receipt["path"] = str(target)
                self.write_receipt(receipt)
                return receipt

            response = self._post_json(
                f"{self.broker_url}/mesh/send",
                {
                    "sender_id": self.agent_id,
                    "recipient_id": agent_id,
                    "channel": "quantum_advisory",
                    "payload": {
                        "intent": "quantum_advisory",
                        "recommendation": recommendation,
                        "delivery_id": delivery_id,
                    },
                },
            )
            if response and response.get("status") == "success":
                receipt["status"] = "delivered"
                receipt["message_id"] = response.get("message_id")
                self.write_receipt(receipt)
                return receipt

        receipt["status"] = "failed"
        self.write_receipt(receipt)
        return receipt

    def broadcast(self, recommendation: Dict[str, Any]) -> List[Dict[str, Any]]:
        agents = self.load_agents()
        targets = self.resolve_targets(recommendation, agents)
        return [self.deliver(recommendation, agent) for agent in targets]

    def run_once(self) -> List[Dict[str, Any]]:
        receipts: List[Dict[str, Any]] = []
        for recommendation in self.collect_from_broker() + self.collect_from_inbox():
            receipts.extend(self.broadcast(recommendation))
        return receipts


def main() -> None:
    parser = argparse.ArgumentParser(description="Broadcast quantum advisory recommendations")
    parser.add_argument("--broker", default=BROKER_URL)
    parser.add_argument("--interval", type=float, default=30.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [quantum_broadcast] %(levelname)s %(message)s")
    broadcaster = QuantumAdvisoryBroadcaster(broker_url=args.broker, dry_run=args.dry_run)

    if args.once:
        print(json.dumps({"receipts": broadcaster.run_once()}, indent=2))
        return

    while True:
        broadcaster.run_once()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
