"""
Mesh Security Layer for SIMP Ecosystem
Features:
- End-to-end message encryption
- Digital signatures for message integrity
- Access control lists
- Audit logging
- Key management
"""

import json
import logging
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import base64
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security levels for messages."""
    NONE = "none"  # No encryption/signing
    SIGNED = "signed"  # Signed but not encrypted
    ENCRYPTED = "encrypted"  # Encrypted and signed
    CONFIDENTIAL = "confidential"  # High-security encryption


class AccessPermission(Enum):
    """Access permissions for agents."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    NONE = "none"


@dataclass
class SecurityPolicy:
    """Security policy for an agent or channel."""
    agent_id: str
    channel: Optional[str] = None  # None = global policy
    security_level: SecurityLevel = SecurityLevel.SIGNED
    allowed_senders: Set[str] = field(default_factory=set)
    allowed_recipients: Set[str] = field(default_factory=set)
    require_encryption: bool = False
    require_signature: bool = True
    max_message_size: int = 1024 * 1024  # 1MB
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "channel": self.channel,
            "security_level": self.security_level.value,
            "allowed_senders": list(self.allowed_senders),
            "allowed_recipients": list(self.allowed_recipients),
            "require_encryption": self.require_encryption,
            "require_signature": self.require_signature,
            "max_message_size": self.max_message_size,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "updated_at": datetime.fromtimestamp(self.updated_at).isoformat(),
        }
    
    def can_send(self, sender_id: str, recipient_id: str) -> bool:
        """Check if sender can send to recipient."""
        if self.channel:
            # Channel policy: check if sender is allowed
            return sender_id in self.allowed_senders
        else:
            # Agent policy: check if sender can send to this specific recipient
            return sender_id in self.allowed_senders and recipient_id in self.allowed_recipients
    
    def update(self, **kwargs):
        """Update policy fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = time.time()


class MeshSecurityLayer:
    """
    Security layer for mesh communications.
    """
    
    def __init__(
        self,
        agent_id: str,
        private_key_path: Optional[str] = None,
        public_key_path: Optional[str] = None,
        shared_secret: Optional[str] = None,
        enable_encryption: bool = True,
        enable_signing: bool = True,
        audit_log_path: Optional[str] = None,
    ):
        """
        Initialize mesh security layer.
        
        Args:
            agent_id: Local agent ID
            private_key_path: Path to private key file
            public_key_path: Path to public key file
            shared_secret: Shared secret for symmetric encryption
            enable_encryption: Whether to enable encryption
            enable_signing: Whether to enable signing
            audit_log_path: Path for audit logs
        """
        self.agent_id = agent_id
        self.enable_encryption = enable_encryption
        self.enable_signing = enable_signing
        
        # Key management
        self._private_key: Optional[rsa.RSAPrivateKey] = None
        self._public_key: Optional[rsa.RSAPublicKey] = None
        self._shared_secret = shared_secret or self._generate_shared_secret()
        self._fernet: Optional[Fernet] = None
        
        # Load or generate keys
        self._load_or_generate_keys(private_key_path, public_key_path)
        
        # Policy management
        self._policies: Dict[str, SecurityPolicy] = {}  # key -> policy
        self._agent_public_keys: Dict[str, str] = {}  # agent_id -> public_key_pem
        
        # Audit logging
        self.audit_log_path = audit_log_path or f"logs/mesh_security_{agent_id}.jsonl"
        self._setup_audit_logging()
        
        # Statistics
        self._stats = {
            "messages_encrypted": 0,
            "messages_decrypted": 0,
            "messages_signed": 0,
            "signatures_verified": 0,
            "security_violations": 0,
            "access_denied": 0,
            "key_exchanges": 0,
        }
        
        # Create default policy for this agent
        self._create_default_policy()
        
        logger.info(f"Mesh Security Layer initialized for {agent_id}")
    
    def _generate_shared_secret(self) -> str:
        """Generate a shared secret for symmetric encryption."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')
    
    def _load_or_generate_keys(self, private_key_path: Optional[str], public_key_path: Optional[str]):
        """Load existing keys or generate new ones."""
        try:
            if private_key_path and public_key_path:
                # Load existing keys
                with open(private_key_path, 'rb') as f:
                    self._private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )
                
                with open(public_key_path, 'rb') as f:
                    self._public_key = serialization.load_pem_public_key(
                        f.read(),
                        backend=default_backend()
                    )
                
                logger.info(f"Loaded keys from {private_key_path}, {public_key_path}")
            else:
                # Generate new keys
                self._private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                    backend=default_backend()
                )
                self._public_key = self._private_key.public_key()
                
                # Save keys if paths provided
                if private_key_path:
                    private_pem = self._private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                    with open(private_key_path, 'wb') as f:
                        f.write(private_pem)
                
                if public_key_path:
                    public_pem = self._public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    with open(public_key_path, 'wb') as f:
                        f.write(public_pem)
                
                logger.info("Generated new RSA key pair")
        
        except Exception as e:
            logger.error(f"Failed to load/generate keys: {e}")
            raise
    
    def _setup_audit_logging(self):
        """Setup audit logging directory."""
        import pathlib
        log_path = pathlib.Path(self.audit_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _create_default_policy(self):
        """Create default security policy for this agent."""
        default_policy = SecurityPolicy(
            agent_id=self.agent_id,
            security_level=SecurityLevel.SIGNED,
            allowed_senders={self.agent_id},
            allowed_recipients={self.agent_id},
            require_encryption=False,
            require_signature=True,
        )
        
        self._policies[f"agent:{self.agent_id}"] = default_policy
        logger.debug(f"Created default policy for {self.agent_id}")
    
    def _log_audit_event(
        self,
        event_type: str,
        message_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        channel: Optional[str] = None,
        action: str = "",
        success: bool = True,
        details: Optional[Dict] = None,
    ):
        """Log security audit event."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "agent_id": self.agent_id,
            "message_id": message_id,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "channel": channel,
            "action": action,
            "success": success,
            "details": details or {},
        }
        
        try:
            with open(self.audit_log_path, 'a') as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_public_key_pem(self) -> str:
        """Get public key in PEM format."""
        if not self._public_key:
            raise ValueError("Public key not available")
        
        public_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return public_pem.decode('utf-8')
    
    def register_agent_public_key(self, agent_id: str, public_key_pem: str):
        """Register another agent's public key."""
        try:
            # Validate and load the public key
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=default_backend()
            )
            
            self._agent_public_keys[agent_id] = public_key_pem
            self._stats["key_exchanges"] += 1
            
            self._log_audit_event(
                event_type="key_registered",
                sender_id=agent_id,
                action="public_key_registered",
                success=True,
                details={"key_length": public_key.key_size if hasattr(public_key, 'key_size') else 'unknown'},
            )
            
            logger.info(f"Registered public key for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to register public key for {agent_id}: {e}")
            self._log_audit_event(
                event_type="key_registration_failed",
                sender_id=agent_id,
                action="public_key_registration",
                success=False,
                details={"error": str(e)},
            )
    
    def create_policy(
        self,
        agent_id: str,
        channel: Optional[str] = None,
        security_level: SecurityLevel = SecurityLevel.SIGNED,
        allowed_senders: Optional[List[str]] = None,
        allowed_recipients: Optional[List[str]] = None,
        require_encryption: bool = False,
        require_signature: bool = True,
    ) -> str:
        """
        Create a security policy.
        
        Returns:
            Policy key
        """
        policy_key = f"channel:{channel}" if channel else f"agent:{agent_id}"
        
        policy = SecurityPolicy(
            agent_id=agent_id,
            channel=channel,
            security_level=security_level,
            allowed_senders=set(allowed_senders or [agent_id]),
            allowed_recipients=set(allowed_recipients or [agent_id]),
            require_encryption=require_encryption,
            require_signature=require_signature,
        )
        
        self._policies[policy_key] = policy
        
        self._log_audit_event(
            event_type="policy_created",
            sender_id=agent_id,
            channel=channel,
            action="create_policy",
            success=True,
            details=policy.to_dict(),
        )
        
        logger.info(f"Created security policy {policy_key}")
        return policy_key
    
    def get_policy(self, agent_id: str, channel: Optional[str] = None) -> Optional[SecurityPolicy]:
        """Get security policy for agent/channel."""
        policy_key = f"channel:{channel}" if channel else f"agent:{agent_id}"
        return self._policies.get(policy_key)
    
    def update_policy(self, policy_key: str, **kwargs) -> bool:
        """Update security policy."""
        if policy_key not in self._policies:
            return False
        
        policy = self._policies[policy_key]
        policy.update(**kwargs)
        
        self._log_audit_event(
            event_type="policy_updated",
            sender_id=policy.agent_id,
            channel=policy.channel,
            action="update_policy",
            success=True,
            details=policy.to_dict(),
        )
        
        logger.info(f"Updated security policy {policy_key}")
        return True
    
    def _get_fernet(self) -> Fernet:
        """Get or create Fernet instance for symmetric encryption."""
        if self._fernet is None:
            # Derive key from shared secret
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"mesh_security_salt",
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(self._shared_secret.encode()))
            self._fernet = Fernet(key)
        
        return self._fernet
    
    def encrypt_message(self, plaintext: str, recipient_id: Optional[str] = None) -> str:
        """
        Encrypt a message.
        
        Args:
            plaintext: Message to encrypt
            recipient_id: Recipient agent ID (for asymmetric encryption)
            
        Returns:
            Encrypted message as base64 string
        """
        if not self.enable_encryption:
            return plaintext
        
        try:
            if recipient_id and recipient_id in self._agent_public_keys:
                # Asymmetric encryption with recipient's public key
                public_key_pem = self._agent_public_keys[recipient_id]
                public_key = serialization.load_pem_public_key(
                    public_key_pem.encode('utf-8'),
                    backend=default_backend()
                )
                
                encrypted = public_key.encrypt(
                    plaintext.encode('utf-8'),
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                result = base64.urlsafe_b64encode(encrypted).decode('utf-8')
                
            else:
                # Symmetric encryption with shared secret
                fernet = self._get_fernet()
                encrypted = fernet.encrypt(plaintext.encode('utf-8'))
                result = encrypted.decode('utf-8')  # Fernet already returns URL-safe base64
            
            self._stats["messages_encrypted"] += 1
            return result
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt_message(self, ciphertext: str, sender_id: Optional[str] = None) -> str:
        """
        Decrypt a message.
        
        Args:
            ciphertext: Encrypted message
            sender_id: Sender agent ID (for asymmetric decryption)
            
        Returns:
            Decrypted plaintext
        """
        if not self.enable_encryption:
            return ciphertext
        
        try:
            if sender_id and self._private_key:
                # Asymmetric decryption with our private key
                encrypted = base64.urlsafe_b64decode(ciphertext)
                decrypted = self._private_key.decrypt(
                    encrypted,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                result = decrypted.decode('utf-8')
                
            else:
                # Symmetric decryption with shared secret
                fernet = self._get_fernet()
                decrypted = fernet.decrypt(ciphertext.encode('utf-8'))
                result = decrypted.decode('utf-8')
            
            self._stats["messages_decrypted"] += 1
            return result
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def sign_message(self, message: str) -> str:
        """
        Sign a message with our private key.
        
        Returns:
            Signature as base64 string
        """
        if not self.enable_signing or not self._private_key:
            return ""
        
        try:
            # Create signature
            signature = self._private_key.sign(
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            self._stats["messages_signed"] += 1
            return base64.urlsafe_b64encode(signature).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Signing failed: {e}")
            raise
    
    def verify_signature(
        self,
        message: str,
        signature: str,
        sender_id: str
    ) -> bool:
        """
        Verify a message signature.
        
        Args:
            message: Original message
            signature: Signature to verify
            sender_id: Sender agent ID
            
        Returns:
            True if signature is valid
        """
        if not self.enable_signing:
            return True
        
        if not signature:
            logger.warning(f"No signature provided for message from {sender_id}")
            return False
        
        if sender_id not in self._agent_public_keys:
            logger.warning(f"No public key registered for {sender_id}")
            return False
        
        try:
            # Load sender's public key
            public_key_pem = self._agent_public_keys[sender_id]
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=default_backend()
            )
            
            # Verify signature
            signature_bytes = base64.urlsafe_b64decode(signature)
            public_key.verify(
                signature_bytes,
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            self._stats["signatures_verified"] += 1
            return True
            
        except InvalidSignature:
            logger.warning(f"Invalid signature from {sender_id}")
            self._stats["security_violations"] += 1
            return False
        except Exception as e:
            logger.error(f"Signature verification failed for {sender_id}: {e}")
            return False
    
    def check_access(
        self,
        sender_id: str,
        recipient_id: str,
        channel: Optional[str] = None,
        security_level: SecurityLevel = SecurityLevel.SIGNED,
    ) -> bool:
        """
        Check if sender has access to send to recipient/channel.
        
        Returns:
            True if access is allowed
        """
        # Get applicable policy
        policy = self.get_policy(recipient_id, channel)
        if not policy:
            # No policy = allow by default (for now)
            return True
        
        # Check if sender is allowed
        if not policy.can_send(sender_id, recipient_id):
            logger.warning(f"Access denied: {sender_id} cannot send to {recipient_id}")
            self._stats["access_denied"] += 1
            
            self._log_audit_event(
                event_type="access_denied",
                message_id=None,
                sender_id=sender_id,
                recipient_id=recipient_id,
                channel=channel,
                action="send_message",
                success=False,
                details={
                    "policy": policy.to_dict(),
                    "security_level": security_level.value,
                },
            )
            
            return False
        
        # Check security level requirements
        if policy.require_encryption and security_level.value not in [
            SecurityLevel.ENCRYPTED.value,
            SecurityLevel.CONFIDENTIAL.value,
        ]:
            logger.warning(f"Encryption required but not provided by {sender_id}")
            return False
        
        if policy.require_signature and security_level == SecurityLevel.NONE:
            logger.warning(f"Signature required but not provided by {sender_id}")
            return False
        
        return True
    
    def secure_message(
        self,
        message: Dict[str, Any],
        recipient_id: Optional[str] = None,
        channel: Optional[str] = None,
        security_level: SecurityLevel = SecurityLevel.SIGNED,
    ) -> Dict[str, Any]:
        """
        Apply security to a message.
        
        Returns:
            Secured message dictionary
        """
        secured = message.copy()
        
        # Check access
        sender_id = secured.get("source_agent", self.agent_id)
        if not self.check_access(sender_id, recipient_id or secured.get("target_agent", ""), channel, security_level):
            raise PermissionError(f"Access denied for {sender_id}")
        
        # Apply security based on level
        if security_level == SecurityLevel.NONE:
            # No security
            secured["security_level"] = SecurityLevel.NONE.value
            secured["signature"] = ""
            
        elif security_level == SecurityLevel.SIGNED:
            # Sign the message
            message_str = json.dumps(secured.get("payload", {}), sort_keys=True)
            signature = self.sign_message(message_str)
            
            secured["security_level"] = SecurityLevel.SIGNED.value
            secured["signature"] = signature
            secured["signing_agent"] = self.agent_id
            
        elif security_level in [SecurityLevel.ENCRYPTED, SecurityLevel.CONFIDENTIAL]:
            # Encrypt and sign
            payload = secured.get("payload", {})
            
            # Encrypt payload
            payload_str = json.dumps(payload, sort_keys=True)
            encrypted_payload = self.encrypt_message(payload_str, recipient_id)
            
            # Sign the encrypted payload
            signature = self.sign_message(encrypted_payload)
            
            secured["security_level"] = security_level.value
            secured["payload"] = encrypted_payload
            secured["signature"] = signature
            secured["signing_agent"] = self.agent_id
            secured["encrypted"] = True
        
        # Add security metadata
        secured["security_timestamp"] = time.time()
        secured["security_agent"] = self.agent_id
        
        self._log_audit_event(
            event_type="message_secured",
            message_id=secured.get("message_id"),
            sender_id=sender_id,
            recipient_id=recipient_id,
            channel=channel,
            action="secure_message",
            success=True,
            details={
                "security_level": security_level.value,
                "original_size": len(json.dumps(message)),
                "secured_size": len(json.dumps(secured)),
            },
        )
        
        return secured
    
    def verify_message(self, message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Verify message security.
        
        Returns:
            (is_valid, error_message)
        """
        security_level = message.get("security_level", SecurityLevel.NONE.value)
        sender_id = message.get("source_agent")
        
        if not sender_id:
            return False, "No source_agent in message"
        
        # Check if message is encrypted
        if message.get("encrypted", False):
            try:
                # Decrypt payload
                encrypted_payload = message.get("payload", "")
                if not encrypted_payload:
                    return False, "No payload in encrypted message"
                
                # Verify signature first
                signature = message.get("signature", "")
                if not self.verify_signature(encrypted_payload, signature, sender_id):
                    return False, "Invalid signature"
                
                # Decrypt payload
                decrypted_payload = self.decrypt_message(encrypted_payload, sender_id)
                message["payload"] = json.loads(decrypted_payload)
                message["encrypted"] = False
                
            except Exception as e:
                logger.error(f"Message decryption/verification failed: {e}")
                return False, f"Decryption failed: {str(e)}"
        
        elif security_level == SecurityLevel.SIGNED.value:
            # Verify signature for signed message
            signature = message.get("signature", "")
            if not signature:
                return False, "No signature in signed message"
            
            # Verify signature
            payload_str = json.dumps(message.get("payload", {}), sort_keys=True)
            if not self.verify_signature(payload_str, signature, sender_id):
                return False, "Invalid signature"
        
        # Check if security is still valid (not expired)
        security_timestamp = message.get("security_timestamp")
        if security_timestamp:
            # Messages are valid for 24 hours
            if time.time() - security_timestamp > 86400:
                return False, "Message security expired"
        
        self._log_audit_event(
            event_type="message_verified",
            message_id=message.get("message_id"),
            sender_id=sender_id,
            recipient_id=self.agent_id,
            action="verify_message",
            success=True,
            details={
                "security_level": security_level,
                "verification_time": time.time() - (security_timestamp or time.time()),
            },
        )
        
        return True, None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get security layer statistics."""
        stats = self._stats.copy()
        
        stats.update({
            "agent_id": self.agent_id,
            "policies_count": len(self._policies),
            "registered_public_keys": len(self._agent_public_keys),
            "encryption_enabled": self.enable_encryption,
            "signing_enabled": self.enable_signing,
            "audit_log_path": self.audit_log_path,
        })
        
        return stats
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        try:
            with open(self.audit_log_path, 'r') as f:
                lines = f.readlines()
            
            # Parse last 'limit' lines
            entries = []
            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
            
            return entries
            
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")
            return []


def get_mesh_security_layer(
    agent_id: str,
    private_key_path: Optional[str] = None,
    public_key_path: Optional[str] = None,
) -> MeshSecurityLayer:
    """
    Get or create mesh security layer singleton.
    
    Args:
        agent_id: Local agent ID
        private_key_path: Path to private key file
        public_key_path: Path to public key file
        
    Returns:
        MeshSecurityLayer instance
    """
    if not hasattr(get_mesh_security_layer, "_instances"):
        get_mesh_security_layer._instances = {}
    
    if agent_id not in get_mesh_security_layer._instances:
        get_mesh_security_layer._instances[agent_id] = MeshSecurityLayer(
            agent_id=agent_id,
            private_key_path=private_key_path,
            public_key_path=public_key_path,
        )
    
    return get_mesh_security_layer._instances[agent_id]