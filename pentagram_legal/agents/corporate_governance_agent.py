"""
Corporate Governance Agent - Build 10 Part 1
Specialized agent for board management, corporate policies, shareholder relations, and governance compliance.
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


class MeetingType(Enum):
    """Types of corporate meetings."""
    BOARD = "board"
    COMMITTEE = "committee"
    SHAREHOLDER = "shareholder"
    ANNUAL_GENERAL = "annual_general"
    SPECIAL = "special"
    EXECUTIVE = "executive"
    AUDIT = "audit"
    COMPENSATION = "compensation"
    NOMINATING = "nominating"


class DocumentType(Enum):
    """Types of corporate governance documents."""
    BYLAWS = "bylaws"
    ARTICLES = "articles"
    MINUTES = "minutes"
    RESOLUTION = "resolution"
    POLICY = "policy"
    CHARTER = "charter"
    CODE_OF_CONDUCT = "code_of_conduct"
    WHISTLEBLOWER = "whistleblower"
    INSIDER_TRADING = "insider_trading"
    ANNUAL_REPORT = "annual_report"
    PROXY_STATEMENT = "proxy_statement"


class ComplianceArea(Enum):
    """Areas of corporate governance compliance."""
    SEC = "sec"  # Securities and Exchange Commission
    SOX = "sox"  # Sarbanes-Oxley Act
    DODD_FRANK = "dodd_frank"
    EXCHANGE_LISTING = "exchange_listing"
    STATE_CORPORATION = "state_corporation"
    TAX = "tax"
    EMPLOYMENT = "employment"
    ENVIRONMENTAL = "environmental"
    DATA_PRIVACY = "data_privacy"
    ANTITRUST = "antitrust"


class RiskCategory(Enum):
    """Categories of governance risks."""
    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    REPUTATIONAL = "reputational"
    CYBERSECURITY = "cybersecurity"
    SUCCESSION = "succession"
    RELATED_PARTY = "related_party"


class ShareholderType(Enum):
    """Types of shareholders."""
    INSTITUTIONAL = "institutional"
    RETAIL = "retail"
    INSIDER = "insider"
    EMPLOYEE = "employee"
    FOUNDER = "founder"
    VENTURE_CAPITAL = "venture_capital"
    PRIVATE_EQUITY = "private_equity"


@dataclass
class BoardMember:
    """Board of Directors member."""
    member_id: str
    name: str
    title: str  # Chair, CEO, Independent Director, etc.
    committee_memberships: List[str] = field(default_factory=list)
    term_start: datetime = field(default_factory=datetime.now)
    term_end: Optional[datetime] = None
    independence_status: str = "independent"  # independent, non-independent, affiliated
    qualifications: List[str] = field(default_factory=list)
    attendance_rate: float = 100.0  # Percentage
    compensation: Optional[float] = None
    contact_info: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class BoardMeeting:
    """Board of Directors meeting."""
    meeting_id: str
    meeting_type: MeetingType
    date: datetime
    location: str
    chairperson: str
    attendees: List[str] = field(default_factory=list)
    agenda_items: List[Dict[str, Any]] = field(default_factory=list)
    minutes: Optional[str] = None
    resolutions: List[Dict[str, Any]] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    quorum_met: bool = True
    next_meeting_date: Optional[datetime] = None
    status: str = "scheduled"  # scheduled, in_progress, completed, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class CorporateResolution:
    """Corporate resolution passed by the board."""
    resolution_id: str
    meeting_id: str
    resolution_type: str  # appointment, compensation, approval, authorization
    title: str
    description: str
    voting_results: Dict[str, Any] = field(default_factory=dict)
    effective_date: datetime = field(default_factory=datetime.now)
    implementation_status: str = "pending"  # pending, in_progress, completed
    responsible_party: Optional[str] = None
    follow_up_required: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class GovernancePolicy:
    """Corporate governance policy."""
    policy_id: str
    policy_type: DocumentType
    title: str
    version: str
    effective_date: datetime
    review_frequency: str = "annual"
    applicable_to: List[str] = field(default_factory=list)
    content: Optional[str] = None
    approval_authority: Optional[str] = None
    last_reviewed: Optional[datetime] = None
    next_review: Optional[datetime] = None
    compliance_areas: List[ComplianceArea] = field(default_factory=list)
    training_required: bool = True
    attestation_required: bool = True
    status: str = "draft"  # draft, approved, active, archived
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ShareholderCommunication:
    """Communication with shareholders."""
    communication_id: str
    shareholder_type: ShareholderType
    communication_type: str  # annual_report, proxy, dividend, announcement, inquiry
    date: datetime
    subject: str
    content: str
    recipients: List[str] = field(default_factory=list)
    delivery_method: str = "email"  # email, mail, website, meeting
    response_required: bool = False
    response_deadline: Optional[datetime] = None
    status: str = "draft"  # draft, sent, delivered, acknowledged
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AnnualReport:
    """Corporate annual report."""
    report_id: str
    fiscal_year: int
    preparation_date: datetime
    filing_deadline: datetime
    sections: Dict[str, str] = field(default_factory=dict)
    financial_statements: List[Dict[str, Any]] = field(default_factory=list)
    management_discussion: Optional[str] = None
    risk_factors: List[str] = field(default_factory=list)
    governance_disclosures: Dict[str, Any] = field(default_factory=dict)
    auditor_opinion: Optional[str] = None
    filing_status: str = "preparation"  # preparation, review, approved, filed
    filed_date: Optional[datetime] = None
    filing_reference: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ComplianceRecord:
    """Record of governance compliance."""
    record_id: str
    compliance_area: ComplianceArea
    requirement: str
    due_date: datetime
    responsible_party: str
    evidence: List[str] = field(default_factory=list)
    completion_date: Optional[datetime] = None
    status: str = "pending"  # pending, in_progress, completed, overdue
    verification: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class RiskAssessment:
    """Governance risk assessment."""
    assessment_id: str
    risk_category: RiskCategory
    description: str
    likelihood: str = "medium"  # low, medium, high
    impact: str = "medium"  # low, medium, high
    mitigation_plan: Optional[str] = None
    responsible_party: Optional[str] = None
    monitoring_frequency: str = "quarterly"
    last_assessed: datetime = field(default_factory=datetime.now)
    next_assessment: Optional[datetime] = None
    status: str = "active"  # active, mitigated, closed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class CorporateRecord:
    """Corporate record keeping entry."""
    record_id: str
    record_type: str  # incorporation, amendment, merger, dissolution
    description: str
    document_reference: str
    filing_date: datetime
    jurisdiction: str
    effective_date: Optional[datetime] = None
    filing_agency: Optional[str] = None
    filing_number: Optional[str] = None
    status: str = "filed"  # draft, filed, effective, archived
    retention_period: str = "permanent"  # temporary, 7_years, permanent
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class CorporateGovernanceAgent(BaseLegalAgent):
    """
    Specialized agent for corporate governance management.
    Handles board operations, policies, shareholder relations, and governance compliance.
    """
    
    def __init__(self, agent_id: str, jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL):
        """
        Initialize Corporate Governance Agent.
        
        Args:
            agent_id: Unique agent identifier
            jurisdiction: Primary jurisdiction
        """
        super().__init__(
            agent_id=agent_id,
            role=LegalAgentRole.CORPORATE_GOVERNANCE,
            jurisdiction=jurisdiction,
            organization="Pentagram Corporate Secretariat"
        )
        
        # Governance specific attributes
        self.board_members: Dict[str, BoardMember] = {}
        self.board_meetings: Dict[str, BoardMeeting] = {}
        self.corporate_resolutions: Dict[str, CorporateResolution] = {}
        self.governance_policies: Dict[str, GovernancePolicy] = {}
        self.shareholder_communications: Dict[str, ShareholderCommunication] = {}
        self.annual_reports: Dict[str, AnnualReport] = {}
        self.compliance_records: Dict[str, ComplianceRecord] = {}
        self.risk_assessments: Dict[str, RiskAssessment] = {}
        self.corporate_records: Dict[str, CorporateRecord] = {}
        
        # Templates and configurations
        self.minutes_templates: Dict[str, Dict[str, Any]] = {}
        self.policy_templates: Dict[str, Dict[str, Any]] = {}
        self.report_templates: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self.governance_metrics = {
            "board_meetings": 0,
            "resolutions_passed": 0,
            "policies_managed": 0,
            "shareholder_communications": 0,
            "annual_reports": 0,
            "compliance_records": 0,
            "risk_assessments": 0,
            "corporate_records": 0,
            "board_attendance_rate": 100.0,  # Percentage
            "compliance_rate": 100.0,  # Percentage
            "shareholder_satisfaction": 0.0  # Score 0-100
        }
        
        # Register governance specific intent handlers
        self._register_governance_handlers()
        
        logger.info(f"Initialized Corporate Governance Agent {agent_id}")
    
    def _register_governance_handlers(self):
        """Register governance specific intent handlers."""
        self.register_handler("manage_board", self.handle_manage_board)
        self.register_handler("schedule_meeting", self.handle_schedule_meeting)
        self.register_handler("create_policy", self.handle_create_policy)
        self.register_handler("communicate_shareholders", self.handle_communicate_shareholders)
        self.register_handler("prepare_annual_report", self.handle_prepare_annual_report)
        self.register_handler("track_compliance", self.handle_track_compliance)
        self.register_handler("assess_risks", self.handle_assess_risks)
        self.register_handler("maintain_records", self.handle_maintain_records)
        
        logger.info("Registered governance intent handlers")    def handle_manage_board(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle management of board members.
        
        Args:
            intent_data: Board management data
            
        Returns:
            Board management result
        """
        try:
            member_id = intent_data.get("member_id", f"board_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            name = intent_data.get("name", "")
            title = intent_data.get("title", "Director")
            
            # Create board member
            board_member = BoardMember(
                member_id=member_id,
                name=name,
                title=title,
                committee_memberships=intent_data.get("committee_memberships", []),
                term_start=intent_data.get("term_start", datetime.now()),
                term_end=intent_data.get("term_end"),
                independence_status=intent_data.get("independence_status", "independent"),
                qualifications=intent_data.get("qualifications", []),
                attendance_rate=intent_data.get("attendance_rate", 100.0),
                compensation=intent_data.get("compensation"),
                contact_info=intent_data.get("contact_info", {})
            )
            
            # Store the board member
            self.board_members[member_id] = board_member
            
            # Update metrics
            self._update_board_metrics()
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="manage_board",
                details={
                    "member_id": member_id,
                    "name": name,
                    "title": title,
                    "independence_status": board_member.independence_status,
                    "committee_count": len(board_member.committee_memberships)
                }
            )
            
            logger.info(f"Managed board member {member_id}: {name}")
            
            return {
                "success": True,
                "member_id": member_id,
                "message": f"Board member {member_id} managed successfully",
                "member_details": {
                    "name": name,
                    "title": title,
                    "independence": board_member.independence_status,
                    "term_start": board_member.term_start.isoformat(),
                    "term_end": board_member.term_end.isoformat() if board_member.term_end else None,
                    "committees": board_member.committee_memberships,
                    "attendance_rate": f"{board_member.attendance_rate}%"
                },
                "compliance_requirements": self._get_board_member_compliance(board_member)
            }
            
        except Exception as e:
            logger.error(f"Error managing board: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to manage board"
            }
    
    def handle_schedule_meeting(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle scheduling of a board meeting.
        
        Args:
            intent_data: Meeting scheduling data
            
        Returns:
            Meeting scheduling result
        """
        try:
            meeting_id = intent_data.get("meeting_id", f"meeting_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            meeting_type_str = intent_data.get("meeting_type", "board")
            date_str = intent_data.get("date", datetime.now().isoformat())
            location = intent_data.get("location", "Board Room")
            chairperson = intent_data.get("chairperson", "")
            
            # Parse date
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            # Create board meeting
            meeting = BoardMeeting(
                meeting_id=meeting_id,
                meeting_type=MeetingType(meeting_type_str),
                date=date,
                location=location,
                chairperson=chairperson,
                attendees=intent_data.get("attendees", []),
                agenda_items=intent_data.get("agenda_items", []),
                quorum_met=intent_data.get("quorum_met", True),
                status="scheduled"
            )
            
            # Set next meeting date (default quarterly)
            if meeting_type_str == "board":
                meeting.next_meeting_date = date + timedelta(days=90)  # Quarterly
            
            # Store the meeting
            self.board_meetings[meeting_id] = meeting
            
            # Update metrics
            self.governance_metrics["board_meetings"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="schedule_meeting",
                details={
                    "meeting_id": meeting_id,
                    "meeting_type": meeting_type_str,
                    "date": date.isoformat(),
                    "chairperson": chairperson,
                    "attendee_count": len(meeting.attendees)
                }
            )
            
            logger.info(f"Scheduled meeting {meeting_id}: {meeting_type_str}")
            
            return {
                "success": True,
                "meeting_id": meeting_id,
                "message": f"Meeting {meeting_id} scheduled successfully",
                "meeting_details": {
                    "type": meeting_type_str,
                    "date": date.isoformat(),
                    "location": location,
                    "chairperson": chairperson,
                    "attendees": meeting.attendees,
                    "agenda_items": len(meeting.agenda_items),
                    "next_meeting": meeting.next_meeting_date.isoformat() if meeting.next_meeting_date else None
                },
                "preparation_steps": [
                    "Distribute meeting notice",
                    "Prepare agenda packet",
                    "Coordinate with presenters",
                    "Arrange logistics",
                    "Prepare attendance sheet"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error scheduling meeting: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to schedule meeting"
            }
    
    def handle_create_policy(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle creation of a governance policy.
        
        Args:
            intent_data: Policy creation data
            
        Returns:
            Policy creation result
        """
        try:
            policy_id = intent_data.get("policy_id", f"policy_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            policy_type_str = intent_data.get("policy_type", "code_of_conduct")
            title = intent_data.get("title", "")
            version = intent_data.get("version", "1.0")
            effective_date_str = intent_data.get("effective_date", datetime.now().isoformat())
            
            # Parse effective date
            effective_date = datetime.fromisoformat(effective_date_str.replace('Z', '+00:00'))
            
            # Create governance policy
            policy = GovernancePolicy(
                policy_id=policy_id,
                policy_type=DocumentType(policy_type_str),
                title=title,
                version=version,
                effective_date=effective_date,
                review_frequency=intent_data.get("review_frequency", "annual"),
                applicable_to=intent_data.get("applicable_to", []),
                content=intent_data.get("content"),
                approval_authority=intent_data.get("approval_authority"),
                compliance_areas=[ComplianceArea(ca) for ca in intent_data.get("compliance_areas", [])],
                training_required=intent_data.get("training_required", True),
                attestation_required=intent_data.get("attestation_required", True),
                status=intent_data.get("status", "draft")
            )
            
            # Calculate next review date
            if policy.review_frequency == "annual":
                policy.next_review = effective_date + timedelta(days=365)
            elif policy.review_frequency == "quarterly":
                policy.next_review = effective_date + timedelta(days=90)
            elif policy.review_frequency == "biannual":
                policy.next_review = effective_date + timedelta(days=180)
            
            # Store the policy
            self.governance_policies[policy_id] = policy
            
            # Update metrics
            self.governance_metrics["policies_managed"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="create_policy",
                details={
                    "policy_id": policy_id,
                    "policy_type": policy_type_str,
                    "title": title,
                    "version": version,
                    "compliance_areas": len(policy.compliance_areas)
                }
            )
            
            logger.info(f"Created policy {policy_id}: {title}")
            
            return {
                "success": True,
                "policy_id": policy_id,
                "message": f"Policy {policy_id} created successfully",
                "policy_details": {
                    "title": title,
                    "type": policy_type_str,
                    "version": version,
                    "effective_date": effective_date.isoformat(),
                    "next_review": policy.next_review.isoformat() if policy.next_review else None,
                    "applicable_to": policy.applicable_to,
                    "training_required": policy.training_required,
                    "attestation_required": policy.attestation_required
                },
                "implementation_steps": [
                    "Obtain approvals",
                    "Distribute to affected parties",
                    "Schedule training sessions",
                    "Collect attestations",
                    "Monitor compliance"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error creating policy: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create policy"
            }
    
    def handle_communicate_shareholders(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle communication with shareholders.
        
        Args:
            intent_data: Shareholder communication data
            
        Returns:
            Shareholder communication result
        """
        try:
            communication_id = intent_data.get("communication_id", f"comm_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shareholder_type_str = intent_data.get("shareholder_type", "institutional")
            communication_type = intent_data.get("communication_type", "announcement")
            date_str = intent_data.get("date", datetime.now().isoformat())
            subject = intent_data.get("subject", "")
            content = intent_data.get("content", "")
            
            # Parse date
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            # Create shareholder communication
            communication = ShareholderCommunication(
                communication_id=communication_id,
                shareholder_type=ShareholderType(shareholder_type_str),
                communication_type=communication_type,
                date=date,
                subject=subject,
                content=content,
                recipients=intent_data.get("recipients", []),
                delivery_method=intent_data.get("delivery_method", "email"),
                response_required=intent_data.get("response_required", False),
                response_deadline=intent_data.get("response_deadline"),
                status="draft"
            )
            
            # Store the communication
            self.shareholder_communications[communication_id] = communication
            
            # Update metrics
            self.governance_metrics["shareholder_communications"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="communicate_shareholders",
                details={
                    "communication_id": communication_id,
                    "shareholder_type": shareholder_type_str,
                    "communication_type": communication_type,
                    "subject": subject,
                    "recipient_count": len(communication.recipients)
                }
            )
            
            logger.info(f"Created shareholder communication {communication_id}: {subject}")
            
            return {
                "success": True,
                "communication_id": communication_id,
                "message": f"Shareholder communication {communication_id} created successfully",
                "communication_details": {
                    "subject": subject,
                    "shareholder_type": shareholder_type_str,
                    "communication_type": communication_type,
                    "date": date.isoformat(),
                    "delivery_method": communication.delivery_method,
                    "recipients": len(communication.recipients),
                    "response_required": communication.response_required,
                    "response_deadline": communication.response_deadline.isoformat() if communication.response_deadline else None
                },
                "distribution_steps": [
                    "Finalize content",
                    "Obtain legal review",
                    "Prepare distribution list",
                    "Schedule delivery",
                    "Track acknowledgments"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error communicating with shareholders: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to communicate with shareholders"
            }
    
    def handle_prepare_annual_report(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle preparation of annual report.
        
        Args:
            intent_data: Annual report preparation data
            
        Returns:
            Annual report preparation result
        """
        try:
            report_id = intent_data.get("report_id", f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            fiscal_year = intent_data.get("fiscal_year", datetime.now().year)
            preparation_date_str = intent_data.get("preparation_date", datetime.now().isoformat())
            filing_deadline_str = intent_data.get("filing_deadline", (datetime.now() + timedelta(days=90)).isoformat())
            
            # Parse dates
            preparation_date = datetime.fromisoformat(preparation_date_str.replace('Z', '+00:00'))
            filing_deadline = datetime.fromisoformat(filing_deadline_str.replace('Z', '+00:00'))
            
            # Create annual report
            annual_report = AnnualReport(
                report_id=report_id,
                fiscal_year=fiscal_year,
                preparation_date=preparation_date,
                filing_deadline=filing_deadline,
                sections=intent_data.get("sections", {}),
                financial_statements=intent_data.get("financial_statements", []),
                management_discussion=intent_data.get("management_discussion"),
                risk_factors=intent_data.get("risk_factors", []),
                governance_disclosures=intent_data.get("governance_disclosures", {}),
                auditor_opinion=intent_data.get("auditor_opinion"),
                filing_status="preparation"
            )
            
            # Store the report
            self.annual_reports[report_id] = annual_report
            
            # Update metrics
            self.governance_metrics["annual_reports"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="prepare_annual_report",
                details={
                    "report_id": report_id,
                    "fiscal_year": fiscal_year,
                    "filing_deadline": filing_deadline.isoformat(),
                    "days_until_deadline": (filing_deadline - datetime.now()).days
                }
            )
            
            logger.info(f"Prepared annual report {report_id} for fiscal year {fiscal_year}")
            
            return {
                "success": True,
                "report_id": report_id,
                "message": f"Annual report {report_id} preparation started",
                "report_details": {
                    "fiscal_year": fiscal_year,
                    "preparation_date": preparation_date.isoformat(),
                    "filing_deadline": filing_deadline.isoformat(),
                    "days_until_deadline": (filing_deadline - datetime.now()).days,
                    "sections_prepared": len(annual_report.sections),
                    "financial_statements": len(annual_report.financial_statements),
                    "risk_factors": len(annual_report.risk_factors)
                },
                "preparation_timeline": self._get_annual_report_timeline(annual_report)
            }
            
        except Exception as e:
            logger.error(f"Error preparing annual report: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to prepare annual report"
            }    def handle_track_compliance(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tracking of governance compliance.
        
        Args:
            intent_data: Compliance tracking data
            
        Returns:
            Compliance tracking result
        """
        try:
            record_id = intent_data.get("record_id", f"comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            compliance_area_str = intent_data.get("compliance_area", "sec")
            requirement = intent_data.get("requirement", "")
            due_date_str = intent_data.get("due_date", datetime.now().isoformat())
            responsible_party = intent_data.get("responsible_party", "")
            
            # Parse due date
            due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            
            # Create compliance record
            compliance_record = ComplianceRecord(
                record_id=record_id,
                compliance_area=ComplianceArea(compliance_area_str),
                requirement=requirement,
                due_date=due_date,
                responsible_party=responsible_party,
                evidence=intent_data.get("evidence", []),
                status="pending"
            )
            
            # Store the record
            self.compliance_records[record_id] = compliance_record
            
            # Update metrics
            self.governance_metrics["compliance_records"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="track_compliance",
                details={
                    "record_id": record_id,
                    "compliance_area": compliance_area_str,
                    "requirement": requirement,
                    "due_date": due_date.isoformat(),
                    "responsible_party": responsible_party
                }
            )
            
            logger.info(f"Tracked compliance record {record_id}: {requirement}")
            
            return {
                "success": True,
                "record_id": record_id,
                "message": f"Compliance record {record_id} tracked successfully",
                "compliance_details": {
                    "area": compliance_area_str,
                    "requirement": requirement,
                    "due_date": due_date.isoformat(),
                    "days_until_due": (due_date - datetime.now()).days,
                    "responsible_party": responsible_party,
                    "evidence_required": len(compliance_record.evidence)
                },
                "completion_steps": [
                    "Gather required evidence",
                    "Prepare compliance documentation",
                    "Obtain necessary approvals",
                    "Submit by deadline",
                    "Record completion"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error tracking compliance: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to track compliance"
            }
    
    def handle_assess_risks(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle assessment of governance risks.
        
        Args:
            intent_data: Risk assessment data
            
        Returns:
            Risk assessment result
        """
        try:
            assessment_id = intent_data.get("assessment_id", f"risk_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            risk_category_str = intent_data.get("risk_category", "strategic")
            description = intent_data.get("description", "")
            likelihood = intent_data.get("likelihood", "medium")
            impact = intent_data.get("impact", "medium")
            
            # Create risk assessment
            risk_assessment = RiskAssessment(
                assessment_id=assessment_id,
                risk_category=RiskCategory(risk_category_str),
                description=description,
                likelihood=likelihood,
                impact=impact,
                mitigation_plan=intent_data.get("mitigation_plan"),
                responsible_party=intent_data.get("responsible_party"),
                monitoring_frequency=intent_data.get("monitoring_frequency", "quarterly"),
                status="active"
            )
            
            # Calculate next assessment date
            if risk_assessment.monitoring_frequency == "quarterly":
                risk_assessment.next_assessment = datetime.now() + timedelta(days=90)
            elif risk_assessment.monitoring_frequency == "monthly":
                risk_assessment.next_assessment = datetime.now() + timedelta(days=30)
            elif risk_assessment.monitoring_frequency == "annual":
                risk_assessment.next_assessment = datetime.now() + timedelta(days=365)
            
            # Store the assessment
            self.risk_assessments[assessment_id] = risk_assessment
            
            # Update metrics
            self.governance_metrics["risk_assessments"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="assess_risks",
                details={
                    "assessment_id": assessment_id,
                    "risk_category": risk_category_str,
                    "description": description,
                    "likelihood": likelihood,
                    "impact": impact
                }
            )
            
            logger.info(f"Assessed risk {assessment_id}: {description}")
            
            return {
                "success": True,
                "assessment_id": assessment_id,
                "message": f"Risk assessment {assessment_id} completed successfully",
                "risk_details": {
                    "category": risk_category_str,
                    "description": description,
                    "likelihood": likelihood,
                    "impact": impact,
                    "risk_level": self._calculate_risk_level(likelihood, impact),
                    "monitoring_frequency": risk_assessment.monitoring_frequency,
                    "next_assessment": risk_assessment.next_assessment.isoformat() if risk_assessment.next_assessment else None
                },
                "mitigation_recommendations": self._get_risk_mitigation_recommendations(risk_assessment)
            }
            
        except Exception as e:
            logger.error(f"Error assessing risks: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to assess risks"
            }
    
    def handle_maintain_records(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle maintenance of corporate records.
        
        Args:
            intent_data: Record maintenance data
            
        Returns:
            Record maintenance result
        """
        try:
            record_id = intent_data.get("record_id", f"corp_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            record_type = intent_data.get("record_type", "incorporation")
            description = intent_data.get("description", "")
            document_reference = intent_data.get("document_reference", "")
            filing_date_str = intent_data.get("filing_date", datetime.now().isoformat())
            jurisdiction = intent_data.get("jurisdiction", "Delaware")
            
            # Parse filing date
            filing_date = datetime.fromisoformat(filing_date_str.replace('Z', '+00:00'))
            
            # Create corporate record
            corporate_record = CorporateRecord(
                record_id=record_id,
                record_type=record_type,
                description=description,
                document_reference=document_reference,
                filing_date=filing_date,
                jurisdiction=jurisdiction,
                effective_date=intent_data.get("effective_date"),
                filing_agency=intent_data.get("filing_agency"),
                filing_number=intent_data.get("filing_number"),
                retention_period=intent_data.get("retention_period", "permanent"),
                status="filed"
            )
            
            # Store the record
            self.corporate_records[record_id] = corporate_record
            
            # Update metrics
            self.governance_metrics["corporate_records"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="maintain_records",
                details={
                    "record_id": record_id,
                    "record_type": record_type,
                    "description": description,
                    "jurisdiction": jurisdiction,
                    "retention_period": corporate_record.retention_period
                }
            )
            
            logger.info(f"Maintained corporate record {record_id}: {description}")
            
            return {
                "success": True,
                "record_id": record_id,
                "message": f"Corporate record {record_id} maintained successfully",
                "record_details": {
                    "type": record_type,
                    "description": description,
                    "document_reference": document_reference,
                    "filing_date": filing_date.isoformat(),
                    "jurisdiction": jurisdiction,
                    "filing_agency": corporate_record.filing_agency,
                    "filing_number": corporate_record.filing_number,
                    "retention_period": corporate_record.retention_period
                },
                "retention_requirements": self._get_record_retention_requirements(corporate_record)
            }
            
        except Exception as e:
            logger.error(f"Error maintaining records: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to maintain records"
            }
    
    def _update_board_metrics(self):
        """Update board-related metrics."""
        if self.board_members:
            total_attendance = sum(member.attendance_rate for member in self.board_members.values())
            self.governance_metrics["board_attendance_rate"] = total_attendance / len(self.board_members)
    
    def _get_board_member_compliance(self, member: BoardMember) -> List[str]:
        """Get compliance requirements for a board member."""
        requirements = []
        
        if member.independence_status == "independent":
            requirements.append("Annual independence certification")
            requirements.append("Disclosure of related party transactions")
        
        requirements.append("Annual director questionnaire")
        requirements.append("Code of conduct attestation")
        requirements.append("Insider trading policy acknowledgment")
        
        if "audit" in [c.lower() for c in member.committee_memberships]:
            requirements.append("Financial literacy certification")
            requirements.append("Audit committee charter familiarity")
        
        if "compensation" in [c.lower() for c in member.committee_memberships]:
            requirements.append("Compensation committee charter familiarity")
            requirements.append("Executive compensation training")
        
        return requirements
    
    def _get_annual_report_timeline(self, report: AnnualReport) -> Dict[str, Any]:
        """Get timeline for annual report preparation."""
        timeline = {
            "filing_deadline": report.filing_deadline.isoformat(),
            "days_until_deadline": (report.filing_deadline - datetime.now()).days,
            "milestones": []
        }
        
        # Add standard milestones
        days_until = (report.filing_deadline - datetime.now()).days
        
        if days_until > 60:
            timeline["milestones"].append({
                "name": "Financial Statement Preparation",
                "target_date": (report.filing_deadline - timedelta(days=60)).isoformat(),
                "description": "Complete audited financial statements"
            })
        
        if days_until > 45:
            timeline["milestones"].append({
                "name": "Management Discussion Draft",
                "target_date": (report.filing_deadline - timedelta(days=45)).isoformat(),
                "description": "Draft management discussion and analysis"
            })
        
        if days_until > 30:
            timeline["milestones"].append({
                "name": "Board Review",
                "target_date": (report.filing_deadline - timedelta(days=30)).isoformat(),
                "description": "Board of Directors review and approval"
            })
        
        if days_until > 14:
            timeline["milestones"].append({
                "name": "Legal and Audit Review",
                "target_date": (report.filing_deadline - timedelta(days=14)).isoformat(),
                "description": "Final legal and audit review"
            })
        
        timeline["milestones"].append({
            "name": "Filing Submission",
            "target_date": report.filing_deadline.isoformat(),
            "description": "Submit to regulatory authorities"
        })
        
        return timeline
    
    def _calculate_risk_level(self, likelihood: str, impact: str) -> str:
        """Calculate risk level from likelihood and impact."""
        likelihood_scores = {"low": 1, "medium": 2, "high": 3}
        impact_scores = {"low": 1, "medium": 2, "high": 3}
        
        score = likelihood_scores.get(likelihood, 2) * impact_scores.get(impact, 2)
        
        if score <= 2:
            return "low"
        elif score <= 4:
            return "medium"
        else:
            return "high"
    
    def _get_risk_mitigation_recommendations(self, risk: RiskAssessment) -> List[str]:
        """Get mitigation recommendations for a risk."""
        recommendations = []
        
        risk_level = self._calculate_risk_level(risk.likelihood, risk.impact)
        
        if risk_level == "high":
            recommendations.append("Immediate executive attention required")
            recommendations.append("Develop comprehensive mitigation plan")
            recommendations.append("Allocate dedicated resources")
            recommendations.append("Consider insurance or hedging")
        
        if risk_level in ["medium", "high"]:
            recommendations.append("Implement monitoring controls")
            recommendations.append("Assign clear responsibility")
            recommendations.append("Establish escalation procedures")
            recommendations.append("Regular review and reporting")
        
        # Category-specific recommendations
        if risk.risk_category == RiskCategory.CYBERSECURITY:
            recommendations.append("Implement security controls and monitoring")
            recommendations.append("Conduct regular vulnerability assessments")
            recommendations.append("Develop incident response plan")
        
        elif risk.risk_category == RiskCategory.FINANCIAL:
            recommendations.append("Strengthen internal controls")
            recommendations.append("Implement financial monitoring")
            recommendations.append("Regular audit and review")
        
        elif risk.risk_category == RiskCategory.COMPLIANCE:
            recommendations.append("Enhance compliance monitoring")
            recommendations.append("Regular training and certification")
            recommendations.append("Implement compliance tracking system")
        
        return recommendations
    
    def _get_record_retention_requirements(self, record: CorporateRecord) -> List[str]:
        """Get retention requirements for a corporate record."""
        requirements = []
        
        if record.record_type == "incorporation":
            requirements.append("Permanent retention required")
            requirements.append("Maintain in corporate minute book")
            requirements.append("Keep certified copies")
        
        elif record.record_type == "amendment":
            requirements.append("Permanent retention required")
            requirements.append("Maintain with original documents")
            requirements.append("Update corporate records")
        
        elif record.record_type == "minutes":
            requirements.append("Permanent retention required")
            requirements.append("Maintain in chronological order")
            requirements.append("Keep signed originals")
        
        elif record.record_type in ["contract", "agreement"]:
            requirements.append("Retain for 7 years after termination")
            requirements.append("Maintain with related correspondence")
            requirements.append("Keep executed copies")
        
        else:
            requirements.append(f"Follow {record.retention_period} retention policy")
            requirements.append("Maintain in organized filing system")
            requirements.append("Regular review and disposition")
        
        return requirements
    
    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get current status of the governance agent.
        
        Returns:
            Agent status information
        """
        base_status = super().get_agent_status()
        
        governance_specific_status = {
            "governance_metrics": self.governance_metrics,
            "active_counts": {
                "board_members": len(self.board_members),
                "board_meetings": len(self.board_meetings),
                "governance_policies": len(self.governance_policies),
                "shareholder_communications": len(self.shareholder_communications),
                "annual_reports": len(self.annual_reports),
                "compliance_records": len(self.compliance_records),
                "risk_assessments": len(self.risk_assessments),
                "corporate_records": len(self.corporate_records)
            },
            "templates_available": {
                "minutes_templates": len(self.minutes_templates),
                "policy_templates": len(self.policy_templates),
                "report_templates": len(self.report_templates)
            },
            "upcoming_deadlines": self._get_upcoming_governance_deadlines()
        }
        
        base_status.update(governance_specific_status)
        return base_status
    
    def _get_upcoming_governance_deadlines(self) -> Dict[str, Any]:
        """Get summary of upcoming governance deadlines."""
        upcoming = {
            "next_30_days": 0,
            "next_90_days": 0,
            "next_180_days": 0,
            "critical": 0
        }
        
        now = datetime.now()
        
        # Check annual report deadlines
        for report in self.annual_reports.values():
            if report.filing_deadline:
                days_until = (report.filing_deadline - now).days
                if 0 <= days_until <= 30:
                    upcoming["next_30_days"] += 1
                    if days_until <= 7:
                        upcoming["critical"] += 1
                elif days_until <= 90:
                    upcoming["next_90_days"] += 1
                elif days_until <= 180:
                    upcoming["next_180_days"] += 1
        
        # Check compliance deadlines
        for record in self.compliance_records.values():
            if record.due_date and record.status != "completed":
                days_until = (record.due_date - now).days
                if 0 <= days_until <= 30:
                    upcoming["next_30_days"] += 1
                    if days_until <= 3:
                        upcoming["critical"] += 1
                elif days_until <= 90:
                    upcoming["next_90_days"] += 1
                elif days_until <= 180:
                    upcoming["next_180_days"] += 1
        
        # Check policy review dates
        for policy in self.governance_policies.values():
            if policy.next_review:
                days_until = (policy.next_review - now).days
                if 0 <= days_until <= 90:
                    upcoming["next_90_days"] += 1
        
        return upcoming
    
    def _log_iso_compliance(self, action: str, details: Dict[str, Any]):
        """Log ISO compliance event."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "action": action,
            "details": details,
            "compliance_standard": "ISO 37000:2021 (Governance of Organizations)",
            "security_level": "confidential"
        }
        
        # Save to compliance log
        log_dir = Path("logs/compliance")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"governance_compliance_{datetime.now().strftime('%Y%m')}.json"
        
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


def test_corporate_governance_agent():
    """Test function for Corporate Governance Agent."""
    print("Testing Corporate Governance Agent...")
    
    # Create agent instance
    agent = CorporateGovernanceAgent("governance_agent_001")
    
    # Test 1: Manage board
    print("\n1. Testing board management...")
    board_data = {
        "name": "Dr. Sarah Johnson",
        "title": "Independent Director",
        "committee_memberships": ["Audit", "Compensation"],
        "independence_status": "independent",
        "qualifications": ["Financial Expert", "Technology Background"],
        "attendance_rate": 95.0
    }
    
    result = agent.handle_manage_board(board_data)
    print(f"Board management result: {result.get('success')}")
    print(f"Member ID: {result.get('member_id')}")
    
    # Test 2: Schedule meeting
    print("\n2. Testing meeting scheduling...")
    meeting_data = {
        "meeting_type": "board",
        "date": datetime.now().isoformat(),
        "location": "Pentagram Headquarters",
        "chairperson": "Chairperson Smith",
        "attendees": ["Director 1", "Director 2", "CEO"],
        "agenda_items": [
            {"topic": "Quarterly Financial Review", "presenter": "CFO"},
            {"topic": "Strategic Planning", "presenter": "CEO"}
        ]
    }
    
    result = agent.handle_schedule_meeting(meeting_data)
    print(f"Meeting scheduling result: {result.get('success')}")
    print(f"Meeting ID: {result.get('meeting_id')}")
    
    # Test 3: Create policy
    print("\n3. Testing policy creation...")
    policy_data = {
        "policy_type": "code_of_conduct",
        "title": "Code of Business Conduct and Ethics",
        "version": "2.0",
        "effective_date": datetime.now().isoformat(),
        "applicable_to": ["all_employees", "directors", "officers"],
        "compliance_areas": ["sec", "sox"],
        "training_required": True
    }
    
    result = agent.handle_create_policy(policy_data)
    print(f"Policy creation result: {result.get('success')}")
    print(f"Policy ID: {result.get('policy_id')}")
    
    # Test 4: Track compliance
    print("\n4. Testing compliance tracking...")
    compliance_data = {
        "compliance_area": "sec",
        "requirement": "Form 10-K Annual Report Filing",
        "due_date": (datetime.now() + timedelta(days=60)).isoformat(),
        "responsible_party": "Corporate Secretary",
        "evidence": ["Financial Statements", "Audit Opinion", "MD&A"]
    }
    
    result = agent.handle_track_compliance(compliance_data)
    print(f"Compliance tracking result: {result.get('success')}")
    print(f"Record ID: {result.get('record_id')}")
    
    # Test 5: Check agent status
    print("\n5. Testing agent status...")
    status = agent.get_agent_status()
    print(f"Agent active: {status.get('active')}")
    print(f"Governance metrics: {status.get('governance_metrics')}")
    
    print("\nCorporate Governance Agent test completed successfully!")


if __name__ == "__main__":
    test_corporate_governance_agent()