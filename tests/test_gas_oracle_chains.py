"""
T32.1/2 — E7: Multi-Chain Gas Oracle Tests
Tests GasOracle.multi_chain_comparison() and cheapest_chain() methods.
"""
import tempfile
import pytest
from simp.organs.quantumarb.gas_oracle import GasOracle, GasSample


class TestMultiChainComparison:
    """Test cross-chain fee comparison (E7)."""

    def setup_method(self):
        self.oracle = GasOracle(data_dir=tempfile.mkdtemp())

    def test_multi_chain_comparison_returns_all_chains(self):
        """E7: multi_chain_comparison should return data for all supported chains."""
        result = self.oracle.multi_chain_comparison(tx_complexity="standard")
        assert isinstance(result, dict)
        assert "all_chains_ranked" in result
        assert len(result["all_chains_ranked"]) > 0

    def test_cheapest_chain_standard(self):
        """E7: cheapest_chain should return the chain with lowest predicted fee."""
        result = self.oracle.cheapest_chain(tx_complexity="standard")
        assert isinstance(result, dict)
        assert "cheapest_chain" in result
        assert "all_chains_ranked" in result

    def test_cheapest_chain_complex(self):
        """E7: cheapest_chain should handle complex transactions."""
        result = self.oracle.cheapest_chain(tx_complexity="complex")
        assert isinstance(result, dict)
        assert "cheapest_chain" in result

    def test_record_sample_per_chain(self):
        """E7: record_sample should track gas per chain."""
        self.oracle.record_sample("ethereum", 25.0)
        self.oracle.record_sample("solana", 0.00025)
        self.oracle.record_sample("arbitrum", 0.15)
        eth_stats = self.oracle.get_chain_stats("ethereum")
        assert eth_stats is not None

    def test_get_chain_stats_ethereum(self):
        """E7: get_chain_stats should return stats for a specific chain."""
        self.oracle.record_sample("ethereum", 30.0)
        stats = self.oracle.get_chain_stats("ethereum")
        assert stats is not None
        assert isinstance(stats, dict)

    def test_get_chain_stats_unknown_chain(self):
        """E7: get_chain_stats should handle unknown chains gracefully."""
        stats = self.oracle.get_chain_stats("unknown_chain_xyz")
        assert stats is not None

    def test_predict_next_blocks_ethereum(self):
        """E7: predict_next_blocks should predict gas for Ethereum."""
        self.oracle.record_sample("ethereum", 30.0)
        prediction = self.oracle.predict_next_blocks("ethereum", blocks=5)
        assert prediction is not None
        assert hasattr(prediction, "predicted_next_gwei")
        assert prediction.chain == "ethereum"

    def test_gas_budget_status(self):
        """E7: get_gas_budget_status should track gas spend per strategy."""
        status = self.oracle.get_gas_budget_status("quantumarb", daily_budget_gwei=500000)
        assert isinstance(status, dict)

    def test_check_tier_upgrade(self):
        """E7: check_tier_upgrade should recommend tier upgrades based on volume."""
        result = self.oracle.check_tier_upgrade(
            venue="coinbase",
            current_volume_30d=1000000.0,
            target_tiers=[
                {"name": "Free", "min_volume": 0, "maker_bps": 50, "taker_bps": 50},
                {"name": "Pro", "min_volume": 500000, "maker_bps": 40, "taker_bps": 45},
                {"name": "Enterprise", "min_volume": 2000000, "maker_bps": 30, "taker_bps": 40},
            ],
        )
        assert isinstance(result, dict)
        assert "current_tier" in result
        assert result["current_tier"] == "Pro"  # Volume 1M qualifies for Pro

    def test_persistence(self):
        """E7: GasOracle should persist samples to disk."""
        oracle = GasOracle(data_dir=tempfile.mkdtemp())
        oracle.record_sample("ethereum", 30.0)
        oracle.persist()
        oracle2 = GasOracle(data_dir=oracle._data_dir)
        stats = oracle2.get_chain_stats("ethereum")
        assert stats is not None

    def test_chain_in_all_chains_ranked(self):
        """E7: Each chain entry should have a 'chain' field."""
        result = self.oracle.multi_chain_comparison(tx_complexity="standard")
        for chain_entry in result["all_chains_ranked"]:
            assert "chain" in chain_entry
            assert isinstance(chain_entry["chain"], str)

    def test_cheapest_chain_selects_solana_for_low_fee(self):
        """E7: cheapest_chain should pick Solana (lowest gas cost)."""
        result = self.oracle.cheapest_chain(tx_complexity="standard")
        assert result["cheapest_chain"] == "solana"  # Solana has lowest gas


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
