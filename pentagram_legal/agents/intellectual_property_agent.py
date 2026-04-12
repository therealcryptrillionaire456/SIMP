"""
Intellectual Property Agent - Build 7 Part 1
Specialized agent for patent, trademark, copyright, and trade secret management.
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


class IPType(Enum):
    """Types of intellectual property."""
    PATENT = "patent"
    TRADEMARK = "trademark"
    COPYRIGHT = "copyright"
    TRADE_SECRET = "trade_secret"
    INDUSTRIAL_DESIGN = "industrial_design"
    PLANT_VARIETY = "plant_variety"
    GEOGRAPHICAL_INDICATION = "geographical_indication"


class PatentType(Enum):
    """Types of patents."""
    UTILITY = "utility"
    DESIGN = "design"
    PLANT = "plant"
    PROVISIONAL = "provisional"
    PCT = "pct"  # Patent Cooperation Treaty
    DIVISIONAL = "divisional"
    CONTINUATION = "continuation"
    CONTINUATION_IN_PART = "continuation_in_part"


class TrademarkClass(Enum):
    """International trademark classes (simplified)."""
    CLASS_1 = "chemicals"
    CLASS_9 = "computers_software"
    CLASS_25 = "clothing"
    CLASS_35 = "advertising_business"
    CLASS_41 = "education_entertainment"
    CLASS_42 = "scientific_services"
    CLASS_45 = "legal_security"


class CopyrightCategory(Enum):
    """Categories of copyrightable works."""
    LITERARY = "literary"
    MUSICAL = "musical"
    DRAMATIC = "dramatic"
    CHOREOGRAPHIC = "choreographic"
    PICTORIAL = "pictorial"
    GRAPHIC = "graphic"
    SCULPTURAL = "sculptural"
    AUDIOVISUAL = "audiovisual"
    SOUND_RECORDING = "sound_recording"
    ARCHITECTURAL = "architectural"
    SOFTWARE = "software"
    DATABASE = "database"


class IPStatus(Enum):
    """Status of intellectual property."""
    DRAFT = "draft"
    FILED = "filed"
    PENDING = "pending"
    PUBLISHED = "published"
    EXAMINATION = "examination"
    ALLOWED = "allowed"
    REGISTERED = "registered"
    GRANTED = "granted"
    ACTIVE = "active"
    EXPIRED = "expired"
    ABANDONED = "abandoned"
    OPPOSED = "opposed"
    CANCELLED = "cancelled"
    REVOKED = "revoked"
    LITIGATION = "litigation"


class IPJurisdiction(Enum):
    """Jurisdictions for IP protection."""
    USPTO = "uspto"  # United States Patent and Trademark Office
    EPO = "epo"  # European Patent Office
    WIPO = "wipo"  # World Intellectual Property Organization
    JPO = "jpo"  # Japan Patent Office
    CNIPA = "cnipa"  # China National Intellectual Property Administration
    KIPO = "kipo"  # Korean Intellectual Property Office
    UKIPO = "ukipo"  # United Kingdom Intellectual Property Office
    CIPO = "cipo"  # Canadian Intellectual Property Office
    IP_AUSTRALIA = "ip_australia"
    MULTI_NATIONAL = "multi_national"


@dataclass
class Inventor:
    """Inventor of a patentable invention."""
    name: str
    address: str
    nationality: str
    contribution: str
    assignment_executed: bool = False
    contact_info: Dict[str, str] = field(default_factory=dict)


@dataclass
class PatentApplication:
    """Patent application representation."""
    application_id: str
    title: str
    patent_type: PatentType
    jurisdiction: IPJurisdiction
    filing_date: datetime
    inventors: List[Inventor]
    abstract: str
    claims: List[str]
    description: str
    drawings: List[str] = field(default_factory=list)
    priority_date: Optional[datetime] = None
    priority_application: Optional[str] = None
    status: IPStatus = IPStatus.DRAFT
    examiner: Optional[str] = None
    office_actions: List[Dict[str, Any]] = field(default_factory=list)
    fees_paid: Dict[str, float] = field(default_factory=dict)
    deadlines: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TrademarkApplication:
    """Trademark application representation."""
    application_id: str
    mark: str
    trademark_class: TrademarkClass
    goods_services: str
    jurisdiction: IPJurisdiction
    filing_date: datetime
    applicant_name: str
    applicant_address: str
    mark_type: str = "standard"  # standard, collective, certification
    mark_format: str = "word"  # word, design, composite, sound, color
    status: IPStatus = IPStatus.DRAFT
    examination_report: Optional[str] = None
    opposition_notices: List[Dict[str, Any]] = field(default_factory=list)
    registration_number: Optional[str] = None
    registration_date: Optional[datetime] = None
    renewal_dates: List[datetime] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class CopyrightWork:
    """Copyrightable work representation."""
    work_id: str
    title: str
    category: CopyrightCategory
    authors: List[str]
    creation_date: datetime
    publication_date: Optional[datetime] = None
    registration_number: Optional[str] = None
    registration_date: Optional[datetime] = None
    deposit_copy: Optional[str] = None
    derivative_works: List[str] = field(default_factory=list)
    licenses: List[Dict[str, Any]] = field(default_factory=list)
    status: IPStatus = IPStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TradeSecret:
    """Trade secret representation."""
    secret_id: str
    name: str
    description: str
    category: str  # formula, process, method, technique, compilation
    confidentiality_level: str = "high"  # low, medium, high, critical
    protection_measures: List[str] = field(default_factory=list)
    access_controls: List[str] = field(default_factory=list)
    authorized_persons: List[str] = field(default_factory=list)
    last_audit: Optional[datetime] = None
    status: str = "active"  # active, compromised, obsolete
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class IPPortfolio:
    """Intellectual property portfolio."""
    portfolio_id: str
    owner: str
    patents: List[PatentApplication] = field(default_factory=list)
    trademarks: List[TrademarkApplication] = field(default_factory=list)
    copyrights: List[CopyrightWork] = field(default_factory=list)
    trade_secrets: List[TradeSecret] = field(default_factory=list)
    valuation: Optional[float] = None
    last_valuation_date: Optional[datetime] = None
    licensing_revenue: float = 0.0
    maintenance_costs: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class IPLicense:
    """Intellectual property license agreement."""
    license_id: str
    licensor: str
    licensee: str
    ip_type: IPType
    ip_references: List[str]  # IDs of patents, trademarks, etc.
    territory: str
    term_years: int
    royalty_rate: float
    upfront_payment: float = 0.0
    minimum_royalties: float = 0.0
    exclusivity: str = "non-exclusive"  # exclusive, non-exclusive, sole
    field_of_use: Optional[str] = None
    sublicense_allowed: bool = False
    audit_rights: bool = True
    termination_clauses: List[str] = field(default_factory=list)
    effective_date: datetime = field(default_factory=datetime.now)
    expiration_date: Optional[datetime] = None
    status: str = "draft"  # draft, active, expired, terminated
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class IntellectualPropertyAgent(BaseLegalAgent):
    """
    Specialized agent for intellectual property management.
    Handles patents, trademarks, copyrights, trade secrets, and IP portfolio management.
    """
    
    def __init__(self, agent_id: str, jurisdiction: Jurisdiction = Jurisdiction.US_FEDERAL):
        """
        Initialize Intellectual Property Agent.
        
        Args:
            agent_id: Unique agent identifier
            jurisdiction: Primary jurisdiction
        """
        super().__init__(
            agent_id=agent_id,
            role=LegalAgentRole.INTELLECTUAL_PROPERTY,
            jurisdiction=jurisdiction,
            organization="Pentagram IP Management"
        )
        
        # IP specific attributes
        self.patent_applications: Dict[str, PatentApplication] = {}
        self.trademark_applications: Dict[str, TrademarkApplication] = {}
        self.copyright_works: Dict[str, CopyrightWork] = {}
        self.trade_secrets: Dict[str, TradeSecret] = {}
        self.ip_portfolios: Dict[str, IPPortfolio] = {}
        self.ip_licenses: Dict[str, IPLicense] = {}
        
        # Templates and configurations
        self.patent_templates: Dict[str, Dict[str, Any]] = {}
        self.trademark_templates: Dict[str, Dict[str, Any]] = {}
        self.license_templates: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self.ip_metrics = {
            "patents_filed": 0,
            "trademarks_registered": 0,
            "copyrights_registered": 0,
            "trade_secrets_protected": 0,
            "ip_portfolios_managed": 0,
            "licenses_negotiated": 0,
            "office_actions_responded": 0,
            "oppositions_handled": 0,
            "total_ip_value": 0.0,
            "licensing_revenue_generated": 0.0
        }
        
        # Register IP specific intent handlers
        self._register_ip_handlers()
        
        logger.info(f"Initialized Intellectual Property Agent {agent_id}")
    
    def _register_ip_handlers(self):
        """Register IP specific intent handlers."""
        self.register_handler("create_patent_application", self.handle_create_patent_application)
        self.register_handler("create_trademark_application", self.handle_create_trademark_application)
        self.register_handler("register_copyright", self.handle_register_copyright)
        self.register_handler("protect_trade_secret", self.handle_protect_trade_secret)
        self.register_handler("manage_ip_portfolio", self.handle_manage_ip_portfolio)
        self.register_handler("create_ip_license", self.handle_create_ip_license)
        self.register_handler("check_ip_status", self.handle_check_ip_status)
        self.register_handler("respond_to_office_action", self.handle_respond_to_office_action)
        
        logger.info("Registered IP intent handlers")    def handle_create_patent_application(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle creation of a new patent application.
        
        Args:
            intent_data: Patent application data
            
        Returns:
            Patent application creation result
        """
        try:
            application_id = intent_data.get("application_id", f"pat_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            title = intent_data.get("title", "")
            patent_type_str = intent_data.get("patent_type", "utility")
            jurisdiction_str = intent_data.get("jurisdiction", "uspto")
            
            # Create inventors list
            inventors = []
            for inv_data in intent_data.get("inventors", []):
                inventor = Inventor(
                    name=inv_data.get("name"),
                    address=inv_data.get("address"),
                    nationality=inv_data.get("nationality", "US"),
                    contribution=inv_data.get("contribution", ""),
                    assignment_executed=inv_data.get("assignment_executed", False),
                    contact_info=inv_data.get("contact_info", {})
                )
                inventors.append(inventor)
            
            # Create patent application
            patent_app = PatentApplication(
                application_id=application_id,
                title=title,
                patent_type=PatentType(patent_type_str),
                jurisdiction=IPJurisdiction(jurisdiction_str),
                filing_date=datetime.now(),
                inventors=inventors,
                abstract=intent_data.get("abstract", ""),
                claims=intent_data.get("claims", []),
                description=intent_data.get("description", ""),
                drawings=intent_data.get("drawings", []),
                priority_date=intent_data.get("priority_date"),
                priority_application=intent_data.get("priority_application"),
                status=IPStatus.DRAFT
            )
            
            # Store the application
            self.patent_applications[application_id] = patent_app
            
            # Update metrics
            self.ip_metrics["patents_filed"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="create_patent_application",
                details={
                    "application_id": application_id,
                    "title": title,
                    "patent_type": patent_type_str,
                    "jurisdiction": jurisdiction_str,
                    "inventor_count": len(inventors)
                }
            )
            
            logger.info(f"Created patent application {application_id}: {title}")
            
            return {
                "success": True,
                "application_id": application_id,
                "message": f"Patent application {application_id} created successfully",
                "next_steps": [
                    "Complete specification drafting",
                    "Prepare drawings",
                    "Execute inventor assignments",
                    "Calculate filing fees"
                ],
                "deadlines": {
                    "filing_deadline": (datetime.now() + timedelta(days=365)).isoformat() if patent_app.priority_date else None,
                    "assignment_filing": (datetime.now() + timedelta(days=90)).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating patent application: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create patent application"
            }
    
    def handle_create_trademark_application(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle creation of a new trademark application.
        
        Args:
            intent_data: Trademark application data
            
        Returns:
            Trademark application creation result
        """
        try:
            application_id = intent_data.get("application_id", f"tm_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            mark = intent_data.get("mark", "")
            trademark_class_str = intent_data.get("trademark_class", "CLASS_35")
            goods_services = intent_data.get("goods_services", "")
            jurisdiction_str = intent_data.get("jurisdiction", "uspto")
            
            # Create trademark application
            tm_app = TrademarkApplication(
                application_id=application_id,
                mark=mark,
                trademark_class=TrademarkClass(trademark_class_str),
                goods_services=goods_services,
                jurisdiction=IPJurisdiction(jurisdiction_str),
                filing_date=datetime.now(),
                applicant_name=intent_data.get("applicant_name", ""),
                applicant_address=intent_data.get("applicant_address", ""),
                mark_type=intent_data.get("mark_type", "standard"),
                mark_format=intent_data.get("mark_format", "word"),
                status=IPStatus.DRAFT
            )
            
            # Store the application
            self.trademark_applications[application_id] = tm_app
            
            # Update metrics
            self.ip_metrics["trademarks_registered"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="create_trademark_application",
                details={
                    "application_id": application_id,
                    "mark": mark,
                    "class": trademark_class_str,
                    "jurisdiction": jurisdiction_str,
                    "applicant": tm_app.applicant_name
                }
            )
            
            logger.info(f"Created trademark application {application_id}: {mark}")
            
            return {
                "success": True,
                "application_id": application_id,
                "message": f"Trademark application {application_id} created successfully",
                "next_steps": [
                    "Conduct trademark search",
                    "Prepare specimen of use",
                    "Calculate filing fees",
                    "File with trademark office"
                ],
                "search_recommendations": self._suggest_trademark_searches(mark, trademark_class_str)
            }
            
        except Exception as e:
            logger.error(f"Error creating trademark application: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create trademark application"
            }
    
    def handle_register_copyright(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle registration of a copyright.
        
        Args:
            intent_data: Copyright registration data
            
        Returns:
            Copyright registration result
        """
        try:
            work_id = intent_data.get("work_id", f"copy_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            title = intent_data.get("title", "")
            category_str = intent_data.get("category", "LITERARY")
            authors = intent_data.get("authors", [])
            creation_date = intent_data.get("creation_date", datetime.now())
            
            # Create copyright work
            copyright_work = CopyrightWork(
                work_id=work_id,
                title=title,
                category=CopyrightCategory(category_str),
                authors=authors,
                creation_date=creation_date,
                publication_date=intent_data.get("publication_date"),
                status=IPStatus.ACTIVE
            )
            
            # Store the work
            self.copyright_works[work_id] = copyright_work
            
            # Update metrics
            self.ip_metrics["copyrights_registered"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="register_copyright",
                details={
                    "work_id": work_id,
                    "title": title,
                    "category": category_str,
                    "author_count": len(authors),
                    "creation_date": creation_date.isoformat()
                }
            )
            
            logger.info(f"Registered copyright work {work_id}: {title}")
            
            return {
                "success": True,
                "work_id": work_id,
                "message": f"Copyright work {work_id} registered successfully",
                "next_steps": [
                    "Prepare deposit copy",
                    "Complete registration form",
                    "Pay registration fee",
                    "File with copyright office"
                ],
                "automatic_protection": "Copyright protection exists from creation; registration provides additional benefits",
                "registration_deadline": (datetime.now() + timedelta(days=90)).isoformat() if copyright_work.publication_date else None
            }
            
        except Exception as e:
            logger.error(f"Error registering copyright: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to register copyright"
            }
    
    def handle_protect_trade_secret(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle protection of a trade secret.
        
        Args:
            intent_data: Trade secret protection data
            
        Returns:
            Trade secret protection result
        """
        try:
            secret_id = intent_data.get("secret_id", f"ts_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            name = intent_data.get("name", "")
            description = intent_data.get("description", "")
            category = intent_data.get("category", "process")
            
            # Create trade secret
            trade_secret = TradeSecret(
                secret_id=secret_id,
                name=name,
                description=description,
                category=category,
                confidentiality_level=intent_data.get("confidentiality_level", "high"),
                protection_measures=intent_data.get("protection_measures", []),
                access_controls=intent_data.get("access_controls", []),
                authorized_persons=intent_data.get("authorized_persons", []),
                status="active"
            )
            
            # Store the trade secret
            self.trade_secrets[secret_id] = trade_secret
            
            # Update metrics
            self.ip_metrics["trade_secrets_protected"] += 1
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="protect_trade_secret",
                details={
                    "secret_id": secret_id,
                    "name": name,
                    "category": category,
                    "confidentiality_level": trade_secret.confidentiality_level
                }
            )
            
            logger.info(f"Protected trade secret {secret_id}: {name}")
            
            return {
                "success": True,
                "secret_id": secret_id,
                "message": f"Trade secret {secret_id} protected successfully",
                "next_steps": [
                    "Implement access controls",
                    "Train authorized personnel",
                    "Document protection measures",
                    "Schedule regular audits"
                ],
                "protection_requirements": [
                    "Maintain secrecy",
                    "Limit access to need-to-know basis",
                    "Use confidentiality agreements",
                    "Implement physical and digital security"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error protecting trade secret: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to protect trade secret"
            }
    
    def handle_manage_ip_portfolio(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle management of an IP portfolio.
        
        Args:
            intent_data: IP portfolio management data
            
        Returns:
            IP portfolio management result
        """
        try:
            portfolio_id = intent_data.get("portfolio_id", f"port_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            owner = intent_data.get("owner", "")
            
            # Create IP portfolio
            portfolio = IPPortfolio(
                portfolio_id=portfolio_id,
                owner=owner,
                valuation=intent_data.get("valuation"),
                last_valuation_date=intent_data.get("last_valuation_date"),
                licensing_revenue=intent_data.get("licensing_revenue", 0.0),
                maintenance_costs=intent_data.get("maintenance_costs", 0.0)
            )
            
            # Add IP assets if provided
            for patent_id in intent_data.get("patent_ids", []):
                if patent_id in self.patent_applications:
                    portfolio.patents.append(self.patent_applications[patent_id])
            
            for tm_id in intent_data.get("trademark_ids", []):
                if tm_id in self.trademark_applications:
                    portfolio.trademarks.append(self.trademark_applications[tm_id])
            
            for copy_id in intent_data.get("copyright_ids", []):
                if copy_id in self.copyright_works:
                    portfolio.copyrights.append(self.copyright_works[copy_id])
            
            for ts_id in intent_data.get("trade_secret_ids", []):
                if ts_id in self.trade_secrets:
                    portfolio.trade_secrets.append(self.trade_secrets[ts_id])
            
            # Store the portfolio
            self.ip_portfolios[portfolio_id] = portfolio
            
            # Update metrics
            self.ip_metrics["ip_portfolios_managed"] += 1
            if portfolio.valuation:
                self.ip_metrics["total_ip_value"] += portfolio.valuation
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="manage_ip_portfolio",
                details={
                    "portfolio_id": portfolio_id,
                    "owner": owner,
                    "asset_counts": {
                        "patents": len(portfolio.patents),
                        "trademarks": len(portfolio.trademarks),
                        "copyrights": len(portfolio.copyrights),
                        "trade_secrets": len(portfolio.trade_secrets)
                    },
                    "valuation": portfolio.valuation
                }
            )
            
            logger.info(f"Managed IP portfolio {portfolio_id} for {owner}")
            
            return {
                "success": True,
                "portfolio_id": portfolio_id,
                "message": f"IP portfolio {portfolio_id} managed successfully",
                "portfolio_summary": {
                    "owner": owner,
                    "total_assets": len(portfolio.patents) + len(portfolio.trademarks) + 
                                   len(portfolio.copyrights) + len(portfolio.trade_secrets),
                    "patents": len(portfolio.patents),
                    "trademarks": len(portfolio.trademarks),
                    "copyrights": len(portfolio.copyrights),
                    "trade_secrets": len(portfolio.trade_secrets),
                    "valuation": portfolio.valuation,
                    "licensing_revenue": portfolio.licensing_revenue
                },
                "recommendations": self._generate_portfolio_recommendations(portfolio)
            }
            
        except Exception as e:
            logger.error(f"Error managing IP portfolio: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to manage IP portfolio"
            }
    
    def handle_create_ip_license(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle creation of an IP license agreement.
        
        Args:
            intent_data: IP license data
            
        Returns:
            IP license creation result
        """
        try:
            license_id = intent_data.get("license_id", f"lic_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            licensor = intent_data.get("licensor", "")
            licensee = intent_data.get("licensee", "")
            ip_type_str = intent_data.get("ip_type", "patent")
            ip_references = intent_data.get("ip_references", [])
            territory = intent_data.get("territory", "worldwide")
            term_years = intent_data.get("term_years", 5)
            royalty_rate = intent_data.get("royalty_rate", 0.05)  # 5%
            
            # Create IP license
            ip_license = IPLicense(
                license_id=license_id,
                licensor=licensor,
                licensee=licensee,
                ip_type=IPType(ip_type_str),
                ip_references=ip_references,
                territory=territory,
                term_years=term_years,
                royalty_rate=royalty_rate,
                upfront_payment=intent_data.get("upfront_payment", 0.0),
                minimum_royalties=intent_data.get("minimum_royalties", 0.0),
                exclusivity=intent_data.get("exclusivity", "non-exclusive"),
                field_of_use=intent_data.get("field_of_use"),
                sublicense_allowed=intent_data.get("sublicense_allowed", False),
                audit_rights=intent_data.get("audit_rights", True),
                termination_clauses=intent_data.get("termination_clauses", []),
                effective_date=datetime.now(),
                expiration_date=datetime.now() + timedelta(days=term_years * 365) if term_years > 0 else None,
                status="draft"
            )
            
            # Store the license
            self.ip_licenses[license_id] = ip_license
            
            # Update metrics
            self.ip_metrics["licenses_negotiated"] += 1
            self.ip_metrics["licensing_revenue_generated"] += ip_license.upfront_payment
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="create_ip_license",
                details={
                    "license_id": license_id,
                    "licensor": licensor,
                    "licensee": licensee,
                    "ip_type": ip_type_str,
                    "royalty_rate": royalty_rate,
                    "term_years": term_years
                }
            )
            
            logger.info(f"Created IP license {license_id} between {licensor} and {licensee}")
            
            return {
                "success": True,
                "license_id": license_id,
                "message": f"IP license {license_id} created successfully",
                "license_summary": {
                    "parties": f"{licensor} → {licensee}",
                    "ip_type": ip_type_str,
                    "ip_references": len(ip_references),
                    "territory": territory,
                    "term": f"{term_years} years",
                    "royalty_rate": f"{royalty_rate * 100}%",
                    "upfront_payment": ip_license.upfront_payment,
                    "exclusivity": ip_license.exclusivity
                },
                "next_steps": [
                    "Draft full license agreement",
                    "Review with legal counsel",
                    "Execute signatures",
                    "Record license if required"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error creating IP license: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create IP license"
            }
    
    def handle_check_ip_status(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle checking status of intellectual property.
        
        Args:
            intent_data: IP status check data
            
        Returns:
            IP status check result
        """
        try:
            ip_id = intent_data.get("ip_id", "")
            ip_type = intent_data.get("ip_type", "")  # patent, trademark, copyright, trade_secret
            
            status_info = {}
            
            if ip_type == "patent" and ip_id in self.patent_applications:
                patent = self.patent_applications[ip_id]
                status_info = {
                    "type": "patent",
                    "id": ip_id,
                    "title": patent.title,
                    "status": patent.status.value,
                    "filing_date": patent.filing_date.isoformat(),
                    "jurisdiction": patent.jurisdiction.value,
                    "deadlines": [{"type": d.get("type"), "date": d.get("date")} for d in patent.deadlines],
                    "office_actions": len(patent.office_actions),
                    "next_action": self._get_next_patent_action(patent)
                }
                
            elif ip_type == "trademark" and ip_id in self.trademark_applications:
                trademark = self.trademark_applications[ip_id]
                status_info = {
                    "type": "trademark",
                    "id": ip_id,
                    "mark": trademark.mark,
                    "status": trademark.status.value,
                    "filing_date": trademark.filing_date.isoformat(),
                    "class": trademark.trademark_class.value,
                    "registration_number": trademark.registration_number,
                    "renewal_dates": [d.isoformat() for d in trademark.renewal_dates],
                    "oppositions": len(trademark.opposition_notices)
                }
                
            elif ip_type == "copyright" and ip_id in self.copyright_works:
                copyright = self.copyright_works[ip_id]
                status_info = {
                    "type": "copyright",
                    "id": ip_id,
                    "title": copyright.title,
                    "status": copyright.status.value,
                    "creation_date": copyright.creation_date.isoformat(),
                    "registration_number": copyright.registration_number,
                    "authors": copyright.authors,
                    "derivative_works": len(copyright.derivative_works)
                }
                
            elif ip_type == "trade_secret" and ip_id in self.trade_secrets:
                trade_secret = self.trade_secrets[ip_id]
                status_info = {
                    "type": "trade_secret",
                    "id": ip_id,
                    "name": trade_secret.name,
                    "status": trade_secret.status,
                    "confidentiality_level": trade_secret.confidentiality_level,
                    "last_audit": trade_secret.last_audit.isoformat() if trade_secret.last_audit else None,
                    "authorized_persons": len(trade_secret.authorized_persons),
                    "protection_measures": len(trade_secret.protection_measures)
                }
                
            else:
                return {
                    "success": False,
                    "error": f"IP {ip_id} of type {ip_type} not found",
                    "message": "IP not found in system"
                }
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="check_ip_status",
                details={
                    "ip_id": ip_id,
                    "ip_type": ip_type,
                    "status": status_info.get("status", "unknown")
                }
            )
            
            logger.info(f"Checked status for {ip_type} {ip_id}")
            
            return {
                "success": True,
                "ip_id": ip_id,
                "ip_type": ip_type,
                "status_info": status_info,
                "message": f"Status check completed for {ip_type} {ip_id}"
            }
            
        except Exception as e:
            logger.error(f"Error checking IP status: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to check IP status"
            }
    
    def handle_respond_to_office_action(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle response to a patent or trademark office action.
        
        Args:
            intent_data: Office action response data
            
        Returns:
            Office action response result
        """
        try:
            ip_id = intent_data.get("ip_id", "")
            ip_type = intent_data.get("ip_type", "patent")
            office_action_id = intent_data.get("office_action_id", "")
            response_text = intent_data.get("response_text", "")
            amendments = intent_data.get("amendments", [])
            
            response_result = {}
            
            if ip_type == "patent" and ip_id in self.patent_applications:
                patent = self.patent_applications[ip_id]
                
                # Record the response
                response_record = {
                    "office_action_id": office_action_id,
                    "response_date": datetime.now().isoformat(),
                    "response_text": response_text,
                    "amendments": amendments,
                    "responded_by": self.agent_id
                }
                
                patent.office_actions.append(response_record)
                patent.updated_at = datetime.now()
                
                # Update status if needed
                if patent.status == IPStatus.EXAMINATION:
                    patent.status = IPStatus.PENDING
                
                response_result = {
                    "type": "patent",
                    "office_action_responded": office_action_id,
                    "next_deadline": (datetime.now() + timedelta(days=90)).isoformat(),  # Typical response deadline
                    "status_update": patent.status.value
                }
                
                # Update metrics
                self.ip_metrics["office_actions_responded"] += 1
                
            elif ip_type == "trademark" and ip_id in self.trademark_applications:
                trademark = self.trademark_applications[ip_id]
                
                # For trademarks, office actions are typically examination reports
                if trademark.examination_report:
                    trademark.examination_report = f"RESPONDED: {response_text}"
                    trademark.updated_at = datetime.now()
                    
                    if trademark.status == IPStatus.EXAMINATION:
                        trademark.status = IPStatus.PENDING
                
                response_result = {
                    "type": "trademark",
                    "examination_report_responded": True,
                    "status_update": trademark.status.value
                }
                
            else:
                return {
                    "success": False,
                    "error": f"Cannot respond to office action for {ip_type} {ip_id}",
                    "message": "IP not found or invalid type for office action"
                }
            
            # Log ISO compliance
            self._log_iso_compliance(
                action="respond_to_office_action",
                details={
                    "ip_id": ip_id,
                    "ip_type": ip_type,
                    "office_action_id": office_action_id,
                    "response_length": len(response_text)
                }
            )
            
            logger.info(f"Responded to office action for {ip_type} {ip_id}")
            
            return {
                "success": True,
                "ip_id": ip_id,
                "ip_type": ip_type,
                "response_result": response_result,
                "message": f"Successfully responded to office action for {ip_type} {ip_id}"
            }
            
        except Exception as e:
            logger.error(f"Error responding to office action: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to respond to office action"
            }
    
    def _suggest_trademark_searches(self, mark: str, trademark_class: str) -> List[str]:
        """Suggest trademark searches to conduct."""
        searches = [
            f"USPTO TESS search for '{mark}' in class {trademark_class}",
            f"Common law search for '{mark}' in business directories",
            f"Internet domain search for '{mark}.com' and variations",
            f"Social media handle search for '@{mark.replace(' ', '')}'"
        ]
        
        if " " in mark:
            searches.append(f"Search for phonetic equivalents of '{mark}'")
        
        return searches
    
    def _get_next_patent_action(self, patent: PatentApplication) -> str:
        """Determine next action needed for a patent."""
        if patent.status == IPStatus.DRAFT:
            return "Complete specification and file application"
        elif patent.status == IPStatus.FILED:
            return "Await official filing receipt"
        elif patent.status == IPStatus.EXAMINATION:
            if patent.office_actions:
                return "Respond to most recent office action"
            else:
                return "Await first office action"
        elif patent.status == IPStatus.ALLOWED:
            return "Pay issue fee"
        elif patent.status == IPStatus.GRANTED:
            return "Schedule maintenance fee payments"
        else:
            return "Monitor status and deadlines"
    
    def _generate_portfolio_recommendations(self, portfolio: IPPortfolio) -> List[str]:
        """Generate recommendations for an IP portfolio."""
        recommendations = []
        
        # Count assets by type
        patent_count = len(portfolio.patents)
        trademark_count = len(portfolio.trademarks)
        copyright_count = len(portfolio.copyrights)
        trade_secret_count = len(portfolio.trade_secrets)
        
        # Generate recommendations based on portfolio composition
        if patent_count > 0:
            recommendations.append(f"Consider patent maintenance fee schedule for {patent_count} patents")
            if patent_count > 5:
                recommendations.append("Evaluate potential for patent pool or cross-licensing")
        
        if trademark_count > 0:
            recommendations.append(f"Monitor trademark renewal dates for {trademark_count} marks")
            recommendations.append("Conduct periodic trademark watch services")
        
        if copyright_count > 0:
            recommendations.append(f"Ensure proper copyright notices on {copyright_count} works")
            if any(c.publication_date for c in portfolio.copyrights):
                recommendations.append("Consider copyright registration for published works")
        
        if trade_secret_count > 0:
            recommendations.append(f"Schedule regular trade secret audits for {trade_secret_count} secrets")
            recommendations.append("Review and update confidentiality agreements")
        
        # General recommendations
        total_assets = patent_count + trademark_count + copyright_count + trade_secret_count
        if total_assets > 10:
            recommendations.append("Consider IP portfolio insurance")
        
        if portfolio.licensing_revenue > 0:
            recommendations.append("Review licensing agreements for optimization")
        
        return recommendations
    
    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get current status of the IP agent.
        
        Returns:
            Agent status information
        """
        base_status = super().get_agent_status()
        
        ip_specific_status = {
            "ip_metrics": self.ip_metrics,
            "active_counts": {
                "patent_applications": len(self.patent_applications),
                "trademark_applications": len(self.trademark_applications),
                "copyright_works": len(self.copyright_works),
                "trade_secrets": len(self.trade_secrets),
                "ip_portfolios": len(self.ip_portfolios),
                "ip_licenses": len(self.ip_licenses)
            },
            "templates_available": {
                "patent_templates": len(self.patent_templates),
                "trademark_templates": len(self.trademark_templates),
                "license_templates": len(self.license_templates)
            }
        }
        
        base_status.update(ip_specific_status)
        return base_status
    
    def _log_iso_compliance(self, action: str, details: Dict[str, Any]):
        """Log ISO compliance event."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "action": action,
            "details": details,
            "compliance_standard": "ISO 27001:2022",
            "security_level": "confidential"
        }
        
        # Save to compliance log
        log_dir = Path("logs/compliance")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"ip_compliance_{datetime.now().strftime('%Y%m')}.json"
        
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


def test_intellectual_property_agent():
    """Test function for Intellectual Property Agent."""
    print("Testing Intellectual Property Agent...")
    
    # Create agent instance
    agent = IntellectualPropertyAgent("ip_agent_001")
    
    # Test 1: Create patent application
    print("\n1. Testing patent application creation...")
    patent_data = {
        "title": "Self-Driving Vehicle Navigation System",
        "patent_type": "utility",
        "jurisdiction": "uspto",
        "inventors": [
            {
                "name": "Dr. Jane Smith",
                "address": "123 Tech Blvd, San Francisco, CA",
                "nationality": "US",
                "contribution": "Primary inventor of navigation algorithm",
                "assignment_executed": True
            }
        ],
        "abstract": "A novel navigation system for autonomous vehicles using AI-based path planning.",
        "claims": [
            "1. A navigation system comprising...",
            "2. The system of claim 1, further comprising..."
        ],
        "description": "Detailed description of the navigation system..."
    }
    
    result = agent.handle_create_patent_application(patent_data)
    print(f"Patent creation result: {result.get('success')}")
    print(f"Application ID: {result.get('application_id')}")
    
    # Test 2: Create trademark application
    print("\n2. Testing trademark application creation...")
    trademark_data = {
        "mark": "AUTOPILOT+",
        "trademark_class": "CLASS_9",
        "goods_services": "Computer software for autonomous vehicle control",
        "jurisdiction": "uspto",
        "applicant_name": "Tech Innovations Inc.",
        "applicant_address": "456 Innovation Way, Palo Alto, CA"
    }
    
    result = agent.handle_create_trademark_application(trademark_data)
    print(f"Trademark creation result: {result.get('success')}")
    print(f"Application ID: {result.get('application_id')}")
    
    # Test 3: Register copyright
    print("\n3. Testing copyright registration...")
    copyright_data = {
        "title": "Autonomous Vehicle Control Software v2.0",
        "category": "SOFTWARE",
        "authors": ["Tech Innovations Inc.", "Dr. Jane Smith"],
        "creation_date": datetime.now()
    }
    
    result = agent.handle_register_copyright(copyright_data)
    print(f"Copyright registration result: {result.get('success')}")
    print(f"Work ID: {result.get('work_id')}")
    
    # Test 4: Check agent status
    print("\n4. Testing agent status...")
    status = agent.get_agent_status()
    print(f"Agent active: {status.get('active')}")
    print(f"IP metrics: {status.get('ip_metrics')}")
    
    print("\nIntellectual Property Agent test completed successfully!")


if __name__ == "__main__":
    test_intellectual_property_agent()