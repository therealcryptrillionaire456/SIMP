"""
Bill Russel Protocol - Defensive MVP for Mythos Reconstruction
Named after the greatest defensive basketball player ever.

Core Capabilities:
1. Pattern Recognition at Depth
2. Autonomous Reasoning Chains  
3. Memory Across Time
"""

__version__ = "1.0.0"
__author__ = "Mythos Reconstruction Team"

from .pattern_recognition import PatternRecognizer
from .reasoning_engine import ReasoningEngine
from .memory_system import MemorySystem
from .threat_database import ThreatDatabase
from .alert_orchestrator import AlertOrchestrator

class BillRusselProtocol:
    """Main orchestrator for the Bill Russel Protocol."""
    
    def __init__(self, db_path: str = "threat_memory.db", telegram_enabled: bool = False):
        self.pattern_recognizer = PatternRecognizer()
        self.reasoning_engine = ReasoningEngine()
        self.memory_system = MemorySystem(db_path=db_path)
        self.threat_database = ThreatDatabase()
        self.alert_orchestrator = AlertOrchestrator(
            telegram_enabled=telegram_enabled
        )
        
    def process_security_event(self, event_data):
        """
        Process a security event through the full protocol.
        
        Args:
            event_data: Dictionary containing event information
            
        Returns:
            Response action and confidence score
        """
        # 1. Pattern Recognition
        patterns = self.pattern_recognizer.analyze(event_data)
        
        # 2. Check Memory for historical context
        historical_context = self.memory_system.get_context(event_data)
        
        # 3. Autonomous Reasoning
        threat_assessment = self.reasoning_engine.assess_threat(
            patterns=patterns,
            context=historical_context
        )
        
        # 4. Update Memory
        self.memory_system.record_event(event_data, threat_assessment)
        
        # 5. Take Action based on confidence
        response = self.alert_orchestrator.orchestrate_response(
            threat_assessment=threat_assessment,
            event_data=event_data
        )
        
        return response
    
    def weekly_correlation_sweep(self):
        """Perform weekly correlation analysis across all events."""
        return self.memory_system.correlate_events(time_window_days=7)
    
    def get_threat_report(self, days=30):
        """Generate threat report for specified time period."""
        return self.threat_database.generate_report(days=days)