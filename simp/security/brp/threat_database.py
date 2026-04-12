"""
Threat Database for Bill Russel Protocol.
"""

from .memory_system import MemorySystem


class ThreatDatabase(MemorySystem):
    """Threat database extending memory system."""
    
    def __init__(self, db_path: str = "threat_memory.db"):
        super().__init__(db_path)
    
    def generate_report(self, days: int = 30):
        """Generate threat report."""
        return self.get_threat_report(days)