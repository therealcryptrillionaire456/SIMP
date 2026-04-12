"""
Query processor for handling user queries and coordinating search and extraction.
"""

import uuid
import time
from datetime import datetime
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import QueryRequest, QueryResponse, SearchResult, ExtractedContent, FetcherType
from .search_providers import get_search_provider
from .scrapling_extractor import extract_multiple_urls
from .config import config


class QueryProcessor:
    """Process user queries by searching and extracting content."""
    
    def __init__(self, search_provider_name: str = "duckduckgo"):
        self.search_provider = get_search_provider(search_provider_name)
        self.active_requests = {}
    
    def process_query(self, request: QueryRequest) -> QueryResponse:
        """
        Process a query request.
        
        Steps:
        1. Search for relevant web pages
        2. Extract content from top results
        3. Return structured response
        """
        request_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow().isoformat()
        
        # Create initial response
        response = QueryResponse(
            query=request.query,
            request_id=request_id,
            submitted_at=submitted_at,
            status="searching"
        )
        
        self.active_requests[request_id] = response
        
        try:
            # Step 1: Search for relevant pages
            search_results = self.search_provider.search(
                query=request.query,
                max_results=request.max_results
            )
            response.search_results = search_results
            response.status = "extracting"
            
            # Step 2: Extract content from search results
            urls = [result.url for result in search_results]
            extracted_contents = extract_multiple_urls(
                urls=urls,
                fetcher_type=request.fetcher_type
            )
            
            # Match extracted content with search results
            for i, content in enumerate(extracted_contents):
                if i < len(search_results):
                    # Add metadata from search result
                    content.metadata.update(search_results[i].metadata)
                    content.metadata["relevance_score"] = search_results[i].relevance_score
            
            response.extracted_content = extracted_contents
            response.status = "completed"
            
        except Exception as e:
            response.status = "failed"
            response.error = str(e)
        
        response.completed_at = datetime.utcnow().isoformat()
        
        # Clean up
        if request_id in self.active_requests:
            del self.active_requests[request_id]
        
        return response
    
    def process_query_async(self, request: QueryRequest) -> str:
        """
        Start processing a query asynchronously and return request ID.
        
        Returns:
            Request ID that can be used to check status
        """
        request_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow().isoformat()
        
        # Create initial response
        response = QueryResponse(
            query=request.query,
            request_id=request_id,
            submitted_at=submitted_at,
            status="queued"
        )
        
        self.active_requests[request_id] = response
        
        # Start processing in background thread
        import threading
        thread = threading.Thread(
            target=self._process_in_background,
            args=(request_id, request),
            daemon=True
        )
        thread.start()
        
        return request_id
    
    def _process_in_background(self, request_id: str, request: QueryRequest):
        """Process query in background thread."""
        if request_id not in self.active_requests:
            return
        
        response = self.active_requests[request_id]
        
        try:
            # Update status
            response.status = "searching"
            
            # Search
            search_results = self.search_provider.search(
                query=request.query,
                max_results=request.max_results
            )
            response.search_results = search_results
            response.status = "extracting"
            
            # Extract content
            urls = [result.url for result in search_results]
            extracted_contents = extract_multiple_urls(
                urls=urls,
                fetcher_type=request.fetcher_type
            )
            
            # Match extracted content with search results
            for i, content in enumerate(extracted_contents):
                if i < len(search_results):
                    content.metadata.update(search_results[i].metadata)
                    content.metadata["relevance_score"] = search_results[i].relevance_score
            
            response.extracted_content = extracted_contents
            response.status = "completed"
            
        except Exception as e:
            response.status = "failed"
            response.error = str(e)
        
        response.completed_at = datetime.utcnow().isoformat()
    
    def get_request_status(self, request_id: str) -> Optional[QueryResponse]:
        """Get the status of a request by ID."""
        return self.active_requests.get(request_id)
    
    def get_all_requests(self) -> List[QueryResponse]:
        """Get all active and recent requests."""
        return list(self.active_requests.values())


# Global query processor instance
query_processor = QueryProcessor()