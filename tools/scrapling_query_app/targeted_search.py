"""
Targeted search module for specific research topics like Anthropic's Mythos/Glasswing/Capybara.
Provides pre-configured search queries and content filtering.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .models import QueryRequest, SearchResult, ExtractedContent
from .query_processor import QueryProcessor

logger = logging.getLogger(__name__)


class ResearchTopic(Enum):
    """Pre-defined research topics."""
    ANTHROPIC_MYTHOS = "anthropic_mythos"
    PROJECT_GLASSWING = "project_glasswing"
    CAPYBARA_LLM = "capybara_llm"
    LLM_RESEARCH = "llm_research"
    AI_SAFETY = "ai_safety"
    CUSTOM = "custom"


@dataclass
class TargetedQuery:
    """A targeted query for specific research."""
    topic: ResearchTopic
    name: str
    query: str
    description: str
    priority: int  # 1-10, higher = more important
    keywords: List[str]
    domains: List[str]  # Preferred domains to search


class TargetedSearch:
    """Manages targeted searches for specific research topics."""
    
    def __init__(self, query_processor: QueryProcessor = None):
        self.query_processor = query_processor or QueryProcessor()
        self.topics = self._load_topics()
        
    def _load_topics(self) -> Dict[ResearchTopic, List[TargetedQuery]]:
        """Load pre-configured research topics."""
        topics = {}
        
        # Anthropic Mythos / Project Glasswing / Capybara
        mythos_queries = [
            TargetedQuery(
                topic=ResearchTopic.ANTHROPIC_MYTHOS,
                name="mythos_announcement",
                query="Anthropic Mythos LLM announcement release date",
                description="Official announcements about Mythos LLM",
                priority=10,
                keywords=["mythos", "anthropic", "llm", "announcement", "release"],
                domains=["anthropic.com", "techcrunch.com", "theverge.com", "wired.com"]
            ),
            TargetedQuery(
                topic=ResearchTopic.ANTHROPIC_MYTHOS,
                name="glasswing_project",
                query='"Project Glasswing" Anthropic research paper technical details',
                description="Technical details about Project Glasswing",
                priority=9,
                keywords=["glasswing", "project", "research", "paper", "technical"],
                domains=["arxiv.org", "anthropic.com", "github.com", "research.anthropic.com"]
            ),
            TargetedQuery(
                topic=ResearchTopic.ANTHROPIC_MYTHOS,
                name="capybara_model",
                query="Capybara LLM model architecture training data",
                description="Capybara model architecture and training",
                priority=8,
                keywords=["capybara", "model", "architecture", "training", "parameters"],
                domains=["arxiv.org", "github.com", "huggingface.co", "paperswithcode.com"]
            ),
            TargetedQuery(
                topic=ResearchTopic.ANTHROPIC_MYTHOS,
                name="source_code",
                query="Anthropic Mythos GitHub repository source code implementation",
                description="Source code repositories",
                priority=7,
                keywords=["github", "source", "code", "repository", "implementation"],
                domains=["github.com", "gitlab.com", "bitbucket.org"]
            ),
            TargetedQuery(
                topic=ResearchTopic.ANTHROPIC_MYTHOS,
                name="capabilities",
                query="Mythos LLM capabilities benchmarks performance evaluation",
                description="Model capabilities and benchmarks",
                priority=8,
                keywords=["capabilities", "benchmarks", "performance", "evaluation", "metrics"],
                domains=["arxiv.org", "paperswithcode.com", "eval.ai", "leaderboard"]
            ),
            TargetedQuery(
                topic=ResearchTopic.ANTHROPIC_MYTHOS,
                name="safety_alignment",
                query="Mythos AI safety alignment constitutional AI",
                description="Safety and alignment research",
                priority=7,
                keywords=["safety", "alignment", "constitutional", "ai", "ethics"],
                domains=["anthropic.com", "arxiv.org", "alignmentforum.org", "lesswrong.com"]
            ),
            TargetedQuery(
                topic=ResearchTopic.ANTHROPIC_MYTHOS,
                name="community_discussion",
                query="Mythos LLM Reddit Hacker News discussion reviews",
                description="Community discussions and reviews",
                priority=6,
                keywords=["reddit", "hacker news", "discussion", "review", "community"],
                domains=["reddit.com", "news.ycombinator.com", "twitter.com"]
            ),
            TargetedQuery(
                topic=ResearchTopic.ANTHROPIC_MYTHOS,
                name="competitor_analysis",
                query="Mythos vs GPT-4 vs Claude vs Gemini comparison",
                description="Comparison with other LLMs",
                priority=6,
                keywords=["comparison", "vs", "gpt-4", "claude", "gemini", "competitor"],
                domains=["medium.com", "towardsdatascience.com", "analyticsvidhya.com"]
            )
        ]
        topics[ResearchTopic.ANTHROPIC_MYTHOS] = mythos_queries
        
        return topics
    
    def search_topic(self, topic: ResearchTopic, max_results_per_query: int = 3) -> Dict[str, Any]:
        """Search for all queries related to a topic."""
        if topic not in self.topics:
            raise ValueError(f"Unknown topic: {topic}")
        
        queries = self.topics[topic]
        all_results = []
        all_content = []
        
        logger.info(f"Searching topic: {topic.value} with {len(queries)} queries")
        
        for i, tq in enumerate(queries):
            logger.info(f"  Query {i+1}/{len(queries)}: {tq.name} - {tq.query}")
            
            # Create query request
            request = QueryRequest(
                query=tq.query,
                max_results=max_results_per_query,
                use_cache=False
            )
            
            try:
                # Process query
                response = self.query_processor.process_query(request)
                
                # Filter results by relevance
                filtered_results = self._filter_by_relevance(response.search_results, tq.keywords)
                filtered_content = self._filter_by_relevance(response.extracted_content, tq.keywords)
                
                # Add topic metadata
                for result in filtered_results:
                    result.metadata = result.metadata or {}
                    result.metadata.update({
                        'research_topic': topic.value,
                        'query_name': tq.name,
                        'priority': tq.priority
                    })
                
                for content in filtered_content:
                    content.metadata = content.metadata or {}
                    content.metadata.update({
                        'research_topic': topic.value,
                        'query_name': tq.name,
                        'priority': tq.priority
                    })
                
                all_results.extend(filtered_results)
                all_content.extend(filtered_content)
                
                logger.info(f"    Found {len(filtered_results)} results, {len(filtered_content)} content items")
                
            except Exception as e:
                logger.error(f"Error processing query '{tq.name}': {e}")
        
        # Deduplicate results by URL
        unique_results = self._deduplicate_by_url(all_results)
        unique_content = self._deduplicate_by_url(all_content)
        
        # Sort by priority and relevance
        unique_results.sort(key=lambda x: x.metadata.get('priority', 0), reverse=True)
        unique_content.sort(key=lambda x: x.metadata.get('priority', 0), reverse=True)
        
        return {
            'topic': topic.value,
            'total_queries': len(queries),
            'total_results': len(unique_results),
            'total_content': len(unique_content),
            'results': unique_results,
            'content': unique_content
        }
    
    def _filter_by_relevance(self, items: List, keywords: List[str]) -> List:
        """Filter items by relevance to keywords."""
        if not items or not keywords:
            return items
        
        filtered = []
        for item in items:
            # Check title, URL, and snippet for keywords
            text_to_check = ""
            if hasattr(item, 'title'):
                text_to_check += item.title.lower() + " "
            if hasattr(item, 'url'):
                text_to_check += item.url.lower() + " "
            if hasattr(item, 'snippet'):
                text_to_check += item.snippet.lower() + " "
            if hasattr(item, 'text_content'):
                text_to_check += item.text_content.lower() + " "
            
            # Count keyword matches
            matches = 0
            for keyword in keywords:
                if keyword.lower() in text_to_check:
                    matches += 1
            
            # Keep if at least one keyword matches
            if matches > 0:
                # Add relevance score
                if hasattr(item, 'metadata'):
                    item.metadata = item.metadata or {}
                    item.metadata['relevance_score'] = matches / len(keywords)
                filtered.append(item)
        
        return filtered
    
    def _deduplicate_by_url(self, items: List) -> List:
        """Remove duplicate items by URL."""
        seen_urls = set()
        unique_items = []
        
        for item in items:
            url = getattr(item, 'url', None)
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)
        
        return unique_items
    
    def extract_technical_details(self, content_items: List[ExtractedContent]) -> Dict[str, Any]:
        """Extract technical details from content about LLMs."""
        technical_info = {
            'model_names': [],
            'parameter_counts': [],
            'training_data': [],
            'architectures': [],
            'capabilities': [],
            'benchmarks': [],
            'safety_features': [],
            'release_dates': [],
            'github_repos': []
        }
        
        for content in content_items:
            text = content.text_content.lower()
            
            # Extract model names
            model_patterns = [
                r'mythos(?:\s+(?:llm|model|ai))?',
                r'glasswing(?:\s+(?:project|model))?',
                r'capybara(?:\s+(?:llm|model))?',
                r'claude(?:\s+\d+)?',
                r'gpt(?:\s*[-]?\s*\d+)',
                r'gemini(?:\s+(?:pro|ultra))?',
                r'llama(?:\s+\d+)?'
            ]
            
            for pattern in model_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if match and match not in technical_info['model_names']:
                        technical_info['model_names'].append(match)
            
            # Extract parameter counts (e.g., "70B parameters", "1.7 trillion")
            param_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:billion|b|trillion|t|million|m)\s*parameters?', text, re.IGNORECASE)
            technical_info['parameter_counts'].extend(param_matches)
            
            # Extract GitHub URLs
            github_matches = re.findall(r'github\.com/[a-zA-Z0-9-]+/[a-zA-Z0-9-_.]+', text)
            technical_info['github_repos'].extend(github_matches)
            
            # Extract capabilities (common phrases)
            capability_phrases = [
                'code generation', 'reasoning', 'mathematics', 'creative writing',
                'translation', 'summarization', 'question answering', 'conversation',
                'multimodal', 'vision', 'audio', 'tool use', 'function calling'
            ]
            
            for phrase in capability_phrases:
                if phrase in text:
                    technical_info['capabilities'].append(phrase)
            
            # Extract benchmarks
            benchmark_patterns = [
                r'mmlu\s*[=:]\s*[\d.]+%',
                r'gsm8k\s*[=:]\s*[\d.]+%',
                r'human eval\s*[=:]\s*[\d.]+%',
                r'hellaswag\s*[=:]\s*[\d.]+%'
            ]
            
            for pattern in benchmark_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                technical_info['benchmarks'].extend(matches)
        
        # Deduplicate lists
        for key in technical_info:
            if isinstance(technical_info[key], list):
                technical_info[key] = list(set(technical_info[key]))
        
        return technical_info
    
    def generate_research_report(self, topic_results: Dict[str, Any]) -> str:
        """Generate a research report from collected data."""
        report = []
        
        report.append(f"# Research Report: {topic_results['topic'].replace('_', ' ').title()}")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"\n## Summary")
        report.append(f"- Total queries executed: {topic_results['total_queries']}")
        report.append(f"- Total search results found: {topic_results['total_results']}")
        report.append(f"- Total content items extracted: {topic_results['total_content']}")
        
        # Technical details
        if topic_results['content']:
            technical_details = self.extract_technical_details(topic_results['content'])
            
            report.append(f"\n## Technical Details")
            
            if technical_details['model_names']:
                report.append(f"\n### Model Names Found:")
                for model in technical_details['model_names']:
                    report.append(f"- {model}")
            
            if technical_details['parameter_counts']:
                report.append(f"\n### Parameter Counts:")
                for params in technical_details['parameter_counts']:
                    report.append(f"- {params}")
            
            if technical_details['github_repos']:
                report.append(f"\n### GitHub Repositories:")
                for repo in technical_details['github_repos']:
                    report.append(f"- https://{repo}")
            
            if technical_details['capabilities']:
                report.append(f"\n### Capabilities Mentioned:")
                for capability in technical_details['capabilities']:
                    report.append(f"- {capability}")
            
            if technical_details['benchmarks']:
                report.append(f"\n### Benchmark Results:")
                for benchmark in technical_details['benchmarks']:
                    report.append(f"- {benchmark}")
        
        # Top results
        if topic_results['results']:
            report.append(f"\n## Top Search Results")
            for i, result in enumerate(topic_results['results'][:10]):
                report.append(f"\n### {i+1}. {result.title}")
                report.append(f"URL: {result.url}")
                if result.snippet:
                    report.append(f"Snippet: {result.snippet[:200]}...")
                if hasattr(result, 'metadata') and result.metadata:
                    report.append(f"Priority: {result.metadata.get('priority', 'N/A')}")
                    report.append(f"Relevance: {result.metadata.get('relevance_score', 'N/A'):.2f}")
        
        # Content summary
        if topic_results['content']:
            report.append(f"\n## Extracted Content Summary")
            successful = [c for c in topic_results['content'] if c.status == 'success']
            failed = [c for c in topic_results['content'] if c.status == 'failed']
            
            report.append(f"- Successful extractions: {len(successful)}")
            report.append(f"- Failed extractions: {len(failed)}")
            
            if successful:
                report.append(f"\n### Top Content Items:")
                for i, content in enumerate(successful[:5]):
                    report.append(f"\n#### {i+1}. {content.title}")
                    report.append(f"URL: {content.url}")
                    if content.author:
                        report.append(f"Author: {content.author}")
                    if content.published_date:
                        report.append(f"Published: {content.published_date}")
                    report.append(f"Content preview: {content.text_content[:300]}...")
        
        return "\n".join(report)


def research_anthropic_mythos(output_file: str = None) -> Dict[str, Any]:
    """Convenience function to research Anthropic Mythos."""
    import json
    from datetime import datetime
    
    logger.info("Starting Anthropic Mythos research...")
    
    # Initialize targeted search
    processor = QueryProcessor(search_provider_name='duckduckgo')
    targeted_search = TargetedSearch(processor)
    
    # Search for Mythos topic
    results = targeted_search.search_topic(ResearchTopic.ANTHROPIC_MYTHOS, max_results_per_query=3)
    
    # Generate report
    report = targeted_search.generate_research_report(results)
    
    # Save to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report)
        logger.info(f"Report saved to: {output_file}")
        
        # Also save raw data as JSON
        json_file = output_file.replace('.txt', '.json').replace('.md', '.json')
        serializable_results = {
            'topic': results['topic'],
            'total_queries': results['total_queries'],
            'total_results': results['total_results'],
            'total_content': results['total_content'],
            'results': [
                {
                    'title': r.title,
                    'url': r.url,
                    'snippet': r.snippet,
                    'metadata': r.metadata
                } for r in results['results']
            ],
            'content': [
                {
                    'title': c.title,
                    'url': c.url,
                    'status': c.status,
                    'text_content': c.text_content[:1000] if c.text_content else '',
                    'metadata': c.metadata
                } for c in results['content']
            ]
        }
        
        with open(json_file, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        logger.info(f"Raw data saved to: {json_file}")
    
    logger.info(f"Research complete. Found {results['total_results']} results and {results['total_content']} content items.")
    
    return results