"""
KashClaw Media Grid - Autonomous Content Creation & Affiliate Monetization Pipeline.

A 4-layer pipeline for autonomous content creation, social media growth, 
and affiliate marketing revenue generation integrated into SIMP/KashClaw ecosystem.

Architecture:
1. Research Layer: Trend Harvester, Offer Intelligence
2. Content Factory: Script Agent, Asset Agent, Edit/Packaging Agent  
3. Distribution Layer: Publisher Agent
4. Monetization Layer: Analytics Agent, Landing Page Agent
"""

from simp.organs.media.agents.trend_harvester_agent import (
    TrendHarvesterAgent, create_trend_harvester_agent
)
from simp.organs.media.agents.script_agent import (
    ScriptAgent, create_script_agent
)
from simp.organs.media.agents.asset_agent import (
    AssetAgent, create_asset_agent
)
from simp.organs.media.agents.edit_packaging_agent import (
    EditPackagingAgent, create_edit_packaging_agent
)
from simp.organs.media.agents.publisher_agent import (
    PublisherAgent, create_publisher_agent
)
from simp.organs.media.agents.analytics_agent import (
    AnalyticsAgent, create_analytics_agent
)

# Import models
from simp.organs.media.models import (
    AffiliateOffer, ContentBrief, ScriptPackage, AssetJob,
    GeneratedAsset, ContentPackage, PublishedPost, PerformanceMetrics,
    LandingPage, ContentOpportunityScore,
    ContentPlatform, ContentFormat, AssetType, GenerationTool,
    OfferCategory, ComplianceRisk
)

__version__ = "0.1.0"
__author__ = "KashClaw Media Grid Team"

# Agent factory functions
def create_media_grid_agents(data_dir: str = "data/media"):
    """Create all media grid agents with default configurations."""
    agents = {
        "trend_harvester": create_trend_harvester_agent(
            agent_id="trend_harvester",
            data_dir=data_dir,
            research_interval_minutes=60
        ),
        "script_agent": create_script_agent(
            agent_id="script_agent",
            data_dir=data_dir,
            generation_tool=GenerationTool.CLAUDE
        ),
        "asset_agent": create_asset_agent(
            agent_id="asset_agent",
            data_dir=data_dir,
            default_tool=GenerationTool.HIGGSFIELD,
            budget_per_job=10.0
        ),
        "edit_packaging_agent": create_edit_packaging_agent(
            agent_id="edit_packaging_agent",
            data_dir=data_dir
        ),
        "publisher_agent": create_publisher_agent(
            agent_id="publisher_agent",
            data_dir=data_dir,
            max_retries=3,
            retry_delay=60
        ),
        "analytics_agent": create_analytics_agent(
            agent_id="analytics_agent",
            data_dir=data_dir,
            analysis_interval_minutes=60
        )
    }
    return agents

# Intent type definitions for SIMP broker
MEDIA_INTENT_TYPES = {
    "media.trend_research": "Research trends and generate content briefs",
    "media.offer_scoring": "Score affiliate offers for monetization potential",
    "media.script_generation": "Generate scripts for content creation",
    "media.asset_generation": "Generate media assets (video/images/audio)",
    "media.content_packaging": "Package content for different platforms",
    "media.content_publishing": "Publish content to social platforms",
    "media.performance_tracking": "Track content performance and analytics",
    "media.landing_page_generation": "Generate landing pages for offers",
    "media.optimization_recommendation": "Generate optimization recommendations"
}

# Export main classes and functions
__all__ = [
    # Agents
    "TrendHarvesterAgent",
    "ScriptAgent", 
    "AssetAgent",
    "EditPackagingAgent",
    "PublisherAgent",
    "AnalyticsAgent",
    
    # Factory functions
    "create_trend_harvester_agent",
    "create_script_agent",
    "create_asset_agent",
    "create_edit_packaging_agent",
    "create_publisher_agent",
    "create_analytics_agent",
    "create_media_grid_agents",
    
    # Models
    "AffiliateOffer",
    "ContentBrief",
    "ScriptPackage",
    "AssetJob",
    "GeneratedAsset",
    "ContentPackage",
    "PublishedPost",
    "PerformanceMetrics",
    "LandingPage",
    "ContentOpportunityScore",
    
    # Enums
    "ContentPlatform",
    "ContentFormat",
    "AssetType",
    "GenerationTool",
    "OfferCategory",
    "ComplianceRisk",
    
    # Constants
    "MEDIA_INTENT_TYPES",
    "__version__"
]