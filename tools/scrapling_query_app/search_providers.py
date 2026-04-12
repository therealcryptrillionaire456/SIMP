"""
Search providers for finding web pages relevant to a query.

This module provides interfaces to different search providers.
Currently implements a simple DuckDuckGo HTML search as a fallback.
"""

import re
import time
from typing import List, Optional
import urllib.parse
import urllib.request

from .models import SearchResult


class SearchProvider:
    """Base class for search providers."""
    
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search for web pages relevant to the query."""
        raise NotImplementedError


class DuckDuckGoSearchProvider(SearchProvider):
    """
    Simple DuckDuckGo HTML search provider.
    
    Note: This is a basic implementation that parses DuckDuckGo's HTML results.
    For production use, consider using official APIs or more robust libraries.
    """
    
    def __init__(self, delay_between_requests: float = 1.0):
        self.delay_between_requests = delay_between_requests
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    def _clean_html(self, html: str) -> str:
        """Clean HTML tags from text."""
        if not html:
            return ""
        
        # Remove HTML tags
        import re
        clean = re.sub(r'<[^>]+>', '', html)
        # Decode HTML entities
        import html as html_module
        clean = html_module.unescape(clean)
        # Normalize whitespace
        clean = ' '.join(clean.split())
        return clean.strip()
    
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search DuckDuckGo for the query."""
        results = []
        
        # DuckDuckGo requires POST request with form data
        url = "https://html.duckduckgo.com/html/"
        
        # Create request with headers
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        # Create form data
        data = urllib.parse.urlencode({'q': query}).encode()
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                # Check if content is gzipped
                import gzip
                import io
                
                content = response.read()
                
                # Try to decode as gzip first
                try:
                    html = gzip.decompress(content).decode('utf-8', errors='ignore')
                except:
                    # If not gzipped, decode directly
                    html = content.decode('utf-8', errors='ignore')
            
            # Parse HTML for results
            # DuckDuckGo HTML structure (as of 2024):
            # <div class="result results_links ...">
            #   <div class="links_main ...">
            #     <h2 class="result__title">
            #       <a class="result__a" href="//duckduckgo.com/l/?uddg=...">Title</a>
            #     </h2>
            #     <a class="result__snippet" href="...">Snippet</a>
            #   </div>
            # </div>
            
            # Find all result links - DuckDuckGo uses result__a class inside result__title
            # Pattern: <a class="result__a" href="URL">Title</a>
            # Handle both single and double quotes
            link_matches = re.findall(r'<a[^>]*class=[\"\']result__a[\"\'][^>]*href=[\"\']([^\"\']+)[\"\']', html)
            
            # Find all titles - extract from result__a links
            title_matches = re.findall(r'<a[^>]*class=[\"\']result__a[\"\'][^>]*href=[\"\'][^\"\']*[\"\'][^>]*>(.*?)</a>', html, re.DOTALL)
            
            # Find all snippets - look for result__snippet class
            snippet_matches = re.findall(r'<a[^>]*class=[\"\']result__snippet[\"\'][^>]*>(.*?)</a>', html, re.DOTALL)
            
            # Combine them
            matches = []
            max_to_process = min(len(link_matches), len(title_matches), max_results)
            
            for i in range(max_to_process):
                result_url = link_matches[i]
                title_html = title_matches[i] if i < len(title_matches) else ""
                snippet_html = snippet_matches[i] if i < len(snippet_matches) else ""
                
                # URLs are now direct, not redirects
                # Make sure URL is absolute
                if result_url.startswith('//'):
                    result_url = 'https:' + result_url
                elif result_url.startswith('/'):
                    # Relative URL, make absolute
                    result_url = 'https://duckduckgo.com' + result_url
                
                # Clean title HTML
                title = self._clean_html(title_html)
                snippet = self._clean_html(snippet_html)
                
                matches.append((result_url, title, snippet))
            
            # If no matches found, use fallback
            if not matches:
                return self._create_fallback_results(query, max_results)
            
            for i, (result_url, title, snippet) in enumerate(matches[:max_results]):
                # URLs are now direct links (not redirects) with POST request
                # No need to extract from redirect
                
                # Clean up snippet (title already cleaned)
                snippet = snippet[:200] + "..." if len(snippet) > 200 else snippet
                
                # Calculate relevance score (simplified)
                relevance_score = 1.0 - (i * 0.1)
                
                result = SearchResult(
                    url=result_url,
                    title=title,
                    snippet=snippet,
                    relevance_score=relevance_score,
                    source="duckduckgo",
                    metadata={"position": i + 1}
                )
                results.append(result)
            
            # Add delay to be respectful
            time.sleep(self.delay_between_requests)
            
        except Exception as e:
            # Fallback: create a dummy result for demonstration
            print(f"Search error: {e}")
            results = self._create_fallback_results(query, max_results)
        
        return results
    
    def _create_fallback_results(self, query: str, max_results: int) -> List[SearchResult]:
        """Create fallback results when search fails."""
        results = []
        for i in range(min(max_results, 5)):
            # Create example URLs based on query
            safe_query = query.replace(' ', '_').lower()
            url = f"https://example.com/{safe_query}/result_{i+1}"
            title = f"Example result for: {query} (#{i+1})"
            snippet = f"This is an example result for the query '{query}'. In a real implementation, this would be actual search results."
            
            result = SearchResult(
                url=url,
                title=title,
                snippet=snippet,
                relevance_score=0.8 - (i * 0.1),
                source="fallback",
                metadata={"is_fallback": True, "position": i + 1}
            )
            results.append(result)
        
        return results


class MockSearchProvider(SearchProvider):
    """Mock search provider for testing."""
    
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Return mock search results."""
        results = []
        for i in range(max_results):
            result = SearchResult(
                url=f"https://example.com/{query.replace(' ', '_')}/result_{i}",
                title=f"Mock result {i} for: {query}",
                snippet=f"This is a mock search result for '{query}'. Result #{i}.",
                relevance_score=0.9 - (i * 0.1),
                source="mock",
                metadata={"is_mock": True, "position": i}
            )
            results.append(result)
        return results


# Factory function to get search provider
def get_search_provider(provider_name: str = "duckduckgo") -> SearchProvider:
    """Get a search provider by name."""
    providers = {
        "duckduckgo": DuckDuckGoSearchProvider,
        "mock": MockSearchProvider,
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown search provider: {provider_name}")
    
    return provider_class()