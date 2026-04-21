"""
Audit Integration System - Build 16 Enhancement
Integrates compliance monitoring with audit systems.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import hashlib
from pathlib import Path

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuditType(Enum):
    """Types of audits."""
    INTERNAL = "internal"
    EXTERNAL = "external"
    REGULATORY = "regulatory"
    ISO = "iso"
    SOC = "soc"  # Service Organization Control
    PCI = "pci"  # Payment Card Industry
    HIPAA = "hipaa"
    SOX = "sox"  # Sarbanes-Oxley
    GDPR = "gdpr"
    CUSTOM = "custom"


class AuditStatus(Enum):
    """Audit status levels."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FOLLOW_UP = "follow_up"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class FindingSeverity(Enum):
    """Audit finding severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


@dataclass
class AuditScope:
    """Scope of an audit."""
    scope_id: str
    name: str
    description: str
    departments: List[str]
    systems: List[str]
    processes: List[str]
    regulations: List[str]
    start_date: datetime
    end_date: datetime
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AuditPlan:
    """Audit plan."""
    plan_id: str
    audit_type: AuditType
    name: str
    description: str
    scope_id: str
    auditor: str
    scheduled_start: datetime
    scheduled_end: datetime
    status: AuditStatus = AuditStatus.PLANNED
    objectives: List[str] = field(default_factory=list)
    criteria: List[str] = field(default_factory=list)
    methodology: str = ""
    resources: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AuditFinding:
    """Audit finding."""
    finding_id: str
    audit_id: str
    title: str
    description: str
    severity: FindingSeverity
    regulation_reference: Optional[str] = None
    process_affected: Optional[str] = None
    system_affected: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    root_cause: Optional[str] = None
    impact: Optional[str] = None
    recommendation: Optional[str] = None
    responsible_party: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "open"  # open, in_progress, resolved, closed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AuditEvidence:
    """Audit evidence."""
    evidence_id: str
    audit_id: str
    finding_id: Optional[str] = None
    name: str
    description: str
    type: str  # document, screenshot, log, interview, test_result
    file_path: Optional[str] = None
    content_hash: Optional[str] = None
    collected_by: str
    collected_at: datetime = field(default_factory=datetime.now)
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AuditReport:
    """Audit report."""
    report_id: str
    audit_id: str
    executive_summary: str
    scope_summary: str
    methodology_summary: str
    findings_summary: Dict[str, int]  # severity -> count
    recommendations: List[str]
    conclusion: str
    prepared_by: str
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    report_date: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class AuditIntegration:
    """
    Audit Integration System.
    Integrates compliance monitoring with audit systems.
    """
    
    def __init__(self, integration_id: str = "audit_integration_001"):
        """
        Initialize Audit Integration.
        
        Args:
            integration_id: Unique integration identifier
        """
        self.integration_id = integration_id
        self.audit_scopes: Dict[str, AuditScope] = {}
        self.audit_plans: Dict[str, AuditPlan] = {}
        self.audit_findings: Dict[str, AuditFinding] = {}
        self.audit_evidence: Dict[str, AuditEvidence] = {}
        self.audit_reports: Dict[str, AuditReport] = {}
        
        # Load default audit scopes
        self._load_default_scopes()
        
        # Metrics
        self.metrics = {
            "total_audits": 0,
            "active_audits": 0,
            "completed_audits": 0,
            "total_findings": 0,
            "open_findings": 0,
            "critical_findings": 0,
            "high_findings": 0,
            "evidence_collected": 0,
            "reports_generated": 0
        }
        
        logger.info(f"Initialized Audit Integration {integration_id}")
    
    def _load_default_scopes(self):
        """Load default audit scopes."""
        default_scopes = [
            AuditScope(
                scope_id="scope_iso_27001",
                name="ISO 27001 Information Security",
                description="Information security management system audit scope",
                departments=["IT", "Security", "Legal", "HR"],
                systems=["Network", "Servers", "Applications", "Databases"],
                processes=["Access Control", "Incident Response", "Risk Management", "Training"],
                regulations=["ISO 27001:2022", "GDPR", "CCPA"],
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=365)
            ),
            AuditScope(
                scope_id="scope_sox",
                name="SOX Financial Controls",
                description="Sarbanes-Oxley financial reporting controls audit",
                departments=["Finance", "Accounting", "Internal Audit"],
                systems=["ERP", "Financial Reporting", "General Ledger"],
                processes=["Financial Close", "Reporting", "Reconciliation", "Disclosure"],
                regulations=["Sarbanes-Oxley Act", "SEC Rules"],
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=180)
            ),
            AuditScope(
                scope_id="scope_gdpr",
                name="GDPR Data Privacy",
                description="General Data Protection Regulation compliance audit",
                departments=["Legal", "IT", "Marketing", "HR"],
                systems=["CRM", "HRIS", "Marketing Automation", "Website"],
                processes=["Data Collection", "Consent Management", "Data Subject Rights", "Breach Notification"],
                regulations=["GDPR", "UK GDPR", "CCPA"],
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=90)
            )
        ]
        
        for scope in default_scopes:
            self.audit_scopes[scope.scope_id] = scope
        
        logger.info(f"Loaded {len(default_scopes)} default audit scopes")
    
    def create_audit_plan(self, plan: AuditPlan) -> str:
        """
        Create a new audit plan.
        
        Args:
            plan: Audit plan
            
        Returns:
            Plan ID
        """
        self.audit_plans[plan.plan_id] = plan
        
        # Update metrics
        self.metrics["total_audits"] += 1
        if plan.status == AuditStatus.IN_PROGRESS:
            self.metrics["active_audits"] += 1
        elif plan.status == AuditStatus.COMPLETED:
            self.metrics["completed_audits"] += 1
        
        logger.info(f"Created audit plan {plan.plan_id}: {plan.name}")
        return plan.plan_id
    
    def start_audit(self, plan_id: str) -> bool:
        """
        Start an audit.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Success status
        """
        if plan_id not in self.audit_plans:
            return False
        
        plan = self.audit_plans[plan_id]
        plan.status = AuditStatus.IN_PROGRESS
        plan.updated_at = datetime.now()
        
        self.metrics["active_audits"] += 1
        
        logger.info(f"Started audit {plan_id}")
        return True
    
    def complete_audit(self, plan_id: str) -> bool:
        """
        Complete an audit.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Success status
        """
        if plan_id not in self.audit_plans:
            return False
        
        plan = self.audit_plans[plan_id]
        plan.status = AuditStatus.COMPLETED
        plan.updated_at = datetime.now()
        
        self.metrics["active_audits"] = max(0, self.metrics["active_audits"] - 1)
        self.metrics["completed_audits"] += 1
        
        logger.info(f"Completed audit {plan_id}")
        return True
    
    def add_finding(self, finding: AuditFinding) -> str:
        """
        Add an audit finding.
        
        Args:
            finding: Audit finding
            
        Returns:
            Finding ID
        """
        self.audit_findings[finding.finding_id] = finding
        
        # Update metrics
        self.metrics["total_findings"] += 1
        if finding.status == "open":
            self.metrics["open_findings"] += 1
        
        if finding.severity == FindingSeverity.CRITICAL:
            self.metrics["critical_findings"] += 1
        elif finding.severity == FindingSeverity.HIGH:
            self.metrics["high_findings"] += 1
        
        logger.info(f"Added audit finding {finding.finding_id}: {finding.title}")
        return finding.finding_id
    
    def add_evidence(self, evidence: AuditEvidence) -> str:
        """
        Add audit evidence.
        
        Args:
            evidence: Audit evidence
            
        Returns:
            Evidence ID
        """
        # Calculate content hash if file path provided
        if evidence.file_path and Path(evidence.file_path).exists():
            try:
                with open(evidence.file_path, 'rb') as f:
                    content = f.read()
                    evidence.content_hash = hashlib.sha256(content).hexdigest()
            except Exception as e:
                logger.warning(f"Could not hash file {evidence.file_path}: {str(e)}")
        
        self.audit_evidence[evidence.evidence_id] = evidence
        self.metrics["evidence_collected"] += 1
        
        logger.info(f"Added audit evidence {evidence.evidence_id}: {evidence.name}")
        return evidence.evidence_id
    
    def generate_audit_report(self, audit_id: str, prepared_by: str) -> Optional[AuditReport]:
        """
        Generate audit report.
        
        Args:
            audit_id: Audit ID
            prepared_by: Person preparing report
            
        Returns:
            Audit report or None if audit not found
        """
        if audit_id not in self.audit_plans:
            return None
        
        plan = self.audit_plans[audit_id]
        
        # Get findings for this audit
        audit_findings = []
        for finding in self.audit_findings.values():
            if finding.audit_id == audit_id:
                audit_findings.append(finding)
        
        # Count findings by severity
        findings_summary = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "informational": 0
        }
        
        for finding in audit_findings:
            severity_key = finding.severity.value
            if severity_key in findings_summary:
                findings_summary[severity_key] += 1
        
        # Generate executive summary
        total_findings = len(audit_findings)
        critical_findings = findings_summary["critical"]
        high_findings = findings_summary["high"]
        
        if critical_findings > 0:
            exec_summary = f"Critical audit with {critical_findings} critical findings requiring immediate attention."
        elif high_findings > 0:
            exec_summary = f"Significant audit with {high_findings} high-risk findings requiring management attention."
        elif total_findings > 0:
            exec_summary = f"Routine audit with {total_findings} findings for improvement."
        else:
            exec_summary = "Clean audit with no findings identified."
        
        # Get scope
        scope = self.audit_scopes.get(plan.scope_id)
        scope_summary = scope.description if scope else "Scope not defined"
        
        # Generate recommendations
        recommendations = []
        if critical_findings > 0:
            recommendations.append(f"Address {critical_findings} critical findings within 30 days")
        if high_findings > 0:
            recommendations.append(f"Address {high_findings} high-risk findings within 60 days")
        
        if total_findings == 0:
            recommendations.append("Maintain current controls and processes")
        else:
            recommendations.append("Implement corrective action plan")
            recommendations.append("Schedule follow-up review in 90 days")
        
        # Create report
        report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        report = AuditReport(
            report_id=report_id,
            audit_id=audit_id,
            executive_summary=exec_summary,
            scope_summary=scope_summary,
            methodology_summary=plan.methodology or "Standard audit procedures",
            findings_summary=findings_summary,
            recommendations=recommendations,
            conclusion="Audit completed according to plan." if plan.status == AuditStatus.COMPLETED else "Audit in progress.",
            prepared_by=prepared_by,
            report_date=datetime.now()
        )
        
        self.audit_reports[report_id] = report
        self.metrics["reports_generated"] += 1
        
        logger.info(f"Generated audit report {report_id} for audit {audit_id}")
        return report
    
    def import_compliance_findings(self, compliance_data: Dict[str, Any]) -> List[str]:
        """
        Import findings from compliance monitoring system.
        
        Args:
            compliance_data: Compliance monitoring data
            
        Returns:
            List of created finding IDs
        """
        finding_ids = []
        
        try:
            # Extract alerts from compliance data
            alerts = compliance_data.get("recent_alerts", [])
            metrics = compliance_data.get("metrics", {})
            
            # Create audit findings from compliance alerts
            for alert in alerts:
                # Map alert severity to finding severity
                alert_severity = alert.get("severity", "medium")
                finding_severity = self._map_severity(alert_severity)
                
                # Create finding
                finding_id = f"finding_comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(finding_ids)}"
                finding = AuditFinding(
                    finding_id=finding_id,
                    audit_id="compliance_audit",  # Default compliance audit
                    title=f"Compliance Alert: {alert.get('title', 'Unknown')}",
                    description=f"Automatically imported from compliance monitoring: {alert.get('description', '')}",
                    severity=finding_severity,
                    regulation_reference="Compliance Monitoring",
                    status="open",
                    recommendation="Review compliance alert and take appropriate action"
                )
                
                self.add_finding(finding)
                finding_ids.append(finding_id)
            
            # Create summary finding from metrics
            if metrics:
                total_alerts = metrics.get("alerts_today", 0)
                if total_alerts > 0:
                    finding_id = f"finding_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    finding = AuditFinding(
                        finding_id=finding_id,
                        audit_id="compliance_audit",
                        title=f"Compliance Monitoring Summary: {total_alerts} alerts today",
                        description=f"Compliance monitoring system detected {total_alerts} alerts. Compliance score: {metrics.get('compliance_score', 0):.1f}%",
                        severity=FindingSeverity.MEDIUM if total_alerts > 5 else FindingSeverity.LOW,
                        regulation_reference="Compliance Monitoring",
                        status="open",
                        recommendation="Review compliance monitoring dashboard regularly"
                    )
                    
                    self.add_finding(finding)
                    finding_ids.append(finding_id)
        
        except Exception as e:
            logger.error(f"Error importing compliance findings: {str(e)}")
        
        logger.info(f"Imported {len(finding_ids)} findings from compliance monitoring")
        return finding_ids
    
    def _map_severity(self, alert_severity: str) -> FindingSeverity:
        """Map alert severity to finding severity."""
        severity_map = {
            "critical": FindingSeverity.CRITICAL,
            "high": FindingSeverity.HIGH,
            "medium": FindingSeverity.MEDIUM,
            "low": FindingSeverity.LOW,
            "info": FindingSeverity.INFORMATIONAL
        }
        
        return severity_map.get(alert_severity.lower(), FindingSeverity.MEDIUM)
    
    def get_audit_dashboard(self) -> Dict[str, Any]:
        """
        Get audit dashboard data.
        
        Returns:
            Dashboard data
        """
        # Update metrics
        self._update_metrics()
        
        # Get recent audits
        recent_audits = []
        for plan in sorted(self.audit_plans.values(),
                          key=lambda p: p.scheduled_start,
                          reverse=True)[:5]:
            recent_audits.append({
                "id": plan.plan_id,
                "name": plan.name,
                "type": plan.audit_type.value,
                "status": plan.status.value,
                "scheduled_start": plan.scheduled_start.isoformat(),
                "scheduled_end": plan.scheduled_end.isoformat(),
                "auditor": plan.auditor
            })
        
        # Get recent findings
        recent_findings = []
        for finding in sorted(self.audit_findings.values(),
                             key=lambda f: f.created_at,
                             reverse=True)[:10]:
            recent_findings.append({
                "id": finding.finding_id,
                "title": finding.title,
                "severity": finding.severity.value,
                "status": finding.status,
                "created_at": finding.created_at.isoformat(),
                "audit_id": finding.audit_id
            })
        
        # Get upcoming audits
        upcoming_audits = []
        now = datetime.now()
        for plan in self.audit_plans.values():
            if plan.scheduled_start > now and plan.status == AuditStatus.PLANNED:
                upcoming_audits.append({
                    "id": plan.plan_id,
                    "name": plan.name,
                    "scheduled_start": plan.scheduled_start.isoformat(),
                    "days_until": (plan.scheduled_start - now).days
                })
        
        # Sort upcoming audits by date
        upcoming_audits.sort(key=lambda x: x["days_until"])
        
        return {
            "metrics": self.metrics,
            "recent_audits": recent_audits,
            "recent_findings": recent_findings,
            "upcoming_audits": upcoming_audits[:5],
            "total_reports": len(self.audit_reports),
            "timestamp": datetime.now().isoformat()
        }
    
    def _update_metrics(self):
        """Update audit metrics."""
        # Count open findings
        open_findings = sum(1 for f in self.audit_findings.values() if f.status == "open")
        self.metrics["open_findings"] = open_findings
        
        # Count active audits
        active_audits = sum(1 for p in self.audit_plans.values() 
                           if p.status == AuditStatus.IN_PROGRESS)
        self.metrics["active_audits"] = active_audits
        
        # Count completed audits
        completed_audits = sum(1 for p in self.audit_plans.values() 
                              if p.status == AuditStatus.COMPLETED)
        self.metrics["completed_audits"] = completed_audits
        
        # Count critical and high findings
        critical = sum(1 for f in self.audit_findings.values() 
                      if f.severity == FindingSeverity.CRITICAL and f.status == "open")
        high = sum(1 for f in self.audit_findings.values() 
                  if f.severity == FindingSeverity.HIGH and f.status == "open")
        
        self.metrics["critical_findings"] = critical
        self.metrics["high_findings"] = high
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get integration status.
        
        Returns:
            Status information
        """
        return {
            "integration_id": self.integration_id,
            "scopes_count": len(self.audit_scopes),
            "plans_count": len(self.audit_plans),
            "findings_count": len(self.audit_findings),
            "evidence_count": len(self.audit_evidence),
            "reports_count": len(self.audit_reports),
            "metrics": self.metrics,
            "timestamp": datetime.now().isoformat()
        }


