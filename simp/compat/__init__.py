"""
SIMP A2A Compatibility Layer — Sprints 1-5, S1-S7

Adapter surface that adds A2A protocol interoperability to SIMP
without touching CanonicalIntent or broker routing.
"""

# Sprint 1 — auth mapping
from simp.compat.auth_map import (
    build_security_schemes,
    get_recommended_scopes_for_agent,
    map_simp_auth_to_a2a,
)

# Sprint 1 — agent card
from simp.compat.agent_card import AgentCardGenerator

# Sprint 2 — capability mapping
from simp.compat.capability_map import capabilities_to_skills, get_capability_map

# Sprint 2 — task translation
from simp.compat.task_map import (
    A2A_TO_SIMP_INTENT,
    translate_a2a_to_simp,
    validate_a2a_payload,
    simp_state_to_a2a,
    build_a2a_task_status,
    is_a2a_terminal,
)

# Sprint 3 — capability schema
from simp.compat.capability_schema import (
    StructuredCapability,
    normalise_capabilities,
    capabilities_to_a2a_skills,
)

# Sprint 4 — discovery cache + errors
from simp.compat.discovery_cache import (
    CardCache,
    CompatError,
    CompatErrorCode,
    validate_agent_card,
)

# Sprint 5 — lifecycle map
from simp.compat.lifecycle_map import (
    SimpLifecycleState,
    A2ATaskState,
    simp_to_a2a_state,
    build_progress_event,
    build_completion_event,
    build_failure_event,
    events_from_intent_history,
)

# Sprint S1 — policy map
from simp.compat.policy_map import (
    get_agent_policy,
    get_agent_security_schemes,
    get_agent_security_requirements,
    AGENT_SAFETY_POLICIES,
    AGENT_SECURITY_SCHEMES,
    AGENT_SECURITY_REQUIREMENTS,
)

# Sprint S4 — ops policy
from simp.compat.ops_policy import (
    OpsPolicy,
    AutonomousOpType,
    validate_op_request,
    get_policy_dict,
    SpendRecord,
    SPEND_LEDGER,
)

# Sprint 41 — payment connector
from simp.compat.payment_connector import (
    PaymentConnectorConfig,
    PaymentResult,
    PaymentConnector,
    StubPaymentConnector,
    ALLOWED_CONNECTORS,
    ALLOWED_VENDOR_CATEGORIES,
    DISALLOWED_PAYMENT_TYPES,
    build_connector,
    validate_payment_request,
    ConnectorHealthTracker,
    HEALTH_TRACKER,
)

# Sprint 43 — approval queue
from simp.compat.approval_queue import (
    PaymentProposalStatus,
    PaymentProposal,
    ApprovalQueue,
    PolicyChangeQueue,
    APPROVAL_QUEUE,
    POLICY_CHANGE_QUEUE,
)

# Sprint 44 — live ledger
from simp.compat.live_ledger import (
    LivePaymentRecord,
    LiveSpendLedger,
    LIVE_LEDGER,
)

# Sprint 45 — reconciliation & payment events
from simp.compat.reconciliation import (
    ReconciliationResult,
    run_reconciliation,
)
from simp.compat.event_stream import (
    build_payment_event,
    PAYMENT_EVENT_KINDS,
)

# Sprint 46 — rollback
from simp.compat.rollback import (
    RollbackManager,
    ROLLBACK_MANAGER,
    RollbackState,
    RollbackRecord,
    LedgerFrozenError,
)

# Sprint 47 — gate manager
from simp.compat.gate_manager import (
    GateManager,
    GATE_MANAGER,
    GateStatus,
    GateCondition,
    GateCheckResult,
)

# Sprint 48 — stripe connector
from simp.compat.stripe_connector import StripeTestConnector

# Sprint 49 — budget monitor
from simp.compat.budget_monitor import (
    BudgetMonitor,
    BUDGET_MONITOR,
    AlertSeverity,
    BudgetAlert,
)

# Sprint 51 — delivery engine
from simp.server.delivery import (
    DeliveryStatus,
    DeliveryResult,
    DeliveryConfig,
    IntentDeliveryEngine,
    DEFAULT_DELIVERY_ENGINE,
)

