"""
Security & Confidentiality Framework - Build 15 Part 1
Provides encryption, access control, audit logging, and data protection for legal system.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import hashlib
import hmac
import base64
import uuid
from pathlib import Path
import secrets
import string

# Try to import cryptography libraries
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("cryptography library not available, using mock encryption")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security levels for data classification."""
    PUBLIC = "public"  # No restrictions
    INTERNAL = "internal"  # Internal use only
    CONFIDENTIAL = "confidential"  # Sensitive business information
    RESTRICTED = "restricted"  # Highly sensitive
    SECRET = "secret"  # Legal privilege, attorney-client


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "aes_256_gcm"
    AES_256_CBC = "aes_256_cbc"
    CHACHA20_POLY1305 = "chacha20_poly1305"
    FERNET = "fernet"


class HashAlgorithm(Enum):
    """Supported hash algorithms."""
    SHA256 = "sha256"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"


class AccessLevel(Enum):
    """Access levels for RBAC."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    AUDIT = "audit"


@dataclass
class SecurityConfig:
    """Security framework configuration."""
    encryption_enabled: bool = True
    default_algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    key_rotation_days: int = 90
    password_hashing_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    password_salt_length: int = 32
    session_timeout_minutes: int = 60
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30
    audit_log_enabled: bool = True
    audit_retention_days: int = 365
    data_retention_days: int = 1095  # 3 years
    backup_encryption: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class User:
    """System user with security attributes."""
    user_id: str
    username: str
    email: str
    roles: List[str] = field(default_factory=list)
    permissions: Dict[str, List[AccessLevel]] = field(default_factory=dict)
    security_level: SecurityLevel = SecurityLevel.INTERNAL
    password_hash: Optional[str] = None
    password_salt: Optional[str] = None
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Role:
    """Role for RBAC."""
    role_id: str
    name: str
    description: str
    permissions: Dict[str, List[AccessLevel]] = field(default_factory=dict)
    security_level: SecurityLevel = SecurityLevel.INTERNAL
    inherits_from: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Resource:
    """Protected resource."""
    resource_id: str
    name: str
    type: str
    security_level: SecurityLevel = SecurityLevel.INTERNAL
    owner_id: str = "system"
    encryption_key_id: Optional[str] = None
    access_policy: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class EncryptionKey:
    """Encryption key for data protection."""
    key_id: str
    algorithm: EncryptionAlgorithm
    key_data: bytes
    key_version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    revoked: bool = False
    revoked_at: Optional[datetime] = None


@dataclass
class AuditLogEntry:
    """Audit log entry."""
    log_id: str
    event_type: str
    user_id: Optional[str] = None
    resource_id: Optional[str] = None
    action: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SecurityMetrics:
    """Security framework metrics."""
    total_users: int = 0
    active_sessions: int = 0
    failed_logins: int = 0
    successful_logins: int = 0
    encryption_operations: int = 0
    decryption_operations: int = 0
    access_denied: int = 0
    audit_entries: int = 0
    calculated_at: datetime = field(default_factory=datetime.now)


class SecurityFramework:
    """
    Security & Confidentiality Framework.
    Provides encryption, access control, audit logging, and data protection.
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None, 
                 master_key: Optional[str] = None):
        """
        Initialize Security Framework.
        
        Args:
            config: Security configuration
            master_key: Master encryption key (for key derivation)
        """
        self.config = config or SecurityConfig()
        self.master_key = master_key or self._generate_master_key()
        
        # Storage
        self.users: Dict[str, User] = {}
        self.roles: Dict[str, Role] = {}
        self.resources: Dict[str, Resource] = {}
        self.encryption_keys: Dict[str, EncryptionKey] = {}
        self.audit_log: List[AuditLogEntry] = []
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Metrics
        self.metrics = SecurityMetrics()
        
        # Initialize default roles and users
        self._initialize_default_roles()
        self._initialize_default_users()
        
        # Generate initial encryption keys
        self._generate_initial_keys()
        
        logger.info("Initialized Security & Confidentiality Framework")
    
    def _generate_master_key(self) -> str:
        """Generate a master key for key derivation."""
        # In production, this would be loaded from secure storage
        # For now, generate a random key
        if CRYPTOGRAPHY_AVAILABLE:
            return Fernet.generate_key().decode()
        else:
            # Generate a random string as fallback
            alphabet = string.ascii_letters + string.digits + string.punctuation
            return ''.join(secrets.choice(alphabet) for _ in range(64))
    
    def _initialize_default_roles(self):
        """Initialize default roles."""
        default_roles = [
            Role(
                role_id="admin",
                name="System Administrator",
                description="Full system access",
                permissions={
                    "*": [AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE, AccessLevel.ADMIN]
                },
                security_level=SecurityLevel.SECRET
            ),
            Role(
                role_id="legal_director",
                name="Legal Director",
                description="Legal department leadership",
                permissions={
                    "cases": [AccessLevel.READ, AccessLevel.WRITE],
                    "contracts": [AccessLevel.READ, AccessLevel.WRITE],
                    "documents": [AccessLevel.READ, AccessLevel.WRITE],
                    "reports": [AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE]
                },
                security_level=SecurityLevel.RESTRICTED
            ),
            Role(
                role_id="attorney",
                name="Attorney",
                description="Legal professional",
                permissions={
                    "cases": [AccessLevel.READ, AccessLevel.WRITE],
                    "contracts": [AccessLevel.READ, AccessLevel.WRITE],
                    "documents": [AccessLevel.READ, AccessLevel.WRITE]
                },
                security_level=SecurityLevel.CONFIDENTIAL
            ),
            Role(
                role_id="paralegal",
                name="Paralegal",
                description="Legal support staff",
                permissions={
                    "cases": [AccessLevel.READ],
                    "documents": [AccessLevel.READ, AccessLevel.WRITE]
                },
                security_level=SecurityLevel.INTERNAL
            ),
            Role(
                role_id="auditor",
                name="Auditor",
                description="Compliance and audit",
                permissions={
                    "*": [AccessLevel.READ, AccessLevel.AUDIT]
                },
                security_level=SecurityLevel.RESTRICTED
            )
        ]
        
        for role in default_roles:
            self.create_role(role)
        
        logger.info(f"Initialized {len(default_roles)} default roles")
    
    def _initialize_default_users(self):
        """Initialize default users."""
        default_users = [
            User(
                user_id="admin_001",
                username="admin",
                email="admin@pentagram.legal",
                roles=["admin"],
                security_level=SecurityLevel.SECRET
            ),
            User(
                user_id="legal_dir_001",
                username="legal_director",
                email="director@pentagram.legal",
                roles=["legal_director", "auditor"],
                security_level=SecurityLevel.RESTRICTED
            ),
            User(
                user_id="attorney_001",
                username="attorney",
                email="attorney@pentagram.legal",
                roles=["attorney"],
                security_level=SecurityLevel.CONFIDENTIAL
            )
        ]
        
        for user in default_users:
            # Set default password
            self.create_user(user, "ChangeMe123!")
        
        logger.info(f"Initialized {len(default_users)} default users")
    
    def _generate_initial_keys(self):
        """Generate initial encryption keys."""
        if not self.config.encryption_enabled:
            return
        
        # Generate keys for each algorithm
        for algorithm in EncryptionAlgorithm:
            key_id = f"key_{algorithm.value}_v1"
            
            if algorithm == EncryptionAlgorithm.FERNET and CRYPTOGRAPHY_AVAILABLE:
                key_data = Fernet.generate_key()
            else:
                # Generate random key data
                key_data = secrets.token_bytes(32)
            
            # Set expiration for key rotation
            expires_at = datetime.now() + timedelta(days=self.config.key_rotation_days)
            
            key = EncryptionKey(
                key_id=key_id,
                algorithm=algorithm,
                key_data=key_data,
                expires_at=expires_at
            )
            
            self.encryption_keys[key_id] = key
        
        logger.info(f"Generated {len(self.encryption_keys)} encryption keys")
    
    def create_user(self, user: User, password: str) -> bool:
        """
        Create a new user with password.
        
        Args:
            user: User object
            password: Plain text password
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate user ID if not provided
            if not user.user_id:
                user.user_id = f"user_{uuid.uuid4().hex[:16]}"
            
            # Check if username already exists
            for existing_user in self.users.values():
                if existing_user.username == user.username:
                    logger.error(f"Username {user.username} already exists")
                    return False
            
            # Hash password
            salt, password_hash = self._hash_password(password)
            user.password_hash = password_hash
            user.password_salt = salt
            
            # Store user
            self.users[user.user_id] = user
            
            # Update metrics
            self.metrics.total_users += 1
            
            # Log audit event
            self._log_audit_event(
                event_type="user_created",
                user_id=user.user_id,
                action="Create user",
                details={"username": user.username, "roles": user.roles}
            )
            
            logger.info(f"Created user {user.username} ({user.user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return False
    
    def authenticate_user(self, username: str, password: str, 
                         ip_address: Optional[str] = None) -> Optional[User]:
        """
        Authenticate a user.
        
        Args:
            username: Username
            password: Password
            ip_address: Client IP address
            
        Returns:
            Authenticated user or None
        """
        try:
            # Find user by username
            user = None
            for u in self.users.values():
                if u.username == username:
                    user = u
                    break
            
            if not user:
                logger.warning(f"Authentication failed: user {username} not found")
                self.metrics.failed_logins += 1
                return None
            
            # Check if account is locked
            if user.account_locked_until and user.account_locked_until > datetime.now():
                logger.warning(f"Account {username} is locked until {user.account_locked_until}")
                self._log_audit_event(
                    event_type="account_locked",
                    user_id=user.user_id,
                    action="Login attempt",
                    details={"reason": "Account locked", "locked_until": user.account_locked_until.isoformat()},
                    ip_address=ip_address,
                    success=False
                )
                return None
            
            # Verify password
            if not self._verify_password(password, user.password_hash, user.password_salt):
                user.failed_login_attempts += 1
                user.updated_at = datetime.now()
                
                # Check if account should be locked
                if user.failed_login_attempts >= self.config.max_login_attempts:
                    user.account_locked_until = datetime.now() + timedelta(minutes=self.config.lockout_duration_minutes)
                    logger.warning(f"Account {username} locked due to {user.failed_login_attempts} failed attempts")
                
                self.users[user.user_id] = user
                self.metrics.failed_logins += 1
                
                # Log failed attempt
                self._log_audit_event(
                    event_type="login_failed",
                    user_id=user.user_id,
                    action="Login attempt",
                    details={"failed_attempts": user.failed_login_attempts},
                    ip_address=ip_address,
                    success=False,
                    error_message="Invalid password"
                )
                
                return None
            
            # Successful authentication
            user.last_login = datetime.now()
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.updated_at = datetime.now()
            
            self.users[user.user_id] = user
            self.metrics.successful_logins += 1
            
            # Log successful login
            self._log_audit_event(
                event_type="login_success",
                user_id=user.user_id,
                action="Login",
                details={},
                ip_address=ip_address,
                success=True
            )
            
            logger.info(f"User {username} authenticated successfully")
            return user
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            self.metrics.failed_logins += 1
            return None
    
    def create_role(self, role: Role) -> bool:
        """
        Create a new role.
        
        Args:
            role: Role object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate role ID if not provided
            if not role.role_id:
                role.role_id = f"role_{uuid.uuid4().hex[:16]}"
            
            # Check if role already exists
            if role.role_id in self.roles:
                logger.warning(f"Role {role.role_id} already exists")
                return False
            
            # Store role
            self.roles[role.role_id] = role
            
            # Log audit event
            self._log_audit_event(
                event_type="role_created",
                action="Create role",
                details={"role_id": role.role_id, "name": role.name}
            )
            
            logger.info(f"Created role {role.name} ({role.role_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error creating role: {str(e)}")
            return False
    
    def assign_role_to_user(self, user_id: str, role_id: str) -> bool:
        """
        Assign a role to a user.
        
        Args:
            user_id: User ID
            role_id: Role ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if user exists
            if user_id not in self.users:
                logger.error(f"User {user_id} not found")
                return False
            
            # Check if role exists
            if role_id not in self.roles:
                logger.error(f"Role {role_id} not found")
                return False
            
            user = self.users[user_id]
            
            # Check if user already has this role
            if role_id in user.roles:
                logger.warning(f"User {user_id} already has role {role_id}")
                return False
            
            # Assign role
            user.roles.append(role_id)
            user.updated_at = datetime.now()
            
            self.users[user_id] = user
            
            # Log audit event
            self._log_audit_event(
                event_type="role_assigned",
                user_id=user_id,
                action="Assign role",
                details={"role_id": role_id, "username": user.username}
            )
            
            logger.info(f"Assigned role {role_id} to user {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Error assigning role: {str(e)}")
            return False
    
    def check_permission(self, user_id: str, resource_type: str, 
                        action: AccessLevel) -> bool:
        """
        Check if user has permission for an action on a resource type.
        
        Args:
            user_id: User ID
            resource_type: Type of resource
            action: Action to perform
            
        Returns:
            True if permitted, False otherwise
        """
        try:
            # Check if user exists
            if user_id not in self.users:
                logger.error(f"User {user_id} not found")
                return False
            
            user = self.users[user_id]
            
            # Get all permissions from user's roles
            all_permissions = {}
            
            for role_id in user.roles:
                if role_id in self.roles:
                    role = self.roles[role_id]
                    
                    # Add role permissions
                    for resource, actions in role.permissions.items():
                        if resource not in all_permissions:
                            all_permissions[resource] = set()
                        all_permissions[resource].update(actions)
                    
                    # Handle inherited roles
                    for inherited_role_id in role.inherits_from:
                        if inherited_role_id in self.roles:
                            inherited_role = self.roles[inherited_role_id]
                            for resource, actions in inherited_role.permissions.items():
                                if resource not in all_permissions:
                                    all_permissions[resource] = set()
                                all_permissions[resource].update(actions)
            
            # Add user-specific permissions
            for resource, actions in user.permissions.items():
                if resource not in all_permissions:
                    all_permissions[resource] = set()
                all_permissions[resource].update(actions)
            
            # Check permission
            # First check specific resource type
            if resource_type in all_permissions:
                if action in all_permissions[resource_type]:
                    return True
            
            # Check wildcard permission
            if "*" in all_permissions:
                if action in all_permissions["*"]:
                    return True
            
            # Permission denied
            self.metrics.access_denied += 1
            
            # Log access denied
            self._log_audit_event(
                event_type="access_denied",
                user_id=user_id,
                action="Check permission",
                details={"resource_type": resource_type, "action": action.value},
                success=False,
                error_message="Insufficient permissions"
            )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking permission: {str(e)}")
            return False
    
    def encrypt_data(self, data: bytes, security_level: SecurityLevel = SecurityLevel.CONFIDENTIAL,
                    algorithm: Optional[EncryptionAlgorithm] = None) -> Dict[str, Any]:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt
            security_level: Security level for key selection
            algorithm: Encryption algorithm (uses default if None)
            
        Returns:
            Dictionary with encrypted data and metadata
        """
        if not self.config.encryption_enabled:
            return {
                "encrypted": False,
                "data": data,
                "algorithm": "none",
                "security_level": security_level.value
            }
        
        try:
            # Select algorithm
            if algorithm is None:
                algorithm = self.config.default_algorithm
            
            # Get appropriate key for security level
            key_id = self._get_key_for_security_level(security_level, algorithm)
            if not key_id:
                logger.error(f"No key found for security level {security_level.value}")
                return {
                    "encrypted": False,
                    "data": data,
                    "error": "No encryption key available"
                }
            
            key = self.encryption_keys[key_id]
            
            # Encrypt data
            if algorithm == EncryptionAlgorithm.FERNET and CRYPTOGRAPHY_AVAILABLE:
                fernet = Fernet(key.key_data)
                encrypted_data = fernet.encrypt(data)
                metadata = {}
            else:
                # Mock encryption for other algorithms
                # In production, would use actual encryption
                encrypted_data = self._mock_encrypt(data, key.key_data)
                metadata = {"mock": True}
            
            self.metrics.encryption_operations += 1
            
            result = {
                "encrypted": True,
                "data": base64.b64encode(encrypted_data).decode(),
                "algorithm": algorithm.value,
                "key_id": key_id,
                "key_version": key.key_version,
                "security_level": security_level.value,
                "metadata": metadata,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error encrypting data: {str(e)}")
            return {
                "encrypted": False,
                "data": data,
                "error": str(e)
            }
    
    def decrypt_data(self, encrypted_data: Dict[str, Any]) -> Optional[bytes]:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Dictionary with encrypted data and metadata
            
        Returns:
            Decrypted data or None if failed
        """
        if not encrypted_data.get("encrypted", False):
            # Data is not encrypted
            data = encrypted_data.get("data")
            if isinstance(data, str):
                return data.encode()
            elif isinstance(data, bytes):
                return data
            else:
                return None
        
        try:
            # Extract metadata
            algorithm_str = encrypted_data.get("algorithm")
            key_id = encrypted_data.get("key_id")
            encoded_data = encrypted_data.get("data")
            
            if not algorithm_str or not key_id or not encoded_data:
                logger.error("Missing encryption metadata")
                return None
            
            algorithm = EncryptionAlgorithm(algorithm_str)
            
            # Get key
            if key_id not in self.encryption_keys:
                logger.error(f"Encryption key {key_id} not found")
                return None
            
            key = self.encryption_keys[key_id]
            
            # Check if key is revoked
            if key.revoked:
                logger.error(f"Encryption key {key_id} is revoked")
                return None
            
            # Decode data
            encrypted_bytes = base64.b64decode(encoded_data)
            
            # Decrypt data
            if algorithm == EncryptionAlgorithm.FERNET and CRYPTOGRAPHY_AVAILABLE:
                fernet = Fernet(key.key_data)
                decrypted_data = fernet.decrypt(encrypted_bytes)
            else:
                # Mock decryption
                decrypted_data = self._mock_decrypt(encrypted_bytes, key.key_data)
            
            self.metrics.decryption_operations += 1
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Error decrypting data: {str(e)}")
            return None
    
    def create_session(self, user_id: str, client_info: Dict[str, Any]) -> Optional[str]:
        """
        Create a new session for a user.
        
        Args:
            user_id: User ID
            client_info: Client information (IP, user agent, etc.)
            
        Returns:
            Session ID or None if failed
        """
        try:
            # Check if user exists
            if user_id not in self.users:
                logger.error(f"User {user_id} not found")
                return None
            
            # Generate session ID
            session_id = f"session_{uuid.uuid4().hex[:32]}"
            
            # Create session
            session = {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": datetime.now(),
                "last_activity": datetime.now(),
                "expires_at": datetime.now() + timedelta(minutes=self.config.session_timeout_minutes),
                "client_info": client_info,
                "active": True
            }
            
            self.active_sessions[session_id] = session
            self.metrics.active_sessions += 1
            
            # Log session creation
            self._log_audit_event(
                event_type="session_created",
                user_id=user_id,
                action="Create session",
                details={"session_id": session_id},
                ip_address=client_info.get("ip_address")
            )
            
            logger.info(f"Created session {session_id} for user {user_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            return None
    
    def validate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Validate a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data if valid, None otherwise
        """
        try:
            if session_id not in self.active_sessions:
                return None
            
            session = self.active_sessions[session_id]
            
            # Check if session is active
            if not session.get("active", False):
                return None
            
            # Check if session has expired
            if session["expires_at"] < datetime.now():
                # Session expired
                session["active"] = False
                self.active_sessions[session_id] = session
                self.metrics.active_sessions -= 1
                return None
            
            # Update last activity
            session["last_activity"] = datetime.now()
            # Extend expiration
            session["expires_at"] = datetime.now() + timedelta(minutes=self.config.session_timeout_minutes)
            
            self.active_sessions[session_id] = session
            
            return session
            
        except Exception as e:
            logger.error(f"Error validating session: {str(e)}")
            return None
    
    def invalidate_session(self, session_id: str):
        """Invalidate a session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session["active"] = False
            self.active_sessions[session_id] = session
            self.metrics.active_sessions -= 1
            
            # Log session invalidation
            self._log_audit_event(
                event_type="session_invalidated",
                user_id=session.get("user_id"),
                action="Invalidate session",
                details={"session_id": session_id}
            )
            
            logger.info(f"Invalidated session {session_id}")
    
    def _hash_password(self, password: str) -> Tuple[str, str]:
        """Hash a password with salt."""
        # Generate salt
        salt = secrets.token_bytes(self.config.password_salt_length)
        salt_b64 = base64.b64encode(salt).decode()
        
        # Hash password
        if self.config.password_hashing_algorithm == HashAlgorithm.SHA256:
            # Use PBKDF2 with SHA256
            if CRYPTOGRAPHY_AVAILABLE:
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                    backend=default_backend()
                )
                key = kdf.derive(password.encode())
                hash_b64 = base64.b64encode(key).decode()
            else:
                # Fallback: simple hash (not secure for production)
                hash_obj = hashlib.sha256(salt + password.encode())
                hash_b64 = base64.b64encode(hash_obj.digest()).decode()
        
        elif self.config.password_hashing_algorithm == HashAlgorithm.SHA512:
            # Use SHA512
            hash_obj = hashlib.sha512(salt + password.encode())
            hash_b64 = base64.b64encode(hash_obj.digest()).decode()
        
        else:
            # Default to SHA256
            hash_obj = hashlib.sha256(salt + password.encode())
            hash_b64 = base64.b64encode(hash_obj.digest()).decode()
        
        return salt_b64, hash_b64
    
    def _verify_password(self, password: str, stored_hash: str, stored_salt: str) -> bool:
        """Verify a password against stored hash."""
        try:
            # Decode salt
            salt = base64.b64decode(stored_salt)
            
            # Hash the provided password
            if self.config.password_hashing_algorithm == HashAlgorithm.SHA256:
                if CRYPTOGRAPHY_AVAILABLE:
                    kdf = PBKDF2HMAC(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=salt,
                        iterations=100000,
                        backend=default_backend()
                    )
                    try:
                        kdf.verify(password.encode(), base64.b64decode(stored_hash))
                        return True
                    except:
                        return False
                else:
                    # Fallback
                    hash_obj = hashlib.sha256(salt + password.encode())
                    test_hash = base64.b64encode(hash_obj.digest()).decode()
                    return hmac.compare_digest(test_hash, stored_hash)
            
            elif self.config.password_hashing_algorithm == HashAlgorithm.SHA512:
                hash_obj = hashlib.sha512(salt + password.encode())
                test_hash = base64.b64encode(hash_obj.digest()).decode()
                return hmac.compare_digest(test_hash, stored_hash)
            
            else:
                # Default
                hash_obj = hashlib.sha256(salt + password.encode())
                test_hash = base64.b64encode(hash_obj.digest()).decode()
                return hmac.compare_digest(test_hash, stored_hash)
                
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False
    
    def _get_key_for_security_level(self, security_level: SecurityLevel, 
                                   algorithm: EncryptionAlgorithm) -> Optional[str]:
        """Get appropriate encryption key for security level."""
        # Map security levels to key priorities
        security_priority = {
            SecurityLevel.PUBLIC: 1,
            SecurityLevel.INTERNAL: 2,
            SecurityLevel.CONFIDENTIAL: 3,
            SecurityLevel.RESTRICTED: 4,
            SecurityLevel.SECRET: 5
        }
        
        priority = security_priority.get(security_level, 3)
        
        # Find the most appropriate key
        best_key = None
        best_priority = -1
        
        for key_id, key in self.encryption_keys.items():
            if (key.algorithm == algorithm and 
                not key.revoked and 
                (key.expires_at is None or key.expires_at > datetime.now())):
                
                # Simple heuristic: higher security levels should use newer keys
                key_priority = key.key_version * 10 + priority
                
                if key_priority > best_priority:
                    best_priority = key_priority
                    best_key = key_id
        
        return best_key
    
    def _mock_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Mock encryption for testing."""
        # In production, this would use actual encryption
        # For now, just XOR with key (not secure!)
        
        # Repeat key to match data length
        key_repeated = (key * (len(data) // len(key) + 1))[:len(data)]
        
        # XOR encryption
        encrypted = bytes(a ^ b for a, b in zip(data, key_repeated))
        
        # Add marker to indicate mock encryption
        marker = b"MOCK_ENC:"
        return marker + encrypted
    
    def _mock_decrypt(self, encrypted_data: bytes, key: bytes) -> bytes:
        """Mock decryption for testing."""
        # Check for mock marker
        marker = b"MOCK_ENC:"
        if encrypted_data.startswith(marker):
            encrypted_data = encrypted_data[len(marker):]
        
        # Repeat key to match data length
        key_repeated = (key * (len(encrypted_data) // len(key) + 1))[:len(encrypted_data)]
        
        # XOR decryption (same as encryption for XOR)
        decrypted = bytes(a ^ b for a, b in zip(encrypted_data, key_repeated))
        
        return decrypted
    
    def _log_audit_event(self, event_type: str, action: str, 
                        details: Dict[str, Any], user_id: Optional[str] = None,
                        resource_id: Optional[str] = None, ip_address: Optional[str] = None,
                        user_agent: Optional[str] = None, success: bool = True,
                        error_message: Optional[str] = None):
        """Log an audit event."""
        if not self.config.audit_log_enabled:
            return
        
        try:
            log_entry = AuditLogEntry(
                log_id=f"audit_{uuid.uuid4().hex[:16]}",
                event_type=event_type,
                user_id=user_id,
                resource_id=resource_id,
                action=action,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                error_message=error_message
            )
            
            self.audit_log.append(log_entry)
            self.metrics.audit_entries += 1
            
            # Trim old audit logs
            self._trim_audit_logs()
            
        except Exception as e:
            logger.error(f"Error logging audit event: {str(e)}")
    
    def _trim_audit_logs(self):
        """Trim audit logs older than retention period."""
        if not self.config.audit_log_enabled:
            return
        
        retention_cutoff = datetime.now() - timedelta(days=self.config.audit_retention_days)
        
        # Keep only logs newer than cutoff
        self.audit_log = [
            log for log in self.audit_log 
            if log.created_at > retention_cutoff
        ]
    
    def get_audit_logs(self, start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None,
                      event_type: Optional[str] = None,
                      user_id: Optional[str] = None) -> List[AuditLogEntry]:
        """
        Get audit logs with optional filters.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            event_type: Event type filter
            user_id: User ID filter
            
        Returns:
            Filtered audit logs
        """
        filtered_logs = self.audit_log
        
        # Apply filters
        if start_date:
            filtered_logs = [log for log in filtered_logs if log.created_at >= start_date]
        
        if end_date:
            filtered_logs = [log for log in filtered_logs if log.created_at <= end_date]
        
        if event_type:
            filtered_logs = [log for log in filtered_logs if log.event_type == event_type]
        
        if user_id:
            filtered_logs = [log for log in filtered_logs if log.user_id == user_id]
        
        # Sort by date (newest first)
        filtered_logs.sort(key=lambda x: x.created_at, reverse=True)
        
        return filtered_logs
    
    def export_audit_logs(self, format: str = "json") -> Dict[str, Any]:
        """
        Export audit logs.
        
        Args:
            format: Export format
            
        Returns:
            Export data
        """
        export_data = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "log_count": len(self.audit_log),
                "format": format,
                "retention_days": self.config.audit_retention_days
            },
            "logs": []
        }
        
        for log in self.audit_log:
            log_dict = {
                "log_id": log.log_id,
                "event_type": log.event_type,
                "user_id": log.user_id,
                "resource_id": log.resource_id,
                "action": log.action,
                "details": log.details,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "success": log.success,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat()
            }
            export_data["logs"].append(log_dict)
        
        return export_data
    
    def rotate_encryption_keys(self):
        """Rotate encryption keys based on configuration."""
        if not self.config.encryption_enabled:
            return
        
        now = datetime.now()
        rotated_count = 0
        
        for key_id, key in list(self.encryption_keys.items()):
            # Check if key needs rotation
            if (key.expires_at and key.expires_at <= now and not key.revoked):
                # Create new key version
                new_key_id = f"{key_id.rsplit('_v', 1)[0]}_v{key.key_version + 1}"
                
                # Generate new key
                if key.algorithm == EncryptionAlgorithm.FERNET and CRYPTOGRAPHY_AVAILABLE:
                    new_key_data = Fernet.generate_key()
                else:
                    new_key_data = secrets.token_bytes(32)
                
                # Set expiration
                new_expires_at = now + timedelta(days=self.config.key_rotation_days)
                
                new_key = EncryptionKey(
                    key_id=new_key_id,
                    algorithm=key.algorithm,
                    key_data=new_key_data,
                    key_version=key.key_version + 1,
                    expires_at=new_expires_at
                )
                
                # Mark old key as revoked
                key.revoked = True
                key.revoked_at = now
                self.encryption_keys[key_id] = key
                
                # Add new key
                self.encryption_keys[new_key_id] = new_key
                rotated_count += 1
                
                # Log key rotation
                self._log_audit_event(
                    event_type="key_rotated",
                    action="Rotate encryption key",
                    details={
                        "old_key_id": key_id,
                        "new_key_id": new_key_id,
                        "algorithm": key.algorithm.value,
                        "reason": "Scheduled rotation"
                    }
                )
        
        if rotated_count > 0:
            logger.info(f"Rotated {rotated_count} encryption keys")
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        now = datetime.now()
        cleaned_count = 0
        
        for session_id, session in list(self.active_sessions.items()):
            if not session.get("active", False) or session["expires_at"] < now:
                del self.active_sessions[session_id]
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.metrics.active_sessions = len(self.active_sessions)
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
    
    def get_security_metrics(self) -> SecurityMetrics:
        """Get current security metrics."""
        self.metrics.calculated_at = datetime.now()
        return self.metrics
    
    def get_framework_status(self) -> Dict[str, Any]:
        """Get security framework status."""
        # Calculate key status
        key_status = {
            "total_keys": len(self.encryption_keys),
            "active_keys": sum(1 for k in self.encryption_keys.values() if not k.revoked),
            "expired_keys": sum(1 for k in self.encryption_keys.values() if k.expires_at and k.expires_at < datetime.now()),
            "revoked_keys": sum(1 for k in self.encryption_keys.values() if k.revoked)
        }
        
        # Calculate user status
        locked_users = sum(1 for u in self.users.values() if u.account_locked_until and u.account_locked_until > datetime.now())
        
        return {
            "config": {
                "encryption_enabled": self.config.encryption_enabled,
                "audit_log_enabled": self.config.audit_log_enabled,
                "key_rotation_days": self.config.key_rotation_days,
                "session_timeout_minutes": self.config.session_timeout_minutes
            },
            "status": {
                "users": {
                    "total": len(self.users),
                    "locked": locked_users,
                    "with_mfa": sum(1 for u in self.users.values() if u.mfa_enabled)
                },
                "roles": len(self.roles),
                "active_sessions": len(self.active_sessions),
                "encryption_keys": key_status,
                "audit_log_size": len(self.audit_log)
            },
            "metrics": self.get_security_metrics(),
            "timestamp": datetime.now().isoformat()
        }
    
    def run_maintenance(self):
        """Run security maintenance tasks."""
        logger.info("Running security maintenance...")
        
        # Rotate encryption keys
        self.rotate_encryption_keys()
        
        # Clean up expired sessions
        self.cleanup_expired_sessions()
        
        # Trim audit logs
        self._trim_audit_logs()
        
        logger.info("Security maintenance completed")


def test_security_framework():
    """Test function for Security Framework."""
    print("Testing Security & Confidentiality Framework...")
    
    # Create security framework
    framework = SecurityFramework()
    
    # Test 1: Get framework status
    print("\n1. Testing framework status...")
    
    status = framework.get_framework_status()
    print(f"Security framework status:")
    print(f"  Users: {status['status']['users']['total']}")
    print(f"  Roles: {status['status']['roles']}")
    print(f"  Active sessions: {status['status']['active_sessions']}")
    print(f"  Encryption keys: {status['status']['encryption_keys']['active_keys']} active")
    
    # Test 2: User authentication
    print("\n2. Testing user authentication...")
    
    # Try to authenticate with wrong password
    user = framework.authenticate_user("admin", "WrongPassword")
    print(f"Wrong password authentication: {'Failed' if user is None else 'Unexpected success'}")
    
    # Authenticate with correct password (default is "ChangeMe123!")
    user = framework.authenticate_user("admin", "ChangeMe123!")
    if user:
        print(f"Correct password authentication: Success as {user.username}")
        print(f"  User ID: {user.user_id}")
        print(f"  Roles: {user.roles}")
        print(f"  Security level: {user.security_level.value}")
    else:
        print("Correct password authentication: Failed")
    
    # Test 3: Permission checking
    print("\n3. Testing permission checking...")
    
    if user:
        # Check permissions
        can_read_cases = framework.check_permission(user.user_id, "cases", AccessLevel.READ)
        can_write_cases = framework.check_permission(user.user_id, "cases", AccessLevel.WRITE)
        can_admin = framework.check_permission(user.user_id, "*", AccessLevel.ADMIN)
        
        print(f"Permission check results for {user.username}:")
        print(f"  Can read cases: {can_read_cases}")
        print(f"  Can write cases: {can_write_cases}")
        print(f"  Has admin access: {can_admin}")
    
    # Test 4: Session management
    print("\n4. Testing session management...")
    
    if user:
        # Create session
        client_info = {
            "ip_address": "192.168.1.100",
            "user_agent": "Test Client/1.0",
            "device": "test"
        }
        
        session_id = framework.create_session(user.user_id, client_info)
        if session_id:
            print(f"Created session: {session_id}")
            
            # Validate session
            session = framework.validate_session(session_id)
            if session:
                print(f"Session validated: User {session['user_id']}, Expires at {session['expires_at']}")
            
            # Invalidate session
            framework.invalidate_session(session_id)
            print("Session invalidated")
    
    # Test 5: Data encryption
    print("\n5. Testing data encryption...")
    
    test_data = b"This is sensitive legal data that needs protection."
    
    # Encrypt data
    encrypted_result = framework.encrypt_data(
        test_data, 
        security_level=SecurityLevel.CONFIDENTIAL
    )
    
    print(f"Encryption result: {'Success' if encrypted_result.get('encrypted') else 'Failed'}")
    if encrypted_result.get("encrypted"):
        print(f"  Algorithm: {encrypted_result.get('algorithm')}")
        print(f"  Security level: {encrypted_result.get('security_level')}")
        print(f"  Key ID: {encrypted_result.get('key_id')}")
        
        # Decrypt data
        decrypted_data = framework.decrypt_data(encrypted_result)
        if decrypted_data:
            print(f"Decryption successful: {decrypted_data.decode()}")
        else:
            print("Decryption failed")
    
    # Test 6: Audit logging
    print("\n6. Testing audit logging...")
    
    # Get recent audit logs
    audit_logs = framework.get_audit_logs()
    print(f"Audit log entries: {len(audit_logs)}")
    
    if audit_logs:
        print(f"Recent audit events:")
        for log in audit_logs[:3]:  # Show first 3
            print(f"  {log.event_type}: {log.action} ({'Success' if log.success else 'Failed'})")
    
    # Test 7: Run maintenance
    print("\n7. Testing maintenance...")
    
    framework.run_maintenance()
    print("Maintenance completed")
    
    # Test 8: Get final metrics
    print("\n8. Testing final metrics...")
    
    metrics = framework.get_security_metrics()
    print(f"Security metrics:")
    print(f"  Total users: {metrics.total_users}")
    print(f"  Successful logins: {metrics.successful_logins}")
    print(f"  Failed logins: {metrics.failed_logins}")
    print(f"  Encryption operations: {metrics.encryption_operations}")
    print(f"  Decryption operations: {metrics.decryption_operations}")
    print(f"  Access denied: {metrics.access_denied}")
    print(f"  Audit entries: {metrics.audit_entries}")
    
    print("\nSecurity & Confidentiality Framework test completed successfully!")


if __name__ == "__main__":
    test_security_framework()