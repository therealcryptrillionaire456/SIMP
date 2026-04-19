"""
Data models for KashClaw Media Grid system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class ContentPlatform(str, Enum):
    """Social media platforms for content distribution."""
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM_REELS = "instagram_reels"
    INSTAGRAM_FEED = "instagram_feed"
    X = "x"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    PINTEREST = "pinterest"


class ContentFormat(str, Enum):
    """Content aspect ratios and formats."""
    PORTRAIT_9_16 = "9:16"  # Shorts/Reels/TikTok
    SQUARE_1_1 = "1:1"      # Instagram feed
    LANDSCAPE_16_9 = "16:9" # YouTube/desktop
    STORY_9_16 = "story_9:16" # Stories format


class AssetType(str, Enum):
    """Types of media assets."""
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    THUMBNAIL = "thumbnail"
    SUBTITLES = "subtitles"


class GenerationTool(str, Enum):
    """AI tools for media generation."""
    HIGGSFIELD = "higgsfield"
    MINIMAX = "minimax"
    KLING = "kling"
    RUNWAY = "runway"
    PIKA = "pika"
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    CLAUDE = "claude"


class OfferCategory(str, Enum):
    """Categories of affiliate offers."""
    AI_TOOLS = "ai_tools"
    PRODUCTIVITY = "productivity"
    FINANCE = "finance"
    HEALTH = "health"
    EDUCATION = "education"
    CREATOR_TOOLS = "creator_tools"
    SOFTWARE = "software"
    ECOMMERCE = "ecommerce"


class ComplianceRisk(str, Enum):
    """Compliance risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AffiliateOffer:
    """Affiliate product offer with scoring."""
    offer_id: str = field(default_factory=lambda: f"offer_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    category: OfferCategory = OfferCategory.AI_TOOLS
    affiliate_network: str = ""  # "clickbank", "shareasale", "cj", "direct"
    commission_rate: float = 0.0  # Percentage
    average_payout: float = 0.0  # USD
    conversion_rate: float = 0.0  # Percentage
    refund_rate: float = 0.0  # Percentage
    target_audience: List[str] = field(default_factory=list)
    compliance_risk: ComplianceRisk = ComplianceRisk.MEDIUM
    platform_restrictions: List[ContentPlatform] = field(default_factory=list)
    disclosure_requirements: List[str] = field(default_factory=list)
    landing_page_url: str = ""
    affiliate_link: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Scoring fields
    opportunity_score: float = 0.0  # 0-100
    content_fit_score: float = 0.0  # 0-100
    monetization_score: float = 0.0  # 0-100
    competition_score: float = 0.0  # 0-100 (lower = less competition)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ContentBrief:
    """Research output with content opportunity details."""
    brief_id: str = field(default_factory=lambda: f"brief_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    primary_offer: Optional[AffiliateOffer] = None
    supporting_offers: List[AffiliateOffer] = field(default_factory=list)
    
    # Content angles
    primary_angle: str = ""  # "comparison", "review", "tutorial", "case_study"
    secondary_angles: List[str] = field(default_factory=list)
    
    # Target platforms and formats
    target_platforms: List[ContentPlatform] = field(default_factory=list)
    required_formats: List[ContentFormat] = field(default_factory=list)
    
    # Audience and keywords
    target_audience: str = ""
    primary_keywords: List[str] = field(default_factory=list)
    secondary_keywords: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    
    # Scoring
    content_opportunity_score: float = 0.0  # 0-100
    estimated_engagement: float = 0.0  # Estimated views/likes
    estimated_conversions: float = 0.0  # Estimated sales
    estimated_revenue: float = 0.0  # USD
    
    # Compliance
    compliance_notes: List[str] = field(default_factory=list)
    required_disclosures: List[str] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ScriptPackage:
    """Generated scripts for content creation."""
    script_id: str = field(default_factory=lambda: f"script_{uuid.uuid4().hex[:8]}")
    brief_id: str = ""
    title: str = ""
    
    # Hooks (attention grabbers)
    hooks: List[str] = field(default_factory=list)  # 10 hooks
    
    # Main scripts
    scripts: List[Dict[str, Any]] = field(default_factory=list)  # 3 scripts with structure
    
    # Call to action variants
    cta_variants: List[str] = field(default_factory=list)  # 3 CTAs
    
    # Platform-specific metadata
    platform_metadata: Dict[ContentPlatform, Dict[str, Any]] = field(default_factory=dict)
    
    # Voice and tone
    brand_voice: str = ""
    tone: str = ""  # "professional", "casual", "enthusiastic", "educational"
    
    # Generation details
    generation_tool: GenerationTool = GenerationTool.CLAUDE
    generation_prompt: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AssetJob:
    """Media generation job specification."""
    job_id: str = field(default_factory=lambda: f"job_{uuid.uuid4().hex[:8]}")
    script_id: str = ""
    asset_type: AssetType = AssetType.VIDEO
    generation_tool: GenerationTool = GenerationTool.HIGGSFIELD
    
    # Input specifications
    script_text: str = ""
    style_reference: str = ""
    voice_preferences: Dict[str, Any] = field(default_factory=dict)
    visual_style: str = ""  # "cinematic", "animated", "talking_head", "screen_recording"
    
    # Output requirements
    target_formats: List[ContentFormat] = field(default_factory=list)
    duration_seconds: int = 60
    resolution: str = "1080p"
    
    # Cost and budget
    estimated_cost: float = 0.0
    budget_limit: float = 10.0  # USD
    
    # Status tracking
    status: str = "pending"  # "pending", "processing", "completed", "failed"
    webhook_url: Optional[str] = None
    callback_data: Dict[str, Any] = field(default_factory=dict)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class GeneratedAsset:
    """Completed media asset."""
    asset_id: str = field(default_factory=lambda: f"asset_{uuid.uuid4().hex[:8]}")
    job_id: str = ""
    asset_type: AssetType = AssetType.VIDEO
    format: ContentFormat = ContentFormat.PORTRAIT_9_16
    
    # Storage references
    file_url: str = ""
    thumbnail_url: str = ""
    subtitle_url: Optional[str] = None
    
    # Generation details
    generation_tool: GenerationTool = GenerationTool.HIGGSFIELD
    generation_time_seconds: float = 0.0
    generation_cost: float = 0.0
    
    # Technical specifications
    duration_seconds: float = 0.0
    resolution: str = ""
    file_size_bytes: int = 0
    file_format: str = ""  # "mp4", "mov", "png", "jpg"
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ContentPackage:
    """Platform-ready content package with multiple formats."""
    package_id: str = field(default_factory=lambda: f"package_{uuid.uuid4().hex[:8]}")
    brief_id: str = ""
    script_id: str = ""
    
    # Assets by format
    assets: Dict[ContentFormat, GeneratedAsset] = field(default_factory=dict)
    
    # Platform-specific packaging
    platform_packages: Dict[ContentPlatform, Dict[str, Any]] = field(default_factory=dict)
    
    # Metadata for each platform
    captions: Dict[ContentPlatform, str] = field(default_factory=dict)
    hashtags: Dict[ContentPlatform, List[str]] = field(default_factory=dict)
    posting_schedule: Dict[ContentPlatform, str] = field(default_factory=dict)
    
    # Compliance
    disclosures_included: bool = False
    compliance_check_passed: bool = False
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PublishedPost:
    """Published content on a platform."""
    post_id: str = field(default_factory=lambda: f"post_{uuid.uuid4().hex[:8]}")
    package_id: str = ""
    platform: ContentPlatform = ContentPlatform.TIKTOK
    
    # Platform references
    platform_post_id: str = ""  # External platform ID
    post_url: str = ""
    
    # Publishing details
    published_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    scheduled_publish: bool = False
    publisher_agent: str = ""  # Which agent published it
    
    # Tracking
    tracking_links: Dict[str, str] = field(default_factory=dict)  # UTM parameters
    affiliate_links: List[str] = field(default_factory=list)
    
    # Initial metrics (will be updated by analytics)
    initial_views: int = 0
    initial_likes: int = 0
    initial_shares: int = 0
    initial_comments: int = 0
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PerformanceMetrics:
    """Performance analytics for published content."""
    metrics_id: str = field(default_factory=lambda: f"metrics_{uuid.uuid4().hex[:8]}")
    post_id: str = ""
    collected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Engagement metrics
    views: int = 0
    likes: int = 0
    shares: int = 0
    comments: int = 0
    saves: int = 0
    watch_time_seconds: float = 0.0
    completion_rate: float = 0.0  # Percentage
    
    # Click metrics
    clicks: int = 0
    click_through_rate: float = 0.0  # Percentage
    unique_clicks: int = 0
    
    # Conversion metrics
    conversions: int = 0
    conversion_rate: float = 0.0  # Percentage
    revenue: float = 0.0  # USD
    cost_per_conversion: float = 0.0  # USD
    
    # Cost metrics
    content_production_cost: float = 0.0
    promotion_cost: float = 0.0
    total_cost: float = 0.0
    
    # ROI calculations
    return_on_investment: float = 0.0  # Percentage
    revenue_per_view: float = 0.0  # USD
    revenue_per_click: float = 0.0  # USD
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LandingPage:
    """Presell landing page for affiliate offers."""
    page_id: str = field(default_factory=lambda: f"page_{uuid.uuid4().hex[:8]}")
    offer_id: str = ""
    title: str = ""
    headline: str = ""
    subheadline: str = ""
    
    # Content sections
    problem_statement: str = ""
    solution_description: str = ""
    benefits: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    testimonials: List[Dict[str, str]] = field(default_factory=list)
    faqs: List[Dict[str, str]] = field(default_factory=list)
    
    # Design
    template: str = "default"
    primary_color: str = "#3B82F6"
    secondary_color: str = "#1E40AF"
    font_family: str = "Inter, sans-serif"
    
    # Tracking and conversion
    tracking_code: str = ""
    utm_parameters: Dict[str, str] = field(default_factory=dict)
    affiliate_link: str = ""
    email_capture: bool = True
    email_placeholder: str = "Enter your email for exclusive tips"
    
    # Compliance
    disclosures: List[str] = field(default_factory=list)
    privacy_policy_link: str = ""
    terms_link: str = ""
    
    # Storage
    html_url: str = ""
    screenshot_url: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ContentOpportunityScore:
    """Calculated opportunity score for content ideas."""
    score_id: str = field(default_factory=lambda: f"score_{uuid.uuid4().hex[:8]}")
    brief_id: str = ""
    
    # Component scores (0-100)
    demand_score: float = 0.0  # Search/social demand
    monetization_score: float = 0.0  # Affiliate payout potential
    content_fit_score: float = 0.0  # Ease of content creation
    distribution_fit_score: float = 0.0  # Platform alignment
    
    # Risk scores (0-100, lower is better)
    competition_score: float = 0.0  # Competitive landscape
    compliance_risk_score: float = 0.0  # Policy/regulatory risk
    production_cost_score: float = 0.0  # Cost to produce
    
    # Final calculated score
    final_score: float = 0.0  # COS = (Demand×Monetization×ContentFit×DistributionFit) - (Competition+ComplianceRisk+ProductionCost)
    
    # Recommendations
    recommendation: str = "proceed"  # "proceed", "review", "reject"
    confidence: float = 0.0  # 0-100
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())