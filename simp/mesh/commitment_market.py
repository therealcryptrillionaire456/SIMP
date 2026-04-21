"""
L6 Commitment Market — trust score staking for predictions.

Agents can stake trust points on predictions, settle outcomes later, and use
the resulting performance to influence routing priority.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .trust_graph import TrustGraph, get_trust_graph


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Commitment:
    commitment_id: str
    agent_id: str
    prediction_type: str
    prediction: Dict[str, Any]
    stake_points: float
    confidence: float
    created_at: str = field(default_factory=_utcnow)
    target_time: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "open"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "agent_id": self.agent_id,
            "prediction_type": self.prediction_type,
            "prediction": self.prediction,
            "stake_points": self.stake_points,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "target_time": self.target_time,
            "metadata": self.metadata,
            "status": self.status,
        }


@dataclass
class Settlement:
    commitment_id: str
    agent_id: str
    success: bool
    payout_points: float
    trust_delta: float
    settled_at: str = field(default_factory=_utcnow)
    outcome: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "agent_id": self.agent_id,
            "success": self.success,
            "payout_points": self.payout_points,
            "trust_delta": self.trust_delta,
            "settled_at": self.settled_at,
            "outcome": self.outcome,
        }


class CommitmentMarket:
    """JSONL-backed commitment market with optional TrustGraph integration."""

    def __init__(
        self,
        base_dir: Optional[Path | str] = None,
        trust_graph: Optional[TrustGraph] = None,
    ) -> None:
        if base_dir is None:
            base_dir = Path(__file__).resolve().parents[2] / "data" / "commitment_market"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.commitments_path = self.base_dir / "commitments.jsonl"
        self.settlements_path = self.base_dir / "settlements.jsonl"
        self.summary_path = self.base_dir / "summary.json"
        self._lock = threading.RLock()
        self._trust_graph = trust_graph
        self._commitments: Dict[str, Commitment] = {}
        self._settlements: List[Settlement] = []
        self._load()

    def _load(self) -> None:
        if self.commitments_path.exists():
            with self.commitments_path.open("r") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    payload = json.loads(line)
                    commitment = Commitment(**payload)
                    self._commitments[commitment.commitment_id] = commitment
        if self.settlements_path.exists():
            with self.settlements_path.open("r") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    self._settlements.append(Settlement(**json.loads(line)))

    def _append_jsonl(self, path: Path, payload: Dict[str, Any]) -> None:
        with path.open("a") as handle:
            handle.write(json.dumps(payload) + "\n")

    def _write_summary(self) -> None:
        self.summary_path.write_text(json.dumps(self.get_market_summary(), indent=2))

    def place_commitment(
        self,
        agent_id: str,
        prediction_type: str,
        prediction: Dict[str, Any],
        stake_points: float,
        confidence: float,
        *,
        target_time: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Commitment:
        if stake_points <= 0:
            raise ValueError("stake_points must be positive")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        commitment = Commitment(
            commitment_id=f"commit-{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            prediction_type=prediction_type,
            prediction=prediction,
            stake_points=float(stake_points),
            confidence=float(confidence),
            target_time=target_time,
            metadata=metadata or {},
        )

        with self._lock:
            self._commitments[commitment.commitment_id] = commitment
            self._append_jsonl(self.commitments_path, commitment.to_dict())
            self._write_summary()
        return commitment

    def settle_commitment(
        self,
        commitment_id: str,
        *,
        success: bool,
        outcome: Optional[Dict[str, Any]] = None,
        trust_graph: Optional[TrustGraph] = None,
    ) -> Settlement:
        with self._lock:
            commitment = self._commitments.get(commitment_id)
            if commitment is None:
                raise KeyError(f"Unknown commitment_id: {commitment_id}")
            if commitment.status == "settled":
                raise ValueError(f"Commitment already settled: {commitment_id}")

            payout = self._calculate_payout(commitment, success)
            trust_delta = self._calculate_trust_delta(commitment, payout)
            settlement = Settlement(
                commitment_id=commitment.commitment_id,
                agent_id=commitment.agent_id,
                success=success,
                payout_points=payout,
                trust_delta=trust_delta,
                outcome=outcome or {},
            )

            commitment.status = "settled"
            self._settlements.append(settlement)
            self._append_jsonl(self.settlements_path, settlement.to_dict())
            self._rewrite_commitments()
            self._write_summary()

        graph = trust_graph or self._trust_graph
        if graph is not None:
            graph.apply_delta(commitment.agent_id, trust_delta, reason=f"commitment:{commitment_id}")

        return settlement

    def _rewrite_commitments(self) -> None:
        with self.commitments_path.open("w") as handle:
            for commitment in self._commitments.values():
                handle.write(json.dumps(commitment.to_dict()) + "\n")

    @staticmethod
    def _calculate_payout(commitment: Commitment, success: bool) -> float:
        directional_multiplier = 1.0 + (commitment.confidence * 0.5)
        payout = commitment.stake_points * directional_multiplier
        return round(payout if success else -payout, 4)

    @staticmethod
    def _calculate_trust_delta(commitment: Commitment, payout: float) -> float:
        baseline = max(commitment.stake_points, 1.0)
        return round(max(-1.5, min(1.5, payout / baseline)), 4)

    def open_commitments(self, agent_id: Optional[str] = None) -> List[Commitment]:
        with self._lock:
            commitments = [c for c in self._commitments.values() if c.status == "open"]
            if agent_id:
                commitments = [c for c in commitments if c.agent_id == agent_id]
            return sorted(commitments, key=lambda c: c.created_at)

    def settled_commitments(self, agent_id: Optional[str] = None) -> List[Settlement]:
        with self._lock:
            settlements = self._settlements[:]
            if agent_id:
                settlements = [s for s in settlements if s.agent_id == agent_id]
            return sorted(settlements, key=lambda s: s.settled_at)

    def get_market_summary(self) -> Dict[str, Any]:
        with self._lock:
            open_count = sum(1 for commitment in self._commitments.values() if commitment.status == "open")
            settled = self._settlements[:]
            by_agent: Dict[str, Dict[str, Any]] = {}
            for settlement in settled:
                stats = by_agent.setdefault(
                    settlement.agent_id,
                    {"settled": 0, "wins": 0, "net_points": 0.0, "trust_delta": 0.0},
                )
                stats["settled"] += 1
                stats["wins"] += 1 if settlement.success else 0
                stats["net_points"] += settlement.payout_points
                stats["trust_delta"] += settlement.trust_delta
            for stats in by_agent.values():
                stats["net_points"] = round(stats["net_points"], 4)
                stats["trust_delta"] = round(stats["trust_delta"], 4)
                stats["win_rate"] = round(
                    stats["wins"] / stats["settled"], 4
                ) if stats["settled"] else 0.0
            return {
                "open_commitments": open_count,
                "settled_commitments": len(settled),
                "agents": by_agent,
            }

    def get_routing_priority(self, agent_id: str, trust_graph: Optional[TrustGraph] = None) -> float:
        graph = trust_graph or self._trust_graph
        base_score = graph.get_effective_score(agent_id) if graph is not None else 1.0
        summary = self.get_market_summary()["agents"].get(agent_id, {})
        win_rate = summary.get("win_rate", 0.0)
        net_points = summary.get("net_points", 0.0)
        settled = summary.get("settled", 0)
        experience_bonus = min(settled / 10.0, 1.0)
        return round(base_score + win_rate + max(-1.0, min(1.0, net_points / 10.0)) + experience_bonus, 4)


_COMMITMENT_MARKET: Optional[CommitmentMarket] = None


def get_commitment_market() -> CommitmentMarket:
    global _COMMITMENT_MARKET
    if _COMMITMENT_MARKET is None:
        _COMMITMENT_MARKET = CommitmentMarket(trust_graph=get_trust_graph())
    return _COMMITMENT_MARKET
