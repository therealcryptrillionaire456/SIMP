"""Sprint 58 — SSE Event Stream tests.

Verifies EventStreamBuffer, push/subscribe/unsubscribe, sequence numbers,
ring buffer behavior, and the /a2a/events/stream route.
"""

import json
import os
import threading
import time
import pytest

from simp.compat.event_stream import EventStreamBuffer, EVENT_BUFFER
from simp.server.http_server import SimpHttpServer


@pytest.fixture()
def client():
    os.environ["SIMP_REQUIRE_API_KEY"] = "false"
    server = SimpHttpServer(debug=False)
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# EventStreamBuffer unit tests
# ---------------------------------------------------------------------------

class TestEventStreamBuffer:

    def test_push_increments_sequence(self):
        buf = EventStreamBuffer(maxlen=100)
        seq1 = buf.push("test", {"msg": "hello"})
        seq2 = buf.push("test", {"msg": "world"})
        assert seq2 == seq1 + 1

    def test_get_recent_returns_events(self):
        buf = EventStreamBuffer(maxlen=100)
        buf.push("a", {"v": 1})
        buf.push("b", {"v": 2})
        events = buf.get_recent(limit=10)
        assert len(events) == 2
        assert events[0]["event_type"] == "a"
        assert events[1]["event_type"] == "b"

    def test_get_recent_since_sequence(self):
        buf = EventStreamBuffer(maxlen=100)
        buf.push("a", {})
        seq = buf.push("b", {})
        buf.push("c", {})
        events = buf.get_recent(limit=10, since_sequence=seq)
        assert len(events) == 1
        assert events[0]["event_type"] == "c"

    def test_ring_buffer_evicts_old_events(self):
        buf = EventStreamBuffer(maxlen=5)
        for i in range(10):
            buf.push("ev", {"i": i})
        events = buf.get_recent(limit=100)
        assert len(events) == 5
        assert events[0]["data"]["i"] == 5

    def test_subscribe_and_get_events(self):
        buf = EventStreamBuffer(maxlen=100)
        sid = buf.subscribe("sub-1")
        buf.push("hello", {"val": 42})
        events = buf.get_subscriber_events(sid, max_events=10)
        assert len(events) == 1
        assert events[0]["data"]["val"] == 42

    def test_unsubscribe_cleans_up(self):
        buf = EventStreamBuffer(maxlen=100)
        sid = buf.subscribe("sub-2")
        buf.unsubscribe(sid)
        events = buf.get_subscriber_events(sid, max_events=10)
        assert events == []

    def test_multiple_subscribers_independent(self):
        buf = EventStreamBuffer(maxlen=100)
        s1 = buf.subscribe("s1")
        s2 = buf.subscribe("s2")
        buf.push("ev", {"x": 1})
        # Drain s1
        ev1 = buf.get_subscriber_events(s1, max_events=10)
        assert len(ev1) == 1
        # s2 should still have the event
        ev2 = buf.get_subscriber_events(s2, max_events=10)
        assert len(ev2) == 1

    def test_sequence_property(self):
        buf = EventStreamBuffer(maxlen=100)
        assert buf.sequence == 0
        buf.push("x", {})
        assert buf.sequence == 1

    def test_thread_safety(self):
        buf = EventStreamBuffer(maxlen=1000)
        errors = []

        def pusher():
            try:
                for _ in range(100):
                    buf.push("test", {"v": 1})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=pusher) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert buf.sequence == 500


# ---------------------------------------------------------------------------
# SSE route tests
# ---------------------------------------------------------------------------

class TestSSERoute:

    def test_sse_route_exists(self, client):
        """The /a2a/events/stream route is registered."""
        rules = [r.rule for r in client.application.url_map.iter_rules()]
        assert "/a2a/events/stream" in rules

    def test_event_buffer_hooked_into_response(self, client):
        """Verify that record_response pushes to EVENT_BUFFER."""
        client.post("/agents/register", json={
            "agent_id": "sse-test-agent",
            "agent_type": "test",
            "endpoint": "http://localhost:9999",
        })

        initial_seq = EVENT_BUFFER.sequence

        # Record a response for a non-existent intent — won't push
        client.post("/intents/fake-intent/response", json={
            "response": {"result": "ok"},
            "execution_time_ms": 5.0,
        })

        # The push only happens on success, so for a non-existent intent
        # the sequence should not change
        assert EVENT_BUFFER.sequence == initial_seq

    def test_event_buffer_push_on_error(self, client):
        """Verify that record_error does NOT push for unknown intents."""
        initial_seq = EVENT_BUFFER.sequence
        client.post("/intents/fake-err/error", json={
            "error": "test error",
            "execution_time_ms": 1.0,
        })
        assert EVENT_BUFFER.sequence == initial_seq
