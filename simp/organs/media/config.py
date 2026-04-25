"""
Configuration for KashClaw Media Grid.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class MediaEnvironment(str, Enum):
    """Media grid environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class MediaGridConfig:
    """Main configuration for KashClaw Media Grid."""
    
    # Environment
    environment: MediaEnvironment = MediaEnvironment.DEVELOPMENT
    
    # Data storage
    data_dir: str = "data/media"
    ledger_retention_days: int = 90
    
    # Agent configurations
    agents_enabled: Dict[str, bool] = field(default_factory=lambda: {
        "trend_harvester": True,
        "script_agent": True,
        "asset_agent": True,
        "edit_packaging_agent": True,
        "publisher_agent": True,
        "analytics_agent": True,
        "simp_news_agent": True,
        "offer_intelligence_agent": True
    })
    
    # Content generation
    default_generation_tool: str = "higgsfield"
    max_content_per_day: int = 10
    content_quality: str = "balanced"  # "fast", "balanced", "quality"
    
    # Publishing
    platforms_enabled: Dict[str, bool] = field(default_factory=lambda: {
        "tiktok": True,
        "youtube_shorts": True,
        "instagram_reels": True,
        "x": True,
        "facebook": False,
        "linkedin": False
    })
    
    max_posts_per_day: int = 20
    posting_schedule_enabled: bool = True
    
    # Monetization
    affiliate_networks: List[str] = field(default_factory=lambda: [
        "clickbank",
        "shareasale",
        "cj",
        "partnerstack",
        "direct"
    ])
    
    min_commission_rate: float = 20.0  # Percentage
    min_payout: float = 25.0  # USD
    
    # Compliance
    disclosure_required: bool = True
    compliance_check_enabled: bool = True
    human_approval_required: bool = False
    
    # Budget and costs
    daily_budget: float = 50.0  # USD
    max_cost_per_content: float = 15.0  # USD
    roi_target: float = 100.0  # Percentage
    
    # Analytics
    tracking_enabled: bool = True
    analysis_interval_minutes: int = 60
    performance_decay_days: int = 7
    
    # SIMP integration
    simp_broker_url: str = "http://127.0.0.1:5555"
    simp_api_key: str = ""
    auto_register_agents: bool = True
    
    # n8n integration
    n8n_webhook_url: str = "http://localhost:5678/webhook/media"
    n8n_enabled: bool = False
    
    # AI tools configuration
    ai_tools: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "higgsfield": {
            "enabled": True,
            "api_key": "",
            "max_cost_per_video": 10.0,
            "quality_preset": "standard"
        },
        "minimax": {
            "enabled": True,
            "api_key": "",
            "max_cost_per_video": 5.0,
            "quality_preset": "fast"
        },
        "elevenlabs": {
            "enabled": True,
            "api_key": "",
            "voice_id": "default",
            "cost_per_character": 0.0003
        },
        "openai": {
            "enabled": True,
            "api_key": "",
            "model": "gpt-4",
            "max_tokens": 2000
        }
    })
    
    # Content templates
    content_templates: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "ai_tools_review": {
            "name": "AI Tools Review",
            "description": "Review and demonstration of AI tools",
            "target_platforms": ["tiktok", "youtube_shorts", "instagram_reels"],
            "duration_seconds": 60,
            "formats": ["9:16"],
            "monetization_method": "affiliate_links",
            "compliance_notes": ["Disclose affiliate relationship", "Accurate capability claims"]
        },
        "productivity_tips": {
            "name": "Productivity Tips",
            "description": "Quick productivity tips and hacks",
            "target_platforms": ["tiktok", "instagram_reels", "x"],
            "duration_seconds": 45,
            "formats": ["9:16", "1:1"],
            "monetization_method": "lead_generation",
            "compliance_notes": ["Educational content", "No medical/financial advice"]
        },
        "comparison_video": {
            "name": "Tool Comparison",
            "description": "Comparison of similar tools or methods",
            "target_platforms": ["youtube_shorts", "instagram_reels"],
            "duration_seconds": 90,
            "formats": ["9:16", "16:9"],
            "monetization_method": "affiliate_links",
            "compliance_notes": ["Fair comparison", "Disclose testing methodology"]
        }
    })
    
    # Account portfolio
    account_portfolio: List[Dict[str, Any]] = field(default_factory=lambda: [
        {
            "name": "KashClawLabs",
            "type": "brand",
            "platforms": ["tiktok", "youtube_shorts", "instagram"],
            "niche": "ai_tools",
            "voice": "professional",
            "posting_frequency": "daily",
            "monetization": ["affiliate_links", "sponsored_content"]
        },
        {
            "name": "ClipCashFlow",
            "type": "niche",
            "platforms": ["tiktok", "instagram_reels"],
            "niche": "productivity",
            "voice": "casual",
            "posting_frequency": "3x_weekly",
            "monetization": ["affiliate_links", "digital_products"]
        },
        {
            "name": "AgentSideHustles",
            "type": "persona",
            "platforms": ["x", "linkedin"],
            "niche": "entrepreneurship",
            "voice": "enthusiastic",
            "posting_frequency": "daily",
            "monetization": ["affiliate_links", "consulting"]
        }
    ])
    
    # Performance thresholds
    performance_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "min_engagement_rate": 0.02,  # 2%
        "min_ctr": 0.01,  # 1%
        "min_conversion_rate": 0.001,  # 0.1%
        "max_cost_per_conversion": 50.0,  # USD
        "min_roi": 50.0,  # 50%
        "content_decay_threshold": 0.1  # 10% of initial views after 7 days
    })
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "media_grid.log"
    log_rotation: str = "daily"
    
    def __post_init__(self):
        """Post-initialization processing."""
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Set SIMP API key from environment if not provided
        if not self.simp_api_key:
            self.simp_api_key = os.getenv("SIMP_API_KEY", "")
        
        # Set AI tool API keys from environment
        for tool_name in self.ai_tools:
            env_key = f"{tool_name.upper()}_API_KEY"
            if env_key in os.environ and not self.ai_tools[tool_name].get("api_key"):
                self.ai_tools[tool_name]["api_key"] = os.environ[env_key]
    
    @classmethod
    def from_env(cls) -> "MediaGridConfig":
        """Create configuration from environment variables."""
        config = cls()
        
        # Environment
        env_str = os.getenv("MEDIA_ENVIRONMENT", "development").upper()
        if env_str in MediaEnvironment.__members__:
            config.environment = MediaEnvironment[env_str]
        
        # Data directory
        if "MEDIA_DATA_DIR" in os.environ:
            config.data_dir = os.getenv("MEDIA_DATA_DIR")
        
        # SIMP integration
        if "SIMP_BROKER_URL" in os.environ:
            config.simp_broker_url = os.getenv("SIMP_BROKER_URL")
        
        # Budget
        if "MEDIA_DAILY_BUDGET" in os.environ:
            try:
                config.daily_budget = float(os.getenv("MEDIA_DAILY_BUDGET"))
            except (ValueError, TypeError):
                pass
        
        # Logging
        if "MEDIA_LOG_LEVEL" in os.environ:
            config.log_level = os.getenv("MEDIA_LOG_LEVEL")
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        import dataclasses
        return dataclasses.asdict(self)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Check required fields
        if not self.simp_broker_url:
            issues.append("SIMP broker URL is required")
        
        if self.environment == MediaEnvironment.PRODUCTION and not self.simp_api_key:
            issues.append("SIMP API key is required for production")
        
        # Check budget constraints
        if self.daily_budget <= 0:
            issues.append("Daily budget must be positive")
        
        if self.max_cost_per_content <= 0:
            issues.append("Max cost per content must be positive")
        
        if self.max_cost_per_content > self.daily_budget:
            issues.append("Max cost per content cannot exceed daily budget")
        
        # Check at least one platform is enabled
        enabled_platforms = [p for p, enabled in self.platforms_enabled.items() if enabled]
        if not enabled_platforms:
            issues.append("At least one platform must be enabled")
        
        # Check at least one agent is enabled
        enabled_agents = [a for a, enabled in self.agents_enabled.items() if enabled]
        if not enabled_agents:
            issues.append("At least one agent must be enabled")
        
        # Check AI tools configuration
        for tool_name, tool_config in self.ai_tools.items():
            if tool_config.get("enabled", False) and not tool_config.get("api_key"):
                if self.environment == MediaEnvironment.PRODUCTION:
                    issues.append(f"API key required for {tool_name} in production")
        
        return issues


