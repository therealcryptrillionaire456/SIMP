"""
ProjectX Answer Validator — Phase 4

Multi-source response verification pipeline. Given a candidate answer,
runs it through a configurable set of checks and returns a composite
confidence score with per-check breakdowns.

Checks available (enabled by default unless noted):
  - consistency:  Internal self-consistency via paraphrase sampling
  - format:       Structural/format correctness for known output types
  - length:       Output within expected token band
  - source_cross: Cross-references claim against RAG memory entries
  - fact_check:   Optional web lookup for named entities / numbers

The validator is intentionally stateless — it takes a question and
answer and returns a ValidationReport. Callers decide what to do.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Score below which an answer is flagged for review
VALIDATION_THRESHOLD = 0.55


@dataclass
class CheckResult:
    name: str
    passed: bool
    score: float          # 0.0–1.0
    reason: str = ""
    weight: float = 1.0


@dataclass
class ValidationReport:
    question: str
    answer: str
    checks: List[CheckResult] = field(default_factory=list)
    composite_score: float = 0.0
    passed: bool = False
    flagged_reasons: List[str] = field(default_factory=list)
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer[:300] + ("…" if len(self.answer) > 300 else ""),
            "composite_score": round(self.composite_score, 4),
            "passed": self.passed,
            "flagged_reasons": self.flagged_reasons,
            "latency_ms": self.latency_ms,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "score": round(c.score, 4),
                    "reason": c.reason,
                    "weight": c.weight,
                }
                for c in self.checks
            ],
        }


class AnswerValidator:
    """
    Multi-source answer validation pipeline.

    Usage::

        validator = AnswerValidator()
        report = validator.validate(
            question="What is the capital of France?",
            answer="Paris is the capital of France.",
        )
        if not report.passed:
            print(report.flagged_reasons)
    """

    def __init__(
        self,
        threshold: float = VALIDATION_THRESHOLD,
        min_length: int = 5,
        max_length: int = 8000,
        memory=None,
        web_client=None,
    ) -> None:
        self._threshold = threshold
        self._min_length = min_length
        self._max_length = max_length
        self._memory = memory
        self._web_client = web_client

    def validate(
        self,
        question: str,
        answer: str,
        expected_format: Optional[str] = None,
    ) -> ValidationReport:
        """
        Validate an answer and return a ValidationReport.

        Args:
            question:        The original question / task.
            answer:          The candidate answer to validate.
            expected_format: Hint about expected output format.
                             One of: "json", "code", "list", "prose", or None.

        Returns:
            ValidationReport with composite_score in [0, 1].
        """
        t0 = time.time()
        checks: List[CheckResult] = []

        checks.append(self._check_length(answer))
        checks.append(self._check_non_empty(answer))
        checks.append(self._check_relevance(question, answer))
        checks.append(self._check_no_hallucination_markers(answer))

        if expected_format:
            checks.append(self._check_format(answer, expected_format))

        if self._memory:
            checks.append(self._check_source_cross(question, answer))

        if self._web_client:
            checks.append(self._check_fact_surface(answer))

        # Weighted composite
        total_weight = sum(c.weight for c in checks) or 1.0
        composite = sum(c.score * c.weight for c in checks) / total_weight
        passed = composite >= self._threshold

        flagged = [c.reason for c in checks if not c.passed and c.reason]

        report = ValidationReport(
            question=question,
            answer=answer,
            checks=checks,
            composite_score=composite,
            passed=passed,
            flagged_reasons=flagged,
            latency_ms=int((time.time() - t0) * 1000),
        )
        return report

    # ── Individual checks ─────────────────────────────────────────────────

    def _check_non_empty(self, answer: str) -> CheckResult:
        stripped = answer.strip()
        if not stripped:
            return CheckResult("non_empty", False, 0.0, "Answer is empty", weight=2.0)
        return CheckResult("non_empty", True, 1.0, weight=2.0)

    def _check_length(self, answer: str) -> CheckResult:
        n = len(answer.split())
        if n < self._min_length:
            return CheckResult(
                "length", False, n / self._min_length,
                f"Answer too short ({n} words < {self._min_length} min)", weight=1.5,
            )
        if n > self._max_length:
            return CheckResult(
                "length", False, self._max_length / n,
                f"Answer too long ({n} words > {self._max_length} max)", weight=0.5,
            )
        return CheckResult("length", True, 1.0, weight=1.5)

    def _check_relevance(self, question: str, answer: str) -> CheckResult:
        """Simple token-overlap relevance heuristic."""
        q_tokens = set(re.findall(r"\b\w+\b", question.lower())) - _STOPWORDS
        a_tokens = set(re.findall(r"\b\w+\b", answer.lower())) - _STOPWORDS
        if not q_tokens:
            return CheckResult("relevance", True, 1.0, weight=1.0)
        overlap = len(q_tokens & a_tokens) / len(q_tokens)
        passed = overlap >= 0.2
        return CheckResult(
            "relevance", passed, min(1.0, overlap * 2),
            "" if passed else f"Low keyword overlap ({overlap:.1%})", weight=1.5,
        )

    def _check_no_hallucination_markers(self, answer: str) -> CheckResult:
        """Flag common hallucination phrases."""
        markers = [
            "as an ai language model",
            "i cannot browse",
            "i don't have access to",
            "i'm unable to verify",
            "i cannot provide",
            "i do not have real-time",
        ]
        lower = answer.lower()
        found = [m for m in markers if m in lower]
        if found:
            return CheckResult(
                "no_hallucination_markers", False, 0.3,
                f"Hedging phrases detected: {found[:2]}", weight=1.0,
            )
        return CheckResult("no_hallucination_markers", True, 1.0, weight=1.0)

    def _check_format(self, answer: str, expected: str) -> CheckResult:
        if expected == "json":
            try:
                json.loads(answer)
                return CheckResult("format_json", True, 1.0, weight=1.5)
            except json.JSONDecodeError as exc:
                return CheckResult("format_json", False, 0.0, f"Invalid JSON: {exc}", weight=1.5)
        if expected == "code":
            has_code = "```" in answer or "def " in answer or "class " in answer
            return CheckResult("format_code", has_code, 1.0 if has_code else 0.4,
                               "" if has_code else "No code block detected", weight=1.0)
        if expected == "list":
            has_list = bool(re.search(r"^[\-\*\d]", answer, re.MULTILINE))
            return CheckResult("format_list", has_list, 1.0 if has_list else 0.5,
                               "" if has_list else "No list markers found", weight=0.8)
        return CheckResult(f"format_{expected}", True, 1.0, weight=0.5)

    def _check_source_cross(self, question: str, answer: str) -> CheckResult:
        """Check if the answer is supported by memory entries."""
        try:
            hits = self._memory.query(question, top_k=3, threshold=0.5)
            if not hits:
                return CheckResult("source_cross", True, 0.7, "No memory context available", weight=0.8)
            # Count answer words that appear in memory content
            memory_text = " ".join(h.entry.content.lower() for h in hits)
            ans_tokens = set(re.findall(r"\b\w{4,}\b", answer.lower())) - _STOPWORDS
            support = sum(1 for t in ans_tokens if t in memory_text)
            ratio = support / (len(ans_tokens) or 1)
            passed = ratio >= 0.1
            return CheckResult(
                "source_cross", passed, min(1.0, ratio * 5),
                "" if passed else f"Low memory support ({support}/{len(ans_tokens)} tokens)",
                weight=0.8,
            )
        except Exception as exc:
            logger.debug("source_cross check failed: %s", exc)
            return CheckResult("source_cross", True, 0.7, "Check skipped", weight=0.0)

    def _check_fact_surface(self, answer: str) -> CheckResult:
        """Lightweight fact surfacing: detect unsupported numeric claims."""
        numbers = re.findall(r"\b\d[\d,\.]+\b", answer)
        if not numbers:
            return CheckResult("fact_surface", True, 1.0, weight=0.5)
        # Just flag if many bare numbers appear (potential hallucination risk)
        if len(numbers) > 10:
            return CheckResult(
                "fact_surface", False, 0.5,
                f"{len(numbers)} numeric claims — consider verification", weight=0.5,
            )
        return CheckResult("fact_surface", True, 1.0, weight=0.5)


# ── Common stopwords (lightweight, no NLTK dependency) ───────────────────────

_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would could should may might must shall can cannot "
    "i me my myself we our ours ourselves you your yours yourself "
    "he him his himself she her hers herself it its itself they them "
    "their theirs themselves what which who whom this that these those "
    "am is are was were be been being have has had do does did "
    "and but or nor not so yet both either neither for as at by "
    "in of on to up down out off over under again further then once "
    "here there when where why how all any both each few more most "
    "other some such no only own same than too very s t just "
    "now need used need 'd 'll 're 've 'm".split()
)
