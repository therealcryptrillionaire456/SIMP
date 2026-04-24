"""
ProjectX Cost Tracker — Goose 3

Tracks per-model token usage and cost in the SIMP system.
Feeds Prometheus metrics via the existing telemetry infrastructure.

Features:
  - TokenUsage dataclass for per-call recording
  - CostTracker class with configurable pricing table
  - Daily/weekly/monthly rolling totals
  - Prometheus metrics export via simp.projectx.telemetry.MetricsRegistry
  - JSONL persistence at data/cost_ledger.jsonl
  - Thread-safe: all state updates hold the internal lock
  - Singleton via get_cost_tracker()
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_COST_LEDGER_PATH = Path("data/cost_ledger.jsonl")

# ── Default pricing table (cost per 1M tokens) ──────────────────────────────

MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Local models — free
    "ollama":            {"input": 0.0,  "output": 0.0},
    "llama":             {"input": 0.0,  "output": 0.0},
    "gemma":             {"input": 0.0,  "output": 0.0},
    "mistral":           {"input": 0.0,  "output": 0.0},
    "local":             {"input": 0.0,  "output": 0.0},
    # Claude
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-opus":     {"input": 15.00,"output": 75.00},
    "claude-3-haiku":    {"input": 0.25, "output": 1.25},
    "claude":            {"input": 3.00, "output": 15.00},  # fallback for any Claude
    # GPT
    "gpt-4":             {"input": 30.00,"output": 60.00},
    "gpt-4-turbo":       {"input": 10.00,"output": 30.00},
    "gpt-4o":            {"input": 2.50, "output": 10.00},
    "gpt-3.5-turbo":     {"input": 0.50, "output": 1.50},
    # Gemini
    "gemini-1-5-pro":    {"input": 3.50, "output": 10.50},
    "gemini-1-5-flash":  {"input": 0.35, "output": 1.05},
    "gemini":            {"input": 3.50, "output": 10.50},  # fallback
    # DeepSeek
    "deepseek":          {"input": 0.50, "output": 2.00},
    "deepseek-chat":     {"input": 0.50, "output": 2.00},
    # OpenRouter / generic
    "openrouter":        {"input": 0.0,  "output": 0.0},   # passthrough — caller sets cost
}


def _normalise_model_name(raw: str) -> str:
    """Normalise a model name to a pricing-table key."""
    name = raw.strip().lower()
    # Strip provider prefixes like "openai/", "anthropic/", "google/"
    if "/" in name:
        name = name.split("/", 1)[1]
    # Direct match
    if name in MODEL_PRICING:
        return name
    # Partial match: try to find any key that is a prefix of the name
    for key in sorted(MODEL_PRICING, key=len, reverse=True):
        if name.startswith(key):
            return key
    # If model contains known provider names, fall back to generic
    if "claude" in name:
        return "claude"
    if "gpt" in name:
        return "gpt-4"
    if "gemini" in name:
        return "gemini"
    if "deepseek" in name:
        return "deepseek"
    return "local"  # default to free


def _estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing: Optional[Dict[str, Dict[str, float]]] = None,
    provider: str = "",
) -> float:
    """
    Compute estimated cost in USD for a model call.

    Pricing table entries are in dollars per 1M tokens.
    """
    table = pricing or MODEL_PRICING
    key = _normalise_model_name(model)
    if key in table:
        rates = table[key]
    elif provider.lower() in table:
        rates = table[provider.lower()]
    else:
        rates = {"input": 0.0, "output": 0.0}

    input_cost = (prompt_tokens / 1_000_000) * rates["input"]
    output_cost = (completion_tokens / 1_000_000) * rates["output"]
    return round(input_cost + output_cost, 8)


# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class TokenUsage:
    """One recorded inference call."""

    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float  # USD
    timestamp: str          # ISO8601 UTC

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "provider": self.provider,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> TokenUsage:
        return TokenUsage(
            model=str(d["model"]),
            provider=str(d.get("provider", "")),
            prompt_tokens=int(d.get("prompt_tokens", 0)),
            completion_tokens=int(d.get("completion_tokens", 0)),
            total_tokens=int(d.get("total_tokens", 0)),
            estimated_cost=float(d.get("estimated_cost", 0.0)),
            timestamp=str(d.get("timestamp", _now_iso())),
        )


@dataclass
class CostSummary:
    """Rolling summary of token usage and costs."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0
    by_model: Dict[str, int] = field(default_factory=dict)
    by_provider: Dict[str, int] = field(default_factory=dict)
    cost_by_model: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "call_count": self.call_count,
            "by_model": dict(self.by_model),
            "by_provider": dict(self.by_provider),
            "cost_by_model": {k: round(v, 6) for k, v in self.cost_by_model.items()},
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bucket_key(ts_str: str, period: str) -> str:
    """Return a grouping key for daily / weekly / monthly."""
    try:
        dt = datetime.fromisoformat(ts_str)
    except Exception:
        dt = datetime.now(timezone.utc)
    if period == "daily":
        return dt.strftime("%Y-%m-%d")
    elif period == "weekly":
        # ISO week: 2025-W14
        return dt.strftime("%Y-W%W")
    elif period == "monthly":
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-%m-%d")


