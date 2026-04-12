"""
Regulatory Compliance Agent - Build 8 Part 1
Specialized agent for regulatory monitoring, compliance management, and audit preparation.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from pathlib import Path

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from pentagram_legal.agents.base_legal_agent import BaseLegalAgent, LegalAgentRole, LegalMatter, LegalDocument, Jurisdiction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RegulationType(Enum):
    """Types of regulations."""
    FINANCIAL = "financial"  # SEC, FINRA, CFTC, etc.
    DATA_PRIVACY = "data_privacy"  # GDPR, CCPA, HIPAA, etc.
    ENVIRONMENTAL = "environmental"  # EPA, Clean Air Act, etc.
    CONSUMER_PROTECTION = "consumer_protection"  # FTC, CFPB, etc.
    LABOR = "labor"  # DOL, OSHA, EEOC, etc.
    TRADE = "trade"  # ITAR, EAR, OFAC, etc.
    HEALTHCARE = "healthcare"  # FDA, CMS, etc.
    TELECOMMUNICATIONS = "telecommunications"  # FCC, etc.
    ENERGY = "energy"  # FERC, DOE, etc.
    TRANSPORTATION = "transportation"  # DOT, FAA, etc.


class ComplianceStatus(Enum):
    """Status of compliance efforts."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    AT_RISK = "at_risk"
    IN_REVIEW = "in_review"
    REMEDIATION_IN_PROGRESS = "remediation_in_progress"
    EXEMPT = "exempt"
    NOT_APPLICABLE = "not_applicable"
    PENDING_VERIFICATION = "pending_verification"


