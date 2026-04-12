"""
Configuration for the Scrapling Query Tool.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ScraplingQueryConfig:
    """Configuration for the Scrapling Query Tool."""
    
    # App settings
    app_name: str = "Scrapling Query Tool"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8051  # Different from SIMP dashboard port 8050
    
    # Scrapling settings
    default_fetcher: str = "dynamic"  # "static" or "dynamic"
    max_results_per_query: int = 10
    max_content_length: int = 5000  # characters
    
    # Search settings
    search_timeout: int = 30  # seconds
    respect_robots_txt: bool = True
    
    # Paths
    data_dir: Path = Path("data/scrapling_query")
    cache_dir: Path = Path("data/scrapling_query/cache")
    logs_dir: Path = Path("data/scrapling_query/logs")
    
    def __post_init__(self):
        """Create necessary directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_env(cls) -> "ScraplingQueryConfig":
        """Create config from environment variables."""
        config = cls()
        
        # Override with environment variables if present
        if host := os.getenv("SCRAPLING_QUERY_HOST"):
            config.host = host
        if port := os.getenv("SCRAPLING_QUERY_PORT"):
            config.port = int(port)
        if fetcher := os.getenv("SCRAPLING_QUERY_FETCHER"):
            config.default_fetcher = fetcher
        if max_results := os.getenv("SCRAPLING_QUERY_MAX_RESULTS"):
            config.max_results_per_query = int(max_results)
        
        return config


# Global configuration instance
config = ScraplingQueryConfig.from_env()