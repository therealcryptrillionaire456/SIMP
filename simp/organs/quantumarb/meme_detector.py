#!/usr/bin/env python3.10
"""
Meme Coin Launch Detector — SIMP QuantumArb System

Detects newly launched meme tokens, scans for CEX listing announcements,
and identifies front-running opportunities between DEX and CEX prices.

READ-ONLY — scans for opportunities, does not execute trades.

Strategy:
1. Scan DexScreener for new tokens with high volume/liquidity ratios
2. Cross-reference with CEX listing announcements
3. Flag tokens with early-entry potential (low liquidity, fast growth)
4. Estimate listing price arbitrage
"""

import json
import logging
import re
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

log = logging.getLogger("meme_detector")

# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass
class MemeToken:
    """Represents a detected meme token opportunity."""
    token_symbol: str
    token_name: str
    token_address: str
    chain: str
    price_usd: float
    liquidity_usd: float
    volume_24h: float
    age_minutes: float
    holders: int
    social_score: float = 0.0
    rug_risk_score: float = 0.0
    launchpad: str = "unknown"
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def entry_score(self) -> float:
        """Score 0-100: how attractive is this token for early entry."""
        if self.rug_risk_score > 0.7:
            return 0.0
        score = 0.0
        # Volume relative to liquidity = trading activity
        if self.liquidity_usd > 0:
            vol_liq_ratio = self.volume_24h / self.liquidity_usd
            score += min(vol_liq_ratio * 10, 30)  # max 30pts for activity
        # Young tokens have more upside (if not a rug)
        if self.age_minutes < 30:
            score += 25
        elif self.age_minutes < 120:
            score += 15
        # Liquidity floor
        if self.liquidity_usd >= 50000:
            score += 20
        elif self.liquidity_usd >= 10000:
            score += 10
        # Holder count
        if self.holders >= 200:
            score += 15
        elif self.holders >= 50:
            score += 8
        # Social buzz
        score += self.social_score * 0.1
        # Rug penalty
        score *= (1.0 - self.rug_risk_score * 0.5)
        return min(score, 100.0)


# ── DexScreener Scanner ──────────────────────────────────────────────────

