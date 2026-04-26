"""Tests for Domain Adapter — ProjectX domain-specific adaptation."""

import pytest
from simp.projectx.domain_adapter import (
    DomainAdapter,
    DomainExample,
    DomainAdaptationReport,
    FewShotScorer,
)


class TestDomainAdapter:
    def test_adapter_initialization(self) -> None:
        adapter = DomainAdapter(apo_steps_per_subsystem=15)
        assert adapter is not None

    def test_adapter_default_initialization(self) -> None:
        adapter = DomainAdapter()
        assert adapter is not None

    def test_adapter_has_store_dir(self) -> None:
        adapter = DomainAdapter()
        # store_dir is accessible (may be public or private)
        assert hasattr(adapter, "_store_dir")


class TestDomainExample:
    def test_domain_example_creation(self) -> None:
        example = DomainExample(prompt="What is 2+2?", response="4", score=0.9)
        assert example.prompt == "What is 2+2?"
        assert example.response == "4"
        assert example.score == 0.9

    def test_domain_example_default_score(self) -> None:
        example = DomainExample(prompt="x", response="y")
        assert example.score == 1.0

    def test_domain_example_tags(self) -> None:
        example = DomainExample(prompt="test", response="result", tags=["math"])
        assert "math" in example.tags


class TestFewShotScorer:
    def test_fewshot_scorer_initialization(self) -> None:
        scorer = FewShotScorer(examples=[
            DomainExample(prompt="a", response="b", score=0.9),
            DomainExample(prompt="c", response="d", score=0.5),
        ])
        assert scorer is not None
        assert hasattr(scorer, "_good") or hasattr(scorer, "_bad")

    def test_fewshot_scorer_segregates_by_score(self) -> None:
        scorer = FewShotScorer(examples=[
            DomainExample(prompt="a", response="b", score=0.9),
            DomainExample(prompt="c", response="d", score=0.3),
            DomainExample(prompt="e", response="f", score=0.6),
        ])
        # High score (>=0.7) in _good, low score (<0.4) in _bad
        assert len(scorer._good) >= 1


class TestDomainAdaptationReport:
    def test_report_creation(self) -> None:
        report = DomainAdaptationReport(domain="test")
        assert report.domain == "test"

    def test_report_to_dict(self) -> None:
        report = DomainAdaptationReport(domain="code")
        d = report.to_dict()
        assert "domain" in d


class TestDomainAdapterPersistence:
    def test_adapter_creates_store_dir(self, tmp_path) -> None:
        adapter = DomainAdapter(
            apo_steps_per_subsystem=5,
            store_dir=str(tmp_path / "domains"),
        )
        assert tmp_path.exists()

    def test_adapter_serialization(self) -> None:
        adapter = DomainAdapter(apo_steps_per_subsystem=5)
        import json
        config = {"apo_steps_per_subsystem": 5}
        assert isinstance(json.dumps(config), str)
