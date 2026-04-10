"""
Agent Card Generator for A2A Compatibility.

This module generates A2A-compliant agent cards for SIMP agents.
Agent cards are served at GET /.well-known/agent-card.json and
provide metadata about agents for discovery and interoperability.

Key features:
- Standardized agent metadata format
- Capability mapping to A2A skills
- Authentication scheme declaration
- Health endpoint integration
- Version compatibility tracking
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# SIMP version for A2A compatibility
_SIMP_VERSION = "0.7.0"


class CompatError(Exception):
    """Base exception for A2A compatibility errors."""
    pass


class AgentStatus(str, Enum):
    """Agent lifecycle status."""
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class AuthScheme(str, Enum):
    """Supported authentication schemes."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    MTLS = "mtls"
    NONE = "none"


@dataclass
class StructuredCapability:
    """
    Structured representation of an agent capability.
    
    This maps SIMP agent capabilities to A2A skills with additional
    metadata for discovery and negotiation.
    """
    type: str  # "skill", "tool", "service"
    name: str  # Unique identifier (e.g., "arbitrage_detection")
    description: str  # Human-readable description
    version: str = "1.0.0"  # Capability version
    parameters: Optional[Dict[str, Any]] = None  # Required parameters
    constraints: Optional[List[str]] = None  # Usage constraints
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata
    
    def to_a2a_skill(self) -> Dict[str, Any]:
        """Convert to A2A skill format."""
        skill = {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }
        
        if self.parameters:
            skill["parameters"] = self.parameters
        if self.constraints:
            skill["constraints"] = self.constraints
        if self.metadata:
            skill["metadata"] = self.metadata
            
        return skill


@dataclass
class AgentCard:
    """
    A2A-compliant agent card.
    
    This represents the standardized metadata for a SIMP agent
    that can be discovered and used by A2A-compliant systems.
    """
    # Core identification
    id: str  # Format: "simp:agent:<agent_id>"
    name: str  # Human-readable name
    version: str = _SIMP_VERSION  # Agent version
    
    # Capabilities
    capabilities: List[Dict[str, Any]] = field(default_factory=list)
    
    # Authentication
    auth_schemes: List[str] = field(default_factory=lambda: [AuthScheme.API_KEY.value])
    
    # Endpoints
    endpoints: Dict[str, str] = field(default_factory=dict)
    
    # Status and health
    status: str = AgentStatus.ACTIVE.value
    last_heartbeat: Optional[str] = None  # ISO 8601 timestamp
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __post_init__(self):
        """Validate the agent card after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate agent card fields."""
        # ID validation
        if not self.id.startswith("simp:agent:"):
            raise ValueError(f"Agent ID must start with 'simp:agent:', got: {self.id}")
        
        # Name validation
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Agent name must be a non-empty string")
        
        # Capabilities validation
        if not isinstance(self.capabilities, list):
            raise ValueError("Capabilities must be a list")
        
        # Auth schemes validation
        if not isinstance(self.auth_schemes, list):
            raise ValueError("Auth schemes must be a list")
        for scheme in self.auth_schemes:
            if scheme not in [s.value for s in AuthScheme]:
                raise ValueError(f"Invalid auth scheme: {scheme}")
        
        # Endpoints validation
        if not isinstance(self.endpoints, dict):
            raise ValueError("Endpoints must be a dictionary")
        
        # Status validation
        if self.status not in [s.value for s in AgentStatus]:
            raise ValueError(f"Invalid status: {self.status}")
        
        # Timestamp validation
        try:
            datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            datetime.fromisoformat(self.updated_at.replace('Z', '+00:00'))
            if self.last_heartbeat:
                datetime.fromisoformat(self.last_heartbeat.replace('Z', '+00:00'))
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def update_heartbeat(self) -> None:
        """Update the last heartbeat timestamp."""
        self.last_heartbeat = datetime.utcnow().isoformat()
        self.updated_at = self.last_heartbeat
    
    def update_status(self, status: AgentStatus) -> None:
        """Update agent status."""
        self.status = status.value
        self.updated_at = datetime.utcnow().isoformat()


