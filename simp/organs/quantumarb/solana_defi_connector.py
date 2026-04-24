#!/usr/bin/env python3.10
"""
Solana DeFi Connector for QuantumArb organ.

Read-only scanner for Solana DeFi opportunities:
- Pump.fun new token launches
- Jupiter DEX arbitrage routes
- Raydium liquidity pool mismatches

No on-chain trade execution. All scanning only.
"""

import json
import logging
import time
import urllib.request as url_req
import urllib.error as url_err
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
log = logging.getLogger("SolanaDefiConnector")
log.setLevel(logging.INFO)

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

DEFAULT_ALCHEMY_RPC = "https://solana-mainnet.g.alchemy.com/v2/demo"
JUPITER_QUOTE_API = "https://jup.ag/api/quote/v6"  # stable hostname (quote-api.jup.ag often fails)
JUPITER_QUOTE_API_FALLBACK = "https://quote-api.jup.ag/v6/quote"
JUPITER_PRICE_API = "https://jup.ag/api/price/v2"  # stable hostname
JUPITER_PRICE_API_FALLBACK = "https://quote-api.jup.ag/v6/price"
RAYDIUM_API = "https://api.raydium.io/v2/main/pairs"
PUMPFUN_API_BASE = "https://frontend-api.pump.fun"

# Well-known SPL token mints (mainnet)
WSOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFza1VYHqJx9J3N3qVQtVjQyYStQPtU1nKqLZn1"
RAY_MINT = "4k3Dyjzvzp8eM4U1RjH2NqCkz7kCkRTxL9w6YjGzKkLp"

# Base tokens commonly used for arbitrage scan paths
DEFAULT_BASE_TOKENS: List[Dict[str, str]] = [
    {"symbol": "WSOL", "mint": WSOL_MINT},
    {"symbol": "USDC", "mint": USDC_MINT},
    {"symbol": "USDT", "mint": USDT_MINT},
    {"symbol": "RAY", "mint": RAY_MINT},
]