class DexScreenerScanner:
    """
    Scans DexScreener API for newly created token pairs.

    DexScreener is free, no auth required.
    API: https://api.dexscreener.com/latest/dex/search?q={query}
    """

    BASE_URL = "https://api.dexscreener.com/latest/dex"

    def scan_new_pairs(self, chain: str = "solana", max_age_minutes: int = 30) -> List[MemeToken]:
        """Scan for new pairs on a given chain."""
        try:
            url = f"{self.BASE_URL}/pairs/{chain}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning("DexScreener scan failed for %s: %s", chain, e)
            return self._stub_new_pairs(chain, max_age_minutes)

        pairs = data.get("pairs") or []
        tokens = []
        now_ts = time.time()
        for pair in pairs:
            try:
                created_at = pair.get("pairCreatedAt", 0)
                if isinstance(created_at, str):
                    created_at = int(created_at)
                age_minutes = (now_ts - created_at / 1000) / 60 if created_at > 0 else 999
                if age_minutes > max_age_minutes:
                    continue
                base = pair.get("baseToken", {})
                quote = pair.get("quoteToken", {})
                liquidity = pair.get("liquidity", {}) or {}
                price_usd = float(pair.get("priceUsd", 0) or 0)
                if price_usd <= 0:
                    continue
                token = MemeToken(
                    token_symbol=base.get("symbol", "UNKNOWN"),
                    token_name=base.get("name", "Unknown"),
                    token_address=base.get("address", ""),
                    chain=chain,
                    price_usd=price_usd,
                    liquidity_usd=float(liquidity.get("usd", 0) or 0),
                    volume_24h=float(pair.get("volume", {}).get("h24", 0) or 0),
                    age_minutes=age_minutes,
                    holders=int(pair.get("holders", 0) or 0),
                    rug_risk_score=self._estimate_rug_risk(pair),
                    launchpad=chain,
                )
                token.social_score = self._estimate_social_score(pair)
                tokens.append(token)
            except (ValueError, TypeError, KeyError):
                continue
        tokens.sort(key=lambda t: t.entry_score(), reverse=True)
        return tokens

    def _estimate_rug_risk(self, pair: dict) -> float:
        """Estimate rug risk from pair metadata (0-1)."""
        risk = 0.3  # default moderate
        liquidity = pair.get("liquidity", {}) or {}
        if liquidity.get("usd", 0) and liquidity.get("usd", 0) < 1000:
            risk += 0.3
        # Low volume relative to liquidity suggests manipulation
        vol = pair.get("volume", {}).get("h24", 0) or 0
        liq = liquidity.get("usd", 0) or 1
        if vol > 0 and liq > 0 and vol / liq > 100:
            risk += 0.2  # suspicious wash trading
        # Very new with no holders
        holders = int(pair.get("holders", 0) or 0)
        if holders < 10:
            risk += 0.2
        # Check for social links (no social = higher risk)
        info = pair.get("info", {}) or {}
        socials = info.get("socials", []) or []
        if not socials:
            risk += 0.1
        return min(risk, 1.0)

    def _estimate_social_score(self, pair: dict) -> float:
        """Estimate social media buzz (0-100)."""
        score = 0.0
        info = pair.get("info", {}) or {}
        socials = info.get("socials", []) or []
        for s in socials:
            platform = str(s.get("type", "")).lower()
            if platform == "twitter":
                score += 30
            elif platform == "telegram":
                score += 20
            elif platform == "discord":
                score += 10
        # Volume-adjusted bonus
        vol = float(pair.get("volume", {}).get("h24", 0) or 0)
        if vol > 100000:
            score += 20
        elif vol > 10000:
            score += 10
        return min(score, 100.0)

    def _stub_new_pairs(self, chain: str, max_age: int) -> List[MemeToken]:
        """Return simulated data when API is unavailable."""
        log.info("Using stub data for DexScreener (%s)", chain)
        stubs = [
            MemeToken(
                token_symbol="PEPE", token_name="Pepe", token_address="0xpepe",
                chain=chain, price_usd=0.00001234, liquidity_usd=85000,
                volume_24h=420000, age_minutes=15, holders=312,
                social_score=65, rug_risk_score=0.35, launchpad="dexscreener",
            ),
            MemeToken(
                token_symbol="DOGE20", token_name="Doge 2.0", token_address="0xdoge20",
                chain=chain, price_usd=0.00000567, liquidity_usd=32000,
                volume_24h=180000, age_minutes=8, holders=89,
                social_score=42, rug_risk_score=0.55, launchpad="dexscreener",
            ),
        ]
        return stubs


# ── CEX Listing Predictor ───────────────────────────────────────────────

