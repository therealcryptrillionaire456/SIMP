"""
Simple HTTP fetcher as a fallback when Scrapling is not available.
This fetches real web content using urllib and parses with regex/BeautifulSoup.
"""

import urllib.request
import urllib.error
import ssl
import time
import re
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from html import unescape

# Try to import BeautifulSoup for better parsing
try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    logging.warning("BeautifulSoup not available, using regex parsing")

logger = logging.getLogger(__name__)


class SimpleFetcher:
    """Simple HTTP fetcher for web content."""
    
    def __init__(self, user_agent: str = None, timeout: int = 30):
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
        self.timeout = timeout
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    def fetch(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse a web page."""
        logger.info(f"Fetching: {url}")
        
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            req = urllib.request.Request(url, headers=headers)
            
            # Add delay to be polite
            time.sleep(0.5)
            
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as response:
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
                
                # Get content type
                content_type = response.getheader('Content-Type', '')
                
                # Parse the HTML
                return self._parse_html(html, url, response.getcode())
                
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e.code} {e.reason}")
            return {
                'url': url,
                'status_code': e.code,
                'error': f"HTTP {e.code}: {e.reason}",
                'success': False
            }
        except urllib.error.URLError as e:
            logger.error(f"URL error for {url}: {e.reason}")
            return {
                'url': url,
                'status_code': 0,
                'error': f"URL error: {e.reason}",
                'success': False
            }
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return {
                'url': url,
                'status_code': 0,
                'error': str(e),
                'success': False
            }
    
    def _parse_html(self, html: str, url: str, status_code: int) -> Dict[str, Any]:
        """Parse HTML content."""
        
        # Parse with BeautifulSoup if available
        if BEAUTIFULSOUP_AVAILABLE:
            return self._parse_with_bs4(html, url, status_code)
        else:
            return self._parse_with_regex(html, url, status_code)
    
    def _parse_with_bs4(self, html: str, url: str, status_code: int) -> Dict[str, Any]:
        """Parse HTML using BeautifulSoup."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get title
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else "No title"
        
        # Get main content - try multiple selectors
        content_selectors = [
            'article',
            'main',
            '.content',
            '#content',
            '.post-content',
            '.article-content',
            '[role="main"]'
        ]
        
        main_content = None
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                main_content = element
                break
        
        # If no specific content element found, use body
        if not main_content:
            main_content = soup.find('body') or soup
        
        # Get text content
        text_content = main_content.get_text(strip=True) if main_content else ""
        
        # Clean text content
        if text_content:
            # Remove extra whitespace
            text_content = ' '.join(text_content.split())
            # Limit length
            if len(text_content) > 5000:
                text_content = text_content[:5000] + "..."
        
        # Extract metadata
        author = None
        author_selectors = [
            'meta[name="author"]',
            '.author',
            '[rel="author"]',
            '[itemprop="author"]'
        ]
        for selector in author_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    author = element.get('content', '')
                else:
                    author = element.get_text(strip=True)
                if author:
                    break
        
        # Extract date
        published_date = None
        date_selectors = [
            'meta[property="article:published_time"]',
            'meta[name="date"]',
            'time[datetime]',
            '.date',
            '.published'
        ]
        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    published_date = element.get('content', '')
                elif element.name == 'time':
                    published_date = element.get('datetime', '')
                else:
                    published_date = element.get_text(strip=True)
                if published_date:
                    break
        
        # Extract images
        images = []
        img_tags = soup.find_all('img', src=True)
        for img in img_tags[:5]:  # Limit to 5 images
            src = img['src']
            if src:
                # Make URL absolute
                src = self._make_absolute_url(src, url)
                images.append(src)
        
        # Extract links
        links = []
        a_tags = soup.find_all('a', href=True)
        for a in a_tags[:10]:  # Limit to 10 links
            href = a['href']
            if href and not href.startswith(('#', 'javascript:')):
                # Make URL absolute
                href = self._make_absolute_url(href, url)
                links.append(href)
        
        # Extract tags
        tags = []
        tag_selectors = [
            'meta[property="article:tag"]',
            '.tags a',
            '.categories a',
            '[rel="tag"]'
        ]
        for selector in tag_selectors:
            elements = soup.select(selector)
            for element in elements:
                if element.name == 'meta':
                    tag = element.get('content', '')
                else:
                    tag = element.get_text(strip=True)
                if tag and tag not in tags:
                    tags.append(tag)
        
        return {
            'url': url,
            'title': title,
            'text_content': text_content or "No content extracted",
            'html_content': str(main_content)[:10000] if main_content else "",  # Limit HTML
            'status_code': status_code,
            'author': author,
            'published_date': published_date,
            'images': images,
            'links': links,
            'tags': tags[:10],  # Limit to 10 tags
            'success': True,
            'parser': 'beautifulsoup'
        }
    
    def _parse_with_regex(self, html: str, url: str, status_code: int) -> Dict[str, Any]:
        """Parse HTML using regex (fallback when BeautifulSoup not available)."""
        
        # Extract title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = unescape(title_match.group(1).strip()) if title_match else "No title"
        
        # Extract main content - simple regex approach
        # Remove scripts and styles
        html_clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r'<style[^>]*>.*?</style>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags to get text
        text_content = re.sub(r'<[^>]+>', ' ', html_clean)
        text_content = unescape(text_content)
        text_content = ' '.join(text_content.split())  # Normalize whitespace
        
        # Limit length
        if len(text_content) > 5000:
            text_content = text_content[:5000] + "..."
        
        # Extract author (simple regex)
        author = None
        author_match = re.search(r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if author_match:
            author = unescape(author_match.group(1))
        
        # Extract date (simple regex)
        published_date = None
        date_match = re.search(r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if date_match:
            published_date = unescape(date_match.group(1))
        
        # Extract images
        images = []
        img_matches = re.findall(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
        for src in img_matches[:5]:
            src = self._make_absolute_url(src, url)
            images.append(src)
        
        # Extract links
        links = []
        link_matches = re.findall(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
        for href in link_matches[:10]:
            if href and not href.startswith(('#', 'javascript:')):
                href = self._make_absolute_url(href, url)
                links.append(href)
        
        return {
            'url': url,
            'title': title,
            'text_content': text_content or "No content extracted",
            'html_content': html_clean[:10000],  # Limit HTML
            'status_code': status_code,
            'author': author,
            'published_date': published_date,
            'images': images,
            'links': links,
            'tags': [],  # Hard to extract tags with regex
            'success': True,
            'parser': 'regex'
        }
    
    def _make_absolute_url(self, url: str, base_url: str) -> str:
        """Convert relative URL to absolute URL."""
        if not url:
            return ""
        
        # If already absolute
        if url.startswith(('http://', 'https://', '//')):
            if url.startswith('//'):
                return 'https:' + url
            return url
        
        # Parse base URL and join
        from urllib.parse import urljoin
        return urljoin(base_url, url)


def fetch_multiple_urls(urls: list, max_workers: int = 3) -> list:
    """Fetch multiple URLs (simple sequential implementation)."""
    fetcher = SimpleFetcher()
    results = []
    
    for i, url in enumerate(urls):
        logger.info(f"Fetching URL {i+1}/{len(urls)}: {url}")
        result = fetcher.fetch(url)
        results.append(result)
    
    return results