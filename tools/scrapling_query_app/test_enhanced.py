#!/usr/bin/env python3
"""
Test the enhanced Scrapling Query Tool with Mythos research.
"""

import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, '.')

from tools.scrapling_query_app.enhanced_processor import EnhancedQueryProcessor
from tools.scrapling_query_app.models import QueryRequest, FetcherType
from tools.scrapling_query_app.targeted_search import ResearchTopic


def test_enhanced_query():
    """Test enhanced query processing."""
    print("Testing enhanced query processing...")
    
    processor = EnhancedQueryProcessor(search_provider_name='duckduckgo')
    
    # Test a query about Mythos
    request = QueryRequest(
        query="Anthropic Mythos LLM technical specifications",
        max_results=2,
        fetcher_type=FetcherType.STATIC
    )
    
    print(f"Processing query: {request.query}")
    response = processor.process_query(request)
    
    print(f"\nQuery completed: {response.status}")
    print(f"Search results found: {len(response.search_results)}")
    print(f"Content extracted: {len(response.extracted_content)}")
    
    if response.extracted_content:
        print("\nExtracted content with technical analysis:")
        for i, content in enumerate(response.extracted_content[:3]):
            print(f"\n{i+1}. {content.title}")
            print(f"   URL: {content.url}")
            print(f"   Status: {content.status}")
            
            if content.metadata and 'technical_analysis' in content.metadata:
                tech = content.metadata['technical_analysis']
                print(f"   Technical score: {tech.get('technical_score', 0):.2%}")
                print(f"   Has source code: {tech.get('has_source_code', False)}")
                print(f"   Has technical specs: {tech.get('has_technical_specs', False)}")
                print(f"   Has API docs: {tech.get('has_api_docs', False)}")
                
                if tech.get('github_repos'):
                    print(f"   GitHub repos: {len(tech['github_repos'])} found")
                
                if tech.get('arxiv_papers'):
                    print(f"   arXiv papers: {len(tech['arxiv_papers'])} found")
    
    return response


def test_targeted_search():
    """Test targeted search for Mythos."""
    print("\n" + "="*70)
    print("Testing targeted search for Anthropic Mythos...")
    print("="*70)
    
    processor = EnhancedQueryProcessor(search_provider_name='duckduckgo')
    
    # Run targeted research
    print("Starting Mythos research (this may take a few minutes)...")
    results = processor.research_topic(
        ResearchTopic.ANTHROPIC_MYTHOS,
        max_results_per_query=2  # Keep small for testing
    )
    
    print(f"\nResearch complete!")
    print(f"Topic: {results['topic']}")
    print(f"Total queries: {results['results']['total_queries']}")
    print(f"Unique results: {results['results']['total_results']}")
    print(f"Content extracted: {results['results']['total_content']}")
    
    # Show some results
    if results['results']['results']:
        print("\nTop 3 search results:")
        for i, result in enumerate(results['results']['results'][:3]):
            print(f"\n{i+1}. {result.title}")
            print(f"   URL: {result.url}")
            if result.snippet:
                print(f"   Snippet: {result.snippet[:100]}...")
    
    # Show technical findings
    tech_data = processor._extract_technical_data(results['results']['content'])
    if tech_data['github_repos']:
        print(f"\nGitHub repositories found: {len(tech_data['github_repos'])}")
        for repo in tech_data['github_repos'][:3]:
            print(f"  - {repo}")
    
    if tech_data['arxiv_papers']:
        print(f"\narXiv papers found: {len(tech_data['arxiv_papers'])}")
        for paper in tech_data['arxiv_papers'][:3]:
            print(f"  - https://arxiv.org/abs/{paper}")
    
    print(f"\nReport saved to: {results['files']['report']}")
    
    return results


def main():
    """Run all tests."""
    print("="*70)
    print("ENHANCED SCRAPLING QUERY TOOL TEST")
    print("="*70)
    
    try:
        # Test 1: Enhanced query processing
        print("\nTEST 1: Enhanced Query Processing")
        print("-"*40)
        test_enhanced_query()
        
        # Test 2: Targeted search
        print("\n\nTEST 2: Targeted Mythos Research")
        print("-"*40)
        test_targeted_search()
        
        print("\n" + "="*70)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*70)
        print("\nThe enhanced Scrapling Query Tool is working correctly.")
        print("It can now:")
        print("1. Process queries with technical analysis")
        print("2. Conduct targeted research on specific topics")
        print("3. Extract source code and technical specifications")
        print("4. Generate comprehensive research reports")
        print("5. Save all data for further analysis")
        
        print("\nTo run comprehensive Mythos research:")
        print("  python -m tools.scrapling_query_app.research_mythos")
        
        print("\nTo start the web server:")
        print("  python -m tools.scrapling_query_app")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()