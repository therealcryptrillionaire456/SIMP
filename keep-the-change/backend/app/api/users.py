"""
Users API router for KEEPTHECHANGE.com
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    get_current_user,
    create_refresh_token,
    verify_refresh_token
)
from app.core.config import settings
from app.models.user import User, UserSession, UserAuditLog
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    TokenResponse,
    SocialAuthRequest,
    UserStatsResponse,
    EmailVerificationRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    TwoFactorSetupRequest
)

router = APIRouter(prefix="/users", tags=["users"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user
    
    - **email**: User's email address
    - **password**: User's password (min 8 characters)
    - **first_name**: User's first name (optional)
    - **last_name**: User's last name (optional)
    """
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        subscription_tier="free",
        subscription_status="active",
        subscription_start_date=datetime.utcnow()
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=user.id,
        action="register",
        resource_type="user",
        resource_id=str(user.id),
        details={"method": "email"}
    )
    db.add(audit_log)
    await db.commit()
    
    return UserResponse.from_orm(user)


@router.post("/auth/login", response_model=TokenResponse)
async def login_user(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login user with email and password
    
    Returns access token and refresh token
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == login_data.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check if account is locked
    if user.account_locked_until and user.account_locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked due to too many failed login attempts"
        )
    
    # Reset failed login attempts on successful login
    user.failed_login_attempts = 0
    user.account_locked_until = None
    user.last_login = datetime.utcnow()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Create user session
    session = UserSession(
        user_id=user.id,
        session_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=30),  # Refresh token valid for 30 days
        device_info=login_data.device_info,
        ip_address=login_data.ip_address,
        user_agent=login_data.user_agent
    )
    
    db.add(session)
    await db.commit()
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=str(user.id),
        details={"method": "email"},
        ip_address=login_data.ip_address,
        user_agent=login_data.user_agent
    )
    db.add(audit_log)
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.from_orm(user)
    )


