"""
Trend Harvester Agent for KashClaw Media Grid.

Responsible for:
- Scraping trending topics from social platforms
- Researching affiliate offers and opportunities
- Identifying content gaps and opportunities
- Generating content briefs with opportunity scores
"""
import asyncio
import json
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from simp.organs.media.agents.base_media_agent import BaseMediaAgent
from simp.organs.media.models import (
    AffiliateOffer, ContentBrief, ContentOpportunityScore,
    ContentPlatform, OfferCategory, ComplianceRisk
)


class TrendHarvesterAgent(BaseMediaAgent):
    """Agent that harvests trends and generates content opportunities."""
    
    def __init__(
        self,
        agent_id: str = "trend_harvester",
        data_dir: Optional[str] = None,
        log_level: str = "INFO",
        research_interval_minutes: int = 60  # How often to research
    ):
        """Initialize the Trend Harvester Agent."""
        super().__init__(
            agent_id=agent_id,
            agent_name="Trend Harvester Agent",
            data_dir=data_dir,
            log_level=log_level
        )
        
        self.research_interval_minutes = research_interval_minutes
        self.last_research_time = None
        
        # Mock data for demonstration
        self.mock_trends = self._load_mock_trends()
        self.mock_offers = self._load_mock_offers()
        
        self.logger.info(f"Trend Harvester Agent initialized with {research_interval_minutes}min interval")
    
    def _load_mock_trends(self) -> List[Dict[str, Any]]:
        """Load mock trending topics for demonstration."""
        return [
            {
                "topic": "AI Video Generation",
                "platforms": ["tiktok", "youtube_shorts", "instagram_reels"],
                "search_volume": 85000,
                "growth_rate": 0.45,
                "competition": 0.65,
                "related_keywords": ["ai video", "text to video", "video ai", "ai animation"],
                "audience_demographics": ["creators", "marketers", "entrepreneurs"],
                "trend_score": 0.82
            },
            {
                "topic": "No-Code Automation",
                "platforms": ["tiktok", "x", "linkedin"],
                "search_volume": 42000,
                "growth_rate": 0.38,
                "competition": 0.42,
                "related_keywords": ["no code", "automation", "zapier", "make.com", "n8n"],
                "audience_demographics": ["business owners", "developers", "product managers"],
                "trend_score": 0.76
            },
            {
                "topic": "Personal Finance Apps",
                "platforms": ["tiktok", "youtube_shorts", "instagram"],
                "search_volume": 68000,
                "growth_rate": 0.32,
                "competition": 0.78,
                "related_keywords": ["budgeting", "investing", "saving money", "finance tips"],
                "audience_demographics": ["young adults", "students", "professionals"],
                "trend_score": 0.68
            },
            {
                "topic": "Productivity Systems",
                "platforms": ["youtube_shorts", "instagram", "x"],
                "search_volume": 55000,
                "growth_rate": 0.28,
                "competition": 0.55,
                "related_keywords": ["productivity", "time management", "gtd", "pomodoro"],
                "audience_demographics": ["professionals", "students", "creators"],
                "trend_score": 0.71
            },
            {
                "topic": "SaaS Affiliate Marketing",
                "platforms": ["tiktok", "youtube_shorts", "linkedin"],
                "search_volume": 32000,
                "growth_rate": 0.52,
                "competition": 0.48,
                "related_keywords": ["saas", "affiliate", "passive income", "software"],
                "audience_demographics": ["marketers", "entrepreneurs", "content creators"],
                "trend_score": 0.79
            }
        ]
    
    def _load_mock_offers(self) -> List[Dict[str, Any]]:
        """Load mock affiliate offers for demonstration."""
        return [
            {
                "name": "Higgsfield AI",
                "description": "AI video generation platform with cinematic quality",
                "category": "ai_tools",
                "affiliate_network": "direct",
                "commission_rate": 30.0,
                "average_payout": 45.0,
                "conversion_rate": 3.2,
                "refund_rate": 1.5,
                "target_audience": ["video creators", "marketers", "agencies"],
                "compliance_risk": "medium",
                "landing_page_url": "https://higgsfield.ai",
                "affiliate_link": "https://higgsfield.ai/ref/kashclaw",
                "tags": ["ai", "video", "generation", "premium"]
            },
            {
                "name": "Notion AI",
                "description": "AI-powered workspace for notes, docs, and projects",
                "category": "productivity",
                "affiliate_network": "partnerstack",
                "commission_rate": 20.0,
                "average_payout": 30.0,
                "conversion_rate": 4.5,
                "refund_rate": 0.8,
                "target_audience": ["students", "professionals", "teams"],
                "compliance_risk": "low",
                "landing_page_url": "https://notion.so",
                "affiliate_link": "https://notion.so/ref/kashclaw",
                "tags": ["productivity", "notes", "organization", "ai"]
            },
            {
                "name": "ClickFunnels",
                "description": "Sales funnel builder for entrepreneurs",
                "category": "creator_tools",
                "affiliate_network": "clickbank",
                "commission_rate": 40.0,
                "average_payout": 100.0,
                "conversion_rate": 2.8,
                "refund_rate": 3.2,
                "target_audience": ["entrepreneurs", "coaches", "consultants"],
                "compliance_risk": "medium",
                "landing_page_url": "https://clickfunnels.com",
                "affiliate_link": "https://clickfunnels.com/ref/kashclaw",
                "tags": ["funnels", "marketing", "sales", "entrepreneur"]
            },
            {
                "name": "Carrd",
                "description": "Simple one-page website builder",
                "category": "creator_tools",
                "affiliate_network": "direct",
                "commission_rate": 35.0,
                "average_payout": 25.0,
                "conversion_rate": 5.2,
                "refund_rate": 1.2,
                "target_audience": ["creators", "freelancers", "small businesses"],
                "compliance_risk": "low",
                "landing_page_url": "https://carrd.co",
                "affiliate_link": "https://carrd.co/ref/kashclaw",
                "tags": ["website", "landing page", "simple", "portfolio"]
            },
            {
                "name": "ConvertKit",
                "description": "Email marketing for creators",
                "category": "creator_tools",
                "affiliate_network": "shareasale",
                "commission_rate": 30.0,
                "average_payout": 35.0,
                "conversion_rate": 3.8,
                "refund_rate": 1.8,
                "target_audience": ["creators", "bloggers", "newsletters"],
                "compliance_risk": "low",
                "landing_page_url": "https://convertkit.com",
                "affiliate_link": "https://convertkit.com/ref/kashclaw",
                "tags": ["email", "marketing", "creators", "newsletter"]
            }
        ]
    
    async def _process_loop(self):
        """Main processing loop for trend research."""
        while self.is_running:
            try:
                # Check if it's time to do research
                should_research = self._should_do_research()
                
                if should_research:
                    self.logger.info("Starting trend research cycle")
                    
                    # Research trends and generate briefs
                    briefs = await self.research_trends_and_generate_briefs()
                    
                    # Log the results
                    self.logger.info(f"Generated {len(briefs)} content briefs")
                    
                    # Update last research time
                    self.last_research_time = datetime.utcnow()
                    
                    # Send briefs to other agents via SIMP broker
                    for brief in briefs:
                        await self._distribute_brief(brief)
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in trend research loop: {e}")
                await asyncio.sleep(30)
    
    def _should_do_research(self) -> bool:
        """Determine if it's time to do research based on interval."""
        if self.last_research_time is None:
            return True
        
        time_since_last = datetime.utcnow() - self.last_research_time
        return time_since_last.total_seconds() >= (self.research_interval_minutes * 60)
    
    async def research_trends_and_generate_briefs(self, limit: int = 5) -> List[ContentBrief]:
        """
        Research trends and generate content briefs.
        
        Args:
            limit: Maximum number of briefs to generate
            
        Returns:
            List of ContentBrief objects
        """
        operation_id = self._log_operation(
            operation="trend_research",
            status="pending",
            details={"limit": limit}
        )
        
        start_time = time.time()
        
        try:
            # In a real implementation, this would:
            # 1. Scrape social platforms for trends
            # 2. Check affiliate networks for new offers
            # 3. Analyze competitor content
            # 4. Use AI to identify opportunities
            
            # For now, use mock data
            briefs = []
            
            for trend in self.mock_trends[:limit]:
                # Find matching offers
                matching_offers = self._find_matching_offers(trend)
                
                if not matching_offers:
                    self.logger.debug(f"No matching offers for trend: {trend['topic']}")
                    continue
                
                # Generate content brief
                brief = self._generate_content_brief(trend, matching_offers)
                briefs.append(brief)
                
                # Save to ledger
                self._save_content_brief(brief)
            
            duration = time.time() - start_time
            
            self._log_operation(
                operation="trend_research",
                status="success",
                details={
                    "briefs_generated": len(briefs),
                    "trends_analyzed": len(self.mock_trends[:limit])
                },
                duration_seconds=duration
            )
            
            return briefs
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_operation(
                operation="trend_research",
                status="failure",
                details={"error": str(e)},
                duration_seconds=duration
            )
            self.logger.error(f"Failed to research trends: {e}")
            return []
    
    def _find_matching_offers(self, trend: Dict[str, Any]) -> List[AffiliateOffer]:
        """Find affiliate offers that match a trend."""
        matching_offers = []
        
        for offer_data in self.mock_offers:
            # Simple matching logic based on categories and keywords
            offer_category = OfferCategory(offer_data["category"])
            trend_keywords = " ".join(trend.get("related_keywords", []) + [trend["topic"].lower()])
            
            # Check category match
            category_match = self._check_category_match(offer_category, trend)
            
            # Check keyword match
            keyword_match = self._check_keyword_match(offer_data, trend_keywords)
            
            if category_match or keyword_match:
                # Create AffiliateOffer object
                offer = AffiliateOffer(
                    offer_id=f"offer_{offer_data['name'].lower().replace(' ', '_')}",
                    name=offer_data["name"],
                    description=offer_data["description"],
                    category=offer_category,
                    affiliate_network=offer_data["affiliate_network"],
                    commission_rate=offer_data["commission_rate"],
                    average_payout=offer_data["average_payout"],
                    conversion_rate=offer_data["conversion_rate"],
                    refund_rate=offer_data["refund_rate"],
                    target_audience=offer_data["target_audience"],
                    compliance_risk=ComplianceRisk(offer_data["compliance_risk"]),
                    landing_page_url=offer_data["landing_page_url"],
                    affiliate_link=offer_data["affiliate_link"],
                    tags=offer_data["tags"]
                )
                
                # Calculate offer scores
                offer.opportunity_score = self._calculate_offer_opportunity_score(offer, trend)
                offer.content_fit_score = self._calculate_content_fit_score(offer, trend)
                offer.monetization_score = self._calculate_monetization_score(offer)
                offer.competition_score = self._calculate_competition_score(trend)
                
                matching_offers.append(offer)
        
        # Sort by opportunity score (highest first)
        matching_offers.sort(key=lambda o: o.opportunity_score, reverse=True)
        
        return matching_offers[:3]  # Return top 3 matches
    
    def _check_category_match(self, offer_category: OfferCategory, trend: Dict[str, Any]) -> bool:
        """Check if offer category matches trend."""
        trend_topic = trend["topic"].lower()
        
        category_mapping = {
            OfferCategory.AI_TOOLS: ["ai", "artificial intelligence", "machine learning", "generative"],
            OfferCategory.PRODUCTIVITY: ["productivity", "time management", "organization", "workflow"],
            OfferCategory.CREATOR_TOOLS: ["creator", "content", "video", "design", "marketing"],
            OfferCategory.SOFTWARE: ["software", "app", "tool", "platform", "saas"],
            OfferCategory.FINANCE: ["finance", "money", "investing", "budget", "saving"]
        }
        
        if offer_category in category_mapping:
            keywords = category_mapping[offer_category]
            return any(keyword in trend_topic for keyword in keywords)
        
        return False
    
    def _check_keyword_match(self, offer: Dict[str, Any], trend_keywords: str) -> bool:
        """Check if offer keywords match trend."""
        offer_name = offer["name"].lower()
        offer_tags = " ".join(offer["tags"]).lower()
        offer_text = f"{offer_name} {offer_tags}"
        
        # Simple keyword matching
        trend_words = set(re.findall(r'\w+', trend_keywords.lower()))
        offer_words = set(re.findall(r'\w+', offer_text.lower()))
        
        common_words = trend_words.intersection(offer_words)
        return len(common_words) >= 2  # At least 2 common words
    
    def _calculate_offer_opportunity_score(self, offer: AffiliateOffer, trend: Dict[str, Any]) -> float:
        """Calculate opportunity score for an offer given a trend."""
        # Base score from trend
        trend_score = trend.get("trend_score", 0.5) * 100
        
        # Adjust based on offer metrics
        commission_factor = offer.commission_rate / 50.0  # Normalize to 0-2
        conversion_factor = offer.conversion_rate / 5.0  # Normalize to 0-2
        payout_factor = offer.average_payout / 50.0  # Normalize to 0-2
        
        # Reduce for refunds
        refund_penalty = offer.refund_rate / 10.0
        
        # Calculate final score (0-100)
        score = trend_score * commission_factor * conversion_factor * payout_factor
        score = score * (1 - refund_penalty)
        
        return min(100, max(0, score))
    
    def _calculate_content_fit_score(self, offer: AffiliateOffer, trend: Dict[str, Any]) -> float:
        """Calculate how well the offer fits content creation."""
        # Factors that make content creation easier
        factors = []
        
        # Visual product (easier to demonstrate)
        visual_keywords = ["video", "design", "ui", "app", "software", "tool"]
        offer_text = f"{offer.name} {offer.description}".lower()
        if any(keyword in offer_text for keyword in visual_keywords):
            factors.append(0.8)
        else:
            factors.append(0.5)
        
        # Demo potential
        if "demo" in offer_text or "trial" in offer_text or "free" in offer_text:
            factors.append(0.9)
        
        # Problem-solution clarity
        problem_solution_keywords = ["solve", "help", "improve", "increase", "reduce"]
        if any(keyword in offer_text for keyword in problem_solution_keywords):
            factors.append(0.7)
        
        # Average the factors
        if factors:
            avg_factor = sum(factors) / len(factors)
        else:
            avg_factor = 0.5
        
        return avg_factor * 100
    
    def _calculate_monetization_score(self, offer: AffiliateOffer) -> float:
        """Calculate monetization potential score."""
        # Weighted combination of commission rate and average payout
        commission_score = min(100, offer.commission_rate * 2)  # 50% commission = 100 score
        payout_score = min(100, offer.average_payout)  # $100 payout = 100 score
        
        # Conversion rate bonus
        conversion_bonus = min(30, offer.conversion_rate * 10)  # 3% conversion = 30 bonus
        
        # Refund penalty
        refund_penalty = min(30, offer.refund_rate * 10)  # 3% refund = 30 penalty
        
        score = (commission_score * 0.4 + payout_score * 0.6) + conversion_bonus - refund_penalty
        
        return max(0, min(100, score))
    
    def _calculate_competition_score(self, trend: Dict[str, Any]) -> float:
        """Calculate competition level (lower is better)."""
        # Convert competition (0-1) to score (0-100, lower = less competition)
        competition = trend.get("competition", 0.5)
        return (1 - competition) * 100  # Invert so higher score = less competition
    
    def _generate_content_brief(
        self,
        trend: Dict[str, Any],
        offers: List[AffiliateOffer]
    ) -> ContentBrief:
        """Generate a content brief from trend and offers."""
        primary_offer = offers[0] if offers else None
        
        # Determine content angle based on trend and offer
        content_angle = self._determine_content_angle(trend, primary_offer)
        
        # Determine target platforms
        platform_names = trend.get("platforms", ["tiktok", "youtube_shorts"])
        platforms = [ContentPlatform(p) for p in platform_names if p in [p.value for p in ContentPlatform]]
        
        # Generate keywords and hashtags
        keywords = trend.get("related_keywords", [])[:5]
        hashtags = self._generate_hashtags(trend["topic"], keywords)
        
        # Calculate opportunity score
        cos = self._calculate_cos_for_brief(trend, primary_offer)
        
        # Create brief
        brief = ContentBrief(
            title=f"{trend['topic']}: {content_angle.replace('_', ' ').title()}",
            description=f"Content exploring {trend['topic']} with focus on {primary_offer.name if primary_offer else 'trend analysis'}",
            primary_offer=primary_offer,
            supporting_offers=offers[1:] if len(offers) > 1 else [],
            primary_angle=content_angle,
            secondary_angles=self._generate_secondary_angles(content_angle),
            target_platforms=platforms,
            required_formats=self._determine_required_formats(platforms),
            target_audience=", ".join(trend.get("audience_demographics", ["general audience"])),
            primary_keywords=keywords,
            secondary_keywords=trend.get("related_keywords", [])[5:10] if len(trend.get("related_keywords", [])) > 5 else [],
            hashtags=hashtags,
            content_opportunity_score=cos.final_score,
            estimated_engagement=self._estimate_engagement(trend),
            estimated_conversions=self._estimate_conversions(primary_offer, trend) if primary_offer else 0,
            estimated_revenue=self._estimate_revenue(primary_offer, trend) if primary_offer else 0,
            compliance_notes=self._generate_compliance_notes(primary_offer) if primary_offer else [],
            required_disclosures=self._generate_required_disclosures(primary_offer) if primary_offer else []
        )
        
        # Save COS
        cos.brief_id = brief.brief_id
        self._save_cos(cos)
        
        return brief
    
    def _determine_content_angle(self, trend: Dict[str, Any], offer: Optional[AffiliateOffer]) -> str:
        """Determine the best content angle for this trend and offer."""
        angles = ["comparison", "review", "tutorial", "case_study", "news", "tips"]
        
        if offer:
            # If we have an offer, prefer angles that showcase it
            if offer.category == OfferCategory.AI_TOOLS:
                return "tutorial" if "how to" in trend["topic"].lower() else "review"
            elif offer.category == OfferCategory.PRODUCTIVITY:
                return "tips" if "tips" in trend["topic"].lower() else "case_study"
            else:
                return "review"
        else:
            # Trend-only content
            if "vs" in trend["topic"].lower() or "comparison" in trend["topic"].lower():
                return "comparison"
            elif "how to" in trend["topic"].lower() or "tutorial" in trend["topic"].lower():
                return "tutorial"
            else:
                return "news"
    
    def _generate_secondary_angles(self, primary_angle: str) -> List[str]:
        """Generate secondary content angles."""
        all_angles = ["comparison", "review", "tutorial", "case_study", "news", "tips"]
        return [angle for angle in all_angles if angle != primary_angle][:2]
    
    def _generate_hashtags(self, topic: str, keywords: List[str]) -> List[str]:
        """Generate hashtags for content."""
        hashtags = []
        
        # Topic hashtag
        topic_tag = topic.lower().replace(" ", "")
        if len(topic_tag) <= 20:  # Platform limits
            hashtags.append(f"#{topic_tag}")
        
        # Keyword hashtags (max 5)
        for keyword in keywords[:5]:
            keyword_tag = keyword.lower().replace(" ", "")
            if 3 <= len(keyword_tag) <= 20:
                hashtags.append(f"#{keyword_tag}")
        
        # Platform-specific hashtags
        hashtags.extend(["#contentcreation", "#digitalmarketing", "#aitools"])
        
        return hashtags[:10]  # Platform limits
    
    def _determine_required_formats(self, platforms: List[ContentPlatform]) -> List[str]:
        """Determine required content formats based on platforms."""
        format_mapping = {
            ContentPlatform.TIKTOK: ["9:16"],
            ContentPlatform.YOUTUBE_SHORTS: ["9:16"],
            ContentPlatform.INSTAGRAM_REELS: ["9:16"],
            ContentPlatform.INSTAGRAM_FEED: ["1:1", "4:5"],
            ContentPlatform.X: ["16:9", "1:1"],
            ContentPlatform.FACEBOOK: ["16:9", "1:1"],
            ContentPlatform.LINKEDIN: ["16:9", "1:1"]
        }
        
        required_formats = set()
        for platform in platforms:
            if platform in format_mapping:
                required_formats.update(format_mapping[platform])
        
        return list(required_formats)
    
    def _calculate_cos_for_brief(
        self,
        trend: Dict[str, Any],
        offer: Optional[AffiliateOffer]
    ) -> ContentOpportunityScore:
        """Calculate Content Opportunity Score for a brief."""
        # Get component scores
        demand = trend.get("trend_score", 0.5) * 100
        monetization = offer.monetization_score if offer else 30.0
        content_fit = offer.content_fit_score if offer else 50.0
        distribution_fit = 70.0  # Assume good distribution fit
        
        competition = 100 - self._calculate_competition_score(trend)  # Convert back
        compliance_risk = 30.0 if offer and offer.compliance_risk == ComplianceRisk.LOW else 60.0
        production_cost = 40.0  # Estimated production cost
        
        # Calculate COS
        cos = self._calculate_content_opportunity_score(
            demand=demand,
            monetization=monetization,
            content_fit=content_fit,
            distribution_fit=distribution_fit,
            competition=competition,
            compliance_risk=compliance_risk,
            production_cost=production_cost
        )
        
        return cos
    
    def _estimate_engagement(self, trend: Dict[str, Any]) -> float:
        """Estimate potential engagement for content."""
        search_volume = trend.get("search_volume", 10000)
        trend_score = trend.get("trend_score", 0.5)
        
        # Simple estimation formula
        estimated_views = search_volume * trend_score * 0.01  # 1% of search volume
        return estimated_views
    
    def _estimate_conversions(self, offer: AffiliateOffer, trend: Dict[str, Any]) -> float:
        """Estimate conversions for an offer."""
        estimated_views = self._estimate_engagement(trend)
        click_rate = 0.03  # 3% CTR assumption
        conversion_rate = offer.conversion_rate / 100.0
        
        estimated_clicks = estimated_views * click_rate
        estimated_conversions = estimated_clicks * conversion_rate
        
        return estimated_conversions
    
    def _estimate_revenue(self, offer: AffiliateOffer, trend: Dict[str, Any]) -> float:
        """Estimate revenue from an offer."""
        estimated_conversions = self._estimate_conversions(offer, trend)
        revenue_per_conversion = offer.average_payout * (offer.commission_rate / 100.0)
        
        estimated_revenue = estimated_conversions * revenue_per_conversion
        return estimated_revenue
    
    def _generate_compliance_notes(self, offer: AffiliateOffer) -> List[str]:
        """Generate compliance notes for an offer."""
        notes = []
        
        if offer.compliance_risk == ComplianceRisk.HIGH:
            notes.append("High compliance risk - requires manual review")
        
        if "ai" in offer.name.lower() or "ai" in offer.tags:
            notes.append("AI tool - ensure accurate capability claims")
        
        if offer.refund_rate > 5.0:
            notes.append(f"High refund rate ({offer.refund_rate}%) - monitor closely")
        
        return notes
    
    def _generate_required_disclosures(self, offer: AffiliateOffer) -> List[str]:
        """Generate required disclosure statements."""
        disclosures = []
        
        # Affiliate disclosure
        disclosures.append("This content contains affiliate links. I may earn a commission if you make a purchase.")
        
        # Platform-specific disclosures
        disclosures.append("Results may vary. Always do your own research before purchasing.")
        
        if offer.compliance_risk == ComplianceRisk.HIGH:
            disclosures.append("This is not financial advice. Consult with a professional.")
        
        return disclosures
    
    def _save_content_brief(self, brief: ContentBrief):
        """Save content brief to ledger."""
        from dataclasses import asdict
        
        record = asdict(brief)
        
        # Convert enum values to strings
        if brief.primary_offer:
            record["primary_offer"] = asdict(brief.primary_offer)
            # Convert enum fields in offer
            for field in ["category", "compliance_risk"]:
                if field in record["primary_offer"]:
                    record["primary_offer"][field] = record["primary_offer"][field].value
        
        # Convert list of offers
        record["supporting_offers"] = []
        for offer in brief.supporting_offers:
            offer_dict = asdict(offer)
            for field in ["category", "compliance_risk"]:
                if field in offer_dict:
                    offer_dict[field] = offer_dict[field].value
            record["supporting_offers"].append(offer_dict)
        
        # Convert platform enums
        record["target_platforms"] = [p.value for p in brief.target_platforms]
        
        self._append_to_ledger("content_briefs", record)
    
    def _save_cos(self, cos: ContentOpportunityScore):
        """Save Content Opportunity Score to ledger."""
        from dataclasses import asdict
        record = asdict(cos)
        self._append_to_ledger("content_opportunity_scores", record)
    
    async def _distribute_brief(self, brief: ContentBrief):
        """Distribute content brief to other agents via SIMP broker."""
        try:
            # Send to Script Agent for script generation
            intent_data = {
                "brief_id": brief.brief_id,
                "title": brief.title,
                "description": brief.description,
                "primary_offer": brief.primary_offer.name if brief.primary_offer else None,
                "content_angle": brief.primary_angle,
                "target_platforms": [p.value for p in brief.target_platforms]
            }
            
            response = self._send_intent("media.script_generation", intent_data)
            
            if response:
                self.logger.info(f"Distributed brief {brief.brief_id} to Script Agent")
            else:
                self.logger.warning(f"Failed to distribute brief {brief.brief_id}")
                
        except Exception as e:
            self.logger.error(f"Error distributing brief {brief.brief_id}: {e}")
    
    def get_recent_briefs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent content briefs."""
        return self._read_ledger("content_briefs", limit=limit)
    
    def get_trend_analysis(self) -> Dict[str, Any]:
        """Get trend analysis summary."""
        briefs = self._read_ledger("content_briefs", limit=50)
        scores = self._read_ledger("content_opportunity_scores", limit=50)
        
        if not briefs:
            return {"status": "no_data", "message": "No briefs generated yet"}
        
        # Calculate statistics
        avg_score = sum(b.get("content_opportunity_score", 0) for b in briefs) / len(briefs)
        high_score_briefs = [b for b in briefs if b.get("content_opportunity_score", 0) > 70]
        
        # Count by platform
        platform_counts = {}
        for brief in briefs:
            for platform in brief.get("target_platforms", []):
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        # Count by category
        category_counts = {}
        for brief in briefs:
            if "primary_offer" in brief and brief["primary_offer"]:
                category = brief["primary_offer"].get("category", "unknown")
                category_counts[category] = category_counts.get(category, 0) + 1
        
        return {
            "status": "success",
            "statistics": {
                "total_briefs": len(briefs),
                "average_opportunity_score": round(avg_score, 2),
                "high_opportunity_briefs": len(high_score_briefs),
                "platform_distribution": platform_counts,
                "category_distribution": category_counts
            },
            "recent_briefs": briefs[:5]
        }


# Factory function for creating the agent
def create_trend_harvester_agent(
    agent_id: str = "trend_harvester",
    data_dir: Optional[str] = None,
    research_interval_minutes: int = 60
) -> TrendHarvesterAgent:
    """Create and return a Trend Harvester Agent instance."""
    return TrendHarvesterAgent(
        agent_id=agent_id,
        data_dir=data_dir,
        research_interval_minutes=research_interval_minutes
    )