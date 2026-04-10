"""
Tests for SIMP Transport Integration (Sprint 76)
"""

import json
import pytest

from simp.transport.manager import TransportManager
from simp.transport.mesh_relay import MeshRouter, MeshPeer
from simp.transport.packet import agent_id_to_peer_id
from simp.server.broker import SimpBroker, BrokerConfig


class TestTransportManager:
    def test_init_default(self):
        tm = TransportManager(agent_id="test")
        assert tm.agent_id == "test"
        assert tm.ble is not None
        assert tm.nostr is not None
        assert tm.broker is None

    def test_init_with_broker(self):
        broker = SimpBroker(BrokerConfig())
        broker.start()
        tm = TransportManager(agent_id="test", broker=broker)
        assert tm.broker is broker

    def test_init_disabled_transports(self):
        tm = TransportManager(agent_id="test", enable_ble=False, enable_nostr=False)
        assert tm.ble is None
        assert tm.nostr is None


class TestDeliveryHTTP:
    def test_deliver_http_with_broker(self):
        broker = SimpBroker(BrokerConfig())
        broker.start()
        broker.register_agent("target", "test", "localhost:5000")

        tm = TransportManager(agent_id="sender", broker=broker)
        result = tm.deliver(
            {"target_agent": "target", "intent_type": "test"},
            target_agent_id="target",
        )
        assert result["transport"] == "http"
        assert result.get("status") in ("routed", "error")

    def test_deliver_http_no_broker(self):
        tm = TransportManager(agent_id="sender", enable_ble=False, enable_nostr=False)
        result = tm.deliver({"target_agent": "x"})
        assert result["status"] == "error"
        assert result["transport"] == "http"

    def test_deliver_with_preferred_transport(self):
        broker = SimpBroker(BrokerConfig())
        broker.start()
        broker.register_agent("target", "test", "localhost:5000")

        tm = TransportManager(agent_id="sender", broker=broker)
        result = tm.deliver(
            {"target_agent": "target", "intent_type": "test"},
            target_agent_id="target",
            preferred_transport="http",
        )
        assert result["transport"] == "http"


class TestDeliveryNostr:
    def test_deliver_nostr(self):
        tm = TransportManager(agent_id="sender", enable_ble=False)
        # Force nostr by making http unavailable
        result = tm._deliver_nostr({"intent_type": "test"}, "target")
        assert result["transport"] == "nostr"
        assert result["status"] == "published"
        assert "event_id" in result

    def test_deliver_nostr_disabled(self):
        tm = TransportManager(agent_id="sender", enable_nostr=False, enable_ble=False)
        result = tm._deliver_nostr({"intent_type": "test"}, "target")
        assert result["status"] == "error"


class TestDeliveryBLE:
    def test_deliver_ble_no_peer(self):
        tm = TransportManager(agent_id="sender")
        result = tm._deliver_ble({"intent_type": "test"}, "target")
        assert result["status"] == "error"
        assert "error" in result


class TestTransportStatus:
    def test_get_status(self):
        tm = TransportManager(agent_id="status-test")
        status = tm.get_status()
        assert "transports" in status
        assert "http" in status["transports"]
        assert "ble" in status["transports"]
        assert "nostr" in status["transports"]
        assert "mesh" in status
        assert "delivery_stats" in status

    def test_get_peers_empty(self):
        tm = TransportManager(agent_id="peer-test")
        peers = tm.get_peers()
        assert peers == []

    def test_get_peers_with_peer(self):
        tm = TransportManager(agent_id="peer-test")
        peer = MeshPeer(
            peer_id=agent_id_to_peer_id("alice"),
            agent_id="alice",
            transport="http",
        )
        tm.mesh.add_peer(peer)
        peers = tm.get_peers()
        assert len(peers) == 1
        assert peers[0]["agent_id"] == "alice"


class TestDiscovery:
    def test_discover(self):
        tm = TransportManager(agent_id="discoverer")
        result = tm.discover(agent_type="mesh-node", capabilities=["trade"])
        assert "nostr" in result
        assert "mesh_packet" in result


class TestHTTPRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        server = SimpHttpServer(BrokerConfig(), debug=True)
        server.broker.start()
        server.app.config["TESTING"] = True
        with server.app.test_client() as client:
            yield client

    def test_transport_status_route(self, client):
        resp = client.get("/transport/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "transport" in data

    def test_transport_peers_route(self, client):
        resp = client.get("/transport/peers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "peers" in data

    def test_transport_discover_route(self, client):
        resp = client.post(
            "/transport/discover",
            data=json.dumps({"agent_type": "test"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "discovery" in data
