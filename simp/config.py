"""Legacy config location — use config.config.SimpConfig instead.

This module re-exports SimpConfig and legacy aliases so that
``from simp.config import SimpConfig`` works.
"""
from config.config import (  # noqa: F401
    SimpConfig,
    Config,
    ProductionConfig,
    DevelopmentConfig,
    TestingConfig,
    config,
)
