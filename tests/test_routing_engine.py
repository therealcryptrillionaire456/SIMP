"""
Tests for Sprint 53 — Routing Engine

Policy-based intent routing with explicit → policy → fallback → capability resolution.
"""

import json
import os
import tempfile
import unittest

from simp.server.routing_engine import (
    RoutingDecision,
    RoutingEngine,
    RoutingPolicy,
)


def _make_agents(**kwargs):
    """Helper: build a fake registered_agents dict."""
    agents = {}
    for aid, meta in kwargs.items():
        agents[aid] = {
            "agent_id": aid,
            "agent_type": meta.get("type", "generic"),
            "endpoint": meta.get("endpoint", f"http://localhost:500{len(agents)}"),
            "metadata": meta.get("metadata", {}),
            "status": "online",
        }
    return agents


def _write_policy(path, rules):
    """Helper: write routing policy JSON to file."""
    with open(path, "w") as fh:
        json.dump({"rules": rules}, fh)


class TestRoutingPolicyDataclass(unittest.TestCase):

    def test_defaults(self):
        p = RoutingPolicy(intent_type="ping")
        assert p.intent_type == "ping"
        assert p.primary_agent == ""
        assert p.fallback_chain == []


class TestRoutingDecisionDataclass(unittest.TestCase):

    def test_fields(self):
        d = RoutingDecision(target_agent="grok:001", reason="explicit")
        assert d.target_agent == "grok:001"
        assert d.reason == "explicit"


class TestExplicitTarget(unittest.TestCase):
    """Step 1: explicit target bypasses policy."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.policy_path = os.path.join(self.tmpdir, "routing_policy.json")
        _write_policy(self.policy_path, [])
        self.engine = RoutingEngine(policy_path=self.policy_path)

    def test_explicit_target_returns_explicit(self):
        agents = _make_agents(**{"grok:001": {}})
        decision = self.engine.resolve("research", "grok:001", agents)
        assert decision.target_agent == "grok:001"
        assert decision.reason == "explicit"
        assert decision.policy_matched is False

    def test_auto_target_not_explicit(self):
        agents = _make_agents(**{"grok:001": {}})
        decision = self.engine.resolve("research", "auto", agents)
        # Should NOT be explicit
        assert decision.reason != "explicit"


class TestPolicyPrimary(unittest.TestCase):
    """Step 2: policy primary agent."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.policy_path = os.path.join(self.tmpdir, "routing_policy.json")
        _write_policy(self.policy_path, [
            {"intent_type": "research", "primary_agent": "grok:001"},
        ])
        self.engine = RoutingEngine(policy_path=self.policy_path)

    def test_policy_primary_matched(self):
        agents = _make_agents(**{"grok:001": {}})
        decision = self.engine.resolve("research", None, agents)
        assert decision.target_agent == "grok:001"
        assert decision.reason == "policy_primary"
        assert decision.policy_matched is True

    def test_policy_primary_not_registered(self):
        agents = _make_agents(**{"vision:001": {}})
        decision = self.engine.resolve("research", None, agents)
        # Primary not registered, should fall through
        assert decision.target_agent is None
        assert decision.reason == "no_route"


