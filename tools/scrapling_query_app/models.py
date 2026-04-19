"""
Data models for the Scrapling Query Tool.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class ExtractionStatus(str, Enum):
    """Status of content extraction."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class FetcherType(str, Enum):
    """Type of fetcher to use."""
    STATIC = "static"  # FetcherSession for static sites
    DYNAMIC = "dynamic"  # DynamicSession for JS-heavy sites
    STEALTHY = "stealthy"  # StealthySession for anti-bot sites


@dataclass
class QueryRequest:
    """Request for a query-based search."""
    query: str
    max_results: int = 10
    fetcher_type: FetcherType = FetcherType.DYNAMIC
    use_cache: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Result from a web search for a query."""
    url: str
    title: str
    snippet: str
    relevance_score: float = 0.0
    source: str = "web_search"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedContent:
    """Content extracted from a web page."""
    url: str
    title: str
    text_content: str
    html_content: Optional[str] = None
    status: ExtractionStatus = ExtractionStatus.PENDING
    error_message: Optional[str] = None
    extracted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Structured fields that might be extracted
    author: Optional[str] = None
    published_date: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)


@dataclass
class QueryResponse:
    """Complete response for a query."""
    query: str
    request_id: str
    submitted_at: str
    completed_at: Optional[str] = None
    search_results: List[SearchResult] = field(default_factory=list)
    extracted_content: List[ExtractedContent] = field(default_factory=list)
    status: str = "processing"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def successful_extractions(self) -> List[ExtractedContent]:
        """Get successfully extracted content."""
        return [c for c in self.extracted_content if c.status == ExtractionStatus.SUCCESS]
    
    @property
    def failed_extractions(self) -> List[ExtractedContent]:
        """Get failed extractions."""
        return [c for c in self.extracted_content if c.status == ExtractionStatus.FAILED]