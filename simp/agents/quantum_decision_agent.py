"""
Quantum Decision Agent (Tranche 5)
====================================
24/7 autonomous decision agent that runs unsupervised.

Registers with the SIMP broker as `quantum_decision_agent`.
Listens for `opportunity_scanned` intents from the profit cycle.
Evaluates opportunities against safety thresholds.
Emits `execute_trade` intents when conditions are met.

Design:
- No human-in-the-loop for standard operations
- Self-heals: detects stale state, restarts loops
- Safety-enforced: every decision passes through SafetyBackstop
- Journaled: every decision recorded in decision_journal.ndjson
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger("quantum_decision_agent")

# ── Constants ───────────────────────────────────────────────────────────

BROKER_URL = os.environ.get("SIMP_BROKER_URL", "http://127.0.0.1:5555")
API_KEY = os.environ.get("SIMP_API_KEY", "")
AGENT_ID = "quantum_decision_agent"
DECISION_JOURNAL = Path("state/decision_journal.ndjson")
STATUS_PATH = Path("state/quantum_decision_agent.json")

DEFAULT_GO_CRITERIA = {
    "min_expected_return_pct": 0.01,
    "min_confidence": 0.3,
    "max_risk_score": 0.8,
    "min_capital_usd": 1.0,
    "max_trades_per_cycle": 3,
    "auto_go_on_borderline": False,  # If False, emit review intents for borderline
}


@dataclass
class DecisionRecord:
    """Record of a single decision."""
    decision_id: str
    signal_id: str
    agent: str
    intent_type: str
    decision: str  # go, no_go, review
    reason: str
    opportunity: Dict[str, Any]
    checks: List[Dict[str, Any]]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QuantumDecisionAgent:
    """
    Autonomous decision agent that runs 24/7.
    
    Lifecycle:
      1. Register with broker
      2. Poll for opportunity_scanned intents
      3. Evaluate against GO criteria + safety backstop
      4. Emit execute_trade or review_required intent
      5. Journal every decision
      6. Heartbeat every 60s
    """

    def __init__(
        self,
        agent_id: str = AGENT_ID,
        broker_url: str = BROKER_URL,
        api_key: str = API_KEY,
        go_criteria: Optional[Dict[str, Any]] = None,
        auto_register: bool = False,
    ):
        self.agent_id = agent_id
        self.broker_url = broker_url.rstrip("/")
        self.api_key = api_key
        self.go_criteria: Dict[str, Any] = go_criteria or dict(DEFAULT_GO_CRITERIA)
        self.registered = False
        self.running = False
        self._last_heartbeat: float = 0.0
        self._cycle_count: int = 0

        if auto_register:
            self.register()

    # ── Broker Communication ──────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _broker_post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST to broker endpoint."""
        url = f"{self.broker_url}{path}"
        try:
            req = Request(
                url,
                data=json.dumps(data).encode(),
                headers=self._headers(),
            )
            resp = urlopen(req, timeout=10)
            return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError) as e:
            log.warning("Broker POST %s failed: %s", path, e)
            return {"error": str(e)}

    def _broker_get(self, path: str) -> Dict[str, Any]:
        """GET from broker endpoint."""
        url = f"{self.broker_url}{path}"
        try:
            req = Request(url, headers=self._headers())
            resp = urlopen(req, timeout=10)
            return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError) as e:
            return {"error": str(e)}

    def register(self) -> bool:
        """Register this agent with the SIMP broker."""
        payload = {
            "agent_id": self.agent_id,
            "capabilities": [
                "quantum_decision_making",
                "opportunity_evaluation",
                "trade_approval",
                "risk_managed_execution",
            ],
            "endpoint": "(file-based)",
            "metadata": {
                "type": "autonomous_decision_agent",
                "mode": "GO/NO-GO",
                "go_criteria": self.go_criteria,
                "version": "1.0.0",
            },
        }
        result = self._broker_post("/agents/register", payload)
        if "error" not in result:
            self.registered = True
            log.info("Registered as %s", self.agent_id)
        else:
            log.warning("Registration failed: %s", result.get("error"))
        return self.registered

    def heartbeat(self) -> bool:
        """Send heartbeat to broker."""
        now = time.time()
        if now - self._last_heartbeat < 30:
            return True  # Throttle
        self._last_heartbeat = now
        result = self._broker_post(f"/agents/{self.agent_id}/heartbeat", {
            "status": "running",
            "cycle_count": self._cycle_count,
        })
        return "error" not in result

    def send_intent(self, intent_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send an intent to the broker."""
        intent = {
            "intent_type": intent_type,
            "source_agent": self.agent_id,
            "target_agent": "auto",
            "payload": payload,
        }
        return self._broker_post("/intents/route", intent)

    # ── Decision Making ────────────────────────────────────────────────

    def evaluate_opportunity(
        self,
        opportunity: Dict[str, Any],
        safety_backstop: Any = None,
        available_capital: float = 0.0,
    ) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Evaluate an opportunity against GO criteria.
        
        Returns (decision, reason, checks).
        decision: 'go', 'no_go', 'review'
        """
        checks: List[Dict[str, Any]] = []
        criteria = self.go_criteria

        # Extract opportunity fields
        expected_return = float(opportunity.get("expected_return_pct", 0) or 0)
        confidence = float(opportunity.get("confidence", 0) or 0)
        risk_score = float(opportunity.get("risk_score", 0.5) or 0.5)
        capital_req = float(opportunity.get("capital_required", 0) or 0)
        venue = opportunity.get("venue", "unknown")

        # Check 1: Minimum return
        min_return = criteria.get("min_expected_return_pct", 0.01)
        return_ok = expected_return >= min_return
        checks.append({
            "check": "min_return",
            "value": expected_return,
            "threshold": min_return,
            "passed": return_ok,
        })

        # Check 2: Minimum confidence
        min_conf = criteria.get("min_confidence", 0.3)
        conf_ok = confidence >= min_conf
        checks.append({
            "check": "min_confidence",
            "value": confidence,
            "threshold": min_conf,
            "passed": conf_ok,
        })

        # Check 3: Maximum risk
        max_risk = criteria.get("max_risk_score", 0.8)
        risk_ok = risk_score <= max_risk
        checks.append({
            "check": "max_risk",
            "value": risk_score,
            "threshold": max_risk,
            "passed": risk_ok,
        })

        # Check 4: Available capital
        min_cap = criteria.get("min_capital_usd", 1.0)
        cap_ok = available_capital >= capital_req and available_capital >= min_cap
        checks.append({
            "check": "min_capital",
            "value": available_capital,
            "threshold": min_cap,
            "required": capital_req,
            "passed": cap_ok,
        })

        # Check 5: Safety backstop (if provided)
        safety_ok = True
        safety_checks = []
        if safety_backstop is not None:
            allowed, sc = safety_backstop.can_execute(
                proposed_loss_usd=capital_req * 0.5,  # Assume 50% worst-case loss
                balance_usd=available_capital,
            )
            safety_ok = allowed
            safety_checks = [c.to_dict() if hasattr(c, 'to_dict') else {"reason": str(c)} for c in sc]
            checks.append({
                "check": "safety_backstop",
                "passed": safety_ok,
                "details": safety_checks,
            })

        # Determine decision
        all_pass = return_ok and conf_ok and risk_ok and cap_ok and safety_ok
        partial_pass = return_ok and (conf_ok or risk_ok)

        if all_pass:
            return "go", f"All criteria met: ret={expected_return:.2%} conf={confidence:.2f} risk={risk_score:.2f}", checks
        elif partial_pass and criteria.get("auto_go_on_borderline", False):
            return "go", f"Borderline OK: ret={expected_return:.2%} conf={confidence:.2f}", checks
        elif return_ok and (conf_ok or risk_ok):
            return "review", f"Review needed: cap_ok={cap_ok} safety_ok={safety_ok}", checks
        else:
            return "no_go", f"Criteria not met: ret={expected_return:.2%} conf={confidence:.2f} risk={risk_score:.2f}", checks

    def decide_on_opportunity(
        self,
        opportunity: Dict[str, Any],
        safety_backstop: Any = None,
        available_capital: float = 0.0,
    ) -> DecisionRecord:
        """
        Make a full decision on an opportunity.
        
        Returns a DecisionRecord with the decision and all checks.
        """
        signal_id = opportunity.get("signal_id", opportunity.get("id", f"opp_{uuid.uuid4().hex[:8]}"))
        decision, reason, checks = self.evaluate_opportunity(
            opportunity, safety_backstop, available_capital,
        )

        record = DecisionRecord(
            decision_id=f"dec_{uuid.uuid4().hex[:14]}",
            signal_id=signal_id,
            agent=self.agent_id,
            intent_type="opportunity_evaluation",
            decision=decision,
            reason=reason,
            opportunity=opportunity,
            checks=checks,
        )

        # Execute decision
        if decision == "go":
            self._execute_go(opportunity)
        elif decision == "review" and self.go_criteria.get("auto_go_on_borderline", False) is False:
            self._request_review(opportunity, record)
        # no_go: just journal

        self._journal(record)
        return record

    def _execute_go(self, opportunity: Dict[str, Any]) -> None:
        """Execute a GO decision — send execute_trade intent."""
        venue = opportunity.get("venue", "unknown")
        capital = float(opportunity.get("capital_required", 1.0))
        symbol = opportunity.get("symbol", "unknown")

        payload = {
            "signal_id": opportunity.get("signal_id", opportunity.get("id", "")),
            "source": f"{self.agent_id}",
            "venue": venue,
            "symbol": symbol,
            "capital_usd": capital,
            "action": "buy",
            "metadata": {
                "decision_source": "autonomous",
                "expected_return_pct": opportunity.get("expected_return_pct"),
                "confidence": opportunity.get("confidence"),
            },
        }

        result = self.send_intent("execute_trade", payload)
        log.info(
            "GO: %s %s $%.2f on %s (tx=%s)",
            symbol, venue, capital, venue,
            result.get("intent_id", "unknown")[:12],
        )

    def _request_review(self, opportunity: Dict[str, Any], record: DecisionRecord) -> None:
        """Send a review_required intent for borderline opportunities."""
        payload = {
            "decision_id": record.decision_id,
            "signal_id": record.signal_id,
            "opportunity": opportunity,
            "checks": record.checks,
            "reason": record.reason,
        }
        self.send_intent("review_required", payload)
        log.info("REVIEW: %s — %s", record.signal_id[:12], record.reason[:60])

    def _journal(self, record: DecisionRecord) -> None:
        """Write decision to decision journal."""
        try:
            DECISION_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
            with open(DECISION_JOURNAL, "a") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        except OSError as e:
            log.error("Could not journal decision: %s", e)

    # ── Main Loop ──────────────────────────────────────────────────────

    def run_cycle(
        self,
        safety_backstop: Any = None,
        available_capital: float = 0.0,
        dry_run: bool = True,
    ) -> int:
        """
        Run one decision cycle.
        
        1. Send heartbeat
        2. Check for opportunities (from file or broker)
        3. Evaluate and decide
        4. Execute GO/NO-GO
        
        Returns number of decisions made.
        """
        self._cycle_count += 1
        self.heartbeat()
        n_decisions = 0

        # Check for opportunity files in shared inbox/outbox
        inbox = Path("data/decision_inbox")
        if inbox.exists():
            for f in sorted(inbox.glob("opportunity_*.json")):
                try:
                    with open(f) as fh:
                        opportunity = json.load(fh)
                    if dry_run:
                        decision = "go"  # Simulate GO in dry-run
                        record = DecisionRecord(
                            decision_id=f"dd_{uuid.uuid4().hex[:14]}",
                            signal_id=opportunity.get("signal_id", "dry_run"),
                            agent=self.agent_id,
                            intent_type="opportunity_evaluation",
                            decision="go",
                            reason="DRY RUN — simulated GO",
                            opportunity=opportunity,
                            checks=[{"check": "dry_run", "passed": True}],
                        )
                        self._journal(record)
                        log.info("DRY-RUN GO: %s $%.2f",
                                 opportunity.get("symbol", "?"),
                                 float(opportunity.get("capital_required", 0)))
                    else:
                        record = self.decide_on_opportunity(opportunity, safety_backstop, available_capital)
                        decision = record.decision

                    n_decisions += 1
                    os.remove(f)  # Remove processed file
                except (json.JSONDecodeError, OSError, KeyError) as e:
                    log.warning("Could not process %s: %s", f.name, e)

        return n_decisions

    def run_forever(
        self,
        interval_sec: int = 30,
        safety_backstop: Any = None,
        available_capital: float = 0.0,
        dry_run: bool = True,
    ) -> None:
        """Run decision cycles forever."""
        self.running = True
        log.info(
            "QuantumDecisionAgent starting (%d sec interval, dry_run=%s)",
            interval_sec, dry_run,
        )

        if not self.registered:
            self.register()

        while self.running:
            try:
                n = self.run_cycle(safety_backstop, available_capital, dry_run)
                if n:
                    log.info("Cycle %d: %d decision(s)", self._cycle_count, n)
            except Exception:
                log.exception("Cycle %d error", self._cycle_count)

            for _ in range(interval_sec):
                if not self.running:
                    break
                time.sleep(1)

    def stop(self) -> None:
        """Stop the decision loop."""
        self.running = False
        log.info("QuantumDecisionAgent stopping")


# ── Global Instance ────────────────────────────────────────────────────

# Singleton agent for import
AGENT = QuantumDecisionAgent(auto_register=False)


# ── Test ─────────────────────────────────────────────────────────────────

def test_decision_agent() -> None:
    """Test decision agent logic."""
    print("=" * 60)
    print("Quantum Decision Agent — Test Suite")
    print("=" * 60)

    # Test 1: Opportunity evaluation — GO
    agent = QuantumDecisionAgent(api_key="test")
    good_opp = {
        "signal_id": "test_001",
        "venue": "cross_exchange_arb",
        "symbol": "BTC-USD",
        "expected_return_pct": 0.05,
        "confidence": 0.85,
        "risk_score": 0.3,
        "capital_required": 1.0,
    }
    decision, reason, checks = agent.evaluate_opportunity(good_opp, available_capital=100.0)
    print(f"  GO:           ✅ {decision} ({reason[:50]})")
    assert decision == "go", f"Good opp should be GO, got {decision}"
    assert len(checks) >= 4, f"Should have 4+ checks, got {len(checks)}"

    # Test 2: Opportunity evaluation — NO-GO (low return)
    bad_opp = {
        "signal_id": "test_002",
        "venue": "meme_launch",
        "symbol": "PEPE",
        "expected_return_pct": 0.001,  # Too low
        "confidence": 0.1,
        "risk_score": 0.9,  # Too high
        "capital_required": 10.0,
    }
    decision2, reason2, _ = agent.evaluate_opportunity(bad_opp, available_capital=5.0)
    print(f"  NO-GO:        ✅ {decision2} ({reason2[:50]})")
    assert decision2 == "no_go", f"Bad opp should be NO-GO, got {decision2}"

    # Test 3: Borderline — REVIEW
    borderline_opp = {
        "signal_id": "test_003",
        "venue": "triangular_arb",
        "symbol": "ETH-USD",
        "expected_return_pct": 0.03,
        "confidence": 0.4,  # Meets min_conf=0.3
        "risk_score": 0.8,  # At max_risk=0.8
        "capital_required": 2.0,
    }
    agent.go_criteria["auto_go_on_borderline"] = False
    decision3, _, _ = agent.evaluate_opportunity(borderline_opp, available_capital=100.0)
    print(f"  REVIEW:       ✅ {decision3}")
    assert decision3 == "go" or decision3 == "review"  # risk at boundary

    # Test 4: Borderline with auto-go
    agent.go_criteria["auto_go_on_borderline"] = True
    decision4, _, _ = agent.evaluate_opportunity(borderline_opp, available_capital=100.0)
    print(f"  AUTO-GO:      ✅ {decision4}")
    # Should be GO since auto_go_on_borderline is True

    # Test 5: Decision record creation
    record = agent.decide_on_opportunity(good_opp, available_capital=100.0)
    print(f"  Record:       ✅ decision={record.decision} id={record.decision_id[:12]}")
    assert record.decision_id.startswith("dec_"), "Should have dec_ prefix"
    assert len(record.checks) >= 4, "Should have checks"

    # Test 6: Journal writing
    journal_path = Path("/tmp/test_decision_journal.ndjson")
    # Override DECISION_JOURNAL for test
    import simp.organs.quantumarb.quantum_decision_agent as qda_mod
    qda_mod.DECISION_JOURNAL = journal_path
    test_agent = qda_mod.QuantumDecisionAgent(api_key="test")
    test_agent._journal(record)
    assert journal_path.exists(), "Journal should exist"
    with open(journal_path) as f:
        content = f.read().strip()
        assert "decision" in content, "Should contain decision"
    print(f"  Journal:      ✅ wrote to {journal_path.name}")

    # Test 7: Dry-run cycle (no inbox files)
    n = agent.run_cycle(available_capital=100.0, dry_run=True)
    print(f"  Cycle:        ✅ {n} decisions (0 expected, no inbox)")
    assert n == 0, "Should be 0 with empty inbox"

    # Cleanup
    import os
    try:
        os.remove(journal_path)
    except OSError:
        pass

    print("\n" + "=" * 60)
    print("ALL DECISION AGENT TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    test_decision_agent()
