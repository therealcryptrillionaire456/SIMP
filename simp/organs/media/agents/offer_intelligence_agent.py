"""
Offer Intelligence Agent for KashClaw Media Grid.

Responsible for:
- Scoring and ranking affiliate offers by profitability
- Detecting commission rate changes and inventory shifts
- Cross-referencing offer data with trend research
- Identifying high-opportunity content niches
- Maintaining historical offer performance tracking
"""
import asyncio
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from simp.organs.media.agents.base_media_agent import BaseMediaAgent
from simp.organs.media.models import (
    AffiliateOffer, ContentOpportunityScore,
    OfferCategory, ComplianceRisk
)


class OfferIntelligenceAgent(BaseMediaAgent):
    """Agent that analyzes and scores affiliate offers for content targeting."""

    def __init__(
        self,
        agent_id: str = "offer_intelligence",
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        scoring_interval_minutes: int = 30,
        min_commission_threshold: float = 5.0,
        max_payout_threshold: float = 5000.0
    ):
        """Initialize the Offer Intelligence Agent."""
        super().__init__(
            agent_id=agent_id,
            agent_name="Offer Intelligence Agent",
            data_dir=data_dir,
            log_level=log_level
        )

        self.scoring_interval_minutes = scoring_interval_minutes
        self.min_commission_threshold = min_commission_threshold
        self.max_payout_threshold = max_payout_threshold

        # In-memory caches
        self._offers: List[Dict[str, Any]] = []
        self._opportunities: List[Dict[str, Any]] = []
        self._historical_trends: Dict[str, List[float]] = {}
        self._last_scoring_time: Optional[float] = None

        # Load mock data
        self._load_mock_offers()
        self._initial_score()

        self.logger.info(
            f"Offer Intelligence Agent initialized "
            f"(interval={scoring_interval_minutes}m, "
            f"min_commission={min_commission_threshold})"
        )

    # ------------------------------------------------------------------
    # Mock Data
    # ------------------------------------------------------------------

    def _load_mock_offers(self) -> None:
        """Seed mock affiliate offers across categories."""
        self._offers = [
            {
                "offer_id": "off-001",
                "name": "Higgsfield AI - Video Generator",
                "category": "saas",
                "url": "https://higgsfield.ai/?ref=simp",
                "commission_rate": 30.0,
                "commission_type": "recurring",
                "payout": 0.0,
                "cookie_days": 30,
                "epc": 4.50,
                "merchant_score": 4.2,
                "conversion_rate": 0.035,
                "network": "impact",
                "is_active": True,
                "restrictions": [],
                "tags": ["ai", "video", "creation", "trending"]
            },
            {
                "offer_id": "off-002",
                "name": "Notion AI - Workspace Plus",
                "category": "saas",
                "url": "https://notion.so/?ref=simp",
                "commission_rate": 20.0,
                "commission_type": "recurring",
                "payout": 0.0,
                "cookie_days": 90,
                "epc": 3.80,
                "merchant_score": 4.5,
                "conversion_rate": 0.042,
                "network": "shareasale",
                "is_active": True,
                "restrictions": [],
                "tags": ["productivity", "ai", "workspace", "high_epc"]
            },
            {
                "offer_id": "off-003",
                "name": "Carrd - Landing Page Builder",
                "category": "saas",
                "url": "https://carrd.co/?ref=simp",
                "commission_rate": 25.0,
                "commission_type": "recurring",
                "payout": 0.0,
                "cookie_days": 60,
                "epc": 2.90,
                "merchant_score": 4.0,
                "conversion_rate": 0.028,
                "network": "shareasale",
                "is_active": True,
                "restrictions": [],
                "tags": ["landing pages", "builder", "low_cost"]
            },
            {
                "offer_id": "off-004",
                "name": "Shopify - Commerce Starter",
                "category": "ecommerce",
                "url": "https://shopify.com/?ref=simp",
                "commission_rate": 100.0,
                "commission_type": "flat",
                "payout": 150.0,
                "cookie_days": 30,
                "epc": 12.00,
                "merchant_score": 4.3,
                "conversion_rate": 0.018,
                "network": "impact",
                "is_active": True,
                "restrictions": ["new_signups_only"],
                "tags": ["ecommerce", "high_payout", "enterprise"]
            },
            {
                "offer_id": "off-005",
                "name": "Coinbase - Crypto Starter",
                "category": "finance",
                "url": "https://coinbase.com/?ref=simp",
                "commission_rate": 50.0,
                "commission_type": "flat",
                "payout": 50.0,
                "cookie_days": 30,
                "epc": 8.50,
                "merchant_score": 3.8,
                "conversion_rate": 0.025,
                "network": "cj",
                "is_active": True,
                "restrictions": ["us_only"],
                "tags": ["crypto", "finance", "high_epc"]
            },
            {
                "offer_id": "off-006",
                "name": "NordVPN - Security Suite",
                "category": "tech",
                "url": "https://nordvpn.com/?ref=simp",
                "commission_rate": 40.0,
                "commission_type": "flat",
                "payout": 35.0,
                "cookie_days": 30,
                "epc": 6.20,
                "merchant_score": 4.1,
                "conversion_rate": 0.032,
                "network": "impact",
                "is_active": True,
                "restrictions": [],
                "tags": ["vpn", "security", "evergreen"]
            },
            {
                "offer_id": "off-007",
                "name": "Teachable - Course Platform",
                "category": "education",
                "url": "https://teachable.com/?ref=simp",
                "commission_rate": 30.0,
                "commission_type": "recurring",
                "payout": 0.0,
                "cookie_days": 45,
                "epc": 5.10,
                "merchant_score": 4.0,
                "conversion_rate": 0.030,
                "network": "shareasale",
                "is_active": True,
                "restrictions": [],
                "tags": ["education", "courses", "creators"]
            },
            {
                "offer_id": "off-008",
                "name": "Kucoin - Trading Pro",
                "category": "finance",
                "url": "https://kucoin.com/?ref=simp",
                "commission_rate": 60.0,
                "commission_type": "flat",
                "payout": 80.0,
                "cookie_days": 30,
                "epc": 9.90,
                "merchant_score": 3.5,
                "conversion_rate": 0.015,
                "network": "cj",
                "is_active": True,
                "restrictions": ["non_us"],
                "tags": ["crypto", "trading", "high_payout"]
            },
            {
                "offer_id": "off-009",
                "name": "Dexcom - Glucose Monitor",
                "category": "health",
                "url": "https://dexcom.com/?ref=simp",
                "commission_rate": 10.0,
                "commission_type": "flat",
                "payout": 100.0,
                "cookie_days": 30,
                "epc": 15.00,
                "merchant_score": 4.4,
                "conversion_rate": 0.012,
                "network": "impact",
                "is_active": True,
                "restrictions": ["healthcare_vertical"],
                "tags": ["health", "medical", "high_epc", "niche"]
            },
            {
                "offer_id": "off-010",
                "name": "Webflow - Designer CMS",
                "category": "saas",
                "url": "https://webflow.com/?ref=simp",
                "commission_rate": 25.0,
                "commission_type": "recurring",
                "payout": 0.0,
                "cookie_days": 60,
                "epc": 4.20,
                "merchant_score": 4.3,
                "conversion_rate": 0.038,
                "network": "shareasale",
                "is_active": True,
                "restrictions": [],
                "tags": ["web design", "cms", "saas", "high_rate"]
            }
        ]

    # ------------------------------------------------------------------
    # Core Scoring Logic
    # ------------------------------------------------------------------

    def _initial_score(self) -> None:
        """Run initial scoring pass on all loaded offers."""
        self._opportunities = []
        for offer in self._offers:
            score = self.score_offer(offer)
            opp = self._build_opportunity(offer, score)
            self._opportunities.append(opp)
        self._opportunities.sort(
            key=lambda x: x["opportunity_score"], reverse=True
        )
        self._log_operation("initial_scoring", "success", {
            "offers_scored": len(self._opportunities),
            "top_offer": self._opportunities[0]["offer_name"]
            if self._opportunities else None
        })

    def score_offer(self, offer: Dict[str, Any]) -> float:
        """
        Compute a composite opportunity score for a single offer.

        Factors considered:
        - Commission rate (weighted by type)
        - EPC (earnings per click)
        - Conversion rate
        - Merchant trust score
        - Active status penalty
        - Tag relevance bonus
        - Restrictions penalty
        """
        score = 0.0

        # --- Commission Value (0-25 points) ---
        comm_rate = offer.get("commission_rate", 0.0)
        comm_type = offer.get("commission_type", "flat")
        payout = offer.get("payout", 0.0)

        if comm_type == "recurring":
            # Recurring is worth more — estimate 6-month value
            comm_value = comm_rate * 6
        elif comm_type == "flat" and payout > 0:
            comm_value = payout
        else:
            comm_value = comm_rate

        # Normalize: $0-200+ scaled to 0-25
        score += min(25.0, comm_value / 8.0)

        # --- EPC Score (0-20 points) ---
        epc = offer.get("epc", 0.0)
        score += min(20.0, epc * 2.0)

        # --- Conversion Rate (0-15 points) ---
        conv = offer.get("conversion_rate", 0.0)
        score += min(15.0, conv * 300.0)

        # --- Merchant Trust (0-15 points) ---
        merchant = offer.get("merchant_score", 3.0)
        score += (merchant / 5.0) * 15.0

        # --- Active Status (0 or -10 penalty) ---
        if not offer.get("is_active", True):
            score -= 10.0

        # --- Tags Bonus (0-10 points) ---
        tags = offer.get("tags", [])
        bonus_keywords = ["trending", "high_epc", "high_rate", "evergreen"]
        tag_bonus = sum(2.0 for t in tags if t in bonus_keywords)
        score += min(10.0, tag_bonus)

        # --- Restrictions Penalty (0 to -10) ---
        restrictions = offer.get("restrictions", [])
        score -= len(restrictions) * 3.0

        return max(0.0, min(100.0, score))

    # ------------------------------------------------------------------
    # Async Batching (Tranche 7)
    # ------------------------------------------------------------------

    def score_batch_async(
        self,
        offers: List[Dict[str, Any]],
        max_workers: int = 4,
        timeout_per_offer: float = 10.0
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Score a batch of offers in parallel using a ThreadPoolExecutor.

        Args:
            offers: List of offer dicts to score
            max_workers: Maximum number of parallel workers (default 4)
            timeout_per_offer: Maximum seconds to wait per offer (default 10)

        Returns:
            List of (offer, score) tuples sorted by score descending.

        Each offer is scored independently. If an individual offer times out
        or raises an exception, it receives a score of 0.0 and the error is
        logged but does not halt the batch.
        """
        if not offers:
            return []

        results: List[Optional[Tuple[Dict[str, Any], float]]] = [None] * len(offers)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self._score_single_offer_with_timeout, offer, timeout_per_offer): i
                for i, offer in enumerate(offers)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    offer, score = future.result()
                    results[idx] = (offer, score)
                except TimeoutError:
                    self.logger.warning(
                        f"Offer scoring timed out after {timeout_per_offer}s (index {idx})"
                    )
                    results[idx] = (offers[idx], 0.0)
                except Exception as e:
                    self.logger.error(
                        f"Offer scoring failed for index {idx}: {e}"
                    )
                    results[idx] = (offers[idx], 0.0)

        # Filter out any remaining None entries (shouldn't happen)
        scored: List[Tuple[Dict[str, Any], float]] = [
            r for r in results if r is not None
        ]

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _score_single_offer_with_timeout(
        self,
        offer: Dict[str, Any],
        timeout: float
    ) -> Tuple[Dict[str, Any], float]:
        """
        Score a single offer with a wall-clock timeout.

        If execution exceeds *timeout* seconds the calling thread will see a
        TimeoutError raised by the future. This wrapper exists so that
        score_batch_async can associate the timed-out offer with a 0.0 score
        rather than losing the offer entirely.
        """
        start = time.monotonic()
        score = self.score_offer(offer)
        elapsed = time.monotonic() - start
        if elapsed > timeout:
            raise TimeoutError(
                f"Score computation took {elapsed:.2f}s "
                f"(limit {timeout}s) for offer {offer.get('offer_id', '?')}"
            )
        return (offer, score)

    def _build_opportunity(
        self,
        offer: Dict[str, Any],
        score: float
    ) -> Dict[str, Any]:
        """Build an opportunity record from an offer and its computed score."""
        now = datetime.utcnow().isoformat()
        return {
            "opportunity_id": f"opp-{offer['offer_id']}",
            "offer_id": offer["offer_id"],
            "offer_name": offer["name"],
            "category": offer["category"],
            "opportunity_score": round(score, 2),
            "commission_rate": offer["commission_rate"],
            "commission_type": offer["commission_type"],
            "payout": offer["payout"],
            "epc": offer["epc"],
            "network": offer["network"],
            "conversion_rate": offer["conversion_rate"],
            "tags": offer["tags"],
            "restrictions": offer.get("restrictions", []),
            "tier": self._tier_for_score(score),
            "last_updated": now,
            "created_at": now
        }

    def _tier_for_score(self, score: float) -> str:
        """Map a numeric score to a priority tier."""
        if score >= 75.0:
            return "platinum"
        elif score >= 55.0:
            return "gold"
        elif score >= 35.0:
            return "silver"
        else:
            return "bronze"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_top_opportunities(
        self,
        category: Optional[str] = None,
        min_score: float = 0.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return the highest-scoring opportunities, filtered and sorted."""
        results = self._opportunities
        if category:
            results = [o for o in results if o["category"] == category]
        if min_score > 0.0:
            results = [o for o in results if o["opportunity_score"] >= min_score]
        return sorted(results, key=lambda x: x["opportunity_score"], reverse=True)[:limit]

    def get_opportunity_by_id(self, opportunity_id: str) -> Optional[Dict[str, Any]]:
        """Look up a single opportunity by ID."""
        for opp in self._opportunities:
            if opp["opportunity_id"] == opportunity_id:
                return opp
        return None

    def get_offer_by_id(self, offer_id: str) -> Optional[Dict[str, Any]]:
        """Look up a single offer by ID."""
        for off in self._offers:
            if off["offer_id"] == offer_id:
                return off
        return None

    def refresh_scores(self) -> List[Dict[str, Any]]:
        """Re-score all offers and return updated opportunities."""
        old_top = self._opportunities[0] if self._opportunities else None
        self._initial_score()
        new_top = self._opportunities[0] if self._opportunities else None

        self._append_to_ledger("score_refresh_log", {
            "timestamp": datetime.utcnow().isoformat(),
            "offers_scored": len(self._offers),
            "previous_top": old_top["offer_name"] if old_top else None,
            "new_top": new_top["offer_name"] if new_top else None
        })
        return self._opportunities

    def get_category_summary(self) -> List[Dict[str, Any]]:
        """Aggregate scoring data by category."""
        from collections import defaultdict
        by_cat: Dict[str, List[Dict]] = defaultdict(list)
        for opp in self._opportunities:
            by_cat[opp["category"]].append(opp)

        summary = []
        for cat, items in sorted(by_cat.items()):
            scores = [i["opportunity_score"] for i in items]
            summary.append({
                "category": cat,
                "count": len(items),
                "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
                "top_score": round(max(scores), 2) if scores else 0.0,
                "top_offer": max(items, key=lambda x: x["opportunity_score"])["offer_name"]
                if items else None,
                "tier_distribution": {
                    "platinum": sum(1 for i in items if i["tier"] == "platinum"),
                    "gold": sum(1 for i in items if i["tier"] == "gold"),
                    "silver": sum(1 for i in items if i["tier"] == "silver"),
                    "bronze": sum(1 for i in items if i["tier"] == "bronze")
                }
            })
        return summary

    def get_content_recommendations(
        self,
        platform: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate content brief recommendations based on top opportunities."""
        top = self.get_top_opportunities(limit=limit)
        recommendations = []
        for opp in top:
            rec = {
                "recommended_topic": f"How to Use {opp['offer_name']} for Maximum Results",
                "offer_name": opp["offer_name"],
                "opportunity_score": opp["opportunity_score"],
                "category": opp["category"],
                "suggested_formats": self._suggest_formats(opp),
                "target_keywords": opp["tags"],
                "tier": opp["tier"],
                "estimated_monthly_epc": opp["epc"] * 30,
                "commission_potential": self._estimate_monthly_commission(opp)
            }
            recommendations.append(rec)
        return recommendations

    def _suggest_formats(self, opportunity: Dict[str, Any]) -> List[str]:
        """Suggest content formats based on opportunity attributes."""
        formats = ["tutorial"]
        tags = opportunity.get("tags", [])
        if "trending" in tags:
            formats.append("trend_reaction")
        if "high_payout" in tags:
            formats.append("comparison_review")
        if "evergreen" in tags:
            formats.append("educational_series")
        return formats

    def _estimate_monthly_commission(self, opportunity: Dict[str, Any]) -> float:
        """Rough monthly commission estimate based on EPC and conversion."""
        est_visitors = 500  # conservative monthly estimate per content piece
        epc = opportunity.get("epc", 0.0)
        conv = opportunity.get("conversion_rate", 0.035)
        est_commission = est_visitors * conv * epc
        return round(est_commission, 2)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scoring agent loop."""
        self.is_running = True
        self.logger.info("Offer Intelligence Agent started")
        asyncio.create_task(self._scoring_loop())

    async def stop(self) -> None:
        """Gracefully stop the agent."""
        self.is_running = False
        self.logger.info("Offer Intelligence Agent stopped")

    async def _scoring_loop(self) -> None:
        """Periodically refresh scores and log changes."""
        while self.is_running:
            try:
                self._log_operation("scoring_cycle", "success", {
                    "timestamp": datetime.utcnow().isoformat(),
                    "offers_count": len(self._offers),
                    "opportunities_count": len(self._opportunities)
                })
                self.refresh_scores()
                self._last_scoring_time = time.time()
            except Exception as e:
                self.logger.error(f"Scoring cycle error: {e}")

            await asyncio.sleep(self.scoring_interval_minutes * 60)

    # ------------------------------------------------------------------
    # Analysis Helpers
    # ------------------------------------------------------------------

    def find_gaps(self) -> List[Dict[str, Any]]:
        """Identify categories with high avg score but low offer count."""
        summary = self.get_category_summary()
        gaps = []
        for s in summary:
            if s["count"] <= 2 and s["avg_score"] >= 40.0:
                gaps.append({
                    "category": s["category"],
                    "current_offers": s["count"] or 0,
                    "avg_score": s["avg_score"] or 0.0,
                    "top_score": s["top_score"] or 0.0,
                    "recommendation": (
                        f"Explore more {s['category']} offers — "
                        f"low competition, high avg score ({s['avg_score']})"
                    )
                })
        return gaps


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def create_offer_intelligence_agent(
    agent_id: str = "offer_intelligence",
    data_dir: Optional[str] = None,
    log_level: str = "INFO",
    scoring_interval_minutes: int = 30
) -> OfferIntelligenceAgent:
    """Factory function for OfferIntelligenceAgent."""
    return OfferIntelligenceAgent(
        agent_id=agent_id,
        data_dir=data_dir,
        log_level=log_level,
        scoring_interval_minutes=scoring_interval_minutes
    )