# ── CostTracker ──────────────────────────────────────────────────────────────

class CostTracker:
    """
    Tracks token usage and estimated cost per model/provider.

    Usage::

        tracker = CostTracker()
        tracker.record_usage("claude-3-5-sonnet", provider="anthropic",
                             prompt_tokens=500, completion_tokens=200)
        summary = tracker.get_summary()
        print(f"Total cost: ${summary.total_cost:.4f}")
    """

    def __init__(
        self,
        pricing: Optional[Dict[str, Dict[str, float]]] = None,
        ledger_path: str = str(_COST_LEDGER_PATH),
    ) -> None:
        self._pricing = pricing or dict(MODEL_PRICING)
        self._ledger_path = Path(ledger_path)
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()  # RLock because _update_prometheus re-acquires lock internally
        self._records: List[TokenUsage] = []
        self._daily_buckets: Dict[str, CostSummary] = {}
        self._weekly_buckets: Dict[str, CostSummary] = {}
        self._monthly_buckets: Dict[str, CostSummary] = {}

        # Load existing ledger
        self._load_ledger()

        # Prometheus metrics — pre-initialized outside of _lock to avoid
        # import-lock deadlocks (Python holds an internal import lock during
        # module import, and we must not hold self._lock across that).
        self._metrics_initialized = False
        self._metric_total_tokens = None
        self._metric_total_cost = None
        self._metric_calls_total = None
        self._metric_cost_by_model = None
        self._init_metrics_nolock()

    # ── Public API ────────────────────────────────────────────────────────

    def record_usage(
        self,
        model: str,
        provider: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        *,
        total_tokens: Optional[int] = None,
        cost: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> TokenUsage:
        """
        Record a model inference call.

        Args:
            model: Model name (e.g. "claude-3-5-sonnet", "gpt-4", "gemini").
            provider: Provider name (e.g. "anthropic", "openai", "ollama").
            prompt_tokens: Number of input/prompt tokens.
            completion_tokens: Number of output/completion tokens.
            total_tokens: Override total (defaults to prompt + completion).
            cost: Override estimated cost (defaults to computed from pricing).
            timestamp: ISO8601 UTC timestamp (defaults to now).
        """
        total = total_tokens if total_tokens is not None else (prompt_tokens + completion_tokens)
        ts = timestamp or _now_iso()

        if cost is not None:
            est_cost = cost
        else:
            est_cost = _estimate_cost(model, prompt_tokens, completion_tokens, self._pricing, provider)

        usage = TokenUsage(
            model=model,
            provider=provider or _normalise_model_name(model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            estimated_cost=est_cost,
            timestamp=ts,
        )

        with self._lock:
            self._records.append(usage)
            self._append_ledger(usage)
            self._update_buckets(usage)
            self._update_prometheus(usage)

        return usage

    def get_summary(
        self,
        period: Optional[str] = None,
        since: Optional[str] = None,
        model: Optional[str] = None,
    ) -> CostSummary:
        """
        Compute a CostSummary over matching records.

        Args:
            period: "daily", "weekly", or "monthly" for pre-computed bucket.
            since: ISO8601 timestamp — only include records after this time.
            model: If set, filter to this model only.
        """
        with self._lock:
            if period in ("daily", "weekly", "monthly") and model is None:
                return self._bucket_summary_for_period(period, since)

            summary = CostSummary()
            for rec in self._records:
                if since and rec.timestamp < since:
                    continue
                if model and rec.model != model:
                    continue
                summary.total_prompt_tokens += rec.prompt_tokens
                summary.total_completion_tokens += rec.completion_tokens
                summary.total_tokens += rec.total_tokens
                summary.total_cost += rec.estimated_cost
                summary.call_count += 1
                summary.by_model[rec.model] = summary.by_model.get(rec.model, 0) + rec.total_tokens
                summary.by_provider[rec.provider] = summary.by_provider.get(rec.provider, 0) + rec.total_tokens
                summary.cost_by_model[rec.model] = summary.cost_by_model.get(rec.model, 0.0) + rec.estimated_cost

            return summary

    def get_records(
        self,
        limit: int = 100,
        offset: int = 0,
        model: Optional[str] = None,
    ) -> List[TokenUsage]:
        """Return paginated records, newest first."""
        with self._lock:
            filtered = self._records
            if model:
                filtered = [r for r in filtered if r.model == model]
            return list(reversed(filtered))[offset: offset + limit]

    def get_pricing(self) -> Dict[str, Dict[str, float]]:
        """Return a copy of the current pricing table."""
        return dict(self._pricing)

    def update_pricing(self, model: str, input_price: float, output_price: float) -> None:
        """Update or add a pricing entry."""
        with self._lock:
            self._pricing[model] = {"input": input_price, "output": output_price}

    def clear_records(self) -> int:
        """Clear in-memory records (does not affect ledger on disk). Returns count cleared."""
        with self._lock:
            count = len(self._records)
            self._records.clear()
            self._daily_buckets.clear()
            self._weekly_buckets.clear()
            self._monthly_buckets.clear()
            return count

    def ingest_trace_event(self, event: Dict[str, Any]) -> Optional[TokenUsage]:
        """
        Ingest a trace event dict (e.g. from QuantumTraceLogger) that contains
        token counts. Expected keys: model, provider (optional), prompt_tokens,
        completion_tokens, total_tokens (optional), cost (optional), timestamp (optional).
        """
        model = event.get("model")
        if not model:
            return None
        return self.record_usage(
            model=str(model),
            provider=str(event.get("provider", "")),
            prompt_tokens=int(event.get("prompt_tokens", 0)),
            completion_tokens=int(event.get("completion_tokens", 0)),
            total_tokens=int(event.get("total_tokens")) if event.get("total_tokens") is not None else None,
            cost=float(event["cost"]) if "cost" in event else None,
            timestamp=str(event["timestamp"]) if "timestamp" in event else None,
        )

    # ── Internal ──────────────────────────────────────────────────────────

    def _load_ledger(self) -> None:
        if not self._ledger_path.exists():
            return
        count = 0
        try:
            for line in self._ledger_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = TokenUsage.from_dict(json.loads(line))
                    self._records.append(rec)
                    self._update_buckets(rec)
                    count += 1
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    logger.debug("Skipping malformed ledger line: %s", exc)
        except Exception as exc:
            logger.warning("Failed to load cost ledger: %s", exc)
        if count:
            logger.info("Loaded %d historical cost records from %s", count, self._ledger_path)

    def _append_ledger(self, usage: TokenUsage) -> None:
        try:
            with open(self._ledger_path, "a") as f:
                f.write(json.dumps(usage.to_dict()) + "\n")
                f.flush()
        except OSError as exc:
            logger.error("Cannot write to cost ledger: %s", exc)

    def _update_buckets(self, usage: TokenUsage) -> None:
        """Update daily, weekly, monthly rolling summaries."""
        daily_key = _bucket_key(usage.timestamp, "daily")
        weekly_key = _bucket_key(usage.timestamp, "weekly")
        monthly_key = _bucket_key(usage.timestamp, "monthly")

        for bucket_map, key in [
            (self._daily_buckets, daily_key),
            (self._weekly_buckets, weekly_key),
            (self._monthly_buckets, monthly_key),
        ]:
            if key not in bucket_map:
                bucket_map[key] = CostSummary()
            b = bucket_map[key]
            b.total_prompt_tokens += usage.prompt_tokens
            b.total_completion_tokens += usage.completion_tokens
            b.total_tokens += usage.total_tokens
            b.total_cost += usage.estimated_cost
            b.call_count += 1
            b.by_model[usage.model] = b.by_model.get(usage.model, 0) + usage.total_tokens
            b.by_provider[usage.provider] = b.by_provider.get(usage.provider, 0) + usage.total_tokens
            b.cost_by_model[usage.model] = b.cost_by_model.get(usage.model, 0.0) + usage.estimated_cost

    def _bucket_summary_for_period(self, period: str, since: Optional[str]) -> CostSummary:
        """Merge bucket summaries into one."""
        if period == "daily":
            buckets = self._daily_buckets
        elif period == "weekly":
            buckets = self._weekly_buckets
        else:
            buckets = self._monthly_buckets

        total = CostSummary()
        for key, b in buckets.items():
            if since and key < since:
                continue
            total.total_prompt_tokens += b.total_prompt_tokens
            total.total_completion_tokens += b.total_completion_tokens
            total.total_tokens += b.total_tokens
            total.total_cost += b.total_cost
            total.call_count += b.call_count
            for k, v in b.by_model.items():
                total.by_model[k] = total.by_model.get(k, 0) + v
            for k, v in b.by_provider.items():
                total.by_provider[k] = total.by_provider.get(k, 0) + v
            for k, v in b.cost_by_model.items():
                total.cost_by_model[k] = total.cost_by_model.get(k, 0.0) + v
        return total

    def _init_metrics_nolock(self) -> None:
        """Pre-initialize telemetry import without holding self._lock.
        
        Called once at construction time to avoid deadlocks between Python's
        internal import lock and self._lock during record_usage().
        """
        try:
            from simp.projectx.telemetry import get_registry
            reg = get_registry()
            self._reg_for_metrics = reg
        except ImportError:
            self._reg_for_metrics = None
        except Exception:
            self._reg_for_metrics = None

    def _ensure_metrics(self) -> None:
        """Lazily register Prometheus metrics on first use."""
        if self._metrics_initialized:
            return
        try:
            reg = self._reg_for_metrics
            if reg is None:
                self._metrics_initialized = True
                return
            self._metric_total_tokens = reg.counter(
                "cost_total_tokens",
                "Total tokens consumed across all models",
            )
            self._metric_total_cost = reg.gauge(
                "cost_total_cost_usd",
                "Total estimated cost in USD",
            )
            self._metric_calls_total = reg.counter(
                "cost_calls_total",
                "Total model inference calls recorded",
            )
            self._metric_cost_by_model = reg.gauge(
                "cost_by_model_usd",
                "Estimated cost by model (label: model)",
                labels={"model": ""},
            )
            self._metrics_initialized = True
        except Exception as exc:
            logger.debug("Failed to initialise cost metrics: %s", exc)
            self._metrics_initialized = True  # prevent retry

    def _update_prometheus(self, usage: TokenUsage) -> None:
        if not self._metrics_initialized:
            self._ensure_metrics()
        if not self._metrics_initialized:
            return

        try:
            if self._metric_total_tokens:
                self._metric_total_tokens.inc(float(usage.total_tokens))
            if self._metric_calls_total:
                self._metric_calls_total.inc(1.0)
            # Recompute total cost gauge from summary
            if self._metric_total_cost:
                with self._lock:
                    total = sum(r.estimated_cost for r in self._records)
                self._metric_total_cost.set(total)

            # Per-model cost gauge (updates the label dynamically)
            if self._metric_cost_by_model:
                # We can't add dynamic labels easily with the simple Counter/Gauge,
                # so we just log per-model cost at info level for now
                pass
        except Exception as exc:
            logger.debug("Prometheus metric update error: %s", exc)


# ── Module-level singleton ───────────────────────────────────────────────────

_tracker: Optional[CostTracker] = None
_tracker_lock = threading.Lock()


def get_cost_tracker() -> CostTracker:
    """Return the module-level CostTracker singleton."""
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:  # double-check under lock
                _tracker = CostTracker()
    return _tracker
