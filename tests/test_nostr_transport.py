"""
Tests for SIMP Nostr Transport (Sprint 75)
"""

import json
import time
import pytest

from simp.transport.nostr_transport import (
    NostrEvent,
    NostrTransport,
    KIND_AGENT_CARD,
    KIND_INTENT,
    KIND_DISCOVERY,
    KIND_ACK,
    DEFAULT_RELAYS,
)


class TestNostrEventConstants:
    def test_kind_values(self):
        assert KIND_AGENT_CARD == 30078
        assert KIND_INTENT == 4
        assert KIND_DISCOVERY == 30023
        assert KIND_ACK == 7

    def test_default_relays(self):
        assert len(DEFAULT_RELAYS) > 0
        for relay in DEFAULT_RELAYS:
            assert relay.startswith("wss://")


class TestNostrEvent:
    def test_default_values(self):
        event = NostrEvent()
        assert event.id == ""
        assert event.pubkey == ""
        assert event.kind == 1
        assert event.tags == []
        assert event.content == ""
        assert event.sig == ""

    def test_serialize_for_id(self):
        event = NostrEvent(
            pubkey="abc123",
            created_at=1000000,
            kind=1,
            tags=[["t", "simp"]],
            content="hello",
        )
        serialized = event.serialize_for_id()
        parsed = json.loads(serialized)
        assert parsed[0] == 0
        assert parsed[1] == "abc123"
        assert parsed[2] == 1000000
        assert parsed[3] == 1
        assert parsed[4] == [["t", "simp"]]
        assert parsed[5] == "hello"

    def test_compute_id(self):
        event = NostrEvent(
            pubkey="abc123",
            created_at=1000000,
            kind=1,
            content="test",
        )
        event_id = event.compute_id()
        assert len(event_id) == 64  # SHA256 hex
        assert event.id == event_id

    def test_compute_id_deterministic(self):
        e1 = NostrEvent(pubkey="x", created_at=100, kind=1, content="y")
        e2 = NostrEvent(pubkey="x", created_at=100, kind=1, content="y")
        assert e1.compute_id() == e2.compute_id()

    def test_to_dict(self):
        event = NostrEvent(
            id="abc",
            pubkey="def",
            created_at=123,
            kind=1,
            tags=[["p", "target"]],
            content="msg",
            sig="sig123",
        )
        d = event.to_dict()
        assert d["id"] == "abc"
        assert d["pubkey"] == "def"
        assert d["kind"] == 1
        assert d["content"] == "msg"

    def test_from_dict(self):
        data = {
            "id": "event-1",
            "pubkey": "pub-1",
            "created_at": 999,
            "kind": 4,
            "tags": [["t", "test"]],
            "content": "content",
            "sig": "sig",
        }
        event = NostrEvent.from_dict(data)
        assert event.id == "event-1"
        assert event.kind == 4
        assert event.content == "content"

    def test_from_dict_missing_fields(self):
        event = NostrEvent.from_dict({})
        assert event.id == ""
        assert event.kind == 1


class TestNostrTransport:
    def test_init(self):
        nt = NostrTransport(agent_id="agent-1")
        assert nt.agent_id == "agent-1"
        assert len(nt.pubkey) > 0
        assert len(nt.relays) > 0

    def test_custom_relays(self):
        nt = NostrTransport(agent_id="a", relays=["wss://custom.relay"])
        assert nt.relays == ["wss://custom.relay"]


class TestBuildAgentCardEvent:
    def test_basic_card(self):
        nt = NostrTransport(agent_id="card-agent")
        event = nt.build_agent_card_event(agent_type="trading")
        assert event.kind == KIND_AGENT_CARD
        assert event.id != ""  # ID was computed

        content = json.loads(event.content)
        assert content["agent_id"] == "card-agent"
        assert content["agent_type"] == "trading"
        assert content["protocol"] == "simp"

    def test_card_with_capabilities(self):
        nt = NostrTransport(agent_id="cap-agent")
        event = nt.build_agent_card_event(capabilities=["trade", "query"])
        content = json.loads(event.content)
        assert "trade" in content["capabilities"]

    def test_card_tags(self):
        nt = NostrTransport(agent_id="tag-agent")
        event = nt.build_agent_card_event(agent_type="vision")
        has_simp_tag = any(t[0] == "t" and t[1] == "simp" for t in event.tags)
        assert has_simp_tag
        has_d_tag = any(t[0] == "d" for t in event.tags)
        assert has_d_tag


class TestBuildIntentEvent:
    def test_basic_intent(self):
        nt = NostrTransport(agent_id="sender")
        intent = {"intent_type": "trade", "params": {"symbol": "BTC"}}
        event = nt.build_intent_event(intent)
        assert event.kind == KIND_INTENT
        assert event.id != ""

        content = json.loads(event.content)
        assert content["intent_type"] == "trade"

    def test_intent_with_target(self):
        nt = NostrTransport(agent_id="sender")
        event = nt.build_intent_event({"intent_type": "test"}, target_pubkey="target-pub")
        has_p_tag = any(t[0] == "p" and t[1] == "target-pub" for t in event.tags)
        assert has_p_tag

    def test_stats_updated(self):
        nt = NostrTransport(agent_id="stats-test")
        nt.build_intent_event({"intent_type": "t"})
        assert nt.stats["events_built"] == 1
        assert nt.stats["intents_sent"] == 1


class TestBuildDiscoveryEvent:
    def test_basic_discovery(self):
        nt = NostrTransport(agent_id="discoverer")
        event = nt.build_discovery_event(agent_type="mesh-node")
        assert event.kind == KIND_DISCOVERY

        content = json.loads(event.content)
        assert content["agent_id"] == "discoverer"
        assert content["agent_type"] == "mesh-node"


class TestEventToIntent:
    def test_valid_simp_event(self):
        nt = NostrTransport(agent_id="parser")
        intent_data = {"intent_type": "test", "params": {"key": "val"}}
        event = nt.build_intent_event(intent_data)

        recovered = nt.event_to_intent(event)
        assert recovered is not None
        assert recovered["intent_type"] == "test"
        assert "_nostr_event_id" in recovered

    def test_non_simp_event_returns_none(self):
        nt = NostrTransport(agent_id="parser")
        event = NostrEvent(
            kind=1,
            content='{"text": "not simp"}',
            tags=[["t", "general"]],
        )
        result = nt.event_to_intent(event)
        assert result is None

    def test_invalid_json_returns_none(self):
        nt = NostrTransport(agent_id="parser")
        event = NostrEvent(
            kind=4,
            content="not json at all",
            tags=[["t", "simp"]],
        )
        result = nt.event_to_intent(event)
        assert result is None


class TestNostrTransportStatus:
    def test_get_status(self):
        nt = NostrTransport(agent_id="status-agent")
        status = nt.get_status()
        assert status["agent_id"] == "status-agent"
        assert "relays" in status
        assert "stats" in status
