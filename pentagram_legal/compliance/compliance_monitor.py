"""
Compliance Monitoring System - Build 16
Real-time compliance checking, monitoring dashboard, and automated reporting.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import asyncio
from pathlib import Path
import threading
import time

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ComplianceStatus(Enum):
    """Compliance status levels."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    AT_RISK = "at_risk"
    PENDING_REVIEW = "pending_review"
    EXEMPT = "exempt"
    NOT_APPLICABLE = "not_applicable"


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RegulationSource(Enum):
    """Sources of regulations."""
    SEC = "sec"
    FINRA = "finra"
    CFTC = "cftc"
    OCC = "occ"
    FDIC = "fdic"
    FED = "fed"
    STATE = "state"
    INTERNATIONAL = "international"
    INDUSTRY = "industry"
    INTERNAL = "internal"


@dataclass
class Regulation:
    """Regulation definition."""
    regulation_id: str
    name: str
    source: RegulationSource
    jurisdiction: str
    effective_date: datetime
    summary: str
    requirements: List[str]
    penalties: List[str]
    compliance_deadline: Optional[datetime] = None
    last_amended: Optional[datetime] = None
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ComplianceCheck:
    """Individual compliance check."""
    check_id: str
    regulation_id: str
    check_name: str
    description: str
    frequency: str  # daily, weekly, monthly, quarterly, annually, realtime
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: ComplianceStatus = ComplianceStatus.PENDING_REVIEW
    findings: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ComplianceAlert:
    """Compliance alert."""
    alert_id: str
    check_id: str
    severity: AlertSeverity
    title: str
    description: str
    affected_entities: List[str]
    recommended_actions: List[str]
    deadline: Optional[datetime] = None
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ComplianceReport:
    """Compliance report."""
    report_id: str
    period_start: datetime
    period_end: datetime
    checks_performed: int
    checks_passed: int
    checks_failed: int
    alerts_generated: int
    critical_alerts: int
    high_alerts: int
    medium_alerts: int
    low_alerts: int
    compliance_score: float
    executive_summary: str
    detailed_findings: List[Dict[str, Any]]
    recommendations: List[str]
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class RegulatoryChange:
    """Regulatory change tracking."""
    change_id: str
    regulation_id: str
    change_type: str  # new, amendment, repeal, guidance
    description: str
    effective_date: datetime
    impact_assessment: str
    affected_areas: List[str]
    action_required: bool
    action_deadline: Optional[datetime] = None
    status: str = "pending_review"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class ComplianceMonitor:
    """
    Compliance Monitoring System.
    Provides real-time compliance checking, monitoring dashboard, and automated reporting.
    """
    
    def __init__(self, monitor_id: str = "compliance_monitor_001"):
        """
        Initialize Compliance Monitor.
        
        Args:
            monitor_id: Unique monitor identifier
        """
        self.monitor_id = monitor_id
        self.regulations: Dict[str, Regulation] = {}
        self.compliance_checks: Dict[str, ComplianceCheck] = {}
        self.active_alerts: Dict[str, ComplianceAlert] = {}
        self.compliance_reports: Dict[str, ComplianceReport] = {}
        self.regulatory_changes: Dict[str, RegulatoryChange] = {}
        
        # Dashboard metrics
        self.metrics = {
            "total_regulations": 0,
            "active_checks": 0,
            "checks_today": 0,
            "alerts_today": 0,
            "compliance_score": 100.0,
            "last_report_date": None,
            "next_audit_date": None,
            "critical_violations": 0,
            "pending_reviews": 0
        }
        
        # Monitoring thread
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Load sample regulations
        self._load_sample_regulations()
        self._create_default_checks()
        
        logger.info(f"Initialized Compliance Monitor {monitor_id}")
    
    def _load_sample_regulations(self):
        """Load sample regulations for demonstration."""
        # SEC Regulations
        sec_regs = [
            Regulation(
                regulation_id="reg_sec_001",
                name="SEC Rule 10b-5",
                source=RegulationSource.SEC,
                jurisdiction="US",
                effective_date=datetime(1942, 1, 1),
                summary="Anti-fraud provision prohibiting material misstatements or omissions",
                requirements=[
                    "Prohibit material misstatements",
                    "Prohibit material omissions",
                    "Prohibit fraudulent or deceptive practices",
                    "Maintain accurate financial disclosures"
                ],
                penalties=[
                    "Civil penalties up to $5 million",
                    "Criminal penalties up to 20 years imprisonment",
                    "Disgorgement of profits",
                    "Industry bar"
                ]
            ),
            Regulation(
                regulation_id="reg_sec_002",
                name="Sarbanes-Oxley Act (SOX)",
                source=RegulationSource.SEC,
                jurisdiction="US",
                effective_date=datetime(2002, 7, 30),
                summary="Corporate accountability and financial transparency requirements",
                requirements=[
                    "CEO/CFO certification of financial statements",
                    "Internal control assessments",
                    "Auditor independence",
                    "Enhanced financial disclosures",
                    "Whistleblower protection"
                ],
                penalties=[
                    "Fines up to $5 million",
                    "Imprisonment up to 20 years",
                    "Forfeiture of bonuses",
                    "Delisting from exchanges"
                ]
            )
        ]
        
        # FINRA Regulations
        finra_regs = [
            Regulation(
                regulation_id="reg_finra_001",
                name="FINRA Rule 2111",
                source=RegulationSource.FINRA,
                jurisdiction="US",
                effective_date=datetime(2011, 7, 9),
                summary="Suitability Rule requiring reasonable basis for recommendations",
                requirements=[
                    "Reasonable basis suitability",
                    "Customer-specific suitability",
                    "Quantitative suitability",
                    "Documentation of suitability analysis"
                ],
                penalties=[
                    "Fines",
                    "Suspension",
                    "Expulsion",
                    "Restitution to customers"
                ]
            )
        ]
        
        # Load all regulations
        for reg in sec_regs + finra_regs:
            self.regulations[reg.regulation_id] = reg
        
        self.metrics["total_regulations"] = len(self.regulations)
    
    def _create_default_checks(self):
        """Create default compliance checks."""
        checks = [
            ComplianceCheck(
                check_id="check_001",
                regulation_id="reg_sec_001",
                check_name="Financial Disclosure Accuracy",
                description="Verify accuracy of financial disclosures and statements",
                frequency="quarterly",
                next_run=datetime.now() + timedelta(days=7)
            ),
            ComplianceCheck(
                check_id="check_002",
                regulation_id="reg_sec_002",
                check_name="SOX Internal Controls",
                description="Assess effectiveness of internal controls over financial reporting",
                frequency="annually",
                next_run=datetime.now() + timedelta(days=30)
            ),
            ComplianceCheck(
                check_id="check_003",
                regulation_id="reg_finra_001",
                check_name="Investment Suitability",
                description="Review investment recommendations for suitability",
                frequency="monthly",
                next_run=datetime.now() + timedelta(days=1)
            ),
            ComplianceCheck(
                check_id="check_004",
                regulation_id="reg_sec_001",
                check_name="Insider Trading Monitoring",
                description="Monitor for potential insider trading activities",
                frequency="realtime",
                next_run=datetime.now()
            )
        ]
        
        for check in checks:
            self.compliance_checks[check.check_id] = check
        
        self.metrics["active_checks"] = len(self.compliance_checks)
    
    def start_monitoring(self):
        """Start the compliance monitoring system."""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("Compliance monitoring started")
    
    def stop_monitoring(self):
        """Stop the compliance monitoring system."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Compliance monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Run scheduled checks
                self._run_scheduled_checks()
                
                # Check for regulatory changes
                self._check_regulatory_changes()
                
                # Update dashboard metrics
                self._update_metrics()
                
                # Sleep for 60 seconds
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(10)
    
    def _run_scheduled_checks(self):
        """Run scheduled compliance checks."""
        now = datetime.now()
        checks_run = 0
        
        # Create a copy of items to avoid dictionary changed during iteration
        checks_to_run = []
        for check_id, check in self.compliance_checks.items():
            if check.next_run and check.next_run <= now:
                checks_to_run.append((check_id, check))
        
        for check_id, check in checks_to_run:
            try:
                # Run the check
                result = self._execute_compliance_check(check)
                
                # Update check status
                check.last_run = now
                check.status = result["status"]
                check.findings = result["findings"]
                check.updated_at = now
                
                # Schedule next run
                check.next_run = self._calculate_next_run(check.frequency)
                
                # Generate alerts if needed
                if result["status"] in [ComplianceStatus.NON_COMPLIANT, ComplianceStatus.AT_RISK]:
                    self._generate_alert(check, result)
                
                checks_run += 1
                
                logger.info(f"Ran compliance check {check.check_name}: {result['status'].value}")
                
            except Exception as e:
                logger.error(f"Error running compliance check {check_id}: {str(e)}")
        
        if checks_run > 0:
            self.metrics["checks_today"] += checks_run
    
    def _execute_compliance_check(self, check: ComplianceCheck) -> Dict[str, Any]:
        """
        Execute a compliance check.
        
        Args:
            check: Compliance check to execute
            
        Returns:
            Check results
        """
        # This is a simulation - in production, this would connect to actual systems
        regulation = self.regulations.get(check.regulation_id)
        
        if not regulation:
            return {
                "status": ComplianceStatus.NOT_APPLICABLE,
                "findings": [{"error": f"Regulation {check.regulation_id} not found"}],
                "score": 0.0
            }
        
        # Simulate check results based on check type
        import random
        
        if "financial" in check.check_name.lower():
            # Financial checks have 85% pass rate
            if random.random() < 0.85:
                status = ComplianceStatus.COMPLIANT
                findings = [{"finding": "Financial disclosures accurate and complete", "severity": "low"}]
                score = 95.0
            else:
                status = ComplianceStatus.AT_RISK
                findings = [
                    {"finding": "Minor discrepancies in footnote disclosures", "severity": "medium"},
                    {"finding": "Recommend enhanced review process", "severity": "low"}
                ]
                score = 75.0
        
        elif "internal" in check.check_name.lower():
            # Internal control checks have 90% pass rate
            if random.random() < 0.90:
                status = ComplianceStatus.COMPLIANT
                findings = [{"finding": "Internal controls effective and properly documented", "severity": "low"}]
                score = 98.0
            else:
                status = ComplianceStatus.NON_COMPLIANT
                findings = [
                    {"finding": "Control deficiency in account reconciliation process", "severity": "high"},
                    {"finding": "Immediate remediation required", "severity": "critical"}
                ]
                score = 60.0
        
        elif "insider" in check.check_name.lower():
            # Insider trading checks have 95% pass rate
            if random.random() < 0.95:
                status = ComplianceStatus.COMPLIANT
                findings = [{"finding": "No suspicious trading activity detected", "severity": "low"}]
                score = 99.0
            else:
                status = ComplianceStatus.AT_RISK
                findings = [
                    {"finding": "Unusual trading pattern detected", "severity": "medium"},
                    {"finding": "Requires further investigation", "severity": "low"}
                ]
                score = 70.0
        
        else:
            # Default check
            status = ComplianceStatus.COMPLIANT
            findings = [{"finding": "Check completed successfully", "severity": "low"}]
            score = 100.0
        
        return {
            "status": status,
            "findings": findings,
            "score": score,
            "regulation": regulation.name,
            "check_name": check.check_name
        }
    
    def _calculate_next_run(self, frequency: str) -> datetime:
        """
        Calculate next run time based on frequency.
        
        Args:
            frequency: Check frequency
            
        Returns:
            Next run datetime
        """
        now = datetime.now()
        
        if frequency == "daily":
            return now + timedelta(days=1)
        elif frequency == "weekly":
            return now + timedelta(weeks=1)
        elif frequency == "monthly":
            return now + timedelta(days=30)
        elif frequency == "quarterly":
            return now + timedelta(days=90)
        elif frequency == "annually":
            return now + timedelta(days=365)
        elif frequency == "realtime":
            return now + timedelta(minutes=5)
        else:
            return now + timedelta(days=1)
    
    def _generate_alert(self, check: ComplianceCheck, result: Dict[str, Any]):
        """Generate compliance alert."""
        alert_id = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Determine severity based on status
        if result["status"] == ComplianceStatus.NON_COMPLIANT:
            severity = AlertSeverity.HIGH
        elif result["status"] == ComplianceStatus.AT_RISK:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW
        
        regulation = self.regulations.get(check.regulation_id)
        
        alert = ComplianceAlert(
            alert_id=alert_id,
            check_id=check.check_id,
            severity=severity,
            title=f"Compliance Issue: {check.check_name}",
            description=f"Check {check.check_name} found {result['status'].value} status",
            affected_entities=["Legal Department", "Finance Department", "Compliance Office"],
            recommended_actions=[
                "Review findings immediately",
                "Assign remediation owner",
                "Schedule follow-up review",
                "Update compliance documentation"
            ],
            deadline=datetime.now() + timedelta(days=7)
        )
        
        self.active_alerts[alert_id] = alert
        self.metrics["alerts_today"] += 1
        
        if severity == AlertSeverity.CRITICAL:
            self.metrics["critical_violations"] += 1
        
        logger.info(f"Generated compliance alert {alert_id}: {alert.title}")
    
    def _check_regulatory_changes(self):
        """Check for regulatory changes (simulated)."""
        # In production, this would connect to regulatory databases
        # For now, we'll simulate occasional changes
        import random
        
        if random.random() < 0.01:  # 1% chance per check
            change_id = f"change_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Pick a random regulation
            if self.regulations:
                reg_id = random.choice(list(self.regulations.keys()))
                regulation = self.regulations[reg_id]
                
                change = RegulatoryChange(
                    change_id=change_id,
                    regulation_id=reg_id,
                    change_type=random.choice(["amendment", "guidance", "interpretation"]),
                    description=f"Updated guidance for {regulation.name}",
                    effective_date=datetime.now() + timedelta(days=30),
                    impact_assessment="Moderate impact expected on compliance procedures",
                    affected_areas=["Reporting", "Documentation", "Training"],
                    action_required=True,
                    action_deadline=datetime.now() + timedelta(days=14)
                )
                
                self.regulatory_changes[change_id] = change
                logger.info(f"Detected regulatory change: {change.description}")
    
    def _update_metrics(self):
        """Update dashboard metrics."""
        # Calculate compliance score
        total_checks = len(self.compliance_checks)
        if total_checks > 0:
            compliant_checks = sum(1 for c in self.compliance_checks.values() 
                                 if c.status == ComplianceStatus.COMPLIANT)
            self.metrics["compliance_score"] = (compliant_checks / total_checks) * 100
        
        # Count pending reviews
        self.metrics["pending_reviews"] = sum(1 for c in self.compliance_checks.values() 
                                            if c.status == ComplianceStatus.PENDING_REVIEW)
        
        # Update last report date if we have reports
        if self.compliance_reports:
            latest_report = max(self.compliance_reports.values(), 
                              key=lambda r: r.generated_at)
            self.metrics["last_report_date"] = latest_report.generated_at
        
        # Set next audit date (quarterly)
        now = datetime.now()
        next_quarter = ((now.month - 1) // 3 + 1) * 3
        if next_quarter > 12:
            next_quarter = 3
            next_year = now.year + 1
        else:
            next_year = now.year
        
        self.metrics["next_audit_date"] = datetime(next_year, next_quarter, 1)
    
    def generate_compliance_report(self, period_start: datetime, period_end: datetime) -> ComplianceReport:
        """
        Generate compliance report for a period.
        
        Args:
            period_start: Report period start
            period_end: Report period end
            
        Returns:
            Compliance report
        """
        report_id = f"report_{period_start.strftime('%Y%m')}"
        
        # Collect checks in period
        period_checks = []
        for check in self.compliance_checks.values():
            if check.last_run and period_start <= check.last_run <= period_end:
                period_checks.append(check)
        
        # Count results
        checks_performed = len(period_checks)
        checks_passed = sum(1 for c in period_checks if c.status == ComplianceStatus.COMPLIANT)
        checks_failed = sum(1 for c in period_checks if c.status == ComplianceStatus.NON_COMPLIANT)
        
        # Count alerts
        period_alerts = []
        for alert in self.active_alerts.values():
            if period_start <= alert.created_at <= period_end:
                period_alerts.append(alert)
        
        alerts_generated = len(period_alerts)
        critical_alerts = sum(1 for a in period_alerts if a.severity == AlertSeverity.CRITICAL)
        high_alerts = sum(1 for a in period_alerts if a.severity == AlertSeverity.HIGH)
        medium_alerts = sum(1 for a in period_alerts if a.severity == AlertSeverity.MEDIUM)
        low_alerts = sum(1 for a in period_alerts if a.severity == AlertSeverity.LOW)
        
        # Calculate compliance score
        if checks_performed > 0:
            compliance_score = (checks_passed / checks_performed) * 100
        else:
            compliance_score = 100.0
        
        # Generate executive summary
        if compliance_score >= 90:
            summary = "Excellent compliance performance with minimal issues."
        elif compliance_score >= 80:
            summary = "Good compliance performance with some areas for improvement."
        elif compliance_score >= 70:
            summary = "Adequate compliance performance requiring attention to several areas."
        else:
            summary = "Poor compliance performance requiring immediate corrective action."
        
        # Detailed findings
        detailed_findings = []
        for check in period_checks:
            if check.findings:
                detailed_findings.append({
                    "check_name": check.check_name,
                    "status": check.status.value,
                    "findings": check.findings,
                    "last_run": check.last_run.isoformat() if check.last_run else None
                })
        
        # Recommendations
        recommendations = []
        if checks_failed > 0:
            recommendations.append(f"Address {checks_failed} failed compliance checks")
        if critical_alerts > 0:
            recommendations.append(f"Resolve {critical_alerts} critical alerts immediately")
        if compliance_score < 80:
            recommendations.append("Implement enhanced compliance training program")
        
        # Create report
        report = ComplianceReport(
            report_id=report_id,
            period_start=period_start,
            period_end=period_end,
            checks_performed=checks_performed,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            alerts_generated=alerts_generated,
            critical_alerts=critical_alerts,
            high_alerts=high_alerts,
            medium_alerts=medium_alerts,
            low_alerts=low_alerts,
            compliance_score=compliance_score,
            executive_summary=summary,
            detailed_findings=detailed_findings,
            recommendations=recommendations
        )
        
        self.compliance_reports[report_id] = report
        
        logger.info(f"Generated compliance report {report_id} with score {compliance_score:.1f}%")
        
        return report
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get dashboard data for monitoring interface.
        
        Returns:
            Dashboard data
        """
        # Update metrics first
        self._update_metrics()
        
        # Get recent alerts
        recent_alerts = []
        for alert in sorted(self.active_alerts.values(), 
                          key=lambda a: a.created_at, 
                          reverse=True)[:10]:
            recent_alerts.append({
                "id": alert.alert_id,
                "title": alert.title,
                "severity": alert.severity.value,
                "created": alert.created_at.isoformat(),
                "acknowledged": alert.acknowledged,
                "resolved": alert.resolved
            })
        
        # Get upcoming checks
        upcoming_checks = []
        for check in sorted(self.compliance_checks.values(),
                          key=lambda c: c.next_run or datetime.max)[:5]:
            upcoming_checks.append({
                "id": check.check_id,
                "name": check.check_name,
                "frequency": check.frequency,
                "next_run": check.next_run.isoformat() if check.next_run else None,
                "status": check.status.value
            })
        
        # Get regulatory changes
        recent_changes = []
        for change in sorted(self.regulatory_changes.values(),
                           key=lambda c: c.created_at,
                           reverse=True)[:5]:
            recent_changes.append({
                "id": change.change_id,
                "type": change.change_type,
                "description": change.description,
                "effective_date": change.effective_date.isoformat(),
                "action_required": change.action_required
            })
        
        return {
            "metrics": self.metrics,
            "recent_alerts": recent_alerts,
            "upcoming_checks": upcoming_checks,
            "recent_changes": recent_changes,
            "total_alerts": len(self.active_alerts),
            "total_changes": len(self.regulatory_changes),
            "monitoring_active": self.monitoring_active,
            "timestamp": datetime.now().isoformat()
        }
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge a compliance alert.
        
        Args:
            alert_id: Alert ID
            acknowledged_by: Person acknowledging
            
        Returns:
            Success status
        """
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now()
        alert.updated_at = datetime.now()
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True
    
    def resolve_alert(self, alert_id: str, resolved_by: str, resolution_notes: str = "") -> bool:
        """
        Resolve a compliance alert.
        
        Args:
            alert_id: Alert ID
            resolved_by: Person resolving
            resolution_notes: Resolution notes
            
        Returns:
            Success status
        """
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.resolved = True
        alert.resolved_by = resolved_by
        alert.resolved_at = datetime.now()
        alert.updated_at = datetime.now()
        
        # Add resolution notes to findings
        if resolution_notes:
            alert.findings = alert.findings or []
            alert.findings.append({
                "type": "resolution",
                "notes": resolution_notes,
                "timestamp": datetime.now().isoformat(),
                "resolved_by": resolved_by
            })
        
        logger.info(f"Alert {alert_id} resolved by {resolved_by}")
        return True
    
    def add_regulation(self, regulation: Regulation) -> str:
        """
        Add a new regulation to monitor.
        
        Args:
            regulation: Regulation to add
            
        Returns:
            Regulation ID
        """
        self.regulations[regulation.regulation_id] = regulation
        self.metrics["total_regulations"] = len(self.regulations)
        
        logger.info(f"Added regulation {regulation.regulation_id}: {regulation.name}")
        return regulation.regulation_id
    
    def add_compliance_check(self, check: ComplianceCheck) -> str:
        """
        Add a new compliance check.
        
        Args:
            check: Compliance check to add
            
        Returns:
            Check ID
        """
        self.compliance_checks[check.check_id] = check
        self.metrics["active_checks"] = len(self.compliance_checks)
        
        logger.info(f"Added compliance check {check.check_id}: {check.check_name}")
        return check.check_id
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get monitor status.
        
        Returns:
            Status information
        """
        return {
            "monitor_id": self.monitor_id,
            "monitoring_active": self.monitoring_active,
            "regulations_count": len(self.regulations),
            "checks_count": len(self.compliance_checks),
            "alerts_count": len(self.active_alerts),
            "reports_count": len(self.compliance_reports),
            "changes_count": len(self.regulatory_changes),
            "metrics": self.metrics,
            "timestamp": datetime.now().isoformat()
        }


