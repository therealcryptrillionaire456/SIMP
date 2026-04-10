"""
A2A (Agent-to-Agent) Compatibility Layer for SIMP.

This module provides compatibility with the A2A Core Schema, allowing
SIMP agents to interoperate with external A2A-compliant systems.

Key components:
- Agent cards: GET /.well-known/agent-card.json
- Task translation: POST /a2a/tasks
- Event streaming: GET /a2a/events, GET /a2a/events/stream
- Security endpoints: GET /a2a/security
- FinancialOps integration: A2A-compatible financial operations

All components follow the A2A Core Schema v0.7.0 and maintain
backward compatibility with existing SIMP agents.
"""

from .agent_card import (
    AgentCardGenerator,
    generate_agent_card,
    get_simp_version,
    validate_agent_card,
    CompatError,
)

from .capability_map import (
    map_capability_to_a2a_skill,
    normalise_capabilities,
    StructuredCapability,
)

from .task_map import (
    translate_simp_to_a2a,
    translate_a2a_to_simp,
    A2ATaskTranslator,
)

from .event_stream import (
    EventStreamBuffer,
    A2AEvent,
    EventType,
    publish_a2a_event,
    get_event_stream,
)

from .a2a_security import (
    get_a2a_security_info,
    A2ASecurityScheme,
    validate_a2a_request,
)

from .financial_ops import (
    FinancialOpsCardGenerator,
    validate_financial_ops_request,
    execute_financial_ops_task,
)

from .projectx_card import (
    generate_projectx_card,
    get_projectx_diagnostics,
)

# Re-export common types
__all__ = [
    # Agent cards
    'AgentCardGenerator',
    'generate_agent_card',
    'get_simp_version',
    'validate_agent_card',
    'CompatError',
    
    # Capability mapping
    'map_capability_to_a2a_skill',
    'normalise_capabilities',
    'StructuredCapability',
    
    # Task translation
    'translate_simp_to_a2a',
    'translate_a2a_to_simp',
    'A2ATaskTranslator',
    
    # Event streaming
    'EventStreamBuffer',
    'A2AEvent',
    'EventType',
    'publish_a2a_event',
    'get_event_stream',
    
    # Security
    'get_a2a_security_info',
    'A2ASecurityScheme',
    'validate_a2a_request',
    
    # FinancialOps
    'FinancialOpsCardGenerator',
    'validate_financial_ops_request',
    'execute_financial_ops_task',
    
    # ProjectX
    'generate_projectx_card',
    'get_projectx_diagnostics',
]

# SIMP version for A2A compatibility
_SIMP_VERSION = "0.7.0"