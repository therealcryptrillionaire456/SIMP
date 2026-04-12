"""
KEEPTHECHANGE.com - FastAPI Backend

Main FastAPI application for the KEEPTHECHANGE.com platform.
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Import routers
from app.api import users, shopping, payments, crypto, subscriptions, mobile, admin

# Configuration
from app.core.config import settings
from app.core.database import engine, SessionLocal
from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.logging import setup_logging

# Setup logging
logger = setup_logging()

# Create base class for SQLAlchemy models
Base = declarative_base()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting KEEPTHECHANGE.com backend...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database URL: {settings.DATABASE_URL}")
    logger.info(f"SIMP Broker: {settings.SIMP_BROKER_URL}")
    
    # Create database tables
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)  # For development only
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down KEEPTHECHANGE.com backend...")
    await engine.dispose()

# Create FastAPI app
app = FastAPI(
    title="KEEPTHECHANGE.com API",
    description="AI-powered shopping assistant that turns savings into crypto investments",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Include routers
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(shopping.router, prefix="/api/v1", tags=["shopping"])
app.include_router(payments.router, prefix="/api/v1", tags=["payments"])
app.include_router(crypto.router, prefix="/api/v1", tags=["crypto"])
app.include_router(subscriptions.router, prefix="/api/v1", tags=["subscriptions"])
app.include_router(mobile.router, prefix="/api/v1", tags=["mobile"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "KEEPTHECHANGE.com API",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "documentation": "/docs" if settings.ENVIRONMENT != "production" else None,
        "endpoints": {
            "auth": "/api/v1/auth/*",
            "users": "/api/v1/users/*",
            "shopping": "/api/v1/shopping/*",
            "payments": "/api/v1/payments/*",
            "crypto": "/api/v1/crypto/*",
            "subscriptions": "/api/v1/subscriptions/*",
            "mobile": "/api/v1/mobile/*",
            "admin": "/api/v1/admin/*"
        },
        "simp_integration": {
            "broker_url": settings.SIMP_BROKER_URL,
            "agent_id": "keep_the_change_agent",
            "enabled": settings.SIMP_INTEGRATION_ENABLED
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "keep_the_change_api",
        "version": "1.0.0",
        "database": "connected" if engine else "disconnected",
        "environment": settings.ENVIRONMENT
    }

@app.get("/api/v1/status")
async def api_status():
    """Detailed API status"""
    return {
        "status": "operational",
        "uptime": "0 days 0 hours 0 minutes",  # Would be calculated in production
        "version": "1.0.0",
        "maintenance_mode": False,
        "incidents": [],
        "components": {
            "api": "operational",
            "database": "operational",
            "payment_processor": "operational" if settings.STRIPE_SECRET_KEY else "disabled",
            "crypto_trading": "operational" if settings.CRYPTO_TRADING_ENABLED else "disabled",
            "simp_integration": "operational" if settings.SIMP_INTEGRATION_ENABLED else "disabled"
        }
    }

# Dependency for database session
async def get_db() -> AsyncSession:
    """Get database session"""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Dependency for current user
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user"""
    # This would verify JWT token and return user
    # For now, return mock user
    from app.models.user import User
    return User(
        id="user_123",
        email="demo@keepthechange.com",
        subscription_tier="pro",
        total_savings=125.50,
        total_invested=85.25
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level="info"
    )