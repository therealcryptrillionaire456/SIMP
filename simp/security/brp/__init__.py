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
from .forecasting import PredictiveSafetyForecaster
from .multimodal_analysis import MultiModalSafetyAnalyzer
from .predictive_safety import PredictiveSafetyIntelligence
from .deterministic_recurrent_controller import DeterministicRecurrentController
from .cache_consistency_by_namespace import NamespacedRuntimeCache
from .protocol_core import EnhancedBillRussellProtocol

# Backwards-compatible export used by older scripts/tests.
BillRusselProtocolEnhanced = EnhancedBillRussellProtocol
