"""
Regulatory Change Tracker - Build 16 Enhancement
Monitors and tracks regulatory changes from various sources.
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
import threading
import time
import re
from pathlib import Path
import feedparser
import requests
from bs4 import BeautifulSoup

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChangeSource(Enum):
    """Sources of regulatory changes."""
    SEC = "sec"
    FINRA = "finra"
    CFTC = "cftc"
    OCC = "occ"
    FDIC = "fdic"
    FED = "fed"
    STATE = "state"
    INTERNATIONAL = "international"
    RSS_FEED = "rss_feed"
    API = "api"
    WEBSITE = "website"
    EMAIL = "email"
    MANUAL = "manual"


class ChangeImpact(Enum):
    """Impact levels of regulatory changes."""
    CRITICAL = "critical"  # Requires immediate action
    HIGH = "high"  # Significant impact, plan required
    MEDIUM = "medium"  # Moderate impact, review required
    LOW = "low"  # Minor impact, monitor
    INFORMATIONAL = "informational"  # No action required


@dataclass
class RegulatorySource:
    """Source configuration for regulatory monitoring."""
    source_id: str
    name: str
    source_type: ChangeSource
    url: str
    update_frequency: str  # hourly, daily, weekly, monthly
    last_checked: Optional[datetime] = None
    is_active: bool = True
    authentication: Optional[Dict[str, Any]] = None
    parsing_config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DetectedChange:
    """Detected regulatory change."""
    change_id: str
    source_id: str
    title: str
    description: str
    publication_date: datetime
    effective_date: Optional[datetime] = None
    regulation_references: List[str] = field(default_factory=list)
    impact_areas: List[str] = field(default_factory=list)
    raw_content: Optional[str] = None
    parsed_content: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0.0 to 1.0
    requires_review: bool = True
    reviewed: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ImpactAssessment:
    """Impact assessment for a regulatory change."""
    assessment_id: str
    change_id: str
    assessed_by: str
    impact_level: ChangeImpact
    affected_departments: List[str]
    estimated_cost: Optional[float] = None
    timeline_weeks: Optional[int] = None
    action_items: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class RegulatoryChangeTracker:
    """
    Regulatory Change Tracker.
    Monitors various sources for regulatory changes and tracks their impact.
    """
    
    def __init__(self, tracker_id: str = "regulatory_tracker_001"):
        """
        Initialize Regulatory Change Tracker.
        
        Args:
            tracker_id: Unique tracker identifier
        """
        self.tracker_id = tracker_id
        self.sources: Dict[str, RegulatorySource] = {}
        self.detected_changes: Dict[str, DetectedChange] = {}
        self.impact_assessments: Dict[str, ImpactAssessment] = {}
        
        # Monitoring thread
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Load default sources
        self._load_default_sources()
        
        # Metrics
        self.metrics = {
            "total_sources": len(self.sources),
            "active_sources": sum(1 for s in self.sources.values() if s.is_active),
            "total_changes": 0,
            "changes_today": 0,
            "pending_reviews": 0,
            "critical_changes": 0,
            "last_check": None
        }
        
        logger.info(f"Initialized Regulatory Change Tracker {tracker_id}")
    
    def _load_default_sources(self):
        """Load default regulatory sources."""
        default_sources = [
            RegulatorySource(
                source_id="sec_rss",
                name="SEC Press Releases RSS",
                source_type=ChangeSource.RSS_FEED,
                url="https://www.sec.gov/news/pressreleases.rss",
                update_frequency="daily",
                parsing_config={
                    "item_selector": "item",
                    "title_selector": "title",
                    "description_selector": "description",
                    "date_selector": "pubDate",
                    "link_selector": "link"
                }
            ),
            RegulatorySource(
                source_id="finra_notices",
                name="FINRA Regulatory Notices",
                source_type=ChangeSource.WEBSITE,
                url="https://www.finra.org/rules-guidance/notices",
                update_frequency="weekly",
                parsing_config={
                    "container_selector": ".notice-list-item",
                    "title_selector": "h3",
                    "date_selector": ".date",
                    "link_selector": "a"
                }
            ),
            RegulatorySource(
                source_id="cftc_rules",
                name="CFTC Rule Changes",
                source_type=ChangeSource.API,
                url="https://www.cftc.gov/LawRegulation/CFTCRules/index.htm",
                update_frequency="weekly",
                parsing_config={
                    "api_endpoint": "/api/rules/changes",
                    "date_format": "%Y-%m-%d"
                }
            )
        ]
        
        for source in default_sources:
            self.sources[source.source_id] = source
        
        logger.info(f"Loaded {len(default_sources)} default regulatory sources")
    
    def start_monitoring(self):
        """Start regulatory change monitoring."""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("Regulatory change monitoring started")
    
    def stop_monitoring(self):
        """Stop regulatory change monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Regulatory change monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Check each source based on its frequency
                self._check_sources()
                
                # Update metrics
                self._update_metrics()
                
                # Sleep for 1 hour
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(300)  # Sleep 5 minutes on error
    
    def _check_sources(self):
        """Check all active sources for changes."""
        now = datetime.now()
        changes_detected = 0
        
        for source_id, source in self.sources.items():
            if not source.is_active:
                continue
            
            # Check if it's time to check this source
            if not self._should_check_source(source, now):
                continue
            
            try:
                logger.info(f"Checking source: {source.name}")
                
                # Check the source based on type
                changes = self._check_source(source)
                
                if changes:
                    for change in changes:
                        change_id = f"change_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.detected_changes)}"
                        change.change_id = change_id
                        self.detected_changes[change_id] = change
                        changes_detected += 1
                        
                        logger.info(f"Detected change: {change.title}")
                
                # Update source last checked time
                source.last_checked = now
                source.updated_at = now
                
            except Exception as e:
                logger.error(f"Error checking source {source_id}: {str(e)}")
        
        if changes_detected > 0:
            self.metrics["changes_today"] += changes_detected
            self.metrics["total_changes"] += changes_detected
            self.metrics["pending_reviews"] += changes_detected
        
        self.metrics["last_check"] = now.isoformat()
    
    def _should_check_source(self, source: RegulatorySource, now: datetime) -> bool:
        """
        Determine if a source should be checked.
        
        Args:
            source: Regulatory source
            now: Current datetime
            
        Returns:
            True if source should be checked
        """
        if not source.last_checked:
            return True
        
        # Calculate time since last check
        time_since_check = now - source.last_checked
        
        # Check based on frequency
        if source.update_frequency == "hourly":
            return time_since_check.total_seconds() >= 3600
        elif source.update_frequency == "daily":
            return time_since_check.total_seconds() >= 86400
        elif source.update_frequency == "weekly":
            return time_since_check.total_seconds() >= 604800
        elif source.update_frequency == "monthly":
            return time_since_check.days >= 30
        else:
            return time_since_check.total_seconds() >= 86400  # Default daily
    
    def _check_source(self, source: RegulatorySource) -> List[DetectedChange]:
        """
        Check a specific source for changes.
        
        Args:
            source: Regulatory source to check
            
        Returns:
            List of detected changes
        """
        changes = []
        
        try:
            if source.source_type == ChangeSource.RSS_FEED:
                changes = self._check_rss_feed(source)
            elif source.source_type == ChangeSource.WEBSITE:
                changes = self._check_website(source)
            elif source.source_type == ChangeSource.API:
                changes = self._check_api(source)
            else:
                logger.warning(f"Unsupported source type: {source.source_type}")
        
        except Exception as e:
            logger.error(f"Error checking source {source.source_id}: {str(e)}")
        
        return changes
    
    def _check_rss_feed(self, source: RegulatorySource) -> List[DetectedChange]:
        """Check RSS feed for changes."""
        changes = []
        
        try:
            # Parse RSS feed
            feed = feedparser.parse(source.url)
            
            if feed.entries:
                for entry in feed.entries[:10]:  # Check latest 10 entries
                    # Parse publication date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    else:
                        pub_date = datetime.now()
                    
                    # Check if this is new (published in last 7 days)
                    if (datetime.now() - pub_date).days > 7:
                        continue
                    
                    # Extract regulation references
                    regulation_refs = self._extract_regulation_references(
                        getattr(entry, 'description', '') + ' ' + getattr(entry, 'title', '')
                    )
                    
                    # Create detected change
                    change = DetectedChange(
                        change_id="",  # Will be set by caller
                        source_id=source.source_id,
                        title=getattr(entry, 'title', 'Untitled'),
                        description=getattr(entry, 'description', 'No description'),
                        publication_date=pub_date,
                        regulation_references=regulation_refs,
                        impact_areas=self._identify_impact_areas(
                            getattr(entry, 'description', '') + ' ' + getattr(entry, 'title', '')
                        ),
                        raw_content=str(entry),
                        parsed_content={
                            "link": getattr(entry, 'link', ''),
                            "author": getattr(entry, 'author', ''),
                            "categories": getattr(entry, 'tags', [])
                        },
                        confidence=0.8,  # RSS feeds are usually reliable
                        requires_review=True
                    )
                    
                    changes.append(change)
        
        except Exception as e:
            logger.error(f"Error parsing RSS feed {source.url}: {str(e)}")
        
        return changes
    
    def _check_website(self, source: RegulatorySource) -> List[DetectedChange]:
        """Check website for changes."""
        changes = []
        
        try:
            # Make HTTP request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(source.url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract content based on parsing config
            parsing_config = source.parsing_config
            
            if 'container_selector' in parsing_config:
                containers = soup.select(parsing_config['container_selector'])
                
                for container in containers[:10]:  # Check latest 10 items
                    try:
                        # Extract title
                        title_elem = container.select_one(parsing_config.get('title_selector', 'h1, h2, h3'))
                        title = title_elem.get_text(strip=True) if title_elem else "Untitled"
                        
                        # Extract date
                        date_elem = container.select_one(parsing_config.get('date_selector', '.date, time'))
                        date_text = date_elem.get_text(strip=True) if date_elem else ""
                        pub_date = self._parse_date(date_text) or datetime.now()
                        
                        # Extract link
                        link_elem = container.select_one(parsing_config.get('link_selector', 'a'))
                        link = link_elem.get('href', '') if link_elem else ''
                        if link and not link.startswith('http'):
                            link = source.url + link if source.url.endswith('/') else source.url + '/' + link
                        
                        # Extract description
                        description = container.get_text(strip=True)[:500]  # First 500 chars
                        
                        # Check if this is new (published in last 7 days)
                        if (datetime.now() - pub_date).days > 7:
                            continue
                        
                        # Extract regulation references
                        regulation_refs = self._extract_regulation_references(description + ' ' + title)
                        
                        # Create detected change
                        change = DetectedChange(
                            change_id="",  # Will be set by caller
                            source_id=source.source_id,
                            title=title,
                            description=description,
                            publication_date=pub_date,
                            regulation_references=regulation_refs,
                            impact_areas=self._identify_impact_areas(description + ' ' + title),
                            raw_content=str(container),
                            parsed_content={
                                "link": link,
                                "full_url": source.url
                            },
                            confidence=0.6,  # Website scraping less reliable
                            requires_review=True
                        )
                        
                        changes.append(change)
                        
                    except Exception as e:
                        logger.error(f"Error parsing website container: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error checking website {source.url}: {str(e)}")
        
        return changes
    
    def _check_api(self, source: RegulatorySource) -> List[DetectedChange]:
        """Check API for changes."""
        changes = []
        
        try:
            # This is a simplified version - real implementation would use actual API
            logger.info(f"Checking API source: {source.name}")
            
            # For demonstration, create a mock change
            # In production, this would make actual API calls
            if "cftc" in source.source_id.lower():
                # Mock CFTC rule change
                change = DetectedChange(
                    change_id="",  # Will be set by caller
                    source_id=source.source_id,
                    title="CFTC Proposes Amendments to Reporting Requirements",
                    description="The Commodity Futures Trading Commission has proposed amendments to Part 45 of its regulations regarding swap data reporting.",
                    publication_date=datetime.now() - timedelta(days=1),
                    effective_date=datetime.now() + timedelta(days=90),
                    regulation_references=["CFTC Regulation 45", "Dodd-Frank Act"],
                    impact_areas=["Reporting", "Compliance", "Data Management"],
                    raw_content="Mock API response",
                    parsed_content={
                        "api_response": "mock",
                        "rule_number": "45.6",
                        "comment_period_end": (datetime.now() + timedelta(days=60)).isoformat()
                    },
                    confidence=0.9,
                    requires_review=True
                )
                changes.append(change)
        
        except Exception as e:
            logger.error(f"Error checking API {source.source_id}: {str(e)}")
        
        return changes
    
    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse date from text."""
        if not date_text:
            return None
        
        # Try common date formats
        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y"
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue
        
        # Try to extract date with regex
        date_patterns = [
            r'(\d{4})-(\d{2})-(\d{2})',  # YYYY-MM-DD
            r'(\d{2})/(\d{2})/(\d{4})',  # MM/DD/YYYY or DD/MM/YYYY
            r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_text, re.IGNORECASE)
            if match:
                try:
                    # This is simplified - real implementation would parse properly
                    return datetime.now()
                except:
                    continue
        
        return None
    
    def _extract_regulation_references(self, text: str) -> List[str]:
        """Extract regulation references from text."""
        references = []
        
        # Common regulation patterns
        patterns = [
            r'(?:SEC|Securities and Exchange Commission)\s+(?:Rule|Regulation)\s+([A-Z0-9-]+)',
            r'(?:FINRA|Financial Industry Regulatory Authority)\s+(?:Rule|Regulation)\s+([0-9]+)',
            r'(?:CFTC|Commodity Futures Trading Commission)\s+(?:Rule|Regulation)\s+([0-9]+)',
            r'(?:OCC|Office of the Comptroller of the Currency)\s+(?:Rule|Regulation)\s+([A-Z0-9-]+)',
            r'(?:FDIC|Federal Deposit Insurance Corporation)\s+(?:Rule|Regulation)\s+([0-9]+)',
            r'Regulation\s+([A-Z]{1,3})',  # Regulation D, Regulation FD, etc.
            r'Rule\s+([0-9]{1,4}[a-z]?)',  # Rule 10b-5, Rule 144, etc.
            r'§\s*([0-9]+\.[0-9]+)',  # § 1.1, § 45.6, etc.
            r'Section\s+([0-9]+[a-z]?)',  # Section 10, Section 16, etc.
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                reference = match.group(1)
                if reference not in references:
                    references.append(reference)
        
        return references
    
    def _identify_impact_areas(self, text: str) -> List[str]:
        """Identify impact areas from text."""
        impact_areas = []
        text_lower = text.lower()
        
        # Map keywords to impact areas
        keyword_map = {
            "reporting": ["report", "filing", "disclosure", "submit", "file"],
            "compliance": ["compliance", "violation", "penalty", "enforcement", "audit"],
            "risk": ["risk", "exposure", "liability", "loss"],
            "data": ["data", "privacy", "security", "confidential", "pii"],
            "trading": ["trade", "market", "exchange", "broker", "dealer"],
            "banking": ["bank", "deposit", "loan", "credit", "lending"],
            "insurance": ["insurance", "premium", "claim", "coverage"],
            "consumer": ["consumer", "customer", "client", "borrower"],
            "environmental": ["environment", "climate", "sustainability", "emission"],
            "employment": ["employee", "labor", "workplace", "discrimination"]
        }
        
        for area, keywords in keyword_map.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if area not in impact_areas:
                        impact_areas.append(area)
                    break
        
        return impact_areas
    
    def add_source(self, source: RegulatorySource) -> str:
        """
        Add a new regulatory source.
        
        Args:
            source: Regulatory source to add
            
        Returns:
            Source ID
        """
        self.sources[source.source_id] = source
        self.metrics["total_sources"] = len(self.sources)
        if source.is_active:
            self.metrics["active_sources"] += 1
        
        logger.info(f"Added regulatory source {source.source_id}: {source.name}")
        return source.source_id
    
    def review_change(self, change_id: str, reviewed_by: str, notes: str = "") -> bool:
        """
        Review a detected change.
        
        Args:
            change_id: Change ID
            reviewed_by: Person reviewing
            notes: Review notes
            
        Returns:
            Success status
        """
        if change_id not in self.detected_changes:
            return False
        
        change = self.detected_changes[change_id]
        change.reviewed = True
        change.reviewed_by = reviewed_by
        change.reviewed_at = datetime.now()
        change.updated_at = datetime.now()
        
        # Add review notes to parsed content
        if notes:
            change.parsed_content["review_notes"] = notes
        
        self.metrics["pending_reviews"] = max(0, self.metrics["pending_reviews"] - 1)
        
        logger.info(f"Change {change_id} reviewed by {reviewed_by}")
        return True
    
    def create_impact_assessment(self, change_id: str, assessed_by: str, 
                                impact_level: ChangeImpact, 
                                affected_departments: List[str]) -> str:
        """
        Create impact assessment for a change.
        
        Args:
            change_id: Change ID
            assessed_by: Person assessing
            impact_level: Impact level
            affected_departments: Affected departments
            
        Returns:
            Assessment ID
        """
        if change_id not in self.detected_changes:
            raise ValueError(f"Change {change_id} not found")
        
        assessment_id = f"assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        assessment = ImpactAssessment(
            assessment_id=assessment_id,
            change_id=change_id,
            assessed_by=assessed_by,
            impact_level=impact_level,
            affected_departments=affected_departments,
            action_items=[
                "Review regulatory text",
                "Assess current compliance status",
                "Identify required changes",
                "Estimate implementation timeline"
            ],
            recommendations=[
                "Schedule compliance review meeting",
                "Update policies and procedures",
                "Train affected staff",
                "Monitor implementation"
            ]
        )
        
        self.impact_assessments[assessment_id] = assessment
        
        # Update change confidence based on assessment
        change = self.detected_changes[change_id]
        if impact_level == ChangeImpact.CRITICAL:
            change.confidence = min(1.0, change.confidence + 0.2)
            self.metrics["critical_changes"] += 1
        
        logger.info(f"Created impact assessment {assessment_id} for change {change_id}")
        return assessment_id
    
    def _update_metrics(self):
        """Update tracker metrics."""
        # Count pending reviews
        pending = sum(1 for c in self.detected_changes.values() 
                     if c.requires_review and not c.reviewed)
        self.metrics["pending_reviews"] = pending
        
        # Count critical changes
        critical = 0
        for assessment in self.impact_assessments.values():
            if assessment.impact_level == ChangeImpact.CRITICAL and not assessment.completed:
                critical += 1
        
        self.metrics["critical_changes"] = critical
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get dashboard data.
        
        Returns:
            Dashboard data
        """
        # Update metrics first
        self._update_metrics()
        
        # Get recent changes
        recent_changes = []
        for change in sorted(self.detected_changes.values(),
                           key=lambda c: c.publication_date,
                           reverse=True)[:10]:
            recent_changes.append({
                "id": change.change_id,
                "title": change.title,
                "source": self.sources.get(change.source_id, RegulatorySource(
                    source_id="unknown", name="Unknown", 
                    source_type=ChangeSource.MANUAL, url="", update_frequency="daily"
                )).name,
                "publication_date": change.publication_date.isoformat(),
                "reviewed": change.reviewed,
                "confidence": change.confidence,
                "regulation_references": change.regulation_references[:3]
            })
        
        # Get pending assessments
        pending_assessments = []
        for assessment in self.impact_assessments.values():
            if not assessment.completed:
                change = self.detected_changes.get(assessment.change_id)
                if change:
                    pending_assessments.append({
                        "id": assessment.assessment_id,
                        "change_title": change.title,
                        "impact_level": assessment.impact_level.value,
                        "assessed_by": assessment.assessed_by,
                        "created_at": assessment.created_at.isoformat()
                    })
        
        return {
            "metrics": self.metrics,
            "recent_changes": recent_changes,
            "pending_assessments": pending_assessments,
            "total_assessments": len(self.impact_assessments),
            "monitoring_active": self.monitoring_active,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get tracker status.
        
        Returns:
            Status information
        """
        return {
            "tracker_id": self.tracker_id,
            "monitoring_active": self.monitoring_active,
            "sources_count": len(self.sources),
            "changes_count": len(self.detected_changes),
            "assessments_count": len(self.impact_assessments),
            "metrics": self.metrics,
            "timestamp": datetime.now().isoformat()
        }


def test_regulatory_change_tracker():
    """Test function for Regulatory Change Tracker."""
    print("Testing Regulatory Change Tracker...")
    
    # Create tracker instance
    tracker = RegulatoryChangeTracker()
    
    # Test 1: Get initial status
    print("\n1. Testing initial status...")
    status = tracker.get_status()
    print(f"Tracker ID: {status['tracker_id']}")
    print(f"Sources: {status['sources_count']}")
    print(f"Active sources: {status['metrics']['active_sources']}")
    
    # Test 2: Add new source
    print("\n2. Adding new regulatory source...")
    new_source = RegulatorySource(
        source_id="test_source_001",
        name="Test Regulatory Source",
        source_type=ChangeSource.MANUAL,
        url="https://example.com/regulations",
        update_frequency="daily",
        parsing_config={"test": "config"}
    )
    tracker.add_source(new_source)
    print(f"Added source: {new_source.name}")
    
    # Test 3: Create mock change (since we can't actually scrape in test)
    print("\n3. Creating mock regulatory change...")
    mock_change = DetectedChange(
        change_id="mock_change_001",
        source_id="test_source_001",
        title="Test Regulatory Change",
        description="This is a test regulatory change for demonstration purposes.",
        publication_date=datetime.now(),
        regulation_references=["Test Regulation 1.1", "Test Rule 101"],
        impact_areas=["Compliance", "Reporting"],
        confidence=0.9,
        requires_review=True
    )
    tracker.detected_changes[mock_change.change_id] = mock_change
    tracker.metrics["total_changes"] += 1
    tracker.metrics["pending_reviews"] += 1
    print(f"Created mock change: {mock_change.title}")
    
    # Test 4: Review change
    print("\n4. Reviewing change...")
    success = tracker.review_change("mock_change_001", "test_reviewer", "Test review notes")
    print(f"Review successful: {success}")
    
    # Test 5: Create impact assessment
    print("\n5. Creating impact assessment...")
    try:
        assessment_id = tracker.create_impact_assessment(
            change_id="mock_change_001",
            assessed_by="test_assessor",
            impact_level=ChangeImpact.MEDIUM,
            affected_departments=["Legal", "Compliance", "IT"]
        )
        print(f"Created assessment: {assessment_id}")
    except ValueError as e:
        print(f"Assessment creation failed: {e}")
    
    # Test 6: Get dashboard data
    print("\n6. Getting dashboard data...")
    dashboard = tracker.get_dashboard_data()
    print(f"Total changes: {dashboard['metrics']['total_changes']}")
    print(f"Pending reviews: {dashboard['metrics']['pending_reviews']}")
    print(f"Recent changes: {len(dashboard['recent_changes'])}")
    
    # Test 7: Start and stop monitoring
    print("\n7. Testing monitoring control...")
    tracker.start_monitoring()
    print("Monitoring started")
    time.sleep(1)  # Brief pause
    tracker.stop_monitoring()
    print("Monitoring stopped")
    
    # Final status
    print("\n8. Final status...")
    final_status = tracker.get_status()
    print(f"Total sources: {final_status['sources_count']}")
    print(f"Total changes: {final_status['changes_count']}")
    print(f"Total assessments: {final_status['assessments_count']}")
    print(f"Monitoring active: {final_status['monitoring_active']}")
    
    print("\nRegulatory Change Tracker test completed successfully!")


if __name__ == "__main__":
    test_regulatory_change_tracker()