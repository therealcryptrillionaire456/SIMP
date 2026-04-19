"""
M&A Transaction Agent - Build 6 Part 1
Specialized agent for mergers, acquisitions, due diligence, deal structuring, and integration planning.
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


class DealPhase(Enum):
    """Phases of an M&A transaction."""
    PRELIMINARY = "preliminary"
    DUE_DILIGENCE = "due_diligence"
    NEGOTIATION = "negotiation"
    DOCUMENTATION = "documentation"
    CLOSING = "closing"
    INTEGRATION = "integration"
    POST_CLOSING = "post_closing"


class DealType(Enum):
    """Types of M&A transactions."""
    MERGER = "merger"
    ACQUISITION = "acquisition"
    ASSET_PURCHASE = "asset_purchase"
    STOCK_PURCHASE = "stock_purchase"
    JOINT_VENTURE = "joint_venture"
    STRATEGIC_ALLIANCE = "strategic_alliance"
    LEVERAGED_BUYOUT = "leveraged_buyout"
    MANAGEMENT_BUYOUT = "management_buyout"


class DueDiligenceArea(Enum):
    """Areas of due diligence."""
    FINANCIAL = "financial"
    LEGAL = "legal"
    OPERATIONAL = "operational"
    TECHNICAL = "technical"
    COMMERCIAL = "commercial"
    TAX = "tax"
    ENVIRONMENTAL = "environmental"
    IP = "intellectual_property"
    HR = "human_resources"
    REGULATORY = "regulatory"


@dataclass
class DealParty:
    """Party involved in a transaction."""
    name: str
    type: str  # "acquirer", "target", "seller", "buyer", "investor"
    jurisdiction: str
    contact_info: Dict[str, str] = field(default_factory=dict)
    financial_capacity: Optional[float] = None
    legal_entity_type: str = "corporation"


@dataclass
class DueDiligenceItem:
    """Individual due diligence item."""
    id: str
    area: DueDiligenceArea
    description: str
    status: str = "pending"  # pending, in_progress, completed, flagged
    findings: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical
    assigned_to: Optional[str] = None
    deadline: Optional[datetime] = None
    documents: List[str] = field(default_factory=list)


@dataclass
class DealTerm:
    """Key term in a transaction."""
    term_type: str  # "purchase_price", "earn_out", "escrow", "indemnification", "representation"
    description: str
    value: Any
    conditions: List[str] = field(default_factory=list)
    negotiated_by: Optional[str] = None
    status: str = "proposed"  # proposed, agreed, rejected, modified


@dataclass
class Transaction:
    """Complete M&A transaction representation."""
    transaction_id: str
    deal_type: DealType
    phase: DealPhase = DealPhase.PRELIMINARY
    parties: List[DealParty] = field(default_factory=list)
    due_diligence_items: List[DueDiligenceItem] = field(default_factory=list)
    deal_terms: List[DealTerm] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    timeline: Dict[str, datetime] = field(default_factory=dict)
    risks: List[Dict[str, Any]] = field(default_factory=list)
    valuation: Optional[float] = None
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class MATransactionAgent(BaseLegalAgent):
    """
    Specialized agent for M&A transactions.
    Handles mergers, acquisitions, due diligence, deal structuring, and integration.
    """
    
    def __init__(self, agent_id: str, jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL):
        """
        Initialize M&A Transaction Agent.
        
        Args:
            agent_id: Unique agent identifier
            jurisdiction: Primary jurisdiction
        """
        super().__init__(
            agent_id=agent_id,
            role=LegalAgentRole.M_A,
            jurisdiction=jurisdiction,
            organization="Pentagram Tech Acquisitions"
        )
        
        # M&A specific attributes
        self.active_transactions: Dict[str, Transaction] = {}
        self.due_diligence_templates: Dict[str, List[DueDiligenceItem]] = {}
        self.deal_templates: Dict[str, Dict[str, Any]] = {}
        self.integration_plans: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self.transaction_metrics = {
            "transactions_completed": 0,
            "total_deal_value": 0.0,
            "average_deal_size": 0.0,
            "due_diligence_items_processed": 0,
            "documents_generated": 0,
            "risks_identified": 0,
            "regulatory_filings": 0
        }
        
        # Register M&A specific intent handlers
        self._register_ma_handlers()
        
        logger.info(f"Initialized M&A Transaction Agent {agent_id}")
    
    def _register_ma_handlers(self):
        """Register M&A specific intent handlers."""
        self.register_handler("create_transaction", self.handle_create_transaction)
        self.register_handler("add_due_diligence", self.handle_add_due_diligence)
        self.register_handler("analyze_risk", self.handle_analyze_risk)
        self.register_handler("generate_document", self.handle_generate_document)
        self.register_handler("advance_phase", self.handle_advance_phase)
        self.register_handler("calculate_valuation", self.handle_calculate_valuation)
        self.register_handler("check_regulatory", self.handle_check_regulatory)
        self.register_handler("create_integration_plan", self.handle_create_integration_plan)
    
    def handle_create_transaction(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle creation of a new M&A transaction.
        
        Args:
            intent_data: Transaction creation data
            
        Returns:
            Transaction creation result
        """
        try:
            transaction_id = intent_data.get("transaction_id", f"txn_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            deal_type_str = intent_data.get("deal_type", "acquisition")
            
            # Create transaction
            transaction = Transaction(
                transaction_id=transaction_id,
                deal_type=DealType(deal_type_str),
                phase=DealPhase.PRELIMINARY
            )
            
            # Add parties
            for party_data in intent_data.get("parties", []):
                party = DealParty(
                    name=party_data.get("name"),
                    type=party_data.get("type"),
                    jurisdiction=party_data.get("jurisdiction", "US"),
                    contact_info=party_data.get("contact_info", {}),
                    financial_capacity=party_data.get("financial_capacity"),
                    legal_entity_type=party_data.get("legal_entity_type", "corporation")
                )
                transaction.parties.append(party)
            
            # Add initial due diligence items
            self._add_standard_due_diligence(transaction)
            
            # Store transaction
            self.active_transactions[transaction_id] = transaction
            
            # Update metrics
            self.transaction_metrics["transactions_completed"] += 1
            
            # Create legal matter
            matter = LegalMatter(
                matter_id=transaction_id,
                title=f"M&A Transaction: {transaction_id}",
                description=f"{deal_type_str} transaction",
                jurisdiction=self.jurisdiction,
                practice_area=self.role,
                status="active",
                priority=1  # High priority
            )
            self.active_matters[transaction_id] = matter
            
            logger.info(f"Created transaction {transaction_id}")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "phase": transaction.phase.value,
                "parties": [p.name for p in transaction.parties],
                "due_diligence_items": len(transaction.due_diligence_items)
            }
            
        except Exception as e:
            logger.error(f"Failed to create transaction: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _add_standard_due_diligence(self, transaction: Transaction):
        """Add standard due diligence items for a transaction."""
        standard_items = [
            DueDiligenceItem(
                id=f"dd_financial_{transaction.transaction_id}",
                area=DueDiligenceArea.FINANCIAL,
                description="Financial statements and projections review",
                risk_level="medium"
            ),
            DueDiligenceItem(
                id=f"dd_legal_{transaction.transaction_id}",
                area=DueDiligenceArea.LEGAL,
                description="Corporate records and contracts review",
                risk_level="high"
            ),
            DueDiligenceItem(
                id=f"dd_ip_{transaction.transaction_id}",
                area=DueDiligenceArea.IP,
                description="Intellectual property portfolio review",
                risk_level="medium"
            ),
            DueDiligenceItem(
                id=f"dd_regulatory_{transaction.transaction_id}",
                area=DueDiligenceArea.REGULATORY,
                description="Regulatory compliance review",
                risk_level="high"
            ),
            DueDiligenceItem(
                id=f"dd_hr_{transaction.transaction_id}",
                area=DueDiligenceArea.HR,
                description="Employee contracts and benefits review",
                risk_level="medium"
            )
        ]
        
        transaction.due_diligence_items.extend(standard_items)
    
    def handle_add_due_diligence(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add due diligence items to a transaction.
        
        Args:
            intent_data: Due diligence addition data
            
        Returns:
            Due diligence addition result
        """
        try:
            transaction_id = intent_data["transaction_id"]
            transaction = self.active_transactions.get(transaction_id)
            
            if not transaction:
                return {"success": False, "error": f"Transaction {transaction_id} not found"}
            
            items_data = intent_data.get("items", [])
            added_items = []
            
            for item_data in items_data:
                item = DueDiligenceItem(
                    id=f"dd_custom_{len(transaction.due_diligence_items)}_{transaction_id}",
                    area=DueDiligenceArea(item_data.get("area", "legal")),
                    description=item_data.get("description", "Custom due diligence item"),
                    risk_level=item_data.get("risk_level", "medium"),
                    assigned_to=item_data.get("assigned_to"),
                    deadline=datetime.fromisoformat(item_data["deadline"]) if "deadline" in item_data else None
                )
                
                transaction.due_diligence_items.append(item)
                added_items.append(item.id)
            
            transaction.updated_at = datetime.now()
            self.transaction_metrics["due_diligence_items_processed"] += len(added_items)
            
            logger.info(f"Added {len(added_items)} due diligence items to {transaction_id}")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "added_items": added_items,
                "total_items": len(transaction.due_diligence_items)
            }
            
        except Exception as e:
            logger.error(f"Failed to add due diligence: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def handle_analyze_risk(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze risks for a transaction.
        
        Args:
            intent_data: Risk analysis data
            
        Returns:
            Risk analysis result
        """
        try:
            transaction_id = intent_data["transaction_id"]
            transaction = self.active_transactions.get(transaction_id)
            
            if not transaction:
                return {"success": False, "error": f"Transaction {transaction_id} not found"}
            
            # Analyze due diligence items for risks
            risks = []
            for item in transaction.due_diligence_items:
                if item.risk_level in ["high", "critical"]:
                    risk = {
                        "due_diligence_id": item.id,
                        "area": item.area.value,
                        "description": item.description,
                        "risk_level": item.risk_level,
                        "findings": item.findings,
                        "mitigation": self._suggest_mitigation(item)
                    }
                    risks.append(risk)
            
            transaction.risks.extend(risks)
            transaction.updated_at = datetime.now()
            self.transaction_metrics["risks_identified"] += len(risks)
            
            logger.info(f"Analyzed risks for {transaction_id}: {len(risks)} risks identified")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "risks_identified": len(risks),
                "risks": risks[:10]  # Return first 10 risks
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze risk: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _suggest_mitigation(self, item: DueDiligenceItem) -> str:
        """Suggest mitigation for a due diligence item."""
        mitigations = {
            DueDiligenceArea.FINANCIAL: "Consider purchase price adjustment or earn-out structure",
            DueDiligenceArea.LEGAL: "Include specific indemnification provisions in agreement",
            DueDiligenceArea.IP: "Conduct IP audit and consider IP representations and warranties",
            DueDiligenceArea.REGULATORY: "Engage regulatory counsel and consider regulatory approval conditions",
            DueDiligenceArea.HR: "Review employee agreements and consider retention bonuses",
            DueDiligenceArea.TAX: "Engage tax counsel for optimal transaction structure",
            DueDiligenceArea.ENVIRONMENTAL: "Conduct Phase I environmental assessment",
            DueDiligenceArea.OPERATIONAL: "Develop integration plan with operational due diligence"
        }
        
        return mitigations.get(item.area, "Conduct further investigation and consider specific representations")
    
    def handle_generate_document(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate M&A document.
        
        Args:
            intent_data: Document generation data
            
        Returns:
            Document generation result
        """
        try:
            transaction_id = intent_data["transaction_id"]
            doc_type = intent_data.get("doc_type", "letter_of_intent")
            
            transaction = self.active_transactions.get(transaction_id)
            if not transaction:
                return {"success": False, "error": f"Transaction {transaction_id} not found"}
            
            # Generate document based on type
            document = self._generate_ma_document(transaction, doc_type)
            
            # Store document
            doc_id = f"{doc_type}_{transaction_id}_{datetime.now().strftime('%Y%m%d')}"
            import hashlib
            content_hash = hashlib.sha256(document.encode()).hexdigest()
            
            legal_doc = LegalDocument(
                document_id=doc_id,
                title=f"{doc_type.replace('_', ' ').title()} - {transaction_id}",
                document_type=doc_type,
                jurisdiction=self.jurisdiction,
                status="draft",
                content_hash=content_hash
            )
            
            self.processed_documents[doc_id] = legal_doc
            transaction.documents.append(doc_id)
            self.transaction_metrics["documents_generated"] += 1
            
            logger.info(f"Generated {doc_type} document for {transaction_id}")
            
            return {
                "success": True,
                "document_id": doc_id,
                "document_type": doc_type,
                "transaction_id": transaction_id,
                "summary": self._summarize_document(document)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate document: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_ma_document(self, transaction: Transaction, doc_type: str) -> str:
        """Generate M&A document content."""
        templates = {
            "letter_of_intent": self._generate_loi,
            "due_diligence_request": self._generate_dd_request,
            "term_sheet": self._generate_term_sheet,
            "risk_assessment": self._generate_risk_assessment
        }
        
        generator = templates.get(doc_type, self._generate_generic_document)
        return generator(transaction)
    
    def _generate_loi(self, transaction: Transaction) -> str:
        """Generate Letter of Intent."""
        parties = ", ".join([p.name for p in transaction.parties])
        
        return f"""LETTER OF INTENT

Date: {datetime.now().strftime('%B %d, %Y')}
Parties: {parties}
Transaction: {transaction.deal_type.value.upper()}

1. PURPOSE
This Letter of Intent outlines the proposed terms for the {transaction.deal_type.value} transaction.

2. KEY TERMS
- Transaction Structure: {transaction.deal_type.value}
- Valuation: To be determined based on due diligence
- Expected Closing: Within 90 days of signing definitive agreement

3. DUE DILIGENCE
The parties agree to a 30-day due diligence period covering:
- Financial records
- Legal contracts
- Intellectual property
- Regulatory compliance
- Employee matters

4. EXCLUSIVITY
The parties agree to a 60-day exclusivity period.

5. CONFIDENTIALITY
All discussions and documents shall remain confidential.

6. GOVERNING LAW
This LOI shall be governed by the laws of {self.jurisdiction.value}.

[Signature Blocks]
"""
    
    def _generate_dd_request(self, transaction: Transaction) -> str:
        """Generate Due Diligence Request List."""
        items_by_area = {}
        for item in transaction.due_diligence_items:
            area = item.area.value
            if area not in items_by_area:
                items_by_area[area] = []
            items_by_area[area].append(item.description)
        
        sections = []
        for area, items in items_by_area.items():
            section = f"{area.upper()} DUE DILIGENCE\n"
            for i, item in enumerate(items, 1):
                section += f"{i}. {item}\n"
            sections.append(section)
        
        return "DUE DILIGENCE REQUEST LIST\n\n" + "\n".join(sections)
    
    def _generate_term_sheet(self, transaction: Transaction) -> str:
        """Generate Term Sheet."""
        return f"""TERM SHEET

Transaction: {transaction.transaction_id}
Type: {transaction.deal_type.value.upper()}
Date: {datetime.now().strftime('%Y-%m-%d')}

1. PURCHASE PRICE
- Base Purchase Price: To be determined
- Payment Structure: Cash and/or stock
- Adjustments: Working capital and net debt

2. CONDITIONS PRECEDENT
- Satisfactory due diligence
- Regulatory approvals
- Board approvals
- No material adverse change

3. REPRESENTATIONS & WARRANTIES
- Standard commercial representations
- Specific representations for key areas
- Survival period: 12-24 months

4. INDEMNIFICATION
- Basket: 0.5% of purchase price
- Cap: 10-20% of purchase price
- Survival: As per representations

5. CLOSING
- Expected Date: TBD
- Location: Virtual or in-person
- Deliverables: As per definitive agreement
"""
    
    def _generate_risk_assessment(self, transaction: Transaction) -> str:
        """Generate Risk Assessment Report."""
        report = f"RISK ASSESSMENT REPORT\n\nTransaction: {transaction.transaction_id}\nDate: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        
        if transaction.risks:
            report += "IDENTIFIED RISKS:\n"
            for i, risk in enumerate(transaction.risks, 1):
                report += f"{i}. {risk['area'].upper()} - {risk['description']}\n"
                report += f"   Risk Level: {risk['risk_level']}\n"
                report += f"   Mitigation: {risk['mitigation']}\n\n"
        else:
            report += "No significant risks identified at this time.\n"
        
        return report
    
    def _generate_generic_document(self, transaction: Transaction) -> str:
        """Generate generic document."""
        return f"""DOCUMENT

Transaction: {transaction.transaction_id}
Type: {transaction.deal_type.value}
Date: {datetime.now().strftime('%Y-%m-%d')}

Content: This document pertains to the {transaction.deal_type.value} transaction.

Status: Draft
"""
    
    def _summarize_document(self, document: str) -> str:
        """Generate a summary of the document."""
        lines = document.split('\n')
        if len(lines) > 10:
            return '\n'.join(lines[:10]) + "\n..."
        return document
    
    def handle_advance_phase(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Advance transaction to next phase.
        
        Args:
            intent_data: Phase advancement data
            
        Returns:
            Phase advancement result
        """
        try:
            transaction_id = intent_data["transaction_id"]
            target_phase = intent_data.get("target_phase")
            
            transaction = self.active_transactions.get(transaction_id)
            if not transaction:
                return {"success": False, "error": f"Transaction {transaction_id} not found"}
            
            current_phase = transaction.phase
            
            # Validate phase transition
            if target_phase:
                try:
                    target_phase_enum = DealPhase(target_phase)
                    transaction.phase = target_phase_enum
                except ValueError:
                    return {"success": False, "error": f"Invalid target phase: {target_phase}"}
            else:
                # Advance to next phase
                phases = list(DealPhase)
                current_index = phases.index(current_phase)
                if current_index < len(phases) - 1:
                    transaction.phase = phases[current_index + 1]
                else:
                    return {"success": False, "error": "Transaction already in final phase"}
            
            transaction.updated_at = datetime.now()
            
            logger.info(f"Advanced {transaction_id} from {current_phase.value} to {transaction.phase.value}")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "previous_phase": current_phase.value,
                "current_phase": transaction.phase.value,
                "next_steps": self._get_phase_next_steps(transaction.phase)
            }
            
        except Exception as e:
            logger.error(f"Failed to advance phase: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_phase_next_steps(self, phase: DealPhase) -> List[str]:
        """Get next steps for a phase."""
        next_steps = {
            DealPhase.PRELIMINARY: [
                "Prepare confidentiality agreement",
                "Initial due diligence request",
                "Draft letter of intent"
            ],
            DealPhase.DUE_DILIGENCE: [
                "Complete due diligence checklist",
                "Analyze findings",
                "Prepare due diligence report"
            ],
            DealPhase.NEGOTIATION: [
                "Draft term sheet",
                "Negotiate key terms",
                "Finalize valuation"
            ],
            DealPhase.DOCUMENTATION: [
                "Draft definitive agreement",
                "Prepare ancillary documents",
                "Coordinate with counsel"
            ],
            DealPhase.CLOSING: [
                "Prepare closing checklist",
                "Coordinate signatures",
                "Arrange funding"
            ],
            DealPhase.INTEGRATION: [
                "Develop integration plan",
                "Communicate with stakeholders",
                "Monitor post-closing items"
            ],
            DealPhase.POST_CLOSING: [
                "File regulatory documents",
                "Process post-closing adjustments",
                "Monitor representations"
            ]
        }
        
        return next_steps.get(phase, ["Continue with current activities"])
    
    def handle_calculate_valuation(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate valuation for a transaction.
        
        Args:
            intent_data: Valuation calculation data
            
        Returns:
            Valuation calculation result
        """
        try:
            transaction_id = intent_data["transaction_id"]
            financial_data = intent_data.get("financial_data", {})
            
            transaction = self.active_transactions.get(transaction_id)
            if not transaction:
                return {"success": False, "error": f"Transaction {transaction_id} not found"}
            
            # Simple valuation calculation (in practice would use DCF, comparables, etc.)
            revenue = financial_data.get("revenue", 0)
            ebitda = financial_data.get("ebitda", 0)
            net_income = financial_data.get("net_income", 0)
            assets = financial_data.get("assets", 0)
            
            # Multiple-based valuation
            revenue_multiple = financial_data.get("revenue_multiple", 2.0)
            ebitda_multiple = financial_data.get("ebitda_multiple", 8.0)
            
            valuation_revenue = revenue * revenue_multiple
            valuation_ebitda = ebitda * ebitda_multiple
            valuation_assets = assets * 1.0  # Asset-based
            
            # Weighted average
            valuation = (valuation_revenue * 0.3 + valuation_ebitda * 0.5 + valuation_assets * 0.2)
            
            transaction.valuation = valuation
            
            # Update metrics
            self.transaction_metrics["total_deal_value"] += valuation
            if self.transaction_metrics["transactions_completed"] > 0:
                self.transaction_metrics["average_deal_size"] = (
                    self.transaction_metrics["total_deal_value"] / 
                    self.transaction_metrics["transactions_completed"]
                )
            
            logger.info(f"Calculated valuation for {transaction_id}: ${valuation:,.2f}")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "valuation": valuation,
                "valuation_components": {
                    "revenue_based": valuation_revenue,
                    "ebitda_based": valuation_ebitda,
                    "asset_based": valuation_assets
                },
                "methodology": "Weighted average of revenue, EBITDA, and asset-based valuations"
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate valuation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def handle_check_regulatory(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check regulatory requirements for a transaction.
        
        Args:
            intent_data: Regulatory check data
            
        Returns:
            Regulatory check result
        """
        try:
            transaction_id = intent_data["transaction_id"]
            jurisdictions = intent_data.get("jurisdictions", [self.jurisdiction.value])
            
            transaction = self.active_transactions.get(transaction_id)
            if not transaction:
                return {"success": False, "error": f"Transaction {transaction_id} not found"}
            
            regulatory_checks = []
            
            for jurisdiction in jurisdictions:
                checks = self._get_regulatory_checks(jurisdiction, transaction)
                regulatory_checks.extend(checks)
            
            # Update metrics
            self.transaction_metrics["regulatory_filings"] += len(regulatory_checks)
            
            logger.info(f"Performed regulatory check for {transaction_id}: {len(regulatory_checks)} requirements")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "regulatory_checks": regulatory_checks,
                "total_requirements": len(regulatory_checks)
            }
            
        except Exception as e:
            logger.error(f"Failed to check regulatory: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_regulatory_checks(self, jurisdiction: str, transaction: Transaction) -> List[Dict[str, Any]]:
        """Get regulatory checks for a jurisdiction."""
        checks = []
        
        # US Federal checks
        if jurisdiction == "us_federal":
            checks.append({
                "jurisdiction": "US Federal",
                "agency": "SEC",
                "filing": "Form 8-K",
                "deadline": "4 business days after signing",
                "description": "Current report for material events"
            })
            
            checks.append({
                "jurisdiction": "US Federal",
                "agency": "FTC/DOJ",
                "filing": "HSR Act Filing",
                "deadline": "30 days pre-closing (if applicable)",
                "description": "Hart-Scott-Rodino pre-merger notification"
            })
        
        # Add more jurisdiction checks as needed
        
        return checks
    
    def handle_create_integration_plan(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create integration plan for a transaction.
        
        Args:
            intent_data: Integration plan data
            
        Returns:
            Integration plan creation result
        """
        try:
            transaction_id = intent_data["transaction_id"]
            
            transaction = self.active_transactions.get(transaction_id)
            if not transaction:
                return {"success": False, "error": f"Transaction {transaction_id} not found"}
            
            # Create integration plan
            integration_plan = {
                "transaction_id": transaction_id,
                "created_at": datetime.now().isoformat(),
                "phases": [
                    {
                        "phase": "Day 1-30",
                        "focus": "Stabilization",
                        "tasks": [
                            "Communicate with employees",
                            "Integrate IT systems",
                            "Align financial reporting"
                        ]
                    },
                    {
                        "phase": "Day 31-90",
                        "focus": "Integration",
                        "tasks": [
                            "Combine operations",
                            "Optimize processes",
                            "Realize synergies"
                        ]
                    },
                    {
                        "phase": "Day 91-180",
                        "focus": "Optimization",
                        "tasks": [
                            "Performance review",
                            "Continuous improvement",
                            "Cultural integration"
                        ]
                    }
                ],
                "key_metrics": [
                    "Employee retention rate",
                    "Customer satisfaction",
                    "Cost synergies realized",
                    "Revenue growth"
                ]
            }
            
            self.integration_plans[transaction_id] = integration_plan
            
            logger.info(f"Created integration plan for {transaction_id}")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "integration_plan": integration_plan
            }
            
        except Exception as e:
            logger.error(f"Failed to create integration plan: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get comprehensive agent status including M&A metrics.
        
        Returns:
            Agent status with M&A specific metrics
        """
        base_status = super().get_agent_status()
        
        ma_status = {
            "agent_type": "ma_transaction_agent",
            "active_transactions": len(self.active_transactions),
            "transactions_by_phase": self._get_transactions_by_phase(),
            "transaction_metrics": self.transaction_metrics,
            "integration_plans": len(self.integration_plans),
            "ma_capabilities": [
                "transaction_creation",
                "due_diligence_management",
                "risk_analysis",
                "document_generation",
                "valuation_calculation",
                "regulatory_compliance",
                "integration_planning"
            ]
        }
        
        base_status.update(ma_status)
        return base_status
    
    def _get_transactions_by_phase(self) -> Dict[str, int]:
        """Get count of transactions by phase."""
        counts = {phase.value: 0 for phase in DealPhase}
        
        for transaction in self.active_transactions.values():
            counts[transaction.phase.value] += 1
        
        return counts


# Test function for Build 6 Part 1
def test_ma_transaction_agent():
    """Test the M&A Transaction Agent."""
    print("🧪 Testing M&A Transaction Agent - Build 6 Part 1")
    
    try:
        # Create agent
        agent = MATransactionAgent(
            agent_id="ma_agent_001",
            jurisdiction=Jurisdiction.US_FEDERAL
        )
        
        print("✅ Agent created successfully")
        
        # Test transaction creation
        create_result = agent.handle_create_transaction({
            "transaction_id": "test_txn_001",
            "deal_type": "acquisition",
            "parties": [
                {
                    "name": "Acquirer Corp",
                    "type": "acquirer",
                    "jurisdiction": "US",
                    "financial_capacity": 100000000
                },
                {
                    "name": "Target Inc",
                    "type": "target",
                    "jurisdiction": "US"
                }
            ]
        })
        
        print(f"✅ Transaction creation: {create_result['success']}")
        print(f"   Transaction ID: {create_result['transaction_id']}")
        print(f"   Parties: {create_result['parties']}")
        
        # Test due diligence addition
        dd_result = agent.handle_add_due_diligence({
            "transaction_id": "test_txn_001",
            "items": [
                {
                    "area": "tax",
                    "description": "Tax structure review",
                    "risk_level": "high"
                }
            ]
        })
        
        print(f"✅ Due diligence addition: {dd_result['success']}")
        print(f"   Added items: {dd_result['added_items']}")
        
        # Test risk analysis
        risk_result = agent.handle_analyze_risk({
            "transaction_id": "test_txn_001"
        })
        
        print(f"✅ Risk analysis: {risk_result['success']}")
        print(f"   Risks identified: {risk_result['risks_identified']}")
        
        # Test document generation
        doc_result = agent.handle_generate_document({
            "transaction_id": "test_txn_001",
            "doc_type": "letter_of_intent"
        })
        
        print(f"✅ Document generation: {doc_result['success']}")
        print(f"   Document ID: {doc_result['document_id']}")
        
        # Test agent status
        status = agent.get_agent_status()
        print(f"✅ Agent status retrieved")
        print(f"   Active transactions: {status['active_transactions']}")
        print(f"   Documents generated: {status['transaction_metrics']['documents_generated']}")
        
        print("\n🎉 BUILD 6 PART 1 COMPLETE - M&A Transaction Agent operational")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run test
    success = test_ma_transaction_agent()
    sys.exit(0 if success else 1)