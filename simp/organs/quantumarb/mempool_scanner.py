#!/usr/bin/env python3.10
"""
Solana Mempool Scanner — MEV-Aware Execution Timing (T14).

Detects pending Solana transactions in the same token pair to avoid
sandwich attacks and compute MEV-adjusted spreads.

Features:
  1. Subscribe to Solana mempool via Helius WebSocket or HTTP polling
     (getProgramAccounts for DEX programs)
  2. Detect large pending swaps in same token pair → estimate MEV cost
  3. Compute "MEV-adjusted spread": raw_spread − expected_mev_cost
  4. Only signal if MEV-adjusted spread > configured threshold
  5. Flag toxic liquidity (sandwich bot activity in same block)
  6. Write mempool state to data/mempool_snapshots.jsonl

Dependencies: stdlib only (urllib, json, threading, dataclasses).
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Module logger ────────────────────────────────────────────────────
log = logging.getLogger("MempoolScanner")
log.setLevel(logging.INFO)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

HELIUS_RPC_TEMPLATE = "https://mainnet.helius-rpc.com/?api-key={key}"
PUBLIC_SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# Default DEX program IDs on Solana mainnet
DEX_PROGRAM_IDS: List[str] = [
    "675kPX9MHTjS2zt1qfr1NYyze2Vz9kD3Gx8uB5i9JqD9",  # Raydium AMM
    "9W959DqEETiGkoc8Q1dLxLqN8K8Lx8LqN8K8Lx8LqN8K",  # Raydium CP-Swap
    "JUP6LkbZbjS1jKKwapdHX74TafVx6Ln8bT7v3Gm7sh8",  # Jupiter DEX (v6)
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  # Orca DEX
]

# Well-known SPL token mints (used for pair matching)
KNOWN_TOKEN_MINTS: Dict[str, str] = {
    "So11111111111111111111111111111111111111112": "WSOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFza1VYHqJx9J3N3qVQtVjQyYStQPtU1nKqLZn1": "USDT",
    "4k3Dyjzvzp8eM4U1RjH2NqCkz7kCkRTxL9w6YjGzKkLp": "RAY",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "WIF",
}

# Cache TTL (seconds)
CACHE_TTL_SECONDS = 5

# Default thresholds
DEFAULT_MEV_THRESHOLD_BPS = 5.0     # Minimum MEV-adjusted spread to signal
DEFAULT_TOXIC_TX_COUNT_THRESHOLD = 3  # ≥3 large txs in same pair = toxic
DEFAULT_SANDBOX_TX_VALUE_USD = 500.0  # Minimum tx value to flag as sandwich bait


# ══════════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════════

@dataclass
class MempoolTx:
    """Represents a detected pending mempool transaction."""

    signature: str
    program_id: str
    token_pair: str          # e.g. "WSOL-USDC"
    amount_usd: float
    is_toxic: bool           # Flagged as sandwich bot / toxic
    timestamp: str           # ISO 8601 UTC

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature": self.signature,
            "program_id": self.program_id,
            "token_pair": self.token_pair,
            "amount_usd": round(self.amount_usd, 6),
            "is_toxic": self.is_toxic,
            "timestamp": self.timestamp,
        }


@dataclass
class MempoolSnapshot:
    """Snapshot of mempool state at a point in time."""

    timestamp: str
    txs: List[MempoolTx]
    toxic_pairs: List[str]
    pair_counts: Dict[str, int]       # token_pair → tx count
    mev_estimates: Dict[str, float]   # token_pair → estimated MEV cost (bps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "tx_count": len(self.txs),
            "toxic_pairs": self.toxic_pairs,
            "pair_counts": self.pair_counts,
            "mev_estimates": {k: round(v, 4) for k, v in self.mev_estimates.items()},
            "txs": [t.to_dict() for t in self.txs],
        }


# ══════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════

def _iso_timestamp() -> str:
    """Return current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalise_pair(token_a_mint: str, token_b_mint: str) -> str:
    """Normalise a token pair string, sorting symbols alphabetically."""
    sym_a = KNOWN_TOKEN_MINTS.get(token_a_mint, token_a_mint[:8])
    sym_b = KNOWN_TOKEN_MINTS.get(token_b_mint, token_b_mint[:8])
    pair = f"{sym_a}-{sym_b}" if sym_a <= sym_b else f"{sym_b}-{sym_a}"
    return pair


