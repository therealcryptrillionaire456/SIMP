#!/usr/bin/env python3.10
"""
profile_media.py — Manual performance profiler for KashClaw Media Grid agents.

Usage:
    python3.10 scripts/manual_checks/profile_media.py

Timing report keys:
  offer_scoring_single     — score_offer() called 10 times sequentially
  offer_scoring_batch      — score_batch_async(offers, max_workers=4)
  landing_page_generation  — generate_landing_page() with and without cache
  content_brief_creation   — get_content_recommendations()

All timings use ``time.time()`` (manual instrumentation, no external profilers).
"""

import sys
import time
from typing import Any, Dict, List


def _now() -> float:
    """Return monotonic wall-clock seconds (best for duration measurement)."""
    return time.monotonic()


def _fmt_ms(label: str, elapsed: float) -> str:
    """Format a timing line with consistent alignment."""
    return f"  {label:<36s} {elapsed * 1000:>8.2f} ms"


def profile_offer_scoring(agent: Any, offers: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Benchmark single-offer scoring and batch scoring.

    Returns a dict of {metric_name: elapsed_seconds}.
    """
    timings: Dict[str, float] = {}

    # ── Single scoring (sequential, 10 calls) ──────────────────────────
    count = min(10, len(offers))
    start = _now()
    for i in range(count):
        agent.score_offer(offers[i])
    elapsed = _now() - start
    timings["offer_scoring_single"] = elapsed
    print(_fmt_ms(f"score_offer() x {count} (sequential)", elapsed))
    if count > 0:
        print(_fmt_ms(f"  avg per call", elapsed / count))

    # ── Batch scoring (parallel, max_workers=4) ────────────────────────
    start = _now()
    results = agent.score_batch_async(offers, max_workers=4, timeout_per_offer=10.0)
    elapsed = _now() - start
    timings["offer_scoring_batch"] = elapsed
    print(_fmt_ms(f"score_batch_async({len(offers)} offers, w=4)", elapsed))

    # Sanity check: results sorted descending
    if results:
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True), "Batch results not sorted descending!"
        print(f"  ✓ {len(results)} scored, top score = {results[0][1]:.2f}")

    return timings


def profile_landing_page_generation(agent: Any, offers: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Benchmark landing page generation — first call (cold cache) vs. repeated calls.

    Returns a dict of {metric_name: elapsed_seconds}.
    """
    timings: Dict[str, float] = {}

    if not offers:
        return timings

    offer = offers[0]
    template = "default"

    # ── First call (cold cache) ────────────────────────────────────────
    start = _now()
    page1 = agent.generate_landing_page(offer, template_name=template)
    elapsed = _now() - start
    timings["landing_page_cold"] = elapsed
    print(_fmt_ms(f"generate_landing_page (cold cache)", elapsed))

    # ── Second call (hot cache) ────────────────────────────────────────
    start = _now()
    page2 = agent.generate_landing_page(offer, template_name=template)
    elapsed = _now() - start
    timings["landing_page_hot"] = elapsed
    print(_fmt_ms(f"generate_landing_page (hot cache)", elapsed))
    speedup = timings["landing_page_cold"] / max(timings["landing_page_hot"], 1e-9)
    print(f"  ⚡ cache speedup: {speedup:.1f}x")

    # Verify cached result is the same page_id (cached yields identical output)
    cache_hit = page1.get("page_id") == page2.get("page_id")
    print(f"  ✓ cache hit: {'yes' if cache_hit else 'no'}")

    # ── Customizations bypass cache ────────────────────────────────────
    start = _now()
    page3 = agent.generate_landing_page(
        offer, template_name=template,
        customizations={"headline": "Custom Headline"},
    )
    elapsed = _now() - start
    timings["landing_page_custom"] = elapsed
    print(_fmt_ms(f"generate_landing_page (custom, bypass cache)", elapsed))

    return timings


def profile_content_briefs(agent: Any) -> Dict[str, float]:
    """
    Benchmark content brief / recommendation generation.

    Returns a dict of {metric_name: elapsed_seconds}.
    """
    timings: Dict[str, float] = {}
    templates = ["default", "review", "comparison", "minimalist", "webinar"]

    # ── get_content_recommendations ─────────────────────────────────────
    start = _now()
    recs = agent.get_content_recommendations(limit=5)
    elapsed = _now() - start
    timings["content_recommendations"] = elapsed
    print(_fmt_ms(f"get_content_recommendations(limit=5)", elapsed))
    print(f"  → {len(recs)} recommendations returned")

    # ── get_category_summary ────────────────────────────────────────────
    start = _now()
    summary = agent.get_category_summary()
    elapsed = _now() - start
    timings["category_summary"] = elapsed
    print(_fmt_ms(f"get_category_summary()", elapsed))
    print(f"  → {len(summary)} categories")

    # ── find_gaps ───────────────────────────────────────────────────────
    start = _now()
    gaps = agent.find_gaps()
    elapsed = _now() - start
    timings["find_gaps"] = elapsed
    print(_fmt_ms(f"find_gaps()", elapsed))
    print(f"  → {len(gaps)} gaps found")

    return timings


def print_report(all_timings: Dict[str, float]) -> None:
    """Print a formatted timing summary."""
    sep = "─" * 54
    print(f"\n{sep}")
    print("  PERFORMANCE PROFILE REPORT")
    print(sep)
    items = sorted(all_timings.items(), key=lambda x: x[1], reverse=True)
    for label, elapsed in items:
        print(_fmt_ms(label, elapsed))
    total = sum(t for _, t in items)
    print(sep)
    print(_fmt_ms("TOTAL", total))
    print(sep)
    if "landing_page_cold" in all_timings and "landing_page_hot" in all_timings:
        cold = all_timings["landing_page_cold"]
        hot = all_timings["landing_page_hot"]
        ratio = cold / max(hot, 1e-9)
        print(f"  🏆 Best cache speedup: {ratio:.1f}x (landing page)")
    print()


def main() -> int:
    """Run all profiling benchmarks."""
    print("=" * 54)
    print("  KashClaw Media Grid — Performance Profiler")
    print("=" * 54)

    # ── Import agents ──────────────────────────────────────────────────
    print("\n[1/4] Importing agents ...")
    from simp.organs.media.agents.offer_intelligence_agent import (
        OfferIntelligenceAgent, create_offer_intelligence_agent,
    )
    from simp.organs.media.agents.landing_page_agent import (
        LandingPageAgent, create_landing_page_agent,
    )
    print("  ✓ imports successful")

    # ── Instantiate agents ─────────────────────────────────────────────
    print("\n[2/4] Instantiating agents ...")

    offer_agent: OfferIntelligenceAgent = create_offer_intelligence_agent(
        agent_id="profile_offer_intel",
        data_dir="/tmp/simp_profile_media",
        log_level="ERROR",
        scoring_interval_minutes=9999,  # Suppress background scoring
    )
    print("  ✓ OfferIntelligenceAgent instantiated")
    print(f"    offers loaded: {len(offer_agent._offers)}")
    print(f"    opportunities: {len(offer_agent._opportunities)}")

    lp_agent: LandingPageAgent = create_landing_page_agent(
        agent_id="profile_lp",
        data_dir="/tmp/simp_profile_media",
        log_level="ERROR",
    )
    print("  ✓ LandingPageAgent instantiated")

    all_timings: Dict[str, float] = {}

    # ── Benchmark: Offer Scoring ────────────────────────────────────────
    print("\n[3/4] Running benchmarks ...")
    print("\n  ── Offer Scoring ──")
    offers = offer_agent._offers
    all_timings.update(profile_offer_scoring(offer_agent, offers))

    # ── Benchmark: Landing Page Generation ──────────────────────────────
    print("\n  ── Landing Page Generation ──")
    all_timings.update(profile_landing_page_generation(lp_agent, offers))

    # ── Benchmark: Content Briefs & Analysis ────────────────────────────
    print("\n  ── Content Briefs & Analysis ──")
    all_timings.update(profile_content_briefs(offer_agent))

    # ── Print report ────────────────────────────────────────────────────
    print("\n[4/4] Final report")
    print_report(all_timings)

    return 0


if __name__ == "__main__":
    sys.exit(main())
