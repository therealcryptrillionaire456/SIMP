"""
ProjectX Durability & Self-Diagnostics — Sprint S6 (Sprint 36)

Provides lightweight diagnostic helpers that can detect and report on
ProjectX-related health signals visible from the SIMP compat layer.

Design rules:
- Read-only. Never modifies broker state or ProjectX files.
- No filesystem access outside of explicitly allowed paths (env-configured).
- All JSONL recovery is advisory: never auto-repairs.
- No shell execution from this module.
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import requests

logger = logging.getLogger("SIMP.ProjectXDiag")


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

class DiagnosticStatus:
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Task ledger integrity check
# ---------------------------------------------------------------------------


def check_task_ledger_integrity(ledger_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Read SIMP task ledger JSONL and check line-level integrity.

    Never raises. Never logs corrupt line content (could contain secrets).
    """
    if ledger_path is None:
        ledger_path = os.environ.get("SIMP_TASK_LEDGER", "task_ledger.jsonl")

    result: Dict[str, Any] = {
        "status": DiagnosticStatus.UNKNOWN,
        "total_lines": 0,
        "valid_lines": 0,
        "corrupt_lines": 0,
        "corrupt_line_numbers": [],
        "last_valid_timestamp": None,
    }

    try:
        with open(ledger_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        result["status"] = DiagnosticStatus.ERROR
        return result
    except Exception:
        result["status"] = DiagnosticStatus.ERROR
        return result

    result["total_lines"] = len(lines)
    corrupt_nums: list = []
    last_ts: Optional[str] = None

    for idx, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            result["valid_lines"] += 1
            ts = obj.get("timestamp")
            if ts:
                last_ts = ts
        except (json.JSONDecodeError, Exception):
            result["corrupt_lines"] += 1
            if len(corrupt_nums) < 10:
                corrupt_nums.append(idx)
            # NEVER log the corrupt line content

    result["corrupt_line_numbers"] = corrupt_nums
    result["last_valid_timestamp"] = last_ts

    if result["corrupt_lines"] == 0:
        result["status"] = DiagnosticStatus.OK
    else:
        result["status"] = DiagnosticStatus.DEGRADED

    return result


# ---------------------------------------------------------------------------
# Protocol facts integrity check
# ---------------------------------------------------------------------------


def check_protocol_facts_integrity(facts_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Check protocol facts file (JSON or JSONL) for parse errors.
    """
    if facts_path is None:
        facts_path = os.environ.get("SIMP_PROTOCOL_FACTS", "protocol_facts.json")

    result: Dict[str, Any] = {
        "status": DiagnosticStatus.UNKNOWN,
        "key_count": 0,
        "last_updated": None,
        "issues": [],
    }

    try:
        with open(facts_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return result  # status stays unknown
    except Exception as e:
        result["issues"].append(str(e)[:200])
        return result

    try:
        data = json.loads(content)
        if isinstance(data, dict):
            result["key_count"] = len(data)
            result["last_updated"] = data.get("last_updated")
        result["status"] = DiagnosticStatus.OK
    except json.JSONDecodeError as e:
        result["status"] = DiagnosticStatus.DEGRADED
        result["issues"].append(f"JSON parse error: {str(e)[:200]}")

    return result


# ---------------------------------------------------------------------------
# Full health report
# ---------------------------------------------------------------------------


def build_projectx_health_report(broker: Any) -> Dict[str, Any]:
    """
    Build a health report for the ProjectX native agent.

    NEVER exposes file paths in the response.
    """
    report: Dict[str, Any] = {
        "status": DiagnosticStatus.UNKNOWN,
        "agent_registered": False,
        "agent_endpoint_reachable": False,
        "task_ledger": {},
        "protocol_facts": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Check agent registration
        agent_info = None
        if broker and hasattr(broker, "agents"):
            for aid, info in broker.agents.items():
                at = info.get("agent_type", "")
                if at == "projectx_native":
                    agent_info = info
                    break

        if agent_info:
            report["agent_registered"] = True
            endpoint = agent_info.get("endpoint", "")
            if endpoint and endpoint != "(file-based)":
                try:
                    resp = requests.head(
                        f"{endpoint}/health", timeout=2, allow_redirects=False
                    )
                    report["agent_endpoint_reachable"] = resp.status_code < 500
                except Exception:
                    report["agent_endpoint_reachable"] = False

        # Task ledger check
        report["task_ledger"] = check_task_ledger_integrity()
        # Remove any path-like fields
        report["task_ledger"].pop("path", None)

        # Protocol facts check
        report["protocol_facts"] = check_protocol_facts_integrity()
        report["protocol_facts"].pop("path", None)

        # Overall status
        ledger_status = report["task_ledger"].get("status", DiagnosticStatus.UNKNOWN)
        if report["agent_registered"] and ledger_status == DiagnosticStatus.OK:
            report["status"] = DiagnosticStatus.OK
        elif report["agent_registered"]:
            report["status"] = DiagnosticStatus.DEGRADED
        else:
            report["status"] = DiagnosticStatus.DEGRADED

    except Exception:
        report["status"] = DiagnosticStatus.ERROR

    return report
