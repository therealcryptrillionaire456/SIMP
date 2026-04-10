#!/usr/bin/env python3
"""
Demonstration showing REAL data extraction (not placeholder examples).
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, '.')

from tools.scrapling_query_app.enhanced_processor import EnhancedQueryProcessor
from tools.scrapling_query_app.models import QueryRequest, FetcherType


def demonstrate_real_data():
    """Show that the tool extracts REAL web data."""
    print("="*80)
    print("DEMONSTRATION: REAL WEB DATA EXTRACTION")
    print("="*80)
    print("\nThis demonstration shows that the tool extracts REAL data from")
    print("actual websites, not placeholder 'Example Article' content.")
    print("\n" + "="*80)
    
    # Initialize processor
    processor = EnhancedQueryProcessor(search_provider_name='duckduckgo')
    
    # Search for Mythos information
    print("\n1. Searching for 'Anthropic Mythos LLM'...")
    request = QueryRequest(
        query="Anthropic Mythos LLM",
        max_results=3,
        fetcher_type=FetcherType.STATIC
    )
    
    response = processor.process_query(request)
    
    print(f"\n2. Search completed:")
    print(f"   - Found {len(response.search_results)} search results")
    print(f"   - Extracted {len(response.extracted_content)} content items")
    print(f"   - {len(response.successful_extractions)} successful extractions")
    print(f"   - {len(response.failed_extractions)} failed extractions")
    
    # Show REAL search results (not examples)
    print("\n3. REAL SEARCH RESULTS (not examples):")
    print("-"*40)
    for i, result in enumerate(response.search_results[:3]):
        print(f"\n   Result {i+1}:")
        print(f"   Title: {result.title}")
        print(f"   URL: {result.url}")
        print(f"   Source: {result.source}")
        if result.snippet:
            print(f"   Snippet: {result.snippet[:150]}...")
    
    # Show REAL extracted content (not examples)
    print("\n4. REAL EXTRACTED CONTENT (not examples):")
    print("-"*40)
    
    real_content_count = 0
    for i, content in enumerate(response.extracted_content):
        if content.status == 'success':
            real_content_count += 1
            print(f"\n   Content {real_content_count}:")
            print(f"   Title: {content.title}")
            print(f"   URL: {content.url}")
            print(f"   Status: {content.status}")
            
            # Check if this is REAL data (not fallback)
            is_real = content.metadata.get('is_real_data', False) if content.metadata else False
            print(f"   Is REAL web data: {'✅ YES' if is_real else '⚠️ Fallback'}")
            
            # Show actual content preview
            if content.text_content and len(content.text_content) > 100:
                preview = content.text_content[:200].replace('\n', ' ')
                print(f"   Content preview: {preview}...")
            
            # Show technical analysis if available
            if content.metadata and 'technical_analysis' in content.metadata:
                tech = content.metadata['technical_analysis']
                print(f"   Technical score: {tech.get('technical_score', 0):.2%}")
            
            # Limit to 2 examples for demonstration
            if real_content_count >= 2:
                break
    
    # Show data persistence
    print("\n5. DATA PERSISTENCE:")
    print("-"*40)
    
    # Find saved files
    data_dir = Path("data/scrapling_research")
    if data_dir.exists():
        json_files = list(data_dir.glob("*.json"))
        if json_files:
            latest_file = max(json_files, key=lambda x: x.stat().st_mtime)
            print(f"   Latest data file: {latest_file.name}")
            
            # Show file contents
            try:
                with open(latest_file, 'r') as f:
                    data = json.load(f)
                
                print(f"   Query: {data.get('query', 'Unknown')}")
                print(f"   Timestamp: {data.get('timestamp', 'Unknown')}")
                print(f"   Results saved: {len(data.get('response', {}).get('search_results', []))}")
                
                # Verify this is REAL data
                sample_result = data.get('response', {}).get('search_results', [{}])[0]
                if sample_result.get('url', '').startswith('https://'):
                    print("   ✅ Contains REAL URLs (not example.com)")
                else:
                    print("   ⚠️ May contain example URLs")
                    
            except Exception as e:
                print(f"   Error reading file: {e}")
        else:
            print("   No data files found yet")
    else:
        print("   Data directory not created yet")
    
    # Final verification
    print("\n6. VERIFICATION:")
    print("-"*40)
    
    has_real_urls = any(
        result.url.startswith('https://') and 'example.com' not in result.url
        for result in response.search_results[:3]
    )
    
    has_real_content = any(
        content.status == 'success' and content.metadata.get('is_real_data', False)
        for content in response.extracted_content[:2]
    )
    
    print(f"   Has real URLs: {'✅ YES' if has_real_urls else '❌ NO'}")
    print(f"   Has real content: {'✅ YES' if has_real_content else '❌ NO'}")
    print(f"   Extracts from actual websites: {'✅ YES' if has_real_urls else '❌ NO'}")
    
    print("\n" + "="*80)
    print("CONCLUSION:")
    print("="*80)
    
    if has_real_urls and has_real_content:
        print("✅ SUCCESS: The tool is extracting REAL web data!")
        print("\nThe Scrapling Query Tool now:")
        print("1. Searches actual websites (not examples)")
        print("2. Extracts real content (not placeholders)")
        print("3. Returns actual URLs and data")
        print("4. Persists real research data")
        print("\nReady for Mythos research!")
    else:
        print("⚠️ ISSUE: Some content may still be fallback")
        print("\nCheck configuration and ensure:")
        print("1. Internet connection is working")
        print("2. DuckDuckGo search is not blocked")
        print("3. Target websites are accessible")
    
    print("\nTo run comprehensive Mythos research:")
    print("  python -m tools.scrapling_query_app.research_mythos")


if __name__ == "__main__":
    demonstrate_real_data()