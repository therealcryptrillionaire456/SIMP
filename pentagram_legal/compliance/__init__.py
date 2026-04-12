"""
Compliance Monitoring System for Legal Department.
Provides real-time compliance checking, monitoring, and reporting.
"""

from .compliance_monitor import (
    ComplianceMonitor,
    ComplianceStatus,
    AlertSeverity,
    RegulationSource,
    Regulation,
    ComplianceCheck,
    ComplianceAlert,
    ComplianceReport,
    RegulatoryChange
)

from .regulatory_change_tracker import (
    RegulatoryChangeTracker,
    ChangeSource,
    ChangeImpact,
    RegulatorySource,
    DetectedChange,
    ImpactAssessment
)

from .audit_integration import (
    AuditIntegration,
    AuditType,
    AuditStatus,
    FindingSeverity,
    AuditScope,
    AuditPlan,
    AuditFinding,
    AuditEvidence,
    AuditReport
)

__all__ = [
    # Compliance Monitor
    "ComplianceMonitor",
    "ComplianceStatus",
    "AlertSeverity",
    "RegulationSource",
    "Regulation",
    "ComplianceCheck",
    "ComplianceAlert",
    "ComplianceReport",
    "RegulatoryChange",
    
    # Regulatory Change Tracker
    "RegulatoryChangeTracker",
    "ChangeSource",
    "ChangeImpact",
    "RegulatorySource",
    "DetectedChange",
    "ImpactAssessment",
    
    # Audit Integration
    "AuditIntegration",
    "AuditType",
    "AuditStatus",
    "FindingSeverity",
    "AuditScope",
    "AuditPlan",
    "AuditFinding",
    "AuditEvidence",
    "AuditReport"
]

__version__ = "1.1.0"