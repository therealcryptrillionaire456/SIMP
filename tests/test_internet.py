"""Tests for Internet — ProjectX web fetch and firewall interface."""

import time
import pytest
from unittest.mock import MagicMock


class TestInternetClient:
    def test_internet_client_imports(self) -> None:
        from simp.projectx.internet import InternetClient, WebRequest, WebResponse
        assert InternetClient is not None

    def test_web_request_dataclass(self) -> None:
        from simp.projectx.internet import WebRequest
        req = WebRequest(url="https://example.com", method="GET")
        assert req.url == "https://example.com"
        assert req.method == "GET"

    def test_web_request_with_headers(self) -> None:
        from simp.projectx.internet import WebRequest
        req = WebRequest(url="https://example.com", headers={"Authorization": "Bearer token"})
        assert "Authorization" in req.headers

    def test_web_request_post_method(self) -> None:
        from simp.projectx.internet import WebRequest
        req = WebRequest(url="https://example.com/api", method="POST", body={"key": "value"})
        assert req.method == "POST"
        assert req.body == {"key": "value"}

    def test_web_response_dataclass(self) -> None:
        from simp.projectx.internet import WebResponse
        resp = WebResponse(
            url="https://example.com",
            status_code=200,
            headers={},
            text="OK",
            elapsed_ms=45,
        )
        assert resp.status_code == 200
        assert resp.text == "OK"

    def test_internet_client_blocks_in_ci(self) -> None:
        from simp.projectx.internet import get_internet_client
        import socket
        original = socket.getaddrinfo
        def blocked(*args, **kwargs):
            raise socket.gaierror("Network unavailable")
        socket.getaddrinfo = blocked
        try:
            client = get_internet_client()
            assert client is not None
        finally:
            socket.getaddrinfo = original


class TestRateLimiter:
    def test_rate_limiter_initialization(self) -> None:
        from simp.projectx.internet import RateLimiter
        limiter = RateLimiter()
        assert limiter is not None
        assert hasattr(limiter, "check")


class TestSecurityFirewall:
    def test_security_firewall_instance(self) -> None:
        from simp.projectx.internet import SecurityFirewall
        fw = SecurityFirewall()
        assert fw is not None

    def test_security_firewall_has_public_methods(self) -> None:
        from simp.projectx.internet import SecurityFirewall
        fw = SecurityFirewall()
        public = [m for m in dir(fw) if not m.startswith("_") and callable(getattr(fw, m))]
        assert len(public) > 0
