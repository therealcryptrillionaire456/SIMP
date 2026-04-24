#!/usr/bin/env python3.10
"""
Solana On-Chain Execution Layer for QuantumArb — Tranche 1.

Reads opportunities detected by solana_defi_connector scanners
(PumpFunDetector / JupiterDexQuoter / SolanaDefiScanner) and
executes them via Jupiter DEX swaps or direct transfers.

THIS IS A DRY-RUN ONLY EXECUTOR.
All execution methods default to dry_run=True and return simulated
results. Setting dry_run=False requires a live private key and is
intended for testnet/sandbox use only.

Dependencies: stdlib only (urllib, json, pathlib, threading).
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Imports from sibling scanner module ──────────────────────────────
from .solana_defi_connector import (
    JupiterDexQuoter,
    PumpFunScanner as PumpFunDetector,
    SolanaDefiScanner,
    JUPITER_QUOTE_API,
    JUPITER_PRICE_API,
    WSOL_MINT,
    USDC_MINT,
    USDT_MINT,
    _http_get,
    _http_post_json,
    _iso_timestamp,
    log as scanner_log,
)

# ── Module logger ────────────────────────────────────────────────────
log = logging.getLogger("SolanaExecutor")
log.setLevel(logging.INFO)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

PLACEHOLDER_RPC = "https://solana-mainnet.g.alchemy.com/v2/demo"
PLACEHOLDER_WALLET = "PlaceholderWalletAddress1111111111111111111111"

DEFAULT_SLIPPAGE_BPS = 100       # 1 %
MAX_SOL_TRANSFER_AMOUNT = 10.0   # safety cap for dry-run

# Standard result keys
RESULT_KEYS = [
    "success", "tx_id", "error", "symbol", "amount_usd", "timestamp",
]


# ══════════════════════════════════════════════════════════════════════
# Standalone helpers
# ══════════════════════════════════════════════════════════════════════

def _make_result(
    success: bool,
    tx_id: str = "",
    error: str = "",
    symbol: str = "",
    amount_usd: float = 0.0,
    timestamp: str = "",
) -> Dict[str, Any]:
    """Build a standardised execution result dict."""
    if not timestamp:
        timestamp = _iso_timestamp()
    return {
        "success": success,
        "tx_id": tx_id,
        "error": error,
        "symbol": symbol,
        "amount_usd": round(amount_usd, 6),
        "timestamp": timestamp,
    }


def get_jupiter_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 100,
) -> Dict[str, Any]:
    """
    Standalone quote fetcher for Jupiter DEX v6.

    Parameters
    ----------
    input_mint : str
        Mint address of the input token.
    output_mint : str
        Mint address of the output token.
    amount : int
        Amount in the smallest unit (e.g. lamports for SOL).
    slippage_bps : int
        Allowed slippage in basis points (default 100 = 1 %).

    Returns
    -------
    dict
        Jupiter quote result with keys: success, input_mint, output_mint,
        amount_in, amount_out, price, route_summary, error, price_impact_pct.
    """
    quoter = JupiterDexQuoter(
        quote_api_url=JUPITER_QUOTE_API,
        price_api_url=JUPITER_PRICE_API,
    )
    return quoter.get_quote(
        input_mint=input_mint,
        output_mint=output_mint,
        amount=amount,
        slippage_bps=slippage_bps,
    )


# ══════════════════════════════════════════════════════════════════════
# SolanaTradeHistory
# ══════════════════════════════════════════════════════════════════════

class SolanaTradeHistory:
    """
    Append-only JSONL ledger for Solana trade records.

    Thread-safe. Each record is written immediately to disk.
    """

    def __init__(self, path: str = "data/solana_trades.jsonl"):
        self._lock = threading.Lock()
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, result: Dict[str, Any]) -> None:
        """
        Append one trade result to the JSONL ledger.

        Parameters
        ----------
        result : dict
            Must contain at minimum the keys in RESULT_KEYS.
        """
        # Ensure all standard keys are present
        entry = {}
        for k in RESULT_KEYS:
            entry[k] = result.get(k, "" if k != "amount_usd" else 0.0)
        # Carry forward any extra metadata
        for k, v in result.items():
            if k not in entry:
                entry[k] = v
        # Ensure timestamp is set
        if not entry.get("timestamp"):
            entry["timestamp"] = _iso_timestamp()

        with self._lock:
            with open(self._path, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def get_stats(self) -> Dict[str, Any]:
        """
        Compute summary statistics from the trade ledger.

        Returns
        -------
        dict
            Keys: total_trades, successful, failed, total_volume_usd,
            oldest_trade, newest_trade.
        """
        trades: List[Dict[str, Any]] = []
        if self._path.exists():
            with self._lock:
                with open(self._path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                trades.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue

        total = len(trades)
        successful = sum(1 for t in trades if t.get("success"))
        failed = total - successful
        total_volume = sum(
            float(t.get("amount_usd", 0) or 0) for t in trades if t.get("success")
        )
        timestamps = [
            t.get("timestamp", "") for t in trades if t.get("timestamp")
        ]

        return {
            "total_trades": total,
            "successful": successful,
            "failed": failed,
            "total_volume_usd": round(total_volume, 6),
            "oldest_trade": min(timestamps) if timestamps else "",
            "newest_trade": max(timestamps) if timestamps else "",
        }

    def get_all_trades(self) -> List[Dict[str, Any]]:
        """Return all trade records from the ledger."""
        trades: List[Dict[str, Any]] = []
        if self._path.exists():
            with self._lock:
                with open(self._path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                trades.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
        return trades


# ══════════════════════════════════════════════════════════════════════
# SolanaExecutor
# ══════════════════════════════════════════════════════════════════════

class SolanaExecutor:
    """
    On-chain Solana transaction executor.

    All execution methods default to dry_run=True and return simulated
    results. No real assets are moved in dry-run mode.

    Parameters
    ----------
    rpc_url : str
        Alchemy/Helius RPC URL for on-chain queries.
    dry_run : bool
        When True (default), all execution is simulated.
    wallet_address : str
        Public wallet address (used for balance queries).
    """

    RPC_URL = PLACEHOLDER_RPC

    # Simulated fee schedule (lamports)
    SIM_TX_FEE_LAMPORTS = 5_000  # ~0.000005 SOL

    def __init__(
        self,
        rpc_url: str = "",
        dry_run: bool = True,
        wallet_address: str = PLACEHOLDER_WALLET,
    ):
        self.rpc_url = rpc_url or self.RPC_URL
        self.dry_run = dry_run
        self.wallet_address = wallet_address
        self._jupiter_quoter = JupiterDexQuoter(
            quote_api_url=JUPITER_QUOTE_API,
            price_api_url=JUPITER_PRICE_API,
        )
        self._scanner = SolanaDefiScanner(alchemy_rpc=self.rpc_url)
        self._history = SolanaTradeHistory()

        log.info(
            "SolanaExecutor initialised — dry_run=%s, rpc=%s",
            dry_run,
            self.rpc_url,
        )

    # ── Public Execution API ─────────────────────────────────────────

    def execute_jupiter_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: float,
        slippage_bps: int = 100,
        symbol: str = "",
    ) -> Dict[str, Any]:
        """
        Execute a swap via Jupiter DEX v6.

        DRY-RUN: Quotes the route via the Jupiter API and logs the result.
        Returns a simulated success with a fake tx_id.

        Parameters
        ----------
        input_mint : str
            Mint address of the token to sell.
        output_mint : str
            Mint address of the token to buy.
        amount : float
            Amount in whole tokens (e.g. 0.1 SOL).
        slippage_bps : int
            Allowed slippage in basis points (default 100 = 1 %).
        symbol : str
            Optional human-readable symbol for the result.

        Returns
        -------
        dict
            Standardised result dict with keys listed in RESULT_KEYS.
        """
        # Convert whole-token amount to smallest unit (lamports for SOL)
        lamports = int(amount * 1_000_000_000)

        # Attempt a real quote (will be None on network error)
        quote = self._jupiter_quoter.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=lamports,
            slippage_bps=slippage_bps,
        )

        if quote and quote.get("success"):
            out_amount = quote.get("amount_out", 0)
            price_impact = quote.get("price_impact_pct", 0.0)
            route_summary = quote.get("route_summary", [])
            log.info(
                "Jupiter quote: in=%d, out=%d, impact=%.4f%%, hops=%d",
                lamports, out_amount, price_impact, len(route_summary),
            )
        else:
            # Simulated fallback for dry-run / offline
            log.info(
                "Jupiter quote unavailable (dry-run mode). "
                "Simulating swap: %d lamports %s -> %s",
                lamports, input_mint[:8], output_mint[:8],
            )

        if self.dry_run:
            ts = _iso_timestamp()
            fake_tx = f"dryrun_jupiter_{int(time.time())}_{input_mint[:8]}"
            log.info(
                "[DRY-RUN] execute_jupiter_swap: %f %s -> %s | tx=%s",
                amount, input_mint[:8], output_mint[:8], fake_tx,
            )
            result = _make_result(
                success=True,
                tx_id=fake_tx,
                symbol=symbol or f"{input_mint[:4]}-{output_mint[:4]}",
                amount_usd=_approximate_usd(amount),
                timestamp=ts,
            )
            self._history.record(result)
            return result

        # REAL execution path — requires private key (not implemented)
        return _make_result(
            success=False,
            error="Live execution requires private key — not implemented in this version",
            symbol=symbol,
        )

    def execute_pumpfun_buy(
        self,
        mint_address: str,
        sol_amount: float,
        symbol: str = "",
    ) -> Dict[str, Any]:
        """
        Buy a pump.fun token (DRY-RUN: simulated).

        Parameters
        ----------
        mint_address : str
            Token mint address.
        sol_amount : float
            Amount of SOL to spend.
        symbol : str
            Optional human-readable symbol.

        Returns
        -------
        dict
            Standardised result dict.
        """
        if sol_amount <= 0 or sol_amount > MAX_SOL_TRANSFER_AMOUNT:
            return _make_result(
                success=False,
                error=f"Invalid SOL amount: {sol_amount}. Must be 0 < amount <= {MAX_SOL_TRANSFER_AMOUNT}",
                symbol=symbol or mint_address[:8],
            )

        if self.dry_run:
            ts = _iso_timestamp()
            fake_tx = f"dryrun_pumpfun_buy_{int(time.time())}_{mint_address[:8]}"
            log.info(
                "[DRY-RUN] execute_pumpfun_buy: %f SOL -> %s | tx=%s",
                sol_amount, mint_address[:8], fake_tx,
            )
            result = _make_result(
                success=True,
                tx_id=fake_tx,
                symbol=symbol or f"PUMP:{mint_address[:8]}",
                amount_usd=_approximate_usd(sol_amount),
                timestamp=ts,
            )
            self._history.record(result)
            return result

        return _make_result(
            success=False,
            error="Live pump.fun execution requires private key",
        )

    def execute_pumpfun_sell(
        self,
        mint_address: str,
        token_amount: float,
        symbol: str = "",
    ) -> Dict[str, Any]:
        """
        Sell a pump.fun token (DRY-RUN: simulated).

        Parameters
        ----------
        mint_address : str
            Token mint address.
        token_amount : float
            Amount of tokens to sell.
        symbol : str
            Optional human-readable symbol.

        Returns
        -------
        dict
            Standardised result dict.
        """
        if token_amount <= 0:
            return _make_result(
                success=False,
                error=f"Invalid token amount: {token_amount}. Must be > 0",
                symbol=symbol or mint_address[:8],
            )

        if self.dry_run:
            ts = _iso_timestamp()
            fake_tx = f"dryrun_pumpfun_sell_{int(time.time())}_{mint_address[:8]}"
            log.info(
                "[DRY-RUN] execute_pumpfun_sell: %f tokens %s | tx=%s",
                token_amount, mint_address[:8], fake_tx,
            )
            # Estimate proceeds: assume ~0.01 SOL per token for dry-run
            estimated_proceeds_sol = token_amount * 0.01
            result = _make_result(
                success=True,
                tx_id=fake_tx,
                symbol=symbol or f"PUMP:{mint_address[:8]}",
                amount_usd=_approximate_usd(estimated_proceeds_sol),
                timestamp=ts,
            )
            self._history.record(result)
            return result

        return _make_result(
            success=False,
            error="Live pump.fun execution requires private key",
        )

    def execute_transfer(
        self,
        to_address: str,
        amount_sol: float,
        symbol: str = "SOL",
    ) -> Dict[str, Any]:
        """
        Transfer SOL to another address (DRY-RUN: simulated).

        Parameters
        ----------
        to_address : str
            Destination wallet address.
        amount_sol : float
            Amount of SOL to send.
        symbol : str
            Asset symbol (default "SOL").

        Returns
        -------
        dict
            Standardised result dict.
        """
        if amount_sol <= 0 or amount_sol > MAX_SOL_TRANSFER_AMOUNT:
            return _make_result(
                success=False,
                error=f"Invalid SOL amount: {amount_sol}. Must be 0 < amount <= {MAX_SOL_TRANSFER_AMOUNT}",
                symbol=symbol,
            )

        if not to_address or len(to_address) < 32:
            return _make_result(
                success=False,
                error=f"Invalid destination address: {to_address}",
                symbol=symbol,
            )

        if self.dry_run:
            ts = _iso_timestamp()
            fake_tx = f"dryrun_transfer_{int(time.time())}_{to_address[:8]}"
            log.info(
                "[DRY-RUN] execute_transfer: %f SOL -> %s | tx=%s",
                amount_sol, to_address[:8], fake_tx,
            )
            result = _make_result(
                success=True,
                tx_id=fake_tx,
                symbol=symbol,
                amount_usd=_approximate_usd(amount_sol),
                timestamp=ts,
            )
            self._history.record(result)
            return result

        return _make_result(
            success=False,
            error="Live SOL transfer requires private key",
            symbol=symbol,
        )

    def get_wallet_balance(self) -> Dict[str, Any]:
        """
        Get SOL balance from the RPC endpoint (real, read-only).

        Returns
        -------
        dict
            Keys: success, balance_sol, balance_lamports, address, error, timestamp.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [self.wallet_address],
        }
        data = _http_post_json(self.rpc_url, payload)
        if data is None:
            log.warning("Failed to fetch balance from RPC")
            return {
                "success": False,
                "balance_sol": 0.0,
                "balance_lamports": 0,
                "address": self.wallet_address,
                "error": "RPC request failed",
                "timestamp": _iso_timestamp(),
            }

        result = data.get("result")
        if result is None:
            err = data.get("error", {})
            log.warning("RPC error for getBalance: %s", err.get("message", "unknown"))
            return {
                "success": False,
                "balance_sol": 0.0,
                "balance_lamports": 0,
                "address": self.wallet_address,
                "error": err.get("message", "unknown RPC error"),
                "timestamp": _iso_timestamp(),
            }

        lamports = result.get("value", 0)
        sol = lamports / 1_000_000_000.0
        log.info("Wallet %s balance: %f SOL (%d lamports)", self.wallet_address[:8], sol, lamports)
        return {
            "success": True,
            "balance_sol": round(sol, 9),
            "balance_lamports": lamports,
            "address": self.wallet_address,
            "error": "",
            "timestamp": _iso_timestamp(),
        }

    def scan_and_execute_best_route(
        self,
        scanner_result: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Given scanner results (or run a fresh scan), pick the best
        opportunity and execute it in dry-run mode.

        Selection criteria (in order):
        1. Highest estimated_profit_pct
        2. Highest confidence
        3. First opportunity if ties

        Parameters
        ----------
        scanner_result : list of dict, optional
            Pre-scanned opportunities. If None, runs a fresh scan.

        Returns
        -------
        dict
            Standardised result dict for the chosen opportunity,
            or an error result if no opportunities found.
        """
        if scanner_result is None:
            log.info("No scanner result provided — running fresh scan")
            scanner_result = self._scanner.scan_all_opportunities()

        if not scanner_result:
            log.info("No opportunities available to execute")
            return _make_result(
                success=False,
                error="No opportunities found",
                timestamp=_iso_timestamp(),
            )

        # Sort by profit_pct desc, then confidence desc
        def _sort_key(op: Dict[str, Any]) -> Tuple[float, float]:
            profit = float(op.get("estimated_profit_pct", 0) or 0)
            conf = float(op.get("confidence", 0) or 0)
            return (profit, conf)

        best = max(scanner_result, key=_sort_key)

        log.info(
            "Best opportunity: type=%s, token=%s, profit=%.2f%%, confidence=%.2f",
            best.get("opportunity_type", "unknown"),
            best.get("token_address", "unknown")[:8],
            float(best.get("estimated_profit_pct", 0) or 0),
            float(best.get("confidence", 0) or 0),
        )

        token_address = best.get("token_address", "")
        opportunity_type = best.get("opportunity_type", "unknown")
        token_symbol = best.get("token_symbol", token_address[:8])
        price_usd = float(best.get("price_usd", 0) or 0)

        # Map opportunity type to execution method
        if opportunity_type in ("new_launch", "pumpfun"):
            return self.execute_pumpfun_buy(
                mint_address=token_address,
                sol_amount=0.01,  # conservative dry-run amount
                symbol=token_symbol,
            )
        elif opportunity_type in ("dex_arb", "cross_venue", "jupiter_arb"):
            return self.execute_jupiter_swap(
                input_mint=WSOL_MINT,
                output_mint=token_address,
                amount=0.01,  # conservative dry-run amount
                symbol=token_symbol,
            )
        elif opportunity_type in ("lp_mismatch", "raydium_lp"):
            return self.execute_jupiter_swap(
                input_mint=USDC_MINT,
                output_mint=token_address,
                amount=10.0,  # $10 USDC for LP opportunity
                symbol=token_symbol,
            )
        else:
            # Generic fallback: execute as a Jupiter swap from WSOL
            return self.execute_jupiter_swap(
                input_mint=WSOL_MINT,
                output_mint=token_address,
                amount=0.01,
                symbol=token_symbol,
            )

    # ── Internal Helpers ─────────────────────────────────────────────

    @property
    def history(self) -> SolanaTradeHistory:
        """Access the trade history ledger."""
        return self._history


# ══════════════════════════════════════════════════════════════════════
# Private helpers (module-level)
# ══════════════════════════════════════════════════════════════════════

def _approximate_usd(sol_amount: float, sol_price_usd: float = 180.0) -> float:
    """
    Approximate SOL amount to USD for dry-run display purposes.

    Parameters
    ----------
    sol_amount : float
        Amount in SOL.
    sol_price_usd : float
        Assumed SOL price (default 180 USD).

    Returns
    -------
    float
        Approximate USD value.
    """
    return sol_amount * sol_price_usd


# ══════════════════════════════════════════════════════════════════════
# Test Suite
# ══════════════════════════════════════════════════════════════════════

def test_solana_executor() -> None:
    """
    Run all SolanaExecutor test cases in dry-run mode.

    Tests:
    - _make_result helper
    - SolanaTradeHistory record / get_stats / get_all_trades
    - SolanaExecutor.execute_jupiter_swap (dry-run)
    - SolanaExecutor.execute_pumpfun_buy (dry-run)
    - SolanaExecutor.execute_pumpfun_sell (dry-run)
    - SolanaExecutor.execute_transfer (dry-run)
    - SolanaExecutor.get_wallet_balance (read-only)
    - SolanaExecutor.scan_and_execute_best_route (with synthetic data)
    - SolanaTradeHistory persistence across instances
    """
    passed = 0
    failed = 0

    def check(label: str, condition: bool) -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
        else:
            failed += 1
            log.error("FAIL: %s", label)

    log.info("=== SolanaExecutor Tests ===")

    # ── _make_result ─────────────────────────────────────────────────
    r = _make_result(True, tx_id="abc123", symbol="SOL-USDC", amount_usd=10.0)
    check("_make_result has all keys", all(k in r for k in RESULT_KEYS))
    check("_make_result success=True", r["success"] is True)
    check("_make_result tx_id set", r["tx_id"] == "abc123")
    check("_make_result timestamp set", bool(r["timestamp"]))
    check("_make_result amount_usd rounded", r["amount_usd"] == 10.0)

    r2 = _make_result(False, error="test error")
    check("_make_result failure", r2["success"] is False)
    check("_make_result error msg", r2["error"] == "test error")
    check("_make_result empty tx_id on fail", r2["tx_id"] == "")

    # ── SolanaTradeHistory ──────────────────────────────────────────
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        hist = SolanaTradeHistory(path=tmp_path)
        stats_empty = hist.get_stats()
        check("empty history total=0", stats_empty["total_trades"] == 0)
        check("empty history successful=0", stats_empty["successful"] == 0)

        hist.record({"success": True, "tx_id": "tx1", "symbol": "SOL", "amount_usd": 50.0})
        hist.record({"success": True, "tx_id": "tx2", "symbol": "BTC", "amount_usd": 100.0})
        hist.record({"success": False, "tx_id": "", "error": "fail", "symbol": "ETH", "amount_usd": 0.0})

        stats = hist.get_stats()
        check("3 trades recorded", stats["total_trades"] == 3)
        check("2 successful", stats["successful"] == 2)
        check("1 failed", stats["failed"] == 1)
        check("total volume 150", stats["total_volume_usd"] == 150.0)

        all_trades = hist.get_all_trades()
        check("get_all_trades returns 3", len(all_trades) == 3)

        # Test persistence: new instance reading same file
        hist2 = SolanaTradeHistory(path=tmp_path)
        stats2 = hist2.get_stats()
        check("persistence total=3", stats2["total_trades"] == 3)
        check("persistence volume=150", stats2["total_volume_usd"] == 150.0)

    finally:
        os.unlink(tmp_path)

    # ── SolanaExecutor.execute_jupiter_swap (dry-run) ────────────────
    executor = SolanaExecutor(dry_run=True)
    swap_result = executor.execute_jupiter_swap(
        input_mint=WSOL_MINT,
        output_mint=USDC_MINT,
        amount=0.1,
        symbol="SOL-USDC",
    )
    check("jupiter swap success", swap_result["success"] is True)
    check("jupiter swap has tx_id", bool(swap_result["tx_id"]))
    check("jupiter swap has dryrun prefix", swap_result["tx_id"].startswith("dryrun_"))
    check("jupiter swap symbol set", swap_result["symbol"] == "SOL-USDC")
    check("jupiter swap amount positive", swap_result["amount_usd"] > 0)

    # ── SolanaExecutor.execute_pumpfun_buy (dry-run) ─────────────────
    buy_result = executor.execute_pumpfun_buy(
        mint_address="AbCdEfGhIjKlMnOpQrStUvWxYz12345678901234",
        sol_amount=0.05,
        symbol="MOON",
    )
    check("pumpfun buy success", buy_result["success"] is True)
    check("pumpfun buy tx_id", bool(buy_result["tx_id"]))
    check("pumpfun buy dryrun prefix", buy_result["tx_id"].startswith("dryrun_pumpfun_buy"))
    check("pumpfun buy symbol MOON", buy_result["symbol"] == "MOON")

    # Invalid amount
    bad_buy = executor.execute_pumpfun_buy(
        mint_address="abc", sol_amount=-1.0, symbol="BAD"
    )
    check("pumpfun buy invalid amount fails", bad_buy["success"] is False)
    check("pumpfun buy error message", bool(bad_buy["error"]))

    # ── SolanaExecutor.execute_pumpfun_sell (dry-run) ────────────────
    sell_result = executor.execute_pumpfun_sell(
        mint_address="AbCdEfGhIjKlMnOpQrStUvWxYz12345678901234",
        token_amount=100.0,
        symbol="MOON",
    )
    check("pumpfun sell success", sell_result["success"] is True)
    check("pumpfun sell tx_id", bool(sell_result["tx_id"]))
    check("pumpfun sell dryrun prefix", sell_result["tx_id"].startswith("dryrun_pumpfun_sell"))

    bad_sell = executor.execute_pumpfun_sell(
        mint_address="abc", token_amount=0, symbol="BAD"
    )
    check("pumpfun sell zero amount fails", bad_sell["success"] is False)

    # ── SolanaExecutor.execute_transfer (dry-run) ────────────────────
    transfer_result = executor.execute_transfer(
        to_address="DestinationWalletAddress1111111111111111111",
        amount_sol=0.5,
    )
    check("transfer success", transfer_result["success"] is True)
    check("transfer dryrun prefix", transfer_result["tx_id"].startswith("dryrun_transfer"))
    check("transfer symbol SOL", transfer_result["symbol"] == "SOL")

    bad_transfer = executor.execute_transfer(
        to_address="short", amount_sol=0.5,
    )
    check("transfer short address fails", bad_transfer["success"] is False)

    bad_transfer2 = executor.execute_transfer(
        to_address="ValidAddress111111111111111111111111111111", amount_sol=0.0,
    )
    check("transfer zero amount fails", bad_transfer2["success"] is False)

    # ── SolanaExecutor.get_wallet_balance (read-only) ─────────────────
    balance = executor.get_wallet_balance()
    # This could fail if no RPC available — that's acceptable
    check("balance has keys", all(k in balance for k in (
        "success", "balance_sol", "balance_lamports", "address", "error", "timestamp"
    )))
    check("balance has address", balance["address"] == PLACEHOLDER_WALLET)
    check("balance sol >= 0", balance["balance_sol"] >= 0)
    check("balance lamports >= 0", balance["balance_lamports"] >= 0)

    # ── SolanaExecutor.scan_and_execute_best_route ───────────────────
    # With empty list
    empty_result = executor.scan_and_execute_best_route(scanner_result=[])
    check("empty scan result fails", empty_result["success"] is False)
    check("empty scan error msg", bool(empty_result["error"]))

    # With synthetic opportunities
    synthetic_ops = [
        {
            "token_address": "TokenAlpha111111111111111111111111111111111",
            "token_symbol": "ALPHA",
            "opportunity_type": "dex_arb",
            "estimated_profit_pct": 5.0,
            "confidence": 0.8,
            "price_usd": 1.0,
            "liquidity_usd": 50000.0,
            "volume_24h": 100000.0,
        },
        {
            "token_address": "TokenBeta222222222222222222222222222222222",
            "token_symbol": "BETA",
            "opportunity_type": "new_launch",
            "estimated_profit_pct": 12.0,  # higher profit → should be picked
            "confidence": 0.6,
            "price_usd": 0.5,
            "liquidity_usd": 10000.0,
            "volume_24h": 50000.0,
        },
    ]

    best_result = executor.scan_and_execute_best_route(scanner_result=synthetic_ops)
    check("best route succeeds", best_result["success"] is True)
    check("best route has tx_id", bool(best_result["tx_id"]))

    # ── SolanaTradeHistory records from executor ─────────────────────
    hist_stats = executor.history.get_stats()
    check("executor history has records", hist_stats["total_trades"] > 0)
    check("executor history successful", hist_stats["successful"] > 0)

    # ── Results ──────────────────────────────────────────────────────
    log.info("─" * 40)
    log.info("Results: %d passed, %d failed", passed, failed)
    if failed > 0:
        log.error("SOME TESTS FAILED")
    else:
        log.info("ALL TESTS PASSED")


def main() -> None:
    """Entry point: run dry-run tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    test_solana_executor()


if __name__ == "__main__":
    main()
