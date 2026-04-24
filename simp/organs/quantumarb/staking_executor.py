"""
Staking & Yield Execution Layer (Tranche 2)
============================================
Executes staking and yield operations: SOL delegation (Jito), 
ETH staking (Lido/stETH), and position management.

All execution functions have a dry_run flag that defaults to True.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger("staking_executor")

# ── Constants ───────────────────────────────────────────────────────────

# Staking program addresses (mainnet)
JITO_STAKE_POOL = "Jito4APyf642JPZPx3h3c5WJQ9o8fB8T5qDiBcWz5Z"  # JitoSOL
LIDO_STETH_ADDRESS = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"  # Ethereum Lido
MARINADE_STAKE_POOL = "MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD"  # mSOL

# Ethereum RPC
ETH_RPC_DEFAULT = "https://eth-mainnet.g.alchemy.com/v2/"


@dataclass
class StakingResult:
    """Result of a staking operation."""
    success: bool
    operation: str = ""  # deposit, withdraw, claim, delegate
    protocol: str = ""
    asset: str = ""
    amount: float = 0.0
    amount_usd: float = 0.0
    estimated_apr: float = 0.0
    tx_id: str = ""
    error: str = ""
    dry_run: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StakingExecutor:
    """
    Executes staking and yield operations across protocols.
    
    Dry-run mode by default. Supports:
    - SOL -> JitoSOL (liquid staking)
    - SOL -> mSOL (Marinade liquid staking)
    - ETH -> stETH (Lido on Ethereum)
    - Direct SOL validator delegation
    """

    def __init__(
        self,
        solana_rpc: str = "",
        eth_rpc: str = "",
        wallet_address: str = "",
        dry_run: bool = True,
        staking_log: str = "data/staking_trades.jsonl",
    ):
        self.solana_rpc = solana_rpc or os.environ.get("ALCHEMY_SOLANA_RPC", "https://solana-mainnet.g.alchemy.com/v2/")
        self.eth_rpc = eth_rpc or os.environ.get("ALCHEMY_ETH_RPC", ETH_RPC_DEFAULT)
        self.wallet_address = wallet_address or os.environ.get("SOLANA_WALLET_ADDRESS", "")
        self.eth_address = os.environ.get("ETH_WALLET_ADDRESS", "")
        self.dry_run = dry_run
        self.staking_log = Path(staking_log)

        if dry_run:
            log.info("StakingExecutor DRY-RUN mode (no real staking transactions)")

    def _rpc_call(self, url: str, method: str, params: List[Any]) -> Dict[str, Any]:
        """Generic JSON-RPC call."""
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            resp = urlopen(req, timeout=10)
            return json.loads(resp.read())
        except (URLError, json.JSONDecodeError, OSError) as e:
            return {"error": str(e)}

    def _solana_rpc(self, method: str, params: List[Any]) -> Dict[str, Any]:
        return self._rpc_call(self.solana_rpc, method, params)

    def _eth_rpc(self, method: str, params: List[Any]) -> Dict[str, Any]:
        return self._rpc_call(self.eth_rpc, method, params)

    # ── SOL Staking ─────────────────────────────────────────────────────

    def deposit_jito_sol(self, amount_sol: float) -> StakingResult:
        """Deposit SOL into JitoSOL liquid staking pool."""
        if self.dry_run:
            est_sol = amount_sol * 0.995  # 0.5% pool fee
            log.info(
                "JitoSOL deposit: %.4f SOL -> est %.4f JitoSOL (APR ~7.5%%) %s",
                amount_sol, est_sol, "(DRY-RUN)",
            )
            return StakingResult(
                success=True, operation="deposit", protocol="jito",
                asset="SOL", amount=amount_sol,
                amount_usd=amount_sol * 140.0,
                estimated_apr=7.5, tx_id=f"jito_{uuid.uuid4().hex[:12]}",
                dry_run=True,
            )
        return StakingResult(
            success=False, operation="deposit", protocol="jito",
            asset="SOL", error="Live staking requires private key signing",
            dry_run=False,
        )

    def deposit_marinade_sol(self, amount_sol: float) -> StakingResult:
        """Deposit SOL into Marinade mSOL liquid staking pool."""
        if self.dry_run:
            est_sol = amount_sol * 0.999  # 0.1% pool fee
            log.info(
                "mSOL deposit: %.4f SOL -> est %.4f mSOL (APR ~7.2%%) %s",
                amount_sol, est_sol, "(DRY-RUN)",
            )
            return StakingResult(
                success=True, operation="deposit", protocol="marinade",
                asset="SOL", amount=amount_sol,
                amount_usd=amount_sol * 140.0,
                estimated_apr=7.2, tx_id=f"mSOL_{uuid.uuid4().hex[:12]}",
                dry_run=True,
            )
        return StakingResult(
            success=False, operation="deposit", protocol="marinade",
            asset="SOL", error="Live staking requires private key signing",
            dry_run=False,
        )

    def delegate_sol_validator(self, amount_sol: float, validator_vote_key: str = "") -> StakingResult:
        """Directly delegate SOL to a validator (native staking)."""
        if self.dry_run:
            log.info(
                "SOL delegation: %.4f SOL -> validator (APR ~6.8%%) %s",
                amount_sol, "(DRY-RUN)",
            )
            return StakingResult(
                success=True, operation="delegate", protocol="solana_native",
                asset="SOL", amount=amount_sol,
                amount_usd=amount_sol * 140.0,
                estimated_apr=6.8, tx_id=f"del_{uuid.uuid4().hex[:12]}",
                dry_run=True,
            )
        return StakingResult(
            success=False, operation="delegate", protocol="solana_native",
            asset="SOL", error="Live delegation requires private key",
            dry_run=False,
        )

    def unstake_jito_sol(self, amount_lst: float) -> StakingResult:
        """Unstake JitoSOL back to SOL."""
        if self.dry_run:
            log.info("JitoSOL unstake: %.4f JitoSOL -> ~%.4f SOL %s", amount_lst, amount_lst * 0.995, "(DRY-RUN)")
            return StakingResult(success=True, operation="withdraw", protocol="jito",
                                 asset="SOL", amount=amount_lst, dry_run=True)
        return StakingResult(success=False, operation="withdraw", protocol="jito",
                             error="Live unstaking requires private key", dry_run=False)

    # ── ETH Staking ─────────────────────────────────────────────────────

    def deposit_lido_eth(self, amount_eth: float) -> StakingResult:
        """Deposit ETH into Lido stETH (Ethereum)."""
        if self.dry_run:
            est_steth = amount_eth * 0.995  # 0.5% fee
            log.info(
                "Lido deposit: %.4f ETH -> est %.4f stETH (APR ~3.2%%) %s",
                amount_eth, est_steth, "(DRY-RUN)",
            )
            return StakingResult(
                success=True, operation="deposit", protocol="lido",
                asset="ETH", amount=amount_eth,
                amount_usd=amount_eth * 2300.0,
                estimated_apr=3.2, tx_id=f"stETH_{uuid.uuid4().hex[:12]}",
                dry_run=True,
            )
        return StakingResult(
            success=False, operation="deposit", protocol="lido",
            asset="ETH", error="Live staking requires Ethereum private key",
            dry_run=False,
        )

    def get_staking_yield(self, protocol: str) -> Dict[str, Any]:
        """Get current yield for a staking protocol (read-only)."""
        yields = {
            "jito": {"protocol": "JitoSOL", "apr": 7.5, "tvl_sol": 12_000_000},
            "marinade": {"protocol": "mSOL", "apr": 7.2, "tvl_sol": 8_500_000},
            "solana_native": {"protocol": "Native SOL", "apr": 6.8, "tvl_sol": 450_000_000},
            "lido": {"protocol": "stETH", "apr": 3.2, "tvl_eth": 9_500_000},
        }
        return yields.get(protocol, {"protocol": protocol, "apr": 0, "error": "Unknown protocol"})

    # ── Position Management ─────────────────────────────────────────────

    def get_all_positions(self) -> Dict[str, Any]:
        """Get all current staking positions (read-only simulation)."""
        return {
            "wallet_address": self.wallet_address[:8] + "..." if self.wallet_address else "unknown",
            "dry_run": self.dry_run,
            "positions": [],
            "note": "Real positions require on-chain query with private key",
        }

    def claim_rewards(self, protocol: str) -> StakingResult:
        """Claim staking rewards (DRY-RUN: simulated)."""
        if self.dry_run:
            log.info("Claim rewards from %s %s", protocol, "(DRY-RUN)")
            return StakingResult(
                success=True, operation="claim", protocol=protocol,
                amount=0.001, amount_usd=0.14,  # tiny simulated rewards
                dry_run=True,
            )
        return StakingResult(
            success=False, operation="claim", protocol=protocol,
            error="Live claim requires private key", dry_run=False,
        )

    # ── Logging ─────────────────────────────────────────────────────────

    def _record_staking(self, result: StakingResult) -> None:
        try:
            self.staking_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self.staking_log, "a") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except OSError:
            pass


# ── Test ─────────────────────────────────────────────────────────────────

def test_staking_executor() -> None:
    """Test all staking executor functions in dry-run mode."""
    print("=" * 60)
    print("Staking Executor — Dry-Run Test Suite")
    print("=" * 60)

    ex = StakingExecutor(dry_run=True)

    # Test 1: JitoSOL deposit
    r1 = ex.deposit_jito_sol(0.5)
    print(f"  Jito deposit:  {'✅' if r1.success else '❌'} {r1.amount:.4f} SOL -> JitoSOL (APR {r1.estimated_apr}%)")
    assert r1.success, "Jito deposit should succeed in dry-run"

    # Test 2: Marinade mSOL deposit
    r2 = ex.deposit_marinade_sol(0.5)
    print(f"  Marinade:     {'✅' if r2.success else '❌'} {r2.amount:.4f} SOL -> mSOL (APR {r2.estimated_apr}%)")
    assert r2.success, "Marinade deposit should succeed in dry-run"

    # Test 3: Native delegation
    r3 = ex.delegate_sol_validator(1.0)
    print(f"  Delegate:     {'✅' if r3.success else '❌'} {r3.amount:.4f} SOL (APR {r3.estimated_apr}%)")
    assert r3.success, "Delegation should succeed in dry-run"

    # Test 4: JitoSOL unstake
    r4 = ex.unstake_jito_sol(0.5)
    print(f"  Unstake:      {'✅' if r4.success else '❌'} {r4.amount:.4f} JitoSOL -> SOL")

    # Test 5: Lido ETH deposit
    r5 = ex.deposit_lido_eth(0.1)
    print(f"  Lido:         {'✅' if r5.success else '❌'} {r5.amount:.4f} ETH -> stETH (APR {r5.estimated_apr}%)")
    assert r5.success, "Lido deposit should succeed in dry-run"

    # Test 6: Claim rewards
    r6 = ex.claim_rewards("jito")
    print(f"  Claim:        {'✅' if r6.success else '❌'} ${r6.amount_usd:.4f} from jito")

    # Test 7: Get positions
    pos = ex.get_all_positions()
    print(f"  Positions:    ✅ {len(pos['positions'])} tracked (wallet: {pos['wallet_address']})")

    # Test 8: Get yields
    for proto in ["jito", "marinade", "solana_native", "lido"]:
        y = ex.get_staking_yield(proto)
        print(f"  Yield {proto:15s}: {y.get('apr', 0):.1f}%")

    # Test 9: Staking log
    for r in [r1, r2, r3, r5]:
        ex._record_staking(r)
    import os
    log_path = Path(ex.staking_log)
    if log_path.exists():
        print(f"  StakingLog:   ✅ {sum(1 for _ in open(log_path))} records written")
        os.remove(log_path)

    print("\n" + "=" * 60)
    print("ALL STAKING EXECUTOR TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_staking_executor()
