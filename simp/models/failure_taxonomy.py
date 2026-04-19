"""
SIMP Failure Taxonomy — Failure classification, retry policies, and fallback logic.

Provides an enum of failure classes and a handler that decides whether to retry,
which delay to use, and which fallback agent to try.
"""

from enum import Enum
from typing import Any, Dict, List, Optional


class FailureClass(str, Enum):
    """Classification of why an intent/task failed."""
    RATE_LIMITED = "rate_limited"
    SCHEMA_INVALID = "schema_invalid"
    POLICY_DENIED = "policy_denied"
    AGENT_UNAVAILABLE = "agent_unavailable"
    TIMEOUT = "timeout"
    EXECUTION_FAILED = "execution_failed"
    CLAIM_CONFLICT = "claim_conflict"


# Static retry policy table
_RETRY_POLICIES: Dict[str, Dict[str, Any]] = {
    FailureClass.RATE_LIMITED: {
        "should_retry": True,
        "delay_seconds": 60,
        "max_retries": 3,
        "requeue": True,
    },
    FailureClass.SCHEMA_INVALID: {
        "should_retry": False,
        "delay_seconds": 0,
        "max_retries": 0,
        "requeue": False,
    },
    FailureClass.POLICY_DENIED: {
        "should_retry": False,
        "delay_seconds": 0,
        "max_retries": 0,
        "requeue": False,
    },
    FailureClass.AGENT_UNAVAILABLE: {
        "should_retry": True,
        "delay_seconds": 10,
        "max_retries": 2,
        "requeue": True,
    },
    FailureClass.TIMEOUT: {
        "should_retry": True,
        "delay_seconds": 5,
        "max_retries": 1,
        "requeue": True,
    },
    FailureClass.EXECUTION_FAILED: {
        "should_retry": True,
        "delay_seconds": 5,
        "max_retries": 1,
        "requeue": True,
    },
    FailureClass.CLAIM_CONFLICT: {
        "should_retry": False,
        "delay_seconds": 0,
        "max_retries": 0,
        "requeue": False,
    },
}


class FailureHandler:
    """Decides what to do when an intent/task fails."""

    def classify_failure(self, error_response: Dict[str, Any]) -> FailureClass:
        """
        Classify a failure from an error response dict.

        Looks at 'error_code' and 'error_message' fields to determine class.
        """
        code = str(error_response.get("error_code", "")).lower()
        msg = str(error_response.get("error_message", error_response.get("error", ""))).lower()

        if "rate_limit" in code or "rate_limit" in msg or "429" in code:
            return FailureClass.RATE_LIMITED
        if "schema" in code or "validation" in msg or "invalid" in code:
            return FailureClass.SCHEMA_INVALID
        if "policy" in code or "denied" in msg or "forbidden" in code:
            return FailureClass.POLICY_DENIED
        if "not_found" in code or "unavailable" in msg or "agent_not_found" in code:
            return FailureClass.AGENT_UNAVAILABLE
        if "timeout" in code or "timeout" in msg or "timed out" in msg:
            return FailureClass.TIMEOUT
        if "claim" in code or "claim_conflict" in code:
            return FailureClass.CLAIM_CONFLICT

        return FailureClass.EXECUTION_FAILED

    def get_retry_policy(self, failure_class: FailureClass) -> Dict[str, Any]:
        """Return the retry policy for a given failure class."""
        return dict(_RETRY_POLICIES.get(failure_class, _RETRY_POLICIES[FailureClass.EXECUTION_FAILED]))

    def get_fallback_agent(
        self,
        failure_class: FailureClass,
        task_type: str,
        builder_pool: Any,
        exclude: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Return a fallback agent ID based on failure class and task type.

        Uses the builder pool to find the next available agent, excluding
        the agent that failed.
        """
        if failure_class in (FailureClass.SCHEMA_INVALID, FailureClass.POLICY_DENIED, FailureClass.CLAIM_CONFLICT):
            return None

        if builder_pool is None:
            return None

        return builder_pool.get_builder(task_type, exclude=exclude or [])
