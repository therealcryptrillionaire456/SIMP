"""Security regression tests for HTTP auth and socket framing."""

import json
import os
import socket
import sys

from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from simp.server.agent_client import SimpAgentClient
from simp.server.control_auth import require_control_auth
from simp.server.http_server import SimpHttpServer


class FakeSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def recv(self, size):
        if not self.chunks:
            raise socket.timeout()
        return self.chunks.pop(0)


class TestHTTPServerAuth:
    def setup_method(self):
        os.environ["SIMP_REQUIRE_API_KEY"] = "true"
        os.environ["SIMP_API_KEYS"] = "test-key"
        self.server = SimpHttpServer()
        self.client = self.server.app.test_client()

    def teardown_method(self):
        os.environ.pop("SIMP_REQUIRE_API_KEY", None)
        os.environ.pop("SIMP_API_KEYS", None)

    def test_agent_lookup_requires_api_key(self):
        response = self.client.get("/agents/example")
        assert response.status_code == 401

    def test_logs_require_api_key(self):
        response = self.client.get("/logs")
        assert response.status_code == 401

    def test_record_error_requires_api_key(self):
        response = self.client.post("/intents/example/error", json={"error": "oops"})
        assert response.status_code == 401

    def test_memory_context_pack_requires_api_key(self):
        response = self.client.get("/memory/context-pack?task_id=abc")
        assert response.status_code == 401

    def test_authorized_request_reaches_handler(self):
        response = self.client.get(
            "/agents/example",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 404


class TestControlAuthReload:
    def test_control_auth_uses_latest_env_token(self):
        app = Flask(__name__)

        @app.route("/control/test", methods=["POST"])
        @require_control_auth
        def control_test():
            return {"status": "ok"}, 200

        client = app.test_client()

        os.environ["SIMP_CONTROL_TOKEN"] = "first-token"
        first = client.post(
            "/control/test",
            headers={"Authorization": "Bearer first-token"},
        )
        assert first.status_code == 200

        os.environ["SIMP_CONTROL_TOKEN"] = "second-token"
        stale = client.post(
            "/control/test",
            headers={"Authorization": "Bearer first-token"},
        )
        fresh = client.post(
            "/control/test",
            headers={"Authorization": "Bearer second-token"},
        )
        assert stale.status_code == 403
        assert fresh.status_code == 200

        os.environ.pop("SIMP_CONTROL_TOKEN", None)


class TestAgentClientFraming:
    def test_receive_partial_message_across_reads(self):
        payload = json.dumps({"status": "ok"}).encode()
        client = SimpAgentClient("agent", "worker", 5001)
        client.socket = FakeSocket([payload[:5], payload[5:] + b"\n"])

        assert client._receive_message() is None
        assert client._receive_message() == {"status": "ok"}

    def test_receive_multiple_messages_from_one_chunk(self):
        first = json.dumps({"seq": 1})
        second = json.dumps({"seq": 2})
        client = SimpAgentClient("agent", "worker", 5001)
        client.socket = FakeSocket([(first + "\n" + second + "\n").encode()])

        assert client._receive_message() == {"seq": 1}
        assert client._receive_message() == {"seq": 2}