TIMEOUT_SECONDS = 15
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _iso_timestamp() -> str:
    """Return current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _http_get(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """Perform a GET request and return parsed JSON, or None on failure."""
    merged = dict(REQUEST_HEADERS)
    if headers:
        merged.update(headers)
    try:
        req = url_req.Request(url, headers=merged, method="GET")
        with url_req.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except (url_err.HTTPError, url_err.URLError, json.JSONDecodeError, OSError) as exc:
        log.warning("HTTP GET failed for %s: %s", url, exc)
        return None


def _http_post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """Perform a POST with JSON body and return parsed JSON, or None on failure."""
    merged = dict(REQUEST_HEADERS)
    merged["Content-Type"] = "application/json"
    if headers:
        merged.update(headers)
    body = json.dumps(payload).encode("utf-8")
    try:
        req = url_req.Request(url, data=body, headers=merged, method="POST")
        with url_req.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except (url_err.HTTPError, url_err.URLError, json.JSONDecodeError, OSError) as exc:
        log.warning("HTTP POST failed for %s: %s", url, exc)
        return None


def _make_opportunity(
    token_symbol: str,
    token_address: str,
    price_usd: float,
    liquidity_usd: float,
    volume_24h: float,
    confidence: float,
    opportunity_type: str,
    estimated_profit_pct: float,
) -> Dict[str, Any]:
    """Build a standardised opportunity record."""
    return {
        "token_symbol": token_symbol,
        "token_address": token_address,
        "price_usd": price_usd,
        "liquidity_usd": liquidity_usd,
        "volume_24h": volume_24h,
        "confidence": round(min(max(confidence, 0.0), 1.0), 4),
        "opportunity_type": opportunity_type,
        "estimated_profit_pct": round(estimated_profit_pct, 4),
        "timestamp": _iso_timestamp(),
    }


# ──────────────────────────────────────────────────────────────────────
# PumpFunScanner
# ──────────────────────────────────────────────────────────────────────

class PumpFunScanner:
    """
    Scan pump.fun for newly launched tokens.

    Uses the public pump.fun frontend API endpoints.  All data is
    read-only — no trades are executed.
    """

    def __init__(self, base_url: str = PUMPFUN_API_BASE):
        self._base_url = base_url.rstrip("/")

    # ── public API ───────────────────────────────────────────────────

    def scan_new_tokens(self, max_age_minutes: int = 10) -> List[Dict[str, Any]]:
        """
        Detect recently launched pump.fun tokens.

        Parameters
        ----------
        max_age_minutes : int
            Maximum age of tokens to include, in minutes.

        Returns
        -------
        List[dict]
            Each dict conforms to the standard opportunity schema.
        """
        opportunities: List[Dict[str, Any]] = []

        # Attempt to fetch recent tokens from pump.fun.
        raw_tokens = self._fetch_recent_tokens()
        if raw_tokens is None:
            log.warning("PumpFunScanner: could not fetch recent tokens.")
            return opportunities

        cutoff_ts = time.time() - (max_age_minutes * 60)
        now_iso = _iso_timestamp()

        for token in raw_tokens:
            created_at = token.get("created_at") or token.get("timestamp") or ""
            created_ts = self._parse_timestamp(created_at)
            if created_ts is not None and created_ts < cutoff_ts:
                continue

            symbol = token.get("symbol") or token.get("ticker") or "UNKNOWN"
            address = token.get("mint") or token.get("address") or token.get("id", "")
            price = float(token.get("price_usd") or token.get("price", 0))
            liquidity = float(
                token.get("liquidity_usd") or token.get("liquidity", 0)
            )
            volume = float(
                token.get("volume_24h") or token.get("volume", 0)
            )

            # Compute a heuristic confidence score for new launches.
            confidence = self._compute_launch_confidence(token, liquidity, volume)

            profit_pct = self._estimate_new_launch_profit(token, confidence)

            opportunities.append(
                _make_opportunity(
                    token_symbol=symbol,
                    token_address=address,
                    price_usd=price,
                    liquidity_usd=liquidity,
                    volume_24h=volume,
                    confidence=confidence,
                    opportunity_type="new_launch",
                    estimated_profit_pct=profit_pct,
                )
            )

        # Sort by confidence descending
        opportunities.sort(key=lambda o: o["confidence"], reverse=True)
        log.info(
            "PumpFunScanner: found %d new tokens (max_age=%d min)",
            len(opportunities),
            max_age_minutes,
        )
        return opportunities

    # ── internal helpers ─────────────────────────────────────────────

    def _fetch_recent_tokens(self) -> Optional[List[Dict[str, Any]]]:
        """
        Try multiple pump.fun endpoints to find recent tokens.

        Returns None if all endpoints fail.
        """
        endpoints = [
            f"{self._base_url}/tokens?limit=50&sort=created_at&order=desc",
            f"{self._base_url}/coins?limit=50&sort=created&order=desc",
            f"{self._base_url}/api/coins?limit=50&sort=created&order=desc",
        ]
        for url in endpoints:
            data = _http_get(url)
            if data is not None:
                # The response might be a dict with a "tokens" or "coins" key,
                # or a plain list.
                if isinstance(data, list):
                    return data
                for key in ("tokens", "coins", "results", "data"):
                    items = data.get(key)
                    if isinstance(items, list):
                        return items
                # If it's a dict but we can't find a list, return as-is.
                return [data]
        return None

    @staticmethod
    def _parse_timestamp(ts_str: str) -> Optional[float]:
        """Try to parse a timestamp string into a Unix epoch float."""
        if not ts_str:
            return None
        # Try ISO8601 first.
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError):
            pass
        # Try Unix epoch (float or int as string).
        try:
            return float(ts_str)
        except (ValueError, TypeError):
            pass
        return None

    @staticmethod
    def _compute_launch_confidence(
        token: Dict[str, Any],
        liquidity_usd: float,
        volume_24h: float,
    ) -> float:
        """
        Heuristic confidence score for a new token.

        Factors:
        - Liquidity > $1000 ⇒ +0.3
        - Volume > $5000  ⇒ +0.2
        - Has social links ⇒ +0.15
        - Has non-zero supply ⇒ +0.1
        - Low liquidity penalty: liquidity < $100 ⇒ -0.2
        """
        score = 0.2  # baseline

        if liquidity_usd >= 1000.0:
            score += 0.3
        elif liquidity_usd >= 100.0:
            score += 0.15
        else:
            score -= 0.2

        if volume_24h >= 5000.0:
            score += 0.2
        elif volume_24h >= 500.0:
            score += 0.1

        social = token.get("social") or token.get("links") or {}
        if isinstance(social, dict) and len(social) > 0:
            score += 0.15
        if isinstance(social, list) and len(social) > 0:
            score += 0.15

        supply_raw = token.get("supply") or token.get("total_supply") or 0
        try:
            if float(supply_raw) > 0:
                score += 0.1
        except (ValueError, TypeError):
            pass

        return min(score, 1.0)

    @staticmethod
    def _estimate_new_launch_profit(
        token: Dict[str, Any],
        confidence: float,
    ) -> float:
        """
        Rough profit potential estimate for a new token.

        Early entries on pump.fun can 2-10x if the token gains traction.
        We use a conservative model based on confidence.
        """
        if confidence < 0.3:
            return 0.0
        # Map confidence 0.3-1.0 to profit 5%-200%.
        return max(0.0, (confidence - 0.3) * 2.85 * 100)


# ──────────────────────────────────────────────────────────────────────
# JupiterDexQuoter
# ──────────────────────────────────────────────────────────────────────

class JupiterDexQuoter:
    """
    Read-only quoter for Jupiter DEX v6.

    Provides price quotes and arbitrage route discovery without
    executing any swaps.
    """

    def __init__(
        self,
        quote_api_url: str = JUPITER_QUOTE_API,
        price_api_url: str = JUPITER_PRICE_API,
    ):
        self._quote_api = quote_api_url.rstrip("/")
        self._price_api = price_api_url.rstrip("/")

    # ── public API ───────────────────────────────────────────────────

    def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> Dict[str, Any]:
        """
        Get a Jupiter quote between two SPL tokens.

        Parameters
        ----------
        input_mint : str
            Mint address of the input token.
        output_mint : str
            Mint address of the output token.
        amount : int
            Amount in the smallest unit (e.g. lamports for SOL).
        slippage_bps : int
            Allowed slippage in basis points (default 50 = 0.5 %).

        Returns
        -------
        dict
            Contains keys: success, price, route_summary, out_amount,
            price_impact_pct, error (if failed).
        """
        params = (
            f"inputMint={input_mint}"
            f"&outputMint={output_mint}"
            f"&amount={amount}"
            f"&slippageBps={slippage_bps}"
        )
        url = f"{self._quote_api}?{params}"
        data = _http_get(url)

        # Retry with fallback hostname if primary fails
        if data is None and JUPITER_QUOTE_API_FALLBACK and self._quote_api != JUPITER_QUOTE_API_FALLBACK:
            fallback_url = f"{JUPITER_QUOTE_API_FALLBACK}?{params}"
            data = _http_get(fallback_url)

        if data is None:
            return {
                "success": False,
                "error": "Failed to fetch quote from Jupiter API",
            }

        # Jupiter v6 returns a flat dict with fields like
        # inAmount, outAmount, routePlan, priceImpactPct, etc.
        out_amount_str = data.get("outAmount") or "0"
        try:
            out_amount = int(out_amount_str)
        except (ValueError, TypeError):
            out_amount = 0

        price_impact_str = data.get("priceImpactPct") or "0"
        try:
            price_impact_pct = float(price_impact_str)
        except (ValueError, TypeError):
            price_impact_pct = 0.0

        route_plan = data.get("routePlan") or []
        route_summary = self._summarise_route(route_plan)

        return {
            "success": True,
            "input_mint": input_mint,
            "output_mint": output_mint,
            "amount_in": amount,
            "amount_out": out_amount,
            "price": out_amount / max(amount, 1),
            "route_summary": route_summary,
            "route_plan": route_plan,
            "price_impact_pct": price_impact_pct,
            "slippage_bps": slippage_bps,
        }

    def scan_profitable_routes(
        self,
        base_tokens: Optional[List[Dict[str, str]]] = None,
        amount: int = 100_000_000,  # 0.1 SOL in lamports
        min_profit_bps: int = 20,   # 0.2 % minimum profit
    ) -> List[Dict[str, Any]]:
        """
        Scan for profitable arbitrage routes between base SPL tokens.

        Parameters
        ----------
        base_tokens : list of dict, optional
            Each dict must have 'symbol' and 'mint' keys.
            Defaults to WSOL, USDC, USDT, RAY.
        amount : int
            Quote amount in smallest unit (default 0.1 SOL-worth).
        min_profit_bps : int
            Minimum profit in basis points to report.

        Returns
        -------
        List[dict]
            Standard opportunity records for dex_arb opportunities.
        """
        tokens = base_tokens or DEFAULT_BASE_TOKENS
        opportunities: List[Dict[str, Any]] = []

        # Build a lookup map: mint → symbol
        mint_to_symbol: Dict[str, str] = {t["mint"]: t["symbol"] for t in tokens}

        for i, token_a in enumerate(tokens):
            for j in range(i + 1, len(tokens)):
                token_b = tokens[j]
                mint_a = token_a["mint"]
                mint_b = token_b["mint"]

                # Quote both directions.
                quote_ab = self.get_quote(mint_a, mint_b, amount)
                quote_ba = self.get_quote(mint_b, mint_a, amount)

                if not quote_ab.get("success") or not quote_ba.get("success"):
                    continue

                # Compute effective cross-rate.
                price_ab = quote_ab.get("price", 0.0)
                price_ba = quote_ba.get("price", 0.0)

                if price_ab <= 0 or price_ba <= 0:
                    continue

                # Mid price from the two quotes.
                price_mid = (price_ab + (1.0 / max(price_ba, 1e-12))) / 2.0
                spread_bps = abs(price_ab - 1.0 / max(price_ba, 1e-12)) / max(
                    price_mid, 1e-12
                )
                spread_bps = int(spread_bps * 10_000)

                if spread_bps < min_profit_bps:
                    continue

                confidence = self._compute_arb_confidence(
                    spread_bps, quote_ab.get("price_impact_pct", 0.0)
                )

                profit_pct = spread_bps / 100.0  # Convert bps → percent

                opportunities.append(
                    _make_opportunity(
                        token_symbol=f"{token_a['symbol']}/{token_b['symbol']}",
                        token_address=f"{mint_a}/{mint_b}",
                        price_usd=price_mid,
                        liquidity_usd=0.0,  # Not available via Jupiter quote
                        volume_24h=0.0,
                        confidence=confidence,
                        opportunity_type="dex_arb",
                        estimated_profit_pct=profit_pct,
                    )
                )

        opportunities.sort(key=lambda o: o["estimated_profit_pct"], reverse=True)
        log.info(
            "JupiterDexQuoter: found %d profitable routes (min=%d bps)",
            len(opportunities),
            min_profit_bps,
        )
        return opportunities

    # ── internal helpers ─────────────────────────────────────────────

    @staticmethod
    def _summarise_route(route_plan: List[Any]) -> List[Dict[str, str]]:
        """Collapse a Jupiter route plan into a human-readable summary."""
        hops: List[Dict[str, str]] = []
        for step in route_plan:
            swap_info = step.get("swapInfo") or {}
            amm_key = swap_info.get("ammKey", "unknown")
            label = swap_info.get("label", "unknown")
            hops.append({"amm": amm_key, "dex": label})
        return hops

    @staticmethod
    def _compute_arb_confidence(
        spread_bps: int,
        price_impact_pct: float,
    ) -> float:
        """
        Heuristic confidence for DEX arbitrage.

        - Higher spread ⇒ higher confidence
        - Lower price impact ⇒ higher confidence
        """
        spread_score = min(spread_bps / 200.0, 0.7)
        impact_penalty = min(price_impact_pct / 10.0, 0.3)
        score = 0.2 + spread_score - impact_penalty
        return min(max(score, 0.0), 1.0)


# ──────────────────────────────────────────────────────────────────────
# RaydiumLpScanner
# ──────────────────────────────────────────────────────────────────────

class RaydiumLpScanner:
    """
    Scan Raydium liquidity pools for price and liquidity mismatches.

    All data is fetched via the public Raydium API — no swaps executed.
    """

    def __init__(self, api_url: str = RAYDIUM_API):
        self._api_url = api_url

    def scan_liquidity_mismatches(
        self,
        min_liquidity_usd: float = 10_000.0,
        min_volume_ratio: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Detect pools where volume is high relative to liquidity
        (potential opportunity for arbitrage or fee generation).

        Parameters
        ----------
        min_liquidity_usd : float
            Minimum pool liquidity in USD.
        min_volume_ratio : float
            Minimum volume / liquidity ratio (e.g. 0.5 means
            volume is at least 50 % of liquidity).

        Returns
        -------
        List[dict]
            Standard opportunity records for liquidity_mismatch.
        """
        opportunities: List[Dict[str, Any]] = []
        pairs = self._fetch_pairs()

        if pairs is None:
            log.warning("RaydiumLpScanner: could not fetch pairs.")
            return opportunities

        for pair in pairs:
            liquidity = float(pair.get("liquidity", 0) or 0)
            volume_24h = float(pair.get("volume24h", 0) or 0)

            if liquidity < min_liquidity_usd:
                continue

            vol_ratio = volume_24h / max(liquidity, 1.0)
            if vol_ratio < min_volume_ratio:
                continue

            symbol = pair.get("symbol", pair.get("name", "UNKNOWN"))
            base_symbol = pair.get("baseSymbol", symbol.split("-")[0] if "-" in symbol else symbol)
            address = pair.get("ammId", pair.get("id", ""))
            price = float(pair.get("price", 0) or 0)

            # High volume / liquidity ratio suggests active trading
            # and potential arbitrage.
            confidence = min(vol_ratio / 5.0, 0.9)
            profit_pct = vol_ratio * 100.0 * 0.3  # Conservative estimate

            opportunities.append(
                _make_opportunity(
                    token_symbol=base_symbol,
                    token_address=address,
                    price_usd=price,
                    liquidity_usd=liquidity,
                    volume_24h=volume_24h,
                    confidence=confidence,
                    opportunity_type="liquidity_mismatch",
                    estimated_profit_pct=profit_pct,
                )
            )

        opportunities.sort(key=lambda o: o["estimated_profit_pct"], reverse=True)
        log.info(
            "RaydiumLpScanner: found %d liquidity mismatches",
            len(opportunities),
        )
        return opportunities

    def _fetch_pairs(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch Raydium pair data from the public API."""
        data = _http_get(self._api_url)
        if data is None:
            return None
        if isinstance(data, list):
            return data
        for key in ("pairs", "results", "data"):
            items = data.get(key)
            if isinstance(items, list):
                return items
        # If it's a single pair envelope, wrap it.
        return [data]


# ──────────────────────────────────────────────────────────────────────
# SolanaDefiScanner (combined)
# ──────────────────────────────────────────────────────────────────────

class SolanaDefiScanner:
    """
    Combined scanner that collects opportunities from:
    - Pump.fun (new token launches)
    - Jupiter DEX (arbitrage routes)
    - Raydium (liquidity mismatches)

    Also supports on-chain queries via Alchemy RPC for additional
    confirmation data (read-only).
    """

    def __init__(
        self,
        alchemy_rpc: str = DEFAULT_ALCHEMY_RPC,
        pump_scanner: Optional[PumpFunScanner] = None,
        jupiter_quoter: Optional[JupiterDexQuoter] = None,
        raydium_scanner: Optional[RaydiumLpScanner] = None,
    ):
        self._rpc = alchemy_rpc
        self._pump = pump_scanner or PumpFunScanner()
        self._jupiter = jupiter_quoter or JupiterDexQuoter()
        self._raydium = raydium_scanner or RaydiumLpScanner()

    # ── public API ───────────────────────────────────────────────────

    def scan_all_opportunities(self) -> List[Dict[str, Any]]:
        """
        Run all scanners and return combined opportunities, deduplicated
        and sorted by estimated profit descending.

        Returns
        -------
        List[dict]
        """
        all_ops: List[Dict[str, Any]] = []

        # 1. Pump.fun new launches
        try:
            pump_ops = self._pump.scan_new_tokens()
            all_ops.extend(pump_ops)
            log.info("Pump.fun: %d opportunities", len(pump_ops))
        except Exception as exc:
            log.error("Pump.fun scan failed: %s", exc)

        # 2. Jupiter DEX arb routes
        try:
            arb_ops = self._jupiter.scan_profitable_routes()
            all_ops.extend(arb_ops)
            log.info("Jupiter DEX: %d opportunities", len(arb_ops))
        except Exception as exc:
            log.error("Jupiter DEX scan failed: %s", exc)

        # 3. Raydium liquidity mismatches
        try:
            lp_ops = self._raydium.scan_liquidity_mismatches()
            all_ops.extend(lp_ops)
            log.info("Raydium: %d opportunities", len(lp_ops))
        except Exception as exc:
            log.error("Raydium scan failed: %s", exc)

        # Deduplicate by (token_address, opportunity_type)
        seen: set = set()
        deduped: List[Dict[str, Any]] = []
        for op in all_ops:
            key = (op["token_address"], op["opportunity_type"])
            if key not in seen:
                seen.add(key)
                deduped.append(op)

        # Sort by estimated profit descending
        deduped.sort(key=lambda o: o.get("estimated_profit_pct", 0), reverse=True)

        log.info(
            "SolanaDefiScanner: total %d unique opportunities",
            len(deduped),
        )
        return deduped

    def get_token_account_info(
        self,
        token_mint: str,
        owner_address: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch on-chain token account data via Alchemy RPC (read-only).

        If owner_address is provided, queries that owner's token account.
        Otherwise returns general mint info.

        Parameters
        ----------
        token_mint : str
            SPL token mint address.
        owner_address : str, optional
            Owner's wallet address.

        Returns
        -------
        Optional[dict]
            Parsed RPC response or None on failure.
        """
        if owner_address:
            return self._rpc_call("getTokenAccountsByOwner", [
                owner_address,
                {"mint": token_mint},
                {"encoding": "jsonParsed"},
            ])
        else:
            return self._rpc_call("getAccountInfo", [
                token_mint,
                {"encoding": "jsonParsed"},
            ])

    def get_token_supply(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Fetch total supply for an SPL token via RPC."""
        return self._rpc_call("getTokenSupply", [token_mint])

    # ── internal helpers ─────────────────────────────────────────────

    def _rpc_call(
        self,
        method: str,
        params: List[Any],
    ) -> Optional[Dict[str, Any]]:
        """Execute a JSON-RPC call against the Alchemy Solana endpoint."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        data = _http_post_json(self._rpc, payload)
        if data is None:
            return None
        result = data.get("result")
        if result is None:
            error = data.get("error", {})
            log.warning(
                "RPC error for %s: %s", method, error.get("message", "unknown")
            )
            return None
        return {"method": method, "result": result}


# ══════════════════════════════════════════════════════════════════════
# Test / Demo
# ══════════════════════════════════════════════════════════════════════

def _run_tests() -> None:
    """Run internal unit tests for the Solana DeFi connector."""
    passed = 0
    failed = 0

    def check(label: str, condition: bool) -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
        else:
            failed += 1
            log.error("FAIL: %s", label)

    log.info("=== SolanaDefiConnector Tests ===")

    # ── _make_opportunity ────────────────────────────────────────────
    op = _make_opportunity("TEST", "addr1", 1.23, 5000.0, 10000.0, 0.75, "new_launch", 12.5)
    check("opportunity has all keys", all(k in op for k in (
        "token_symbol", "token_address", "price_usd", "liquidity_usd",
        "volume_24h", "confidence", "opportunity_type",
        "estimated_profit_pct", "timestamp",
    )))
    check("opportunity type is new_launch", op["opportunity_type"] == "new_launch")
    check("confidence clamped", 0.0 <= op["confidence"] <= 1.0)
    check("price set", op["price_usd"] == 1.23)

    # ── _make_opportunity confidence clamping ────────────────────────
    op_high = _make_opportunity("X", "a", 1.0, 100, 100, 2.5, "dex_arb", 5.0)
    check("confidence clamped high", op_high["confidence"] <= 1.0)
    op_low = _make_opportunity("Y", "b", 1.0, 100, 100, -0.5, "dex_arb", 5.0)
    check("confidence clamped low", op_low["confidence"] >= 0.0)

    # ── _iso_timestamp ───────────────────────────────────────────────
    ts = _iso_timestamp()
    check("timestamp is ISO8601", "T" in ts and ts.endswith("+00:00"))

    # ── PumpFunScanner confidence heuristic ──────────────────────────
    scanner = PumpFunScanner()
    # High liquidity + volume
    conf_high = scanner._compute_launch_confidence(
        {"social": {"twitter": "@test"}}, 5000.0, 50_000.0
    )
    check("high confidence token", 0.7 <= conf_high <= 1.0)
    # Low liquidity + volume
    conf_low = scanner._compute_launch_confidence({}, 10.0, 0.0)
    check("low confidence token", 0.0 <= conf_low <= 0.5)

    # ── JupiterDexQuoter route summary ───────────────────────────────
    quoter = JupiterDexQuoter()
    route_plan = [
        {"swapInfo": {"ammKey": "amm1", "label": "Orca"}},
        {"swapInfo": {"ammKey": "amm2", "label": "Raydium"}},
    ]
    summary = quoter._summarise_route(route_plan)
    check("route summary length", len(summary) == 2)
    check("first hop dex", summary[0]["dex"] == "Orca")

    # ── JupiterDexQuoter arb confidence ──────────────────────────────
    arb_conf = quoter._compute_arb_confidence(50, 0.5)
    check("arb confidence range", 0.0 <= arb_conf <= 1.0)
    arb_conf_high = quoter._compute_arb_confidence(500, 0.1)
    check("high spread = higher conf", arb_conf_high > arb_conf)

    # ── SolanaDefiScanner constructor ────────────────────────────────
    combined = SolanaDefiScanner()
    check("combined scanner has pump scanner", hasattr(combined, "_pump"))
    check("combined scanner has jupiter quoter", hasattr(combined, "_jupiter"))
    check("combined scanner has raydium scanner", hasattr(combined, "_raydium"))

    # ── RPC URL construction ─────────────────────────────────────────
    check("default alchemy rpc set", combined._rpc == DEFAULT_ALCHEMY_RPC)

    # ── Results ──────────────────────────────────────────────────────
    log.info("─" * 40)
    log.info("Results: %d passed, %d failed", passed, failed)
    if failed > 0:
        log.error("SOME TESTS FAILED")
    else:
        log.info("ALL TESTS PASSED")


def main() -> None:
    """Entry point for testing this module."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _run_tests()


if __name__ == "__main__":
    main()
