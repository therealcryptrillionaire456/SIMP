"""
Tests for the Scrapling Query Tool.
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Add the tools directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.scrapling_query_app.models import (
    QueryRequest, QueryResponse, SearchResult, ExtractedContent,
    ExtractionStatus, FetcherType
)
from tools.scrapling_query_app.search_providers import (
    SearchProvider, MockSearchProvider, DuckDuckGoSearchProvider
)
from tools.scrapling_query_app.scrapling_extractor import ScraplingExtractor
from tools.scrapling_query_app.query_processor import QueryProcessor


class TestModels:
    """Test data models."""
    
    def test_query_request(self):
        """Test QueryRequest model."""
        request = QueryRequest(
            query="test query",
            max_results=5,
            fetcher_type=FetcherType.DYNAMIC,
            use_cache=True,
            metadata={"test": "data"}
        )
        
        assert request.query == "test query"
        assert request.max_results == 5
        assert request.fetcher_type == FetcherType.DYNAMIC
        assert request.use_cache is True
        assert request.metadata == {"test": "data"}
    
    def test_search_result(self):
        """Test SearchResult model."""
        result = SearchResult(
            url="https://example.com",
            title="Example Title",
            snippet="Example snippet text",
            relevance_score=0.85,
            source="test",
            metadata={"position": 1}
        )
        
        assert result.url == "https://example.com"
        assert result.title == "Example Title"
        assert result.snippet == "Example snippet text"
        assert result.relevance_score == 0.85
        assert result.source == "test"
        assert result.metadata == {"position": 1}
    
    def test_extracted_content(self):
        """Test ExtractedContent model."""
        content = ExtractedContent(
            url="https://example.com",
            title="Example Article",
            text_content="This is the article content.",
            html_content="<html><body>Content</body></html>",
            status=ExtractionStatus.SUCCESS,
            error_message=None,
            extracted_at="2024-01-01T00:00:00",
            metadata={"fetcher": "static"},
            author="Test Author",
            published_date="2024-01-01",
            tags=["test", "example"],
            images=["https://example.com/image.jpg"],
            links=["https://example.com/link"]
        )
        
        assert content.url == "https://example.com"
        assert content.title == "Example Article"
        assert content.text_content == "This is the article content."
        assert content.status == ExtractionStatus.SUCCESS
        assert content.author == "Test Author"
        assert len(content.tags) == 2
        assert len(content.images) == 1
        assert len(content.links) == 1
    
    def test_query_response(self):
        """Test QueryResponse model."""
        search_result = SearchResult(
            url="https://example.com",
            title="Example",
            snippet="Snippet"
        )
        
        extracted_content = ExtractedContent(
            url="https://example.com",
            title="Example",
            text_content="Content",
            status=ExtractionStatus.SUCCESS
        )
        
        response = QueryResponse(
            query="test",
            request_id="123",
            submitted_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T00:00:01",
            search_results=[search_result],
            extracted_content=[extracted_content],
            status="completed",
            error=None,
            metadata={"test": True}
        )
        
        assert response.query == "test"
        assert response.request_id == "123"
        assert response.status == "completed"
        assert len(response.search_results) == 1
        assert len(response.extracted_content) == 1
        assert len(response.successful_extractions) == 1
        assert len(response.failed_extractions) == 0


class TestSearchProviders:
    """Test search providers."""
    
    def test_mock_search_provider(self):
        """Test MockSearchProvider."""
        provider = MockSearchProvider()
        results = provider.search("test query", max_results=3)
        
        assert len(results) == 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert all("test query" in r.title for r in results)
        assert all(r.source == "mock" for r in results)
    
    def test_duckduckgo_search_provider_fallback(self):
        """Test DuckDuckGoSearchProvider fallback behavior."""
        provider = DuckDuckGoSearchProvider()
        
        # Mock the request to force fallback
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Test error")
            results = provider.search("test", max_results=2)
        
        # Should return fallback results
        assert len(results) == 2
        assert all(r.source == "fallback" for r in results)
    
    def test_get_search_provider(self):
        """Test get_search_provider factory function."""
        from tools.scrapling_query_app.search_providers import get_search_provider
        
        # Test mock provider
        mock_provider = get_search_provider("mock")
        assert isinstance(mock_provider, MockSearchProvider)
        
        # Test duckduckgo provider
        ddg_provider = get_search_provider("duckduckgo")
        assert isinstance(ddg_provider, DuckDuckGoSearchProvider)
        
        # Test invalid provider
        with pytest.raises(ValueError):
            get_search_provider("invalid")


class TestScraplingExtractor:
    """Test Scrapling extractor."""
    
    def test_extractor_initialization(self):
        """Test ScraplingExtractor initialization."""
        extractor = ScraplingExtractor(FetcherType.STATIC)
        assert extractor.fetcher_type == FetcherType.STATIC
        
        extractor = ScraplingExtractor(FetcherType.DYNAMIC)
        assert extractor.fetcher_type == FetcherType.DYNAMIC
        
        extractor = ScraplingExtractor(FetcherType.STEALTHY)
        assert extractor.fetcher_type == FetcherType.STEALTHY
    
    def test_extract_content_fallback(self):
        """Test content extraction with fallback (Scrapling not installed)."""
        extractor = ScraplingExtractor(FetcherType.DYNAMIC)
        content = extractor.extract_content("https://example.com/python/article")
        
        assert isinstance(content, ExtractedContent)
        assert content.url == "https://example.com/python/article"
        assert content.status == ExtractionStatus.SUCCESS
        assert content.title is not None
        assert len(content.text_content) > 0
        assert content.metadata.get("is_fallback") is True
    
    def test_extract_multiple_urls(self):
        """Test extracting content from multiple URLs."""
        urls = [
            "https://example.com/test1",
            "https://example.com/test2"
        ]
        
        from tools.scrapling_query_app.scrapling_extractor import extract_multiple_urls
        results = extract_multiple_urls(urls, FetcherType.DYNAMIC)
        
        assert len(results) == 2
        assert all(isinstance(r, ExtractedContent) for r in results)
        assert all(r.status == ExtractionStatus.SUCCESS for r in results)


class TestQueryProcessor:
    """Test query processor."""
    
    def test_processor_initialization(self):
        """Test QueryProcessor initialization."""
        processor = QueryProcessor(search_provider_name="mock")
        assert processor.search_provider is not None
    
    def test_process_query(self):
        """Test query processing."""
        processor = QueryProcessor(search_provider_name="mock")
        request = QueryRequest(
            query="test query",
            max_results=2,
            fetcher_type=FetcherType.DYNAMIC
        )
        
        response = processor.process_query(request)
        
        assert isinstance(response, QueryResponse)
        assert response.query == "test query"
        assert response.status == "completed"
        assert len(response.search_results) == 2
        assert len(response.extracted_content) == 2
        assert len(response.successful_extractions) > 0
    
    def test_process_query_async(self):
        """Test async query processing."""
        processor = QueryProcessor(search_provider_name="mock")
        request = QueryRequest(
            query="async test",
            max_results=1,
            fetcher_type=FetcherType.STATIC
        )
        
        request_id = processor.process_query_async(request)
        assert isinstance(request_id, str)
        assert len(request_id) > 0
        
        # Check status
        response = processor.get_request_status(request_id)
        assert response is not None
        assert response.request_id == request_id
        assert response.query == "async test"
    
    def test_get_all_requests(self):
        """Test getting all requests."""
        processor = QueryProcessor(search_provider_name="mock")
        
        # Start a request
        request = QueryRequest(query="test", max_results=1)
        request_id = processor.process_query_async(request)
        
        # Get all requests
        all_requests = processor.get_all_requests()
        assert isinstance(all_requests, list)
        assert len(all_requests) > 0
        assert any(r.request_id == request_id for r in all_requests)


class TestErrorHandling:
    """Test error handling."""
    
    def test_extraction_error(self):
        """Test extraction error handling."""
        extractor = ScraplingExtractor(FetcherType.DYNAMIC)
        
        # Test with a URL that might cause issues
        content = extractor.extract_content("invalid://url")
        
        # Should still return an ExtractedContent object
        assert isinstance(content, ExtractedContent)
        # Might be success (fallback) or failed depending on implementation
    
    def test_query_processor_error(self):
        """Test query processor error handling."""
        processor = QueryProcessor(search_provider_name="mock")
        
        # Create a mock search provider that raises an exception
        mock_provider = Mock()
        mock_provider.search.side_effect = Exception("Search failed")
        processor.search_provider = mock_provider
        
        request = QueryRequest(query="test", max_results=1)
        response = processor.process_query(request)
        
        # Should handle the error gracefully
        assert response.status == "failed"
        assert response.error is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])