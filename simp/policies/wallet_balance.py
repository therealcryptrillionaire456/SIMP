"""
SIMP Wallet Balance Fetcher
============================

Fetches real account balances from connected exchanges and wallets,
converts everything to USD, and returns total portfolio value.

This is used by TradingPolicy to set risk limits against actual capital,
not a hardcoded placeholder.

Supported sources (checked in order, all optional):
    1. Coinbase (USD, BTC, ETH, SOL, ETH) via existing CoinbaseConnector
    2. Alpaca (USD cash) via REST
    3. Solana wallet (SOL balance via public RPC — no key needed for read)
    4. Manual override via SIMP_STARTING_CAPITAL_USD env var

Credential env vars consumed (same names as quantumarb_agent_phase4):
    COINBASE_API_KEY  /  COINBASE_PRODUCTION_API_KEY  /  COINBASE_LIVE_API_KEY
    COINBASE_API_SECRET  /  COINBASE_PRODUCTION_API_SECRET  /  COINBASE_API_PRIVATE_KEY
    COINBASE_API_PASSPHRASE  /  COINBASE_PRODUCTION_PASSPHRASE
    ALPACA_API_KEY  /  ALPACA_LIVE_API_KEY
    ALPACA_SECRET_KEY  /  ALPACA_LIVE_SECRET_KEY
    SOLANA_WALLET_ADDRESS  (public address — read-only RPC, no private key)

Usage:
    from simp.policies.wallet_balance import fetch_portfolio_usd, BalanceReport

    report = fetch_portfolio_usd()
    print(report.total_usd)          # e.g. 847.32
    print(report.breakdown)          # per-source detail
    print(report.is_live_account)    # True = production, False = sandbox/unverified
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("simp.policies.wallet_balance")

# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class SourceBalance:
    source: str           # e.g. "coinbase", "alpaca", "solana_rpc"
    currency: str         # e.g. "USD", "BTC", "SOL"
    native_amount: float  # amount in the native currency
    usd_value: float      # converted to USD
    price_used: float     # price per unit in USD (1.0 for USD)
    is_live: bool         # True = real exchange, False = sandbox / estimate
    error: Optional[str] = None  # populated if fetch failed


@dataclass
class BalanceReport:
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sources: List[SourceBalance] = field(default_factory=list)
    total_usd: float = 0.0
    is_live_account: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def breakdown(self) -> Dict[str, float]:
        return {f"{s.source}:{s.currency}": s.usd_value for s in self.sources if not s.error}

    def summary_str(self) -> str:
        lines = [
            f"Portfolio total: ${self.total_usd:.2f} USD  "
            f"({'LIVE' if self.is_live_account else 'SANDBOX/PAPER'})",
            f"Fetched at: {self.fetched_at}",
        ]
        for s in self.sources:
            if s.error:
                lines.append(f"  ✗ {s.source}:{s.currency} — ERROR: {s.error}")
            else:
                lines.append(
                    f"  ✓ {s.source}:{s.currency}  "
                    f"{s.native_amount:.6g} × ${s.price_used:.2f} = ${s.usd_value:.2f}"
                )
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env_first(*names: str) -> str:
    """Return first non-empty env var from the list."""
    for name in names:
        v = os.environ.get(name, "").strip()
        if v:
            return v
    return ""


def _simple_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> dict:
    """Minimal HTTP GET returning parsed JSON. Raises on error."""
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Price fetcher (public endpoints, no auth required)
# ---------------------------------------------------------------------------

def _spot_price_usd(symbol: str) -> Optional[float]:
    """
    Fetch spot price in USD for a crypto symbol.
    Tries Coinbase public ticker first, falls back to CoinGecko.
    Returns None on failure.
    """
    # Coinbase public product ticker
    try:
        data = _simple_get(
            f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot",
            timeout=8,
        )
        amount = data.get("data", {}).get("amount")
        if amount:
            return float(amount)
    except Exception as e:
        log.debug("Coinbase public price failed for %s: %s", symbol, e)

    # CoinGecko fallback (free tier, no key)
    coin_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "USDC": "usd-coin"}
    gecko_id = coin_map.get(symbol.upper())
    if gecko_id:
        try:
            data = _simple_get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={gecko_id}&vs_currencies=usd",
                timeout=8,
            )
            return float(data[gecko_id]["usd"])
        except Exception as e:
            log.debug("CoinGecko price failed for %s: %s", symbol, e)

    return None


# ---------------------------------------------------------------------------
# .env loader that handles multi-line PEM keys
# ---------------------------------------------------------------------------

def _load_env_file(path: str = ".env") -> Dict[str, str]:
    """
    Parse a .env file, correctly handling multi-line values like PEM keys.
    python-dotenv chokes on raw PEM blocks; this handles them properly.
    Returns dict of {VAR_NAME: value}.
    """
    result: Dict[str, str] = {}
    env_path = Path(path)
    if not env_path.exists():
        return result

    current_key: Optional[str] = None
    current_val: List[str] = []
    in_multiline = False

    for raw_line in env_path.read_text(errors="replace").splitlines():
        line = raw_line.rstrip()

        # Continue a multi-line value (PEM block)
        if in_multiline:
            current_val.append(line)
            if line.startswith("-----END"):
                result[current_key] = "\n".join(current_val)
                current_key = None
                current_val = []
                in_multiline = False
            continue

        # Skip comments and blank lines
        if not line or line.startswith("#"):
            continue

        # KEY=VALUE line
        if "=" in line and not line.startswith(" "):
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()

            # Strip surrounding quotes
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]

            # Detect start of PEM multi-line value
            if val.startswith("-----BEGIN"):
                current_key = key
                current_val = [val]
                in_multiline = True
            else:
                result[key] = val

    return result


def _get_coinbase_credentials() -> Tuple[str, str]:
    """
    Return (api_key_name, private_key_pem) for Coinbase Advanced Trade API.
    Loads from env vars first, then falls back to reading .env directly
    (handles multi-line PEM keys that break standard dotenv parsing).
    """
    # Try env vars first (set if loaded by another mechanism)
    key_name = _env_first("COINBASE_API_KEY_NAME")
    private_key = _env_first("COINBASE_API_PRIVATE_KEY")

    if key_name and private_key:
        return key_name, private_key

    # Fall back to reading .env directly
    env_vars = _load_env_file(".env")
    key_name = key_name or env_vars.get("COINBASE_API_KEY_NAME", "")
    private_key = private_key or env_vars.get("COINBASE_API_PRIVATE_KEY", "")

    return key_name, private_key


# ---------------------------------------------------------------------------
# Coinbase Advanced Trade balance fetcher
# ---------------------------------------------------------------------------

def _fetch_coinbase(report: BalanceReport) -> None:
    """
    Fetch USD + crypto balances from Coinbase Advanced Trade API.
    Uses EC key / JWT auth (COINBASE_API_KEY_NAME + COINBASE_API_PRIVATE_KEY).
    Mutates report.
    """
    key_name, private_key = _get_coinbase_credentials()

    if not key_name or not private_key:
        report.warnings.append(
            "Coinbase credentials not found. "
            "Set COINBASE_API_KEY_NAME and COINBASE_API_PRIVATE_KEY in .env."
        )
        return

    try:
        from coinbase.rest import RESTClient  # coinbase-advanced-py
        client = RESTClient(api_key=key_name, api_secret=private_key)

        # get_accounts returns paginated accounts
        resp = client.get_accounts()
        accounts = getattr(resp, "accounts", None) or []

        currencies_to_check = {"USD", "USDC", "BTC", "ETH", "SOL"}

        for account in accounts:
            # account is an object with .currency, .available_balance, .type
            currency = getattr(account, "currency", None) or ""
            if currency.upper() not in currencies_to_check:
                continue

            try:
                avail_obj = getattr(account, "available_balance", None)
                available = float(getattr(avail_obj, "value", 0) or 0)
            except (TypeError, ValueError):
                available = 0.0

            if available < 0.0000001:
                continue  # dust

            currency = currency.upper()
            if currency in ("USD", "USDC"):
                price = 1.0
                usd_val = available
            else:
                price = _spot_price_usd(currency) or 0.0
                usd_val = available * price

            report.sources.append(SourceBalance(
                source="coinbase",
                currency=currency,
                native_amount=available,
                usd_value=usd_val,
                price_used=price,
                is_live=True,  # Advanced Trade API = production account
            ))
            report.is_live_account = True

    except ImportError:
        report.warnings.append(
            "coinbase-advanced-py not installed. "
            "Run: pip install coinbase-advanced-py"
        )
    except Exception as e:
        report.errors.append(f"Coinbase fetch failed: {str(e)[:200]}")
        log.warning("Coinbase balance fetch error: %s", e)


# ---------------------------------------------------------------------------
# Alpaca balance fetcher
# ---------------------------------------------------------------------------

def _fetch_alpaca(report: BalanceReport) -> None:
    """Fetch USD cash balance from Alpaca. Mutates report."""
    api_key = _env_first("ALPACA_API_KEY", "ALPACA_LIVE_API_KEY", "APCA_API_KEY_ID", "APCA_API_KEY")
    secret = _env_first("ALPACA_SECRET_KEY", "ALPACA_LIVE_SECRET_KEY", "APCA_API_SECRET_KEY", "APCA_SECRET_KEY")

    if not api_key or not secret:
        report.warnings.append(
            "Alpaca credentials not found. Set ALPACA_API_KEY and ALPACA_SECRET_KEY."
        )
        return

    is_live = bool(_env_first("ALPACA_LIVE_API_KEY", "APCA_LIVE"))
    base = "https://api.alpaca.markets" if is_live else "https://paper-api.alpaca.markets"

    try:
        data = _simple_get(
            f"{base}/v2/account",
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret,
            },
        )
        cash = float(data.get("cash", 0.0))
        equity = float(data.get("equity", 0.0))
        portfolio_value = float(data.get("portfolio_value", equity or cash))

        report.sources.append(SourceBalance(
            source="alpaca",
            currency="USD",
            native_amount=portfolio_value,
            usd_value=portfolio_value,
            price_used=1.0,
            is_live=is_live,
        ))
        if is_live:
            report.is_live_account = True

    except Exception as e:
        report.errors.append(f"Alpaca fetch failed: {e!s:.120}")
        log.warning("Alpaca balance fetch error: %s", e)


# ---------------------------------------------------------------------------
# Solana on-chain balance (public RPC — read only, no key needed)
# ---------------------------------------------------------------------------

def _fetch_solana(report: BalanceReport) -> None:
    """Fetch SOL balance via public RPC. Mutates report."""
    wallet = _env_first("SOLANA_WALLET_ADDRESS")
    if not wallet or wallet == "your_solana_wallet_address_here":
        return  # Not configured

    rpc_url = _env_first("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com"

    try:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet],
        }).encode()
        req = urllib.request.Request(
            rpc_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        lamports = data.get("result", {}).get("value", 0)
        sol_amount = lamports / 1_000_000_000  # 1 SOL = 1e9 lamports

        if sol_amount < 0.0000001:
            return

        price = _spot_price_usd("SOL") or 0.0
        usd_val = sol_amount * price

        report.sources.append(SourceBalance(
            source="solana_rpc",
            currency="SOL",
            native_amount=sol_amount,
            usd_value=usd_val,
            price_used=price,
            is_live=True,  # mainnet RPC = real balance
        ))
        report.is_live_account = True

    except Exception as e:
        report.errors.append(f"Solana RPC fetch failed: {e!s:.120}")
        log.warning("Solana balance fetch error: %s", e)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def fetch_portfolio_usd(
    include_coinbase: bool = True,
    include_alpaca: bool = True,
    include_solana: bool = True,
) -> BalanceReport:
    """
    Fetch real portfolio value across all configured exchanges/wallets.

    Returns a BalanceReport with total_usd, per-source breakdown,
    and whether any live (non-sandbox) accounts were found.

    Never raises — errors are captured in report.errors.
    """
    report = BalanceReport()

    if include_coinbase:
        _fetch_coinbase(report)
    if include_alpaca:
        _fetch_alpaca(report)
    if include_solana:
        _fetch_solana(report)

    # Sum up all USD values from successful sources
    report.total_usd = sum(s.usd_value for s in report.sources if not s.error)

    # If nothing found, check for manual override
    if report.total_usd <= 0:
        manual = os.environ.get("SIMP_STARTING_CAPITAL_USD", "")
        if manual:
            try:
                report.total_usd = float(manual)
                report.warnings.append(
                    f"No exchange balances fetched. Using manual override: ${report.total_usd:.2f}"
                )
            except ValueError:
                pass

    if report.total_usd <= 0:
        report.warnings.append(
            "No portfolio value could be determined from any source. "
            "Set SIMP_STARTING_CAPITAL_USD as a manual fallback, or check credentials."
        )

    log.info("Portfolio fetch complete: $%.2f USD  live=%s", report.total_usd, report.is_live_account)
    return report