class TestFallbackChain(unittest.TestCase):
    """Step 3: fallback chain when primary not available."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.policy_path = os.path.join(self.tmpdir, "routing_policy.json")
        _write_policy(self.policy_path, [
            {
                "intent_type": "planning",
                "primary_agent": "reasoning:001",
                "fallback_chain": ["grok:001", "vision:001"],
            },
        ])
        self.engine = RoutingEngine(policy_path=self.policy_path)

    def test_first_fallback(self):
        agents = _make_agents(**{"grok:001": {}, "vision:001": {}})
        decision = self.engine.resolve("planning", None, agents)
        assert decision.target_agent == "grok:001"
        assert decision.reason == "fallback"

    def test_second_fallback(self):
        agents = _make_agents(**{"vision:001": {}})
        decision = self.engine.resolve("planning", None, agents)
        assert decision.target_agent == "vision:001"
        assert decision.reason == "fallback"


class TestCapabilityMatch(unittest.TestCase):
    """Step 4: capability-based routing."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.policy_path = os.path.join(self.tmpdir, "routing_policy.json")
        _write_policy(self.policy_path, [
            {
                "intent_type": "code_task",
                "primary_agent": "coder:001",
                "required_capability": "code_generation",
            },
        ])
        self.engine = RoutingEngine(policy_path=self.policy_path)

    def test_capability_match(self):
        agents = _make_agents(**{
            "flex:001": {"metadata": {"capabilities": ["code_generation", "review"]}},
        })
        decision = self.engine.resolve("code_task", None, agents)
        assert decision.target_agent == "flex:001"
        assert decision.reason == "capability_match"

    def test_no_capability_match(self):
        agents = _make_agents(**{
            "flex:001": {"metadata": {"capabilities": ["trading"]}},
        })
        decision = self.engine.resolve("code_task", None, agents)
        assert decision.target_agent is None
        assert decision.reason == "no_route"


class TestNoRoute(unittest.TestCase):
    """Step 5: no route found."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.policy_path = os.path.join(self.tmpdir, "routing_policy.json")
        _write_policy(self.policy_path, [])
        self.engine = RoutingEngine(policy_path=self.policy_path)

    def test_unknown_intent_type(self):
        agents = _make_agents(**{"a:001": {}})
        decision = self.engine.resolve("nonexistent", None, agents)
        assert decision.target_agent is None
        assert decision.reason == "no_route"

    def test_no_agents(self):
        decision = self.engine.resolve("research", None, {})
        assert decision.target_agent is None


class TestLoadPolicy(unittest.TestCase):
    """Policy loading and reloading."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.policy_path = os.path.join(self.tmpdir, "routing_policy.json")

    def test_load_from_file(self):
        _write_policy(self.policy_path, [
            {"intent_type": "ping"},
            {"intent_type": "research", "primary_agent": "g:001"},
        ])
        engine = RoutingEngine(policy_path=self.policy_path)
        summary = engine.get_policy_summary()
        assert summary["rule_count"] == 2

    def test_reload_policy(self):
        _write_policy(self.policy_path, [{"intent_type": "ping"}])
        engine = RoutingEngine(policy_path=self.policy_path)
        assert engine.get_policy_summary()["rule_count"] == 1

        # Add another rule
        _write_policy(self.policy_path, [
            {"intent_type": "ping"},
            {"intent_type": "research"},
        ])
        count = engine.reload_policy()
        assert count == 2

    def test_missing_file(self):
        engine = RoutingEngine(policy_path="/nonexistent/path.json")
        summary = engine.get_policy_summary()
        assert summary["rule_count"] == 0


class TestGetPolicySummary(unittest.TestCase):
    """get_policy_summary() returns serialisable dict."""

    def test_summary_structure(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "routing_policy.json")
        _write_policy(path, [
            {
                "intent_type": "research",
                "primary_agent": "g:001",
                "fallback_chain": ["v:001"],
                "required_capability": "research",
                "description": "Research tasks",
            },
        ])
        engine = RoutingEngine(policy_path=path)
        summary = engine.get_policy_summary()
        assert "rule_count" in summary
        assert "rules" in summary
        assert "policy_path" in summary
        rule = summary["rules"][0]
        assert rule["intent_type"] == "research"
        assert rule["primary_agent"] == "g:001"


class TestDefaultPolicyFile(unittest.TestCase):
    """The shipped routing_policy.json loads correctly."""

    def test_shipped_policy_loads(self):
        engine = RoutingEngine()
        summary = engine.get_policy_summary()
        # We ship 15 rules in docs/routing_policy.json
        assert summary["rule_count"] >= 10


if __name__ == "__main__":
    unittest.main()
