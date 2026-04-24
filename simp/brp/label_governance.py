"""
Label governance and corpus hygiene for BRP benchmark.

Defines v1 label classes, headline metric exclusion rules, and traffic
filtering (test/demo/duplicate removal). This is a measurement governance
layer only — it never modifies detection logic.

Use by passing a CorpusHygiene instance to DetectionBenchmark.run_all().
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Label classes ───────────────────────────────────────────────────────────

class LabelClass(str, Enum):
    """V1 label taxonomy for BRP scenario classification."""

    CONFIRMED_ATTACK = "confirmed_attack"
    BENIGN = "benign"
    SUSPECTED_ATTACK = "suspected_attack"
    UNKNOWN = "unknown"


# ── Label policy ────────────────────────────────────────────────────────────

@dataclass
class LabelPolicy:
    """Defines which label classes appear in headline vs. supplementary metrics.

    ``headline_positive`` — label classes counted as positive in headline
    precision/recall/F1 (default: only CONFIRMED_ATTACK).

    ``headline_negative`` — label classes counted as negative in headline
    metrics (default: only BENIGN).

    ``excluded_from_headline`` — label classes excluded from headline
    computation entirely (default: SUSPECTED_ATTACK, UNKNOWN). These are
    reported only in supplementary metrics.
    """

    headline_positive: Set[LabelClass] = field(
        default_factory=lambda: {LabelClass.CONFIRMED_ATTACK}
    )
    headline_negative: Set[LabelClass] = field(
        default_factory=lambda: {LabelClass.BENIGN}
    )
    excluded_from_headline: Set[LabelClass] = field(
        default_factory=lambda: {LabelClass.SUSPECTED_ATTACK, LabelClass.UNKNOWN}
    )
    excluded_reason: str = (
        "Excluded from headline metrics — ambiguous or unverified"
    )


# ── Hygiene report ──────────────────────────────────────────────────────────

HYGIENE_REPORT_KEYS = [
    "total_input",
    "test_demo_removed",
    "duplicates_removed",
    "final_count",
    "label_counts",
    "headline_positive",
    "headline_negative",
    "excluded_count",
]


def _empty_hygiene_report() -> Dict[str, Any]:
    """Return a zeroed-out hygiene report."""
    return {
        "total_input": 0,
        "test_demo_removed": 0,
        "duplicates_removed": 0,
        "final_count": 0,
        "label_counts": {
            "confirmed_attack": 0,
            "benign": 0,
            "suspected_attack": 0,
            "unknown": 0,
        },
        "headline_positive": 0,
        "headline_negative": 0,
        "excluded_count": 0,
    }


# ── Corpus hygiene engine ───────────────────────────────────────────────────

class CorpusHygiene:
    """Filters and classifies a corpus of BRP samples for fair measurement.

    Responsibilities:
    1. Classify each record into a LabelClass via heuristic rules.
    2. Detect and remove test/demo/bookkeeping traffic.
    3. Detect and remove duplicate records.
    4. Compute headline metrics using only non-excluded label classes.
    5. Compute supplementary metrics including all labels.
    """

    def __init__(
        self,
        label_policy: Optional[LabelPolicy] = None,
    ) -> None:
        self._policy = label_policy or LabelPolicy()
        self._lock = threading.Lock()

    # ── Label classification ───────────────────────────────────────────

    def classify_label(self, record: Dict[str, Any]) -> LabelClass:
        """Heuristic label classification for a BRP record.

        Uses record fields such as ``attack_type``, ``expected_detection_sources``,
        ``expected_detection_count_min``, or a top-level ``label`` field
        to decide membership.
        """
        # Explicit ground-truth label
        explicit = record.get("label")
        if explicit is not None:
            try:
                return LabelClass(explicit)
            except ValueError:
                pass

        # Attack type from canonical scenario
        attack_type = record.get("attack_type", "")

        # Benign classification
        if attack_type == "benign":
            return LabelClass.BENIGN

        # Confirmed attack: has attack_type in AttackType.ALL and
        # at least one expected detection source
        from simp.brp.detection_benchmark import AttackType

        is_attack = attack_type in AttackType.ALL
        expected_sources = record.get("expected_detection_sources", [])
        expected_count = record.get("expected_detection_count_min", 0)

        if is_attack and len(expected_sources) > 0 and expected_count > 0:
            return LabelClass.CONFIRMED_ATTACK

        # Suspected attack: has attack type but zero or empty expected sources
        if is_attack:
            return LabelClass.SUSPECTED_ATTACK

        # Fallback
        return LabelClass.UNKNOWN

    # ── Traffic filtering ──────────────────────────────────────────────

    @staticmethod
    def is_test_or_demo(record: Dict[str, Any]) -> bool:
        """Detect test, demo, or bookkeeping traffic.

        Checks the following fields (case-insensitive substring match):
        - ``name``
        - ``description``
        - ``source`` / ``tags`` (if present as strings or lists of strings)
        - ``metadata`` sub-dict fields
        """
        test_demo_markers = {"test", "demo", "bookkeeping"}

        # Check top-level string fields
        for key in ("name", "description", "source", "event_type"):
            value = record.get(key)
            if isinstance(value, str):
                lower = value.lower()
                if any(marker in lower for marker in test_demo_markers):
                    return True

        # Check tags list
        tags = record.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.lower() in test_demo_markers:
                    return True

        # Check metadata dict
        metadata = record.get("metadata")
        if isinstance(metadata, dict):
            for v in metadata.values():
                if isinstance(v, str):
                    lower = v.lower()
                    if any(marker in lower for marker in test_demo_markers):
                        return True

        return False

    # ── Deduplication ──────────────────────────────────────────────────

    @staticmethod
    def is_duplicate(record: Dict[str, Any], seen: Set[str]) -> bool:
        """Check if a record is a duplicate based on event_id or content hash.

        Adds the dedup key to ``seen`` if not already present.
        Returns True if the record was already seen.
        """
        # Prefer event_id
        event_id = record.get("event_id")
        if event_id is not None:
            key = f"event_id:{event_id}"
            if key in seen:
                return True
            seen.add(key)
            return False

        # Fall back to content hash of a canonical subset
        content_parts = []
        for k in ("attack_type", "name", "description", "expected_detection_sources"):
            v = record.get(k)
            if v is not None:
                content_parts.append(f"{k}={v!r}")
        content_str = "|".join(content_parts)
        content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
        key = f"hash:{content_hash}"
        if key in seen:
            return True
        seen.add(key)
        return False

    # ── Corpus filtering pipeline ──────────────────────────────────────

    def filter_corpus(
        self,
        samples: List[Dict[str, Any]],
        deduplicate: bool = True,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Filter a corpus of samples, returning (clean_samples, report).

        Steps:
        1. Remove test/demo/bookkeeping records.
        2. Optionally remove duplicates.
        3. Classify each remaining record.
        4. Generate hygiene report with label counts.
        """
        report = _empty_hygiene_report()
        report["total_input"] = len(samples)

        if not samples:
            return [], report

        # Step 1: Remove test/demo traffic
        cleaned: List[Dict[str, Any]] = []
        for record in samples:
            if self.is_test_or_demo(record):
                report["test_demo_removed"] += 1
            else:
                cleaned.append(record)

        # Step 2: Deduplicate
        if deduplicate:
            seen: Set[str] = set()
            deduped: List[Dict[str, Any]] = []
            for record in cleaned:
                if self.is_duplicate(record, seen):
                    report["duplicates_removed"] += 1
                else:
                    deduped.append(record)
            cleaned = deduped

        # Step 3: Classify and count labels
        label_counts: Dict[str, int] = {
            "confirmed_attack": 0,
            "benign": 0,
            "suspected_attack": 0,
            "unknown": 0,
        }
        headline_positive = 0
        headline_negative = 0
        excluded_count = 0

        for record in cleaned:
            lc = self.classify_label(record)
            label_counts[lc.value] = label_counts.get(lc.value, 0) + 1

            if lc in self._policy.headline_positive:
                headline_positive += 1
            elif lc in self._policy.headline_negative:
                headline_negative += 1
            else:
                excluded_count += 1

        report["final_count"] = len(cleaned)
        report["label_counts"] = label_counts
        report["headline_positive"] = headline_positive
        report["headline_negative"] = headline_negative
        report["excluded_count"] = excluded_count

        return cleaned, report

    # ── Headline metrics ───────────────────────────────────────────────

    def compute_headline_metrics(
        self,
        predictions: List[Tuple[str, str]],
    ) -> Dict[str, Any]:
        """Compute precision, recall, and F1 using only headline labels.

        Each prediction is a tuple of (true_label, predicted_label) where
        each label is a string value from LabelClass.

        Records whose true_label is in ``excluded_from_headline`` are
        silently skipped.
        """
        tp = 0  # true positive = predicted positive & true positive class
        fp = 0  # false positive = predicted positive but true negative class
        fn = 0  # false negative = predicted negative but true positive class
        tn = 0  # true negative = predicted negative & true negative class

        for true_str, pred_str in predictions:
            try:
                true_lc = LabelClass(true_str)
            except ValueError:
                continue  # skip unparseable

            # Skip excluded labels
            if true_lc in self._policy.excluded_from_headline:
                continue

            try:
                pred_lc = LabelClass(pred_str)
            except ValueError:
                pred_lc = LabelClass.UNKNOWN

            is_true_pos = true_lc in self._policy.headline_positive
            is_pred_pos = pred_lc in self._policy.headline_positive

            if is_true_pos and is_pred_pos:
                tp += 1
            elif not is_true_pos and is_pred_pos:
                fp += 1
            elif is_true_pos and not is_pred_pos:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "total_headline": tp + fp + fn + tn,
        }

    # ── Supplementary metrics ──────────────────────────────────────────

    def compute_supplementary_metrics(
        self,
        predictions: List[Tuple[str, str]],
    ) -> Dict[str, Any]:
        """Compute full metrics including all label classes.

        Unlike ``compute_headline_metrics``, no labels are excluded.
        This allows comparison of headline vs. full-corpus performance.
        """
        tp = fp = fn = tn = 0
        label_breakdown: Dict[str, Dict[str, int]] = {}

        for true_str, pred_str in predictions:
            try:
                true_lc = LabelClass(true_str)
            except ValueError:
                continue

            try:
                pred_lc = LabelClass(pred_str)
            except ValueError:
                pred_lc = LabelClass.UNKNOWN

            label_key = true_lc.value
            if label_key not in label_breakdown:
                label_breakdown[label_key] = {
                    "total": 0, "correct": 0, "incorrect": 0,
                }
            label_breakdown[label_key]["total"] += 1

            is_true_pos = true_lc in self._policy.headline_positive
            is_pred_pos = pred_lc in self._policy.headline_positive

            if is_true_pos and is_pred_pos:
                tp += 1
                if true_lc == pred_lc:
                    label_breakdown[label_key]["correct"] += 1
                else:
                    label_breakdown[label_key]["incorrect"] += 1
            elif not is_true_pos and is_pred_pos:
                fp += 1
                label_breakdown[label_key]["incorrect"] += 1
            elif is_true_pos and not is_pred_pos:
                fn += 1
                label_breakdown[label_key]["incorrect"] += 1
            else:
                tn += 1
                if true_lc == pred_lc:
                    label_breakdown[label_key]["correct"] += 1
                else:
                    label_breakdown[label_key]["incorrect"] += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "total_corpus": tp + fp + fn + tn,
            "label_breakdown": label_breakdown,
        }
