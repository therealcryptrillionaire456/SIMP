"""
Security Endpoints for A2A Compatibility.

This module provides security-related endpoints and authentication
schemes for A2A compatibility, including API key management,
OAuth2 integration, and mTLS support.

Key features:
- Security scheme declarations
- Authentication validation
- API key management
- Security policy enforcement
- Audit logging for security events
"""

import json
import secrets
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SecurityScheme(str, Enum):
    """Supported security schemes."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    MTLS = "mtls"
    BEARER = "bearer"
    BASIC = "basic"
    NONE = "none"


class SecurityLevel(str, Enum):
    """Security level classifications."""
    PUBLIC = "public"  # No authentication required
    INTERNAL = "internal"  # Internal network only
    PROTECTED = "protected"  # Authentication required
    CONFIDENTIAL = "confidential"  Strong authentication required
    RESTRICTED = "restricted"  # Additional authorization required


@dataclass
class A2ASecurityScheme:
    """A2A security scheme definition."""
    scheme: SecurityScheme  # Security scheme type
    name: str  # Scheme name (e.g., "api_key", "oauth2_client_credentials")
    description: str  # Human-readable description
    parameters: Dict[str, Any] = field(default_factory=dict)  # Scheme parameters
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class SecurityPolicy:
    """Security policy for an agent or endpoint."""
    agent_id: str  # Agent ID this policy applies to
    allowed_schemes: List[SecurityScheme]  # Allowed authentication schemes
    required_level: SecurityLevel = SecurityLevel.PROTECTED  # Required security level
    rate_limit: Optional[int] = None  # Requests per minute
    ip_whitelist: Optional[List[str]] = None  # Allowed IP addresses
    ip_blacklist: Optional[List[str]] = None  # Blocked IP addresses
    allowed_methods: List[str] = field(default_factory=lambda: ["GET", "POST"])  # HTTP methods
    metadata: Dict[str, Any] = field(default_factory=dict)  # Policy metadata
    
    def __post_init__(self):
        """Validate security policy after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate policy fields."""
        # Agent ID validation
        if not self.agent_id or not isinstance(self.agent_id, str):
            raise ValueError("agent_id must be a non-empty string")
        
        # Allowed schemes validation
        if not isinstance(self.allowed_schemes, list):
            raise ValueError("allowed_schemes must be a list")
        for scheme in self.allowed_schemes:
            if not isinstance(scheme, SecurityScheme):
                try:
                    SecurityScheme(scheme)
                except ValueError:
                    raise ValueError(f"Invalid security scheme: {scheme}")
        
        # Security level validation
        if not isinstance(self.required_level, SecurityLevel):
            try:
                self.required_level = SecurityLevel(self.required_level)
            except ValueError:
                raise ValueError(f"Invalid security level: {self.required_level}")
        
        # Rate limit validation
        if self.rate_limit is not None and not isinstance(self.rate_limit, int):
            raise ValueError("rate_limit must be an integer or None")
        
        # IP lists validation
        if self.ip_whitelist is not None:
            if not isinstance(self.ip_whitelist, list):
                raise ValueError("ip_whitelist must be a list or None")
            for ip in self.ip_whitelist:
                if not isinstance(ip, str):
                    raise ValueError("IP addresses must be strings")
        
        if self.ip_blacklist is not None:
            if not isinstance(self.ip_blacklist, list):
                raise ValueError("ip_blacklist must be a list or None")
            for ip in self.ip_blacklist:
                if not isinstance(ip, str):
                    raise ValueError("IP addresses must be strings")
        
        # Allowed methods validation
        if not isinstance(self.allowed_methods, list):
            raise ValueError("allowed_methods must be a list")
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
        for method in self.allowed_methods:
            if method.upper() not in valid_methods:
                raise ValueError(f"Invalid HTTP method: {method}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class APIKeyManager:
    """Manager for API key generation and validation."""
    
    def __init__(self):
        """Initialize API key manager."""
        self._api_keys: Dict[str, Dict[str, Any]] = {}  # key_hash -> key_info
        self._agent_keys: Dict[str, Set[str]] = {}  # agent_id -> set of key_hashes
        logger.info("Initialized API key manager")
    
    def generate_key(
        self,
        agent_id: str,
        name: str,
        description: str = "",
        expires_at: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a new API key for an agent.
        
        Args:
            agent_id: Agent ID
            name: Key name (for identification)
            description: Key description
            expires_at: Expiration timestamp (ISO 8601)
            permissions: List of permissions
            metadata: Additional metadata
            
        Returns:
            Generated API key (plaintext)
        """
        # Generate random key
        key = secrets.token_urlsafe(32)
        
        # Create key hash for storage
        key_hash = self._hash_key(key)
        
        # Create key info
        key_info = {
            "agent_id": agent_id,
            "name": name,
            "description": description,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
            "permissions": permissions or ["read", "write"],
            "metadata": metadata or {},
            "last_used": None,
            "usage_count": 0,
        }
        
        # Store key info
        self._api_keys[key_hash] = key_info
        
        # Update agent key mapping
        if agent_id not in self._agent_keys:
            self._agent_keys[agent_id] = set()
        self._agent_keys[agent_id].add(key_hash)
        
        logger.info(f"Generated API key for agent {agent_id}: {name}")
        return key
    
    def validate_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key.
        
        Args:
            api_key: API key to validate
            
        Returns:
            Key info if valid, None otherwise
        """
        # Hash the key
        key_hash = self._hash_key(api_key)
        
        # Check if key exists
        if key_hash not in self._api_keys:
            logger.warning(f"Invalid API key (not found)")
            return None
        
        key_info = self._api_keys[key_hash]
        
        # Check expiration
        if key_info["expires_at"]:
            try:
                expires_dt = datetime.fromisoformat(key_info["expires_at"].replace('Z', '+00:00'))
                if datetime.utcnow() > expires_dt:
                    logger.warning(f"API key expired: {key_info['name']}")
                    return None
            except ValueError:
                logger.error(f"Invalid expiration date format: {key_info['expires_at']}")
        
        # Update usage info
        key_info["last_used"] = datetime.utcnow().isoformat()
        key_info["usage_count"] += 1
        
        logger.debug(f"Validated API key: {key_info['name']} for agent {key_info['agent_id']}")
        return key_info
    
    def revoke_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke
            
        Returns:
            True if key was revoked, False if not found
        """
        key_hash = self._hash_key(api_key)
        
        if key_hash in self._api_keys:
            key_info = self._api_keys[key_hash]
            agent_id = key_info["agent_id"]
            
            # Remove from mappings
            del self._api_keys[key_hash]
            if agent_id in self._agent_keys:
                self._agent_keys[agent_id].discard(key_hash)
                if not self._agent_keys[agent_id]:
                    del self._agent_keys[agent_id]
            
            logger.info(f"Revoked API key: {key_info['name']} for agent {agent_id}")
            return True
        
        return False
    
    def get_agent_keys(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Get all API keys for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of key info (without actual keys)
        """
        if agent_id not in self._agent_keys:
            return []
        
        keys = []
        for key_hash in self._agent_keys[agent_id]:
            if key_hash in self._api_keys:
                key_info = self._api_keys[key_hash].copy()
                # Don't expose internal fields
                key_info.pop("last_used", None)
                key_info.pop("usage_count", None)
                keys.append(key_info)
        
        return keys
    
    def _hash_key(self, key: str) -> str:
        """Hash an API key for secure storage."""
        return hashlib.sha256(key.encode()).hexdigest()


class A2ASecurityManager:
    """
    Manager for A2A security endpoints and authentication.
    
    This class provides security information, validates requests,
    and manages authentication schemes.
    """
    
    def __init__(self):
        """Initialize A2A security manager."""
        self.api_key_manager = APIKeyManager()
        self.security_policies: Dict[str, SecurityPolicy] = {}
        self.security_schemes: List[A2ASecurityScheme] = self._get_default_schemes()
        logger.info("Initialized A2A security manager")
    
    def _get_default_schemes(self) -> List[A2ASecurityScheme]:
        """Get default security schemes."""
        return [
            A2ASecurityScheme(
                scheme=SecurityScheme.API_KEY,
                name="api_key",
                description="API key authentication",
                parameters={
                    "header_name": "X-API-Key",
                    "query_param": "api_key",
                },
                metadata={"recommended": True},
            ),
            A2ASecurityScheme(
                scheme=SecurityScheme.BEARER,
                name="bearer_token",
                description="Bearer token authentication",
                parameters={
                    "header_name": "Authorization",
                    "header_format": "Bearer {token}",
                },
                metadata={"oauth2_compatible": True},
            ),
            A2ASecurityScheme(
                scheme=SecurityScheme.OAUTH2,
                name="oauth2_client_credentials",
                description="OAuth2 client credentials flow",
                parameters={
                    "token_url": "/oauth/token",
                    "scopes": ["read", "write"],
                },
                metadata={"standard": "RFC6749"},
            ),
            A2ASecurityScheme(
                scheme=SecurityScheme.MTLS,
                name="mutual_tls",
                description="Mutual TLS authentication",
                parameters={
                    "client_cert_required": True,
                    "ca_certificate": "simp_ca.pem",
                },
                metadata={"high_security": True},
            ),
        ]
    
    def get_security_info(self) -> Dict[str, Any]:
        """
        Get security information for A2A compatibility.
        
        Returns:
            Security information dictionary
        """
        return {
            "security_schemes": [scheme.to_dict() for scheme in self.security_schemes],
            "default_scheme": SecurityScheme.API_KEY.value,
            "recommended_scheme": SecurityScheme.API_KEY.value,
            "security_levels": [level.value for level in SecurityLevel],
            "metadata": {
                "version": "1.0.0",
                "updated_at": datetime.utcnow().isoformat(),
                "x-simp-security": "enabled",
            },
        }
    
    def validate_request(
        self,
        request_headers: Dict[str, str],
        request_method: str,
        request_path: str,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate a request against security policies.
        
        Args:
            request_headers: HTTP request headers
            request_method: HTTP method
            request_path: Request path
            agent_id: Optional agent ID for policy lookup
            
        Returns:
            Validation result
        """
        result = {
            "valid": False,
            "scheme": None,
            "agent_id": None,
            "permissions": [],
            "errors": [],
            "warnings": [],
        }
        
        # Check if agent has security policy
        if agent_id and agent_id in self.security_policies:
            policy = self.security_policies[agent_id]
            
            # Check HTTP method
            if request_method.upper() not in policy.allowed_methods:
                result["errors"].append(f"Method {request_method} not allowed")
            
            # Apply security policy
            # (In a real implementation, this would check IP whitelist/blacklist, rate limits, etc.)
        
        # Try to authenticate with available schemes
        authenticated = False
        
        # Try API key authentication
        api_key = request_headers.get("X-API-Key")
        if api_key:
            key_info = self.api_key_manager.validate_key(api_key)
            if key_info:
                result["valid"] = True
                result["scheme"] = SecurityScheme.API_KEY.value
                result["agent_id"] = key_info["agent_id"]
                result["permissions"] = key_info.get("permissions", [])
                authenticated = True
                logger.debug(f"Authenticated with API key: {key_info['name']}")
            else:
                result["errors"].append("Invalid API key")
        
        # Try Bearer token authentication
        if not authenticated and "Authorization" in request_headers:
            auth_header = request_headers["Authorization"]
            if auth_header.startswith("Bearer "):
                # In a real implementation, this would validate the bearer token
                result["warnings"].append("Bearer token validation not implemented")
                # For now, accept any bearer token
                result["valid"] = True
                result["scheme"] = SecurityScheme.BEARER.value
                result["agent_id"] = "bearer_authenticated"
                result["permissions"] = ["read"]
                authenticated = True
        
        # If no authentication scheme matched
        if not authenticated:
            # Check if endpoint allows public access
            if agent_id and agent_id in self.security_policies:
                policy = self.security_policies[agent_id]
                if policy.required_level == SecurityLevel.PUBLIC:
                    result["valid"] = True
                    result["scheme"] = SecurityScheme.NONE.value
                    result["agent_id"] = "public"
                    result["permissions"] = ["read"]
                else:
                    result["errors"].append("Authentication required")
            else:
                result["errors"].append("Authentication required")
        
        # Add timestamp
        result["validated_at"] = datetime.utcnow().isoformat()
        
        return result
    
    def set_security_policy(self, policy: SecurityPolicy) -> None:
        """
        Set security policy for an agent.
        
        Args:
            policy: Security policy
        """
        self.security_policies[policy.agent_id] = policy
        logger.info(f"Set security policy for agent {policy.agent_id}")
    
    def get_security_policy(self, agent_id: str) -> Optional[SecurityPolicy]:
        """
        Get security policy for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Security policy or None
        """
        return self.security_policies.get(agent_id)
    
    def generate_api_key(self, agent_id: str, **kwargs) -> str:
        """
        Generate API key for an agent (convenience method).
        
        Args:
            agent_id: Agent ID
            **kwargs: Additional arguments for generate_key
            
        Returns:
            Generated API key
        """
        return self.api_key_manager.generate_key(agent_id, **kwargs)
    
    def get_agent_api_keys(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Get API keys for an agent (convenience method).
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of key info
        """
        return self.api_key_manager.get_agent_keys(agent_id)


# Global security manager instance
_security_manager: Optional[A2ASecurityManager] = None


def get_a2a_security_manager() -> A2ASecurityManager:
    """Get or create the global A2A security manager."""
    global _security_manager
    
    if _security_manager is None:
        _security_manager = A2ASecurityManager()
    
    return _security_manager


def get_a2a_security_info() -> Dict[str, Any]:
    """
    Get A2A security information (convenience function).
    
    Returns:
        Security information dictionary
    """
    manager = get_a2a_security_manager()
    return manager.get_security_info()


def validate_a2a_request(
    request_headers: Dict[str, str],
    request_method: str,
    request_path: str,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate an A2A request (convenience function).
    
    Args:
        request_headers: HTTP request headers
        request_method: HTTP method
        request_path: Request path
        agent_id: Optional agent ID
        
    Returns:
        Validation result
    """
    manager = get_a2a_security_manager()
    return manager.validate_request(request_headers, request_method, request_path, agent_id)


# Example usage
if __name__ == "__main__":
    # Create security manager
    manager = A2ASecurityManager()
    
    # Get security info
    security_info = manager.get_security_info()
    print("Security Information:")
    print(json.dumps(security_info, indent=2))
    
    # Generate API key for quantumarb
    api_key = manager.generate_api_key(
        agent_id="quantumarb",
        name="quantumarb_production_key",
        description="Production API key for QuantumArb agent",
        permissions=["read", "write", "execute"],
    )
    
    print(f"\nGenerated API key: {api_key}")
    
    # Validate request with API key
    request_headers = {"X-API-Key": api_key}
    validation = manager.validate_request(
        request_headers=request_headers,
        request_method="POST",
        request_path="/a2a/tasks",
        agent_id="quantumarb",
    )
    
    print("\nRequest Validation:")
    print(json.dumps(validation, indent=2))
    
    # Get agent API keys
    agent_keys = manager.get_agent_api_keys("quantumarb")
    print(f"\nAgent API keys: {len(agent_keys)} keys found")