@router.post("/auth/social", response_model=TokenResponse)
async def social_auth(
    social_data: SocialAuthRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user via social provider (Google, Facebook, Apple)
    
    - **provider**: Social provider (google, facebook, apple)
    - **token**: Access token from social provider
    - **user_info**: Additional user information from social provider
    """
    # In production, this would validate the social token with the provider
    # For now, we'll create or update user based on social auth data
    
    # Extract user info from social data
    social_id = social_data.user_info.get("id")
    email = social_data.user_info.get("email")
    first_name = social_data.user_info.get("given_name") or social_data.user_info.get("first_name")
    last_name = social_data.user_info.get("family_name") or social_data.user_info.get("last_name")
    avatar_url = social_data.user_info.get("picture")
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required for social authentication"
        )
    
    # Check if user exists by social auth ID
    result = await db.execute(
        select(User).where(
            (User.social_auth_provider == social_data.provider) &
            (User.social_auth_id == social_id)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Check if user exists by email
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Link social auth to existing account
            user.social_auth_provider = social_data.provider
            user.social_auth_id = social_id
            user.social_auth_data = social_data.user_info
        else:
            # Create new user
            user = User(
                email=email,
                email_verified=True,  # Social auth emails are typically verified
                social_auth_provider=social_data.provider,
                social_auth_id=social_id,
                social_auth_data=social_data.user_info,
                first_name=first_name,
                last_name=last_name,
                avatar_url=avatar_url,
                subscription_tier="free",
                subscription_status="active",
                subscription_start_date=datetime.utcnow()
            )
            db.add(user)
    
    user.last_login = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    
    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Create user session
    session = UserSession(
        user_id=user.id,
        session_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=30),
        device_info=social_data.device_info,
        ip_address=social_data.ip_address,
        user_agent=social_data.user_agent
    )
    
    db.add(session)
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=str(user.id),
        details={"method": f"social_{social_data.provider}"},
        ip_address=social_data.ip_address,
        user_agent=social_data.user_agent
    )
    db.add(audit_log)
    
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.from_orm(user)
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    # Verify refresh token
    payload = verify_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = uuid.UUID(payload.get("sub"))
    
    # Check if session exists
    result = await db.execute(
        select(UserSession).where(
            (UserSession.user_id == user_id) &
            (UserSession.session_token == refresh_token) &
            (UserSession.expires_at > datetime.utcnow())
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )
    
    # Update session last activity
    session.last_activity = datetime.utcnow()
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,  # Same refresh token
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.from_orm(user)
    )


@router.post("/auth/logout")
async def logout_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout user and invalidate session
    """
    # In production, you might want to accept a specific session token to logout
    # For now, we'll just create an audit log entry
    
    audit_log = UserAuditLog(
        user_id=current_user.id,
        action="logout",
        resource_type="user",
        resource_id=str(current_user.id)
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information
    """
    return UserResponse.from_orm(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user information
    """
    # Update user fields
    update_data = user_data.dict(exclude_unset=True)
    
    # Handle password update
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))
    
    # Update user object
    for field, value in update_data.items():
        if hasattr(current_user, field):
            setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=current_user.id,
        action="update_profile",
        resource_type="user",
        resource_id=str(current_user.id),
        details={"updated_fields": list(update_data.keys())}
    )
    db.add(audit_log)
    
    await db.commit()
    await db.refresh(current_user)
    
    return UserResponse.from_orm(current_user)


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user statistics and performance metrics
    """
    # In production, you would calculate these from database queries
    # For now, return mock data based on user fields
    
    return UserStatsResponse(
        user_id=current_user.id,
        total_savings=current_user.total_savings or 0.0,
        total_invested=current_user.total_invested or 0.0,
        crypto_balance=current_user.crypto_balance or 0.0,
        total_returns=current_user.total_returns or 0.0,
        portfolio_value=current_user.total_portfolio_value,
        subscription_tier=current_user.subscription_tier,
        account_age_days=(datetime.utcnow() - current_user.created_at).days,
        last_login=current_user.last_login,
        metrics={
            "total_purchases": 5,  # Mock
            "average_savings_per_purchase": current_user.total_savings / 5 if current_user.total_savings else 0,
            "investment_roi": (current_user.total_returns / current_user.total_invested * 100) if current_user.total_invested else 0,
            "subscription_savings": 25.0,  # Mock
            "agent_tips": 10.0  # Mock
        }
    )


@router.delete("/me")
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete current user account (soft delete)
    """
    # Soft delete user
    current_user.deleted_at = datetime.utcnow()
    current_user.email = f"deleted_{current_user.id}_{current_user.email}"
    current_user.social_auth_id = None
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=current_user.id,
        action="delete_account",
        resource_type="user",
        resource_id=str(current_user.id)
    )
    db.add(audit_log)
    
    await db.commit()
    
    return {"message": "Account successfully deleted"}


