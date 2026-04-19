"""
External Integration Layer - Build 14 Part 1
Integrates with external legal systems: PACER, SEC EDGAR, USPTO, CourtListener, etc.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import time
import hashlib
from pathlib import Path
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    """Types of external integrations."""
    PACER = "pacer"  # Public Access to Court Electronic Records
    SEC_EDGAR = "sec_edgar"  # SEC Electronic Data Gathering, Analysis, and Retrieval
    USPTO = "uspto"  # United States Patent and Trademark Office
    COURT_LISTENER = "court_listener"
    OPEN_STATES = "open_states"
    BLOOMBERG_LAW = "bloomberg_law"
    LEXIS_NEXIS = "lexis_nexis"
    WESTLAW = "westlaw"
    FASTCASE = "fastcase"
    CUSTOM = "custom"


class IntegrationStatus(Enum):
    """Integration status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    MAINTENANCE = "maintenance"


class DataFormat(Enum):
    """Data formats from external systems."""
    JSON = "json"
    XML = "xml"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"
    CSV = "csv"


@dataclass
class IntegrationConfig:
    """Configuration for an external integration."""
    integration_id: str
    integration_type: IntegrationType
    base_url: str
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    rate_limit: int = 100  # requests per hour
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5  # seconds
    cache_enabled: bool = True
    cache_ttl: int = 3600  # seconds
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class IntegrationMetrics:
    """Metrics for an integration."""
    integration_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limit_hits: int = 0
    average_response_time: float = 0.0
    last_request: Optional[datetime] = None
    last_error: Optional[str] = None
    calculated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExternalRequest:
    """Request to external system."""
    request_id: str
    integration_id: str
    endpoint: str
    method: str = "GET"
    params: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    priority: int = 1  # 1=low, 5=high
    timeout_seconds: int = 30
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExternalResponse:
    """Response from external system."""
    request_id: str
    integration_id: str
    status_code: int
    data: Any
    format: DataFormat
    response_time: float  # seconds
    headers: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    received_at: datetime = field(default_factory=datetime.now)


@dataclass
class CachedData:
    """Cached external data."""
    cache_key: str
    integration_id: str
    endpoint: str
    params_hash: str
    data: Any
    format: DataFormat
    ttl: int  # seconds
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 1


