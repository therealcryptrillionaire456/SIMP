"""
T42: HashiCorp Vault Integration for Secrets Management
====================================================
API keys, private keys, and secrets should never be in .env.

This module provides:
1. Vault client for secret retrieval
2. Secrets inventory tracking
3. Automatic secrets rotation
4. Emergency revocation

Usage:
    vault = VaultClient()
    api_key = vault.get_secret("coinbase/api_key")
    vault.rotate_secret("coinbase/api_key")
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("vault_client")

# ── Constants ───────────────────────────────────────────────────────────

VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN", "")
SECRETS_INVENTORY_PATH = Path("config/secrets_inventory.json")
SECRETS_LOG_PATH = Path("data/secrets_access_log.jsonl")


@dataclass
class SecretMetadata:
    """Metadata for a tracked secret."""
    name: str
    path: str  # Vault path
    owner: str
    created_at: str
    last_rotated: str
    rotation_interval_days: int = 90
    last_accessed: str = ""
    access_count: int = 0
    is_critical: bool = False

    def needs_rotation(self) -> bool:
        """Check if this secret needs rotation."""
        if not self.last_rotated:
            return True
        try:
            last = datetime.fromisoformat(self.last_rotated)
            age_days = (datetime.now(timezone.utc) - last).days
            return age_days >= self.rotation_interval_days
        except (ValueError, TypeError):
            return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "owner": self.owner,
            "created_at": self.created_at,
            "last_rotated": self.last_rotated,
            "rotation_interval_days": self.rotation_interval_days,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "is_critical": self.is_critical,
        }


class VaultClient:
    """
    HashiCorp Vault client for secrets management.
    
    Thread-safe. Provides secret retrieval, rotation, and audit logging.
    """

    def __init__(
        self,
        vault_addr: str = VAULT_ADDR,
        vault_token: str = VAULT_TOKEN,
        inventory_path: str = str(SECRETS_INVENTORY_PATH),
        cache_seconds: int = 60,
    ):
        self._lock = threading.Lock()
        self.vault_addr = vault_addr
        self.vault_token = vault_token
        self.inventory_path = Path(inventory_path)
        self.cache_seconds = cache_seconds
        self._cache: Dict[str, tuple[float, str]] = {}  # (timestamp, value)
        self._inventory: Dict[str, SecretMetadata] = {}
        self._connected = False
        
        # Try to connect to Vault
        self._connect()
        
        # Load inventory
        self._load_inventory()

    def _connect(self) -> bool:
        """Try to connect to Vault."""
        if not self.vault_token:
            log.warning("VAULT_TOKEN not set - running in mock mode")
            return False
        
        try:
            import hvac  # type: ignore
            self._hvac = hvac.Client(url=self.vault_addr, token=self.vault_token)
            self._connected = self._hvac.is_authenticated()
            if self._connected:
                log.info(f"Connected to Vault at {self.vault_addr}")
            return self._connected
        except ImportError:
            log.warning("hvac not installed - running in mock mode")
            return False
        except Exception as e:
            log.warning(f"Failed to connect to Vault: {e}")
            return False

    def _load_inventory(self) -> None:
        """Load secrets inventory from disk."""
        try:
            if self.inventory_path.exists():
                with open(self.inventory_path) as f:
                    data = json.load(f)
                    self._inventory = {
                        k: SecretMetadata(**v) for k, v in data.items()
                    }
                log.info(f"Loaded {len(self._inventory)} secrets from inventory")
            else:
                self._create_default_inventory()
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"Failed to load inventory: {e}")
            self._create_default_inventory()

    def _create_default_inventory(self) -> None:
        """Create default inventory for known secrets."""
        now = datetime.now(timezone.utc).isoformat()
        self._inventory = {
            "coinbase_api_key": SecretMetadata(
                name="coinbase_api_key",
                path="secret/data/coinbase/api_key",
                owner="system",
                created_at=now,
                last_rotated=now,
                is_critical=True,
            ),
            "coinbase_secret": SecretMetadata(
                name="coinbase_secret",
                path="secret/data/coinbase/secret",
                owner="system",
                created_at=now,
                last_rotated=now,
                is_critical=True,
            ),
            "telegram_bot_token": SecretMetadata(
                name="telegram_bot_token",
                path="secret/data/telegram/bot_token",
                owner="ops",
                created_at=now,
                last_rotated=now,
                rotation_interval_days=180,
                is_critical=True,
            ),
            "database_password": SecretMetadata(
                name="database_password",
                path="secret/data/database/password",
                owner="dba",
                created_at=now,
                last_rotated=now,
                is_critical=True,
            ),
        }
        self._save_inventory()

    def _save_inventory(self) -> None:
        """Persist inventory to disk."""
        try:
            self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.inventory_path, "w") as f:
                json.dump({
                    k: v.to_dict() for k, v in self._inventory.items()
                }, f, indent=2)
        except OSError as e:
            log.error(f"Failed to save inventory: {e}")

    def _log_access(self, secret_name: str, action: str) -> None:
        """Log secret access for audit trail."""
        try:
            SECRETS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SECRETS_LOG_PATH, "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "secret_name": secret_name,
                    "action": action,
                    "accessed_by": os.environ.get("USER", "unknown"),
                }) + "\n")
        except OSError:
            pass

    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret from Vault.
        
        Args:
            secret_name: Name of the secret (must be in inventory)
            default: Default value if not found (for development)
            
        Returns:
            The secret value or default
        """
        # Check cache first
        with self._lock:
            if secret_name in self._cache:
                ts, value = self._cache[secret_name]
                if time.time() - ts < self.cache_seconds:
                    return value
            
            # Check inventory
            if secret_name not in self._inventory:
                log.warning(f"Secret {secret_name} not in inventory")
                self._log_access(secret_name, "access_denied")
                return default
            
            meta = self._inventory[secret_name]
            
            # Try to get from Vault
            if self._connected:
                try:
                    response = self._hvac.secrets.kv.v2.read_secret_version(
                        path=meta.path.split("/")[-1],
                        mount_point="/".join(meta.path.split("/")[:-2]) if "/" in meta.path else "secret",
                    )
                    value = response["data"]["data"].get("value", default)
                    
                    # Update cache and metadata
                    self._cache[secret_name] = (time.time(), value)
                    meta.last_accessed = datetime.now(timezone.utc).isoformat()
                    meta.access_count += 1
                    self._log_access(secret_name, "accessed")
                    
                    return value
                except Exception as e:
                    log.error(f"Failed to get {secret_name} from Vault: {e}")
            
            # Fallback to environment or default
            env_key = secret_name.upper().replace("/", "_").replace("-", "_")
            value = os.environ.get(env_key, default)
            
            self._cache[secret_name] = (time.time(), value)
            meta.last_accessed = datetime.now(timezone.utc).isoformat()
            meta.access_count += 1
            self._log_access(secret_name, "accessed_fallback")
            
            return value

    def set_secret(self, secret_name: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set a secret in Vault.
        
        Args:
            secret_name: Name of the secret
            value: Secret value
            metadata: Optional metadata
            
        Returns:
            True if successful
        """
        if secret_name not in self._inventory:
            # Add to inventory
            self._inventory[secret_name] = SecretMetadata(
                name=secret_name,
                path=f"secret/data/{secret_name}",
                owner="system",
                created_at=datetime.now(timezone.utc).isoformat(),
                last_rotated=datetime.now(timezone.utc).isoformat(),
            )
        
        if self._connected:
            try:
                meta = self._inventory[secret_name]
                mount_point, path = meta.path.split("/data/") if "/data/" in meta.path else ("secret", meta.path)
                self._hvac.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret={"value": value, **(metadata or {})},
                    mount_point=mount_point,
                )
                self._log_access(secret_name, "set")
                log.info(f"Set secret {secret_name} in Vault")
                return True
            except Exception as e:
                log.error(f"Failed to set {secret_name} in Vault: {e}")
                return False
        
        # Fallback: set in environment (dev only)
        os.environ[secret_name.upper()] = value
        self._log_access(secret_name, "set_fallback")
        log.warning(f"Set {secret_name} in environment (dev fallback)")
        return True

    def rotate_secret(self, secret_name: str, new_value: Optional[str] = None) -> bool:
        """
        Rotate a secret.
        
        Args:
            secret_name: Name of the secret to rotate
            new_value: New value (generated if not provided)
            
        Returns:
            True if successful
        """
        if new_value is None:
            import secrets
            new_value = secrets.token_urlsafe(32)
        
        success = self.set_secret(secret_name, new_value)
        
        if success:
            with self._lock:
                if secret_name in self._inventory:
                    self._inventory[secret_name].last_rotated = datetime.now(timezone.utc).isoformat()
                    self._save_inventory()
            self._log_access(secret_name, "rotated")
            log.info(f"Rotated secret {secret_name}")
            
            # Clear cache
            with self._lock:
                if secret_name in self._cache:
                    del self._cache[secret_name]
        
        return success

    def revoke_secret(self, secret_name: str) -> bool:
        """
        Revoke a secret immediately.
        
        Args:
            secret_name: Name of the secret to revoke
            
        Returns:
            True if successful
        """
        if self._connected:
            try:
                meta = self._inventory[secret_name]
                mount_point, path = meta.path.split("/data/") if "/data/" in meta.path else ("secret", meta.path)
                self._hvac.secrets.kv.v2.delete_metadata_and_all_versions(path=path, mount_point=mount_point)
                self._log_access(secret_name, "revoked")
                log.critical(f"Revoked secret {secret_name}")
                return True
            except Exception as e:
                log.error(f"Failed to revoke {secret_name}: {e}")
                return False
        
        # Fallback: remove from environment
        env_key = secret_name.upper().replace("/", "_").replace("-", "_")
        if env_key in os.environ:
            del os.environ[env_key]
        self._log_access(secret_name, "revoked_fallback")
        log.critical(f"Revoked {secret_name} from environment")
        return True

    def get_inventory(self) -> List[SecretMetadata]:
        """Get all tracked secrets."""
        return list(self._inventory.values())

    def get_rotation_report(self) -> Dict[str, Any]:
        """Get secrets that need rotation."""
        needs_rotation = []
        critical_expiring = []
        
        for name, meta in self._inventory.items():
            if meta.needs_rotation():
                needs_rotation.append(meta.to_dict())
                if meta.is_critical:
                    critical_expiring.append(meta.to_dict())
        
        return {
            "total_secrets": len(self._inventory),
            "needs_rotation": len(needs_rotation),
            "critical_needing_rotation": len(critical_expiring),
            "secrets": needs_rotation,
            "critical": critical_expiring,
        }


# ── Module-level singleton ──────────────────────────────────────────────

_vault_client: Optional[VaultClient] = None


def get_vault_client(**kwargs) -> VaultClient:
    """Get or create the global VaultClient singleton."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient(**kwargs)
    return _vault_client


# ── Demo / Test ─────────────────────────────────────────────────────────

def demo_vault_client():
    """Demonstrate the vault client."""
    print("=" * 60)
    print("T42 — Vault Client Demo")
    print("=" * 60)

    vault = VaultClient()

    print("\n[1] Secrets inventory:")
    inventory = vault.get_inventory()
    for secret in inventory[:5]:
        print(f"    {secret.name}: critical={secret.is_critical}, needs_rotation={secret.needs_rotation()}")

    print("\n[2] Rotation report:")
    report = vault.get_rotation_report()
    print(f"    Total secrets: {report['total_secrets']}")
    print(f"    Needs rotation: {report['needs_rotation']}")
    print(f"    Critical expiring: {report['critical_needing_rotation']}")

    print("\n[3] Secret access (fallback mode):")
    # In dev mode, this returns None or env var
    secret = vault.get_secret("coinbase_api_key")
    print(f"    coinbase_api_key: {'***' if secret else 'None'}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_vault_client()
