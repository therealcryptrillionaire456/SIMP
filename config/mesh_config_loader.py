#!/usr/bin/env python3
"""
Mesh Configuration Loader
Loads and validates mesh configuration from YAML files
"""
import os
import sys
import yaml
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class MeshNetworkConfig:
    """Mesh network configuration"""
    multicast_group: str = "239.255.255.250"
    multicast_port: int = 9999
    ttl: int = 2
    buffer_size: int = 65536
    enable_udp: bool = True
    enable_tcp_fallback: bool = True
    tcp_port: int = 8889
    discovery_interval: int = 30
    heartbeat_interval: int = 10

@dataclass
class MeshSecurityConfig:
    """Mesh security configuration"""
    encryption_enabled: bool = True
    require_authentication: bool = True
    encryption_algorithm: str = "chacha20poly1305"
    key_rotation_interval: int = 86400
    auth_method: str = "shared_secret"
    shared_secret_path: str = "/etc/simp/mesh_secret"
    max_messages_per_second: int = 1000
    max_connections_per_agent: int = 10

@dataclass
class MeshPerformanceConfig:
    """Mesh performance configuration"""
    max_message_size: int = 1048576
    default_ttl_seconds: int = 3600
    default_ttl_hops: int = 10
    
    # Priority queue settings
    priority_queues: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "low": {"max_size": 10000, "timeout_seconds": 86400},
        "normal": {"max_size": 5000, "timeout_seconds": 3600},
        "high": {"max_size": 1000, "timeout_seconds": 300}
    })
    
    # Offline storage
    offline_storage: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "db_path": "/var/lib/simp/mesh_offline.db",
        "max_size_mb": 1024,
        "cleanup_interval": 3600
    })

@dataclass
class MeshMonitoringConfig:
    """Mesh monitoring configuration"""
    enable_metrics: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    health_check_interval: int = 30
    health_check_timeout: int = 5
    
    # Alerting
    alerts: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "high_latency_ms": 1000,
        "high_error_rate": 0.01,
        "low_delivery_rate": 0.99
    })
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "/var/log/simp/mesh.log"
    log_rotation: str = "daily"
    log_retention_days: int = 30

@dataclass
class MeshBridgeConfig:
    """Mesh bridge configuration"""
    enabled: bool = True
    broker_url: str = "http://127.0.0.1:5555"
    forward_to_mesh: bool = True
    forward_to_broker: bool = True
    
    # Intent mapping
    intent_mapping: Dict[str, str] = field(default_factory=lambda: {
        "ping": "heartbeat",
        "analysis_request": "event",
        "trade_execution": "command"
    })
    
    # Performance
    batch_size: int = 100
    batch_timeout: float = 1.0

@dataclass
class MeshConfig:
    """Complete mesh configuration"""
    enabled: bool = True
    mode: str = "hybrid"  # hybrid, mesh-only, http-only
    
    # Sub-configurations
    network: MeshNetworkConfig = field(default_factory=MeshNetworkConfig)
    security: MeshSecurityConfig = field(default_factory=MeshSecurityConfig)
    performance: MeshPerformanceConfig = field(default_factory=MeshPerformanceConfig)
    monitoring: MeshMonitoringConfig = field(default_factory=MeshMonitoringConfig)
    bridge: MeshBridgeConfig = field(default_factory=MeshBridgeConfig)
    
    # Features
    features: Dict[str, Any] = field(default_factory=lambda: {
        "delivery_receipts": {"enabled": True, "timeout": 30.0, "require_receipt": False},
        "compression": {"enabled": True, "algorithm": "zlib", "min_size": 1024},
        "deduplication": {"enabled": True, "window_seconds": 300},
        "gossip": {"enabled": True, "fanout": 3, "interval": 60}
    })
    
    # Agent-specific settings
    agents: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "quantumarb": {
            "mesh_id": "mesh_quantumarb",
            "features": ["basic_messaging", "priority_queues", "payment_channels"],
            "priority": "high"
        },
        "kashclaw_gemma": {
            "mesh_id": "mesh_kashclaw_gemma",
            "features": ["basic_messaging", "compression"],
            "priority": "normal"
        },
        "bullbear_predictor": {
            "mesh_id": "mesh_bullbear_predictor",
            "features": ["basic_messaging", "deduplication"],
            "priority": "normal"
        }
    })

