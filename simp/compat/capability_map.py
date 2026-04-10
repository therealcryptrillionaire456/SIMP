"""
Capability Mapping for A2A Compatibility.

This module maps SIMP agent capabilities to A2A skills and provides
normalization functions for consistent capability representation.

Key features:
- Standardized capability taxonomy
- Mapping between SIMP and A2A capability types
- Normalization of capability descriptions
- Validation of capability schemas
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Set
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class CapabilityType(str, Enum):
    """Standardized capability types."""
    SKILL = "skill"  # Analytical or decision-making ability
    TOOL = "tool"    # Utility function or API
    SERVICE = "service"  # Long-running service
    ADAPTER = "adapter"  # Protocol or format adapter
    CONNECTOR = "connector"  # External system integration


class A2ASkillCategory(str, Enum):
    """A2A skill categories for discovery."""
    TRADING = "trading"
    ANALYSIS = "analysis"
    RESEARCH = "research"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    MAINTENANCE = "maintenance"
    SECURITY = "security"
    COMMUNICATION = "communication"
    OTHER = "other"


@dataclass
class CapabilityMapping:
    """Mapping between SIMP capability and A2A skill."""
    simp_name: str  # SIMP capability name
    a2a_skill: str  # A2A skill name
    category: A2ASkillCategory  # Skill category
    description: str  # Human-readable description
    version: str = "1.0.0"  # Mapping version
    parameters_map: Optional[Dict[str, str]] = None  # Parameter name mapping
    constraints: Optional[List[str]] = None  # Usage constraints
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata


# Standard capability mappings
STANDARD_CAPABILITY_MAPPINGS = {
    # QuantumArb capabilities
    "arbitrage_detection": CapabilityMapping(
        simp_name="arbitrage_detection",
        a2a_skill="arbitrage_analysis",
        category=A2ASkillCategory.TRADING,
        description="Detects cross-exchange arbitrage opportunities",
        parameters_map={
            "exchanges": "venues",
            "assets": "instruments",
            "min_spread_bps": "min_spread",
        },
        constraints=["requires_market_data", "testnet_only"],
        metadata={"risk_level": "medium", "latency_sensitive": True},
    ),
    
    # KashClaw capabilities
    "technical_analysis": CapabilityMapping(
        simp_name="technical_analysis",
        a2a_skill="market_analysis",
        category=A2ASkillCategory.ANALYSIS,
        description="Performs technical analysis using indicators and patterns",
        parameters_map={
            "indicators": "analysis_methods",
            "timeframe": "analysis_horizon",
        },
        constraints=["requires_historical_data"],
        metadata={"analysis_type": "technical"},
    ),
    
    "trade_execution": CapabilityMapping(
        simp_name="trade_execution",
        a2a_skill="order_execution",
        category=A2ASkillCategory.EXECUTION,
        description="Executes trades with risk management",
        parameters_map={
            "exchange": "venue",
            "asset_pair": "instrument",
            "quantity": "amount",
        },
        constraints=["requires_api_key", "sandbox_only"],
        metadata={"execution_type": "spot"},
    ),
    
    # Kloutbot capabilities
    "sentiment_analysis": CapabilityMapping(
        simp_name="sentiment_analysis",
        a2a_skill="market_sentiment",
        category=A2ASkillCategory.ANALYSIS,
        description="Analyzes market sentiment from news and social media",
        parameters_map={
            "sources": "data_sources",
            "time_window": "analysis_window",
        },
        constraints=["requires_text_data"],
        metadata={"analysis_type": "sentiment"},
    ),
    
    # ProjectX capabilities
    "health_check": CapabilityMapping(
        simp_name="health_check",
        a2a_skill="system_health",
        category=A2ASkillCategory.MONITORING,
        description="Performs system health checks and diagnostics",
        parameters_map={
            "components": "monitored_components",
            "metrics": "health_metrics",
        },
        constraints=["requires_system_access"],
        metadata={"monitoring_type": "system"},
    ),
    
    "security_audit": CapabilityMapping(
        simp_name="security_audit",
        a2a_skill="security_scan",
        category=A2ASkillCategory.SECURITY,
        description="Performs security audits and vulnerability scans",
        parameters_map={
            "targets": "scan_targets",
            "checks": "security_checks",
        },
        constraints=["requires_permissions"],
        metadata={"audit_type": "security"},
    ),
    
    # FinancialOps capabilities
    "payment_processing": CapabilityMapping(
        simp_name="payment_processing",
        a2a_skill="payment_execution",
        category=A2ASkillCategory.EXECUTION,
        description="Processes payments with approval workflows",
        parameters_map={
            "amount": "payment_amount",
            "currency": "payment_currency",
            "recipient": "beneficiary",
        },
        constraints=["requires_approval", "simulated_only"],
        metadata={"payment_type": "financial"},
    ),
    
    "budget_monitoring": CapabilityMapping(
        simp_name="budget_monitoring",
        a2a_skill="budget_tracking",
        category=A2ASkillCategory.MONITORING,
        description="Monitors budget usage and alerts on thresholds",
        parameters_map={
            "budget": "budget_limit",
            "thresholds": "alert_thresholds",
        },
        constraints=["requires_financial_data"],
        metadata={"monitoring_type": "financial"},
    ),
}


def map_capability_to_a2a_skill(
    simp_capability: str,
    capability_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Map a SIMP capability to an A2A skill.
    
    Args:
        simp_capability: SIMP capability name
        capability_data: Additional capability data
        
    Returns:
        A2A skill representation
    """
    # Get standard mapping or create default
    if simp_capability in STANDARD_CAPABILITY_MAPPINGS:
        mapping = STANDARD_CAPABILITY_MAPPINGS[simp_capability]
    else:
        # Create default mapping for unknown capabilities
        mapping = CapabilityMapping(
            simp_name=simp_capability,
            a2a_skill=simp_capability,
            category=A2ASkillCategory.OTHER,
            description=f"SIMP capability: {simp_capability}",
        )
    
    # Build base skill
    skill = {
        "type": "skill",
        "name": mapping.a2a_skill,
        "description": mapping.description,
        "version": mapping.version,
        "category": mapping.category.value,
        "metadata": {
            "simp_capability": mapping.simp_name,
            "mapping_version": mapping.version,
        },
    }
    
    # Add parameters if provided
    if capability_data and "parameters" in capability_data:
        skill["parameters"] = capability_data["parameters"]
    
    # Add constraints
    if mapping.constraints:
        skill["constraints"] = mapping.constraints
    
    # Add additional metadata
    if mapping.metadata:
        if "metadata" not in skill:
            skill["metadata"] = {}
        skill["metadata"].update(mapping.metadata)
    
    # Add capability data metadata
    if capability_data:
        if "metadata" not in skill:
            skill["metadata"] = {}
        
        # Include relevant fields from capability data
        for field in ["version", "author", "created_at"]:
            if field in capability_data:
                skill["metadata"][f"simp_{field}"] = capability_data[field]
    
    logger.debug(f"Mapped SIMP capability '{simp_capability}' to A2A skill '{mapping.a2a_skill}'")
    return skill