class ExternalIntegrationLayer:
    """
    External Integration Layer.
    Manages connections to external legal systems with rate limiting, caching, and error handling.
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize External Integration Layer.
        
        Args:
            config_dir: Directory for configuration files
        """
        self.config_dir = config_dir or "config/integrations"
        
        # Storage
        self.integrations: Dict[str, IntegrationConfig] = {}
        self.integration_metrics: Dict[str, IntegrationMetrics] = {}
        self.cache: Dict[str, CachedData] = {}
        
        # Request tracking
        self.request_queue: List[ExternalRequest] = []
        self.request_history: Dict[str, ExternalResponse] = {}
        
        # Rate limiting
        self.rate_limits: Dict[str, Dict[str, Any]] = {}  # integration_id -> rate limit data
        
        # Statistics
        self.stats = {
            "total_integrations": 0,
            "active_integrations": 0,
            "total_requests": 0,
            "cached_responses": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "rate_limit_exceeded": 0
        }
        
        # Load configurations
        self._load_integration_configs()
        
        logger.info("Initialized External Integration Layer")
    
    def _load_integration_configs(self):
        """Load integration configurations."""
        # Create config directory if it doesn't exist
        config_path = Path(self.config_dir)
        config_path.mkdir(parents=True, exist_ok=True)
        
        # Load default configurations
        default_configs = self._get_default_configs()
        
        for config in default_configs:
            self.add_integration(config)
        
        logger.info(f"Loaded {len(self.integrations)} integration configurations")
    
    def _get_default_configs(self) -> List[IntegrationConfig]:
        """Get default integration configurations."""
        return [
            # PACER integration (mock - would require actual PACER credentials)
            IntegrationConfig(
                integration_id="pacer_default",
                integration_type=IntegrationType.PACER,
                base_url="https://pacer.uscourts.gov",
                rate_limit=50,  # PACER has strict rate limits
                timeout_seconds=60,
                enabled=True
            ),
            
            # SEC EDGAR integration
            IntegrationConfig(
                integration_id="sec_edgar_default",
                integration_type=IntegrationType.SEC_EDGAR,
                base_url="https://www.sec.gov/edgar",
                rate_limit=10,  # SEC recommends 10 requests per second
                timeout_seconds=30,
                enabled=True
            ),
            
            # USPTO integration
            IntegrationConfig(
                integration_id="uspto_default",
                integration_type=IntegrationType.USPTO,
                base_url="https://developer.uspto.gov",
                rate_limit=1000,
                timeout_seconds=30,
                enabled=True
            ),
            
            # CourtListener integration (requires API key)
            IntegrationConfig(
                integration_id="court_listener_default",
                integration_type=IntegrationType.COURT_LISTENER,
                base_url="https://www.courtlistener.com/api",
                rate_limit=100,
                timeout_seconds=30,
                enabled=True
            ),
            
            # Open States integration
            IntegrationConfig(
                integration_id="open_states_default",
                integration_type=IntegrationType.OPEN_STATES,
                base_url="https://v3.openstates.org",
                rate_limit=5000,
                timeout_seconds=30,
                enabled=True
            )
        ]
    
    def add_integration(self, config: IntegrationConfig) -> bool:
        """
        Add a new integration configuration.
        
        Args:
            config: Integration configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate ID if not provided
            if not config.integration_id:
                config.integration_id = f"int_{uuid.uuid4().hex[:16]}"
            
            # Check if already exists
            if config.integration_id in self.integrations:
                logger.warning(f"Integration {config.integration_id} already exists, updating")
                return self.update_integration(config.integration_id, config)
            
            # Store configuration
            self.integrations[config.integration_id] = config
            
            # Initialize metrics
            self.integration_metrics[config.integration_id] = IntegrationMetrics(
                integration_id=config.integration_id
            )
            
            # Initialize rate limiting
            self.rate_limits[config.integration_id] = {
                "requests_this_hour": 0,
                "last_reset": datetime.now(),
                "limit": config.rate_limit
            }
            
            # Update statistics
            self.stats["total_integrations"] += 1
            if config.enabled:
                self.stats["active_integrations"] += 1
            
            # Save configuration to file
            self._save_integration_config(config)
            
            logger.info(f"Added integration {config.integration_id}: {config.integration_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding integration: {str(e)}")
            return False
    
    def update_integration(self, integration_id: str, config: IntegrationConfig) -> bool:
        """
        Update an existing integration configuration.
        
        Args:
            integration_id: Integration ID
            config: Updated configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if integration_id not in self.integrations:
                logger.error(f"Integration {integration_id} not found")
                return False
            
            old_config = self.integrations[integration_id]
            
            # Update configuration
            config.updated_at = datetime.now()
            self.integrations[integration_id] = config
            
            # Update rate limit if changed
            if config.rate_limit != old_config.rate_limit:
                self.rate_limits[integration_id]["limit"] = config.rate_limit
            
            # Update statistics if enabled status changed
            if config.enabled != old_config.enabled:
                if config.enabled:
                    self.stats["active_integrations"] += 1
                else:
                    self.stats["active_integrations"] -= 1
            
            # Save updated configuration
            self._save_integration_config(config)
            
            logger.info(f"Updated integration {integration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating integration: {str(e)}")
            return False
    
    def remove_integration(self, integration_id: str) -> bool:
        """
        Remove an integration configuration.
        
        Args:
            integration_id: Integration ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if integration_id not in self.integrations:
                logger.error(f"Integration {integration_id} not found")
                return False
            
            config = self.integrations[integration_id]
            
            # Remove from storage
            del self.integrations[integration_id]
            
            if integration_id in self.integration_metrics:
                del self.integration_metrics[integration_id]
            
            if integration_id in self.rate_limits:
                del self.rate_limits[integration_id]
            
            # Update statistics
            self.stats["total_integrations"] -= 1
            if config.enabled:
                self.stats["active_integrations"] -= 1
            
            # Delete configuration file
            config_file = Path(self.config_dir) / f"{integration_id}.json"
            if config_file.exists():
                config_file.unlink()
            
            logger.info(f"Removed integration {integration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing integration: {str(e)}")
            return False
    
    def make_request(self, integration_id: str, endpoint: str, 
                    method: str = "GET", params: Optional[Dict[str, Any]] = None,
                    headers: Optional[Dict[str, str]] = None,
                    body: Optional[Dict[str, Any]] = None,
                    priority: int = 1,
                    use_cache: bool = True) -> Optional[ExternalResponse]:
        """
        Make a request to an external system.
        
        Args:
            integration_id: Integration ID
            endpoint: API endpoint
            method: HTTP method
            params: Query parameters
            headers: HTTP headers
            body: Request body
            priority: Request priority (1-5)
            use_cache: Whether to use cached responses
            
        Returns:
            External response or None if failed
        """
        try:
            # Check if integration exists and is enabled
            if integration_id not in self.integrations:
                logger.error(f"Integration {integration_id} not found")
                return None
            
            config = self.integrations[integration_id]
            
            if not config.enabled:
                logger.error(f"Integration {integration_id} is disabled")
                return None
            
            # Check rate limiting
            if not self._check_rate_limit(integration_id):
                logger.warning(f"Rate limit exceeded for {integration_id}")
                self.stats["rate_limit_exceeded"] += 1
                return None
            
            # Check cache first
            cache_key = None
            if use_cache and config.cache_enabled:
                cache_key = self._generate_cache_key(integration_id, endpoint, params, method, body)
                cached_data = self._get_cached_data(cache_key)
                
                if cached_data:
                    # Check if cache is still valid
                    if self._is_cache_valid(cached_data):
                        logger.info(f"Cache hit for {endpoint}")
                        self.stats["cache_hits"] += 1
                        
                        # Update cache access info
                        cached_data.accessed_at = datetime.now()
                        cached_data.access_count += 1
                        self.cache[cache_key] = cached_data
                        
                        # Create response from cache
                        return ExternalResponse(
                            request_id=f"cached_{uuid.uuid4().hex[:8]}",
                            integration_id=integration_id,
                            status_code=200,
                            data=cached_data.data,
                            format=cached_data.format,
                            response_time=0.001,  # Very fast from cache
                            headers={"X-Cache": "HIT"}
                        )
                    else:
                        # Cache expired, remove it
                        del self.cache[cache_key]
                        self.stats["cached_responses"] -= 1
            
            self.stats["cache_misses"] += 1
            
            # Create request
            request_id = f"req_{uuid.uuid4().hex[:16]}"
            
            request = ExternalRequest(
                request_id=request_id,
                integration_id=integration_id,
                endpoint=endpoint,
                method=method,
                params=params or {},
                headers=headers or {},
                body=body,
                priority=priority,
                timeout_seconds=config.timeout_seconds
            )
            
            # Make the request
            response = self._execute_request(request, config)
            
            # Update metrics
            self._update_metrics(integration_id, response)
            
            # Cache the response if successful
            if (use_cache and config.cache_enabled and 
                response.status_code == 200 and cache_key):
                self._cache_response(cache_key, integration_id, endpoint, 
                                   params or {}, method, body or {}, 
                                   response.data, response.format, config.cache_ttl)
            
            # Store in history
            self.request_history[request_id] = response
            
            self.stats["total_requests"] += 1
            
            return response
            
        except Exception as e:
            logger.error(f"Error making request: {str(e)}")
            
            # Create error response
            return ExternalResponse(
                request_id=f"error_{uuid.uuid4().hex[:8]}",
                integration_id=integration_id,
                status_code=500,
                data={"error": str(e)},
                format=DataFormat.JSON,
                response_time=0.0,
                errors=[str(e)]
            )
    
    def batch_request(self, requests: List[Dict[str, Any]]) -> List[Optional[ExternalResponse]]:
        """
        Make multiple requests in batch.
        
        Args:
            requests: List of request specifications
            
        Returns:
            List of responses
        """
        responses = []
        
        for req_spec in requests:
            response = self.make_request(
                integration_id=req_spec.get("integration_id"),
                endpoint=req_spec.get("endpoint", ""),
                method=req_spec.get("method", "GET"),
                params=req_spec.get("params"),
                headers=req_spec.get("headers"),
                body=req_spec.get("body"),
                priority=req_spec.get("priority", 1),
                use_cache=req_spec.get("use_cache", True)
            )
            
            responses.append(response)
        
        return responses
    
    def query_pacer(self, case_number: Optional[str] = None, 
                   party_name: Optional[str] = None,
                   court: Optional[str] = None,
                   date_range: Optional[Tuple[datetime, datetime]] = None) -> Optional[ExternalResponse]:
        """
        Query PACER for court records.
        
        Args:
            case_number: Case number to search
            party_name: Party name to search
            court: Court jurisdiction
            date_range: Date range for cases
            
        Returns:
            PACER response
        """
        # Find PACER integration
        pacer_id = None
        for int_id, config in self.integrations.items():
            if config.integration_type == IntegrationType.PACER and config.enabled:
                pacer_id = int_id
                break
        
        if not pacer_id:
            logger.error("No active PACER integration found")
            return None
        
        # Build PACER query
        params = {}
        if case_number:
            params["case_number"] = case_number
        if party_name:
            params["party_name"] = party_name
        if court:
            params["court"] = court
        if date_range:
            params["from_date"] = date_range[0].strftime("%Y-%m-%d")
            params["to_date"] = date_range[1].strftime("%Y-%m-%d")
        
        # Make request
        return self.make_request(
            integration_id=pacer_id,
            endpoint="/search/cases",
            method="GET",
            params=params,
            priority=3  # Medium priority
        )
    
    def query_sec_edgar(self, cik: Optional[str] = None,
                       company_name: Optional[str] = None,
                       form_type: Optional[str] = None,
                       filing_date: Optional[datetime] = None) -> Optional[ExternalResponse]:
        """
        Query SEC EDGAR for company filings.
        
        Args:
            cik: Central Index Key
            company_name: Company name
            form_type: Form type (10-K, 10-Q, etc.)
            filing_date: Filing date
            
        Returns:
            SEC EDGAR response
        """
        # Find SEC EDGAR integration
        sec_id = None
        for int_id, config in self.integrations.items():
            if config.integration_type == IntegrationType.SEC_EDGAR and config.enabled:
                sec_id = int_id
                break
        
        if not sec_id:
            logger.error("No active SEC EDGAR integration found")
            return None
        
        # Build SEC EDGAR query
        params = {}
        if cik:
            params["cik"] = cik
        if company_name:
            params["company"] = company_name
        if form_type:
            params["type"] = form_type
        if filing_date:
            params["date"] = filing_date.strftime("%Y%m%d")
        
        # Make request
        return self.make_request(
            integration_id=sec_id,
            endpoint="/search",
            method="GET",
            params=params,
            priority=2  # Lower priority (SEC data is less time-sensitive)
        )
    
    def query_uspto(self, patent_number: Optional[str] = None,
                   application_number: Optional[str] = None,
                   inventor_name: Optional[str] = None,
                   assignee_name: Optional[str] = None) -> Optional[ExternalResponse]:
        """
        Query USPTO for patent/trademark information.
        
        Args:
            patent_number: Patent number
            application_number: Application number
            inventor_name: Inventor name
            assignee_name: Assignee name
            
        Returns:
            USPTO response
        """
        # Find USPTO integration
        uspto_id = None
        for int_id, config in self.integrations.items():
            if config.integration_type == IntegrationType.USPTO and config.enabled:
                uspto_id = int_id
                break
        
        if not uspto_id:
            logger.error("No active USPTO integration found")
            return None
        
        # Build USPTO query
        params = {}
        if patent_number:
            params["patent_number"] = patent_number
        if application_number:
            params["application_number"] = application_number
        if inventor_name:
            params["inventor_name"] = inventor_name
        if assignee_name:
            params["assignee_name"] = assignee_name
        
        # Make request
        return self.make_request(
            integration_id=uspto_id,
            endpoint="/patents",
            method="GET",
            params=params,
            priority=3
        )
    
    def query_court_listener(self, citation: Optional[str] = None,
                           case_name: Optional[str] = None,
                           court: Optional[str] = None,
                           judge: Optional[str] = None) -> Optional[ExternalResponse]:
        """
        Query CourtListener for case law.
        
        Args:
            citation: Legal citation
            case_name: Case name
            court: Court
            judge: Judge name
            
        Returns:
            CourtListener response
        """
        # Find CourtListener integration
        cl_id = None
        for int_id, config in self.integrations.items():
            if config.integration_type == IntegrationType.COURT_LISTENER and config.enabled:
                cl_id = int_id
                break
        
        if not cl_id:
            logger.error("No active CourtListener integration found")
            return None
        
        # Build CourtListener query
        params = {}
        if citation:
            params["citation"] = citation
        if case_name:
            params["case_name"] = case_name
        if court:
            params["court"] = court
        if judge:
            params["judge"] = judge
        
        # Make request
        return self.make_request(
            integration_id=cl_id,
            endpoint="/rest/v3/search",
            method="GET",
            params=params,
            priority=4  # High priority for case law
        )
    
    def get_integration_status(self, integration_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an integration."""
        if integration_id not in self.integrations:
            return None
        
        config = self.integrations[integration_id]
        metrics = self.integration_metrics.get(integration_id)
        
        # Check if integration is responding
        status = IntegrationStatus.ACTIVE
        last_error = metrics.last_error if metrics else None
        
        if last_error and "rate limit" in last_error.lower():
            status = IntegrationStatus.RATE_LIMITED
        elif last_error:
            status = IntegrationStatus.ERROR
        
        return {
            "integration_id": integration_id,
            "type": config.integration_type.value,
            "status": status.value,
            "enabled": config.enabled,
            "base_url": config.base_url,
            "metrics": self._metrics_to_dict(metrics) if metrics else {},
            "rate_limit": self.rate_limits.get(integration_id, {}),
            "last_updated": config.updated_at.isoformat()
        }
    
    def get_all_integrations_status(self) -> List[Dict[str, Any]]:
        """Get status of all integrations."""
        status_list = []
        
        for integration_id in self.integrations:
            status = self.get_integration_status(integration_id)
            if status:
                status_list.append(status)
        
        return status_list
    
    def clear_cache(self, integration_id: Optional[str] = None):
        """
        Clear cache for an integration or all integrations.
        
        Args:
            integration_id: Integration ID (clear all if None)
        """
        if integration_id:
            # Clear cache for specific integration
            keys_to_remove = []
            for key, cached_data in self.cache.items():
                if cached_data.integration_id == integration_id:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
            
            removed_count = len(keys_to_remove)
            self.stats["cached_responses"] -= removed_count
            
            logger.info(f"Cleared {removed_count} cached responses for {integration_id}")
        else:
            # Clear all cache
            removed_count = len(self.cache)
            self.cache.clear()
            self.stats["cached_responses"] = 0
            
            logger.info(f"Cleared all {removed_count} cached responses")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get integration layer statistics."""
        # Calculate cache hit rate
        total_cache_access = self.stats["cache_hits"] + self.stats["cache_misses"]
        cache_hit_rate = (self.stats["cache_hits"] / total_cache_access * 100) if total_cache_access > 0 else 0
        
        # Calculate success rate
        total_requests = self.stats["total_requests"]
        successful_requests = sum(m.successful_requests for m in self.integration_metrics.values())
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 100
        
        return {
            "statistics": {
                **self.stats,
                "cache_hit_rate": cache_hit_rate,
                "success_rate": success_rate,
                "cache_size": len(self.cache),
                "request_history_size": len(self.request_history)
            },
            "integrations": {
                "total": self.stats["total_integrations"],
                "active": self.stats["active_integrations"],
                "by_type": self._count_integrations_by_type()
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def _check_rate_limit(self, integration_id: str) -> bool:
        """Check if request is within rate limit."""
        if integration_id not in self.rate_limits:
            return True
        
        rate_data = self.rate_limits[integration_id]
        config = self.integrations[integration_id]
        
        # Reset counter if hour has passed
        now = datetime.now()
        if (now - rate_data["last_reset"]).total_seconds() >= 3600:
            rate_data["requests_this_hour"] = 0
            rate_data["last_reset"] = now
        
        # Check if within limit
        if rate_data["requests_this_hour"] >= config.rate_limit:
            return False
        
        # Increment counter
        rate_data["requests_this_hour"] += 1
        return True
    
    def _generate_cache_key(self, integration_id: str, endpoint: str, 
                           params: Dict[str, Any], method: str, body: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for request."""
        # Create string representation of request
        request_str = f"{integration_id}:{endpoint}:{method}:"
        
        # Add params
        if params:
            sorted_params = sorted(params.items())
            request_str += json.dumps(sorted_params, sort_keys=True)
        
        # Add body if present
        if body:
            request_str += ":" + json.dumps(body, sort_keys=True)
        
        # Create hash
        return hashlib.md5(request_str.encode()).hexdigest()
    
    def _get_cached_data(self, cache_key: str) -> Optional[CachedData]:
        """Get cached data for key."""
        return self.cache.get(cache_key)
    
    def _is_cache_valid(self, cached_data: CachedData) -> bool:
        """Check if cached data is still valid."""
        now = datetime.now()
        age = (now - cached_data.created_at).total_seconds()
        return age < cached_data.ttl
    
    def _cache_response(self, cache_key: str, integration_id: str, endpoint: str,
                       params: Dict[str, Any], method: str, body: Dict[str, Any],
                       data: Any, format: DataFormat, ttl: int):
        """Cache a response."""
        # Create params hash for reference
        params_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()
        
        cached_data = CachedData(
            cache_key=cache_key,
            integration_id=integration_id,
            endpoint=endpoint,
            params_hash=params_hash,
            data=data,
            format=format,
            ttl=ttl
        )
        
        self.cache[cache_key] = cached_data
        self.stats["cached_responses"] += 1
    
    def _execute_request(self, request: ExternalRequest, config: IntegrationConfig) -> ExternalResponse:
        """Execute a request to external system."""
        start_time = time.time()
        
        try:
            # Build full URL
            url = f"{config.base_url.rstrip('/')}/{request.endpoint.lstrip('/')}"
            
            # Add query parameters
            if request.params:
                # For mock implementation, just log the request
                logger.info(f"Mock request to {url} with params: {request.params}")
            else:
                logger.info(f"Mock request to {url}")
            
            # Mock response based on integration type
            mock_data = self._generate_mock_response(config.integration_type, request)
            
            response_time = time.time() - start_time
            
            return ExternalResponse(
                request_id=request.request_id,
                integration_id=request.integration_id,
                status_code=200,
                data=mock_data,
                format=DataFormat.JSON,
                response_time=response_time,
                headers={"X-Mock": "true"}
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            
            return ExternalResponse(
                request_id=request.request_id,
                integration_id=request.integration_id,
                status_code=500,
                data={"error": str(e)},
                format=DataFormat.JSON,
                response_time=response_time,
                errors=[str(e)]
            )
    
    def _generate_mock_response(self, integration_type: IntegrationType, 
                               request: ExternalRequest) -> Dict[str, Any]:
        """Generate mock response for testing."""
        if integration_type == IntegrationType.PACER:
            return self._mock_pacer_response(request)
        elif integration_type == IntegrationType.SEC_EDGAR:
            return self._mock_sec_edgar_response(request)
        elif integration_type == IntegrationType.USPTO:
            return self._mock_uspto_response(request)
        elif integration_type == IntegrationType.COURT_LISTENER:
            return self._mock_court_listener_response(request)
        else:
            return self._mock_generic_response(request)
    
    def _mock_pacer_response(self, request: ExternalRequest) -> Dict[str, Any]:
        """Generate mock PACER response."""
        case_number = request.params.get("case_number", "1:23-cv-45678")
        party_name = request.params.get("party_name", "Smith")
        
        return {
            "status": "success",
            "data": {
                "cases": [
                    {
                        "case_number": case_number,
                        "case_name": f"{party_name} v. Jones",
                        "court": "US District Court",
                        "filed_date": "2023-05-15",
                        "status": "pending",
                        "parties": [
                            {"name": party_name, "role": "plaintiff"},
                            {"name": "Jones Corporation", "role": "defendant"}
                        ],
                        "docket_entries": [
                            {"date": "2023-05-15", "description": "Complaint filed"},
                            {"date": "2023-06-01", "description": "Answer filed"},
                            {"date": "2023-07-15", "description": "Motion to dismiss"}
                        ]
                    }
                ],
                "count": 1,
                "query": request.params
            },
            "metadata": {
                "source": "PACER",
                "timestamp": datetime.now().isoformat(),
                "mock": True
            }
        }
    
    def _mock_sec_edgar_response(self, request: ExternalRequest) -> Dict[str, Any]:
        """Generate mock SEC EDGAR response."""
        cik = request.params.get("cik", "0001234567")
        company_name = request.params.get("company", "Example Corporation")
        
        return {
            "status": "success",
            "data": {
                "company": {
                    "cik": cik,
                    "name": company_name,
                    "sic": "7372",
                    "state": "DE"
                },
                "filings": [
                    {
                        "form": "10-K",
                        "filing_date": "2024-03-15",
                        "period": "2023-12-31",
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/000123456724000123/0001234567-24-000123-index.htm",
                        "size": "5.2MB"
                    },
                    {
                        "form": "10-Q",
                        "filing_date": "2024-02-14",
                        "period": "2023-09-30",
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/000123456724000122/0001234567-24-000122-index.htm",
                        "size": "2.1MB"
                    },
                    {
                        "form": "8-K",
                        "filing_date": "2024-01-25",
                        "description": "Current report",
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/000123456724000121/0001234567-24-000121-index.htm",
                        "size": "0.5MB"
                    }
                ],
                "count": 3
            },
            "metadata": {
                "source": "SEC EDGAR",
                "timestamp": datetime.now().isoformat(),
                "mock": True
            }
        }
    
    def _mock_uspto_response(self, request: ExternalRequest) -> Dict[str, Any]:
        """Generate mock USPTO response."""
        patent_number = request.params.get("patent_number", "US12345678B2")
        
        return {
            "status": "success",
            "data": {
                "patent": {
                    "number": patent_number,
                    "title": "System and Method for Automated Legal Analysis",
                    "inventors": ["John Doe", "Jane Smith"],
                    "assignee": "LegalTech Inc.",
                    "filing_date": "2022-06-15",
                    "issue_date": "2023-12-01",
                    "abstract": "A system for automated legal analysis using artificial intelligence...",
                    "claims": [
                        "1. A system for legal analysis comprising...",
                        "2. The system of claim 1, further comprising..."
                    ]
                },
                "status": "active",
                "maintenance_fees": {
                    "next_due": "2025-12-01",
                    "amount": 2200.00
                }
            },
            "metadata": {
                "source": "USPTO",
                "timestamp": datetime.now().isoformat(),
                "mock": True
            }
        }
    
    def _mock_court_listener_response(self, request: ExternalRequest) -> Dict[str, Any]:
        """Generate mock CourtListener response."""
        citation = request.params.get("citation", "123 F.3d 456")
        
        return {
            "status": "success",
            "data": {
                "cases": [
                    {
                        "id": 123456,
                        "name": "Smith v. Jones",
                        "citation": citation,
                        "court": "United States Court of Appeals",
                        "date_decided": "2023-08-15",
                        "docket_number": "22-1234",
                        "precedential_status": "Published",
                        "jurisdiction": "Federal",
                        "opinion": {
                            "type": "Majority",
                            "author": "Judge Johnson",
                            "text": "This case presents the question of whether..."
                        },
                        "cited_by": 15,
                        "cites": ["456 F.3d 789", "789 F.3d 012"]
                    }
                ],
                "count": 1,
                "next": None
            },
            "metadata": {
                "source": "CourtListener",
                "timestamp": datetime.now().isoformat(),
                "mock": True
            }
        }
    
    def _mock_generic_response(self, request: ExternalRequest) -> Dict[str, Any]:
        """Generate mock generic response."""
        return {
            "status": "success",
            "data": {
                "message": "Mock response from external system",
                "endpoint": request.endpoint,
                "params": request.params,
                "timestamp": datetime.now().isoformat()
            },
            "metadata": {
                "source": "External System",
                "mock": True
            }
        }
    
    def _update_metrics(self, integration_id: str, response: ExternalResponse):
        """Update metrics for an integration."""
        if integration_id not in self.integration_metrics:
            return
        
        metrics = self.integration_metrics[integration_id]
        
        metrics.total_requests += 1
        metrics.last_request = datetime.now()
        
        if response.status_code == 200:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1
            metrics.last_error = response.errors[0] if response.errors else f"HTTP {response.status_code}"
        
        # Update average response time
        if metrics.total_requests == 1:
            metrics.average_response_time = response.response_time
        else:
            # Weighted average
            metrics.average_response_time = (
                (metrics.average_response_time * (metrics.total_requests - 1) + response.response_time) 
                / metrics.total_requests
            )
        
        metrics.calculated_at = datetime.now()
    
    def _save_integration_config(self, config: IntegrationConfig):
        """Save integration configuration to file."""
        try:
            config_file = Path(self.config_dir) / f"{config.integration_id}.json"
            
            config_dict = {
                "integration_id": config.integration_id,
                "integration_type": config.integration_type.value,
                "base_url": config.base_url,
                "api_key": config.api_key,
                "username": config.username,
                "password": config.password,  # Note: In production, encrypt this
                "rate_limit": config.rate_limit,
                "timeout_seconds": config.timeout_seconds,
                "retry_attempts": config.retry_attempts,
                "retry_delay": config.retry_delay,
                "cache_enabled": config.cache_enabled,
                "cache_ttl": config.cache_ttl,
                "enabled": config.enabled,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error saving integration config: {str(e)}")
    
    def _metrics_to_dict(self, metrics: IntegrationMetrics) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "rate_limit_hits": metrics.rate_limit_hits,
            "average_response_time": metrics.average_response_time,
            "last_request": metrics.last_request.isoformat() if metrics.last_request else None,
            "last_error": metrics.last_error,
            "calculated_at": metrics.calculated_at.isoformat()
        }
    
    def _count_integrations_by_type(self) -> Dict[str, int]:
        """Count integrations by type."""
        counts = {}
        
        for config in self.integrations.values():
            type_str = config.integration_type.value
            counts[type_str] = counts.get(type_str, 0) + 1
        
        return counts


def test_external_integration():
    """Test function for External Integration Layer."""
    print("Testing External Integration Layer...")
    
    # Create integration layer
    integration_layer = ExternalIntegrationLayer()
    
    # Test 1: Get integration status
    print("\n1. Testing integration status...")
    
    status_list = integration_layer.get_all_integrations_status()
    print(f"Loaded {len(status_list)} integrations")
    
    for status in status_list[:3]:  # Show first 3
        print(f"  {status['type']}: {status['status']} ({'enabled' if status['enabled'] else 'disabled'})")
    
    # Test 2: Query PACER
    print("\n2. Testing PACER query...")
    
    response = integration_layer.query_pacer(
        case_number="1:23-cv-45678",
        party_name="Smith"
    )
    
    if response and response.status_code == 200:
        data = response.data
        print(f"PACER query successful")
        print(f"  Found {data['data']['count']} case(s)")
        if data['data']['cases']:
            case = data['data']['cases'][0]
            print(f"  Case: {case['case_name']}")
            print(f"  Court: {case['court']}")
            print(f"  Status: {case['status']}")
    else:
        print(f"PACER query failed: {response.errors if response else 'No response'}")
    
    # Test 3: Query SEC EDGAR
    print("\n3. Testing SEC EDGAR query...")
    
    response = integration_layer.query_sec_edgar(
        company_name="Example Corporation",
        form_type="10-K"
    )
    
    if response and response.status_code == 200:
        data = response.data
        print(f"SEC EDGAR query successful")
        print(f"  Company: {data['data']['company']['name']}")
        print(f"  CIK: {data['data']['company']['cik']}")
        print(f"  Filings found: {len(data['data']['filings'])}")
    else:
        print(f"SEC EDGAR query failed")
    
    # Test 4: Query USPTO
    print("\n4. Testing USPTO query...")
    
    response = integration_layer.query_uspto(
        patent_number="US12345678B2",
        inventor_name="John Doe"
    )
    
    if response and response.status_code == 200:
        data = response.data
        print(f"USPTO query successful")
        print(f"  Patent: {data['data']['patent']['number']}")
        print(f"  Title: {data['data']['patent']['title']}")
        print(f"  Inventors: {', '.join(data['data']['patent']['inventors'])}")
    else:
        print(f"USPTO query failed")
    
    # Test 5: Test caching
    print("\n5. Testing caching...")
    
    # First request (should miss cache)
    response1 = integration_layer.query_pacer(case_number="test-001")
    print(f"First request: {'Cache miss' if response1.headers.get('X-Cache') != 'HIT' else 'Cache hit'}")
    
    # Second request (should hit cache)
    response2 = integration_layer.query_pacer(case_number="test-001")
    print(f"Second request: {'Cache miss' if response2.headers.get('X-Cache') != 'HIT' else 'Cache hit'}")
    
    # Test 6: Get statistics
    print("\n6. Testing statistics...")
    
    stats = integration_layer.get_statistics()
    print(f"Statistics:")
    print(f"  Total requests: {stats['statistics']['total_requests']}")
    print(f"  Cache hits: {stats['statistics']['cache_hits']}")
    print(f"  Cache misses: {stats['statistics']['cache_misses']}")
    print(f"  Cache hit rate: {stats['statistics']['cache_hit_rate']:.1f}%")
    print(f"  Active integrations: {stats['integrations']['active']}")
    
    # Test 7: Clear cache
    print("\n7. Testing cache clearing...")
    
    integration_layer.clear_cache()
    print("Cache cleared")
    
    # Get updated stats
    stats = integration_layer.get_statistics()
    print(f"Cache size after clearing: {stats['statistics']['cache_size']}")
    
    print("\nExternal Integration Layer test completed successfully!")


if __name__ == "__main__":
    test_external_integration()