@router.post("/me/wallet/connect")
async def connect_crypto_wallet(
    wallet_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Connect crypto wallet for returns distribution
    """
    wallet_address = wallet_data.get("wallet_address")
    wallet_type = wallet_data.get("wallet_type", "solana")
    
    if not wallet_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet address is required"
        )
    
    # Validate wallet address (basic validation)
    if wallet_type == "solana" and not wallet_address.startswith(("1", "2", "3", "4", "5")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Solana wallet address"
        )
    
    # Update user wallet info
    current_user.crypto_wallet_address = wallet_address
    current_user.crypto_wallet_type = wallet_type
    current_user.updated_at = datetime.utcnow()
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=current_user.id,
        action="connect_wallet",
        resource_type="user",
        resource_id=str(current_user.id),
        details={"wallet_type": wallet_type, "wallet_address": wallet_address[:10] + "..."}
    )
    db.add(audit_log)
    
    await db.commit()
    
    return {
        "message": "Wallet connected successfully",
        "wallet_type": wallet_type,
        "wallet_address": wallet_address
    }


@router.get("/me/sessions")
async def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's active sessions
    """
    result = await db.execute(
        select(UserSession).where(
            (UserSession.user_id == current_user.id) &
            (UserSession.expires_at > datetime.utcnow())
        ).order_by(UserSession.last_activity.desc())
    )
    sessions = result.scalars().all()
    
    return {
        "sessions": [
            {
                "id": str(session.id),
                "device_info": session.device_info,
                "ip_address": session.ip_address,
                "last_activity": session.last_activity,
                "expires_at": session.expires_at
            }
            for session in sessions
        ]
    }


@router.delete("/me/sessions/{session_id}")
async def revoke_user_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke a specific user session
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID"
        )
    
    result = await db.execute(
        select(UserSession).where(
            (UserSession.id == session_uuid) &
            (UserSession.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Expire the session immediately
    session.expires_at = datetime.utcnow()
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=current_user.id,
        action="revoke_session",
        resource_type="session",
        resource_id=session_id
    )
    db.add(audit_log)
    
    await db.commit()
    
    return {"message": "Session revoked successfully"}


@router.post("/auth/verify-email/request")
async def request_email_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Request email verification token
    
    In production, this would send an email with verification link
    For now, we'll generate a token and return it (for testing)
    """
    if current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )
    
    # Generate verification token (in production, this would be sent via email)
    from app.core.security import generate_secure_random_string
    verification_token = generate_secure_random_string(32)
    
    # In production, you would:
    # 1. Store the token in database with expiration
    # 2. Send email with verification link
    # 3. Return success message
    
    # For now, return the token for testing
    return {
        "message": "Verification email sent (in production)",
        "verification_token": verification_token,  # Only for testing
        "note": "In production, token would be sent via email"
    }


@router.post("/auth/verify-email/confirm")
async def confirm_email_verification(
    verification_data: EmailVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm email verification with token
    
    In production, this would validate the token from email
    For testing, any token will work
    """
    if current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )
    
    # In production, you would:
    # 1. Validate the token against stored token
    # 2. Check expiration
    # 3. Mark email as verified
    
    # For testing, we'll accept any token
    current_user.email_verified = True
    current_user.updated_at = datetime.utcnow()
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=current_user.id,
        action="verify_email",
        resource_type="user",
        resource_id=str(current_user.id)
    )
    db.add(audit_log)
    
    await db.commit()
    
    return {"message": "Email verified successfully"}


@router.post("/auth/password-reset/request")
async def request_password_reset(
    reset_request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset token
    
    In production, this would send an email with reset link
    For now, we'll generate a token and return it (for testing)
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == reset_request.email)
    )
    user = result.scalar_one_or_none()
    
    # For security, always return success even if user doesn't exist
    if not user:
        return {
            "message": "If the email exists, a password reset link has been sent",
            "note": "This prevents email enumeration attacks"
        }
    
    # Generate reset token (in production, this would be sent via email)
    from app.core.security import generate_secure_random_string
    reset_token = generate_secure_random_string(32)
    
    # In production, you would:
    # 1. Store the token in database with expiration
    # 2. Send email with reset link
    # 3. Return success message
    
    # For now, return the token for testing
    return {
        "message": "Password reset email sent (in production)",
        "reset_token": reset_token,  # Only for testing
        "note": "In production, token would be sent via email"
    }


