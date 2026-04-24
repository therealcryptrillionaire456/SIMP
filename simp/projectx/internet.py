"""
ProjectX Internet Integration Layer — Phase 1

Provides safe, auditable web access and API integration for agents.
All requests are rate-limited, logged, and filtered through the
security firewall before being returned to callers.

Registered as ACTION_TIERS tier-0 (read-only) and tier-1 (POST/auth).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Domains blocked outright — extend as needed
_BLOCKED_DOMAINS = frozenset({
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",  # AWS metadata
})

# Per-domain request budget (requests / 60 s)
_DEFAULT_RATE_LIMIT = 10
_DOMAIN_RATE_LIMITS: Dict[str, int] = {
    "api.openai.com": 20,
    "api.anthropic.com": 20,
}


@dataclass
class WebRequest:
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)
    body: Optional[Any] = None
    timeout: int = 15
    allow_redirects: bool = True


@dataclass
class WebResponse:
    url: str
    status_code: int
    headers: Dict[str, str]
    text: str
    elapsed_ms: int
    cached: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> Any:
        return json.loads(self.text)


class RateLimiter:
    """Token-bucket per-domain rate limiter."""

    def __init__(self) -> None:
        self._buckets: Dict[str, List[float]] = {}

    def check(self, domain: str) -> bool:
        limit = _DOMAIN_RATE_LIMITS.get(domain, _DEFAULT_RATE_LIMIT)
        now = time.time()
        window = self._buckets.setdefault(domain, [])
        # Drop timestamps older than 60 s
        self._buckets[domain] = [t for t in window if now - t < 60]
        if len(self._buckets[domain]) >= limit:
            return False
        self._buckets[domain].append(now)
        return True


class SecurityFirewall:
    """Validates URLs and response content before returning to callers."""

    @staticmethod
    def validate_url(url: str) -> Optional[str]:
        """Return None if URL is safe, otherwise return a rejection reason."""
        try:
            parsed = urlparse(url)
        except Exception:
            return "Malformed URL"
        if parsed.scheme not in ("http", "https"):
            return f"Scheme '{parsed.scheme}' not allowed"
        host = parsed.hostname or ""
        if not host:
            return "Missing host"
        if host in _BLOCKED_DOMAINS:
            return f"Domain '{host}' is blocked"
        # Reject bare IP literals (covers IPv4 private + IPv6 loopback/link-local)
        import ipaddress
        try:
            ip = ipaddress.ip_address(host)
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_multicast or ip.is_unspecified
                    or ip.is_reserved):
                return f"Address '{host}' is not publicly routable"
            # Reject IPv4-mapped IPv6 that encode private ranges (::ffff:192.168.x.x)
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                mapped = ip.ipv4_mapped
                if mapped.is_private or mapped.is_loopback:
                    return f"IPv4-mapped IPv6 '{host}' routes to private address"
        except ValueError:
            pass  # hostname — DNS check happens at request time in _check_resolved_ip
        return None

    @staticmethod
    def check_resolved_ip(host: str) -> Optional[str]:
        """
        Resolve hostname to IP(s) and verify none are private.

        Called just before each outbound request to defeat DNS rebinding:
        the attacker controls a hostname that returns a public IP during
        validation but a private IP when the actual TCP connection is made.
        We re-resolve immediately before connecting.
        """
        import ipaddress
        import socket
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return f"DNS resolution failed for '{host}'"
        for info in infos:
            addr_str = info[4][0]
            try:
                ip = ipaddress.ip_address(addr_str)
                if (ip.is_private or ip.is_loopback or ip.is_link_local
                        or ip.is_multicast or ip.is_unspecified
                        or ip.is_reserved):
                    return f"DNS '{host}' resolved to non-public address '{addr_str}'"
                if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                    mapped = ip.ipv4_mapped
                    if mapped.is_private or mapped.is_loopback:
                        return f"DNS '{host}' resolved to IPv4-mapped private '{addr_str}'"
            except ValueError:
                pass
        return None

    @staticmethod
    def sanitise_response(text: str, max_bytes: int = 512_000) -> str:
        """Truncate oversized responses; strip null bytes and control characters."""
        if len(text) > max_bytes:
            text = text[:max_bytes] + "\n[TRUNCATED]"
        # Remove null bytes and dangerous control characters
        text = text.replace("\x00", "")
        return text


class InternetClient:
    """
    Safe web client for ProjectX agents.

    Usage::

        client = InternetClient()
        resp = client.fetch("https://api.example.com/data")
        if resp.ok:
            data = resp.json()
    """

    def __init__(
        self,
        cache_ttl: int = 300,
        user_agent: str = "ProjectX/1.0 (SIMP autonomous agent)",
    ) -> None:
        self._rate_limiter = RateLimiter()
        self._firewall = SecurityFirewall()
        self._cache: Dict[str, tuple[float, WebResponse]] = {}
        self._cache_ttl = cache_ttl
        self._user_agent = user_agent
        self._request_log: List[Dict[str, Any]] = []

    # ── Public API ────────────────────────────────────────────────────────

    def fetch(self, url: str, **kwargs) -> WebResponse:
        """GET a URL and return a WebResponse."""
        return self._request(WebRequest(url=url, method="GET", **kwargs))

    def post(self, url: str, body: Any = None, **kwargs) -> WebResponse:
        """POST to a URL and return a WebResponse."""
        return self._request(WebRequest(url=url, method="POST", body=body, **kwargs))

    def stream_fetch(self, url: str, chunk_size: int = 4096):
        """Generator that yields chunks of a streamed response."""
        rejection = self._firewall.validate_url(url)
        if rejection:
            raise ValueError(f"Blocked: {rejection}")
        import requests
        try:
            with requests.get(url, stream=True, timeout=30,
                              headers={"User-Agent": self._user_agent}) as resp:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        yield chunk
        except Exception as exc:
            logger.warning("stream_fetch failed for %s: %s", url, exc)
            raise

    def scrape_text(self, url: str) -> str:
        """Fetch a page and extract plain text (strips HTML tags)."""
        resp = self.fetch(url)
        if not resp.ok:
            return ""
        return self._strip_html(resp.text)

    # ── Internal ──────────────────────────────────────────────────────────

    def _request(self, req: WebRequest) -> WebResponse:
        import requests as _requests

        # Static URL validation (scheme, literal IPs)
        rejection = self._firewall.validate_url(req.url)
        if rejection:
            return WebResponse(
                url=req.url, status_code=403, headers={},
                text="", elapsed_ms=0, error=rejection,
            )

        domain = urlparse(req.url).hostname or ""

        # DNS-rebinding protection — resolve and verify at request time
        dns_rejection = self._firewall.check_resolved_ip(domain)
        if dns_rejection:
            return WebResponse(
                url=req.url, status_code=403, headers={},
                text="", elapsed_ms=0, error=dns_rejection,
            )

        # Cache check (GET only)
        if req.method == "GET":
            cache_key = self._cache_key(req)
            cached = self._cache.get(cache_key)
            if cached and (time.time() - cached[0]) < self._cache_ttl:
                resp = cached[1]
                resp.cached = True
                return resp

        # Rate limit
        if not self._rate_limiter.check(domain):
            return WebResponse(
                url=req.url, status_code=429, headers={},
                text="", elapsed_ms=0, error="Rate limit exceeded",
            )

        # Circuit breaker — trip after 5 failures on this domain
        try:
            from simp.projectx.hardening import get_circuit_breaker
            cb = get_circuit_breaker(f"http:{domain}")
        except ImportError:
            cb = None

        headers = {"User-Agent": self._user_agent, **req.headers}
        t0 = time.time()

        def _do_request():
            return _requests.request(
                method=req.method,
                url=req.url,
                headers=headers,
                params=req.params,
                json=req.body if isinstance(req.body, (dict, list)) else None,
                data=req.body if isinstance(req.body, (str, bytes)) else None,
                timeout=req.timeout,
                allow_redirects=False,   # never follow redirects blindly
            )

        try:
            if cb:
                from simp.projectx.hardening import CircuitBreakerOpen
                try:
                    http_resp = cb.call(_do_request)
                except CircuitBreakerOpen as exc:
                    return WebResponse(
                        url=req.url, status_code=503, headers={},
                        text="", elapsed_ms=0, error=str(exc),
                    )
            else:
                http_resp = _do_request()

            # Reject redirects to private addresses
            if http_resp.status_code in (301, 302, 303, 307, 308):
                location = http_resp.headers.get("Location", "")
                redir_rejection = self._firewall.validate_url(location) if location else None
                if redir_rejection:
                    elapsed = int((time.time() - t0) * 1000)
                    return WebResponse(
                        url=req.url, status_code=403, headers={},
                        text="", elapsed_ms=elapsed,
                        error=f"Redirect blocked: {redir_rejection}",
                    )
                if req.allow_redirects and location:
                    http_resp = _do_request()   # one manual redirect only

            elapsed = int((time.time() - t0) * 1000)
            text = self._firewall.sanitise_response(http_resp.text)
            response = WebResponse(
                url=req.url,
                status_code=http_resp.status_code,
                headers=dict(http_resp.headers),
                text=text,
                elapsed_ms=elapsed,
            )
        except Exception as exc:
            elapsed = int((time.time() - t0) * 1000)
            response = WebResponse(
                url=req.url, status_code=0, headers={},
                text="", elapsed_ms=elapsed, error=str(exc),
            )

        # Store in cache
        if req.method == "GET" and response.ok:
            self._cache[self._cache_key(req)] = (time.time(), response)

        self._log_request(req, response)
        return response

    @staticmethod
    def _cache_key(req: WebRequest) -> str:
        key = req.url + json.dumps(req.params, sort_keys=True)
        return hashlib.md5(key.encode()).hexdigest()

    def _log_request(self, req: WebRequest, resp: WebResponse) -> None:
        self._request_log.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": req.method,
            "url": req.url,
            "status": resp.status_code,
            "elapsed_ms": resp.elapsed_ms,
            "cached": resp.cached,
            "error": resp.error,
        })
        # Keep last 500 entries in memory
        if len(self._request_log) > 500:
            self._request_log = self._request_log[-500:]

    def get_log(self) -> List[Dict[str, Any]]:
        return list(self._request_log)

    @staticmethod
    def _strip_html(html: str) -> str:
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


# Module-level singleton
_client: Optional[InternetClient] = None


def get_internet_client() -> InternetClient:
    global _client
    if _client is None:
        _client = InternetClient()
    return _client
