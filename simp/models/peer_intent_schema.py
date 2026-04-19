"""
SIMP Peer Intent Schema — Perplexity ↔ CoWork Contract
=======================================================
Version: 1.0.0
Authors: Perplexity Computer (design) + Claude CoWork (implementation)

This module defines the locked, versioned intent schemas for communication
between perplexity_research and claude_cowork agents over the SIMP broker.

Hard rules (cannot be relaxed without a schema version bump):
  1. intent_type must be in ALLOWED_REQUEST_TYPES or ALLOWED_RESULT_TYPES.
  2. task_id must be non-empty and trace back to a queued work item.
  3. source/target must be in PEER_AGENTS (no trading agents on this path).
  4. Results must carry status ("ok" | "error" | "rejected").
  5. Schema version must match SCHEMA_VERSION exactly.

Usage:
    from peer_intent_schema import PeerIntentRequest, PeerIntentResult
    from peer_intent_schema import validate_request, validate_result

    req = PeerIntentRequest.create(
        intent_type="code_task",
        source_agent="perplexity_research",
        target_agent="claude_cowork",
        topic="quantumarb_scaffold",
        prompt="Scaffold QuantumArb agent class...",
        context={"files": ["simp/agents/quantumarb_agent.py"]},
    )
    validate_request(req.to_dict())  # raises ValueError if invalid
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------

#: Agents that may appear on source or target of peer intents.
#: Trading agents are explicitly excluded from this path.
PEER_AGENTS: frozenset[str] = frozenset({
    "perplexity_research",
    "claude_cowork",
    "kloutbot",          # orchestrator only — may delegate to either peer
    "simp_router",       # broker internal
})

#: Intent types claude_cowork accepts.
ALLOWED_REQUEST_TYPES: frozenset[str] = frozenset({
    "code_task",
    "planning",
    "coordination",
    "status_check",
    "capability_query",
    "ping",
})

#: Intent types claude_cowork emits as responses.
ALLOWED_RESULT_TYPES: frozenset[str] = frozenset({
    "code_task_result",
    "planning_result",
    "coordination_result",
    "status_check_result",
    "capability_query_result",
    "intent_rejected",
    "pong",
})

#: Intent types explicitly forbidden on the Perplexity ↔ CoWork path.
#: These map to the bridge's hard firewall (HTTP 403, no queue).
FORBIDDEN_TYPES: frozenset[str] = frozenset({
    "execute_trade",
    "position_sizing",
    "dry_run_trade",
    "place_order",
    "cancel_order",
    "arbitrage_execute",
    "kashclaw_execute",
    "organ_execute",
    "trade_signal",
    "prediction_signal",   # may carry dry_run=False downstream
})

ALLOWED_STATUS: frozenset[str] = frozenset({"ok", "error", "rejected", "queued"})

# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------

@dataclass
class PeerIntentRequest:
    """
    Structured request intent between Perplexity and CoWork.

    Both agents must use this schema; the bridge validates it on receive.
    """
    intent_type:   str
    source_agent:  str
    target_agent:  str
    task_id:       str
    topic:         str
    prompt:        str
    intent_id:     str                       = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp:     str                       = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str                      = field(default=SCHEMA_VERSION)
    context:       Dict[str, Any]            = field(default_factory=dict)
    priority:      str                       = "normal"   # "low" | "normal" | "high" | "urgent"
    requires_response: bool                  = True
    timeout_seconds: Optional[int]           = 300
    dry_run:       bool                      = True       # always True on this path

    @classmethod
    def create(
        cls,
        intent_type: str,
        source_agent: str,
        target_agent: str,
        topic: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
        task_id: Optional[str] = None,
        timeout_seconds: int = 300,
    ) -> "PeerIntentRequest":
        return cls(
            intent_type      = intent_type,
            source_agent     = source_agent,
            target_agent     = target_agent,
            topic            = topic,
            prompt           = prompt,
            context          = context or {},
            priority         = priority,
            task_id          = task_id or f"peer-{uuid.uuid4().hex[:12]}",
            timeout_seconds  = timeout_seconds,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # SIMP broker expects top-level params dict
        d["params"] = {
            "task_id":          self.task_id,
            "topic":            self.topic,
            "prompt":           self.prompt,
            "context":          self.context,
            "priority":         self.priority,
            "requires_response": self.requires_response,
            "timeout_seconds":  self.timeout_seconds,
            "dry_run":          self.dry_run,
            "schema_version":   self.schema_version,
        }
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ---------------------------------------------------------------------------
# Result schema
# ---------------------------------------------------------------------------

@dataclass
class PeerIntentResult:
    """
    Structured result intent emitted by claude_cowork back to the requester.
    """
    intent_type:    str
    source_agent:   str
    target_agent:   str
    task_id:        str
    status:         str                      # "ok" | "error" | "rejected"
    intent_id:      str                      = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp:      str                      = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str                      = field(default=SCHEMA_VERSION)
    artifacts:      List[Dict[str, str]]     = field(default_factory=list)
    notes:          str                      = ""
    error_message:  Optional[str]            = None
    dry_run:        bool                     = True

    @classmethod
    def ok(
        cls,
        source_agent: str,
        target_agent: str,
        task_id: str,
        result_type: str,
        artifacts: Optional[List[Dict[str, str]]] = None,
        notes: str = "",
    ) -> "PeerIntentResult":
        return cls(
            intent_type  = result_type,
            source_agent = source_agent,
            target_agent = target_agent,
            task_id      = task_id,
            status       = "ok",
            artifacts    = artifacts or [],
            notes        = notes,
        )

    @classmethod
    def error(
        cls,
        source_agent: str,
        target_agent: str,
        task_id: str,
        result_type: str,
        error_message: str,
    ) -> "PeerIntentResult":
        return cls(
            intent_type   = result_type,
            source_agent  = source_agent,
            target_agent  = target_agent,
            task_id       = task_id,
            status        = "error",
            error_message = error_message,
        )

    @classmethod
    def rejected(
        cls,
        source_agent: str,
        target_agent: str,
        task_id: str,
        reason: str,
    ) -> "PeerIntentResult":
        return cls(
            intent_type   = "intent_rejected",
            source_agent  = source_agent,
            target_agent  = target_agent,
            task_id       = task_id,
            status        = "rejected",
            error_message = reason,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["params"] = {
            "task_id":       self.task_id,
            "status":        self.status,
            "artifacts":     self.artifacts,
            "notes":         self.notes,
            "error_message": self.error_message,
            "dry_run":       self.dry_run,
            "schema_version": self.schema_version,
        }
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

class PeerSchemaError(ValueError):
    """Raised when a peer intent fails schema validation."""

def validate_request(data: Dict[str, Any]) -> None:
    """
    Validate an inbound request intent dict.
    Raises PeerSchemaError with a descriptive message on failure.
    """
    _require("intent_type", data)
    _require("source_agent", data)
    _require("target_agent", data)

    intent_type  = data["intent_type"]
    source_agent = data["source_agent"]
    target_agent = data["target_agent"]

    # Hard firewall: forbidden types must be caught before reaching the queue
    if intent_type in FORBIDDEN_TYPES:
        raise PeerSchemaError(
            f"FIREWALL: intent_type '{intent_type}' is forbidden on the "
            f"Perplexity↔CoWork path. No trading intents may flow through this channel."
        )

    # Must be an accepted request type
    if intent_type not in ALLOWED_REQUEST_TYPES:
        raise PeerSchemaError(
            f"intent_type '{intent_type}' is not in ALLOWED_REQUEST_TYPES. "
            f"Allowed: {sorted(ALLOWED_REQUEST_TYPES)}"
        )

    # Source/target must be peer agents
    for role, agent in [("source_agent", source_agent), ("target_agent", target_agent)]:
        if agent not in PEER_AGENTS:
            raise PeerSchemaError(
                f"{role} '{agent}' is not a recognised peer agent. "
                f"Peer agents: {sorted(PEER_AGENTS)}"
            )

    # task_id required for non-trivial requests
    params = data.get("params", {})
    if intent_type not in {"ping", "status_check", "capability_query"}:
        task_id = data.get("task_id") or params.get("task_id", "")
        if not task_id:
            raise PeerSchemaError(
                f"task_id is required for intent_type '{intent_type}'"
            )


def validate_result(data: Dict[str, Any]) -> None:
    """
    Validate an outbound result intent dict.
    Raises PeerSchemaError on failure.
    """
    _require("intent_type", data)
    _require("source_agent", data)
    _require("target_agent", data)
    _require("status", data)

    intent_type = data["intent_type"]
    status      = data["status"]

    if intent_type not in ALLOWED_RESULT_TYPES:
        raise PeerSchemaError(
            f"intent_type '{intent_type}' is not in ALLOWED_RESULT_TYPES. "
            f"Allowed: {sorted(ALLOWED_RESULT_TYPES)}"
        )

    if status not in ALLOWED_STATUS:
        raise PeerSchemaError(
            f"status '{status}' is not valid. Allowed: {sorted(ALLOWED_STATUS)}"
        )

    params = data.get("params", {})
    task_id = data.get("task_id") or params.get("task_id", "")
    if intent_type != "pong" and not task_id:
        raise PeerSchemaError("task_id is required in results")


def _require(key: str, data: Dict[str, Any]) -> None:
    if not data.get(key):
        raise PeerSchemaError(f"Required field '{key}' is missing or empty")


# ---------------------------------------------------------------------------
# JSON Schema export (draft-07 compatible)
# ---------------------------------------------------------------------------

def export_json_schema() -> Dict[str, Any]:
    """Export a JSON Schema document describing both request and result formats."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://github.com/therealcryptrillionaire456/SIMP/simp/models/peer_intent_schema.json",
        "title": "SIMP Peer Intent Schema",
        "description": (
            "Locked schema for intents exchanged between perplexity_research "
            "and claude_cowork agents. Version: " + SCHEMA_VERSION
        ),
        "version": SCHEMA_VERSION,
        "definitions": {
            "PeerIntentRequest": {
                "type": "object",
                "required": ["intent_type", "source_agent", "target_agent",
                             "task_id", "topic", "prompt"],
                "properties": {
                    "intent_type":    {"type": "string", "enum": sorted(ALLOWED_REQUEST_TYPES)},
                    "source_agent":   {"type": "string", "enum": sorted(PEER_AGENTS)},
                    "target_agent":   {"type": "string", "enum": sorted(PEER_AGENTS)},
                    "task_id":        {"type": "string", "minLength": 1},
                    "topic":          {"type": "string", "minLength": 1},
                    "prompt":         {"type": "string", "minLength": 1},
                    "intent_id":      {"type": "string"},
                    "timestamp":      {"type": "string", "format": "date-time"},
                    "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                    "context":        {"type": "object"},
                    "priority":       {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
                    "requires_response": {"type": "boolean"},
                    "timeout_seconds":   {"type": ["integer", "null"]},
                    "dry_run":           {"type": "boolean", "const": True},
                    "params":            {"type": "object"},
                },
                "not": {
                    "properties": {
                        "intent_type": {"enum": sorted(FORBIDDEN_TYPES)}
                    }
                }
            },
            "PeerIntentResult": {
                "type": "object",
                "required": ["intent_type", "source_agent", "target_agent",
                             "task_id", "status"],
                "properties": {
                    "intent_type":    {"type": "string", "enum": sorted(ALLOWED_RESULT_TYPES)},
                    "source_agent":   {"type": "string", "enum": sorted(PEER_AGENTS)},
                    "target_agent":   {"type": "string", "enum": sorted(PEER_AGENTS)},
                    "task_id":        {"type": "string"},
                    "status":         {"type": "string", "enum": sorted(ALLOWED_STATUS)},
                    "intent_id":      {"type": "string"},
                    "timestamp":      {"type": "string", "format": "date-time"},
                    "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                    "artifacts":      {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path":        {"type": "string"},
                                "description": {"type": "string"},
                                "type":        {"type": "string"},
                            }
                        }
                    },
                    "notes":          {"type": "string"},
                    "error_message":  {"type": ["string", "null"]},
                    "dry_run":        {"type": "boolean", "const": True},
                    "params":         {"type": "object"},
                },
            }
        },
        "forbidden_intent_types": sorted(FORBIDDEN_TYPES),
        "peer_agents":            sorted(PEER_AGENTS),
        "allowed_request_types":  sorted(ALLOWED_REQUEST_TYPES),
        "allowed_result_types":   sorted(ALLOWED_RESULT_TYPES),
    }


if __name__ == "__main__":
    import sys

    if "--export-schema" in sys.argv:
        print(json.dumps(export_json_schema(), indent=2))
    else:
        # Quick self-test
        req = PeerIntentRequest.create(
            intent_type  = "code_task",
            source_agent = "perplexity_research",
            target_agent = "claude_cowork",
            topic        = "test",
            prompt       = "Scaffold something",
        )
        validate_request(req.to_dict())

        result = PeerIntentResult.ok(
            source_agent = "claude_cowork",
            target_agent = "perplexity_research",
            task_id      = req.task_id,
            result_type  = "code_task_result",
            artifacts    = [{"path": "simp/agents/test.py", "type": "python"}],
            notes        = "Done",
        )
        validate_result(result.to_dict())

        print(f"PeerIntentRequest v{SCHEMA_VERSION}  task_id={req.task_id}")
        print(f"PeerIntentResult  status={result.status}  artifacts={len(result.artifacts)}")
        print("✅ Self-test passed")
