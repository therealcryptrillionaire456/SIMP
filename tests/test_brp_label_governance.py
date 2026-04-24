"""
Tests for label governance module (Tranche 4 — Corpus Hygiene & Label Governance).

Tests match the actual API of simp.brp.label_governance.
"""

import pytest
from typing import Dict, List, Set, Tuple

from simp.brp.label_governance import (
    LabelClass,
    LabelPolicy,
    CorpusHygiene,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def hygiene() -> CorpusHygiene:
    return CorpusHygiene()


def _scenario(
    attack_type: str = "",
    expected_sources: list = None,
    expected_count: int = 0,
    name: str = "",
    **extra,
) -> Dict:
    """Build a canonical scenario-like record."""
    rec: Dict = {"attack_type": attack_type}
    if expected_sources:
        rec["expected_detection_sources"] = expected_sources
    if expected_count:
        rec["expected_detection_count_min"] = expected_count
    if name:
        rec["name"] = name
    rec.update(extra)
    return rec


# ── LabelClass Tests ─────────────────────────────────────────────────────────


class TestLabelClass:
    def test_enum_values(self):
        assert LabelClass.CONFIRMED_ATTACK.value == "confirmed_attack"
        assert LabelClass.BENIGN.value == "benign"
        assert LabelClass.SUSPECTED_ATTACK.value == "suspected_attack"
        assert LabelClass.UNKNOWN.value == "unknown"


# ── LabelPolicy Tests ────────────────────────────────────────────────────────


class TestLabelPolicy:
    def test_default_policy(self):
        p = LabelPolicy()
        assert LabelClass.CONFIRMED_ATTACK in p.headline_positive
        assert LabelClass.BENIGN in p.headline_negative
        assert LabelClass.SUSPECTED_ATTACK in p.excluded_from_headline
        assert LabelClass.UNKNOWN in p.excluded_from_headline


# ── Classification Tests ─────────────────────────────────────────────────────


class TestClassification:
    def test_confirmed_attack(self, hygiene):
        r = _scenario("privilege_escalation", ["brp_gateway"], 1)
        assert hygiene.classify_label(r) == LabelClass.CONFIRMED_ATTACK

    def test_benign(self, hygiene):
        r = _scenario("benign")
        assert hygiene.classify_label(r) == LabelClass.BENIGN

    def test_suspected_attack_no_sources(self, hygiene):
        r = _scenario("code_exploit")
        assert hygiene.classify_label(r) == LabelClass.SUSPECTED_ATTACK

    def test_unknown_no_relevant_fields(self, hygiene):
        assert hygiene.classify_label({"foo": "bar"}) == LabelClass.UNKNOWN

    def test_explicit_label_override(self, hygiene):
        r = _scenario("sql_injection", label="benign")
        assert hygiene.classify_label(r) == LabelClass.BENIGN


# ── Test/Demo Detection Tests ────────────────────────────────────────────────


class TestTestDemoDetection:
    def test_name_contains_test(self):
        assert CorpusHygiene.is_test_or_demo({"name": "test_scenario"}) is True

    def test_name_contains_demo(self):
        assert CorpusHygiene.is_test_or_demo({"name": "demo_run"}) is True

    def test_event_type_bookkeeping(self):
        assert CorpusHygiene.is_test_or_demo({"event_type": "bookkeeping_log"}) is True

    def test_tags_contains_test(self):
        assert CorpusHygiene.is_test_or_demo({"tags": ["test", "synthetic"]}) is True

    def test_metadata_test_key(self):
        assert CorpusHygiene.is_test_or_demo({"metadata": {"env": "test"}}) is True

    def test_clean_record_not_detected(self):
        r = _scenario("sql_injection", ["brp_gateway"], 1)
        assert CorpusHygiene.is_test_or_demo(r) is False


# ── Deduplication Tests ──────────────────────────────────────────────────────


class TestDeduplication:
    def test_duplicate_by_event_id(self):
        seen: Set[str] = set()
        r1 = {"event_id": "evt_001", "attack_type": "sql_injection"}
        r2 = {"event_id": "evt_001", "attack_type": "sql_injection"}
        assert CorpusHygiene.is_duplicate(r1, seen) is False
        assert CorpusHygiene.is_duplicate(r2, seen) is True

    def test_duplicate_by_content_hash(self):
        seen: Set[str] = set()
        r1 = {"attack_type": "sql_injection", "name": "SQL Probe", "description": "test"}
        r2 = {"attack_type": "sql_injection", "name": "SQL Probe", "description": "test"}
        assert CorpusHygiene.is_duplicate(r1, seen) is False
        assert CorpusHygiene.is_duplicate(r2, seen) is True

    def test_unique_not_deduped(self):
        seen: Set[str] = set()
        for i in range(5):
            r = {"event_id": f"evt_{i:03d}", "attack_type": "sql_injection"}
            assert CorpusHygiene.is_duplicate(r, seen) is False


# ── Full Corpus Filtering Tests ──────────────────────────────────────────────


class TestCorpusFiltering:
    def test_empty_corpus(self, hygiene):
        clean, report = hygiene.filter_corpus([])
        assert report["total_input"] == 0
        assert report["final_count"] == 0
        assert len(clean) == 0

    def test_removes_test_demo_traffic(self, hygiene):
        samples = [
            _scenario("privilege_escalation", ["brp"], 1),  # keep
            {"name": "test_scenario"},                       # test → remove
            _scenario("benign"),                             # keep
            {"tags": ["demo"]},                              # demo → remove
        ]
        clean, report = hygiene.filter_corpus(samples)
        assert report["total_input"] == 4
        assert report["test_demo_removed"] == 2
        assert report["final_count"] == 2

    def test_removes_duplicates(self, hygiene):
        samples = [
            _scenario("privilege_escalation", ["brp"], 1, name="SQL-1"),
            _scenario("privilege_escalation", ["brp"], 1, name="SQL-1"),  # dup
            _scenario("benign", name="B-1"),
        ]
        clean, report = hygiene.filter_corpus(samples)
        assert report["total_input"] == 3
        assert report["duplicates_removed"] == 1
        assert report["final_count"] == 2

    def test_hygiene_report_shape(self, hygiene):
        samples = [
            _scenario("privilege_escalation", ["brp"], 1),
            _scenario("benign"),
        ]
        _, report = hygiene.filter_corpus(samples)
        for key in ("total_input", "test_demo_removed", "duplicates_removed",
                     "final_count", "label_counts", "headline_positive",
                     "headline_negative", "excluded_count"):
            assert key in report, f"Missing key: {key}"


# ── Headline Metrics Tests ───────────────────────────────────────────────────


class TestHeadlineMetrics:
    def test_only_confirmed_and_benign_counted(self, hygiene):
        predictions: List[Tuple[str, str]] = [
            ("confirmed_attack", "confirmed_attack"),  # TP
            ("confirmed_attack", "benign"),             # FN
            ("benign", "benign"),                       # TN
            ("benign", "confirmed_attack"),             # FP
            ("suspected_attack", "suspected_attack"),   # excluded
            ("unknown", "confirmed_attack"),            # excluded
        ]
        m = hygiene.compute_headline_metrics(predictions)
        assert m["total_headline"] == 4  # only 4 usable
        assert m["true_positives"] == 1
        assert m["false_positives"] == 1
        assert m["false_negatives"] == 1
        assert m["true_negatives"] == 1
        assert m["precision"] == 0.5
        assert m["recall"] == 0.5
        assert m["f1_score"] == 0.5

    def test_perfect_headline(self, hygiene):
        predictions: List[Tuple[str, str]] = [
            ("confirmed_attack", "confirmed_attack"),
            ("confirmed_attack", "confirmed_attack"),
            ("benign", "benign"),
            ("benign", "benign"),
        ]
        m = hygiene.compute_headline_metrics(predictions)
        assert m["total_headline"] == 4
        assert m["precision"] == 1.0
        assert m["recall"] == 1.0
        assert m["f1_score"] == 1.0

    def test_all_excluded(self, hygiene):
        predictions: List[Tuple[str, str]] = [
            ("suspected_attack", "suspected_attack"),
            ("unknown", "unknown"),
        ]
        m = hygiene.compute_headline_metrics(predictions)
        assert m["total_headline"] == 0
        assert m["precision"] == 0.0
        assert m["recall"] == 0.0
        assert m["f1_score"] == 0.0


# ── Supplementary Metrics Tests ──────────────────────────────────────────────


class TestSupplementaryMetrics:
    def test_includes_all_labels(self, hygiene):
        predictions: List[Tuple[str, str]] = [
            ("confirmed_attack", "confirmed_attack"),
            ("benign", "benign"),
            ("suspected_attack", "suspected_attack"),
            ("unknown", "confirmed_attack"),
        ]
        m = hygiene.compute_supplementary_metrics(predictions)
        assert m["total_corpus"] == 4
        assert "label_breakdown" in m
        # Breakdown should report the 4 distinct labels per true label
        assert len(m["label_breakdown"]) >= 3  # at least 3 unique true labels

    def test_empty(self, hygiene):
        m = hygiene.compute_supplementary_metrics([])
        assert m["total_corpus"] == 0


# ── Integration Tests ────────────────────────────────────────────────────────


class TestIntegration:
    def test_classify_then_filter_then_metrics(self, hygiene):
        raw = [
            _scenario("privilege_escalation", ["brp"], 1, name="SQL Attack"),
            _scenario("benign", name="Normal traffic"),
            {"name": "test_scenario", "attack_type": "benign"},
            _scenario("code_exploit", name="SQL Probe No Sources"),
        ]
        # Classify each
        labels = [hygiene.classify_label(r) for r in raw]
        assert labels[0] == LabelClass.CONFIRMED_ATTACK
        assert labels[1] == LabelClass.BENIGN
        assert labels[2] == LabelClass.BENIGN
        assert labels[3] == LabelClass.SUSPECTED_ATTACK

        # Filter
        clean, report = hygiene.filter_corpus(raw)
        assert report["total_input"] == 4
        assert report["test_demo_removed"] == 1  # test_scenario
        assert report["final_count"] == 3

        # Headline metrics on predictions
        preds: List[Tuple[str, str]] = []
        for r in clean:
            tl = hygiene.classify_label(r).value
            preds.append((tl, tl))  # perfect prediction

        m = hygiene.compute_headline_metrics(preds)
        assert m["total_headline"] == 2  # only confirmed_attack + benign
        assert m["f1_score"] == 1.0
