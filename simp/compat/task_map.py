"""
Task Translation for A2A Compatibility.

This module translates between SIMP intents and A2A tasks,
enabling interoperability between SIMP agents and external
A2A-compliant systems.

Key features:
- Bidirectional translation (SIMP ↔ A2A)
- Type mapping and field conversion
- Error handling and validation
- Metadata preservation
"""

import uuid
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Standard A2A task types."""
    EXECUTE_TRADE = "execute_trade"
    ANALYZE_MARKET = "analyze_market"
    RESEARCH_TOPIC = "research_topic"
    MONITOR_SYSTEM = "monitor_system"
    AUDIT_SECURITY = "audit_security"
    PROCESS_PAYMENT = "process_payment"
    GENERATE_REPORT = "generate_report"
    CUSTOM = "custom"


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class A2ATask:
    """A2A-compliant task representation."""
    task_id: str  # Unique task identifier
    type: TaskType  # Task type
    parameters: Dict[str, Any]  # Task parameters
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None  # Optional expiration time
    priority: int = 0  # Task priority (higher = more important)
    
    def __post_init__(self):
        """Validate task after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate task fields."""
        # Task ID validation
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("task_id must be a non-empty string")
        
        # Task type validation
        if not isinstance(self.type, TaskType):
            try:
                self.type = TaskType(self.type)
            except ValueError:
                raise ValueError(f"type must be one of {[t.value for t in TaskType]}")
        
        # Parameters validation
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dictionary")
        
        # Metadata validation
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        
        # Timestamp validation
        try:
            datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            if self.expires_at:
                datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {e}")
        
        # Priority validation
        if not isinstance(self.priority, int):
            raise ValueError("priority must be an integer")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class TaskResponse:
    """A2A task response."""
    task_id: str  # Original task ID
    status: TaskStatus  # Response status
    result: Optional[Dict[str, Any]] = None  # Task result
    error: Optional[str] = None  # Error message if failed
    metadata: Dict[str, Any] = field(default_factory=dict)  # Response metadata
    completed_at: Optional[str] = None  # Completion timestamp
    
    def __post_init__(self):
        """Validate response after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate response fields."""
        # Task ID validation
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("task_id must be a non-empty string")
        
        # Status validation
        if not isinstance(self.status, TaskStatus):
            try:
                self.status = TaskStatus(self.status)
            except ValueError:
                raise ValueError(f"status must be one of {[s.value for s in TaskStatus]}")
        
        # Result validation
        if self.result is not None and not isinstance(self.result, dict):
            raise ValueError("result must be a dictionary or None")
        
        # Error validation
        if self.error is not None and not isinstance(self.error, str):
            raise ValueError("error must be a string or None")
        
        # Metadata validation
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        
        # Timestamp validation
        if self.completed_at:
            try:
                datetime.fromisoformat(self.completed_at.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"Invalid timestamp format: {self.completed_at}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class A2ATaskTranslator:
    """
    Translator between SIMP intents and A2A tasks.
    
    This class handles bidirectional translation with field mapping,
    type conversion, and metadata preservation.
    """
    
    # Mapping from SIMP intent types to A2A task types
    INTENT_TO_TASK_MAP = {
        "trade_execution": TaskType.EXECUTE_TRADE,
        "market_analysis": TaskType.ANALYZE_MARKET,
        "research_request": TaskType.RESEARCH_TOPIC,
        "health_check": TaskType.MONITOR_SYSTEM,
        "security_audit": TaskType.AUDIT_SECURITY,
        "payment_request": TaskType.PROCESS_PAYMENT,
        "report_generation": TaskType.GENERATE_REPORT,
        "ping": TaskType.CUSTOM,  # Special case
    }
    
    # Mapping from A2A task types to SIMP intent types
    TASK_TO_INTENT_MAP = {v: k for k, v in INTENT_TO_TASK_MAP.items()}
    
    # Field mapping for trade execution
    TRADE_FIELD_MAP = {
        "instrument": "asset",
        "asset_pair": "asset",
        "side": "action",
        "quantity": "amount",
        "units": "currency",
        "price": "limit_price",
        "exchange": "venue",
    }
    
    # Field mapping for analysis tasks
    ANALYSIS_FIELD_MAP = {
        "ticker": "instrument",
        "timeframe": "analysis_period",
        "indicators": "analysis_methods",
        "depth": "analysis_depth",
    }
    
    def __init__(self, default_agent: str = "simp_broker"):
        """
        Initialize the task translator.
        
        Args:
            default_agent: Default agent ID for generated tasks
        """
        self.default_agent = default_agent
        logger.info(f"Initialized A2A task translator with default agent: {default_agent}")
    
    def translate_simp_to_a2a(
        self,
        simp_intent: Dict[str, Any],
        source_agent: Optional[str] = None
    ) -> A2ATask:
        """
        Translate SIMP intent to A2A task.
        
        Args:
            simp_intent: SIMP intent dictionary
            source_agent: Source agent ID (defaults to intent source or default)
            
        Returns:
            A2ATask object
        """
        # Extract intent information
        intent_type = simp_intent.get("intent_type", "custom")
        intent_id = simp_intent.get("intent_id", str(uuid.uuid4()))
        payload = simp_intent.get("payload", {})
        
        # Determine source agent
        if source_agent is None:
            source_agent = simp_intent.get("source_agent", self.default_agent)
        
        # Map intent type to task type
        task_type = self.INTENT_TO_TASK_MAP.get(intent_type, TaskType.CUSTOM)
        
        # Generate task ID
        task_id = f"a2a:{intent_id}"
        
        # Translate parameters based on task type
        parameters = self._translate_parameters(intent_type, payload)
        
        # Build metadata
        metadata = {
            "x-simp-intent-id": intent_id,
            "x-simp-intent-type": intent_type,
            "x-simp-source-agent": source_agent,
            "x-simp-translated-at": datetime.utcnow().isoformat(),
        }
        
        # Include original intent metadata if present
        if "metadata" in simp_intent:
            metadata["x-simp-original-metadata"] = simp_intent["metadata"]
        
        # Create A2A task
        task = A2ATask(
            task_id=task_id,
            type=task_type,
            parameters=parameters,
            metadata=metadata,
        )
        
        logger.debug(f"Translated SIMP intent '{intent_type}' to A2A task '{task_type}'")
        return task
    
    def translate_a2a_to_simp(
        self,
        a2a_task: Union[A2ATask, Dict[str, Any]],
        target_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translate A2A task to SIMP intent.
        
        Args:
            a2a_task: A2A task or task dictionary
            target_agent: Target agent ID (defaults to metadata or auto)
            
        Returns:
            SIMP intent dictionary
        """
        # Convert dict to A2ATask if needed
        if isinstance(a2a_task, dict):
            a2a_task = A2ATask(**a2a_task)
        
        # Extract task information
        task_type = a2a_task.type
        task_id = a2a_task.task_id
        parameters = a2a_task.parameters
        metadata = a2a_task.metadata
        
        # Map task type to intent type
        intent_type = self.TASK_TO_INTENT_MAP.get(task_type, "custom")
        
        # Extract intent ID from metadata or generate
        intent_id = metadata.get("x-simp-intent-id", task_id.replace("a2a:", ""))
        
        # Determine target agent
        if target_agent is None:
            target_agent = metadata.get("x-simp-target-agent", "auto")
        
        # Determine source agent
        source_agent = metadata.get("x-simp-source-agent", "a2a_external")
        
        # Translate parameters based on task type
        payload = self._reverse_translate_parameters(task_type, parameters)
        
        # Build SIMP intent
        intent = {
            "intent_type": intent_type,
            "intent_id": intent_id,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "payload": payload,
            "metadata": {
                "x-a2a-task-id": task_id,
                "x-a2a-task-type": task_type.value,
                "x-a2a-translated-at": datetime.utcnow().isoformat(),
                **{k: v for k, v in metadata.items() if not k.startswith("x-simp-")},
            },
        }
        
        logger.debug(f"Translated A2A task '{task_type}' to SIMP intent '{intent_type}'")
        return intent
    
    def _translate_parameters(
        self,
        intent_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Translate SIMP payload to A2A parameters."""
        if intent_type == "trade_execution":
            return self._translate_trade_parameters(payload)
        elif intent_type == "market_analysis":
            return self._translate_analysis_parameters(payload)
        elif intent_type == "research_request":
            return self._translate_research_parameters(payload)
        elif intent_type == "health_check":
            return self._translate_health_parameters(payload)
        elif intent_type == "security_audit":
            return self._translate_security_parameters(payload)
        elif intent_type == "payment_request":
            return self._translate_payment_parameters(payload)
        else:
            # For custom or unknown intents, pass through with metadata
            return {
                "action": intent_type,
                "parameters": payload,
                "metadata": {"original_intent_type": intent_type},
            }
    
    def _reverse_translate_parameters(
        self,
        task_type: TaskType,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Translate A2A parameters to SIMP payload."""
        if task_type == TaskType.EXECUTE_TRADE:
            return self._reverse_translate_trade_parameters(parameters)
        elif task_type == TaskType.ANALYZE_MARKET:
            return self._reverse_translate_analysis_parameters(parameters)
        elif task_type == TaskType.RESEARCH_TOPIC:
            return self._reverse_translate_research_parameters(parameters)
        elif task_type == TaskType.MONITOR_SYSTEM:
            return self._reverse_translate_health_parameters(parameters)
        elif task_type == TaskType.AUDIT_SECURITY:
            return self._reverse_translate_security_parameters(parameters)
        elif task_type == TaskType.PROCESS_PAYMENT:
            return self._reverse_translate_payment_parameters(parameters)
        else:
            # For custom tasks, extract from parameters
            if "parameters" in parameters:
                return parameters["parameters"]
            else:
                return parameters
    
    def _translate_trade_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Translate trade execution parameters."""
        translated = {}
        
        for simp_field, a2a_field in self.TRADE_FIELD_MAP.items():
            if simp_field in payload:
                translated[a2a_field] = payload[simp_field]
        
        # Add default values if missing
        if "currency" not in translated and "units" in payload:
            translated["currency"] = payload["units"]
        
        if "venue" not in translated:
            translated["venue"] = "auto"  # Let executor choose
        
        # Add order type if not specified
        if "order_type" not in translated:
            translated["order_type"] = "market"
        
        return translated
    
    def _reverse_translate_trade_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse translate trade execution parameters."""
        translated = {}
        
        # Build reverse mapping
        reverse_map = {v: k for k, v in self.TRADE_FIELD_MAP.items()}
        
        for a2a_field, simp_field in reverse_map.items():
            if a2a_field in parameters:
                translated[simp_field] = parameters[a2a_field]
        
        # Map order_type to SIMP format
        if "order_type" in parameters:
            translated["order_type"] = parameters["order_type"]
        
        return translated
    
    def _translate_analysis_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Translate market analysis parameters."""
        translated = {}
        
        for simp_field, a2a_field in self.ANALYSIS_FIELD_MAP.items():
            if simp_field in payload:
                translated[a2a_field] = payload[simp_field]
        
        # Add analysis type
        if "analysis_type" not in translated:
            translated["analysis_type"] = "comprehensive"
        
        return translated
    
    def _reverse_translate_analysis_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse translate market analysis parameters."""
        translated = {}
        
        # Build reverse mapping
        reverse_map = {v: k for k, v in self.ANALYSIS_FIELD_MAP.items()}
        
        for a2a_field, simp_field in reverse_map.items():
            if a2a_field in parameters:
                translated[simp_field] = parameters[a2a_field]
        
        return translated
    
    def _translate_research_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Translate research parameters."""
        return {
            "topic": payload.get("topic", ""),
            "depth": payload.get("depth", "standard"),
            "sources": payload.get("sources", ["web", "academic", "news"]),
            "format": payload.get("format", "report"),
        }
    
    def _reverse_translate_research_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse translate research parameters."""
        return {
            "topic": parameters.get("topic", ""),
            "depth": parameters.get("depth", "standard"),
            "sources": parameters.get("sources", []),
            "format": parameters.get("format", "report"),
        }
    
    def _translate_health_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Translate health check parameters."""
        return {
            "components": payload.get("components", ["all"]),
            "checks": payload.get("checks", ["basic"]),
            "depth": payload.get("depth", "standard"),
        }
    
    def _reverse_translate_health_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse translate health check parameters."""
        return {
            "components": parameters.get("components", ["all"]),
            "checks": parameters.get("checks", ["basic"]),
            "depth": parameters.get("depth", "standard"),
        }
    
    def _translate_security_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Translate security audit parameters."""
        return {
            "targets": payload.get("targets", ["system"]),
            "checks": payload.get("checks", ["basic"]),
            "depth": payload.get("depth", "standard"),
        }
    
    def _reverse_translate_security_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse translate security audit parameters."""
        return {
            "targets": parameters.get("targets", ["system"]),
            "checks": parameters.get("checks", ["basic"]),
            "depth": parameters.get("depth", "standard"),
        }
    
    def _translate_payment_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Translate payment parameters."""
        return {
            "amount": payload.get("amount", 0),
            "currency": payload.get("currency", "USD"),
            "recipient": payload.get("recipient", ""),
            "purpose": payload.get("purpose", ""),
            "reference": payload.get("reference", ""),
        }
    
    def _reverse_translate_payment_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse translate payment parameters."""
        return {
            "amount": parameters.get("amount", 0),
            "currency": parameters.get("currency", "USD"),
            "recipient": parameters.get("recipient", ""),
            "purpose": parameters.get("purpose", ""),
            "reference": parameters.get("reference", ""),
        }


# Helper functions
def translate_simp_to_a2a(
    simp_intent: Dict[str, Any],
    source_agent: Optional[str] = None
) -> Dict[str, Any]:
    """
    Translate SIMP intent to A2A task (convenience function).
    
    Args:
        simp_intent: SIMP intent dictionary
        source_agent: Source agent ID
        
    Returns:
        A2A task dictionary
    """
    translator = A2ATaskTranslator()
    task = translator.translate_simp_to_a2a(simp_intent, source_agent)
    return task.to_dict()


def translate_a2a_to_simp(
    a2a_task: Dict[str, Any],
    target_agent: Optional[str] = None
) -> Dict[str, Any]:
    """
    Translate A2A task to SIMP intent (convenience function).
    
    Args:
        a2a_task: A2A task dictionary
        target_agent: Target agent ID
        
    Returns:
        SIMP intent dictionary
    """
    translator = A2ATaskTranslator()
    intent = translator.translate_a2a_to_simp(a2a_task, target_agent)
    return intent


# Example usage
if __name__ == "__main__":
    # Example SIMP intent
    simp_intent = {
        "intent_type": "trade_execution",
        "intent_id": "trade_001",
        "source_agent": "quantumarb",
        "target_agent": "kashclaw",
        "payload": {
            "instrument": "BTC-USD",
            "side": "buy",
            "quantity": 1000,
            "units": "USD",
            "exchange": "coinbase",
        },
    }
    
    # Translate to A2A
    translator = A2ATaskTranslator()
    a2a_task = translator.translate_simp_to_a2a(simp_intent)
    
    print("Original SIMP Intent:")
    print(json.dumps(simp_intent, indent=2))
    print("\nTranslated A2A Task:")
    print(json.dumps(a2a_task.to_dict(), indent=2))
    
    # Translate back to SIMP
    simp_back = translator.translate_a2a_to_simp(a2a_task)
    
    print("\nBack-translated SIMP Intent:")
    print(json.dumps(simp_back, indent=2))