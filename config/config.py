"""
SIMP configuration via Pydantic v2 BaseSettings.

Environment variables override defaults.  An optional .env file is also loaded.
"""

import os
from pathlib import Path

from pydantic import ConfigDict, Field

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # type: ignore[no-redef]

# ── default path helpers ─────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _default_db() -> str:
    return str(_PROJECT_ROOT / "data" / "intents.db")


def _default_audit_db() -> str:
    return str(_PROJECT_ROOT / "data" / "audit.db")


def _default_log_dir() -> str:
    return str(_PROJECT_ROOT / "logs")


def _default_tmp_dir() -> str:
    return str(_PROJECT_ROOT / "tmp")


# ── settings model ───────────────────────────────────────────────────────────

class SimpConfig(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        populate_by_name=True,
    )

    HOST: str = Field(default="127.0.0.1", validation_alias="SIMP_HOST")
    PORT: int = Field(default=5555, validation_alias="SIMP_PORT")
    HTTP_HOST: str = Field(default="127.0.0.1", validation_alias="SIMP_HTTP_HOST")
    HTTP_PORT: int = Field(default=8080, validation_alias="SIMP_HTTP_PORT")

    ENABLE_TLS: bool = Field(default=False, validation_alias="SIMP_ENABLE_TLS")
    TLS_CERT_PATH: str = Field(default="", validation_alias="SIMP_TLS_CERT")
    TLS_KEY_PATH: str = Field(default="", validation_alias="SIMP_TLS_KEY")
    TLS_CA_BUNDLE: str = Field(default="", validation_alias="SIMP_TLS_CA")

    REQUIRE_SIGNATURES: bool = Field(default=True, validation_alias="SIMP_REQUIRE_SIGNATURES")
    REQUIRE_API_KEY: bool = Field(default=True, validation_alias="SIMP_REQUIRE_API_KEY")
    API_KEYS: str = Field(default="", validation_alias="SIMP_API_KEYS")

    RATE_LIMIT_ROUTE: str = Field(default="60 per minute", validation_alias="SIMP_RATE_LIMIT_ROUTE")
    RATE_LIMIT_DEFAULT: str = Field(default="200 per day", validation_alias="SIMP_RATE_LIMIT_DEFAULT")
    MAX_PENDING_INTENTS: int = Field(default=500, validation_alias="SIMP_MAX_PENDING_INTENTS")

    SOCKET_CONNECT_TIMEOUT: float = Field(default=10.0, validation_alias="SIMP_SOCKET_CONNECT_TIMEOUT")
    SOCKET_RECV_TIMEOUT: float = Field(default=30.0, validation_alias="SIMP_SOCKET_RECV_TIMEOUT")
    HEALTH_CHECK_TIMEOUT: float = Field(default=5.0, validation_alias="SIMP_HEALTH_CHECK_TIMEOUT")
    HEALTH_CHECK_INTERVAL: float = Field(default=30.0, validation_alias="SIMP_HEALTH_CHECK_INTERVAL")
    HEALTH_CHECK_FAIL_THRESHOLD: int = Field(default=3, validation_alias="SIMP_HEALTH_FAIL_THRESHOLD")

    INTENT_DB_PATH: str = Field(default_factory=_default_db, validation_alias="SIMP_DB_PATH")
    AUDIT_DB_PATH: str = Field(default_factory=_default_audit_db, validation_alias="SIMP_AUDIT_DB_PATH")
    LOG_DIR: str = Field(default_factory=_default_log_dir, validation_alias="SIMP_LOG_DIR")
    TMP_DIR: str = Field(default_factory=_default_tmp_dir, validation_alias="SIMP_TMP_DIR")

    INTENT_TTL_SECONDS: int = Field(default=3600, validation_alias="SIMP_INTENT_TTL")
    INTENT_CLEANUP_INTERVAL: int = Field(default=300, validation_alias="SIMP_CLEANUP_INTERVAL")

    MAX_AGENTS: int = Field(default=100, validation_alias="SIMP_MAX_AGENTS")
    MAX_PAYLOAD_BYTES: int = Field(default=1_000_000, validation_alias="SIMP_MAX_PAYLOAD_BYTES")
    MAX_INTENT_ID_LEN: int = Field(default=256, validation_alias="SIMP_MAX_INTENT_ID_LEN")
    MAX_AGENT_ID_LEN: int = Field(default=128, validation_alias="SIMP_MAX_AGENT_ID_LEN")

    LOG_LEVEL: str = Field(default="INFO", validation_alias="SIMP_LOG_LEVEL")
    OBFUSCATE_IPS: bool = Field(default=True, validation_alias="SIMP_OBFUSCATE_IPS")


# Singleton used by the rest of the codebase: `from config.config import config`
config = SimpConfig()
