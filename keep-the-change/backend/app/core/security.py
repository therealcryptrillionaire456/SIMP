"""
Security utilities for KEEPTHECHANGE.com
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
import secrets
import string

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=30)  # Refresh tokens valid for 30 days
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """Verify JWT token and return payload if valid"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            return None
        
        # Check expiration
        exp = payload.get("exp")
        if exp is None or datetime.utcfromtimestamp(exp) < datetime.utcnow():
            return None
        
        return payload
    except JWTError:
        return None


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify access token"""
    return verify_token(token, "access")


def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify refresh token"""
    return verify_token(token, "refresh")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get current user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_access_token(token)
    if payload is None:
        raise credentials_exception
    
    # In production, you would fetch the user from database
    # For now, return a mock user based on token payload
    from app.schemas.user import UserResponse
    
    user_id = payload.get("sub")
    email = payload.get("email")
    
    if user_id is None or email is None:
        raise credentials_exception
    
    # Mock user response
    return UserResponse(
        id=user_id,
        email=email,
        email_verified=True,
        subscription_tier="free",
        subscription_status="active",
        total_savings=0.0,
        total_invested=0.0,
        crypto_balance=0.0,
        total_returns=0.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


def generate_api_key(length: int = 32) -> str:
    """Generate a secure API key"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_2fa_secret() -> str:
    """Generate a secret for 2FA"""
    return secrets.token_hex(16)


def sanitize_input(input_string: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", ';', '=', '&', '|']
    for char in dangerous_chars:
        input_string = input_string.replace(char, '')
    
    # Trim whitespace
    input_string = input_string.strip()
    
    return input_string


def validate_email(email: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength"""
    result = {
        "valid": True,
        "errors": [],
        "score": 0  # 0-4 score
    }
    
    # Check length
    if len(password) < 8:
        result["valid"] = False
        result["errors"].append("Password must be at least 8 characters")
    else:
        result["score"] += 1
    
    # Check for uppercase
    if not any(c.isupper() for c in password):
        result["errors"].append("Password should contain at least one uppercase letter")
    else:
        result["score"] += 1
    
    # Check for lowercase
    if not any(c.islower() for c in password):
        result["errors"].append("Password should contain at least one lowercase letter")
    else:
        result["score"] += 1
    
    # Check for digits
    if not any(c.isdigit() for c in password):
        result["errors"].append("Password should contain at least one digit")
    else:
        result["score"] += 1
    
    # Check for special characters
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        result["errors"].append("Password should contain at least one special character")
    else:
        result["score"] += 1
    
    # Update valid status based on score
    if result["score"] < 3:
        result["valid"] = False
    
    return result


def generate_csrf_token() -> str:
    """Generate CSRF token"""
    return secrets.token_urlsafe(32)


def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data (like API keys, tokens) for storage"""
    return pwd_context.hash(data)


def generate_secure_random_string(length: int = 16) -> str:
    """Generate secure random string"""
    return secrets.token_urlsafe(length)


def rate_limit_key(identifier: str, endpoint: str) -> str:
    """Generate rate limit key"""
    return f"rate_limit:{identifier}:{endpoint}"


# Export
__all__ = [
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "verify_access_token",
    "verify_refresh_token",
    "get_current_user",
    "generate_api_key",
    "generate_2fa_secret",
    "sanitize_input",
    "validate_email",
    "validate_password_strength",
    "generate_csrf_token",
    "hash_sensitive_data",
    "generate_secure_random_string",
    "rate_limit_key",
    "oauth2_scheme",
    "pwd_context"
]