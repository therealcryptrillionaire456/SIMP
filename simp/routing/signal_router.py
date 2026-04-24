"""
SIMP Multi-Platform Signal Router
==================================

Single entry point that takes one signal and dispatches it to every configured
platform simultaneously — Coinbase spot, Kalshi prediction market hedge,
Alpaca equities hedge — then aggregates results.

Architecture
------------
RouterSignal (unified format)
        │
        ▼
  OrganRegistry          — discovers which platforms have valid credentials
        │
        ▼
  SignalNormalizer        — translates one signal → per-platform params
        │
     ┌──┴──────────────────────┐
     ▼                         ▼                         ▼
CoinbaseLiveOrgan      KalshiLiveOrgan          AlpacaLiveOrgan
(spot buy/sell)        (prediction hedge)       (equities hedge)
     │                         │                         │
     └──────────┬──────────────┘
                ▼
         RouterResult
   (aggregated, written to router_journal.jsonl)

Hedge Logic
-----------
Coinbase buys BTC/ETH/SOL  →  Kalshi YES on price-above-X  (amplify upside)
Coinbase buys crypto       →  Alpaca buys BITO/GBTC/ETHE   (equities mirror)

If Kalshi or Alpaca credentials are absent the platform is silently skipped —
it will activate automatically the moment keys land in .env.

Usage
-----
    from simp.routing.signal_router import MultiPlatformRouter

    router = MultiPlatformRouter()
    result = await router.route(signal_dict)

    # Or from a sync context:
    import asyncio
    result = asyncio.run(router.route(signal_dict))

Configuration (env vars)
------------------------
All platform auth pulled from .env automatically.
    COINBASE_API_KEY_NAME / COINBASE_API_PRIVATE_KEY  — already working
    KALSHI_API_KEY_ID + KALSHI_PRIVATE_KEY             — enables Kalshi organ
    ALPACA_API_KEY + ALPACA_SECRET_KEY                 — enables Alpaca organ
    SIMP_ROUTER_DRY_RUN=true                           — log only, no live orders
    SIMP_HEDGE_KALSHI=true                             — enable Kalshi hedging
    SIMP_HEDGE_ALPACA=true                             — enable Alpaca equities mirror
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("simp.routing.signal_router")

REPO = Path(__file__).resolve().parents[2]
ROUTER_JOURNAL = REPO / "data" / "router_journal.jsonl"

# ---------------------------------------------------------------------------
# Platform enum
# ---------------------------------------------------------------------------

class Platform(str, Enum):
    COINBASE   = "coinbase"
    KALSHI     = "kalshi"
    ALPACA     = "alpaca"
    SOLANA     = "solana"


# ---------------------------------------------------------------------------
# Unified signal / result shapes
# ---------------------------------------------------------------------------

@dataclass
class RouterSignal:
    """
    Normalised inbound signal. Accepts the quantum_signal_bridge format or
    any dict with an 'assets' key.
    """
    signal_id: str
    source: str
    assets: Dict[str, Dict[str, Any]]   # {"BTC-USD": {"action":"buy","position_usd":4.0}}
    quality_score: float = 0.5
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "RouterSignal":
        assets = d.get("assets", {})
        meta   = d.get("metadata", {})
        return cls(
            signal_id     = d.get("signal_id", str(uuid.uuid4())),
            source        = d.get("source", "unknown"),
            assets        = assets,
            quality_score = float(meta.get("quality_score", 0.5)),
            raw           = d,
        )


@dataclass
class PlatformResult:
    platform: Platform
    status: str                          # "ok" | "skipped" | "error" | "blocked"
    executions: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str]  = None
    latency_ms: float     = 0.0


@dataclass
class RouterResult:
    router_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = ""
    routed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    platforms: List[PlatformResult] = field(default_factory=list)
    total_usd_deployed: float = 0.0
    dry_run: bool = False

    def summary(self) -> str:
        lines = [f"Router {self.router_id[:8]}  signal={self.signal_id[:8]}  dry_run={self.dry_run}"]
        for p in self.platforms:
            execs = len(p.executions)
            lines.append(f"  {p.platform.value:<12} {p.status:<8}  executions={execs}  {p.error or ''}")
        lines.append(f"  Total USD deployed: ${self.total_usd_deployed:.2f}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------

def _env(*names: str) -> str:
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return ""


def _load_env_file(path: str = ".env") -> Dict[str, str]:
    """Parse .env handling multi-line PEM keys."""
    result: Dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return result
    current_key: Optional[str] = None
    current_val: List[str] = []
    in_multi = False
    for raw in p.read_text(errors="replace").splitlines():
        line = raw.rstrip()
        if in_multi:
            current_val.append(line)
            if line.startswith("-----END"):
                result[current_key] = "\n".join(current_val)
                current_key = None; current_val = []; in_multi = False
            continue
        if not line or line.startswith("#"):
            continue
        if "=" in line and not line.startswith(" "):
            k, _, v = line.partition("=")
            k = k.strip(); v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            if v.startswith("-----BEGIN"):
                current_key = k; current_val = [v]; in_multi = True
            else:
                result[k] = v
    return result


_ENV_CACHE: Optional[Dict[str, str]] = None

def _env_or_file(*names: str) -> str:
    """Check os.environ first, then .env file."""
    global _ENV_CACHE
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    if _ENV_CACHE is None:
        _ENV_CACHE = _load_env_file(str(REPO / ".env"))
    for n in names:
        v = _ENV_CACHE.get(n, "").strip()
        if v:
            return v
    return ""


# ---------------------------------------------------------------------------
# Live organ: Coinbase
# ---------------------------------------------------------------------------

class CoinbaseLiveOrgan:
    """
    Executes spot market orders on Coinbase Advanced Trade.
    Wraps the same RESTClient used by gate4_inbox_consumer.
    """

    PLATFORM = Platform.COINBASE
    FEE_RATE  = 0.006   # conservative taker estimate

    def __init__(self, dry_run: bool = False):
        self.dry_run   = dry_run
        self._client   = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        key_name = _env_or_file("COINBASE_API_KEY_NAME")
        priv_key = _env_or_file("COINBASE_API_PRIVATE_KEY")
        if not key_name or not priv_key:
            log.warning("CoinbaseLiveOrgan: credentials not found, platform unavailable")
            return
        try:
            from coinbase.rest import RESTClient  # type: ignore
            self._client   = RESTClient(api_key=key_name, api_secret=priv_key)
            self._available = True
            log.info("CoinbaseLiveOrgan: ready (dry_run=%s)", self.dry_run)
        except ImportError:
            log.warning("coinbase-advanced-py not installed")
        except Exception as e:
            log.warning("CoinbaseLiveOrgan init error: %s", e)

    @property
    def available(self) -> bool:
        return self._available

    def _spot_price(self, symbol: str) -> float:
        if not self._client:
            return 0.0
        try:
            pb = self._client.get_best_bid_ask(product_ids=[symbol])
            books = pb.get("pricebooks", []) if isinstance(pb, dict) else []
            if books:
                bids = books[0].get("bids", [])
                asks = books[0].get("asks", [])
                if bids and asks:
                    return (float(bids[0]["price"]) + float(asks[0]["price"])) / 2
        except Exception:
            pass
        return 0.0

    async def execute(self, signal: RouterSignal) -> PlatformResult:
        t0 = time.monotonic()
        result = PlatformResult(platform=self.PLATFORM, status="ok")

        for symbol, leg in signal.assets.items():
            action  = leg.get("action", "").lower()
            usd_amt = float(leg.get("position_usd", 0) or 0)
            if not usd_amt or action not in ("buy", "sell"):
                continue

            # Policy gate
            try:
                from simp.policies.trading_policy import check_trade_allowed, PolicyViolation
                check_trade_allowed(exchange="coinbase", size_usd=usd_amt)
            except Exception as pv:
                result.executions.append({
                    "symbol": symbol, "action": action, "usd": usd_amt,
                    "status": "policy_blocked", "error": str(pv)[:120]
                })
                continue

            cid  = f"router-{signal.signal_id[:8]}-{symbol}-{uuid.uuid4().hex[:6]}"
            px   = self._spot_price(symbol)
            exec_rec: Dict[str, Any] = {
                "symbol": symbol, "action": action, "usd": usd_amt,
                "market_price": px, "client_order_id": cid,
            }

            if self.dry_run or not self._client:
                exec_rec["status"] = "dry_run"
                log.info("[DRY-RUN] Coinbase %s %s $%.2f", action.upper(), symbol, usd_amt)
            else:
                try:
                    if action == "buy":
                        resp = self._client.market_order_buy(
                            client_order_id=cid,
                            product_id=symbol,
                            quote_size=str(usd_amt),
                        )
                    else:
                        base_currency = symbol.split("-")[0]
                        qty = usd_amt / px if px else 0
                        resp = self._client.market_order_sell(
                            client_order_id=cid,
                            product_id=symbol,
                            base_size=f"{qty:.8f}",
                        )
                    success = getattr(resp, "success", None)
                    if success is None and isinstance(resp, dict):
                        success = resp.get("success", False)
                    exec_rec["status"] = "ok" if success else "failed"
                    exec_rec["order_id"] = str(
                        getattr(getattr(resp, "success_response", None), "order_id", "")
                        or (resp.get("success_response", {}) or {}).get("order_id", "")
                    )
                    if not success:
                        err = getattr(getattr(resp, "error_response", None), "error", "")
                        exec_rec["error"] = err or "unknown"
                        result.status = "partial"
                except Exception as e:
                    exec_rec["status"] = "error"
                    exec_rec["error"]  = str(e)[:120]
                    result.status = "partial"

            result.executions.append(exec_rec)

        result.latency_ms = (time.monotonic() - t0) * 1000
        if not result.executions:
            result.status = "skipped"
        return result


# ---------------------------------------------------------------------------
# Live organ: Kalshi (prediction market hedge)
# ---------------------------------------------------------------------------

class KalshiLiveOrgan:
    """
    Hedges crypto positions on Kalshi prediction markets.

    Hedge logic:
        BUY  BTC/ETH/SOL  →  buy YES contract on price-above-X
        SELL BTC/ETH/SOL  →  buy NO  contract on price-above-X

    When credentials are not yet configured the organ silently marks itself
    unavailable — it activates automatically once KALSHI_API_KEY_ID and
    KALSHI_PRIVATE_KEY land in .env.
    """

    PLATFORM = Platform.KALSHI
    BASE_URL  = "https://trading-api.kalshi.com/trade-api/v2"

    # Maps crypto ticker → Kalshi series prefix for price-range contracts
    # These are approximate; live series lookup is done in _find_contract()
    CRYPTO_SERIES = {
        "BTC": "KXBTC",
        "ETH": "KXETH",
        "SOL": "KXSOL",
    }

    def __init__(self, dry_run: bool = False):
        self.dry_run    = dry_run
        self._key_id    = _env_or_file("KALSHI_API_KEY_ID")
        raw_key         = _env_or_file(
            "KALSHI_PRIVATE_KEY", "KALSHI_PRODUCTION_PRIVATE_KEY"
        )
        # Support file-path keys (path to PEM file) vs inline PEM
        if raw_key and not raw_key.startswith("-----"):
            key_path = os.path.expanduser(raw_key)
            if os.path.isfile(key_path):
                with open(key_path) as _kf:
                    self._priv_key = _kf.read().strip()
                log.info("KalshiLiveOrgan: loaded key from %s", key_path)
            else:
                self._priv_key = raw_key
                log.warning("KalshiLiveOrgan: key path %s not found", key_path)
        else:
            self._priv_key = raw_key
        self._available = bool(self._key_id and self._priv_key)
        if self._available:
            log.info("KalshiLiveOrgan: ready (dry_run=%s)", self.dry_run)
        else:
            log.info(
                "KalshiLiveOrgan: unavailable — add KALSHI_API_KEY_ID + "
                "KALSHI_PRIVATE_KEY to .env to enable prediction market hedging"
            )

    @property
    def available(self) -> bool:
        return self._available

    def _auth_headers(self) -> Dict[str, str]:
        """Build Kalshi JWT-style auth headers using RSA private key."""
        import base64, hashlib, hmac, struct
        try:
            # Kalshi uses RSA-PSS signatures
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend

            ts_ms = str(int(time.time() * 1000))
            msg   = (ts_ms + "GET" + "/trade-api/v2").encode()

            key_bytes = self._priv_key.encode() if isinstance(self._priv_key, str) else self._priv_key
            private_key = serialization.load_pem_private_key(
                key_bytes, password=None, backend=default_backend()
            )
            sig = private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
            sig_b64 = base64.b64encode(sig).decode()

            return {
                "KALSHI-ACCESS-KEY":       self._key_id,
                "KALSHI-ACCESS-TIMESTAMP": ts_ms,
                "KALSHI-ACCESS-SIGNATURE": sig_b64,
                "Content-Type":            "application/json",
            }
        except Exception as e:
            log.warning("Kalshi auth header build failed: %s", e)
            return {"Content-Type": "application/json"}

    def _find_contract(self, ticker: str, action: str, spot_price: float) -> Optional[str]:
        """
        Find the most liquid Kalshi contract for a crypto hedge.
        Returns the market ticker string or None if not found.

        Looks for contracts where the strike price is close to spot.
        """
        import urllib.request
        series = self.CRYPTO_SERIES.get(ticker.upper())
        if not series:
            return None
        try:
            url  = f"{self.BASE_URL}/markets?series_ticker={series}&status=open&limit=20"
            req  = urllib.request.Request(url, headers=self._auth_headers())
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            markets = data.get("markets", [])
            # Find contract closest to spot price with decent volume
            best = None
            best_dist = float("inf")
            for m in markets:
                floor_p = float(m.get("floor_strike", 0) or 0)
                cap_p   = float(m.get("cap_strike",   0) or 0)
                vol     = float(m.get("volume", 0) or 0)
                mid     = (floor_p + cap_p) / 2 if cap_p else floor_p
                dist    = abs(mid - spot_price)
                if dist < best_dist and vol > 0:
                    best_dist = dist
                    best      = m.get("ticker")
            return best
        except Exception as e:
            log.debug("Kalshi contract lookup failed: %s", e)
            return None

    async def execute(self, signal: RouterSignal) -> PlatformResult:
        t0 = time.monotonic()
        result = PlatformResult(platform=self.PLATFORM, status="ok")

        if not self._available:
            result.status = "skipped"
            result.error  = "credentials not configured"
            result.latency_ms = 0
            return result

        import urllib.request, urllib.error

        for symbol, leg in signal.assets.items():
            action  = leg.get("action", "").lower()
            usd_amt = float(leg.get("position_usd", 0) or 0)
            if not usd_amt or action not in ("buy", "sell"):
                continue

            # Stake = 10% of position as hedge (configurable)
            stake_pct = float(os.environ.get("SIMP_KALSHI_HEDGE_PCT", "0.10"))
            stake_usd = round(usd_amt * stake_pct, 2)
            if stake_usd < 0.01:
                continue

            ticker_base = symbol.split("-")[0]
            # BUY crypto → YES on price-above (bullish hedge amplifier)
            # SELL crypto → NO on price-above (bearish protective hedge)
            kalshi_side = "yes" if action == "buy" else "no"

            exec_rec: Dict[str, Any] = {
                "symbol":       symbol,
                "action":       action,
                "kalshi_side":  kalshi_side,
                "stake_usd":    stake_usd,
                "hedge_pct":    stake_pct,
            }

            if self.dry_run:
                exec_rec["status"] = "dry_run"
                log.info(
                    "[DRY-RUN] Kalshi hedge: %s %s $%.2f stake",
                    kalshi_side.upper(), ticker_base, stake_usd,
                )
                result.executions.append(exec_rec)
                continue

            # Live: find contract then place order
            contract = self._find_contract(ticker_base, action, spot_price=0)
            if not contract:
                exec_rec["status"] = "skipped"
                exec_rec["error"]  = f"no open {ticker_base} contract found"
                result.executions.append(exec_rec)
                continue

            exec_rec["contract"] = contract
            try:
                payload = json.dumps({
                    "ticker":    contract,
                    "action":    "buy",
                    "side":      kalshi_side,
                    "type":      "market",
                    "count":     max(1, int(stake_usd)),  # 1 contract = $1 max loss
                }).encode()
                req = urllib.request.Request(
                    f"{self.BASE_URL}/portfolio/orders",
                    data=payload,
                    headers=self._auth_headers(),
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    resp_data = json.loads(r.read().decode())
                exec_rec["status"]   = "ok"
                exec_rec["order_id"] = resp_data.get("order", {}).get("order_id", "")
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:200]
                exec_rec["status"] = "error"
                exec_rec["error"]  = f"HTTP {e.code}: {body}"
                result.status = "partial"
            except Exception as e:
                exec_rec["status"] = "error"
                exec_rec["error"]  = str(e)[:120]
                result.status = "partial"

            result.executions.append(exec_rec)

        result.latency_ms = (time.monotonic() - t0) * 1000
        if not result.executions:
            result.status = "skipped"
        return result


# ---------------------------------------------------------------------------
# Live organ: Alpaca (equities hedge)
# ---------------------------------------------------------------------------

class AlpacaLiveOrgan:
    """
    Mirrors crypto positions into crypto-linked equities on Alpaca.

    Mirror map (crypto → equity proxy):
        BTC  →  BITO  (ProShares Bitcoin ETF)
        ETH  →  ETHE  (Grayscale Ethereum Trust)
        SOL  →  SOL   (not directly listed; mirrors to COIN as proxy)

    Stake = SIMP_ALPACA_MIRROR_PCT of the crypto position (default 20%).
    Activates automatically when ALPACA_API_KEY + ALPACA_SECRET_KEY are in .env.
    """

    PLATFORM = Platform.ALPACA

    MIRROR_MAP = {
        "BTC": "BITO",
        "ETH": "ETHE",
        "SOL": "COIN",   # Coinbase stock as SOL proxy
    }

    def __init__(self, dry_run: bool = False):
        self.dry_run   = dry_run
        self._api_key  = _env_or_file("ALPACA_API_KEY", "ALPACA_LIVE_API_KEY", "APCA_API_KEY_ID", "APCA_API_KEY")
        self._secret   = _env_or_file("ALPACA_SECRET_KEY", "ALPACA_LIVE_SECRET_KEY", "APCA_API_SECRET_KEY", "APCA_SECRET_KEY")
        is_live        = bool(_env_or_file("ALPACA_LIVE_API_KEY")) or bool(self._api_key)
        self._base_url = (
            "https://api.alpaca.markets"
            if is_live else
            "https://paper-api.alpaca.markets"
        )
        self._is_live  = is_live
        self._available = bool(self._api_key and self._secret)
        if self._available:
            log.info("AlpacaLiveOrgan: ready  live=%s  dry_run=%s", is_live, self.dry_run)
        else:
            log.info(
                "AlpacaLiveOrgan: unavailable — add ALPACA_API_KEY + "
                "ALPACA_SECRET_KEY to .env to enable equities mirroring"
            )

    @property
    def available(self) -> bool:
        return self._available

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID":     self._api_key,
            "APCA-API-SECRET-KEY": self._secret,
            "Content-Type":        "application/json",
        }

    def _get_quote(self, symbol: str) -> float:
        import urllib.request
        try:
            req = urllib.request.Request(
                f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest",
                headers=self._headers(),
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            q = data.get("quote", {})
            ap = float(q.get("ap", 0) or 0)
            bp = float(q.get("bp", 0) or 0)
            return (ap + bp) / 2 if ap and bp else max(ap, bp)
        except Exception:
            return 0.0

    async def execute(self, signal: RouterSignal) -> PlatformResult:
        t0 = time.monotonic()
        result = PlatformResult(platform=self.PLATFORM, status="ok")

        if not self._available:
            result.status = "skipped"
            result.error  = "credentials not configured"
            result.latency_ms = 0
            return result

        import urllib.request, urllib.error

        mirror_pct = float(os.environ.get("SIMP_ALPACA_MIRROR_PCT", "0.20"))

        for symbol, leg in signal.assets.items():
            action  = leg.get("action", "").lower()
            usd_amt = float(leg.get("position_usd", 0) or 0)
            if not usd_amt or action not in ("buy", "sell"):
                continue

            crypto_ticker = symbol.split("-")[0]
            equity_ticker = self.MIRROR_MAP.get(crypto_ticker)
            if not equity_ticker:
                continue

            mirror_usd = round(usd_amt * mirror_pct, 2)
            if mirror_usd < 1.0:
                continue

            exec_rec: Dict[str, Any] = {
                "crypto_symbol":  symbol,
                "equity_ticker":  equity_ticker,
                "action":         action,
                "mirror_usd":     mirror_usd,
                "mirror_pct":     mirror_pct,
            }

            if self.dry_run:
                exec_rec["status"] = "dry_run"
                log.info(
                    "[DRY-RUN] Alpaca mirror: %s %s $%.2f",
                    action.upper(), equity_ticker, mirror_usd,
                )
                result.executions.append(exec_rec)
                continue

            # Fractional dollar-value order (notional)
            try:
                payload = json.dumps({
                    "symbol":       equity_ticker,
                    "notional":     str(mirror_usd),
                    "side":         action,
                    "type":         "market",
                    "time_in_force": "day",
                }).encode()
                req = urllib.request.Request(
                    f"{self._base_url}/v2/orders",
                    data=payload,
                    headers=self._headers(),
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    resp_data = json.loads(r.read().decode())
                exec_rec["status"]   = "ok"
                exec_rec["order_id"] = resp_data.get("id", "")
                exec_rec["alpaca_status"] = resp_data.get("status", "")
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:200]
                exec_rec["status"] = "error"
                exec_rec["error"]  = f"HTTP {e.code}: {body}"
                result.status = "partial"
            except Exception as e:
                exec_rec["status"] = "error"
                exec_rec["error"]  = str(e)[:120]
                result.status = "partial"

            result.executions.append(exec_rec)

        result.latency_ms = (time.monotonic() - t0) * 1000
        if not result.executions:
            result.status = "skipped"
        return result


# ---------------------------------------------------------------------------
# Organ Registry — discovers available organs from credentials
# ---------------------------------------------------------------------------

class OrganRegistry:
    """
    Central registry for live organs.
    Organs are instantiated once and reused; only configured platforms appear.
    """

    def __init__(self, dry_run: bool = False):
        self._dry_run = dry_run
        self._organs: Dict[Platform, Any] = {}
        self._build()

    def _build(self) -> None:
        self._organs[Platform.COINBASE] = CoinbaseLiveOrgan(dry_run=self._dry_run)
        self._organs[Platform.KALSHI]   = KalshiLiveOrgan(dry_run=self._dry_run)
        self._organs[Platform.ALPACA]   = AlpacaLiveOrgan(dry_run=self._dry_run)

    def available(self) -> List[Platform]:
        return [p for p, o in self._organs.items() if o.available]

    def get(self, platform: Platform) -> Optional[Any]:
        return self._organs.get(platform)

    def status(self) -> Dict[str, Any]:
        return {
            p.value: {
                "available": o.available,
                "dry_run":   getattr(o, "dry_run", False),
            }
            for p, o in self._organs.items()
        }


# ---------------------------------------------------------------------------
# Multi-Platform Router
# ---------------------------------------------------------------------------

class MultiPlatformRouter:
    """
    One signal in → all configured platforms execute in parallel → one result out.

    Parameters
    ----------
    dry_run : bool
        If True, no live orders are placed on any platform.  Override with
        env var SIMP_ROUTER_DRY_RUN=true.
    platforms : list[Platform] | None
        Restrict routing to specific platforms.  None = all available.
    hedge_kalshi : bool
        Route crypto signals to Kalshi as prediction market hedge.
        Default False; set SIMP_HEDGE_KALSHI=true to enable.
    hedge_alpaca : bool
        Mirror crypto signals to Alpaca equities.
        Default False; set SIMP_HEDGE_ALPACA=true to enable.
    """

    def __init__(
        self,
        dry_run:       bool = False,
        platforms:     Optional[List[Platform]] = None,
        hedge_kalshi:  bool = False,
        hedge_alpaca:  bool = False,
    ):
        env_dry = os.environ.get("SIMP_ROUTER_DRY_RUN", "").lower() == "true"
        self._dry_run      = dry_run or env_dry
        self._platforms    = platforms
        self._hedge_kalshi = hedge_kalshi or os.environ.get("SIMP_HEDGE_KALSHI", "").lower() == "true"
        self._hedge_alpaca = hedge_alpaca or os.environ.get("SIMP_HEDGE_ALPACA", "").lower() == "true"
        self._registry     = OrganRegistry(dry_run=self._dry_run)

        avail = self._registry.available()
        log.info(
            "MultiPlatformRouter ready: available=%s  dry_run=%s  hedge_kalshi=%s  hedge_alpaca=%s",
            [p.value for p in avail], self._dry_run, self._hedge_kalshi, self._hedge_alpaca,
        )

    def _select_organs(self) -> List[Any]:
        """Return organ instances that should execute this signal."""
        organs = []
        reg    = self._registry

        coinbase = reg.get(Platform.COINBASE)
        if coinbase:
            organs.append(coinbase)

        if self._hedge_kalshi:
            kalshi = reg.get(Platform.KALSHI)
            if kalshi:
                organs.append(kalshi)

        if self._hedge_alpaca:
            alpaca = reg.get(Platform.ALPACA)
            if alpaca:
                organs.append(alpaca)

        if self._platforms:
            restrict = {p for p in self._platforms}
            organs = [o for o in organs if o.PLATFORM in restrict]

        return organs

    async def route(self, signal: dict | RouterSignal) -> RouterResult:
        """
        Route a signal to all configured platforms simultaneously.

        Args:
            signal: dict (quantum_signal_bridge format) or RouterSignal

        Returns:
            RouterResult with per-platform outcomes.
        """
        if isinstance(signal, dict):
            sig = RouterSignal.from_dict(signal)
        else:
            sig = signal

        result = RouterResult(
            signal_id = sig.signal_id,
            dry_run   = self._dry_run,
        )

        organs = self._select_organs()
        if not organs:
            log.warning("No organs available for routing — check credentials")
            return result

        # Parallel execution
        tasks    = [organ.execute(sig) for organ in organs]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        total_usd = 0.0
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                log.error("Organ execution raised: %s", outcome)
                result.platforms.append(PlatformResult(
                    platform=Platform.COINBASE,   # placeholder
                    status="error",
                    error=str(outcome)[:120],
                ))
                continue
            result.platforms.append(outcome)
            for ex in outcome.executions:
                if ex.get("status") in ("ok", "dry_run"):
                    total_usd += float(ex.get("usd", 0) or ex.get("mirror_usd", 0) or ex.get("stake_usd", 0))

        result.total_usd_deployed = total_usd
        log.info(result.summary())
        self._persist(result)
        return result

    def route_sync(self, signal: dict | RouterSignal) -> RouterResult:
        """Synchronous wrapper for use in non-async contexts."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already inside an event loop (e.g. Jupyter) — schedule as task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(1) as ex:
                    future = ex.submit(asyncio.run, self.route(signal))
                    return future.result()
            else:
                return loop.run_until_complete(self.route(signal))
        except RuntimeError:
            return asyncio.run(self.route(signal))

    def _persist(self, result: RouterResult) -> None:
        try:
            ROUTER_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
            with ROUTER_JOURNAL.open("a") as f:
                row = {
                    "router_id":  result.router_id,
                    "signal_id":  result.signal_id,
                    "routed_at":  result.routed_at,
                    "dry_run":    result.dry_run,
                    "total_usd":  result.total_usd_deployed,
                    "platforms": [
                        {
                            "platform":    p.platform.value,
                            "status":      p.status,
                            "executions":  p.executions,
                            "latency_ms":  round(p.latency_ms, 1),
                            "error":       p.error,
                        }
                        for p in result.platforms
                    ],
                }
                f.write(json.dumps(row) + "\n")
        except Exception as e:
            log.warning("Failed to persist router result: %s", e)

    def status(self) -> Dict[str, Any]:
        """Return registry status — useful for dashboards."""
        return {
            "dry_run":      self._dry_run,
            "hedge_kalshi": self._hedge_kalshi,
            "hedge_alpaca": self._hedge_alpaca,
            "organs":       self._registry.status(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton + convenience function
# ---------------------------------------------------------------------------

_DEFAULT_ROUTER: Optional[MultiPlatformRouter] = None


def get_router(
    dry_run:      bool = False,
    hedge_kalshi: bool = False,
    hedge_alpaca: bool = False,
) -> MultiPlatformRouter:
    """Return (or create) the module-level router singleton."""
    global _DEFAULT_ROUTER
    if _DEFAULT_ROUTER is None:
        _DEFAULT_ROUTER = MultiPlatformRouter(
            dry_run=dry_run,
            hedge_kalshi=hedge_kalshi,
            hedge_alpaca=hedge_alpaca,
        )
    return _DEFAULT_ROUTER


def route_signal(signal: dict, dry_run: bool = False) -> RouterResult:
    """
    Convenience function for synchronous callers.

    from simp.routing.signal_router import route_signal
    result = route_signal(signal_dict)
    """
    return get_router(dry_run=dry_run).route_sync(signal)
