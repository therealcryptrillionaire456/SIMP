"""
Bill Russell Protocol (BRP) - Core Security Module

Defensive security protocol for SIMP, providing:
1. Pattern Recognition at Depth
2. Autonomous Reasoning Chains
3. Memory Across Time
4. Threat Database & Alert Orchestration
"""

__version__ = "1.0.0"

from .pattern_recognition import PatternRecognizer
from .reasoning_engine import ReasoningEngine
from .memory_system import MemorySystem
from .threat_database import ThreatDatabase
from .alert_orchestrator import AlertOrchestrator
from .predictive_safety import PredictiveSafetyIntelligence
from .protocol_core import EnhancedBillRussellProtocol

# Backwards-compatible export used by older scripts/tests.
BillRusselProtocolEnhanced = EnhancedBillRussellProtocol
