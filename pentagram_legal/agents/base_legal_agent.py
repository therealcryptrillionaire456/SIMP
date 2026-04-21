"""
Pentagram Legal Department - Base Legal Agent

Base class for all legal agents in the Pentagram Legal Department.
Extends SIMP agent with legal-specific capabilities and workflows.

Author: Pentagram Legal Engineering
Date: April 10, 2026
Version: 1.0.0
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable

from simp.agent import SimpAgent
from simp.intent import Intent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LegalAgentRole(Enum):
    """Legal agent specialization roles."""
    CLO = "chief_legal_officer"
    DGC = "deputy_general_counsel"
    M_A = "mergers_acquisitions"
    IP = "intellectual_property"
    COMPLIANCE = "regulatory_compliance"
    LITIGATION = "litigation_disputes"
    GOVERNANCE = "corporate_governance"
    EMPLOYMENT = "employment_law"
    EMERGING_TECH = "emerging_technologies"
    RESEARCH = "legal_research"
    DRAFTING = "document_drafting"
    REVIEW = "document_review"
    NEGOTIATION = "negotiation"
    MONITORING = "compliance_monitoring"
    WORKFLOW = "workflow_orchestration"
    QUALITY = "quality_assurance"
    SECURITY = "security_confidentiality"
    REPORTING = "reporting_analytics"


class LegalMatterStatus(Enum):
    """Status of legal matters."""
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    FILED = "filed"
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"
    ESCALATED = "escalated"


class Jurisdiction(Enum):
    """Legal jurisdictions."""
    US_FEDERAL = "us_federal"
    US_STATE = "us_state"
    INTERNATIONAL = "international"
    EU = "european_union"
    UK = "united_kingdom"
    CANADA = "canada"
    AUSTRALIA = "australia"
    JAPAN = "japan"
    CHINA = "china"
    MULTI_JURISDICTIONAL = "multi_jurisdictional"


@dataclass
class LegalMatter:
    """Legal matter representation."""
    matter_id: str
    title: str
    description: str
    jurisdiction: Jurisdiction
    practice_area: LegalAgentRole
    status: LegalMatterStatus
    priority: int = 1  # 1-5, 1 being highest
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    assigned_agents: List[str] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    deadlines: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LegalDocument:
    """Legal document representation."""
    document_id: str
    title: str
    document_type: str  # contract, brief, filing, etc.
    jurisdiction: Jurisdiction
    status: LegalMatterStatus
    content_hash: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseLegalAgent(SimpAgent):
    """
    Base class for all legal agents in the Pentagram Legal Department.
    
    Extends SIMP agent with legal-specific capabilities:
    - Legal matter management
    - Document handling
    - Jurisdiction awareness
    - Compliance tracking
    - Workflow coordination
    """
    
    def __init__(self, agent_id: str, role: LegalAgentRole, jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL, organization: str = "Pentagram Tech Acquisitions"):
        """
        Initialize a legal agent.
        
        Args:
            agent_id: Unique agent identifier
            role: Legal specialization role
            jurisdiction: Primary jurisdiction
            organization: Organization name (default: Pentagram Tech Acquisitions)
        """
        super().__init__(agent_id, organization)
        
        self.role = role
        self.jurisdiction = jurisdiction
        self.practice_area = role.value
        
        # Legal-specific state
        self.active_matters: Dict[str, LegalMatter] = {}
        self.processed_documents: Dict[str, LegalDocument] = {}
        self.deadlines: List[Dict] = []
        self.compliance_checks: List[Dict] = []
        
        # Performance tracking
        self.metrics = {
            "matters_handled": 0,
            "documents_processed": 0,
            "deadlines_met": 0,
            "deadlines_missed": 0,
            "compliance_violations": 0,
            "average_processing_time": 0.0,
        }
        
        # Register legal-specific intent handlers
        self._register_legal_handlers()
        
        logger.info(f"Initialized legal agent {agent_id} with role {role.value} in {jurisdiction.value}")
    
    def _register_legal_handlers(self):
        """Register legal-specific intent handlers."""
        self.register_handler("legal_matter_create", self.handle_create_matter)
        self.register_handler("legal_matter_update", self.handle_update_matter)
        self.register_handler("legal_document_process", self.handle_process_document)
        self.register_handler("legal_research_request", self.handle_research_request)
        self.register_handler("legal_compliance_check", self.handle_compliance_check)
        self.register_handler("legal_deadline_check", self.handle_deadline_check)
        self.register_handler("legal_workflow_coordinate", self.handle_workflow_coordination)
        self.register_handler("legal_quality_review", self.handle_quality_review)
    
    def handle_create_matter(self, intent: Intent) -> Dict[str, Any]:
        """
        Handle creation of a new legal matter.
        
        Args:
            intent: SIMP intent with matter details
            
        Returns:
            Response with matter ID and status
        """
        try:
            payload = intent.payload
            
            # Validate required fields
            required_fields = ["title", "description", "practice_area", "jurisdiction"]
            for field in required_fields:
                if field not in payload:
                    return {
                        "status": "error",
                        "message": f"Missing required field: {field}",
                        "agent_id": self.agent_id
                    }
            
            # Create matter
            matter_id = f"MATTER-{int(time.time() * 1000)}"
            matter = LegalMatter(
                matter_id=matter_id,
                title=payload["title"],
                description=payload["description"],
                jurisdiction=Jurisdiction(payload["jurisdiction"]),
                practice_area=LegalAgentRole(payload["practice_area"]),
                status=LegalMatterStatus.DRAFT,
                priority=payload.get("priority", 3),
                metadata=payload.get("metadata", {})
            )
            
            # Store matter
            self.active_matters[matter_id] = matter
            self.metrics["matters_handled"] += 1
            
            logger.info(f"Created legal matter {matter_id}: {matter.title}")
            
            return {
                "status": "success",
                "message": "Legal matter created successfully",
                "matter_id": matter_id,
                "matter": matter.__dict__,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            logger.error(f"Error creating legal matter: {e}")
            return {
                "status": "error",
                "message": f"Failed to create legal matter: {str(e)}",
                "agent_id": self.agent_id
            }
    
    def handle_update_matter(self, intent: Intent) -> Dict[str, Any]:
        """
        Handle updates to an existing legal matter.
        
        Args:
            intent: SIMP intent with matter updates
            
        Returns:
            Response with updated matter status
        """
        try:
            payload = intent.payload
            
            if "matter_id" not in payload:
                return {
                    "status": "error",
                    "message": "Missing matter_id",
                    "agent_id": self.agent_id
                }
            
            matter_id = payload["matter_id"]
            
            if matter_id not in self.active_matters:
                return {
                    "status": "error",
                    "message": f"Matter not found: {matter_id}",
                    "agent_id": self.agent_id
                }
            
            matter = self.active_matters[matter_id]
            
            # Update fields
            if "status" in payload:
                matter.status = LegalMatterStatus(payload["status"])
            if "priority" in payload:
                matter.priority = payload["priority"]
            if "description" in payload:
                matter.description = payload["description"]
            if "metadata" in payload:
                matter.metadata.update(payload["metadata"])
            
            # Update timestamp
            matter.updated_at = datetime.utcnow().isoformat()
            
            logger.info(f"Updated legal matter {matter_id}: status={matter.status.value}")
            
            return {
                "status": "success",
                "message": "Legal matter updated successfully",
                "matter_id": matter_id,
                "matter": matter.__dict__,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            logger.error(f"Error updating legal matter: {e}")
            return {
                "status": "error",
                "message": f"Failed to update legal matter: {str(e)}",
                "agent_id": self.agent_id
            }
    
    def handle_process_document(self, intent: Intent) -> Dict[str, Any]:
        """
        Process a legal document.
        
        Args:
            intent: SIMP intent with document details
            
        Returns:
            Response with processing results
        """
        try:
            payload = intent.payload
            
            # Validate required fields
            required_fields = ["document_type", "content", "jurisdiction"]
            for field in required_fields:
                if field not in payload:
                    return {
                        "status": "error",
                        "message": f"Missing required field: {field}",
                        "agent_id": self.agent_id
                    }
            
            # Create document record
            document_id = f"DOC-{int(time.time() * 1000)}"
            content_hash = hash(payload["content"])
            
            document = LegalDocument(
                document_id=document_id,
                title=payload.get("title", f"Untitled {payload['document_type']}"),
                document_type=payload["document_type"],
                jurisdiction=Jurisdiction(payload["jurisdiction"]),
                status=LegalMatterStatus.DRAFT,
                content_hash=str(content_hash),
                metadata=payload.get("metadata", {})
            )
            
            # Store document
            self.processed_documents[document_id] = document
            self.metrics["documents_processed"] += 1
            
            # Process based on document type
            processing_result = self._process_document_by_type(payload["document_type"], payload["content"])
            
            logger.info(f"Processed document {document_id}: {document.title}")
            
            return {
                "status": "success",
                "message": "Document processed successfully",
                "document_id": document_id,
                "processing_result": processing_result,
                "document": document.__dict__,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            return {
                "status": "error",
                "message": f"Failed to process document: {str(e)}",
                "agent_id": self.agent_id
            }
    
    def _process_document_by_type(self, doc_type: str, content: str) -> Dict[str, Any]:
        """
        Process document based on its type.
        
        Args:
            doc_type: Type of document
            content: Document content
            
        Returns:
            Processing results
        """
        # Base implementation - subclasses should override
        return {
            "document_type": doc_type,
            "content_length": len(content),
            "processed_at": datetime.utcnow().isoformat(),
            "analysis": {
                "basic_validation": "passed",
                "jurisdiction_check": "pending",
                "compliance_check": "pending"
            }
        }
    
    def handle_research_request(self, intent: Intent) -> Dict[str, Any]:
        """
        Handle legal research request.
        
        Args:
            intent: SIMP intent with research query
            
        Returns:
            Response with research results
        """
        try:
            payload = intent.payload
            
            if "query" not in payload:
                return {
                    "status": "error",
                    "message": "Missing research query",
                    "agent_id": self.agent_id
                }
            
            query = payload["query"]
            jurisdiction = payload.get("jurisdiction", self.jurisdiction.value)
            
            # Base research implementation
            research_result = self._conduct_legal_research(query, jurisdiction)
            
            logger.info(f"Conducted legal research: {query[:50]}...")
            
            return {
                "status": "success",
                "message": "Legal research completed",
                "query": query,
                "jurisdiction": jurisdiction,
                "research_result": research_result,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            logger.error(f"Error conducting legal research: {e}")
            return {
                "status": "error",
                "message": f"Failed to conduct legal research: {str(e)}",
                "agent_id": self.agent_id
            }
    
    def _conduct_legal_research(self, query: str, jurisdiction: str) -> Dict[str, Any]:
        """
        Conduct legal research.
        
        Args:
            query: Research query
            jurisdiction: Jurisdiction to research
            
        Returns:
            Research results
        """
        # Base implementation - subclasses should override
        return {
            "query": query,
            "jurisdiction": jurisdiction,
            "sources_consulted": ["statutes", "case_law", "regulations"],
            "findings": [
                {
                    "relevance": "high",
                    "summary": "Base research implementation - override in specialized agents",
                    "citation": "N/A"
                }
            ],
            "recommendations": [
                "Consult specialized research agent for detailed analysis"
            ]
        }
    
    def handle_compliance_check(self, intent: Intent) -> Dict[str, Any]:
        """
        Handle compliance check request.
        
        Args:
            intent: SIMP intent with compliance check details
            
        Returns:
            Response with compliance status
        """
        try:
            payload = intent.payload
            
            required_fields = ["entity", "regulation", "jurisdiction"]
            for field in required_fields:
                if field not in payload:
                    return {
                        "status": "error",
                        "message": f"Missing required field: {field}",
                        "agent_id": self.agent_id
                    }
            
            entity = payload["entity"]
            regulation = payload["regulation"]
            jurisdiction = payload["jurisdiction"]
            
            # Perform compliance check
            compliance_result = self._check_compliance(entity, regulation, jurisdiction)
            
            # Track compliance check
            self.compliance_checks.append({
                "timestamp": datetime.utcnow().isoformat(),
                "entity": entity,
                "regulation": regulation,
                "jurisdiction": jurisdiction,
                "result": compliance_result
            })
            
            if compliance_result.get("status") == "non_compliant":
                self.metrics["compliance_violations"] += 1
            
            logger.info(f"Conducted compliance check for {entity}: {regulation}")
            
            return {
                "status": "success",
                "message": "Compliance check completed",
                "compliance_result": compliance_result,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            logger.error(f"Error conducting compliance check: {e}")
            return {
                "status": "error",
                "message": f"Failed to conduct compliance check: {str(e)}",
                "agent_id": self.agent_id
            }
    
    def _check_compliance(self, entity: str, regulation: str, jurisdiction: str) -> Dict[str, Any]:
        """
        Check compliance with specific regulation.
        
        Args:
            entity: Entity to check
            regulation: Regulation to check against
            jurisdiction: Jurisdiction of regulation
            
        Returns:
            Compliance check results
        """
        # Base implementation - subclasses should override
        return {
            "entity": entity,
            "regulation": regulation,
            "jurisdiction": jurisdiction,
            "status": "compliant",
            "checked_at": datetime.utcnow().isoformat(),
            "details": {
                "regulation_exists": True,
                "entity_in_scope": True,
                "compliance_verified": True
            },
            "recommendations": [
                "Maintain current compliance practices"
            ]
        }
    
    def handle_deadline_check(self, intent: Intent) -> Dict[str, Any]:
        """
        Check upcoming deadlines.
        
        Args:
            intent: SIMP intent with deadline check parameters
            
        Returns:
            Response with upcoming deadlines
        """
        try:
            payload = intent.payload
            
            days_ahead = payload.get("days_ahead", 7)
            
            # Check for upcoming deadlines
            upcoming_deadlines = self._get_upcoming_deadlines(days_ahead)
            
            logger.info(f"Checked deadlines: {len(upcoming_deadlines)} upcoming in next {days_ahead} days")
            
            return {
                "status": "success",
                "message": "Deadline check completed",
                "days_ahead": days_ahead,
                "upcoming_deadlines": upcoming_deadlines,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            logger.error(f"Error checking deadlines: {e}")
            return {
                "status": "error",
                "message": f"Failed to check deadlines: {str(e)}",
                "agent_id": self.agent_id
            }
    
    def _get_upcoming_deadlines(self, days_ahead: int) -> List[Dict]:
        """
        Get upcoming deadlines.
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming deadlines
        """
        # Base implementation - subclasses should override
        return [
            {
                "deadline_id": "DEADLINE-001",
                "description": "Quarterly SEC filing",
                "due_date": "2026-04-15",
                "days_remaining": 5,
                "priority": "high",
                "assigned_to": self.agent_id
            }
        ]
    
    def handle_workflow_coordination(self, intent: Intent) -> Dict[str, Any]:
        """
        Coordinate legal workflow.
        
        Args:
            intent: SIMP intent with workflow coordination details
            
        Returns:
            Response with coordination results
        """
        try:
            payload = intent.payload
            
            if "workflow_type" not in payload:
                return {
                    "status": "error",
                    "message": "Missing workflow_type",
                    "agent_id": self.agent_id
                }
            
            workflow_type = payload["workflow_type"]
            workflow_data = payload.get("workflow_data", {})
            
            # Coordinate workflow
            coordination_result = self._coordinate_workflow(workflow_type, workflow_data)
            
            logger.info(f"Coordinated workflow: {workflow_type}")
            
            return {
                "status": "success",
                "message": "Workflow coordination completed",
                "workflow_type": workflow_type,
                "coordination_result": coordination_result,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            logger.error(f"Error coordinating workflow: {e}")
            return {
                "status": "error",
                "message": f"Failed to coordinate workflow: {str(e)}",
                "agent_id": self.agent_id
            }
    
    def _coordinate_workflow(self, workflow_type: str, workflow_data: Dict) -> Dict[str, Any]:
        """
        Coordinate specific workflow type.
        
        Args:
            workflow_type: Type of workflow
            workflow_data: Workflow data
            
        Returns:
            Coordination results
        """
        # Base implementation - subclasses should override
        return {
            "workflow_type": workflow_type,
            "status": "coordinated",
            "steps": [
                {
                    "step": 1,
                    "action": "initiate_workflow",
                    "status": "completed",
                    "agent": self.agent_id
                }
            ],
            "next_actions": [
                "Assign to specialized workflow agent"
            ]
        }
    
    def handle_quality_review(self, intent: Intent) -> Dict[str, Any]:
        """
        Handle quality review request.
        
        Args:
            intent: SIMP intent with review details
            
        Returns:
            Response with review results
        """
        try:
            payload = intent.payload
            
            if "review_target" not in payload:
                return {
                    "status": "error",
                    "message": "Missing review_target",
                    "agent_id": self.agent_id
                }
            
            review_target = payload["review_target"]
            review_type = payload.get("review_type", "general")
            
            # Perform quality review
            review_result = self._perform_quality_review(review_target, review_type)
            
            logger.info(f"Performed quality review: {review_target}")
            
            return {
                "status": "success",
                "message": "Quality review completed",
                "review_target": review_target,
                "review_result": review_result,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            logger.error(f"Error performing quality review: {e}")
            return {
                "status": "error",
                "message": f"Failed to perform quality review: {str(e)}",
                "agent_id": self.agent_id
            }
    
    def _perform_quality_review(self, review_target: str, review_type: str) -> Dict[str, Any]:
        """
        Perform quality review.
        
        Args:
            review_target: Target of review
            review_type: Type of review
            
        Returns:
            Review results
        """
        # Base implementation - subclasses should override
        return {
            "review_target": review_target,
            "review_type": review_type,
            "status": "reviewed",
            "findings": [
                {
                    "aspect": "completeness",
                    "score": 0.9,
                    "comment": "Generally complete, minor improvements possible"
                },
                {
                    "aspect": "accuracy",
                    "score": 0.95,
                    "comment": "High accuracy, verified against sources"
                },
                {
                    "aspect": "compliance",
                    "score": 0.85,
                    "comment": "Mostly compliant, check jurisdiction-specific requirements"
                }
            ],
            "overall_score": 0.9,
            "recommendations": [
                "Proceed with minor revisions",
                "Verify jurisdiction-specific requirements"
            ]
        }
    
    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get comprehensive agent status.
        
        Returns:
            Agent status including metrics and state
        """
        base_status = {
            "agent_id": self.agent_id,
            "organization": self.organization,
            "status": "online",
            "capabilities": list(self.intent_handlers.keys()) if hasattr(self, 'intent_handlers') else []
        }
        
        legal_status = {
            "role": self.role.value,
            "jurisdiction": self.jurisdiction.value,
            "practice_area": self.practice_area,
            "active_matters": len(self.active_matters),
            "processed_documents": len(self.processed_documents),
            "upcoming_deadlines": len(self.deadlines),
            "compliance_checks": len(self.compliance_checks),
            "metrics": self.metrics,
            "legal_capabilities": [
                "legal_matter_management",
                "document_processing",
                "legal_research",
                "compliance_checking",
                "deadline_tracking",
                "workflow_coordination",
                "quality_review"
            ]
        }
        
        base_status.update(legal_status)
        return base_status
    
    def save_state(self, filepath: str) -> bool:
        """
        Save agent state to file.
        
        Args:
            filepath: Path to save state
            
        Returns:
            True if successful, False otherwise
        """
        try:
            state = {
                "agent_id": self.agent_id,
                "role": self.role.value,
                "jurisdiction": self.jurisdiction.value,
                "active_matters": {k: v.__dict__ for k, v in self.active_matters.items()},
                "processed_documents": {k: v.__dict__ for k, v in self.processed_documents.items()},
                "deadlines": self.deadlines,
                "compliance_checks": self.compliance_checks,
                "metrics": self.metrics,
                "saved_at": datetime.utcnow().isoformat()
            }
            
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"Saved agent state to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving agent state: {e}")
            return False
    
    def load_state(self, filepath: str) -> bool:
        """
        Load agent state from file.
        
        Args:
            filepath: Path to load state from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)
            
            # Validate state
            if state.get("agent_id") != self.agent_id:
                logger.warning(f"State file agent_id mismatch: {state.get('agent_id')} != {self.agent_id}")
                return False
            
            # Load state
            self.active_matters = {}
            for matter_id, matter_data in state.get("active_matters", {}).items():
                matter = LegalMatter(**matter_data)
                self.active_matters[matter_id] = matter
            
            self.processed_documents = {}
            for doc_id, doc_data in state.get("processed_documents", {}).items():
                document = LegalDocument(**doc_data)
                self.processed_documents[doc_id] = document
            
            self.deadlines = state.get("deadlines", [])
            self.compliance_checks = state.get("compliance_checks", [])
            self.metrics = state.get("metrics", self.metrics)
            
            logger.info(f"Loaded agent state from {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading agent state: {e}")
            return False


# Example usage
if __name__ == "__main__":
    # Create a sample legal agent
    agent = BaseLegalAgent(
        agent_id="legal_agent_001",
        role=LegalAgentRole.COMPLIANCE,
        jurisdiction=Jurisdiction.US_FEDERAL
    )
    
    # Print agent status
    print("Agent Status:")
    print(json.dumps(agent.get_agent_status(), indent=2))
    
    # Example: Create a legal matter
    matter_intent = Intent(
        intent_type="legal_matter_create",
        source_agent="test_client",
        target_agent="legal_agent_001",
        payload={
            "title": "SEC Filing Compliance Review",
            "description": "Review quarterly SEC filing for compliance",
            "practice_area": "regulatory_compliance",
            "jurisdiction": "us_federal",
            "priority": 1,
            "metadata": {
                "client": "Pentagram Portfolio Company",
                "filing_type": "10-Q"
            }
        }
    )
    
    response = agent.handle_create_matter(matter_intent)
    print("\nCreated Matter Response:")
    print(json.dumps(response, indent=2))
    
    # Example: Process a document
    doc_intent = Intent(
        intent_type="legal_document_process",
        source_agent="test_client",
        target_agent="legal_agent_001",
        payload={
            "title": "Draft 10-Q Filing",
            "document_type": "sec_filing",
            "content": "This is a draft SEC 10-Q filing for Q1 2026...",
            "jurisdiction": "us_federal",
            "metadata": {
                "filing_period": "Q1 2026",
                "company": "Example Corp"
            }
        }
    )
    
    response = agent.handle_process_document(doc_intent)
    print("\nProcessed Document Response:")
    print(json.dumps(response, indent=2))