def test_compliance_monitor():
    """Test function for Compliance Monitor."""
    print("Testing Compliance Monitoring System...")
    
    # Create monitor instance
    monitor = ComplianceMonitor()
    
    # Test 1: Get initial status
    print("\n1. Testing initial status...")
    status = monitor.get_status()
    print(f"Monitor ID: {status['monitor_id']}")
    print(f"Regulations: {status['regulations_count']}")
    print(f"Compliance checks: {status['checks_count']}")
    
    # Test 2: Get dashboard data
    print("\n2. Testing dashboard data...")
    dashboard = monitor.get_dashboard_data()
    print(f"Compliance score: {dashboard['metrics']['compliance_score']:.1f}%")
    print(f"Active checks: {dashboard['metrics']['active_checks']}")
    
    # Test 3: Start monitoring
    print("\n3. Starting monitoring...")
    monitor.start_monitoring()
    print("Monitoring started")
    
    # Test 4: Generate compliance report
    print("\n4. Generating compliance report...")
    period_start = datetime.now() - timedelta(days=30)
    period_end = datetime.now()
    report = monitor.generate_compliance_report(period_start, period_end)
    print(f"Report ID: {report.report_id}")
    print(f"Checks performed: {report.checks_performed}")
    print(f"Compliance score: {report.compliance_score:.1f}%")
    
    # Test 5: Add new regulation
    print("\n5. Adding new regulation...")
    new_reg = Regulation(
        regulation_id="reg_test_001",
        name="Test Regulation",
        source=RegulationSource.INTERNAL,
        jurisdiction="Global",
        effective_date=datetime.now(),
        summary="Test regulation for demonstration",
        requirements=["Requirement 1", "Requirement 2"],
        penalties=["Penalty 1", "Penalty 2"]
    )
    monitor.add_regulation(new_reg)
    print(f"Added regulation: {new_reg.name}")
    
    # Test 6: Add new compliance check
    print("\n6. Adding new compliance check...")
    new_check = ComplianceCheck(
        check_id="check_test_001",
        regulation_id="reg_test_001",
        check_name="Test Compliance Check",
        description="Test check for demonstration",
        frequency="monthly",
        next_run=datetime.now() + timedelta(days=1)
    )
    monitor.add_compliance_check(new_check)
    print(f"Added check: {new_check.check_name}")
    
    # Test 7: Stop monitoring
    print("\n7. Stopping monitoring...")
    monitor.stop_monitoring()
    print("Monitoring stopped")
    
    # Final status
    print("\n8. Final status...")
    final_status = monitor.get_status()
    print(f"Total regulations: {final_status['regulations_count']}")
    print(f"Total checks: {final_status['checks_count']}")
    print(f"Total alerts: {final_status['alerts_count']}")
    print(f"Total reports: {final_status['reports_count']}")
    
    print("\nCompliance Monitoring System test completed successfully!")


if __name__ == "__main__":
    test_compliance_monitor()