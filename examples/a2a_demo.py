"""
SIMP A2A End-to-End Demo — Sprint S9 (Sprint 39)

Demonstrates a complete A2A->SIMP->Kashclaw->ProjectX->FinancialOps (simulated) flow.

This is a reference demo client — not production code. It runs against a live broker.
Usage: python3 examples/a2a_demo.py [--broker-url http://127.0.0.1:5555] [--api-key ...]

Flow:
1. Discover available agents via GET /.well-known/agent-card.json
2. Submit a planning task via POST /a2a/tasks (maps to kashclaw_gemma -> planning)
3. Submit a maintenance.health_check via POST /a2a/agents/projectx/tasks
4. Simulate a financial op via POST /a2a/agents/financial-ops/tasks
5. Query events via GET /a2a/events
6. Print structured summary

All steps are non-destructive and read-only or simulate-only.
"""

import argparse
import json
import sys
from typing import Dict, Any, Optional

import requests


class A2ADemoClient:
    """Reference A2A client for the SIMP broker."""

    def __init__(self, broker_url: str, api_key: str = ""):
        self.broker_url = broker_url.rstrip("/")
        self.headers: Dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-API-Key"] = api_key

    def discover(self) -> Dict[str, Any]:
        """Step 1: Discover available agents via well-known card."""
        url = f"{self.broker_url}/.well-known/agent-card.json"
        resp = requests.get(url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def submit_planning_task(self) -> Dict[str, Any]:
        """Step 2: Submit a planning task (maps to kashclaw_gemma planning)."""
        url = f"{self.broker_url}/a2a/tasks"
        payload = {
            "task_type": "planning",
            "input": {"goal": "Optimize CI/CD pipeline for ProjectX"},
        }
        resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def run_maintenance_check(self) -> Dict[str, Any]:
        """Step 3: Submit a ProjectX health check."""
        url = f"{self.broker_url}/a2a/agents/projectx/tasks"
        payload = {
            "skill_id": "maintenance.health_check",
            "input": {},
        }
        resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def simulate_financial_op(self) -> Dict[str, Any]:
        """Step 4: Simulate a financial operation."""
        url = f"{self.broker_url}/a2a/agents/financial-ops/tasks"
        payload = {
            "op_type": "small_purchase",
            "would_spend": 5.00,
            "description": "Demo: simulated purchase of CI runner credits",
        }
        resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def fetch_events(self, limit: int = 10) -> Dict[str, Any]:
        """Step 5: Query recent A2A events."""
        url = f"{self.broker_url}/a2a/events?limit={limit}"
        resp = requests.get(url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()


def run_demo(broker_url: str, api_key: str = "") -> Dict[str, Any]:
    """Orchestrate the full A2A demo flow."""
    client = A2ADemoClient(broker_url, api_key)
    results: Dict[str, Any] = {}

    print("=" * 60)
    print("SIMP A2A End-to-End Demo")
    print("=" * 60)

    # Step 1
    print("\n[1/5] Discovering agents...")
    try:
        card = client.discover()
        results["discover"] = card
        agent_count = len(card.get("agents", []))
        print(f"  Broker: {card.get('name', 'unknown')}")
        print(f"  Agents: {agent_count}")
    except requests.ConnectionError:
        raise ConnectionError(f"Cannot connect to broker at {broker_url}")

    # Step 2
    print("\n[2/5] Submitting planning task...")
    try:
        plan_result = client.submit_planning_task()
        results["planning"] = plan_result
        print(f"  Task ID: {plan_result.get('taskId', 'N/A')}")
        print(f"  State: {plan_result.get('state', 'N/A')}")
    except Exception as e:
        results["planning"] = {"error": str(e)}
        print(f"  Error: {e}")

    # Step 3
    print("\n[3/5] Running maintenance health check...")
    try:
        maint_result = client.run_maintenance_check()
        results["maintenance"] = maint_result
        print(f"  Task ID: {maint_result.get('taskId', 'N/A')}")
        print(f"  State: {maint_result.get('state', 'N/A')}")
    except Exception as e:
        results["maintenance"] = {"error": str(e)}
        print(f"  Error: {e}")

    # Step 4
    print("\n[4/5] Simulating financial operation...")
    try:
        fin_result = client.simulate_financial_op()
        results["financial"] = fin_result
        print(f"  Status: {fin_result.get('status', 'N/A')}")
        print(f"  Would-spend: ${fin_result.get('would_spend', 0):.2f}")
        print(f"  Approved: {fin_result.get('x-simp', {}).get('approved', False)}")
    except Exception as e:
        results["financial"] = {"error": str(e)}
        print(f"  Error: {e}")

    # Step 5
    print("\n[5/5] Fetching recent events...")
    try:
        events_result = client.fetch_events()
        results["events"] = events_result
        print(f"  Events: {events_result.get('count', 0)}")
    except Exception as e:
        results["events"] = {"error": str(e)}
        print(f"  Error: {e}")

    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SIMP A2A End-to-End Demo")
    parser.add_argument(
        "--broker-url",
        default="http://127.0.0.1:5555",
        help="SIMP broker URL (default: http://127.0.0.1:5555)",
    )
    parser.add_argument("--api-key", default="", help="API key for authenticated endpoints")
    args = parser.parse_args()

    try:
        run_demo(args.broker_url, args.api_key)
    except ConnectionError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