class RiskLevel(Enum):
    """Levels of compliance risk."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditType(Enum):
    """Types of audits."""
    INTERNAL = "internal"
    EXTERNAL = "external"
    REGULATORY = "regulatory"
    CERTIFICATION = "certification"
    DUE_DILIGENCE = "due_diligence"
    INVESTIGATION = "investigation"


class EnforcementAction(Enum):
    """Types of regulatory enforcement actions."""
    WARNING_LETTER = "warning_letter"
    CIVIL_PENALTY = "civil_penalty"
    CRIMINAL_CHARGES = "criminal_charges"
    INJUNCTION = "injunction"
    LICENSE_REVOCATION = "license_revocation"
    CONSENT_DECREE = "consent_decree"
    SETTLEMENT = "settlement"
    MONITORING = "monitoring"


@dataclass
class Regulation:
    """Regulatory requirement representation."""
    regulation_id: str
    name: str
    type: RegulationType
    jurisdiction: str
    issuing_agency: str
    effective_date: datetime
    summary: str
    key_requirements: List[str]
    covered_entities: List[str] = field(default_factory=list)
    exemptions: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    compliance_deadline: Optional[datetime] = None
    amendment_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ComplianceRequirement:
    """Specific compliance requirement."""
    requirement_id: str
    regulation_id: str
    description: str
    applicable_to: List[str]  # Departments, roles, processes
    implementation_guidance: str
    evidence_required: List[str]
    frequency: str = "ongoing"  # ongoing, monthly, quarterly, annually, event-driven
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: ComplianceStatus = ComplianceStatus.IN_REVIEW
    last_assessed: Optional[datetime] = None
    next_assessment: Optional[datetime] = None
    responsible_party: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PolicyDocument:
    """Compliance policy document."""
    policy_id: str
    title: str
    version: str
    regulation_ids: List[str]
    content: str
    effective_date: datetime
    review_frequency: str = "annual"
    last_reviewed: Optional[datetime] = None
    next_review: Optional[datetime] = None
    approval_authority: Optional[str] = None
    distribution_list: List[str] = field(default_factory=list)
    training_required: bool = True
    attestation_required: bool = True
    status: str = "draft"  # draft, approved, active, archived
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AuditFinding:
    """Finding from a compliance audit."""
    finding_id: str
    audit_id: str
    requirement_id: str
    description: str
    severity: RiskLevel
    evidence: List[str]
    root_cause: Optional[str] = None
    impact_assessment: Optional[str] = None
    recommendation: Optional[str] = None
    responsible_party: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "open"  # open, in_progress, resolved, closed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ComplianceAudit:
    """Compliance audit representation."""
    audit_id: str
    audit_type: AuditType
    scope: List[str]
    auditor: str  # Internal team or external firm
    start_date: datetime
    end_date: Optional[datetime] = None
    regulations_covered: List[str] = field(default_factory=list)
    findings: List[AuditFinding] = field(default_factory=list)
    overall_rating: Optional[str] = None  # satisfactory, needs improvement, unsatisfactory
    report_location: Optional[str] = None
    follow_up_required: bool = False
    next_audit_date: Optional[datetime] = None
    status: str = "scheduled"  # scheduled, in_progress, completed, reported
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class RegulatoryFiling:
    """Regulatory filing or report."""
    filing_id: str
    regulation_id: str
    filing_type: str  # annual_report, quarterly_filing, incident_report, etc.
    due_date: datetime
    submitted_date: Optional[datetime] = None
    status: str = "pending"  # pending, drafted, reviewed, submitted, accepted, rejected
    filing_agency: Optional[str] = None
    reference_number: Optional[str] = None
    content_summary: Optional[str] = None
    attachments: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class RiskAssessment:
    """Compliance risk assessment."""
    assessment_id: str
    title: str
    scope: List[str]
    methodology: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    overall_risk_level: RiskLevel = RiskLevel.MEDIUM
    mitigation_plan: Optional[str] = None
    next_assessment_date: Optional[datetime] = None
    approved_by: Optional[str] = None
    status: str = "draft"  # draft, in_review, approved, implemented
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TrainingRecord:
    """Compliance training record."""
    record_id: str
    employee_id: str
    training_type: str
    policy_ids: List[str]
    completion_date: datetime
    score: Optional[float] = None
    certification_number: Optional[str] = None
    expiration_date: Optional[datetime] = None
    trainer: Optional[str] = None
    status: str = "completed"  # scheduled, in_progress, completed, expired
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class RegulatoryComplianceAgent(BaseLegalAgent):
    """
    Specialized agent for regulatory compliance management.
    Handles regulatory monitoring, compliance programs, audits, and reporting.
    """
    
    def __init__(self, agent_id: str, jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL):
        """
        Initialize Regulatory Compliance Agent.
        
        Args:
            agent_id: Unique agent identifier
            jurisdiction: Primary jurisdiction
        """
        super().__init__(
            agent_id=agent_id,
            role=LegalAgentRole.REGULATORY_COMPLIANCE,
            jurisdiction=jurisdiction,
            organization="Pentagram Compliance Office"
        )
        
        # Compliance specific attributes
        self.regulations: Dict[str, Regulation] = {}
        self.compliance_requirements: Dict[str, ComplianceRequirement] = {}
        self.policies: Dict[str, PolicyDocument] = {}
        self.audits: Dict[str, ComplianceAudit] = {}
        self.regulatory_filings: Dict[str, RegulatoryFiling] = {}
        self.risk_assessments: Dict[str, RiskAssessment] = {}
        self.training_records: Dict[str, TrainingRecord] = {}
        
        # Templates and configurations
        self.policy_templates: Dict[str, Dict[str, Any]] = {}
        self.audit_templates: Dict[str, Dict[str, Any]] = {}
        self.report_templates: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self.compliance_metrics = {
            "regulations_tracked": 0,
            "compliance_requirements": 0,
            "policies_managed": 0,
            "audits_completed": 0,
            "findings_resolved": 0,
            "regulatory_filings": 0,
            "risk_assessments": 0,
            "training_records": 0,
            "compliance_rate": 100.0,  # Percentage
            "audit_success_rate": 100.0  # Percentage
        }
        
        # Register compliance specific intent handlers
        self._register_compliance_handlers()
        
        logger.info(f"Initialized Regulatory Compliance Agent {agent_id}")
    
    def _register_compliance_handlers(self):
        """Register compliance specific intent handlers."""
        self.register_handler("track_regulation", self.handle_track_regulation)
        self.register_handler("assess_compliance", self.handle_assess_compliance)
        self.register_handler("create_policy", self.handle_create_policy)
        self.register_handler("schedule_audit", self.handle_schedule_audit)
        self.register_handler("prepare_filing", self.handle_prepare_filing)
        self.register_handler("conduct_risk_assessment", self.handle_conduct_risk_assessment)
        self.register_handler("record_training", self.handle_record_training)
        self.register_handler("monitor_deadlines", self.handle_monitor_deadlines)
        
        logger.info("Registered compliance intent handlers")    def handle_track_regulation(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tracking of a new regulation.
        
        Args:
            intent_data: Regulation tracking data
            
        Returns:
            Regulation tracking result
        """
        try:
            regulation_id = intent_data.get("regulation_id", f"reg_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            name = intent_data.get("name", "")
            regulation_type_str = intent_data.get("type", "financial")
            jurisdiction = intent_data.get("jurisdiction", "US")
            issuing_agency = intent_data.get("issuing_agency", "")
            effective_date_str = intent_data.get("effective_date", datetime.now().isoformat())
            
            # Parse effective date
            effective_date = datetime.fromisoformat(effective_date_str.replace('Z', '+00:00'))
            
            # Create regulation
            regulation = Regulation(
                regulation_id=regulation_id,
                name=name,
                type=RegulationType(regulation_type_str),
                jurisdiction=jurisdiction,
                issuing_agency=issuing_agency,
                effective_date=effective_date,
                summary=intent_data.get("summary", ""),
                key_requirements=intent_data.get("key_requirements", []),
                covered_entities=intent_data.get("covered_entities", []),
                exemptions=intent_data.get("exemptions", []),
                penalties=intent_data.get("penalties", []),
                compliance_deadline=intent_data.get("compliance_deadline")
            )
            
            # Store the regulation
            self.regulations[regulation_id] = regulation
            
            # Update metrics
            self.compliance_metrics["regulations_tracked"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="track_regulation",
                details={
                    "regulation_id": regulation_id,
                    "name": name,
                    "type": regulation_type_str,
                    "jurisdiction": jurisdiction,
                    "issuing_agency": issuing_agency
                }
            )
            
            logger.info(f"Tracked regulation {regulation_id}: {name}")
            
            return {
                "success": True,
                "regulation_id": regulation_id,
                "message": f"Regulation {regulation_id} tracked successfully",
                "next_steps": [
                    "Analyze applicability to organization",
                    "Identify compliance requirements",
                    "Assess implementation timeline",
                    "Assign responsible parties"
                ],
                "compliance_timeline": self._generate_compliance_timeline(regulation)
            }
            
        except Exception as e:
            logger.error(f"Error tracking regulation: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to track regulation"
            }
    
    def handle_assess_compliance(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle assessment of compliance with a regulation.
        
        Args:
            intent_data: Compliance assessment data
            
        Returns:
            Compliance assessment result
        """
        try:
            requirement_id = intent_data.get("requirement_id", f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            regulation_id = intent_data.get("regulation_id", "")
            description = intent_data.get("description", "")
            applicable_to = intent_data.get("applicable_to", [])
            
            # Check if regulation exists
            if regulation_id not in self.regulations:
                return {
                    "success": False,
                    "error": f"Regulation {regulation_id} not found",
                    "message": "Cannot assess compliance for unknown regulation"
                }
            
            # Create compliance requirement
            requirement = ComplianceRequirement(
                requirement_id=requirement_id,
                regulation_id=regulation_id,
                description=description,
                applicable_to=applicable_to,
                implementation_guidance=intent_data.get("implementation_guidance", ""),
                evidence_required=intent_data.get("evidence_required", []),
                frequency=intent_data.get("frequency", "ongoing"),
                risk_level=RiskLevel(intent_data.get("risk_level", "medium")),
                status=ComplianceStatus(intent_data.get("status", "in_review")),
                last_assessed=datetime.now(),
                next_assessment=datetime.now() + timedelta(days=90),  # Default 90 days
                responsible_party=intent_data.get("responsible_party")
            )
            
            # Store the requirement
            self.compliance_requirements[requirement_id] = requirement
            
            # Update metrics
            self.compliance_metrics["compliance_requirements"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="assess_compliance",
                details={
                    "requirement_id": requirement_id,
                    "regulation_id": regulation_id,
                    "risk_level": requirement.risk_level.value,
                    "status": requirement.status.value
                }
            )
            
            logger.info(f"Assessed compliance requirement {requirement_id}")
            
            return {
                "success": True,
                "requirement_id": requirement_id,
                "message": f"Compliance requirement {requirement_id} assessed successfully",
                "assessment_summary": {
                    "regulation": self.regulations[regulation_id].name,
                    "description": description,
                    "risk_level": requirement.risk_level.value,
                    "status": requirement.status.value,
                    "next_assessment": requirement.next_assessment.isoformat() if requirement.next_assessment else None
                },
                "evidence_checklist": requirement.evidence_required
            }
            
        except Exception as e:
            logger.error(f"Error assessing compliance: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to assess compliance"
            }
    
    def handle_create_policy(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle creation of a compliance policy.
        
        Args:
            intent_data: Policy creation data
            
        Returns:
            Policy creation result
        """
        try:
            policy_id = intent_data.get("policy_id", f"policy_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            title = intent_data.get("title", "")
            version = intent_data.get("version", "1.0")
            regulation_ids = intent_data.get("regulation_ids", [])
            content = intent_data.get("content", "")
            effective_date_str = intent_data.get("effective_date", datetime.now().isoformat())
            
            # Parse effective date
            effective_date = datetime.fromisoformat(effective_date_str.replace('Z', '+00:00'))
            
            # Create policy document
            policy = PolicyDocument(
                policy_id=policy_id,
                title=title,
                version=version,
                regulation_ids=regulation_ids,
                content=content,
                effective_date=effective_date,
                review_frequency=intent_data.get("review_frequency", "annual"),
                approval_authority=intent_data.get("approval_authority"),
                distribution_list=intent_data.get("distribution_list", []),
                training_required=intent_data.get("training_required", True),
                attestation_required=intent_data.get("attestation_required", True),
                status=intent_data.get("status", "draft")
            )
            
            # Calculate next review date
            if policy.review_frequency == "annual":
                policy.next_review = effective_date + timedelta(days=365)
            elif policy.review_frequency == "quarterly":
                policy.next_review = effective_date + timedelta(days=90)
            elif policy.review_frequency == "monthly":
                policy.next_review = effective_date + timedelta(days=30)
            elif policy.review_frequency == "biannual":
                policy.next_review = effective_date + timedelta(days=180)
            
            # Store the policy
            self.policies[policy_id] = policy
            
            # Update metrics
            self.compliance_metrics["policies_managed"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="create_policy",
                details={
                    "policy_id": policy_id,
                    "title": title,
                    "version": version,
                    "regulation_count": len(regulation_ids),
                    "status": policy.status
                }
            )
            
            logger.info(f"Created policy {policy_id}: {title}")
            
            return {
                "success": True,
                "policy_id": policy_id,
                "message": f"Policy {policy_id} created successfully",
                "policy_details": {
                    "title": title,
                    "version": version,
                    "effective_date": effective_date.isoformat(),
                    "next_review": policy.next_review.isoformat() if policy.next_review else None,
                    "training_required": policy.training_required,
                    "attestation_required": policy.attestation_required
                },
                "implementation_steps": [
                    "Obtain approvals",
                    "Distribute to stakeholders",
                    "Schedule training sessions",
                    "Collect attestations"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error creating policy: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create policy"
            }
    
    def handle_schedule_audit(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle scheduling of a compliance audit.
        
        Args:
            intent_data: Audit scheduling data
            
        Returns:
            Audit scheduling result
        """
        try:
            audit_id = intent_data.get("audit_id", f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            audit_type_str = intent_data.get("audit_type", "internal")
            scope = intent_data.get("scope", [])
            auditor = intent_data.get("auditor", "")
            start_date_str = intent_data.get("start_date", datetime.now().isoformat())
            
            # Parse start date
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            
            # Create audit
            audit = ComplianceAudit(
                audit_id=audit_id,
                audit_type=AuditType(audit_type_str),
                scope=scope,
                auditor=auditor,
                start_date=start_date,
                regulations_covered=intent_data.get("regulations_covered", []),
                status="scheduled"
            )
            
            # Calculate end date (default 2 weeks)
            audit.end_date = start_date + timedelta(days=14)
            
            # Store the audit
            self.audits[audit_id] = audit
            
            # Update metrics
            self.compliance_metrics["audits_completed"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="schedule_audit",
                details={
                    "audit_id": audit_id,
                    "audit_type": audit_type_str,
                    "auditor": auditor,
                    "scope_size": len(scope)
                }
            )
            
            logger.info(f"Scheduled audit {audit_id} with {auditor}")
            
            return {
                "success": True,
                "audit_id": audit_id,
                "message": f"Audit {audit_id} scheduled successfully",
                "audit_details": {
                    "type": audit_type_str,
                    "auditor": auditor,
                    "start_date": start_date.isoformat(),
                    "end_date": audit.end_date.isoformat() if audit.end_date else None,
                    "scope": scope,
                    "regulations_covered": len(audit.regulations_covered)
                },
                "preparation_steps": [
                    "Prepare audit plan",
                    "Gather relevant documents",
                    "Schedule interviews",
                    "Set up audit workspace"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error scheduling audit: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to schedule audit"
            }
    
    def handle_prepare_filing(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle preparation of a regulatory filing.
        
        Args:
            intent_data: Filing preparation data
            
        Returns:
            Filing preparation result
        """
        try:
            filing_id = intent_data.get("filing_id", f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            regulation_id = intent_data.get("regulation_id", "")
            filing_type = intent_data.get("filing_type", "annual_report")
            due_date_str = intent_data.get("due_date", datetime.now().isoformat())
            
            # Parse due date
            due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            
            # Check if regulation exists
            if regulation_id not in self.regulations:
                return {
                    "success": False,
                    "error": f"Regulation {regulation_id} not found",
                    "message": "Cannot prepare filing for unknown regulation"
                }
            
            # Create regulatory filing
            filing = RegulatoryFiling(
                filing_id=filing_id,
                regulation_id=regulation_id,
                filing_type=filing_type,
                due_date=due_date,
                filing_agency=intent_data.get("filing_agency"),
                content_summary=intent_data.get("content_summary", ""),
                attachments=intent_data.get("attachments", []),
                status="pending"
            )
            
            # Store the filing
            self.regulatory_filings[filing_id] = filing
            
            # Update metrics
            self.compliance_metrics["regulatory_filings"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="prepare_filing",
                details={
                    "filing_id": filing_id,
                    "regulation_id": regulation_id,
                    "filing_type": filing_type,
                    "due_date": due_date.isoformat()
                }
            )
            
            logger.info(f"Prepared filing {filing_id} for regulation {regulation_id}")
            
            return {
                "success": True,
                "filing_id": filing_id,
                "message": f"Regulatory filing {filing_id} prepared successfully",
                "filing_details": {
                    "regulation": self.regulations[regulation_id].name,
                    "type": filing_type,
                    "due_date": due_date.isoformat(),
                    "days_until_due": (due_date - datetime.now()).days,
                    "agency": filing.filing_agency
                },
                "preparation_steps": [
                    "Gather required data",
                    "Draft filing content",
                    "Review for accuracy",
                    "Obtain approvals",
                    "Submit by deadline"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error preparing filing: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to prepare filing"
            }
    
    def handle_conduct_risk_assessment(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle conduct of a compliance risk assessment.
        
        Args:
            intent_data: Risk assessment data
            
        Returns:
            Risk assessment result
        """
        try:
            assessment_id = intent_data.get("assessment_id", f"risk_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            title = intent_data.get("title", "")
            scope = intent_data.get("scope", [])
            methodology = intent_data.get("methodology", "qualitative")
            
            # Create risk assessment
            assessment = RiskAssessment(
                assessment_id=assessment_id,
                title=title,
                scope=scope,
                methodology=methodology,
                findings=intent_data.get("findings", []),
                overall_risk_level=RiskLevel(intent_data.get("overall_risk_level", "medium")),
                mitigation_plan=intent_data.get("mitigation_plan"),
                status=intent_data.get("status", "draft"),
                approved_by=intent_data.get("approved_by")
            )
            
            # Calculate next assessment date (default 1 year)
            assessment.next_assessment_date = datetime.now() + timedelta(days=365)
            
            # Store the assessment
            self.risk_assessments[assessment_id] = assessment
            
            # Update metrics
            self.compliance_metrics["risk_assessments"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="conduct_risk_assessment",
                details={
                    "assessment_id": assessment_id,
                    "title": title,
                    "scope_size": len(scope),
                    "risk_level": assessment.overall_risk_level.value
                }
            )
            
            logger.info(f"Conducted risk assessment {assessment_id}: {title}")
            
            return {
                "success": True,
                "assessment_id": assessment_id,
                "message": f"Risk assessment {assessment_id} conducted successfully",
                "assessment_summary": {
                    "title": title,
                    "scope": scope,
                    "methodology": methodology,
                    "overall_risk": assessment.overall_risk_level.value,
                    "finding_count": len(assessment.findings),
                    "next_assessment": assessment.next_assessment_date.isoformat() if assessment.next_assessment_date else None
                },
                "recommendations": self._generate_risk_recommendations(assessment)
            }
            
        except Exception as e:
            logger.error(f"Error conducting risk assessment: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to conduct risk assessment"
            }
    
    def handle_record_training(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle recording of compliance training.
        
        Args:
            intent_data: Training record data
            
        Returns:
            Training recording result
        """
        try:
            record_id = intent_data.get("record_id", f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            employee_id = intent_data.get("employee_id", "")
            training_type = intent_data.get("training_type", "")
            policy_ids = intent_data.get("policy_ids", [])
            completion_date_str = intent_data.get("completion_date", datetime.now().isoformat())
            
            # Parse completion date
            completion_date = datetime.fromisoformat(completion_date_str.replace('Z', '+00:00'))
            
            # Create training record
            training_record = TrainingRecord(
                record_id=record_id,
                employee_id=employee_id,
                training_type=training_type,
                policy_ids=policy_ids,
                completion_date=completion_date,
                score=intent_data.get("score"),
                certification_number=intent_data.get("certification_number"),
                expiration_date=intent_data.get("expiration_date"),
                trainer=intent_data.get("trainer"),
                status="completed"
            )
            
            # Store the record
            self.training_records[record_id] = training_record
            
            # Update metrics
            self.compliance_metrics["training_records"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="record_training",
                details={
                    "record_id": record_id,
                    "employee_id": employee_id,
                    "training_type": training_type,
                    "policy_count": len(policy_ids)
                }
            )
            
            logger.info(f"Recorded training {record_id} for employee {employee_id}")
            
            return {
                "success": True,
                "record_id": record_id,
                "message": f"Training record {record_id} created successfully",
                "training_details": {
                    "employee": employee_id,
                    "training_type": training_type,
                    "completion_date": completion_date.isoformat(),
                    "score": training_record.score,
                    "certification": training_record.certification_number,
                    "expiration": training_record.expiration_date.isoformat() if training_record.expiration_date else None
                },
                "next_steps": [
                    "Update employee training profile",
                    "Schedule refresher training if needed",
                    "Notify relevant managers"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error recording training: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to record training"
            }
    
    def handle_monitor_deadlines(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle monitoring of compliance deadlines.
        
        Args:
            intent_data: Deadline monitoring data
            
        Returns:
            Deadline monitoring result
        """
        try:
            days_ahead = intent_data.get("days_ahead", 30)
            cutoff_date = datetime.now() + timedelta(days=days_ahead)
            
            deadlines = []
            
            # Check regulatory filing deadlines
            for filing_id, filing in self.regulatory_filings.items():
                if filing.due_date and filing.due_date <= cutoff_date and filing.status != "submitted":
                    deadlines.append({
                        "type": "regulatory_filing",
                        "id": filing_id,
                        "description": f"Filing for {filing.regulation_id}",
                        "due_date": filing.due_date.isoformat(),
                        "days_remaining": (filing.due_date - datetime.now()).days,
                        "status": filing.status,
                        "priority": "high" if (filing.due_date - datetime.now()).days < 7 else "medium"
                    })
            
            # Check audit deadlines
            for audit_id, audit in self.audits.items():
                if audit.start_date and audit.start_date <= cutoff_date and audit.status == "scheduled":
                    deadlines.append({
                        "type": "audit",
                        "id": audit_id,
                        "description": f"{audit.audit_type.value.capitalize()} audit",
                        "due_date": audit.start_date.isoformat(),
                        "days_remaining": (audit.start_date - datetime.now()).days,
                        "status": audit.status,
                        "priority": "medium"
                    })
            
            # Check policy review deadlines
            for policy_id, policy in self.policies.items():
                if policy.next_review and policy.next_review <= cutoff_date:
                    deadlines.append({
                        "type": "policy_review",
                        "id": policy_id,
                        "description": f"Review of {policy.title}",
                        "due_date": policy.next_review.isoformat(),
                        "days_remaining": (policy.next_review - datetime.now()).days,
                        "status": policy.status,
                        "priority": "low" if (policy.next_review - datetime.now()).days > 30 else "medium"
                    })
            
            # Sort by priority and days remaining
            deadlines.sort(key=lambda x: (x["priority"], x["days_remaining"]))
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="monitor_deadlines",
                details={
                    "days_ahead": days_ahead,
                    "deadlines_found": len(deadlines),
                    "high_priority": len([d for d in deadlines if d["priority"] == "high"])
                }
            )
            
            logger.info(f"Monitored deadlines for next {days_ahead} days, found {len(deadlines)} deadlines")
            
            return {
                "success": True,
                "days_ahead": days_ahead,
                "deadlines": deadlines,
                "message": f"Found {len(deadlines)} deadlines in next {days_ahead} days",
                "summary": {
                    "total": len(deadlines),
                    "high_priority": len([d for d in deadlines if d["priority"] == "high"]),
                    "medium_priority": len([d for d in deadlines if d["priority"] == "medium"]),
                    "low_priority": len([d for d in deadlines if d["priority"] == "low"])
                }
            }
            
        except Exception as e:
            logger.error(f"Error monitoring deadlines: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to monitor deadlines"
            }
    
    def _generate_compliance_timeline(self, regulation: Regulation) -> Dict[str, Any]:
        """Generate compliance timeline for a regulation."""
        timeline = {}
        
        if regulation.effective_date:
            timeline["effective_date"] = regulation.effective_date.isoformat()
            timeline["days_until_effective"] = (regulation.effective_date - datetime.now()).days
        
        if regulation.compliance_deadline:
            timeline["compliance_deadline"] = regulation.compliance_deadline.isoformat()
            timeline["days_until_deadline"] = (regulation.compliance_deadline - datetime.now()).days
        
        # Add standard compliance milestones
        if regulation.effective_date:
            timeline["milestones"] = [
                {
                    "name": "Gap Analysis",
                    "target_date": (regulation.effective_date - timedelta(days=60)).isoformat(),
                    "description": "Identify compliance gaps"
                },
                {
                    "name": "Implementation Plan",
                    "target_date": (regulation.effective_date - timedelta(days=30)).isoformat(),
                    "description": "Develop implementation plan"
                },
                {
                    "name": "Training Complete",
                    "target_date": (regulation.effective_date - timedelta(days=14)).isoformat(),
                    "description": "Complete employee training"
                },
                {
                    "name": "Full Compliance",
                    "target_date": regulation.effective_date.isoformat(),
                    "description": "Achieve full compliance"
                }
            ]
        
        return timeline
    
    def _generate_risk_recommendations(self, assessment: RiskAssessment) -> List[str]:
        """Generate recommendations based on risk assessment."""
        recommendations = []
        
        if assessment.overall_risk_level == RiskLevel.CRITICAL:
            recommendations.append("Immediate executive review required")
            recommendations.append("Develop emergency mitigation plan")
            recommendations.append("Consider external consultation")
        
        if assessment.overall_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("Increase monitoring frequency")
            recommendations.append("Allocate additional resources")
            recommendations.append("Update risk register immediately")
        
        if len(assessment.findings) > 5:
            recommendations.append("Prioritize findings by severity")
            recommendations.append("Develop phased remediation plan")
            recommendations.append("Assign dedicated remediation team")
        
        if assessment.methodology == "qualitative":
            recommendations.append("Consider quantitative validation of findings")
        
        # General recommendations
        recommendations.append(f"Schedule next assessment for {assessment.next_assessment_date.strftime('%Y-%m-%d') if assessment.next_assessment_date else 'TBD'}")
        recommendations.append("Document all findings and actions")
        recommendations.append("Communicate results to relevant stakeholders")
        
        return recommendations
    
    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get current status of the compliance agent.
        
        Returns:
            Agent status information
        """
        base_status = super().get_agent_status()
        
        compliance_specific_status = {
            "compliance_metrics": self.compliance_metrics,
            "active_counts": {
                "regulations": len(self.regulations),
                "compliance_requirements": len(self.compliance_requirements),
                "policies": len(self.policies),
                "audits": len(self.audits),
                "regulatory_filings": len(self.regulatory_filings),
                "risk_assessments": len(self.risk_assessments),
                "training_records": len(self.training_records)
            },
            "templates_available": {
                "policy_templates": len(self.policy_templates),
                "audit_templates": len(self.audit_templates),
                "report_templates": len(self.report_templates)
            },
            "upcoming_deadlines": self._get_upcoming_deadlines_summary()
        }
        
        base_status.update(compliance_specific_status)
        return base_status
    
    def _get_upcoming_deadlines_summary(self) -> Dict[str, Any]:
        """Get summary of upcoming deadlines."""
        upcoming = {
            "next_7_days": 0,
            "next_30_days": 0,
            "next_90_days": 0,
            "critical": 0
        }
        
        now = datetime.now()
        
        # Check filings
        for filing in self.regulatory_filings.values():
            if filing.due_date and filing.status != "submitted":
                days_until = (filing.due_date - now).days
                if 0 <= days_until <= 7:
                    upcoming["next_7_days"] += 1
                    if days_until <= 3:
                        upcoming["critical"] += 1
                elif days_until <= 30:
                    upcoming["next_30_days"] += 1
                elif days_until <= 90:
                    upcoming["next_90_days"] += 1
        
        # Check audits
        for audit in self.audits.values():
            if audit.start_date and audit.status == "scheduled":
                days_until = (audit.start_date - now).days
                if 0 <= days_until <= 7:
                    upcoming["next_7_days"] += 1
                elif days_until <= 30:
                    upcoming["next_30_days"] += 1
                elif days_until <= 90:
                    upcoming["next_90_days"] += 1
        
        return upcoming
    
    def _log_iso_compliance(self, action: str, details: Dict[str, Any]):
        """Log ISO compliance event."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "action": action,
            "details": details,
            "compliance_standard": "ISO 19600:2014 (Compliance Management)",
            "security_level": "confidential"
        }
        
        # Save to compliance log
        log_dir = Path("logs/compliance")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"compliance_audit_{datetime.now().strftime('%Y%m')}.json"
        
        try:
            if log_file.exists():
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            logs.append(log_entry)
            
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to write compliance log: {str(e)}")


def test_regulatory_compliance_agent():
    """Test function for Regulatory Compliance Agent."""
    print("Testing Regulatory Compliance Agent...")
    
    # Create agent instance
    agent = RegulatoryComplianceAgent("compliance_agent_001")
    
    # Test 1: Track regulation
    print("\n1. Testing regulation tracking...")
    regulation_data = {
        "name": "General Data Protection Regulation (GDPR)",
        "type": "data_privacy",
        "jurisdiction": "EU",
        "issuing_agency": "European Commission",
        "effective_date": datetime.now().isoformat(),
        "summary": "Regulation on data protection and privacy in the EU",
        "key_requirements": [
            "Data subject rights",
            "Lawful basis for processing",
            "Data protection by design",
            "Data breach notification"
        ]
    }
    
    result = agent.handle_track_regulation(regulation_data)
    print(f"Regulation tracking result: {result.get('success')}")
    print(f"Regulation ID: {result.get('regulation_id')}")
    
    # Test 2: Assess compliance
    print("\n2. Testing compliance assessment...")
    compliance_data = {
        "regulation_id": result.get("regulation_id"),
        "description": "Implement data subject access request process",
        "applicable_to": ["IT Department", "Legal Department", "Customer Support"],
        "risk_level": "high",
        "evidence_required": ["Process documentation", "Training records", "Request logs"]
    }
    
    result = agent.handle_assess_compliance(compliance_data)
    print(f"Compliance assessment result: {result.get('success')}")
    print(f"Requirement ID: {result.get('requirement_id')}")
    
    # Test 3: Create policy
    print("\n3. Testing policy creation...")
    policy_data = {
        "title": "Data Protection and Privacy Policy",
        "version": "1.0",
        "regulation_ids": [result.get("regulation_id")],
        "content": "Policy content detailing data protection measures...",
        "effective_date": datetime.now().isoformat(),
        "distribution_list": ["all_employees"],
        "training_required": True
    }
    
    result = agent.handle_create_policy(policy_data)
    print(f"Policy creation result: {result.get('success')}")
    print(f"Policy ID: {result.get('policy_id')}")
    
    # Test 4: Monitor deadlines
    print("\n4. Testing deadline monitoring...")
    result = agent.handle_monitor_deadlines({"days_ahead": 30})
    print(f"Deadline monitoring result: {result.get('success')}")
    print(f"Deadlines found: {result.get('summary', {}).get('total', 0)}")
    
    # Test 5: Check agent status
    print("\n5. Testing agent status...")
    status = agent.get_agent_status()
    print(f"Agent active: {status.get('active')}")
    print(f"Compliance metrics: {status.get('compliance_metrics')}")
    
    print("\nRegulatory Compliance Agent test completed successfully!")


if __name__ == "__main__":
    test_regulatory_compliance_agent()