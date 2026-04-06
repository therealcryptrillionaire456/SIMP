"""
SIMP A2A ProjectX Diagnostics — Sprint S6 (Sprint 36) tests.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from simp.compat.projectx_diagnostics import (
    DiagnosticStatus,
    check_task_ledger_integrity,
    check_protocol_facts_integrity,
    build_projectx_health_report,
)


class TestTaskLedgerIntegrity:
    def test_valid_jsonl(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"intent_id": "i1", "timestamp": "2026-01-01T00:00:00Z"}\n')
            f.write('{"intent_id": "i2", "timestamp": "2026-01-02T00:00:00Z"}\n')
            path = f.name
        try:
            result = check_task_ledger_integrity(path)
            assert result["status"] == DiagnosticStatus.OK
            assert result["total_lines"] == 2
            assert result["valid_lines"] == 2
            assert result["corrupt_lines"] == 0
        finally:
            os.unlink(path)

    def test_corrupt_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"ok": true}\n')
            f.write('NOT JSON\n')
            f.write('{"ok": true}\n')
            path = f.name
        try:
            result = check_task_ledger_integrity(path)
            assert result["status"] == DiagnosticStatus.DEGRADED
            assert result["corrupt_lines"] == 1
            assert 2 in result["corrupt_line_numbers"]
        finally:
            os.unlink(path)

    def test_missing_file(self):
        result = check_task_ledger_integrity("/nonexistent/path/ledger.jsonl")
        assert result["status"] == DiagnosticStatus.ERROR

    def test_never_logs_corrupt_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('SECRET_TOKEN_12345\n')
            path = f.name
        try:
            with patch("simp.compat.projectx_diagnostics.logger") as mock_logger:
                result = check_task_ledger_integrity(path)
                # Ensure corrupt line content was never logged
                for call_args in mock_logger.method_calls:
                    for arg in call_args.args:
                        if isinstance(arg, str):
                            assert "SECRET_TOKEN_12345" not in arg
        finally:
            os.unlink(path)


class TestProtocolFactsIntegrity:
    def test_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key1": "val1", "key2": "val2"}, f)
            path = f.name
        try:
            result = check_protocol_facts_integrity(path)
            assert result["status"] == DiagnosticStatus.OK
            assert result["key_count"] == 2
        finally:
            os.unlink(path)

    def test_missing_file(self):
        result = check_protocol_facts_integrity("/nonexistent/facts.json")
        assert result["status"] == DiagnosticStatus.UNKNOWN


class TestProjectXHealthReport:
    def test_returns_required_keys(self):
        mock_broker = MagicMock()
        mock_broker.agents = {}
        report = build_projectx_health_report(mock_broker)
        assert "status" in report
        assert "agent_registered" in report
        assert "agent_endpoint_reachable" in report
        assert "task_ledger" in report
        assert "protocol_facts" in report
        assert "timestamp" in report

    def test_no_file_paths_in_report(self):
        mock_broker = MagicMock()
        mock_broker.agents = {}
        report = build_projectx_health_report(mock_broker)
        raw = str(report)
        assert "/Users/" not in raw

    def test_broker_error_returns_200_shape(self):
        """Even with a broken broker, should not crash."""
        report = build_projectx_health_report(None)
        assert "status" in report


class TestProjectXHealthRoute:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_health_endpoint_returns_json(self, client):
        resp = client.get("/a2a/agents/projectx/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "status" in data