def normalise_capabilities(
    capabilities: Union[List[str], List[Dict[str, Any]], Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Normalize capabilities to a standard format.
    
    Args:
        capabilities: Capabilities in various formats:
            - List of strings: ["arbitrage_detection", "technical_analysis"]
            - List of dicts: [{"name": "arbitrage_detection", "params": {...}}]
            - Dict: {"arbitrage_detection": {...}, "technical_analysis": {...}}
            
    Returns:
        List of normalized capability dictionaries
    """
    normalized = []
    
    if isinstance(capabilities, dict):
        # Convert dict to list of capabilities
        for name, data in capabilities.items():
            if isinstance(data, dict):
                normalized.append({"name": name, **data})
            else:
                normalized.append({"name": name, "description": str(data)})
    
    elif isinstance(capabilities, list):
        for item in capabilities:
            if isinstance(item, str):
                normalized.append({"name": item})
            elif isinstance(item, dict):
                normalized.append(item)
            else:
                logger.warning(f"Unsupported capability format: {type(item)}")
    
    else:
        raise ValueError(f"Unsupported capabilities format: {type(capabilities)}")
    
    # Ensure each capability has at least a name
    for cap in normalized:
        if "name" not in cap:
            raise ValueError(f"Capability missing 'name' field: {cap}")
    
    return normalized


def validate_capability_schema(capability: Dict[str, Any]) -> bool:
    """
    Validate a capability against the schema.
    
    Args:
        capability: Capability dictionary to validate
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    # Check required fields
    if "name" not in capability:
        raise ValueError("Capability missing 'name' field")
    
    # Validate name format
    name = capability["name"]
    if not isinstance(name, str):
        raise ValueError(f"Capability name must be string, got: {type(name)}")
    
    if not re.match(r'^[a-z][a-z0-9_]*$', name):
        raise ValueError(f"Invalid capability name format: {name}. Use lowercase with underscores.")
    
    # Validate description if present
    if "description" in capability and not isinstance(capability["description"], str):
        raise ValueError("Capability description must be string")
    
    # Validate version if present
    if "version" in capability:
        version = capability["version"]
        if not isinstance(version, str):
            raise ValueError("Capability version must be string")
        if not re.match(r'^\d+\.\d+\.\d+$', version):
            raise ValueError(f"Invalid version format: {version}. Use semantic versioning.")
    
    # Validate parameters if present
    if "parameters" in capability and not isinstance(capability["parameters"], dict):
        raise ValueError("Capability parameters must be dictionary")
    
    # Validate constraints if present
    if "constraints" in capability:
        constraints = capability["constraints"]
        if not isinstance(constraints, list):
            raise ValueError("Capability constraints must be list")
        for constraint in constraints:
            if not isinstance(constraint, str):
                raise ValueError("Constraint items must be strings")
    
    # Validate metadata if present
    if "metadata" in capability and not isinstance(capability["metadata"], dict):
        raise ValueError("Capability metadata must be dictionary")
    
    return True


def get_capability_categories() -> List[str]:
    """Get list of all capability categories."""
    return [category.value for category in A2ASkillCategory]


def get_capabilities_by_category(
    capabilities: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group capabilities by category.
    
    Args:
        capabilities: List of normalized capabilities
        
    Returns:
        Dictionary mapping categories to capabilities
    """
    categorized = {category.value: [] for category in A2ASkillCategory}
    categorized["unknown"] = []
    
    for capability in capabilities:
        # Map to A2A skill to get category
        skill = map_capability_to_a2a_skill(capability["name"], capability)
        category = skill.get("category", "unknown")
        
        if category in categorized:
            categorized[category].append(skill)
        else:
            categorized["unknown"].append(skill)
    
    # Remove empty categories
    return {cat: caps for cat, caps in categorized.items() if caps}


def merge_capabilities(
    existing: List[Dict[str, Any]],
    new: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge capability lists, preferring newer versions.
    
    Args:
        existing: Existing capabilities
        new: New capabilities to merge
        
    Returns:
        Merged capabilities list
    """
    # Convert to dict for easy lookup
    existing_dict = {cap["name"]: cap for cap in existing}
    
    for capability in new:
        name = capability["name"]
        
        if name in existing_dict:
            # Merge existing and new
            existing_cap = existing_dict[name]
            
            # Prefer newer version
            existing_version = existing_cap.get("version", "0.0.0")
            new_version = capability.get("version", "0.0.0")
            
            if _compare_versions(new_version, existing_version) > 0:
                existing_dict[name] = capability
                logger.debug(f"Updated capability '{name}' from v{existing_version} to v{new_version}")
        else:
            # Add new capability
            existing_dict[name] = capability
    
    return list(existing_dict.values())


def _compare_versions(v1: str, v2: str) -> int:
    """Compare semantic versions. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
    try:
        v1_parts = list(map(int, v1.split('.')))
        v2_parts = list(map(int, v2.split('.')))
        
        # Pad with zeros if needed
        while len(v1_parts) < 3:
            v1_parts.append(0)
        while len(v2_parts) < 3:
            v2_parts.append(0)
        
        for i in range(3):
            if v1_parts[i] > v2_parts[i]:
                return 1
            elif v1_parts[i] < v2_parts[i]:
                return -1
        
        return 0
    except (ValueError, AttributeError):
        # Fallback to string comparison
        return 1 if v1 > v2 else (-1 if v1 < v2 else 0)


# Re-export StructuredCapability from agent_card for convenience
from .agent_card import StructuredCapability

__all__ = [
    'CapabilityType',
    'A2ASkillCategory',
    'CapabilityMapping',
    'map_capability_to_a2a_skill',
    'normalise_capabilities',
    'validate_capability_schema',
    'get_capability_categories',
    'get_capabilities_by_category',
    'merge_capabilities',
    'StructuredCapability',
]