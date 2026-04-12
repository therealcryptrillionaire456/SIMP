import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

def _default_db() -> str:
    return str(Path(__file__).parent.parent / "data" / "simp.db")

def _default_audit_db() -> str:
    return str(Path(__file__).parent.parent / "data" / "audit.db")

def _default_log_dir() -> str:
    return str(Path(__file__).parent.parent / "logs")

def _default_tmp_dir() -> str:
    return str(Path(__file__).parent.parent / "tmp")

class SimpConfig(BaseSettings):
    # Broker settings
    SIMP_BROKER_URL: str = "http://127.0.0.1:5555"
    SIMP_API_KEY: str = "test-key-123"  # Default test key
    
    # Database settings
    DATABASE_URL: str = Field(default_factory=_default_db)
    AUDIT_DATABASE_URL: str = Field(default_factory=_default_audit_db)
    
    # Directory settings
    LOG_DIR: str = Field(default_factory=_default_log_dir)
    TMP_DIR: str = Field(default_factory=_default_tmp_dir)
    
    # Security settings
    REQUIRE_API_KEY: bool = False
    ALLOW_UNREGISTERED_AGENTS: bool = True
    
    # Financial ops settings
    FINANCIAL_OPS_LIVE_ENABLED: bool = False
    FINANCIAL_OPS_DRY_RUN_DAYS: int = 7
    
    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST_SIZE: int = 10
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create singleton instance
config = SimpConfig()