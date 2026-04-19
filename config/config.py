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

def _default_mesh_db() -> str:
    return str(Path(__file__).parent.parent / "data" / "mesh_offline.db")

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
    
    # Broker settings (for BrokerConfig defaults)
    PORT: int = 5555
    HOST: str = "127.0.0.1"
    MAX_AGENTS: int = 100
    HEALTH_CHECK_INTERVAL: float = 30.0
    HEALTH_CHECK_TIMEOUT: float = 5.0
    LOG_LEVEL: str = "INFO"
    REQUIRE_SIGNATURES: bool = False
    INTENT_TTL: int = 3600
    CLEANUP_INTERVAL: int = 300
    HEALTH_CHECK_FAIL_THRESHOLD: int = 3
    OBFUSCATE_IPS: bool = True
    
    # Rate limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST_SIZE: int = 10
    
    # Mesh settings
    MESH_SHARED_SECRET: str = Field(
        default="",
        description="Stable HMAC secret for receipt signing. Set via env MESH_SHARED_SECRET."
    )
    MESH_DB_PATH: str = Field(default_factory=_default_mesh_db)
    MESH_LOG_DIR: str = Field(default_factory=_default_log_dir)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create singleton instance
config = SimpConfig()