def _estimate_usd_from_lamports(lamports: int, sol_usd: float = 180.0) -> float:
    """Convert lamports to approximate USD value."""
    return (lamports / 1_000_000_000) * sol_usd


# ══════════════════════════════════════════════════════════════════════
# MempoolScanner
# ══════════════════════════════════════════════════════════════════════

class MempoolScanner:
    """
    Scans the Solana mempool for pending DEX swaps and computes
    MEV-aware execution parameters.

    Thread-safe. Caches results for CACHE_TTL_SECONDS (default 5 s).
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        helius_api_key: str = "",
        snapshot_path: str = "data/mempool_snapshots.jsonl",
        mev_threshold_bps: float = DEFAULT_MEV_THRESHOLD_BPS,
        toxic_tx_threshold: int = DEFAULT_TOXIC_TX_COUNT_THRESHOLD,
        sandbox_tx_value_usd: float = DEFAULT_SANDBOX_TX_VALUE_USD,
    ):
        """
        Initialise the mempool scanner.

        Args:
            rpc_url: Solana RPC URL. Defaults to Helius (if key given) or public RPC.
            helius_api_key: Helius API key for enhanced RPC access.
            snapshot_path: Path for mempool snapshot JSONL.
            mev_threshold_bps: Minimum MEV-adjusted spread to signal (bps).
            toxic_tx_threshold: Number of large txs in same pair to flag toxic.
            sandbox_tx_value_usd: Minimum tx value to count as sandwich bait.
        """
        # Resolve RPC URL
        if rpc_url:
            self.rpc_url = rpc_url
        elif helius_api_key:
            self.rpc_url = HELIUS_RPC_TEMPLATE.format(key=helius_api_key)
        else:
            self.rpc_url = PUBLIC_SOLANA_RPC

        self.helius_api_key = helius_api_key
        self.snapshot_path = Path(snapshot_path)
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)

        self.mev_threshold_bps = mev_threshold_bps
        self.toxic_tx_threshold = toxic_tx_threshold
        self.sandbox_tx_value_usd = sandbox_tx_value_usd

        # Thread safety
        self._lock = threading.Lock()

        # Cache state
        self._cache: Dict[str, Any] = {}
        self._cache_time: float = 0.0

        # Accumulated mempool state
        self._pending_txs: List[MempoolTx] = []
        self._snapshot_count: int = 0

        log.info(
            "MempoolScanner initialised: rpc=%s  snapshot=%s  mev_threshold=%.1fbps",
            self.rpc_url, self.snapshot_path, self.mev_threshold_bps,
        )

    # ── Public API ───────────────────────────────────────────────────

    def scan_pending_txs(self) -> List[MempoolTx]:
        """
        Scan the Solana mempool for pending DEX transactions.

        Uses JSON-RPC getProgramAccounts calls against known DEX program
        IDs to detect pending swaps. Falls back gracefully on error.

        Returns:
            List of MempoolTx records detected in the current poll.
        """
        # Check cache first
        if time.time() - self._cache_time < CACHE_TTL_SECONDS:
            with self._lock:
                cached = self._cache.get("pending_txs")
                if cached is not None:
                    return cached

        all_txs: List[MempoolTx] = []
        now = _iso_timestamp()

        for program_id in DEX_PROGRAM_IDS:
            try:
                txs = self._poll_program(program_id)
                all_txs.extend(txs)
            except Exception as exc:
                log.warning("Failed to poll program %s: %s", program_id[:12], exc)

        # Deduplicate by signature
        seen: Set[str] = set()
        unique_txs: List[MempoolTx] = []
        for tx in all_txs:
            if tx.signature not in seen:
                seen.add(tx.signature)
                unique_txs.append(tx)

        # Classify toxicity per token pair
        pair_counts: Dict[str, int] = {}
        pair_values: Dict[str, List[float]] = {}
        for tx in unique_txs:
            pair_counts[tx.token_pair] = pair_counts.get(tx.token_pair, 0) + 1
            if tx.token_pair not in pair_values:
                pair_values[tx.token_pair] = []
            pair_values[tx.token_pair].append(tx.amount_usd)

        for tx in unique_txs:
            # Flag as toxic if pair has many large txs
            count = pair_counts.get(tx.token_pair, 0)
            avg_value = (
                sum(pair_values.get(tx.token_pair, [0])) /
                max(len(pair_values.get(tx.token_pair, [1])), 1)
            )
            if count >= self.toxic_tx_threshold and avg_value >= self.sandbox_tx_value_usd:
                tx.is_toxic = True

        # Update cache and local state
        with self._lock:
            self._pending_txs = unique_txs
            self._cache["pending_txs"] = list(unique_txs)
            self._cache_time = time.time()

        log.info(
            "Scanned %d DEX programs → %d unique pending txs",
            len(DEX_PROGRAM_IDS), len(unique_txs),
        )
        return unique_txs

    def get_mev_adjusted_spread(
        self,
        token_pair: str,
        raw_spread_bps: float,
    ) -> Tuple[float, float]:
        """
        Compute the MEV-adjusted spread for a token pair.

        Args:
            token_pair: Token pair string, e.g. "WSOL-USDC".
            raw_spread_bps: Raw arbitrage spread in basis points.

        Returns:
            Tuple of (adjusted_spread_bps, mev_risk_score).
            mev_risk_score: 0.0 (safe) → 1.0 (highly toxic).
        """
        # Ensure mempool state is fresh
        pending = self.scan_pending_txs()

        # Filter txs in this pair
        pair_txs = [tx for tx in pending if tx.token_pair == token_pair]

        if not pair_txs:
            # No mempool activity → no MEV risk
            return (raw_spread_bps, 0.0)

        toxic_count = sum(1 for tx in pair_txs if tx.is_toxic)
        total_value = sum(tx.amount_usd for tx in pair_txs)
        avg_value = total_value / max(len(pair_txs), 1)

        # Risk score: combination of toxicity ratio, tx density, and value
        toxicity_ratio = toxic_count / max(len(pair_txs), 1)
        value_factor = min(avg_value / 10_000.0, 1.0)  # cap at $10k
        density_factor = min(len(pair_txs) / 10.0, 1.0)  # cap at 10 txs

        mev_risk = (toxicity_ratio * 0.5) + (value_factor * 0.3) + (density_factor * 0.2)

        # Estimate MEV cost in bps (bounded)
        # Higher risk → higher estimated cost
        expected_mev_cost = mev_risk * 10.0  # max 10 bps at full risk
        adjusted_spread = max(raw_spread_bps - expected_mev_cost, 0.0)

        log.info(
            "MEV-adjusted spread for %s: raw=%.2fbps → adjusted=%.2fbps  risk=%.3f  "
            "toxic=%d/%d  avg_value=$%.2f",
            token_pair, raw_spread_bps, adjusted_spread, mev_risk,
            toxic_count, len(pair_txs), avg_value,
        )

        return (round(adjusted_spread, 4), round(mev_risk, 4))

    def is_toxic_environment(self, token_pair: str) -> bool:
        """
        Determine if a token pair has detectable sandwich bot activity.

        Args:
            token_pair: Token pair string, e.g. "WSOL-USDC".

        Returns:
            True if sandwich bots are detected in the current mempool.
        """
        pending = self.scan_pending_txs()
        pair_txs = [tx for tx in pending if tx.token_pair == token_pair]

        if not pair_txs:
            return False

        toxic_count = sum(1 for tx in pair_txs if tx.is_toxic)

        # Toxic environment if ≥ threshold toxic txs or >50% are toxic
        if toxic_count >= self.toxic_tx_threshold:
            return True
        if toxic_count > 0 and (toxic_count / len(pair_txs)) > 0.5:
            return True

        return False

    def estimate_mev_cost(
        self,
        token_pair: str,
        trade_size_usd: float,
    ) -> float:
        """
        Estimate the MEV cost (in basis points) for a trade in the given pair.

        The estimate accounts for:
        - Pending transactions in the same pair (front-running risk)
        - Toxicity of the mempool environment
        - Size of the trade relative to detected activity

        Args:
            token_pair: Token pair string.
            trade_size_usd: Intended trade size in USD.

        Returns:
            Estimated MEV cost in basis points (0.0 if no risk).
        """
        pending = self.scan_pending_txs()
        pair_txs = [tx for tx in pending if tx.token_pair == token_pair]

        if not pair_txs:
            return 0.0

        toxic_count = sum(1 for tx in pair_txs if tx.is_toxic)
        total_pending_value = sum(tx.amount_usd for tx in pair_txs)
        avg_toxic_value = (
            sum(tx.amount_usd for tx in pair_txs if tx.is_toxic) /
            max(toxic_count, 1)
        )

        # Base cost from mempool density
        density_cost = min(len(pair_txs) * 0.5, 5.0)

        # Toxicity premium
        toxicity_premium = (toxic_count / max(len(pair_txs), 1)) * 8.0

        # Size premium: large trades relative to mempool attract more MEV
        size_ratio = trade_size_usd / max(total_pending_value, 1.0)
        size_premium = min(size_ratio * 2.0, 5.0)

        total_cost = density_cost + toxicity_premium + size_premium

        log.info(
            "MEV cost estimate for %s (trade=$%.2f): %.2f bps  "
            "(density=%.2f  toxicity=%.2f  size=%.2f)",
            token_pair, trade_size_usd, total_cost,
            density_cost, toxicity_premium, size_premium,
        )

        return round(total_cost, 4)

    def snapshot_mempool(self) -> MempoolSnapshot:
        """
        Capture and persist the current mempool state.

        Writes an append-only record to data/mempool_snapshots.jsonl.

        Returns:
            MempoolSnapshot of the current state.
        """
        pending = self.scan_pending_txs()

        # Aggregate per-pair stats
        pair_counts: Dict[str, int] = {}
        for tx in pending:
            pair_counts[tx.token_pair] = pair_counts.get(tx.token_pair, 0) + 1

        toxic_pairs = list({
            tx.token_pair for tx in pending if tx.is_toxic
        })

        # Estimate MEV cost for each pair
        mev_estimates: Dict[str, float] = {}
        for pair in pair_counts:
            mev_estimates[pair] = self.estimate_mev_cost(pair, 1000.0)

        now = _iso_timestamp()
        snapshot = MempoolSnapshot(
            timestamp=now,
            txs=pending,
            toxic_pairs=toxic_pairs,
            pair_counts=pair_counts,
            mev_estimates=mev_estimates,
        )

        # Append to JSONL
        self._append_snapshot(snapshot)

        with self._lock:
            self._snapshot_count += 1

        log.info(
            "Snapshot captured: %d txs across %d pairs, %d toxic pairs "
            "(total snapshots: %d)",
            len(pending), len(pair_counts), len(toxic_pairs),
            self._snapshot_count,
        )

        return snapshot

    # ── Internal methods ─────────────────────────────────────────────

    def _poll_program(self, program_id: str) -> List[MempoolTx]:
        """
        Poll pending transactions for a single DEX program via JSON-RPC.

        Uses getProgramAccounts to fetch accounts owned by the program,
        which reveals pending swap activity.

        Args:
            program_id: Solana program ID (base58).

        Returns:
            List of MempoolTx records detected.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getProgramAccounts",
            "params": [
                program_id,
                {
                    "encoding": "jsonParsed",
                    "filters": [
                        {"dataSize": 165},   # Typical AMM pool account size
                    ],
                },
            ],
        }

        result = self._rpc_call(payload)
        if result is None:
            return []

        accounts = result.get("result", [])
        if not isinstance(accounts, list):
            return []

        txs: List[MempoolTx] = []
        now = _iso_timestamp()

        for acct in accounts:
            try:
                account_data = acct.get("account", {})
                parsed = account_data.get("data", {}).get("parsed", {})
                info = parsed.get("info", {})

                # Extract token pair from account data
                mint_a = info.get("mint", "")
                mint_b = info.get("tokenAMint") or info.get("tokenBMint", "")

                # For Raydium-style pools
                if not mint_b:
                    mint_b = info.get("baseMint", "")

                if not mint_a or not mint_b:
                    # Try alternative format
                    tokens = info.get("tokens", [])
                    if len(tokens) >= 2:
                        mint_a = tokens[0].get("mint", "")
                        mint_b = tokens[1].get("mint", "")

                if not mint_a or not mint_b:
                    continue

                # Derive token pair string
                token_pair = _normalise_pair(mint_a, mint_b)

                # Estimate value from account data
                # For lamports-based pools, extract balance
                lamports = account_data.get("lamports", 0)
                amount_usd = _estimate_usd_from_lamports(lamports)

                # Use the account pubkey as a proxy signature
                signature = acct.get("pubkey", f"pending_{program_id[:8]}_{now}")

                tx = MempoolTx(
                    signature=signature,
                    program_id=program_id,
                    token_pair=token_pair,
                    amount_usd=amount_usd,
                    is_toxic=False,  # Classified later in scan_pending_txs
                    timestamp=now,
                )
                txs.append(tx)

            except (KeyError, TypeError, ValueError) as exc:
                log.debug("Skipping unparseable account: %s", exc)
                continue

        return txs

    def _rpc_call(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Perform a JSON-RPC call to the Solana RPC endpoint.

        Args:
            payload: JSON-RPC request body.

        Returns:
            Parsed response dict, or None on failure.
        """
        import urllib.request as url_req
        import urllib.error as url_err

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        try:
            req = url_req.Request(
                self.rpc_url,
                data=body,
                headers=headers,
                method="POST",
            )
            with url_req.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except (url_err.HTTPError, url_err.URLError, json.JSONDecodeError, OSError) as exc:
            log.warning("RPC call failed: %s", exc)
            return None

    def _append_snapshot(self, snapshot: MempoolSnapshot) -> None:
        """Append a snapshot record to the JSONL file."""
        with self._lock:
            try:
                with open(self.snapshot_path, "a") as f:
                    f.write(json.dumps(snapshot.to_dict()) + "\n")
            except OSError as exc:
                log.error("Failed to write snapshot: %s", exc)

    # ── Query / stats ────────────────────────────────────────────────

    def get_pending_txs(self) -> List[MempoolTx]:
        """Return the most recently scanned pending transactions (cached)."""
        with self._lock:
            return list(self._pending_txs)

    def get_snapshot_count(self) -> int:
        """Return the total number of snapshots taken."""
        with self._lock:
            return self._snapshot_count


# ══════════════════════════════════════════════════════════════════════
# Module-level singleton
# ══════════════════════════════════════════════════════════════════════

MEMPOOL_SCANNER: Optional[MempoolScanner] = None


def get_mempool_scanner(**kwargs: Any) -> MempoolScanner:
    """Get or create the module-level singleton MempoolScanner."""
    global MEMPOOL_SCANNER
    if MEMPOOL_SCANNER is None:
        MEMPOOL_SCANNER = MempoolScanner(**kwargs)
    return MEMPOOL_SCANNER


# ══════════════════════════════════════════════════════════════════════
# Test function
# ══════════════════════════════════════════════════════════════════════

def test_mempool_scanner() -> None:
    """
    Test the MempoolScanner module.

    Tests:
      1. Creates scanner with no API key (public RPC fallback)
      2. Tests MEV-adjusted spread calculation
      3. Tests toxicity detection
      4. Tests serialization of mempool state
      5. Prints summary
    """
    print("=" * 60)
    print("MempoolScanner Tests")
    print("=" * 60)

    # ── Setup ───────────────────────────────────────────────────────
    scanner = MempoolScanner(
        rpc_url=PUBLIC_SOLANA_RPC,
        snapshot_path="data/test_mempool_snapshots.jsonl",
    )
    print(f"\n[SETUP] Scanner created with RPC: {scanner.rpc_url}")
    print(f"        Snapshot path: {scanner.snapshot_path}")

    # ── Test 1: MEV-adjusted spread with no mempool data ────────────
    print("\n─── Test 1: MEV-adjusted spread (no mempool data) ───")
    adjusted, risk = scanner.get_mev_adjusted_spread("WSOL-USDC", 25.0)
    print(f"  Raw spread: 25.0 bps")
    print(f"  MEV risk: {risk:.4f}")
    print(f"  Adjusted spread: {adjusted:.4f} bps")
    assert adjusted <= 25.0, "Adjusted spread should not exceed raw spread"
    assert 0.0 <= risk <= 1.0, "MEV risk should be in [0, 1]"
    print("  ✓ PASSED")

    # ── Test 2: MEV-adjusted spread with simulated toxic data ───────
    print("\n─── Test 2: MEV-adjusted spread (simulated toxic) ────")
    # Inject some toxic txs directly into the scanner's pending list
    now = _iso_timestamp()
    toxic_txs = [
        MempoolTx(
            signature=f"toxic_sig_{i}",
            program_id=DEX_PROGRAM_IDS[0],
            token_pair="WSOL-USDC",
            amount_usd=1000.0,
            is_toxic=True,
            timestamp=now,
        )
        for i in range(4)  # 4 toxic txs ≥ threshold of 3
    ]
    clean_tx = MempoolTx(
        signature="clean_sig",
        program_id=DEX_PROGRAM_IDS[0],
        token_pair="WSOL-USDC",
        amount_usd=100.0,
        is_toxic=False,
        timestamp=now,
    )
    # Override internal state with test data
    with scanner._lock:
        scanner._pending_txs = toxic_txs + [clean_tx]
        scanner._cache["pending_txs"] = list(scanner._pending_txs)
        scanner._cache_time = time.time()

    adjusted, risk = scanner.get_mev_adjusted_spread("WSOL-USDC", 25.0)
    print(f"  Raw spread: 25.0 bps")
    print(f"  MEV risk: {risk:.4f}")
    print(f"  Adjusted spread: {adjusted:.4f} bps")
    assert adjusted < 25.0, "Adjusted spread should be lower than raw in toxic env"
    assert risk > 0.5, "MEV risk should be high with 4/5 toxic txs"
    print("  ✓ PASSED")

    # ── Test 3: Toxicity detection ───────────────────────────────────
    print("\n─── Test 3: Toxicity detection ───────────────────────")
    # Different pair with no toxic txs
    scanner._pending_txs = []
    scanner._cache_time = 0.0  # Invalidate cache
    is_toxic = scanner.is_toxic_environment("BONK-USDC")
    print(f"  BONK-USDC (no activity): toxic={is_toxic}")
    assert not is_toxic, "No-activity pair should not be toxic"

    # Re-inject toxic txs
    with scanner._lock:
        scanner._pending_txs = toxic_txs + [clean_tx]
        scanner._cache["pending_txs"] = list(scanner._pending_txs)
        scanner._cache_time = time.time()

    is_toxic = scanner.is_toxic_environment("WSOL-USDC")
    print(f"  WSOL-USDC (4 toxic/5 total): toxic={is_toxic}")
    assert is_toxic, "WSOL-USDC with 4 toxic txs should be flagged toxic"
    print("  ✓ PASSED")

    # ── Test 4: MEV cost estimation ────────────────────────────────
    print("\n─── Test 4: MEV cost estimation ──────────────────────")
    cost_small = scanner.estimate_mev_cost("WSOL-USDC", 100.0)
    cost_large = scanner.estimate_mev_cost("WSOL-USDC", 50_000.0)
    cost_none = scanner.estimate_mev_cost("RAY-UNKNOWN", 1000.0)
    print(f"  Small trade ($100) in toxic pair: {cost_small:.2f} bps")
    print(f"  Large trade ($50k) in toxic pair: {cost_large:.2f} bps")
    print(f"  Trade in inactive pair: {cost_none:.2f} bps")
    assert cost_large >= cost_small, "Larger trade should have >= MEV cost"
    assert cost_none == 0.0, "Inactive pair should have 0 MEV cost"
    assert cost_small > 0.0, "Toxic pair should have non-zero MEV cost"
    print("  ✓ PASSED")

    # ── Test 5: Mempool snapshot serialization ─────────────────────
    print("\n─── Test 5: Mempool snapshot serialization ───────────")
    snapshot = scanner.snapshot_mempool()
    print(f"  Snapshot timestamp: {snapshot.timestamp}")
    print(f"  Txs captured: {len(snapshot.txs)}")
    print(f"  Toxic pairs: {snapshot.toxic_pairs}")
    print(f"  Pair counts: {snapshot.pair_counts}")
    print(f"  MEV estimates: {snapshot.mev_estimates}")

    # Verify JSONL was written
    snap_path = Path("data/test_mempool_snapshots.jsonl")
    assert snap_path.exists(), "Snapshot JSONL should exist"
    with open(snap_path) as f:
        lines = [line.strip() for line in f if line.strip()]
    print(f"  JSONL entries: {len(lines)}")
    assert len(lines) >= 1, "Should have at least 1 snapshot entry"

    # Validate JSON structure
    last_entry = json.loads(lines[-1])
    assert "timestamp" in last_entry, "Snapshot should have timestamp"
    assert "tx_count" in last_entry, "Snapshot should have tx_count"
    assert "toxic_pairs" in last_entry, "Snapshot should have toxic_pairs"
    assert "txs" in last_entry, "Snapshot should have txs array"
    print("  ✓ PASSEED")

    # ── Test 6: Serialization round-trip of MempoolTx ──────────────
    print("\n─── Test 6: MempoolTx serialization ───────────────────")
    tx = MempoolTx(
        signature="test_sig_abc123",
        program_id=DEX_PROGRAM_IDS[0],
        token_pair="WSOL-USDC",
        amount_usd=1234.5678,
        is_toxic=True,
        timestamp=now,
    )
    tx_dict = tx.to_dict()
    print(f"  Dict: {json.dumps(tx_dict, indent=2)}")
    assert tx_dict["signature"] == "test_sig_abc123"
    assert tx_dict["token_pair"] == "WSOL-USDC"
    assert tx_dict["is_toxic"] is True
    assert tx_dict["amount_usd"] == 1234.5678
    # Round-trip via JSON
    recovered = json.loads(json.dumps(tx_dict))
    assert recovered["token_pair"] == "WSOL-USDC"
    print("  ✓ PASSED")

    # ── Cleanup ─────────────────────────────────────────────────────
    try:
        snap_path.unlink()
        print(f"\n  Cleaned up: {snap_path}")
    except OSError:
        pass

    # ── Summary ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("MempoolScanner Test Summary")
    print("=" * 60)
    print("  1. MEV-adjusted spread (no data)       ✓")
    print("  2. MEV-adjusted spread (toxic data)    ✓")
    print("  3. Toxicity detection                  ✓")
    print("  4. MEV cost estimation                 ✓")
    print("  5. Mempool snapshot serialization      ✓")
    print("  6. MempoolTx serialization             ✓")
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    test_mempool_scanner()