# Default configuration instance
default_config = MediaGridConfig()

# Environment-specific configurations
configs = {
    MediaEnvironment.DEVELOPMENT: MediaGridConfig(
        environment=MediaEnvironment.DEVELOPMENT,
        log_level="DEBUG",
        human_approval_required=True,
        max_content_per_day=3,
        max_posts_per_day=5,
        daily_budget=25.0,
        compliance_check_enabled=True
    ),
    MediaEnvironment.STAGING: MediaGridConfig(
        environment=MediaEnvironment.STAGING,
        log_level="INFO",
        human_approval_required=False,
        max_content_per_day=10,
        max_posts_per_day=15,
        daily_budget=100.0,
        compliance_check_enabled=True
    ),
    MediaEnvironment.PRODUCTION: MediaGridConfig(
        environment=MediaEnvironment.PRODUCTION,
        log_level="WARNING",
        human_approval_required=False,
        max_content_per_day=50,
        max_posts_per_day=100,
        daily_budget=500.0,
        compliance_check_enabled=True,
        auto_register_agents=True
    )
}


def get_config(environment: Optional[MediaEnvironment] = None) -> MediaGridConfig:
    """
    Get configuration for specified environment.
    
    Args:
        environment: Environment type, defaults to MEDIA_ENVIRONMENT env var or DEVELOPMENT
    
    Returns:
        MediaGridConfig instance
    """
    if environment is None:
        env_str = os.getenv("MEDIA_ENVIRONMENT", "development").upper()
        if env_str in MediaEnvironment.__members__:
            environment = MediaEnvironment[env_str]
        else:
            environment = MediaEnvironment.DEVELOPMENT
    
    # Return environment-specific config with environment variable overrides
    config = configs.get(environment, default_config).from_env()
    return config