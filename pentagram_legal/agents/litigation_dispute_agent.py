"""
Litigation & Dispute Agent - Build 9 Part 1
Specialized agent for litigation management, dispute resolution, and case strategy.
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


class CaseType(Enum):
    """Types of legal cases."""
    CIVIL = "civil"
    CRIMINAL = "criminal"
    ADMINISTRATIVE = "administrative"
    APPELLATE = "appellate"
    CLASS_ACTION = "class_action"
    ARBITRATION = "arbitration"
    MEDIATION = "mediation"
    SMALL_CLAIMS = "small_claims"
    FAMILY = "family"
    BANKRUPTCY = "bankruptcy"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    EMPLOYMENT = "employment"
    CONTRACT = "contract"
    TORT = "tort"
    PROPERTY = "property"


class CaseStatus(Enum):
    """Status of legal cases."""
    INVESTIGATION = "investigation"
    PLEADINGS = "pleadings"
    DISCOVERY = "discovery"
    PRETRIAL = "pretrial"
    TRIAL = "trial"
    POST_TRIAL = "post_trial"
    APPEAL = "appeal"
    SETTLED = "settled"
    DISMISSED = "dismissed"
    JUDGMENT = "judgment"
    ENFORCEMENT = "enforcement"
    CLOSED = "closed"


class CourtLevel(Enum):
    """Levels of courts."""
    STATE_TRIAL = "state_trial"
    STATE_APPELLATE = "state_appellate"
    STATE_SUPREME = "state_supreme"
    FEDERAL_DISTRICT = "federal_district"
    FEDERAL_APPELLATE = "federal_appellate"
    US_SUPREME = "us_supreme"
    ADMINISTRATIVE = "administrative"
    INTERNATIONAL = "international"
    ARBITRATION = "arbitration"


class DiscoveryPhase(Enum):
    """Phases of discovery."""
    INITIAL_DISCLOSURES = "initial_disclosures"
    INTERROGATORIES = "interrogatories"
    REQUESTS_PRODUCTION = "requests_production"
    REQUESTS_ADMISSION = "requests_admission"
    DEPOSITIONS = "depositions"
    EXPERT_DISCOVERY = "expert_discovery"
    DISCOVERY_COMPLETE = "discovery_complete"


class MotionType(Enum):
    """Types of legal motions."""
    DISMISS = "dismiss"
    SUMMARY_JUDGMENT = "summary_judgment"
    COMPEL = "compel"
    PROTECTIVE_ORDER = "protective_order"
    LIMINE = "limine"
    CONTINUANCE = "continuance"
    DEFAULT_JUDGMENT = "default_judgment"
    SANCTIONS = "sanctions"
    APPEAL = "appeal"
    RECONSIDERATION = "reconsideration"


@dataclass
class LegalParty:
    """Party in a legal case."""
    party_id: str
    name: str
    role: str  # plaintiff, defendant, third_party, intervenor
    entity_type: str = "individual"  # individual, corporation, government, etc.
    representation: Optional[str] = None
    contact_info: Dict[str, str] = field(default_factory=dict)
    insurance_coverage: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class LegalCase:
    """Legal case representation."""
    case_id: str
    case_number: str
    case_type: CaseType
    court_level: CourtLevel
    jurisdiction: str
    caption: str
    filing_date: datetime
    parties: List[LegalParty] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)
    defenses: List[str] = field(default_factory=list)
    status: CaseStatus = CaseStatus.INVESTIGATION
    current_phase: DiscoveryPhase = DiscoveryPhase.INITIAL_DISCLOSURES
    assigned_attorney: Optional[str] = None
    opposing_counsel: Optional[str] = None
    judge: Optional[str] = None
    damages_sought: Optional[float] = None
    settlement_offers: List[Dict[str, Any]] = field(default_factory=list)
    key_dates: Dict[str, datetime] = field(default_factory=dict)
    documents: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DiscoveryRequest:
    """Discovery request in a case."""
    request_id: str
    case_id: str
    request_type: str  # interrogatory, production, admission
    requesting_party: str
    receiving_party: str
    questions: List[str] = field(default_factory=list)
    documents_requested: List[str] = field(default_factory=list)
    due_date: Optional[datetime] = None
    response_date: Optional[datetime] = None
    objections: List[str] = field(default_factory=list)
    responses: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, objected, responded, compelled
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class LegalMotion:
    """Legal motion in a case."""
    motion_id: str
    case_id: str
    motion_type: MotionType
    moving_party: str
    grounds: str
    relief_sought: str
    filing_date: datetime
    hearing_date: Optional[datetime] = None
    opposition_filed: bool = False
    reply_filed: bool = False
    decision: Optional[str] = None
    decision_date: Optional[datetime] = None
    status: str = "draft"  # draft, filed, scheduled, decided
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Deposition:
    """Deposition in a case."""
    deposition_id: str
    case_id: str
    deponent: str
    role: str  # party, witness, expert
    date: datetime
    location: str
    examining_attorney: str
    defending_attorney: Optional[str] = None
    transcript_available: bool = False
    transcript_location: Optional[str] = None
    key_testimony: List[str] = field(default_factory=list)
    status: str = "scheduled"  # scheduled, completed, transcribed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class SettlementOffer:
    """Settlement offer in a case."""
    offer_id: str
    case_id: str
    offering_party: str
    amount: float
    terms: List[str]
    expiration_date: datetime
    response: Optional[str] = None
    response_date: Optional[datetime] = None
    counter_offer: Optional[float] = None
    status: str = "pending"  # pending, accepted, rejected, countered
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TrialPreparation:
    """Trial preparation materials."""
    preparation_id: str
    case_id: str
    trial_date: datetime
    witness_list: List[Dict[str, Any]] = field(default_factory=list)
    exhibit_list: List[Dict[str, Any]] = field(default_factory=list)
    opening_statement: Optional[str] = None
    closing_argument: Optional[str] = None
    jury_instructions: List[str] = field(default_factory=list)
    voir_dire_questions: List[str] = field(default_factory=list)
    status: str = "preparation"  # preparation, ready, presented
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ADRProceeding:
    """Alternative Dispute Resolution proceeding."""
    adr_id: str
    case_id: str
    adr_type: str  # mediation, arbitration, negotiation
    neutral: str
    date: datetime
    location: str
    participants: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    outcome: Optional[str] = None
    settlement_reached: bool = False
    status: str = "scheduled"  # scheduled, completed, settled
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class LitigationDisputeAgent(BaseLegalAgent):
    """
    Specialized agent for litigation and dispute resolution.
    Handles case management, discovery, motions, settlements, and trial preparation.
    """
    
    def __init__(self, agent_id: str, jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL):
        """
        Initialize Litigation & Dispute Agent.
        
        Args:
            agent_id: Unique agent identifier
            jurisdiction: Primary jurisdiction
        """
        super().__init__(
            agent_id=agent_id,
            role=LegalAgentRole.LITIGATION,
            jurisdiction=jurisdiction,
            organization="Pentagram Litigation Group"
        )
        
        # Litigation specific attributes
        self.legal_cases: Dict[str, LegalCase] = {}
        self.discovery_requests: Dict[str, DiscoveryRequest] = {}
        self.legal_motions: Dict[str, LegalMotion] = {}
        self.depositions: Dict[str, Deposition] = {}
        self.settlement_offers: Dict[str, SettlementOffer] = {}
        self.trial_preparations: Dict[str, TrialPreparation] = {}
        self.adr_proceedings: Dict[str, ADRProceeding] = {}
        
        # Templates and configurations
        self.pleading_templates: Dict[str, Dict[str, Any]] = {}
        self.discovery_templates: Dict[str, Dict[str, Any]] = {}
        self.motion_templates: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self.litigation_metrics = {
            "cases_managed": 0,
            "discovery_requests": 0,
            "motions_filed": 0,
            "depositions_taken": 0,
            "settlements_reached": 0,
            "trials_prepared": 0,
            "adr_proceedings": 0,
            "success_rate": 0.0,  # Percentage
            "average_case_duration": 0,  # Days
            "total_damages_awarded": 0.0,
            "total_settlement_value": 0.0
        }
        
        # Register litigation specific intent handlers
        self._register_litigation_handlers()
        
        logger.info(f"Initialized Litigation & Dispute Agent {agent_id}")
    
    def _register_litigation_handlers(self):
        """Register litigation specific intent handlers."""
        self.register_handler("open_case", self.handle_open_case)
        self.register_handler("manage_discovery", self.handle_manage_discovery)
        self.register_handler("file_motion", self.handle_file_motion)
        self.register_handler("schedule_deposition", self.handle_schedule_deposition)
        self.register_handler("negotiate_settlement", self.handle_negotiate_settlement)
        self.register_handler("prepare_for_trial", self.handle_prepare_for_trial)
        self.register_handler("initiate_adr", self.handle_initiate_adr)
        self.register_handler("track_deadlines", self.handle_track_deadlines)
        
        logger.info("Registered litigation intent handlers")
    
    def handle_open_case(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle opening of a new legal case.
        
        Args:
            intent_data: Case opening data
            
        Returns:
            Case opening result
        """
        try:
            case_id = intent_data.get("case_id", f"case_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            case_number = intent_data.get("case_number", "")
            case_type_str = intent_data.get("case_type", "civil")
            court_level_str = intent_data.get("court_level", "state_trial")
            jurisdiction = intent_data.get("jurisdiction", "California")
            caption = intent_data.get("caption", "")
            filing_date_str = intent_data.get("filing_date", datetime.now().isoformat())
            
            # Parse filing date
            filing_date = datetime.fromisoformat(filing_date_str.replace('Z', '+00:00'))
            
            # Create legal case
            legal_case = LegalCase(
                case_id=case_id,
                case_number=case_number,
                case_type=CaseType(case_type_str),
                court_level=CourtLevel(court_level_str),
                jurisdiction=jurisdiction,
                caption=caption,
                filing_date=filing_date,
                claims=intent_data.get("claims", []),
                defenses=intent_data.get("defenses", []),
                status=CaseStatus.INVESTIGATION,
                current_phase=DiscoveryPhase.INITIAL_DISCLOSURES,
                assigned_attorney=intent_data.get("assigned_attorney"),
                opposing_counsel=intent_data.get("opposing_counsel"),
                damages_sought=intent_data.get("damages_sought")
            )
            
            # Add parties if provided
            for party_data in intent_data.get("parties", []):
                party = LegalParty(
                    party_id=party_data.get("party_id", f"party_{len(legal_case.parties) + 1}"),
                    name=party_data.get("name"),
                    role=party_data.get("role", "defendant"),
                    entity_type=party_data.get("entity_type", "individual"),
                    representation=party_data.get("representation"),
                    contact_info=party_data.get("contact_info", {}),
                    insurance_coverage=party_data.get("insurance_coverage")
                )
                legal_case.parties.append(party)
            
            # Set key dates
            legal_case.key_dates = {
                "filing": filing_date,
                "initial_conference": filing_date + timedelta(days=45),
                "disclosure_deadline": filing_date + timedelta(days=60),
                "discovery_cutoff": filing_date + timedelta(days=180),
                "pretrial_conference": filing_date + timedelta(days=210)
            }
            
            # Store the case
            self.legal_cases[case_id] = legal_case
            
            # Update metrics
            self.litigation_metrics["cases_managed"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="open_case",
                details={
                    "case_id": case_id,
                    "case_number": case_number,
                    "case_type": case_type_str,
                    "court_level": court_level_str,
                    "jurisdiction": jurisdiction,
                    "party_count": len(legal_case.parties)
                }
            )
            
            logger.info(f"Opened case {case_id}: {caption}")
            
            return {
                "success": True,
                "case_id": case_id,
                "message": f"Case {case_id} opened successfully",
                "case_summary": {
                    "caption": caption,
                    "case_number": case_number,
                    "type": case_type_str,
                    "court": court_level_str,
                    "filing_date": filing_date.isoformat(),
                    "status": legal_case.status.value,
                    "parties": [{"name": p.name, "role": p.role} for p in legal_case.parties]
                },
                "next_steps": [
                    "Serve parties",
                    "File initial pleadings",
                    "Schedule case management conference",
                    "Begin discovery planning"
                ],
                "key_dates": {k: v.isoformat() for k, v in legal_case.key_dates.items()}
            }
            
        except Exception as e:
            logger.error(f"Error opening case: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to open case"
            }
    
    def handle_manage_discovery(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle management of discovery requests.
        
        Args:
            intent_data: Discovery management data
            
        Returns:
            Discovery management result
        """
        try:
            request_id = intent_data.get("request_id", f"disc_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            case_id = intent_data.get("case_id", "")
            request_type = intent_data.get("request_type", "interrogatory")
            requesting_party = intent_data.get("requesting_party", "")
            receiving_party = intent_data.get("receiving_party", "")
            
            # Check if case exists
            if case_id not in self.legal_cases:
                return {
                    "success": False,
                    "error": f"Case {case_id} not found",
                    "message": "Cannot manage discovery for unknown case"
                }
            
            # Create discovery request
            discovery_request = DiscoveryRequest(
                request_id=request_id,
                case_id=case_id,
                request_type=request_type,
                requesting_party=requesting_party,
                receiving_party=receiving_party,
                questions=intent_data.get("questions", []),
                documents_requested=intent_data.get("documents_requested", []),
                due_date=intent_data.get("due_date"),
                status="pending"
            )
            
            # Set default due date (30 days)
            if not discovery_request.due_date:
                discovery_request.due_date = datetime.now() + timedelta(days=30)
            
            # Store the request
            self.discovery_requests[request_id] = discovery_request
            
            # Update case phase if needed
            case = self.legal_cases[case_id]
            if case.current_phase == DiscoveryPhase.INITIAL_DISCLOSURES:
                case.current_phase = DiscoveryPhase.INTERROGATORIES
            case.updated_at = datetime.now()
            
            # Update metrics
            self.litigation_metrics["discovery_requests"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="manage_discovery",
                details={
                    "request_id": request_id,
                    "case_id": case_id,
                    "request_type": request_type,
                    "requesting_party": requesting_party,
                    "question_count": len(discovery_request.questions),
                    "document_count": len(discovery_request.documents_requested)
                }
            )
            
            logger.info(f"Managed discovery request {request_id} for case {case_id}")
            
            return {
                "success": True,
                "request_id": request_id,
                "message": f"Discovery request {request_id} managed successfully",
                "discovery_details": {
                    "case": case.caption,
                    "type": request_type,
                    "from": requesting_party,
                    "to": receiving_party,
                    "due_date": discovery_request.due_date.isoformat() if discovery_request.due_date else None,
                    "questions": len(discovery_request.questions),
                    "documents": len(discovery_request.documents_requested)
                },
                "response_guidelines": self._get_discovery_response_guidelines(request_type)
            }
            
        except Exception as e:
            logger.error(f"Error managing discovery: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to manage discovery"
            }
    
    def handle_file_motion(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle filing of a legal motion.
        
        Args:
            intent_data: Motion filing data
            
        Returns:
            Motion filing result
        """
        try:
            motion_id = intent_data.get("motion_id", f"motion_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            case_id = intent_data.get("case_id", "")
            motion_type_str = intent_data.get("motion_type", "dismiss")
            moving_party = intent_data.get("moving_party", "")
            grounds = intent_data.get("grounds", "")
            relief_sought = intent_data.get("relief_sought", "")
            filing_date_str = intent_data.get("filing_date", datetime.now().isoformat())
            
            # Parse filing date
            filing_date = datetime.fromisoformat(filing_date_str.replace('Z', '+00:00'))
            
            # Check if case exists
            if case_id not in self.legal_cases:
                return {
                    "success": False,
                    "error": f"Case {case_id} not found",
                    "message": "Cannot file motion for unknown case"
                }
            
            # Create legal motion
            motion = LegalMotion(
                motion_id=motion_id,
                case_id=case_id,
                motion_type=MotionType(motion_type_str),
                moving_party=moving_party,
                grounds=grounds,
                relief_sought=relief_sought,
                filing_date=filing_date,
                status="filed"
            )
            
            # Set hearing date (default 30 days after filing)
            motion.hearing_date = filing_date + timedelta(days=30)
            
            # Store the motion
            self.legal_motions[motion_id] = motion
            
            # Update metrics
            self.litigation_metrics["motions_filed"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="file_motion",
                details={
                    "motion_id": motion_id,
                    "case_id": case_id,
                    "motion_type": motion_type_str,
                    "moving_party": moving_party,
                    "relief_sought": relief_sought
                }
            )
            
            logger.info(f"Filed motion {motion_id} for case {case_id}")
            
            return {
                "success": True,
                "motion_id": motion_id,
                "message": f"Motion {motion_id} filed successfully",
                "motion_details": {
                    "case": self.legal_cases[case_id].caption,
                    "type": motion_type_str,
                    "moving_party": moving_party,
                    "grounds": grounds,
                    "relief_sought": relief_sought,
                    "filing_date": filing_date.isoformat(),
                    "hearing_date": motion.hearing_date.isoformat() if motion.hearing_date else None
                },
                "next_steps": [
                    "Serve motion on opposing counsel",
                    "Prepare memorandum of points and authorities",
                    "Schedule hearing with court",
                    "Prepare for oral argument"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error filing motion: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to file motion"
            }
    
    def handle_schedule_deposition(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle scheduling of a deposition.
        
        Args:
            intent_data: Deposition scheduling data
            
        Returns:
            Deposition scheduling result
        """
        try:
            deposition_id = intent_data.get("deposition_id", f"dep_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            case_id = intent_data.get("case_id", "")
            deponent = intent_data.get("deponent", "")
            role = intent_data.get("role", "witness")
            date_str = intent_data.get("date", datetime.now().isoformat())
            location = intent_data.get("location", "Law Office Conference Room")
            examining_attorney = intent_data.get("examining_attorney", "")
            
            # Parse date
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            # Check if case exists
            if case_id not in self.legal_cases:
                return {
                    "success": False,
                    "error": f"Case {case_id} not found",
                    "message": "Cannot schedule deposition for unknown case"
                }
            
            # Create deposition
            deposition = Deposition(
                deposition_id=deposition_id,
                case_id=case_id,
                deponent=deponent,
                role=role,
                date=date,
                location=location,
                examining_attorney=examining_attorney,
                defending_attorney=intent_data.get("defending_attorney"),
                status="scheduled"
            )
            
            # Store the deposition
            self.depositions[deposition_id] = deposition
            
            # Update metrics
            self.litigation_metrics["depositions_taken"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="schedule_deposition",
                details={
                    "deposition_id": deposition_id,
                    "case_id": case_id,
                    "deponent": deponent,
                    "role": role,
                    "examining_attorney": examining_attorney
                }
            )
            
            logger.info(f"Scheduled deposition {deposition_id} for case {case_id}")
            
            return {
                "success": True,
                "deposition_id": deposition_id,
                "message": f"Deposition {deposition_id} scheduled successfully",
                "deposition_details": {
                    "case": self.legal_cases[case_id].caption,
                    "deponent": deponent,
                    "role": role,
                    "date": date.isoformat(),
                    "location": location,
                    "examining_attorney": examining_attorney,
                    "defending_attorney": deposition.defending_attorney
                },
                "preparation_steps": [
                    "Prepare deposition notice",
                    "Draft examination outline",
                    "Coordinate with court reporter",
                    "Arrange for videography if needed",
                    "Prepare exhibits"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error scheduling deposition: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to schedule deposition"
            }
    
    def handle_negotiate_settlement(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle negotiation of a settlement.
        
        Args:
            intent_data: Settlement negotiation data
            
        Returns:
            Settlement negotiation result
        """
        try:
            offer_id = intent_data.get("offer_id", f"offer_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            case_id = intent_data.get("case_id", "")
            offering_party = intent_data.get("offering_party", "")
            amount = intent_data.get("amount", 0.0)
            terms = intent_data.get("terms", [])
            expiration_date_str = intent_data.get("expiration_date", (datetime.now() + timedelta(days=30)).isoformat())
            
            # Parse expiration date
            expiration_date = datetime.fromisoformat(expiration_date_str.replace('Z', '+00:00'))
            
            # Check if case exists
            if case_id not in self.legal_cases:
                return {
                    "success": False,
                    "error": f"Case {case_id} not found",
                    "message": "Cannot negotiate settlement for unknown case"
                }
            
            # Create settlement offer
            settlement_offer = SettlementOffer(
                offer_id=offer_id,
                case_id=case_id,
                offering_party=offering_party,
                amount=amount,
                terms=terms,
                expiration_date=expiration_date,
                status="pending"
            )
            
            # Store the offer
            self.settlement_offers[offer_id] = settlement_offer
            
            # Add to case
            case = self.legal_cases[case_id]
            case.settlement_offers.append({
                "offer_id": offer_id,
                "offering_party": offering_party,
                "amount": amount,
                "expiration_date": expiration_date.isoformat()
            })
            case.updated_at = datetime.now()
            
            # Update metrics
            if settlement_offer.status == "accepted":
                self.litigation_metrics["settlements_reached"] += 1
                self.litigation_metrics["total_settlement_value"] += amount
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="negotiate_settlement",
                details={
                    "offer_id": offer_id,
                    "case_id": case_id,
                    "offering_party": offering_party,
                    "amount": amount,
                    "term_count": len(terms)
                }
            )
            
            logger.info(f"Negotiated settlement offer {offer_id} for case {case_id}")
            
            return {
                "success": True,
                "offer_id": offer_id,
                "message": f"Settlement offer {offer_id} negotiated successfully",
                "offer_details": {
                    "case": case.caption,
                    "offering_party": offering_party,
                    "amount": f"${amount:,.2f}",
                    "terms": terms,
                    "expiration_date": expiration_date.isoformat(),
                    "days_until_expiration": (expiration_date - datetime.now()).days
                },
                "evaluation_factors": [
                    "Strength of legal position",
                    "Cost of continued litigation",
                    "Time to resolution",
                    "Risk of adverse judgment",
                    "Client objectives"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error negotiating settlement: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to negotiate settlement"
            }
    
    def handle_prepare_for_trial(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle preparation for trial.
        
        Args:
            intent_data: Trial preparation data
            
        Returns:
            Trial preparation result
        """
        try:
            preparation_id = intent_data.get("preparation_id", f"trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            case_id = intent_data.get("case_id", "")
            trial_date_str = intent_data.get("trial_date", datetime.now().isoformat())
            
            # Parse trial date
            trial_date = datetime.fromisoformat(trial_date_str.replace('Z', '+00:00'))
            
            # Check if case exists
            if case_id not in self.legal_cases:
                return {
                    "success": False,
                    "error": f"Case {case_id} not found",
                    "message": "Cannot prepare for trial for unknown case"
                }
            
            # Create trial preparation
            trial_prep = TrialPreparation(
                preparation_id=preparation_id,
                case_id=case_id,
                trial_date=trial_date,
                witness_list=intent_data.get("witness_list", []),
                exhibit_list=intent_data.get("exhibit_list", []),
                opening_statement=intent_data.get("opening_statement"),
                closing_argument=intent_data.get("closing_argument"),
                jury_instructions=intent_data.get("jury_instructions", []),
                voir_dire_questions=intent_data.get("voir_dire_questions", []),
                status="preparation"
            )
            
            # Store the preparation
            self.trial_preparations[preparation_id] = trial_prep
            
            # Update case status
            case = self.legal_cases[case_id]
            case.status = CaseStatus.TRIAL
            case.updated_at = datetime.now()
            
            # Update metrics
            self.litigation_metrics["trials_prepared"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="prepare_for_trial",
                details={
                    "preparation_id": preparation_id,
                    "case_id": case_id,
                    "trial_date": trial_date.isoformat(),
                    "witness_count": len(trial_prep.witness_list),
                    "exhibit_count": len(trial_prep.exhibit_list)
                }
            )
            
            logger.info(f"Prepared for trial {preparation_id} for case {case_id}")
            
            return {
                "success": True,
                "preparation_id": preparation_id,
                "message": f"Trial preparation {preparation_id} completed successfully",
                "preparation_summary": {
                    "case": case.caption,
                    "trial_date": trial_date.isoformat(),
                    "days_until_trial": (trial_date - datetime.now()).days,
                    "witnesses": len(trial_prep.witness_list),
                    "exhibits": len(trial_prep.exhibit_list),
                    "status": trial_prep.status
                },
                "checklist": [
                    "Finalize witness list and order",
                    "Prepare exhibit binders",
                    "Draft opening and closing statements",
                    "Prepare direct and cross examinations",
                    "Review jury instructions",
                    "Prepare voir dire questions",
                    "Coordinate with expert witnesses",
                    "Prepare trial notebooks"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error preparing for trial: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to prepare for trial"
            }
    
    def handle_initiate_adr(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle initiation of Alternative Dispute Resolution.
        
        Args:
            intent_data: ADR initiation data
            
        Returns:
            ADR initiation result
        """
        try:
            adr_id = intent_data.get("adr_id", f"adr_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            case_id = intent_data.get("case_id", "")
            adr_type = intent_data.get("adr_type", "mediation")
            neutral = intent_data.get("neutral", "")
            date_str = intent_data.get("date", datetime.now().isoformat())
            location = intent_data.get("location", "Mediation Center")
            
            # Parse date
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            # Check if case exists
            if case_id not in self.legal_cases:
                return {
                    "success": False,
                    "error": f"Case {case_id} not found",
                    "message": "Cannot initiate ADR for unknown case"
                }
            
            # Create ADR proceeding
            adr_proceeding = ADRProceeding(
                adr_id=adr_id,
                case_id=case_id,
                adr_type=adr_type,
                neutral=neutral,
                date=date,
                location=location,
                participants=intent_data.get("participants", []),
                issues=intent_data.get("issues", []),
                status="scheduled"
            )
            
            # Store the proceeding
            self.adr_proceedings[adr_id] = adr_proceeding
            
            # Update metrics
            self.litigation_metrics["adr_proceedings"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="initiate_adr",
                details={
                    "adr_id": adr_id,
                    "case_id": case_id,
                    "adr_type": adr_type,
                    "neutral": neutral,
                    "participant_count": len(adr_proceeding.participants)
                }
            )
            
            logger.info(f"Initiated ADR {adr_id} for case {case_id}")
            
            return {
                "success": True,
                "adr_id": adr_id,
                "message": f"ADR proceeding {adr_id} initiated successfully",
                "adr_details": {
                    "case": self.legal_cases[case_id].caption,
                    "type": adr_type,
                    "neutral": neutral,
                    "date": date.isoformat(),
                    "location": location,
                    "participants": adr_proceeding.participants,
                    "issues": adr_proceeding.issues
                },
                "preparation_steps": self._get_adr_preparation_steps(adr_type)
            }
            
        except Exception as e:
            logger.error(f"Error initiating ADR: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to initiate ADR"
            }
    
    def handle_track_deadlines(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tracking of litigation deadlines.
        
        Args:
            intent_data: Deadline tracking data
            
        Returns:
            Deadline tracking result
        """
        try:
            days_ahead = intent_data.get("days_ahead", 30)
            cutoff_date = datetime.now() + timedelta(days=days_ahead)
            
            deadlines = []
            
            # Check case deadlines
            for case_id, case in self.legal_cases.items():
                for date_name, date_value in case.key_dates.items():
                    if date_value and date_value <= cutoff_date:
                        # Check if this is a meaningful deadline
                        if date_name in ["disclosure_deadline", "discovery_cutoff", "pretrial_conference", "trial_date"]:
                            deadlines.append({
                                "type": "case_deadline",
                                "case_id": case_id,
                                "description": f"{date_name.replace('_', ' ').title()} for {case.caption}",
                                "due_date": date_value.isoformat(),
                                "days_remaining": (date_value - datetime.now()).days,
                                "priority": self._get_deadline_priority(date_name, date_value)
                            })
            
            # Check discovery deadlines
            for request_id, request in self.discovery_requests.items():
                if request.due_date and request.due_date <= cutoff_date and request.status == "pending":
                    case = self.legal_cases.get(request.case_id)
                    if case:
                        deadlines.append({
                            "type": "discovery_deadline",
                            "request_id": request_id,
                            "case_id": request.case_id,
                            "description": f"Discovery response due from {request.receiving_party}",
                            "due_date": request.due_date.isoformat(),
                            "days_remaining": (request.due_date - datetime.now()).days,
                            "priority": "high" if (request.due_date - datetime.now()).days < 7 else "medium"
                        })
            
            # Check motion hearing dates
            for motion_id, motion in self.legal_motions.items():
                if motion.hearing_date and motion.hearing_date <= cutoff_date and motion.status == "filed":
                    case = self.legal_cases.get(motion.case_id)
                    if case:
                        deadlines.append({
                            "type": "motion_hearing",
                            "motion_id": motion_id,
                            "case_id": motion.case_id,
                            "description": f"Hearing on {motion.motion_type.value} motion",
                            "due_date": motion.hearing_date.isoformat(),
                            "days_remaining": (motion.hearing_date - datetime.now()).days,
                            "priority": "high" if (motion.hearing_date - datetime.now()).days < 14 else "medium"
                        })
            
            # Check deposition dates
            for deposition_id, deposition in self.depositions.items():
                if deposition.date and deposition.date <= cutoff_date and deposition.status == "scheduled":
                    case = self.legal_cases.get(deposition.case_id)
                    if case:
                        deadlines.append({
                            "type": "deposition",
                            "deposition_id": deposition_id,
                            "case_id": deposition.case_id,
                            "description": f"Deposition of {deposition.deponent}",
                            "due_date": deposition.date.isoformat(),
                            "days_remaining": (deposition.date - datetime.now()).days,
                            "priority": "medium"
                        })
            
            # Sort by priority and days remaining
            deadlines.sort(key=lambda x: (x["priority"], x["days_remaining"]))
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="track_deadlines",
                details={
                    "days_ahead": days_ahead,
                    "deadlines_found": len(deadlines),
                    "high_priority": len([d for d in deadlines if d["priority"] == "high"])
                }
            )
            
            logger.info(f"Tracked deadlines for next {days_ahead} days, found {len(deadlines)} deadlines")
            
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
            logger.error(f"Error tracking deadlines: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to track deadlines"
            }
    
    def _get_discovery_response_guidelines(self, request_type: str) -> List[str]:
        """Get guidelines for responding to discovery requests."""
        guidelines = []
        
        if request_type == "interrogatory":
            guidelines = [
                "Answer each interrogatory separately and fully",
                "Object to improper questions with specificity",
                "Provide verified responses under oath",
                "Supplement responses if additional information becomes available"
            ]
        elif request_type == "production":
            guidelines = [
                "Produce responsive documents in a reasonable manner",
                "Organize and label documents to correspond to requests",
                "Prepare a privilege log for withheld documents",
                "Object to overbroad or unduly burdensome requests"
            ]
        elif request_type == "admission":
            guidelines = [
                "Admit or deny each request specifically",
                "State reasons for inability to admit or deny",
                "Object to improper requests",
                "Responses are binding for purposes of the case"
            ]
        
        return guidelines
    
    def _get_adr_preparation_steps(self, adr_type: str) -> List[str]:
        """Get preparation steps for ADR proceedings."""
        steps = []
        
        if adr_type == "mediation":
            steps = [
                "Prepare mediation brief summarizing positions",
                "Identify key issues for resolution",
                "Determine settlement authority",
                "Prepare opening statement",
                "Identify potential settlement options",
                "Coordinate with mediator on logistics"
            ]
        elif adr_type == "arbitration":
            steps = [
                "Prepare arbitration submission",
                "Organize evidence and exhibits",
                "Prepare witness statements",
                "Research arbitrator's background",
                "Prepare opening and closing arguments",
                "Understand arbitration rules and procedures"
            ]
        elif adr_type == "negotiation":
            steps = [
                "Define negotiation objectives and BATNA",
                "Prepare negotiation strategy",
                "Research opposing party's interests",
                "Identify potential trade-offs",
                "Prepare draft settlement agreement",
                "Coordinate meeting logistics"
            ]
        
        return steps
    
    def _get_deadline_priority(self, deadline_type: str, deadline_date: datetime) -> str:
        """Determine priority level for a deadline."""
        days_until = (deadline_date - datetime.now()).days
        
        if deadline_type in ["trial_date", "discovery_cutoff"]:
            if days_until < 30:
                return "high"
            elif days_until < 60:
                return "medium"
            else:
                return "low"
        elif deadline_type in ["disclosure_deadline", "pretrial_conference"]:
            if days_until < 14:
                return "high"
            elif days_until < 30:
                return "medium"
            else:
                return "low"
        else:
            if days_until < 7:
                return "high"
            elif days_until < 14:
                return "medium"
            else:
                return "low"
    
    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get current status of the litigation agent.
        
        Returns:
            Agent status information
        """
        base_status = super().get_agent_status()
        
        litigation_specific_status = {
            "litigation_metrics": self.litigation_metrics,
            "active_counts": {
                "legal_cases": len(self.legal_cases),
                "discovery_requests": len(self.discovery_requests),
                "legal_motions": len(self.legal_motions),
                "depositions": len(self.depositions),
                "settlement_offers": len(self.settlement_offers),
                "trial_preparations": len(self.trial_preparations),
                "adr_proceedings": len(self.adr_proceedings)
            },
            "templates_available": {
                "pleading_templates": len(self.pleading_templates),
                "discovery_templates": len(self.discovery_templates),
                "motion_templates": len(self.motion_templates)
            },
            "case_status_summary": self._get_case_status_summary()
        }
        
        base_status.update(litigation_specific_status)
        return base_status
    
    def _get_case_status_summary(self) -> Dict[str, Any]:
        """Get summary of case statuses."""
        summary = {
            "total_cases": len(self.legal_cases),
            "by_status": {},
            "by_type": {},
            "by_court": {}
        }
        
        # Count by status
        for case in self.legal_cases.values():
            status = case.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            case_type = case.case_type.value
            summary["by_type"][case_type] = summary["by_type"].get(case_type, 0) + 1
            
            court = case.court_level.value
            summary["by_court"][court] = summary["by_court"].get(court, 0) + 1
        
        return summary
    
    def _log_iso_compliance(self, action: str, details: Dict[str, Any]):
        """Log ISO compliance event."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "action": action,
            "details": details,
            "compliance_standard": "ISO 20700:2017 (Legal Services)",
            "security_level": "confidential"
        }
        
        # Save to compliance log
        log_dir = Path("logs/compliance")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"litigation_compliance_{datetime.now().strftime('%Y%m')}.json"
        
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


def test_litigation_dispute_agent():
    """Test function for Litigation & Dispute Agent."""
    print("Testing Litigation & Dispute Agent...")
    
    # Create agent instance
    agent = LitigationDisputeAgent("litigation_agent_001")
    
    # Test 1: Open case
    print("\n1. Testing case opening...")
    case_data = {
        "case_number": "CV-2024-001234",
        "case_type": "civil",
        "court_level": "state_trial",
        "jurisdiction": "California",
        "caption": "Smith v. Jones Corporation",
        "filing_date": datetime.now().isoformat(),
        "claims": ["Breach of contract", "Fraud"],
        "parties": [
            {
                "name": "John Smith",
                "role": "plaintiff",
                "entity_type": "individual"
            },
            {
                "name": "Jones Corporation",
                "role": "defendant",
                "entity_type": "corporation"
            }
        ]
    }
    
    result = agent.handle_open_case(case_data)
    print(f"Case opening result: {result.get('success')}")
    print(f"Case ID: {result.get('case_id')}")
    
    case_id = result.get("case_id")
    
    # Test 2: Manage discovery
    print("\n2. Testing discovery management...")
    discovery_data = {
        "case_id": case_id,
        "request_type": "interrogatory",
        "requesting_party": "Plaintiff",
        "receiving_party": "Defendant",
        "questions": [
            "Identify all persons with knowledge of the contract",
            "Describe all communications regarding the alleged breach"
        ]
    }
    
    result = agent.handle_manage_discovery(discovery_data)
    print(f"Discovery management result: {result.get('success')}")
    print(f"Request ID: {result.get('request_id')}")
    
    # Test 3: File motion
    print("\n3. Testing motion filing...")
    motion_data = {
        "case_id": case_id,
        "motion_type": "dismiss",
        "moving_party": "Defendant",
        "grounds": "Failure to state a claim upon which relief can be granted",
        "relief_sought": "Dismissal of complaint with prejudice"
    }
    
    result = agent.handle_file_motion(motion_data)
    print(f"Motion filing result: {result.get('success')}")
    print(f"Motion ID: {result.get('motion_id')}")
    
    # Test 4: Track deadlines
    print("\n4. Testing deadline tracking...")
    result = agent.handle_track_deadlines({"days_ahead": 90})
    print(f"Deadline tracking result: {result.get('success')}")
    print(f"Deadlines found: {result.get('summary', {}).get('total', 0)}")
    
    # Test 5: Check agent status
    print("\n5. Testing agent status...")
    status = agent.get_agent_status()
    print(f"Agent active: {status.get('active')}")
    print(f"Litigation metrics: {status.get('litigation_metrics')}")
    
    print("\nLitigation & Dispute Agent test completed successfully!")


if __name__ == "__main__":
    test_litigation_dispute_agent()