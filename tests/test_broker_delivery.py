"""
Tests for Sprint 51 — Intent Delivery Engine

All HTTP delivery is mocked via unittest.mock.patch on urllib.request.urlopen.
"""

import io
import json
import time
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

from simp.server.delivery import (
    DeliveryConfig,
    DeliveryResult,
    DeliveryStatus,
    IntentDeliveryEngine,
    DEFAULT_DELIVERY_ENGINE,
)


class TestDeliveryStatus(unittest.TestCase):
    """DeliveryStatus constants are available."""

    def test_delivered(self):
        assert DeliveryStatus.DELIVERED == "delivered"

    def test_file_based_skip(self):
        assert DeliveryStatus.FILE_BASED_SKIP == "file_based_skip"

    def test_failed_timeout(self):
        assert DeliveryStatus.FAILED_TIMEOUT == "failed_timeout"

    def test_failed_http(self):
        assert DeliveryStatus.FAILED_HTTP == "failed_http"

    def test_failed_connection(self):
        assert DeliveryStatus.FAILED_CONNECTION == "failed_connection"

    def test_failed_invalid_endpoint(self):
        assert DeliveryStatus.FAILED_INVALID_ENDPOINT == "failed_invalid_endpoint"


class TestDeliveryConfig(unittest.TestCase):
    """DeliveryConfig defaults."""

    def test_defaults(self):
        cfg = DeliveryConfig()
        assert cfg.max_attempts == 3
        assert cfg.base_backoff_s == 1.0
        assert cfg.timeout_s == 10.0
        assert cfg.max_response_body == 500


class TestIsFileBased(unittest.TestCase):
    """IntentDeliveryEngine.is_file_based()."""

    def test_empty_endpoint(self):
        assert IntentDeliveryEngine.is_file_based("") is True

    def test_file_based_marker(self):
        assert IntentDeliveryEngine.is_file_based("agent:001 (file-based)") is True

    def test_non_http_endpoint(self):
        assert IntentDeliveryEngine.is_file_based("ipc://agent.sock") is True

    def test_http_endpoint(self):
        assert IntentDeliveryEngine.is_file_based("http://localhost:5001") is False

    def test_https_endpoint(self):
        assert IntentDeliveryEngine.is_file_based("https://agent.example.com") is False


class TestDeliverFileBased(unittest.TestCase):
    """File-based agents never get HTTP delivery."""

    def test_file_based_returns_skip(self):
        engine = IntentDeliveryEngine()
        result = engine.deliver("agent:001 (file-based)", {"intent_id": "i1"})
        assert result.status == DeliveryStatus.FILE_BASED_SKIP
        assert result.attempts == 0

    def test_non_http_returns_skip(self):
        engine = IntentDeliveryEngine()
        result = engine.deliver("ipc://test.sock", {"intent_id": "i2"})
        assert result.status == DeliveryStatus.FILE_BASED_SKIP


class TestDeliverHTTPSuccess(unittest.TestCase):
    """Successful HTTP delivery with mocked urllib."""

    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_successful_delivery(self, mock_urlopen):
        resp_body = json.dumps({"ok": True}).encode()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = resp_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        engine = IntentDeliveryEngine()
        result = engine.deliver("http://localhost:5001", {"intent_id": "i3"})

        assert result.status == DeliveryStatus.DELIVERED
        assert result.attempts == 1
        assert result.http_status == 200
        assert "ok" in result.response_body
        mock_urlopen.assert_called_once()

    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_response_body_truncated(self, mock_urlopen):
        long_body = ("x" * 1000).encode()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = long_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        engine = IntentDeliveryEngine()
        result = engine.deliver("http://localhost:5001", {"intent_id": "i4"})

        assert len(result.response_body) <= 500


class TestDeliverHTTPError(unittest.TestCase):
    """4xx/5xx errors fail immediately without retry."""

    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_http_404_no_retry(self, mock_urlopen):
        exc = urllib.error.HTTPError(
            url="http://localhost:5001/intent",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b"not found"),
        )
        mock_urlopen.side_effect = exc

        engine = IntentDeliveryEngine()
        result = engine.deliver("http://localhost:5001", {"intent_id": "i5"})

        assert result.status == DeliveryStatus.FAILED_HTTP
        assert result.http_status == 404
        assert result.attempts == 1
        # Should NOT retry on HTTP errors
        assert mock_urlopen.call_count == 1

    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_http_500_no_retry(self, mock_urlopen):
        exc = urllib.error.HTTPError(
            url="http://localhost:5001/intent",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=io.BytesIO(b"error"),
        )
        mock_urlopen.side_effect = exc

        engine = IntentDeliveryEngine()
        result = engine.deliver("http://localhost:5001", {"intent_id": "i6"})

        assert result.status == DeliveryStatus.FAILED_HTTP
        assert result.http_status == 500
        assert mock_urlopen.call_count == 1


class TestDeliverConnectionError(unittest.TestCase):
    """Connection errors retry with backoff."""

    @patch("simp.server.delivery.time.sleep")
    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_connection_retry_exhausted(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        engine = IntentDeliveryEngine(DeliveryConfig(max_attempts=3, base_backoff_s=0.01))
        result = engine.deliver("http://localhost:5001", {"intent_id": "i7"})

        assert result.status == DeliveryStatus.FAILED_CONNECTION
        assert result.attempts == 3
        assert mock_urlopen.call_count == 3
        # Should have slept twice (after attempt 1 and 2, not after 3)
        assert mock_sleep.call_count == 2

    @patch("simp.server.delivery.time.sleep")
    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_connection_retry_then_success(self, mock_urlopen, mock_sleep):
        # First call fails, second succeeds
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            urllib.error.URLError("Connection refused"),
            mock_resp,
        ]

        engine = IntentDeliveryEngine(DeliveryConfig(max_attempts=3, base_backoff_s=0.01))
        result = engine.deliver("http://localhost:5001", {"intent_id": "i8"})

        assert result.status == DeliveryStatus.DELIVERED
        assert result.attempts == 2


class TestDeliverTimeout(unittest.TestCase):
    """Timeout errors fail immediately."""

    @patch("simp.server.delivery.urllib.request.urlopen")
    def test_timeout_no_retry(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")

        engine = IntentDeliveryEngine()
        result = engine.deliver("http://localhost:5001", {"intent_id": "i9"})

        assert result.status == DeliveryStatus.FAILED_TIMEOUT
        assert result.attempts == 1
        assert mock_urlopen.call_count == 1


class TestDefaultSingleton(unittest.TestCase):
    """Module-level singleton is available."""

    def test_singleton_exists(self):
        assert DEFAULT_DELIVERY_ENGINE is not None
        assert isinstance(DEFAULT_DELIVERY_ENGINE, IntentDeliveryEngine)


class TestDeliveryElapsed(unittest.TestCase):
    """elapsed_ms is always populated."""

    def test_file_based_has_elapsed(self):
        engine = IntentDeliveryEngine()
        result = engine.deliver("(file-based)", {"intent_id": "t1"})
        assert result.elapsed_ms >= 0


if __name__ == "__main__":
    unittest.main()
