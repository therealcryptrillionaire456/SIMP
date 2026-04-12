"""
Configuration settings for KEEPTHECHANGE.com
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, Field, validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "KEEPTHECHANGE.com"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    SECRET_KEY: str = Field(default="your-secret-key-here-change-in-production", env="SECRET_KEY")
    
    # Server
    HOST: str = Field(default="127.0.0.1", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost/keepthechange",
        env="DATABASE_URL"
    )
    
    # Redis (for caching and queues)
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # SIMP Integration
    SIMP_BROKER_URL: str = Field(default="http://localhost:5555", env="SIMP_BROKER_URL")
    SIMP_API_KEY: str = Field(default="test_key", env="SIMP_API_KEY")
    SIMP_INTEGRATION_ENABLED: bool = Field(default=True, env="SIMP_INTEGRATION_ENABLED")
    
    # Payment Processing (Stripe)
    STRIPE_SECRET_KEY: str = Field(default="", env="STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY: str = Field(default="", env="STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET: str = Field(default="", env="STRIPE_WEBHOOK_SECRET")
    
    # Crypto Trading
    CRYPTO_TRADING_ENABLED: bool = Field(default=True, env="CRYPTO_TRADING_ENABLED")
    COINBASE_API_KEY: str = Field(default="", env="COINBASE_API_KEY")
    COINBASE_API_SECRET: str = Field(default="", env="COINBASE_API_SECRET")
    BINANCE_API_KEY: str = Field(default="", env="BINANCE_API_KEY")
    BINANCE_API_SECRET: str = Field(default="", env="BINANCE_API_SECRET")
    
    # Solana Integration
    SOLANA_RPC_URL: str = Field(
        default="https://api.mainnet-beta.solana.com",
        env="SOLANA_RPC_URL"
    )
    SOLANA_WALLET_PRIVATE_KEY: str = Field(default="", env="SOLANA_WALLET_PRIVATE_KEY")
    
    # Retailer APIs
    WALMART_API_KEY: str = Field(default="", env="WALMART_API_KEY")
    TARGET_API_KEY: str = Field(default="", env="TARGET_API_KEY")
    AMAZON_ASSOCIATE_TAG: str = Field(default="", env="AMAZON_ASSOCIATE_TAG")
    
    # Shipping APIs
    SHIPENGINE_API_KEY: str = Field(default="", env="SHIPENGINE_API_KEY")
    EASYPOST_API_KEY: str = Field(default="", env="EASYPOST_API_KEY")
    
    # Email
    SMTP_HOST: str = Field(default="smtp.gmail.com", env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: str = Field(default="", env="SMTP_USERNAME")
    SMTP_PASSWORD: str = Field(default="", env="SMTP_PASSWORD")
    EMAIL_FROM: str = Field(default="noreply@keepthechange.com", env="EMAIL_FROM")
    
    # Social Authentication
    GOOGLE_CLIENT_ID: str = Field(default="", env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", env="GOOGLE_CLIENT_SECRET")
    FACEBOOK_APP_ID: str = Field(default="", env="FACEBOOK_APP_ID")
    FACEBOOK_APP_SECRET: str = Field(default="", env="FACEBOOK_APP_SECRET")
    APPLE_CLIENT_ID: str = Field(default="", env="APPLE_CLIENT_ID")
    APPLE_TEAM_ID: str = Field(default="", env="APPLE_TEAM_ID")
    APPLE_KEY_ID: str = Field(default="", env="APPLE_KEY_ID")
    APPLE_PRIVATE_KEY: str = Field(default="", env="APPLE_PRIVATE_KEY")
    
    # JWT
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24 * 7, env="ACCESS_TOKEN_EXPIRE_MINUTES")  # 7 days
    
    # File Uploads
    MAX_UPLOAD_SIZE: int = Field(default=16 * 1024 * 1024, env="MAX_UPLOAD_SIZE")  # 16MB
    UPLOAD_DIR: str = Field(default="uploads", env="UPLOAD_DIR")
    
    # Analytics
    MIXPANEL_TOKEN: str = Field(default="", env="MIXPANEL_TOKEN")
    SEGMENT_WRITE_KEY: str = Field(default="", env="SEGMENT_WRITE_KEY")
    
    # Security
    RATE_LIMIT_REQUESTS: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_PERIOD: int = Field(default=60, env="RATE_LIMIT_PERIOD")  # seconds
    
    # Business Logic
    MIN_SAVINGS_FOR_INVESTMENT: float = Field(default=0.01, env="MIN_SAVINGS_FOR_INVESTMENT")  # $0.01
    MAX_INVESTMENT_PER_DAY: float = Field(default=100.00, env="MAX_INVESTMENT_PER_DAY")
    DEFAULT_CRYPTO_ASSET: str = Field(default="SOL", env="DEFAULT_CRYPTO_ASSET")
    PLATFORM_FEE_PERCENTAGE: float = Field(default=0.20, env="PLATFORM_FEE_PERCENTAGE")  # 20% of savings
    
    # Subscription Tiers
    SUBSCRIPTION_TIERS: dict = {
        "free": {
            "price": 0.00,
            "user_share": 0.00,  # 0% of agent returns
            "transaction_fee": 0.02,  # 2% transaction fee
            "features": ["basic_price_comparison", "manual_purchasing"]
        },
        "basic": {
            "price": 4.99,
            "user_share": 0.10,  # 10% of agent returns
            "transaction_fee": 0.01,  # 1% transaction fee
            "features": ["advanced_price_comparison", "auto_purchasing", "basic_support"]
        },
        "pro": {
            "price": 14.99,
            "user_share": 0.25,  # 25% of agent returns
            "transaction_fee": 0.00,  # 0% transaction fee
            "features": ["premium_price_comparison", "priority_support", "advanced_analytics"]
        },
        "elite": {
            "price": 49.99,
            "user_share": 0.50,  # 50% of agent returns
            "transaction_fee": 0.00,  # 0% transaction fee
            "features": ["custom_strategies", "24/7_support", "enterprise_features"]
        }
    }
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Ensure database URL is valid"""
        if not v:
            raise ValueError("DATABASE_URL must be set")
        return v
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        """Ensure secret key is strong in production"""
        if os.getenv("ENVIRONMENT") == "production" and v == "your-secret-key-here-change-in-production":
            raise ValueError("SECRET_KEY must be changed in production")
        return v
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string to list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Export settings
__all__ = ["settings"]