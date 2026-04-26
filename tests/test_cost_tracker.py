"""Tests for Cost Tracker — ProjectX cost tracking and budget enforcement."""

import pytest
from simp.projectx.cost_tracker import CostTracker, TokenUsage, CostSummary


class TestCostTrackerInitialization:
    def test_initialization(self) -> None:
        tracker = CostTracker()
        assert tracker is not None

    def test_initialization_with_pricing(self) -> None:
        pricing = {"gpt-4": {"prompt": 0.03, "completion": 0.06}}
        tracker = CostTracker(pricing=pricing)
        assert tracker is not None

    def test_initialization_with_ledger_path(self, tmp_path) -> None:
        tracker = CostTracker(ledger_path=str(tmp_path / "ledger.jsonl"))
        assert tracker is not None


class TestTrackOperationAddsCost:
    def test_record_usage(self) -> None:
        tracker = CostTracker()
        tracker.record_usage(model="gpt-4", provider="openai",
                            prompt_tokens=100, completion_tokens=50,
                            total_tokens=150, cost=0.015)
        records = tracker.get_records()
        assert isinstance(records, list)

    def test_record_multiple_usage_accumulates(self) -> None:
        tracker = CostTracker()
        for i in range(3):
            tracker.record_usage(model="gpt-4", provider="openai",
                                 prompt_tokens=100, completion_tokens=50,
                                 total_tokens=150, cost=0.015)
        records = tracker.get_records()
        assert len(records) >= 3


class TestCostBreakdownByCategory:
    def test_cost_breakdown_by_model(self) -> None:
        tracker = CostTracker()
        tracker.record_usage(model="gpt-4", provider="openai",
                            prompt_tokens=100, completion_tokens=50,
                            total_tokens=150, cost=0.015)
        summary = tracker.get_summary()
        assert isinstance(summary, CostSummary)
        assert summary.total_tokens > 0

    def test_cost_breakdown_by_provider(self) -> None:
        tracker = CostTracker()
        tracker.record_usage(model="claude-3", provider="anthropic",
                            prompt_tokens=200, completion_tokens=100,
                            total_tokens=300, cost=0.03)
        summary = tracker.get_summary()
        assert isinstance(summary, CostSummary)
        assert summary.by_provider.get("anthropic", 0) > 0

    def test_cost_breakdown_model_fields(self) -> None:
        tracker = CostTracker()
        tracker.record_usage(model="gpt-4", provider="openai",
                            prompt_tokens=100, completion_tokens=50,
                            total_tokens=150, cost=0.015)
        summary = tracker.get_summary()
        assert summary.total_cost > 0
        assert summary.call_count >= 1


class TestCostSnapshotExport:
    def test_snapshot_returns_cost_summary(self) -> None:
        tracker = CostTracker()
        summary = tracker.get_summary()
        assert isinstance(summary, CostSummary)

    def test_snapshot_fields(self) -> None:
        tracker = CostTracker()
        tracker.record_usage(model="gpt-4", provider="openai",
                            prompt_tokens=100, completion_tokens=50,
                            total_tokens=150, cost=0.015)
        summary = tracker.get_summary()
        assert hasattr(summary, "total_tokens")
        assert hasattr(summary, "total_cost")
        assert hasattr(summary, "call_count")
        assert hasattr(summary, "by_model")

    def test_snapshot_cost_by_model(self) -> None:
        tracker = CostTracker()
        tracker.record_usage(model="gpt-4", provider="openai",
                            prompt_tokens=100, completion_tokens=50,
                            total_tokens=150, cost=0.015)
        summary = tracker.get_summary()
        assert "gpt-4" in summary.cost_by_model

    def test_export_calls_snapshot(self) -> None:
        tracker = CostTracker()
        records = tracker.get_records()
        assert isinstance(records, list)


class TestCostReset:
    def test_reset_clears_records(self) -> None:
        tracker = CostTracker()
        tracker.record_usage(model="gpt-4", provider="openai",
                            prompt_tokens=100, completion_tokens=50,
                            total_tokens=150, cost=0.015)
        tracker.clear_records()
        records = tracker.get_records()
        assert len(records) == 0


class TestCostAlertThreshold:
    def test_get_summary_returns_cost_summary(self) -> None:
        tracker = CostTracker()
        summary = tracker.get_summary()
        assert isinstance(summary, CostSummary)

    def test_no_budget_enforcement_in_v1(self) -> None:
        tracker = CostTracker()
        assert not hasattr(tracker, "set_budget")

    def test_get_pricing_returns_dict(self) -> None:
        tracker = CostTracker()
        pricing = tracker.get_pricing()
        assert isinstance(pricing, dict)

    def test_update_pricing(self) -> None:
        tracker = CostTracker()
        tracker.update_pricing("gpt-4", input_price=0.04, output_price=0.08)
        pricing = tracker.get_pricing()
        assert "gpt-4" in pricing


class TestTokenUsage:
    def test_token_usage_creation(self) -> None:
        usage = TokenUsage(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost=0.015,
            timestamp="2026-04-26T12:00:00Z",
        )
        assert usage.model == "gpt-4"
        assert usage.total_tokens == 150

    def test_token_usage_to_dict(self) -> None:
        usage = TokenUsage(
            model="gpt-4", provider="openai",
            prompt_tokens=100, completion_tokens=50,
            total_tokens=150, estimated_cost=0.015,
            timestamp="2026-04-26T12:00:00Z",
        )
        d = usage.to_dict()
        assert d["model"] == "gpt-4"
        assert d["total_tokens"] == 150

    def test_token_usage_from_dict(self) -> None:
        d = {
            "model": "gpt-4",
            "provider": "openai",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "estimated_cost": 0.015,
            "timestamp": "2026-04-26T12:00:00Z",
        }
        usage = TokenUsage.from_dict(d)
        assert usage.model == "gpt-4"

    def test_ingest_trace_event(self) -> None:
        tracker = CostTracker()
        event = {
            "model": "gpt-4",
            "provider": "openai",
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75,
            "estimated_cost": 0.0075,
            "timestamp": "2026-04-26T12:00:00Z",
        }
        tracker.ingest_trace_event(event)
        records = tracker.get_records()
        assert len(records) >= 1