@router.post("/auth/password-reset/confirm")
async def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm password reset with token
    
    In production, this would validate the token from email
    For testing, any token will work
    """
    # In production, you would:
    # 1. Validate the token against stored token
    # 2. Check expiration
    # 3. Find user associated with token
    # 4. Update password
    
    # For testing, we need to find user by email or token
    # Since we don't have token-user mapping in this simple implementation,
    # we'll require the user to be logged in or provide additional info
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset confirmation requires proper token storage implementation"
    )


@router.post("/auth/2fa/setup")
async def setup_two_factor(
    twofa_data: TwoFactorSetupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Setup two-factor authentication
    
    In production, this would generate QR code for TOTP
    For now, we'll simulate the setup
    """
    if twofa_data.enable:
        if current_user.two_factor_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is already enabled"
            )
        
        # Generate 2FA secret (in production, use proper TOTP library)
        from app.core.security import generate_2fa_secret
        secret = generate_2fa_secret()
        
        # Store secret (in production, encrypt it)
        current_user.two_factor_enabled = True
        current_user.two_factor_secret = secret
        current_user.updated_at = datetime.utcnow()
        
        # Create audit log
        audit_log = UserAuditLog(
            user_id=current_user.id,
            action="enable_2fa",
            resource_type="user",
            resource_id=str(current_user.id),
            details={"method": twofa_data.method}
        )
        db.add(audit_log)
        
        await db.commit()
        
        return {
            "message": "2FA setup initiated",
            "method": twofa_data.method,
            "secret": secret,  # In production, only show QR code, not secret
            "note": "In production, show QR code for TOTP app"
        }
    else:
        # Disable 2FA
        if not current_user.two_factor_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is not enabled"
            )
        
        current_user.two_factor_enabled = False
        current_user.two_factor_secret = None
        current_user.updated_at = datetime.utcnow()
        
        # Create audit log
        audit_log = UserAuditLog(
            user_id=current_user.id,
            action="disable_2fa",
            resource_type="user",
            resource_id=str(current_user.id)
        )
        db.add(audit_log)
        
        await db.commit()
        
        return {"message": "2FA disabled successfully"}


@router.post("/auth/2fa/verify")
async def verify_two_factor(
    code: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify two-factor authentication code
    
    In production, this would validate TOTP code
    For now, we'll accept any 6-digit code
    """
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this account"
        )
    
    # In production, you would:
    # 1. Validate the TOTP code using the stored secret
    # 2. Check for code reuse (prevent replay attacks)
    
    # For testing, accept any 6-digit code
    if not code or len(code) != 6 or not code.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code format"
        )
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=current_user.id,
        action="verify_2fa",
        resource_type="user",
        resource_id=str(current_user.id)
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "2FA verification successful"}


@router.post("/auth/account-lockout/test")
async def test_account_lockout(
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Test account lockout mechanism
    
    This endpoint simulates failed login attempts
    WARNING: Only for testing purposes
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Simulate failed login attempts
    max_attempts = 5
    user.failed_login_attempts += 1
    
    if user.failed_login_attempts >= max_attempts:
        # Lock account for 15 minutes
        lockout_duration = timedelta(minutes=15)
        user.account_locked_until = datetime.utcnow() + lockout_duration
        
        # Create audit log
        audit_log = UserAuditLog(
            user_id=user.id,
            action="account_locked",
            resource_type="user",
            resource_id=str(user.id),
            details={
                "reason": "too_many_failed_attempts",
                "lockout_until": user.account_locked_until.isoformat()
            }
        )
        db.add(audit_log)
    
    await db.commit()
    
    return {
        "message": f"Failed attempt recorded. Attempt {user.failed_login_attempts} of {max_attempts}",
        "account_locked": user.account_locked_until is not None,
        "locked_until": user.account_locked_until,
        "failed_attempts": user.failed_login_attempts
    }


@router.post("/auth/account-lockout/reset")
async def reset_account_lockout(
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset account lockout (admin/testing only)
    
    WARNING: Only for testing purposes
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Reset lockout
    user.failed_login_attempts = 0
    user.account_locked_until = None
    
    # Create audit log
    audit_log = UserAuditLog(
        user_id=user.id,
        action="account_lockout_reset",
        resource_type="user",
        resource_id=str(user.id)
    )
    db.add(audit_log)
    
    await db.commit()
    
    return {"message": "Account lockout reset successfully"}