# Sprint 52 — task ledger
from simp.server.task_ledger import (
    LedgerConfig,
    TaskLedger,
    TASK_LEDGER,
)

# Sprint 53 — routing engine
from simp.server.routing_engine import (
    RoutingPolicy,
    RoutingDecision,
    RoutingEngine,
)

# Sprint 54 — orchestration
from simp.orchestration.orchestration_manager import (
    OrchestrationStepStatus,
    OrchestrationStep,
    OrchestrationPlan,
    OrchestrationManager,
)

__all__ = [
    # Sprint 1
    "build_security_schemes",
    "get_recommended_scopes_for_agent",
    "map_simp_auth_to_a2a",
    "AgentCardGenerator",
    # Sprint 2
    "capabilities_to_skills",
    "get_capability_map",
    "A2A_TO_SIMP_INTENT",
    "translate_a2a_to_simp",
    "validate_a2a_payload",
    "simp_state_to_a2a",
    "build_a2a_task_status",
    "is_a2a_terminal",
    # Sprint 3
    "StructuredCapability",
    "normalise_capabilities",
    "capabilities_to_a2a_skills",
    # Sprint 4
    "CardCache",
    "CompatError",
    "CompatErrorCode",
    "validate_agent_card",
    # Sprint 5
    "SimpLifecycleState",
    "A2ATaskState",
    "simp_to_a2a_state",
    "build_progress_event",
    "build_completion_event",
    "build_failure_event",
    "events_from_intent_history",
    # Sprint S1
    "get_agent_policy",
    "get_agent_security_schemes",
    "get_agent_security_requirements",
    "AGENT_SAFETY_POLICIES",
    "AGENT_SECURITY_SCHEMES",
    "AGENT_SECURITY_REQUIREMENTS",
    # Sprint S4
    "OpsPolicy",
    "AutonomousOpType",
    "validate_op_request",
    "get_policy_dict",
    "SpendRecord",
    "SPEND_LEDGER",
    # Sprint 41
    "PaymentConnectorConfig",
    "PaymentResult",
    "PaymentConnector",
    "StubPaymentConnector",
    "ALLOWED_CONNECTORS",
    "ALLOWED_VENDOR_CATEGORIES",
    "DISALLOWED_PAYMENT_TYPES",
    "build_connector",
    "validate_payment_request",
    "ConnectorHealthTracker",
    "HEALTH_TRACKER",
    # Sprint 43
    "PaymentProposalStatus",
    "PaymentProposal",
    "ApprovalQueue",
    "PolicyChangeQueue",
    "APPROVAL_QUEUE",
    "POLICY_CHANGE_QUEUE",
    # Sprint 44
    "LivePaymentRecord",
    "LiveSpendLedger",
    "LIVE_LEDGER",
    # Sprint 45
    "ReconciliationResult",
    "run_reconciliation",
    "build_payment_event",
    "PAYMENT_EVENT_KINDS",
    # Sprint 46
    "RollbackManager",
    "ROLLBACK_MANAGER",
    "RollbackState",
    "RollbackRecord",
    "LedgerFrozenError",
    # Sprint 47
    "GateManager",
    "GATE_MANAGER",
    "GateStatus",
    "GateCondition",
    "GateCheckResult",
    # Sprint 48
    "StripeTestConnector",
    # Sprint 49
    "BudgetMonitor",
    "BUDGET_MONITOR",
    "AlertSeverity",
    "BudgetAlert",
    # Sprint 51
    "DeliveryStatus",
    "DeliveryResult",
    "DeliveryConfig",
    "IntentDeliveryEngine",
    "DEFAULT_DELIVERY_ENGINE",
    # Sprint 52
    "LedgerConfig",
    "TaskLedger",
    "TASK_LEDGER",
    # Sprint 53
    "RoutingPolicy",
    "RoutingDecision",
    "RoutingEngine",
    # Sprint 54
    "OrchestrationStepStatus",
    "OrchestrationStep",
    "OrchestrationPlan",
    "OrchestrationManager",
]
