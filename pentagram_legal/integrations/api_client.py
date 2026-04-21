"""
API Client for External Integration Layer.
Handles HTTP requests, authentication, and response parsing for external APIs.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import logging
import time
import hashlib
from pathlib import Path

# Try to import requests, but provide fallback
try:
    import requests
    from requests.adapters import HTTPAdapter
    from requests.packages.urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("requests library not available, using mock HTTP client")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class APIClientConfig:
    """API client configuration."""
    base_url: str
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    auth_type: str = "api_key"  # api_key, basic, oauth2, none
    timeout: int = 30
    retry_attempts: int = 3
    retry_backoff: float = 1.5
    retry_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    rate_limit: int = 100  # requests per hour
    user_agent: str = "PentagramLegal/1.0.0"
    default_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class APIRequest:
    """API request specification."""
    method: str
    endpoint: str
    params: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    data: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None


@dataclass
class APIResponse:
    """API response."""
    status_code: int
    data: Any
    headers: Dict[str, str]
    elapsed: float  # seconds
    url: str
    error: Optional[str] = None


class APIClient:
    """
    Generic API client for external integrations.
    Handles HTTP requests with retries, rate limiting, and error handling.
    """
    
    def __init__(self, config: APIClientConfig):
        """
        Initialize API Client.
        
        Args:
            config: API client configuration
        """
        self.config = config
        self.session = None
        self.rate_limit_data = {
            "requests_this_hour": 0,
            "last_reset": datetime.now(),
            "limit": config.rate_limit
        }
        
        # Initialize session if requests is available
        if REQUESTS_AVAILABLE:
            self._init_session()
        
        logger.info(f"Initialized API Client for {config.base_url}")
    
    def _init_session(self):
        """Initialize HTTP session with retry configuration."""
        if not REQUESTS_AVAILABLE:
            return
        
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.retry_attempts,
            backoff_factor=self.config.retry_backoff,
            status_forcelist=self.config.retry_status_codes,
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
        )
        
        # Mount retry adapter
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        # Add custom headers
        if self.config.default_headers:
            self.session.headers.update(self.config.default_headers)
        
        # Add authentication
        self._setup_authentication()
    
    def _setup_authentication(self):
        """Setup authentication for the session."""
        if not self.session:
            return
        
        if self.config.auth_type == "api_key" and self.config.api_key:
            # API key authentication (usually in headers)
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.api_key}",
                "X-API-Key": self.config.api_key
            })
        
        elif self.config.auth_type == "basic" and self.config.username and self.config.password:
            # Basic authentication
            self.session.auth = (self.config.username, self.config.password)
        
        elif self.config.auth_type == "oauth2" and self.config.api_key:
            # OAuth2 authentication
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.api_key}"
            })
    
    def _check_rate_limit(self) -> bool:
        """Check if request is within rate limit."""
        now = datetime.now()
        
        # Reset counter if hour has passed
        if (now - self.rate_limit_data["last_reset"]).total_seconds() >= 3600:
            self.rate_limit_data["requests_this_hour"] = 0
            self.rate_limit_data["last_reset"] = now
        
        # Check if within limit
        if self.rate_limit_data["requests_this_hour"] >= self.config.rate_limit:
            return False
        
        # Increment counter
        self.rate_limit_data["requests_this_hour"] += 1
        return True
    
    def request(self, api_request: APIRequest) -> APIResponse:
        """
        Make an API request.
        
        Args:
            api_request: API request specification
            
        Returns:
            API response
        """
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning(f"Rate limit exceeded for {self.config.base_url}")
            return APIResponse(
                status_code=429,
                data={"error": "Rate limit exceeded"},
                headers={},
                elapsed=0.0,
                url=f"{self.config.base_url}/{api_request.endpoint}",
                error="Rate limit exceeded"
            )
        
        # Build URL
        url = f"{self.config.base_url.rstrip('/')}/{api_request.endpoint.lstrip('/')}"
        
        # Prepare headers
        headers = api_request.headers or {}
        
        # Prepare request data
        data = None
        json_data = None
        
        if api_request.data:
            data = api_request.data
        elif api_request.json_data:
            json_data = api_request.json_data
        
        # Set timeout
        timeout = api_request.timeout or self.config.timeout
        
        try:
            start_time = time.time()
            
            if REQUESTS_AVAILABLE and self.session:
                # Make actual HTTP request
                response = self.session.request(
                    method=api_request.method,
                    url=url,
                    params=api_request.params,
                    headers=headers,
                    data=data,
                    json=json_data,
                    timeout=timeout
                )
                
                elapsed = time.time() - start_time
                
                # Parse response
                try:
                    if response.headers.get('Content-Type', '').startswith('application/json'):
                        response_data = response.json()
                    else:
                        response_data = response.text
                except:
                    response_data = response.text
                
                return APIResponse(
                    status_code=response.status_code,
                    data=response_data,
                    headers=dict(response.headers),
                    elapsed=elapsed,
                    url=url
                )
            
            else:
                # Mock request (for testing or when requests is not available)
                elapsed = time.time() - start_time
                
                # Generate mock response
                mock_data = self._generate_mock_response(api_request)
                
                return APIResponse(
                    status_code=200,
                    data=mock_data,
                    headers={"X-Mock": "true"},
                    elapsed=elapsed,
                    url=url
                )
                
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0.0
            
            logger.error(f"API request error: {str(e)}")
            
            return APIResponse(
                status_code=500,
                data={"error": str(e)},
                headers={},
                elapsed=elapsed,
                url=url,
                error=str(e)
            )
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """
        Make GET request.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: HTTP headers
            
        Returns:
            API response
        """
        request = APIRequest(
            method="GET",
            endpoint=endpoint,
            params=params,
            headers=headers
        )
        
        return self.request(request)
    
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
             json_data: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """
        Make POST request.
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            headers: HTTP headers
            
        Returns:
            API response
        """
        request = APIRequest(
            method="POST",
            endpoint=endpoint,
            data=data,
            json_data=json_data,
            headers=headers
        )
        
        return self.request(request)
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
            json_data: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """
        Make PUT request.
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            headers: HTTP headers
            
        Returns:
            API response
        """
        request = APIRequest(
            method="PUT",
            endpoint=endpoint,
            data=data,
            json_data=json_data,
            headers=headers
        )
        
        return self.request(request)
    
    def delete(self, endpoint: str, headers: Optional[Dict[str, str]] = None) -> APIResponse:
        """
        Make DELETE request.
        
        Args:
            endpoint: API endpoint
            headers: HTTP headers
            
        Returns:
            API response
        """
        request = APIRequest(
            method="DELETE",
            endpoint=endpoint,
            headers=headers
        )
        
        return self.request(request)
    
    def _generate_mock_response(self, api_request: APIRequest) -> Dict[str, Any]:
        """Generate mock response for testing."""
        # Extract endpoint information
        endpoint = api_request.endpoint.lower()
        
        # Generate response based on endpoint
        if "search" in endpoint or "query" in endpoint:
            return {
                "status": "success",
                "data": {
                    "results": [
                        {"id": 1, "name": "Result 1", "type": "document"},
                        {"id": 2, "name": "Result 2", "type": "case"},
                        {"id": 3, "name": "Result 3", "type": "filing"}
                    ],
                    "count": 3,
                    "page": 1,
                    "total_pages": 1
                },
                "metadata": {
                    "source": self.config.base_url,
                    "endpoint": api_request.endpoint,
                    "timestamp": datetime.now().isoformat(),
                    "mock": True
                }
            }
        
        elif "cases" in endpoint or "docket" in endpoint:
            return {
                "status": "success",
                "data": {
                    "case": {
                        "id": "1:23-cv-45678",
                        "name": "Smith v. Jones",
                        "court": "US District Court",
                        "status": "pending",
                        "filed_date": "2023-05-15",
                        "parties": [
                            {"name": "John Smith", "role": "plaintiff"},
                            {"name": "Jones Corporation", "role": "defendant"}
                        ]
                    }
                },
                "metadata": {
                    "source": self.config.base_url,
                    "timestamp": datetime.now().isoformat(),
                    "mock": True
                }
            }
        
        elif "filings" in endpoint or "sec" in endpoint:
            return {
                "status": "success",
                "data": {
                    "filing": {
                        "cik": "0001234567",
                        "company": "Example Corporation",
                        "form": "10-K",
                        "filing_date": "2024-03-15",
                        "period": "2023-12-31"
                    }
                },
                "metadata": {
                    "source": self.config.base_url,
                    "timestamp": datetime.now().isoformat(),
                    "mock": True
                }
            }
        
        else:
            # Generic response
            return {
                "status": "success",
                "data": {
                    "message": "Mock API response",
                    "endpoint": api_request.endpoint,
                    "method": api_request.method,
                    "timestamp": datetime.now().isoformat()
                },
                "metadata": {
                    "source": self.config.base_url,
                    "mock": True
                }
            }
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        now = datetime.now()
        time_since_reset = (now - self.rate_limit_data["last_reset"]).total_seconds()
        time_until_reset = 3600 - time_since_reset
        
        return {
            "requests_this_hour": self.rate_limit_data["requests_this_hour"],
            "rate_limit": self.config.rate_limit,
            "remaining": max(0, self.config.rate_limit - self.rate_limit_data["requests_this_hour"]),
            "last_reset": self.rate_limit_data["last_reset"].isoformat(),
            "time_until_reset": max(0, time_until_reset),
            "utilization_percentage": (self.rate_limit_data["requests_this_hour"] / self.config.rate_limit * 100) if self.config.rate_limit > 0 else 0
        }
    
    def close(self):
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            self.session = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class PACERClient(APIClient):
    """Specialized client for PACER API."""
    
    def search_cases(self, case_number: Optional[str] = None,
                    party_name: Optional[str] = None,
                    court: Optional[str] = None,
                    date_from: Optional[datetime] = None,
                    date_to: Optional[datetime] = None,
                    page: int = 1,
                    page_size: int = 20) -> APIResponse:
        """
        Search for cases in PACER.
        
        Args:
            case_number: Case number
            party_name: Party name
            court: Court code
            date_from: Start date
            date_to: End date
            page: Page number
            page_size: Results per page
            
        Returns:
            API response
        """
        params = {
            "page": page,
            "page_size": page_size
        }
        
        if case_number:
            params["case_number"] = case_number
        if party_name:
            params["party_name"] = party_name
        if court:
            params["court"] = court
        if date_from:
            params["date_from"] = date_from.strftime("%Y-%m-%d")
        if date_to:
            params["date_to"] = date_to.strftime("%Y-%m-%d")
        
        return self.get("/search/cases", params=params)
    
    def get_case_docket(self, case_id: str) -> APIResponse:
        """
        Get docket for a specific case.
        
        Args:
            case_id: Case ID
            
        Returns:
            API response
        """
        return self.get(f"/cases/{case_id}/docket")
    
    def get_document(self, document_id: str) -> APIResponse:
        """
        Get a specific document.
        
        Args:
            document_id: Document ID
            
        Returns:
            API response
        """
        return self.get(f"/documents/{document_id}")


class SECEdgarClient(APIClient):
    """Specialized client for SEC EDGAR API."""
    
    def search_company(self, cik: Optional[str] = None,
                      company_name: Optional[str] = None,
                      sic: Optional[str] = None) -> APIResponse:
        """
        Search for company information.
        
        Args:
            cik: Central Index Key
            company_name: Company name
            sic: Standard Industrial Classification code
            
        Returns:
            API response
        """
        params = {}
        
        if cik:
            params["cik"] = cik
        if company_name:
            params["company"] = company_name
        if sic:
            params["sic"] = sic
        
        return self.get("/company", params=params)
    
    def get_filings(self, cik: str, form_type: Optional[str] = None,
                   date_from: Optional[datetime] = None,
                   date_to: Optional[datetime] = None) -> APIResponse:
        """
        Get filings for a company.
        
        Args:
            cik: Central Index Key
            form_type: Form type (10-K, 10-Q, etc.)
            date_from: Start date
            date_to: End date
            
        Returns:
            API response
        """
        params = {"cik": cik}
        
        if form_type:
            params["type"] = form_type
        if date_from:
            params["datebgn"] = date_from.strftime("%Y%m%d")
        if date_to:
            params["dateend"] = date_to.strftime("%Y%m%d")
        
        return self.get("/filings", params=params)
    
    def get_filing_text(self, accession_number: str) -> APIResponse:
        """
        Get full text of a filing.
        
        Args:
            accession_number: Filing accession number
            
        Returns:
            API response
        """
        return self.get(f"/files/{accession_number}")


class USPTOClient(APIClient):
    """Specialized client for USPTO API."""
    
    def search_patents(self, patent_number: Optional[str] = None,
                      application_number: Optional[str] = None,
                      inventor_name: Optional[str] = None,
                      assignee_name: Optional[str] = None,
                      title: Optional[str] = None) -> APIResponse:
        """
        Search for patents.
        
        Args:
            patent_number: Patent number
            application_number: Application number
            inventor_name: Inventor name
            assignee_name: Assignee name
            title: Patent title
            
        Returns:
            API response
        """
        params = {}
        
        if patent_number:
            params["patentNumber"] = patent_number
        if application_number:
            params["applicationNumber"] = application_number
        if inventor_name:
            params["inventorName"] = inventor_name
        if assignee_name:
            params["assigneeName"] = assignee_name
        if title:
            params["title"] = title
        
        return self.get("/patents", params=params)
    
    def get_patent(self, patent_id: str) -> APIResponse:
        """
        Get detailed patent information.
        
        Args:
            patent_id: Patent ID
            
        Returns:
            API response
        """
        return self.get(f"/patents/{patent_id}")
    
    def search_trademarks(self, mark: Optional[str] = None,
                         owner: Optional[str] = None,
                         serial_number: Optional[str] = None) -> APIResponse:
        """
        Search for trademarks.
        
        Args:
            mark: Trademark text
            owner: Owner name
            serial_number: Serial number
            
        Returns:
            API response
        """
        params = {}
        
        if mark:
            params["mark"] = mark
        if owner:
            params["owner"] = owner
        if serial_number:
            params["serialNumber"] = serial_number
        
        return self.get("/trademarks", params=params)


def test_api_client():
    """Test function for API Client."""
    print("Testing API Client...")
    
    # Test 1: Generic API client
    print("\n1. Testing generic API client...")
    
    config = APIClientConfig(
        base_url="https://api.example.com",
        api_key="test_key_123",
        rate_limit=100,
        timeout=30
    )
    
    client = APIClient(config)
    
    # Make a test request
    response = client.get("/test/endpoint", params={"query": "test"})
    
    print(f"Response status: {response.status_code}")
    print(f"Response time: {response.elapsed:.3f}s")
    print(f"Response data keys: {list(response.data.keys()) if isinstance(response.data, dict) else 'N/A'}")
    
    # Test rate limit status
    rate_status = client.get_rate_limit_status()
    print(f"Rate limit status: {rate_status['requests_this_hour']}/{rate_status['rate_limit']}")
    
    # Test 2: PACER client
    print("\n2. Testing PACER client...")
    
    pacer_config = APIClientConfig(
        base_url="https://pacer.uscourts.gov/api",
        auth_type="api_key",
        rate_limit=50
    )
    
    pacer_client = PACERClient(pacer_config)
    
    # Mock search
    response = pacer_client.search_cases(
        case_number="1:23-cv-45678",
        party_name="Smith"
    )
    
    print(f"PACER search response: {response.status_code}")
    if response.status_code == 200:
        print(f"Found {len(response.data['data']['results'])} results")
    
    # Test 3: SEC EDGAR client
    print("\n3. Testing SEC EDGAR client...")
    
    sec_config = APIClientConfig(
        base_url="https://www.sec.gov/edgar/api",
        rate_limit=10
    )
    
    sec_client = SECEdgarClient(sec_config)
    
    # Mock company search
    response = sec_client.search_company(company_name="Example Corp")
    
    print(f"SEC EDGAR search response: {response.status_code}")
    
    # Test 4: USPTO client
    print("\n4. Testing USPTO client...")
    
    uspto_config = APIClientConfig(
        base_url="https://developer.uspto.gov/api",
        auth_type="api_key",
        rate_limit=1000
    )
    
    uspto_client = USPTOClient(uspto_config)
    
    # Mock patent search
    response = uspto_client.search_patents(
        inventor_name="John Doe",
        title="Legal Analysis"
    )
    
    print(f"USPTO search response: {response.status_code}")
    
    # Close clients
    client.close()
    pacer_client.close()
    sec_client.close()
    uspto_client.close()
    
    print("\nAPI Client test completed successfully!")


if __name__ == "__main__":
    test_api_client()