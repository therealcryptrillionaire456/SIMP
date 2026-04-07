"""
SIMP Task Ledger — Sprint 52 (DEPRECATED: renamed to intent_ledger in Sprint 61)

This module re-exports from simp.server.intent_ledger for backward compatibility.
"""

from simp.server.intent_ledger import (
    LedgerConfig,
    IntentLedger as TaskLedger,
    INTENT_LEDGER as TASK_LEDGER,
)

__all__ = ["LedgerConfig", "TaskLedger", "TASK_LEDGER"]