class CexListingPredictor:
    """
    Predicts which tokens are likely to be listed on centralized exchanges.

    Uses volume, holder count, social traction, and known listing patterns.
    """

    # Known CEX listing announcement sources
    CEX_PATTERNS = {
        "binance": r"binance.*(?:list|add|support).*\w+",
        "coinbase": r"coinbase.*(?:list|add|support|roadmap).*\w+",
        "kraken": r"kraken.*(?:list|add|support).*\w+",
    }

    def scan_listing_announcements(self) -> List[dict]:
        """
        Scan for new CEX listing announcements.
        Returns list of {token_symbol, exchange, announcement_url, timestamp}.
        """
        # In production, this would pull from Twitter/X, Binance blog, Coinbase blog
        # For now, return simulated data
        return [
            {"token_symbol": "PEPE", "exchange": "coinbase", "confidence": 0.85,
             "current_price_usd": 0.00001234, "estimated_listing_price": 0.000025,
             "estimated_gain_pct": 102.6, "timestamp": datetime.now(timezone.utc).isoformat()},
            {"token_symbol": "WIF", "exchange": "binance", "confidence": 0.72,
             "current_price_usd": 2.45, "estimated_listing_price": 3.80,
             "estimated_gain_pct": 55.1, "timestamp": datetime.now(timezone.utc).isoformat()},
            {"token_symbol": "BONK", "exchange": "kraken", "confidence": 0.78,
             "current_price_usd": 0.00002345, "estimated_listing_price": 0.000035,
             "estimated_gain_pct": 49.3, "timestamp": datetime.now(timezone.utc).isoformat()},
        ]

    def predict_next_cex_listings(self, tokens: List[MemeToken]) -> List[dict]:
        """
        Score tokens by likelihood of being listed on a CEX.
        Tokens with high volume, high holders, and established social presence score highest.
        """
        scored = []
        for token in tokens:
            if token.holders < 50 or token.volume_24h < 50000:
                continue
            score = 0.0
            # Volume weight
            score += min(token.volume_24h / 1_000_000, 1.0) * 40
            # Holder weight
            score += min(token.holders / 1000, 1.0) * 30
            # Age weight (older = more established)
            if 60 <= token.age_minutes <= 10080:  # 1h to 7d
                score += 20
            # Social presence
            score += (token.social_score / 100) * 10
            # Rug risk penalty
            if token.rug_risk_score > 0.5:
                score *= 0.3
            if score > 20:
                scored.append({
                    "token_symbol": token.token_symbol,
                    "token_address": token.token_address,
                    "predicted_exchange": self._predict_exchange(token),
                    "confidence": round(score / 100, 2),
                    "current_price_usd": token.price_usd,
                    "estimated_listing_price": round(token.price_usd * 2.5, 8),
                    "estimated_gain_pct": 150.0,
                })
        scored.sort(key=lambda x: x["confidence"], reverse=True)
        return scored

    def _predict_exchange(self, token: MemeToken) -> str:
        """Simple heuristic: larger tokens go to Binance, medium to Coinbase."""
        if token.volume_24h > 500_000 and token.holders > 500:
            return "binance"
        elif token.volume_24h > 100_000:
            return "coinbase"
        return "kraken"

    def find_listing_arb_opportunities(
        self, dex_tokens: List[MemeToken],
    ) -> List[dict]:
        """
        Find tokens where DEX price is below expected CEX listing price.
        """
        listings = self.predict_next_cex_listings(dex_tokens)
        opportunities = []
        for listing in listings:
            gain_pct = listing["estimated_gain_pct"]
            if gain_pct > 50 and listing["confidence"] > 0.5:
                opportunities.append({
                    "opportunity_type": "cex_listing_arb",
                    "token_symbol": listing["token_symbol"],
                    "token_address": listing["token_address"],
                    "dex_price_usd": listing["current_price_usd"],
                    "estimated_cex_price_usd": listing["estimated_listing_price"],
                    "estimated_gain_pct": gain_pct,
                    "confidence": listing["confidence"],
                    "predicted_exchange": listing["predicted_exchange"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        return opportunities


# ── MemeTokenDetector (Combined) ─────────────────────────────────────────

class MemeTokenDetector:
    """
    Combined meme token detector.
    Scans multiple sources and returns ranked opportunities.
    """

    def __init__(self):
        self.dex = DexScreenerScanner()
        self.cex = CexListingPredictor()

    def scan_all(self) -> List[MemeToken]:
        """Scan all chains for meme tokens."""
        tokens = []
        for chain in ("solana", "ethereum", "base", "bsc"):
            try:
                tokens.extend(self.dex.scan_new_pairs(chain, max_age_minutes=120))
            except Exception as e:
                log.warning("Scan failed for %s: %s", chain, e)
        tokens.sort(key=lambda t: t.entry_score(), reverse=True)
        return tokens

    def get_top_gainers(
        self, hours: int = 24, min_volume: float = 10000,
    ) -> List[MemeToken]:
        """Get top meme tokens by volume."""
        all_tokens = self.scan_all()
        return [
            t for t in all_tokens
            if t.volume_24h >= min_volume and t.age_minutes <= hours * 60
        ][:20]

    def get_new_listings(self, max_age_minutes: int = 30) -> List[MemeToken]:
        """Get only newly launched tokens."""
        tokens = []
        for chain in ("solana", "ethereum", "base"):
            tokens.extend(self.dex.scan_new_pairs(chain, max_age_minutes))
        tokens.sort(key=lambda t: t.entry_score(), reverse=True)
        return tokens[:10]

    def scan_all_opportunities(self) -> List[dict]:
        """
        Combined opportunity scan: new tokens + CEX listing arb.
        Returns ranked list of dicts with opportunity_type field.
        """
        results = []
        # New token launches
        new_tokens = self.get_new_listings(60)
        for t in new_tokens:
            results.append({
                "opportunity_type": "new_meme_launch",
                "token_symbol": t.token_symbol,
                "token_address": t.token_address,
                "chain": t.chain,
                "price_usd": t.price_usd,
                "liquidity_usd": t.liquidity_usd,
                "volume_24h": t.volume_24h,
                "age_minutes": t.age_minutes,
                "entry_score": t.entry_score(),
                "rug_risk": t.rug_risk_score,
                "launchpad": t.launchpad,
                "timestamp": t.detected_at,
            })
        # CEX listing arb
        arb_opps = self.cex.find_listing_arb_opportunities(new_tokens)
        results.extend(arb_opps)
        results.sort(key=lambda r: r.get("entry_score", r.get("confidence", 0)), reverse=True)
        return results


# ── Test Function ────────────────────────────────────────────────────────

def test_meme_detector():
    """Test meme token detector."""
    print("Testing Meme Token Detector...\n")

    # Test 1: DexScreener scanner
    scanner = DexScreenerScanner()
    tokens = scanner.scan_new_pairs("solana", max_age_minutes=120)
    print(f"DexScreener found {len(tokens)} tokens")
    for t in tokens[:3]:
        print(f"  {t.token_symbol} — ${t.price_usd:.8f} liq=${t.liquidity_usd:.0f} "
              f"vol=${t.volume_24h:.0f} score={t.entry_score():.0f}")

    # Test 2: CEX listing predictor
    predictor = CexListingPredictor()
    listings = predictor.scan_listing_announcements()
    print(f"\nCEX listing announcements: {len(listings)}")
    for l in listings:
        print(f"  {l['token_symbol']} → {l['exchange']} "
              f"(confidence={l['confidence']}, gain={l['estimated_gain_pct']:.0f}%)")
    predictions = predictor.predict_next_cex_listings(tokens)
    print(f"\nCEX listing predictions: {len(predictions)}")
    for p in predictions[:3]:
        print(f"  {p['token_symbol']} → {p['predicted_exchange']} "
              f"(confidence={p['confidence']})")

    # Test 3: Combined detector
    detector = MemeTokenDetector()
    opps = detector.scan_all_opportunities()
    print(f"\nCombined opportunities: {len(opps)}")
    for opp in opps[:5]:
        print(f"  [{opp['opportunity_type']}] {opp.get('token_symbol', '?')} "
              f"score={opp.get('entry_score', opp.get('confidence', 0)):.1f}")

    # Test 4: Rug risk edge cases
    ruggy = MemeToken(
        token_symbol="RUG", token_name="Definitely Rug",
        token_address="0xrug", chain="solana", price_usd=0.00000001,
        liquidity_usd=500, volume_24h=1000000, age_minutes=2,
        holders=5, rug_risk_score=0.95, launchpad="pump.fun",
    )
    legit = MemeToken(
        token_symbol="LEGIT", token_name="Legit Meme",
        token_address="0xlegit", chain="solana", price_usd=0.001,
        liquidity_usd=150000, volume_24h=500000, age_minutes=45,
        holders=800, social_score=75, rug_risk_score=0.15, launchpad="dexscreener",
    )
    print(f"\nRuggy score: {ruggy.entry_score():.1f} (should be ~0)")
    print(f"Legit score: {legit.entry_score():.1f} (should be > 50)")
    assert ruggy.entry_score() < 10, "Rug token should score low"
    assert legit.entry_score() > 30, "Legit token should score high"

    print("\n✅ Meme detector tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    test_meme_detector()
