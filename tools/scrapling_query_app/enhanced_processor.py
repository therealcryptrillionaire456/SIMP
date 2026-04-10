"""
Enhanced query processor with technical analysis and targeted research capabilities.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from .models import QueryRequest, QueryResponse, FetcherType
from .query_processor import QueryProcessor
from .targeted_search import TargetedSearch, ResearchTopic, research_anthropic_mythos
from .technical_analyzer import TechnicalAnalyzer

logger = logging.getLogger(__name__)


class EnhancedQueryProcessor:
    """Enhanced query processor with technical analysis capabilities."""
    
    def __init__(self, search_provider_name: str = 'duckduckgo'):
        self.base_processor = QueryProcessor(search_provider_name)
        self.targeted_search = TargetedSearch(self.base_processor)
        self.technical_analyzer = TechnicalAnalyzer()
        self.output_dir = Path("data/scrapling_research")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process_query(self, request: QueryRequest) -> QueryResponse:
        """Process a query with enhanced capabilities."""
        logger.info(f"Processing enhanced query: {request.query}")
        
        # First, get base results
        base_response = self.base_processor.process_query(request)
        
        # Enhance with technical analysis
        enhanced_response = self._enhance_with_technical_analysis(base_response)
        
        # Save results
        self._save_results(enhanced_response, request.query)
        
        return enhanced_response
    
    def _enhance_with_technical_analysis(self, response: QueryResponse) -> QueryResponse:
        """Enhance response with technical analysis."""
        logger.info("Enhancing response with technical analysis")
        
        # Analyze each content item
        for content in response.extracted_content:
            if content.status == 'success' and content.text_content:
                try:
                    analysis = self.technical_analyzer.analyze_content(
                        content.text_content,
                        content.url
                    )
                    
                    # Add analysis to metadata
                    content.metadata = content.metadata or {}
                    content.metadata['technical_analysis'] = {
                        'has_source_code': analysis['has_source_code'],
                        'has_technical_specs': analysis['has_technical_specs'],
                        'has_api_docs': analysis['has_api_docs'],
                        'technical_score': analysis['overall_technical_score'],
                        'github_repos': analysis['github_repos'][:5],  # Limit to 5
                        'arxiv_papers': analysis['arxiv_papers'][:5],  # Limit to 5
                        'code_snippet_count': len(analysis['code_snippets'])
                    }
                    
                    # Add technical score to overall score
                    if 'score' not in content.metadata:
                        content.metadata['score'] = 0.0
                    content.metadata['score'] += analysis['overall_technical_score'] * 0.3
                    
                except Exception as e:
                    logger.error(f"Error analyzing content from {content.url}: {e}")
        
        # Sort by technical score
        response.extracted_content.sort(
            key=lambda x: x.metadata.get('technical_analysis', {}).get('technical_score', 0)
            if x.metadata else 0,
            reverse=True
        )
        
        return response
    
    def research_topic(self, topic: ResearchTopic, max_results_per_query: int = 3) -> Dict[str, Any]:
        """Conduct comprehensive research on a specific topic."""
        logger.info(f"Starting comprehensive research on topic: {topic.value}")
        
        # Use targeted search
        results = self.targeted_search.search_topic(topic, max_results_per_query)
        
        # Enhance with technical analysis
        for content in results['content']:
            if content.status == 'success' and content.text_content:
                try:
                    analysis = self.technical_analyzer.analyze_content(
                        content.text_content,
                        content.url
                    )
                    
                    # Add analysis to metadata
                    content.metadata = content.metadata or {}
                    content.metadata['technical_analysis'] = {
                        'has_source_code': analysis['has_source_code'],
                        'has_technical_specs': analysis['has_technical_specs'],
                        'has_api_docs': analysis['has_api_docs'],
                        'technical_score': analysis['overall_technical_score']
                    }
                    
                except Exception as e:
                    logger.error(f"Error analyzing content: {e}")
        
        # Generate comprehensive report
        report = self.targeted_search.generate_research_report(results)
        
        # Add technical analysis summary
        tech_summary = self._generate_technical_summary(results['content'])
        report += f"\n\n## Technical Analysis Summary\n{tech_summary}"
        
        # Save everything
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        topic_dir = self.output_dir / topic.value
        topic_dir.mkdir(exist_ok=True)
        
        # Save report
        report_file = topic_dir / f"research_report_{timestamp}.md"
        with open(report_file, 'w') as f:
            f.write(report)
        
        # Save raw data
        data_file = topic_dir / f"research_data_{timestamp}.json"
        serializable_data = self._serialize_results(results)
        with open(data_file, 'w') as f:
            json.dump(serializable_data, f, indent=2)
        
        # Save technical analysis details
        tech_file = topic_dir / f"technical_analysis_{timestamp}.json"
        tech_data = self._extract_technical_data(results['content'])
        with open(tech_file, 'w') as f:
            json.dump(tech_data, f, indent=2)
        
        logger.info(f"Research complete. Reports saved to: {topic_dir}")
        
        return {
            'topic': topic.value,
            'results': results,
            'report': report,
            'files': {
                'report': str(report_file),
                'data': str(data_file),
                'technical': str(tech_file)
            }
        }
    
    def _generate_technical_summary(self, content_items: List) -> str:
        """Generate technical analysis summary."""
        if not content_items:
            return "No content available for technical analysis."
        
        tech_scores = []
        has_source_code = 0
        has_tech_specs = 0
        has_api_docs = 0
        github_repos = set()
        arxiv_papers = set()
        
        for content in content_items:
            if hasattr(content, 'metadata') and content.metadata:
                tech_analysis = content.metadata.get('technical_analysis')
                if tech_analysis:
                    tech_scores.append(tech_analysis.get('technical_score', 0))
                    if tech_analysis.get('has_source_code'):
                        has_source_code += 1
                    if tech_analysis.get('has_technical_specs'):
                        has_tech_specs += 1
                    if tech_analysis.get('has_api_docs'):
                        has_api_docs += 1
                    
                    # Collect GitHub repos and arXiv papers
                    for repo in tech_analysis.get('github_repos', []):
                        github_repos.add(repo)
                    for paper in tech_analysis.get('arxiv_papers', []):
                        arxiv_papers.add(paper)
        
        summary = []
        
        if tech_scores:
            avg_score = sum(tech_scores) / len(tech_scores)
            summary.append(f"- Average Technical Score: {avg_score:.2%}")
        
        summary.append(f"- Documents with source code: {has_source_code}")
        summary.append(f"- Documents with technical specs: {has_tech_specs}")
        summary.append(f"- Documents with API docs: {has_api_docs}")
        
        if github_repos:
            summary.append(f"\n- GitHub Repositories Found ({len(github_repos)}):")
            for repo in list(github_repos)[:10]:  # Show top 10
                summary.append(f"  - {repo}")
        
        if arxiv_papers:
            summary.append(f"\n- arXiv Papers Found ({len(arxiv_papers)}):")
            for paper in list(arxiv_papers)[:10]:  # Show top 10
                summary.append(f"  - https://arxiv.org/abs/{paper}")
        
        return "\n".join(summary)
    
    def _serialize_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize results for JSON storage."""
        return {
            'topic': results['topic'],
            'total_queries': results['total_queries'],
            'total_results': results['total_results'],
            'total_content': results['total_content'],
            'results': [
                {
                    'title': r.title,
                    'url': r.url,
                    'snippet': r.snippet,
                    'source': r.source,
                    'metadata': r.metadata
                } for r in results['results']
            ],
            'content': [
                {
                    'title': c.title,
                    'url': c.url,
                    'status': c.status,
                    'text_content': c.text_content[:2000] if c.text_content else '',
                    'metadata': c.metadata
                } for c in results['content']
            ]
        }
    
    def _extract_technical_data(self, content_items: List) -> Dict[str, Any]:
        """Extract technical data for storage."""
        tech_data = {
            'code_snippets': [],
            'technical_specs': [],
            'github_repos': [],
            'arxiv_papers': [],
            'summary': {}
        }
        
        for content in content_items:
            if hasattr(content, 'metadata') and content.metadata:
                tech_analysis = content.metadata.get('technical_analysis')
                if tech_analysis:
                    # Collect data
                    tech_data['github_repos'].extend(tech_analysis.get('github_repos', []))
                    tech_data['arxiv_papers'].extend(tech_analysis.get('arxiv_papers', []))
        
        # Deduplicate
        tech_data['github_repos'] = list(set(tech_data['github_repos']))
        tech_data['arxiv_papers'] = list(set(tech_data['arxiv_papers']))
        
        # Add summary
        tech_data['summary'] = {
            'total_github_repos': len(tech_data['github_repos']),
            'total_arxiv_papers': len(tech_data['arxiv_papers']),
            'unique_github_repos': tech_data['github_repos'][:20],  # Limit to 20
            'unique_arxiv_papers': tech_data['arxiv_papers'][:20]   # Limit to 20
        }
        
        return tech_data
    
    def _save_results(self, response: QueryResponse, query: str) -> None:
        """Save query results to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_safe = "".join(c if c.isalnum() else "_" for c in query[:50])
        filename = f"query_{query_safe}_{timestamp}.json"
        filepath = self.output_dir / filename
        
        data = {
            'query': query,
            'timestamp': timestamp,
            'response': {
                'status': response.status,
                'search_results_count': len(response.search_results),
                'extracted_content_count': len(response.extracted_content),
                'successful_extractions': len(response.successful_extractions),
                'failed_extractions': len(response.failed_extractions),
                'search_results': [
                    {
                        'title': r.title,
                        'url': r.url,
                        'snippet': r.snippet,
                        'source': r.source
                    } for r in response.search_results
                ],
                'extracted_content': [
                    {
                        'title': c.title,
                        'url': c.url,
                        'status': c.status,
                        'text_preview': c.text_content[:500] if c.text_content else '',
                        'metadata': c.metadata
                    } for c in response.extracted_content
                ]
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Results saved to: {filepath}")


def run_mythos_research(output_dir: str = None) -> Dict[str, Any]:
    """
    Run comprehensive research on Anthropic Mythos/Glasswing/Capybara.
    
    Args:
        output_dir: Optional custom output directory
        
    Returns:
        Research results and file paths
    """
    logger.info("=" * 70)
    logger.info("STARTING COMPREHENSIVE MYTHOS/GLASSWING/CAPYBARA RESEARCH")
    logger.info("=" * 70)
    
    # Initialize enhanced processor
    processor = EnhancedQueryProcessor(search_provider_name='duckduckgo')
    
    if output_dir:
        processor.output_dir = Path(output_dir)
        processor.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run research
    results = processor.research_topic(
        ResearchTopic.ANTHROPIC_MYTHOS,
        max_results_per_query=3
    )
    
    logger.info("=" * 70)
    logger.info("RESEARCH COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Found {results['results']['total_results']} search results")
    logger.info(f"Extracted {results['results']['total_content']} content items")
    logger.info(f"Reports saved to: {results['files']['report']}")
    
    # Print quick summary
    print("\n" + "=" * 70)
    print("MYTHOS RESEARCH SUMMARY")
    print("=" * 70)
    print(f"Topic: {results['topic']}")
    print(f"Search queries executed: {results['results']['total_queries']}")
    print(f"Unique search results found: {results['results']['total_results']}")
    print(f"Content items extracted: {results['results']['total_content']}")
    
    # Show top results
    if results['results']['results']:
        print("\nTop 5 Search Results:")
        for i, result in enumerate(results['results']['results'][:5]):
            print(f"  {i+1}. {result.title}")
            print(f"     URL: {result.url}")
            if result.snippet:
                print(f"     Snippet: {result.snippet[:100]}...")
            print()
    
    # Show technical findings
    tech_data = processor._extract_technical_data(results['results']['content'])
    if tech_data['github_repos']:
        print(f"GitHub Repositories Found: {len(tech_data['github_repos'])}")
        for repo in tech_data['github_repos'][:5]:
            print(f"  - {repo}")
    
    if tech_data['arxiv_papers']:
        print(f"\narXiv Papers Found: {len(tech_data['arxiv_papers'])}")
        for paper in tech_data['arxiv_papers'][:3]:
            print(f"  - https://arxiv.org/abs/{paper}")
    
    print(f"\nFull report: {results['files']['report']}")
    print(f"Raw data: {results['files']['data']}")
    print(f"Technical analysis: {results['files']['technical']}")
    
    return results