def test_audit_integration():
    """Test function for Audit Integration."""
    print("Testing Audit Integration System...")
    
    # Create integration instance
    integration = AuditIntegration()
    
    # Test 1: Get initial status
    print("\n1. Testing initial status...")
    status = integration.get_status()
    print(f"Integration ID: {status['integration_id']}")
    print(f"Audit scopes: {status['scopes_count']}")
    print(f"Audit plans: {status['plans_count']}")
    
    # Test 2: Create audit plan
    print("\n2. Creating audit plan...")
    plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    plan = AuditPlan(
        plan_id=plan_id,
        audit_type=AuditType.ISO,
        name="ISO 27001 Internal Audit Q2 2026",
        description="Quarterly internal audit of information security controls",
        scope_id="scope_iso_27001",
        auditor="Internal Audit Team",
        scheduled_start=datetime.now() + timedelta(days=7),
        scheduled_end=datetime.now() + timedelta(days=14),
        objectives=[
            "Assess effectiveness of ISMS",
            "Verify compliance with ISO 27001 requirements",
            "Identify improvement opportunities"
        ],
        criteria=["ISO 27001:2022", "Internal policies and procedures"],
        methodology="Document review, interviews, testing"
    )
    integration.create_audit_plan(plan)
    print(f"Created audit plan: {plan.name}")
    
    # Test 3: Start audit
    print("\n3. Starting audit...")
    success = integration.start_audit(plan_id)
    print(f"Audit started: {success}")
    
    # Test 4: Add audit finding
    print("\n4. Adding audit finding...")
    finding_id = f"finding_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    finding = AuditFinding(
        finding_id=finding_id,
        audit_id=plan_id,
        title="Weak Password Policy",
        description="Password policy does not enforce sufficient complexity requirements",
        severity=FindingSeverity.HIGH,
        regulation_reference="ISO 27001 A.9.4.1",
        process_affected="Access Control",
        system_affected="Active Directory",
        root_cause="Policy not updated to reflect current security standards",
        impact="Increased risk of unauthorized access",
        recommendation="Update password policy to require 12+ characters with complexity",
        responsible_party="Security Team",
        due_date=datetime.now() + timedelta(days=30)
    )
    integration.add_finding(finding)
    print(f"Added finding: {finding.title}")
    
    # Test 5: Add audit evidence
    print("\n5. Adding audit evidence...")
    evidence_id = f"evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    evidence = AuditEvidence(
        evidence_id=evidence_id,
        audit_id=plan_id,
        finding_id=finding_id,
        name="Password Policy Document",
        description="Current password policy document",
        type="document",
        collected_by="Auditor 001",
        collected_at=datetime.now()
    )
    integration.add_evidence(evidence)
    print(f"Added evidence: {evidence.name}")
    
    # Test 6: Complete audit
    print("\n6. Completing audit...")
    success = integration.complete_audit(plan_id)
    print(f"Audit completed: {success}")
    
    # Test 7: Generate audit report
    print("\n7. Generating audit report...")
    report = integration.generate_audit_report(plan_id, "Chief Audit Executive")
    if report:
        print(f"Generated report: {report.report_id}")
        print(f"Executive summary: {report.executive_summary[:100]}...")
        print(f"Findings summary: {report.findings_summary}")
    else:
        print("Failed to generate report")
    
    # Test 8: Import compliance findings
    print("\n8. Importing compliance findings...")
    compliance_data = {
        "recent_alerts": [
            {
                "title": "GDPR Data Processing Violation",
                "description": "Personal data processed without proper consent",
                "severity": "high"
            },
            {
                "title": "SOX Control Deficiency",
                "description": "Financial reporting control not operating effectively",
                "severity": "critical"
            }
        ],
        "metrics": {
            "alerts_today": 5,
            "compliance_score": 85.5
        }
    }
    finding_ids = integration.import_compliance_findings(compliance_data)
    print(f"Imported {len(finding_ids)} compliance findings")
    
    # Test 9: Get dashboard data
    print("\n9. Getting dashboard data...")
    dashboard = integration.get_audit_dashboard()
    print(f"Total audits: {dashboard['metrics']['total_audits']}")
    print(f"Active audits: {dashboard['metrics']['active_audits']}")
    print(f"Open findings: {dashboard['metrics']['open_findings']}")
    print(f"Recent findings: {len(dashboard['recent_findings'])}")
    
    # Final status
    print("\n10. Final status...")
    final_status = integration.get_status()
    print(f"Total plans: {final_status['plans_count']}")
    print(f"Total findings: {final_status['findings_count']}")
    print(f"Total evidence: {final_status['evidence_count']}")
    print(f"Total reports: {final_status['reports_count']}")
    
    print("\nAudit Integration System test completed successfully!")


if __name__ == "__main__":
    test_audit_integration()