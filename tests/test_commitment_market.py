import tempfile
from pathlib import Path

from simp.mesh.commitment_market import CommitmentMarket


class StubTrustGraph:
    def __init__(self) -> None:
        self.applied = []

    def apply_delta(self, agent_id: str, delta: float, reason: str = "") -> float:
        self.applied.append((agent_id, delta, reason))
        return delta

    def get_effective_score(self, agent_id: str) -> float:
        return 2.5


def test_place_and_settle_commitment_updates_ledger_and_trust():
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = StubTrustGraph()
        market = CommitmentMarket(base_dir=tmpdir, trust_graph=graph)

        commitment = market.place_commitment(
            agent_id="bullbear_predictor",
            prediction_type="prediction_signal",
            prediction={"ticker": "BTC-USD", "direction": "bull"},
            stake_points=2.0,
            confidence=0.8,
        )

        assert commitment.commitment_id.startswith("commit-")
        assert len(market.open_commitments("bullbear_predictor")) == 1

        settlement = market.settle_commitment(
            commitment.commitment_id,
            success=True,
            outcome={"observed_direction": "bull"},
        )

        assert settlement.success is True
        assert settlement.payout_points > 0
        assert len(graph.applied) == 1
        assert market.open_commitments("bullbear_predictor") == []


def test_routing_priority_uses_market_performance():
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = StubTrustGraph()
        market = CommitmentMarket(base_dir=tmpdir, trust_graph=graph)
        commitment = market.place_commitment(
            agent_id="quantumarb_real",
            prediction_type="trade_signal",
            prediction={"pair": "BTC-USD/ETH-USD"},
            stake_points=1.0,
            confidence=0.9,
        )
        market.settle_commitment(commitment.commitment_id, success=True)

        priority = market.get_routing_priority("quantumarb_real")
        assert priority > graph.get_effective_score("quantumarb_real")


def test_summary_file_is_written():
    with tempfile.TemporaryDirectory() as tmpdir:
        market = CommitmentMarket(base_dir=tmpdir)
        market.place_commitment(
            agent_id="projectx_native",
            prediction_type="maintenance",
            prediction={"action": "restart_component"},
            stake_points=1.5,
            confidence=0.6,
        )

        summary_path = Path(tmpdir) / "summary.json"
        assert summary_path.exists()
        assert "open_commitments" in summary_path.read_text()