class AgentCardGenerator:
    """
    Generator for A2A-compliant agent cards.
    
    This class creates agent cards for SIMP agents based on their
    registration information and capabilities.
    """
    
    def __init__(self, broker_url: str = "http://127.0.0.1:5555"):
        """
        Initialize the agent card generator.
        
        Args:
            broker_url: Base URL of the SIMP broker
        """
        self.broker_url = broker_url.rstrip('/')
        self._agent_cards: Dict[str, AgentCard] = {}
    
    def generate_card(
        self,
        agent_id: str,
        agent_name: str,
        capabilities: List[StructuredCapability],
        auth_schemes: Optional[List[AuthScheme]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: AgentStatus = AgentStatus.ACTIVE
    ) -> AgentCard:
        """
        Generate an A2A-compliant agent card.
        
        Args:
            agent_id: SIMP agent ID (e.g., "quantumarb")
            agent_name: Human-readable agent name
            capabilities: List of agent capabilities
            auth_schemes: Supported authentication schemes
            metadata: Additional agent metadata
            status: Current agent status
            
        Returns:
            AgentCard object
        """
        # Build agent ID
        full_agent_id = f"simp:agent:{agent_id}"
        
        # Convert capabilities to A2A skills
        a2a_capabilities = [cap.to_a2a_skill() for cap in capabilities]
        
        # Default auth schemes
        if auth_schemes is None:
            auth_schemes = [AuthScheme.API_KEY]
        
        # Build endpoints
        endpoints = {
            "tasks": f"{self.broker_url}/a2a/tasks",
            "events": f"{self.broker_url}/a2a/events",
            "events_stream": f"{self.broker_url}/a2a/events/stream",
            "health": f"{self.broker_url}/agents/{agent_id}/health",
            "security": f"{self.broker_url}/a2a/security",
        }
        
        # Build metadata
        if metadata is None:
            metadata = {}
        
        # Add SIMP-specific metadata
        metadata.update({
            "x-simp-version": _SIMP_VERSION,
            "x-simp-agent-id": agent_id,
            "x-simp-broker-url": self.broker_url,
        })
        
        # Create agent card
        card = AgentCard(
            id=full_agent_id,
            name=agent_name,
            version=_SIMP_VERSION,
            capabilities=a2a_capabilities,
            auth_schemes=[scheme.value for scheme in auth_schemes],
            endpoints=endpoints,
            status=status.value,
            metadata=metadata,
        )
        
        # Store for caching
        self._agent_cards[agent_id] = card
        
        logger.info(f"Generated agent card for {agent_id} ({agent_name})")
        return card
    
    def get_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get cached agent card by ID."""
        return self._agent_cards.get(agent_id)
    
    def update_card_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Update status of cached agent card."""
        if agent_id in self._agent_cards:
            self._agent_cards[agent_id].update_status(status)
            return True
        return False
    
    def update_card_heartbeat(self, agent_id: str) -> bool:
        """Update heartbeat of cached agent card."""
        if agent_id in self._agent_cards:
            self._agent_cards[agent_id].update_heartbeat()
            return True
        return False
    
    def get_all_cards(self) -> Dict[str, AgentCard]:
        """Get all cached agent cards."""
        return self._agent_cards.copy()


# Helper functions
def generate_agent_card(
    agent_id: str,
    agent_name: str,
    capabilities: List[StructuredCapability],
    broker_url: str = "http://127.0.0.1:5555",
    **kwargs
) -> Dict[str, Any]:
    """
    Generate an A2A-compliant agent card (convenience function).
    
    Args:
        agent_id: SIMP agent ID
        agent_name: Human-readable agent name
        capabilities: List of agent capabilities
        broker_url: Base URL of the SIMP broker
        **kwargs: Additional arguments for AgentCardGenerator.generate_card
        
    Returns:
        Dictionary representation of the agent card
    """
    generator = AgentCardGenerator(broker_url)
    card = generator.generate_card(agent_id, agent_name, capabilities, **kwargs)
    return card.to_dict()


def validate_agent_card(card_data: Dict[str, Any]) -> bool:
    """
    Validate an agent card against A2A schema.
    
    Args:
        card_data: Agent card data to validate
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    try:
        # Check required fields
        required_fields = ["id", "name", "version", "capabilities", "auth_schemes", "endpoints"]
        for field in required_fields:
            if field not in card_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate ID format
        if not card_data["id"].startswith("simp:agent:"):
            raise ValueError(f"Agent ID must start with 'simp:agent:', got: {card_data['id']}")
        
        # Validate capabilities
        if not isinstance(card_data["capabilities"], list):
            raise ValueError("Capabilities must be a list")
        
        # Validate auth schemes
        if not isinstance(card_data["auth_schemes"], list):
            raise ValueError("Auth schemes must be a list")
        
        valid_schemes = [s.value for s in AuthScheme]
        for scheme in card_data["auth_schemes"]:
            if scheme not in valid_schemes:
                raise ValueError(f"Invalid auth scheme: {scheme}")
        
        # Validate endpoints
        if not isinstance(card_data["endpoints"], dict):
            raise ValueError("Endpoints must be a dictionary")
        
        # Validate timestamps if present
        timestamp_fields = ["created_at", "updated_at", "last_heartbeat"]
        for field in timestamp_fields:
            if field in card_data and card_data[field]:
                try:
                    datetime.fromisoformat(card_data[field].replace('Z', '+00:00'))
                except ValueError:
                    raise ValueError(f"Invalid timestamp format for {field}: {card_data[field]}")
        
        return True
        
    except Exception as e:
        raise CompatError(f"Agent card validation failed: {e}")


def get_simp_version() -> str:
    """Get the current SIMP version for A2A compatibility."""
    return _SIMP_VERSION


# Example usage
if __name__ == "__main__":
    # Example: Generate agent card for QuantumArb
    quantumarb_capabilities = [
        StructuredCapability(
            type="skill",
            name="arbitrage_detection",
            description="Detects cross-exchange arbitrage opportunities",
            version="1.0.0",
            parameters={
                "exchanges": ["binance", "coinbase", "kraken"],
                "assets": ["BTC", "ETH", "SOL"],
                "min_spread_bps": 10,
            },
            constraints=["requires_market_data", "testnet_only"],
            metadata={"category": "trading", "risk_level": "medium"},
        )
    ]
    
    card = generate_agent_card(
        agent_id="quantumarb",
        agent_name="QuantumArb",
        capabilities=quantumarb_capabilities,
        broker_url="http://127.0.0.1:5555",
    )
    
    print("Example Agent Card:")
    print(json.dumps(card, indent=2))