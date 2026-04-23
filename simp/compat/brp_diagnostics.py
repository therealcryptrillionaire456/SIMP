"""
BRP diagnostics helpers for the A2A/HTTP surface.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from simp.security.brp.quantum_defense import QuantumDefenseAdvisor
from simp.security.brp_bridge import BRPBridge


def build_brp_health_report(data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Return a compact BRP health report with quantum-defense posture."""
    status = BRPBridge.read_operator_status(data_dir=data_dir, recent_limit=25)
    incidents = BRPBridge.read_operator_incidents(data_dir=data_dir, limit=10)
    quantum = QuantumDefenseAdvisor().build_posture_summary()
    return {
        "status": "success",
        "brp": status,
        "incidents": {
            "count": incidents.get("count", 0),
            "open_alerts": incidents.get("open_alerts", 0),
            "critical_open_alerts": incidents.get("critical_open_alerts", 0),
            "state_counts": incidents.get("state_counts", {}),
        },
        "quantum_defense": quantum,
    }
