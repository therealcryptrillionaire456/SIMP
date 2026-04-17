#!/usr/bin/env python3
"""
Seed mock mesh payment channels for trust-score growth testing.

Opens or reuses channels in logs/mesh_payments.db and applies enough payments
to reach a target HTLC count per channel. This is intentionally conservative
and idempotent-ish: repeated runs reuse existing open channels instead of
creating duplicates whenever possible.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from simp.mesh.enhanced_bus import PaymentSettler, ChannelState


DEFAULT_PAIRS = (
    ("quantumarb_primary", "ktc_agent"),
    ("quantumarb_primary", "quantum_intelligence_prime"),
    ("quantum_intelligence_prime", "ktc_agent"),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _find_open_channel(
    settler: PaymentSettler,
    initiator_id: str,
    counterparty_id: str,
) -> Optional[dict]:
    for channel in settler.list_channels(state_filter=ChannelState.OPEN):
        if (
            channel.get("initiator_id") == initiator_id
            and channel.get("counterparty_id") == counterparty_id
        ):
            return channel
    return None


def seed_pair(
    db_path: Path,
    initiator_id: str,
    counterparty_id: str,
    opening_balance: float,
    target_sequence: int,
    payment_amount: float,
) -> dict:
    settler = PaymentSettler(
        agent_id=initiator_id,
        db_path=str(db_path),
        shared_secret=b"mock-payment-seed",
    )

    channel = _find_open_channel(settler, initiator_id, counterparty_id)
    created = False
    if channel is None:
        channel_obj = settler.open_channel(counterparty_id, opening_balance, 0.0)
        channel_id = channel_obj.channel_id
        sequence = channel_obj.sequence
        created = True
    else:
        channel_id = channel["channel_id"]
        sequence = int(channel.get("sequence", 0))

    while sequence < target_sequence:
        ok = settler.pay(
            channel_id=channel_id,
            amount=payment_amount,
            description=f"mock trust seed {sequence + 1}",
        )
        if not ok:
            raise RuntimeError(
                f"Failed to apply payment on {channel_id} ({initiator_id} -> {counterparty_id})"
            )
        sequence += 1

    refreshed = settler.get_channel(channel_id)
    return {
        "channel_id": channel_id,
        "initiator_id": initiator_id,
        "counterparty_id": counterparty_id,
        "created": created,
        "sequence": refreshed.sequence if refreshed else sequence,
        "initiator_balance": refreshed.initiator_balance if refreshed else None,
        "counterparty_balance": refreshed.counterparty_balance if refreshed else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed mock mesh payment channels")
    parser.add_argument(
        "--db-path",
        default=str(_repo_root() / "logs" / "mesh_payments.db"),
        help="Path to shared mesh payments database",
    )
    parser.add_argument(
        "--target-sequence",
        type=int,
        default=3,
        help="Ensure each seeded channel reaches at least this HTLC count",
    )
    parser.add_argument(
        "--opening-balance",
        type=float,
        default=5.0,
        help="Opening initiator balance for new channels",
    )
    parser.add_argument(
        "--payment-amount",
        type=float,
        default=0.25,
        help="Amount for each mock HTLC/payment increment",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Seeding mock payment channels in {db_path}")
    for initiator_id, counterparty_id in DEFAULT_PAIRS:
        result = seed_pair(
            db_path=db_path,
            initiator_id=initiator_id,
            counterparty_id=counterparty_id,
            opening_balance=args.opening_balance,
            target_sequence=args.target_sequence,
            payment_amount=args.payment_amount,
        )
        print(
            f"{result['initiator_id']} -> {result['counterparty_id']}: "
            f"channel={result['channel_id']} created={result['created']} "
            f"sequence={result['sequence']} balances="
            f"{result['initiator_balance']:.2f}/{result['counterparty_balance']:.2f}"
        )


if __name__ == "__main__":
    main()
