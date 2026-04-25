"""Media Grid Configuration."""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class MediaEnvironment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class MediaGridConfig:
    """Configuration for the Media Grid subsystem.

    All fields have defaults sourced from environment variables.
    """

    # Environment
    environment: MediaEnvironment = MediaEnvironment.DEVELOPMENT
    log_level: str = "DEBUG"  # DEBUG, INFO, WARNING, ERROR

    # Agent enablement flags
    enable_trend_harvester: bool = True
    enable_script_agent: bool = True
    enable_asset_agent: bool = True
    enable_edit_packaging: bool = True
    enable_publisher: bool = True
    enable_analytics: bool = True
    enable_landing_page: bool = True
    enable_offer_intelligence: bool = True
    enable_simp_news: bool = True

    # Content generation
    default_generation_tool: str = "higgsfield"
    max_content_per_day: int = 20
    quality_mode: str = "balanced"

    # Publishing
    enable_tiktok: bool = True
    enable_youtube_shorts: bool = True
    enable_instagram_reels: bool = True
    enable_x: bool = False

    # Monetization
    min_affiliate_commission: float = 20.0
    default_affiliate_network: str = "amazon"

    # Budget
    daily_budget: float = 50.0
    max_cost_per_content: float = 5.0
    budget_alert_threshold: float = 0.8

    # Performance
    rate_limit_calls_per_minute: int = 10

    # SIMP Integration
    simp_broker_url: str = "http://127.0.0.1:5555"
    simp_api_key: str = ""

    # Enabled agents (derived from flags)
    enabled_agents: Set[str] = None

    def __post_init__(self):
        if self.enabled_agents is None:
            self.enabled_agents = self._compute_enabled_agents()

    def _compute_enabled_agents(self) -> Set[str]:
        agents = set()
        if self.enable_trend_harvester:
            agents.add("trend_harvester")
        if self.enable_script_agent:
            agents.add("script_agent")
        if self.enable_asset_agent:
            agents.add("asset_agent")
        if self.enable_edit_packaging:
            agents.add("edit_packaging")
        if self.enable_publisher:
            agents.add("publisher")
        if self.enable_analytics:
            agents.add("analytics")
        if self.enable_landing_page:
            agents.add("landing_page")
        if self.enable_offer_intelligence:
            agents.add("offer_intelligence")
        if self.enable_simp_news:
            agents.add("simp_news")
        return agents

    @property
    def agents_enabled(self) -> Dict[str, bool]:
        """Backward-compatible dict view for orchestrator compatibility."""
        return {
            "trend_harvester": self.enable_trend_harvester,
            "script_agent": self.enable_script_agent,
            "asset_agent": self.enable_asset_agent,
            "edit_packaging": self.enable_edit_packaging,
            "publisher": self.enable_publisher,
            "analytics": self.enable_analytics,
            "landing_page": self.enable_landing_page,
            "offer_intelligence": self.enable_offer_intelligence,
            "simp_news": self.enable_simp_news,
        }

    def validate(self) -> List[str]:
        """Validate config values. Returns list of error messages (empty = valid)."""
        errors = []
        if self.environment not in list(MediaEnvironment):
            errors.append(f"Invalid environment: {self.environment}")
        if self.max_content_per_day < 1:
            errors.append("max_content_per_day must be >= 1")
        if self.max_cost_per_content < 0:
            errors.append("max_cost_per_content must be >= 0")
        if self.daily_budget < 0:
            errors.append("daily_budget must be >= 0")
        if self.budget_alert_threshold < 0 or self.budget_alert_threshold > 1:
            errors.append("budget_alert_threshold must be between 0 and 1")
        if self.rate_limit_calls_per_minute < 1:
            errors.append("rate_limit_calls_per_minute must be >= 1")
        if self.min_affiliate_commission < 0 or self.min_affiliate_commission > 100:
            errors.append("min_affiliate_commission must be between 0 and 100")
        return errors


def load_config() -> MediaGridConfig:
    """Load configuration from environment variables."""
    env_str = os.environ.get("MEDIA_ENVIRONMENT", "development")
    try:
        env = MediaEnvironment(env_str)
    except ValueError:
        env = MediaEnvironment.DEVELOPMENT

    return MediaGridConfig(
        environment=env,
        enable_trend_harvester=_env_bool("MEDIA_ENABLE_TREND_HARVESTER", True),
        enable_script_agent=_env_bool("MEDIA_ENABLE_SCRIPT_AGENT", True),
        enable_asset_agent=_env_bool("MEDIA_ENABLE_ASSET_AGENT", True),
        enable_edit_packaging=_env_bool("MEDIA_ENABLE_EDIT_PACKAGING", True),
        enable_publisher=_env_bool("MEDIA_ENABLE_PUBLISHER", True),
        enable_analytics=_env_bool("MEDIA_ENABLE_ANALYTICS", True),
        enable_landing_page=_env_bool("MEDIA_ENABLE_LANDING_PAGE", True),
        enable_offer_intelligence=_env_bool("MEDIA_ENABLE_OFFER_INTELLIGENCE", True),
        enable_simp_news=_env_bool("MEDIA_ENABLE_SIMP_NEWS", True),
        default_generation_tool=os.environ.get("MEDIA_DEFAULT_GENERATION_TOOL", "higgsfield"),
        max_content_per_day=int(os.environ.get("MEDIA_MAX_CONTENT_PER_DAY", "20")),
        quality_mode=os.environ.get("MEDIA_QUALITY_MODE", "balanced"),
        enable_tiktok=_env_bool("MEDIA_ENABLE_TIKTOK", True),
        enable_youtube_shorts=_env_bool("MEDIA_ENABLE_YOUTUBE_SHORTS", True),
        enable_instagram_reels=_env_bool("MEDIA_ENABLE_INSTAGRAM_REELS", True),
        enable_x=_env_bool("MEDIA_ENABLE_X", False),
        min_affiliate_commission=float(os.environ.get("MEDIA_MIN_AFFILIATE_COMMISSION", "20.0")),
        default_affiliate_network=os.environ.get("MEDIA_DEFAULT_AFFILIATE_NETWORK", "amazon"),
        daily_budget=float(os.environ.get("MEDIA_DAILY_BUDGET", "50.0")),
        max_cost_per_content=float(os.environ.get("MEDIA_MAX_COST_PER_CONTENT", "5.0")),
        budget_alert_threshold=float(os.environ.get("MEDIA_BUDGET_ALERT_THRESHOLD", "0.8")),
        rate_limit_calls_per_minute=int(os.environ.get("MEDIA_RATE_LIMIT_CALLS_PER_MINUTE", "10")),
        simp_broker_url=os.environ.get("MEDIA_SIMP_BROKER_URL", "http://127.0.0.1:5555"),
        simp_api_key=os.environ.get("MEDIA_SIMP_API_KEY", ""),
    )


# Backward-compatible alias
get_config = load_config


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes")
