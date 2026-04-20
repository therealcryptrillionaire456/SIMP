from __future__ import annotations

import json
import sqlite3

import requests

from simp.organs.ktc.api import app as app_module
from simp.organs.ktc.mesh_agent import KTCMeshAgent
from simp.organs.ktc import start_ktc


def test_mesh_agent_queues_investment_request_to_quantumarb_inbox(tmp_path):
    db_path = tmp_path / "ktc.db"
    inbox_dir = tmp_path / "quantumarb_phase4" / "inbox"
    agent = KTCMeshAgent(
        db_path=str(db_path),
        quantumarb_inbox=str(inbox_dir),
        live_execution_enabled=False,
    )

    result = agent.queue_investment_request(
        user_id="user-123",
        amount_usd=12.34,
        receipt_id="receipt-1",
        auto_approve=True,
    )

    assert result["status"] == "pending_review"
    assert result["review_required"] is True
    assert len(result["queue_paths"]) >= 1

    queued_file = inbox_dir / f"ktc_investment_{result['investment_id']}.json"
    queued_payload = json.loads(queued_file.read_text(encoding="utf-8"))
    assert queued_payload["intent_type"] == "ktc_investment_request"
    assert queued_payload["params"]["amount_usd"] == 12.34
    assert queued_payload["params"]["review_required"] is True

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT user_id, amount_usd, status FROM ktc_investments WHERE id = ?",
        (result["investment_id"],),
    ).fetchone()
    conn.close()

    assert row == ("user-123", 12.34, "pending_review")


def test_create_investment_endpoint_returns_queued_status(tmp_path):
    db_path = tmp_path / "ktc.db"
    inbox_dir = tmp_path / "quantumarb_phase4" / "inbox"
    mesh_agent = KTCMeshAgent(
        db_path=str(db_path),
        quantumarb_inbox=str(inbox_dir),
        live_execution_enabled=False,
    )
    app_module.configure_runtime(
        mesh_agent=mesh_agent,
        simp_broker_url="http://127.0.0.1:5555",
    )
    client = app_module.app.test_client()

    response = client.post(
        "/api/investments/create",
        json={
            "user_id": "user-456",
            "amount": 7.25,
            "receipt_id": "receipt-2",
            "auto_approve": True,
            "asset": "SOL",
        },
    )

    assert response.status_code == 202
    body = response.get_json()
    assert body["status"] == "accepted"
    assert body["routing"]["status"] == "pending_review"
    assert body["routing"]["amount_usd"] == 7.25

    queued_file = inbox_dir / f"ktc_investment_{body['routing']['investment_id']}.json"
    assert queued_file.exists()


def test_start_ktc_api_configures_runtime_before_start(monkeypatch):
    calls = {}

    def fake_configure_runtime(mesh_agent=None, simp_broker_url=None):
        calls["mesh_agent"] = mesh_agent
        calls["simp_broker_url"] = simp_broker_url

    def fake_start_server(host: str, port: int, debug: bool):
        calls["host"] = host
        calls["port"] = port
        calls["debug"] = debug

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self._target = target

        def start(self):
            self._target()

    class FakeResponse:
        status_code = 200

    mesh_agent = object()

    monkeypatch.setattr(app_module, "configure_runtime", fake_configure_runtime)
    monkeypatch.setattr(app_module, "start_server", fake_start_server)
    monkeypatch.setattr(start_ktc.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

    assert start_ktc.start_ktc_api(
        host="127.0.0.1",
        port=8765,
        debug=False,
        simp_url="http://broker:5555",
        mesh_agent=mesh_agent,
    )
    assert calls["mesh_agent"] is mesh_agent
    assert calls["simp_broker_url"] == "http://broker:5555"
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8765
    assert calls["debug"] is False