class MeshConfigLoader:
    """Loads and manages mesh configuration"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_path()
        self.config = None
        
    def _find_config_path(self) -> str:
        """Find configuration file path"""
        possible_paths = [
            "config/mesh_config.yaml",
            "config/mesh_config.yaml.example",
            "/etc/simp/mesh_config.yaml",
            "./mesh_config.yaml"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Return default path
        return "config/mesh_config.yaml"
    
    def load(self) -> MeshConfig:
        """Load configuration from file"""
        logger.info(f"Loading mesh configuration from: {self.config_path}")
        
        if not os.path.exists(self.config_path):
            logger.warning(f"Configuration file not found: {self.config_path}")
            logger.info("Using default configuration")
            self.config = MeshConfig()
            return self.config
        
        try:
            with open(self.config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
            
            # Convert YAML to dataclass
            self.config = self._yaml_to_dataclass(yaml_config)
            logger.info("Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            logger.info("Falling back to default configuration")
            self.config = MeshConfig()
        
        return self.config
    
    def _yaml_to_dataclass(self, yaml_config: Dict[str, Any]) -> MeshConfig:
        """Convert YAML configuration to dataclass"""
        # Start with default config
        config = MeshConfig()
        
        # Update from YAML if present
        if not yaml_config or 'mesh' not in yaml_config:
            return config
        
        mesh_config = yaml_config.get('mesh', {})
        
        # Update basic settings
        if 'enabled' in mesh_config:
            config.enabled = mesh_config['enabled']
        if 'mode' in mesh_config:
            config.mode = mesh_config['mode']
        
        # Update network configuration
        if 'network' in mesh_config:
            network = mesh_config['network']
            config.network = MeshNetworkConfig(
                multicast_group=network.get('multicast_group', config.network.multicast_group),
                multicast_port=network.get('multicast_port', config.network.multicast_port),
                ttl=network.get('ttl', config.network.ttl),
                buffer_size=network.get('buffer_size', config.network.buffer_size),
                enable_udp=network.get('enable_udp', config.network.enable_udp),
                enable_tcp_fallback=network.get('enable_tcp_fallback', config.network.enable_tcp_fallback),
                tcp_port=network.get('tcp_port', config.network.tcp_port),
                discovery_interval=network.get('discovery_interval', config.network.discovery_interval),
                heartbeat_interval=network.get('heartbeat_interval', config.network.heartbeat_interval)
            )
        
        # Update security configuration
        if 'security' in mesh_config:
            security = mesh_config['security']
            config.security = MeshSecurityConfig(
                encryption_enabled=security.get('encryption_enabled', config.security.encryption_enabled),
                require_authentication=security.get('require_authentication', config.security.require_authentication),
                encryption_algorithm=security.get('encryption_algorithm', config.security.encryption_algorithm),
                key_rotation_interval=security.get('key_rotation_interval', config.security.key_rotation_interval),
                auth_method=security.get('auth_method', config.security.auth_method),
                shared_secret_path=security.get('shared_secret_path', config.security.shared_secret_path),
                max_messages_per_second=security.get('max_messages_per_second', config.security.max_messages_per_second),
                max_connections_per_agent=security.get('max_connections_per_agent', config.security.max_connections_per_agent)
            )
        
        # Update features
        if 'features' in mesh_config:
            config.features.update(mesh_config['features'])
        
        # Update agents
        if 'agents' in yaml_config:
            config.agents.update(yaml_config['agents'])
        
        return config
    
    def validate(self) -> bool:
        """Validate configuration"""
        if not self.config:
            logger.error("Configuration not loaded")
            return False
        
        errors = []
        
        # Validate network configuration
        if not 1024 <= self.config.network.multicast_port <= 65535:
            errors.append(f"Invalid multicast port: {self.config.network.multicast_port}")
        
        if not 1 <= self.config.network.ttl <= 255:
            errors.append(f"Invalid TTL: {self.config.network.ttl}")
        
        # Validate security
        if self.config.security.encryption_enabled and not self.config.security.shared_secret_path:
            errors.append("Encryption enabled but no shared secret path specified")
        
        # Validate performance
        if self.config.performance.max_message_size <= 0:
            errors.append(f"Invalid max message size: {self.config.performance.max_message_size}")
        
        # Log validation results
        if errors:
            for error in errors:
                logger.error(f"Configuration validation error: {error}")
            return False
        else:
            logger.info("Configuration validation passed")
            return True
    
    def get_agent_config(self, agent_id: str) -> Dict[str, Any]:
        """Get configuration for specific agent"""
        if not self.config:
            self.load()
        
        # Return agent-specific config or defaults
        agent_config = self.config.agents.get(agent_id, {})
        
        # Merge with default agent template
        default_agent = {
            "mesh_id": f"mesh_{agent_id}",
            "features": ["basic_messaging"],
            "priority": "normal"
        }
        
        default_agent.update(agent_config)
        return default_agent
    
    def save_default_config(self, path: str = "config/mesh_config.yaml"):
        """Save default configuration to file"""
        default_config = {
            "mesh": {
                "enabled": True,
                "mode": "hybrid",
                "network": {
                    "multicast_group": "239.255.255.250",
                    "multicast_port": 9999,
                    "ttl": 2,
                    "buffer_size": 65536,
                    "enable_udp": True,
                    "enable_tcp_fallback": True,
                    "tcp_port": 8889,
                    "discovery_interval": 30,
                    "heartbeat_interval": 10
                },
                "security": {
                    "encryption_enabled": True,
                    "require_authentication": True,
                    "encryption_algorithm": "chacha20poly1305",
                    "key_rotation_interval": 86400,
                    "auth_method": "shared_secret",
                    "shared_secret_path": "/etc/simp/mesh_secret",
                    "max_messages_per_second": 1000,
                    "max_connections_per_agent": 10
                },
                "features": {
                    "delivery_receipts": {"enabled": True, "timeout": 30.0, "require_receipt": False},
                    "compression": {"enabled": True, "algorithm": "zlib", "min_size": 1024},
                    "deduplication": {"enabled": True, "window_seconds": 300},
                    "gossip": {"enabled": True, "fanout": 3, "interval": 60}
                }
            },
            "agents": {
                "quantumarb": {
                    "mesh_id": "mesh_quantumarb",
                    "features": ["basic_messaging", "priority_queues", "payment_channels"],
                    "priority": "high"
                }
            },
            "environment": "development"
        }
        
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            logger.info(f"Default configuration saved to: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save default configuration: {e}")
            return False

def main():
    """Test configuration loading"""
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create loader
    loader = MeshConfigLoader()
    
    # Try to load configuration
    config = loader.load()
    
    # Validate
    if loader.validate():
        print("✅ Configuration loaded and validated successfully")
        print(f"   Mode: {config.mode}")
        print(f"   Multicast: {config.network.multicast_group}:{config.network.multicast_port}")
        print(f"   Agents configured: {len(config.agents)}")
        
        # Show agent configs
        print("\n📋 Agent configurations:")
        for agent_id in ["quantumarb", "kashclaw_gemma", "bullbear_predictor"]:
            agent_config = loader.get_agent_config(agent_id)
            print(f"   {agent_id}: {agent_config['mesh_id']} ({agent_config['priority']})")
        
        return 0
    else:
        print("❌ Configuration validation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())