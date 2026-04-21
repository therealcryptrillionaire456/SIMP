#!/usr/bin/env python3
"""
Deep Mythos Research - Comprehensive intelligence gathering for Mythos recreation.
This goes beyond basic scraping to find EVERYTHING needed to recreate the model.
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.scrapling_query_app.enhanced_processor import EnhancedQueryProcessor
from tools.scrapling_query_app.targeted_search import ResearchTopic
from tools.scrapling_query_app.technical_analyzer import TechnicalAnalyzer


class DeepMythosResearch:
    """Deep research system for Mythos recreation intelligence."""
    
    def __init__(self):
        self.processor = EnhancedQueryProcessor(search_provider_name='duckduckgo')
        self.tech_analyzer = TechnicalAnalyzer()
        self.research_dir = Path("data/deep_mythos_research")
        self.research_dir.mkdir(parents=True, exist_ok=True)
        
        # Extended search queries for deep research
        self.deep_queries = [
            # Architecture and implementation
            ("mythos transformer architecture attention layers", "architecture"),
            ("anthropic mythos model code implementation github", "implementation"),
            ("mythos llm pytorch tensorflow jax code", "framework"),
            ("project glasswing source code repository", "source_code"),
            
            # Training and data
            ("mythos training data dataset composition", "training_data"),
            ("anthropic constitutional ai training methodology", "training_method"),
            ("mythos fine-tuning reinforcement learning", "finetuning"),
            ("capybara model pretraining corpus", "pretraining"),
            
            # Technical specifications
            ("mythos model parameters layers dimensions", "specs"),
            ("anthropic mythos context length tokenizer", "tokenizer"),
            ("mythos compute requirements flops training", "compute"),
            ("glasswing model size memory requirements", "resources"),
            
            # Safety and alignment
            ("mythos constitutional ai implementation code", "safety"),
            ("anthropic harmlessness helpfulness honesty", "alignment"),
            ("mythos red teaming adversarial testing", "testing"),
            ("capybara model safety mitigations", "mitigations"),
            
            # Benchmarks and evaluation
            ("mythos benchmark results mmlu gsm8k", "benchmarks"),
            ("anthropic model evaluation framework", "evaluation"),
            ("mythos vs gpt4 vs claude comparison", "comparison"),
            ("glasswing performance metrics", "performance"),
            
            # Research papers and technical docs
            ("anthropic research paper pdf arxiv", "papers"),
            ("mythos technical documentation api", "docs"),
            ("project glasswing whitepaper", "whitepaper"),
            ("capybara model card system card", "model_card"),
            
            # Community and reverse engineering
            ("mythos reverse engineering analysis", "reverse_engineer"),
            ("anthropic model leaked information", "leaks"),
            ("mythos implementation details discussion", "discussion"),
            ("recreating anthropic models guide", "recreation"),
        ]
    
    def conduct_deep_research(self) -> Dict[str, Any]:
        """Conduct comprehensive deep research."""
        logger.info("Starting deep Mythos research...")
        
        all_results = []
        all_content = []
        
        # Run all deep queries
        for i, (query, category) in enumerate(self.deep_queries):
            logger.info(f"Query {i+1}/{len(self.deep_queries)}: {query}")
            
            try:
                from tools.scrapling_query_app.models import QueryRequest, FetcherType
                
                request = QueryRequest(
                    query=query,
                    max_results=5,  # Get more results for deep research
                    fetcher_type=FetcherType.STATIC
                )
                
                response = self.processor.process_query(request)
                
                # Add category metadata
                for result in response.search_results:
                    result.metadata = result.metadata or {}
                    result.metadata['deep_research_category'] = category
                
                for content in response.extracted_content:
                    content.metadata = content.metadata or {}
                    content.metadata['deep_research_category'] = category
                
                all_results.extend(response.search_results)
                all_content.extend(response.extracted_content)
                
                logger.info(f"  Found {len(response.search_results)} results, {len(response.extracted_content)} content items")
                
            except Exception as e:
                logger.error(f"Error processing query '{query}': {e}")
        
        # Deduplicate
        unique_results = self._deduplicate_by_url(all_results)
        unique_content = self._deduplicate_by_url(all_content)
        
        # Analyze technical content
        technical_analysis = self._analyze_all_content(unique_content)
        
        # Extract reconstruction specifications
        reconstruction_specs = self._extract_reconstruction_specs(unique_content)
        
        # Generate comprehensive report
        report = self._generate_deep_research_report(
            unique_results, unique_content, technical_analysis, reconstruction_specs
        )
        
        # Save everything
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._save_research_data(
            timestamp, unique_results, unique_content, 
            technical_analysis, reconstruction_specs, report
        )
        
        return {
            'timestamp': timestamp,
            'total_results': len(unique_results),
            'total_content': len(unique_content),
            'technical_analysis': technical_analysis,
            'reconstruction_specs': reconstruction_specs,
            'report': report,
            'files': self._get_file_paths(timestamp)
        }
    
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
    
    def _analyze_all_content(self, content_items: List) -> Dict[str, Any]:
        """Analyze all content for technical details."""
        logger.info("Analyzing all content for technical details...")
        
        analysis = {
            'code_snippets': [],
            'github_repos': [],
            'arxiv_papers': [],
            'technical_specs': [],
            'architecture_details': [],
            'training_info': [],
            'safety_components': [],
            'benchmark_data': []
        }
        
        for content in content_items:
            if content.status == 'success' and content.text_content:
                try:
                    # Basic technical analysis
                    tech_analysis = self.tech_analyzer.analyze_content(
                        content.text_content, content.url
                    )
                    
                    analysis['code_snippets'].extend(tech_analysis['code_snippets'])
                    analysis['github_repos'].extend(tech_analysis['github_repos'])
                    analysis['arxiv_papers'].extend(tech_analysis['arxiv_papers'])
                    
                    # Extract specific information for reconstruction
                    text = content.text_content.lower()
                    
                    # Architecture details
                    arch_patterns = [
                        r'(\d+)\s*layers',
                        r'(\d+(?:\.\d+)?)\s*(billion|b|million|m)\s*parameters',
                        r'hidden\s*size\s*[:\-]\s*(\d+)',
                        r'attention\s*heads\s*[:\-]\s*(\d+)',
                        r'context\s*length\s*[:\-]\s*(\d+(?:,\d+)*)',
                        r'vocabulary\s*size\s*[:\-]\s*(\d+(?:,\d+)*)'
                    ]
                    
                    for pattern in arch_patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                analysis['architecture_details'].append({
                                    'type': pattern.split()[0],
                                    'value': match[0],
                                    'unit': match[1] if len(match) > 1 else None,
                                    'source': content.url
                                })
                            else:
                                analysis['architecture_details'].append({
                                    'type': pattern.split()[0],
                                    'value': match,
                                    'source': content.url
                                })
                    
                    # Training information
                    if any(term in text for term in ['training', 'pretraining', 'finetuning']):
                        training_terms = ['epochs', 'batch size', 'learning rate', 'optimizer', 'loss']
                        for term in training_terms:
                            if term in text:
                                analysis['training_info'].append({
                                    'term': term,
                                    'context': self._extract_context(text, term),
                                    'source': content.url
                                })
                    
                    # Safety components
                    safety_terms = ['constitutional ai', 'red teaming', 'harmlessness', 
                                   'helpfulness', 'honesty', 'safety', 'alignment']
                    for term in safety_terms:
                        if term in text:
                            analysis['safety_components'].append({
                                'component': term,
                                'context': self._extract_context(text, term),
                                'source': content.url
                            })
                    
                    # Benchmark data
                    benchmark_patterns = [
                        r'(mmlu|gsm8k|human eval|hellaswag)[\s:=]+([\d.]+)%?',
                        r'score\s+of\s+([\d.]+)%?\s+on\s+(\w+)',
                        r'benchmark\s+([\d.]+)%?\s+(\w+)'
                    ]
                    
                    for pattern in benchmark_patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple) and len(match) >= 2:
                                analysis['benchmark_data'].append({
                                    'benchmark': match[0],
                                    'score': match[1],
                                    'source': content.url
                                })
                    
                except Exception as e:
                    logger.debug(f"Error analyzing content: {e}")
        
        # Deduplicate
        for key in analysis:
            if isinstance(analysis[key], list):
                # Simple deduplication for lists of strings
                if analysis[key] and isinstance(analysis[key][0], str):
                    analysis[key] = list(set(analysis[key]))
                # For dicts, deduplicate by a key
                elif analysis[key] and isinstance(analysis[key][0], dict):
                    seen = set()
                    unique = []
                    for item in analysis[key]:
                        item_str = str(item)
                        if item_str not in seen:
                            seen.add(item_str)
                            unique.append(item)
                    analysis[key] = unique
        
        return analysis
    
    def _extract_context(self, text: str, term: str, context_chars: int = 200) -> str:
        """Extract context around a term."""
        idx = text.find(term)
        if idx == -1:
            return ""
        
        start = max(0, idx - context_chars)
        end = min(len(text), idx + len(term) + context_chars)
        return text[start:end]
    
    def _extract_reconstruction_specs(self, content_items: List) -> Dict[str, Any]:
        """Extract specifications needed for reconstruction."""
        logger.info("Extracting reconstruction specifications...")
        
        specs = {
            'architecture': {},
            'training': {},
            'data': {},
            'safety': {},
            'resources': {},
            'implementation': {}
        }
        
        # Collect all architecture details
        arch_details = []
        for content in content_items:
            if content.status == 'success' and content.text_content:
                text = content.text_content.lower()
                
                # Extract parameter count
                param_match = re.search(r'(\d+(?:\.\d+)?)\s*(billion|b|trillion|t)\s*parameters?', text)
                if param_match:
                    specs['architecture']['parameters'] = {
                        'value': param_match.group(1),
                        'unit': param_match.group(2),
                        'source': content.url
                    }
                
                # Extract layers
                layers_match = re.search(r'(\d+)\s*layers', text)
                if layers_match:
                    specs['architecture']['layers'] = {
                        'value': layers_match.group(1),
                        'source': content.url
                    }
                
                # Extract hidden size
                hidden_match = re.search(r'hidden\s*(?:size|dimension)\s*[:\-]\s*(\d+)', text)
                if hidden_match:
                    specs['architecture']['hidden_size'] = {
                        'value': hidden_match.group(1),
                        'source': content.url
                    }
                
                # Extract attention heads
                heads_match = re.search(r'attention\s*heads\s*[:\-]\s*(\d+)', text)
                if heads_match:
                    specs['architecture']['attention_heads'] = {
                        'value': heads_match.group(1),
                        'source': content.url
                    }
        
        return specs
    
    def _generate_deep_research_report(self, results: List, content: List, 
                                      analysis: Dict, specs: Dict) -> str:
        """Generate comprehensive deep research report."""
        logger.info("Generating deep research report...")
        
        report = []
        
        report.append("# DEEP MYTHOS RESEARCH REPORT")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Total search results: {len(results)}")
        report.append(f"Total content extracted: {len(content)}")
        
        # Reconstruction specifications
        report.append("\n## RECONSTRUCTION SPECIFICATIONS")
        
        if specs['architecture']:
            report.append("\n### Architecture")
            for key, value in specs['architecture'].items():
                if isinstance(value, dict):
                    report.append(f"- **{key}**: {value.get('value', 'N/A')} {value.get('unit', '')}")
                else:
                    report.append(f"- **{key}**: {value}")
        
        # Technical findings
        report.append("\n## TECHNICAL FINDINGS")
        
        if analysis['github_repos']:
            report.append(f"\n### GitHub Repositories ({len(analysis['github_repos'])})")
            for repo in analysis['github_repos'][:20]:
                report.append(f"- https://github.com/{repo}")
        
        if analysis['arxiv_papers']:
            report.append(f"\n### arXiv Papers ({len(analysis['arxiv_papers'])})")
            for paper in analysis['arxiv_papers'][:10]:
                report.append(f"- https://arxiv.org/abs/{paper}")
        
        if analysis['architecture_details']:
            report.append(f"\n### Architecture Details ({len(analysis['architecture_details'])})")
            for detail in analysis['architecture_details'][:10]:
                report.append(f"- {detail.get('type', 'Unknown')}: {detail.get('value', 'N/A')} {detail.get('unit', '')}")
        
        if analysis['training_info']:
            report.append(f"\n### Training Information ({len(analysis['training_info'])})")
            for info in analysis['training_info'][:10]:
                report.append(f"- {info.get('term', 'Unknown')}: {info.get('context', 'N/A')[:100]}...")
        
        if analysis['safety_components']:
            report.append(f"\n### Safety Components ({len(analysis['safety_components'])})")
            for component in analysis['safety_components'][:10]:
                report.append(f"- {component.get('component', 'Unknown')}: {component.get('context', 'N/A')[:100]}...")
        
        if analysis['benchmark_data']:
            report.append(f"\n### Benchmark Data ({len(analysis['benchmark_data'])})")
            for benchmark in analysis['benchmark_data'][:10]:
                report.append(f"- {benchmark.get('benchmark', 'Unknown')}: {benchmark.get('score', 'N/A')}%")
        
        # Top content
        report.append("\n## TOP CONTENT FOR RECONSTRUCTION")
        
        successful_content = [c for c in content if c.status == 'success']
        sorted_content = sorted(
            successful_content,
            key=lambda x: x.metadata.get('technical_analysis', {}).get('technical_score', 0)
            if x.metadata else 0,
            reverse=True
        )
        
        for i, content_item in enumerate(sorted_content[:10]):
            report.append(f"\n### {i+1}. {content_item.title}")
            report.append(f"URL: {content_item.url}")
            
            if content_item.metadata and 'technical_analysis' in content_item.metadata:
                tech = content_item.metadata['technical_analysis']
                report.append(f"Technical score: {tech.get('technical_score', 0):.2%}")
                report.append(f"Has source code: {tech.get('has_source_code', False)}")
                report.append(f"Has technical specs: {tech.get('has_technical_specs', False)}")
            
            if content_item.text_content:
                report.append(f"Preview: {content_item.text_content[:300]}...")
        
        # Reconstruction roadmap
        report.append("\n## RECONSTRUCTION ROADMAP")
        report.append("\n### Phase 1: Architecture Implementation")
        report.append("1. Implement transformer architecture based on gathered specs")
        report.append("2. Add attention mechanisms and layer configurations")
        report.append("3. Implement tokenizer based on vocabulary size")
        report.append("4. Add positional encoding and embeddings")
        
        report.append("\n### Phase 2: Training Pipeline")
        report.append("1. Collect and preprocess training data")
        report.append("2. Implement training loop with gathered hyperparameters")
        report.append("3. Add optimization and learning rate scheduling")
        report.append("4. Implement checkpointing and logging")
        
        report.append("\n### Phase 3: Safety & Alignment")
        report.append("1. Implement Constitutional AI components")
        report.append("2. Add safety filters and content moderation")
        report.append("3. Implement red teaming and adversarial testing")
        report.append("4. Add alignment training procedures")
        
        report.append("\n### Phase 4: Evaluation & Deployment")
        report.append("1. Implement benchmark evaluation suite")
        report.append("2. Add performance monitoring and metrics")
        report.append("3. Create API and inference server")
        report.append("4. Document and package for distribution")
        
        report.append("\n## NEXT STEPS")
        report.append("1. Review the gathered specifications")
        report.append("2. Start implementing the architecture in code")
        report.append("3. Set up training infrastructure")
        report.append("4. Begin with a smaller proof-of-concept model")
        report.append("5. Iteratively scale up based on results")
        
        return "\n".join(report)
    
    def _save_research_data(self, timestamp: str, results: List, content: List,
                           analysis: Dict, specs: Dict, report: str):
        """Save all research data."""
        # Save report
        report_file = self.research_dir / f"deep_research_report_{timestamp}.md"
        with open(report_file, 'w') as f:
            f.write(report)
        
        # Save raw data
        data_file = self.research_dir / f"research_data_{timestamp}.json"
        data = {
            'timestamp': timestamp,
            'results': [
                {
                    'title': r.title,
                    'url': r.url,
                    'snippet': r.snippet,
                    'metadata': r.metadata
                } for r in results
            ],
            'content': [
                {
                    'title': c.title,
                    'url': c.url,
                    'status': c.status,
                    'text_content': c.text_content[:5000] if c.text_content else '',
                    'metadata': c.metadata
                } for c in content
            ],
            'technical_analysis': analysis,
            'reconstruction_specs': specs
        }
        
        with open(data_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Save reconstruction blueprint
        blueprint_file = self.research_dir / f"reconstruction_blueprint_{timestamp}.json"
        blueprint = self._create_reconstruction_blueprint(specs, analysis)
        with open(blueprint_file, 'w') as f:
            json.dump(blueprint, f, indent=2)
        
        logger.info(f"Research saved to: {self.research_dir}")
        logger.info(f"  - Report: {report_file.name}")
        logger.info(f"  - Data: {data_file.name}")
        logger.info(f"  - Blueprint: {blueprint_file.name}")
    
    def _create_reconstruction_blueprint(self, specs: Dict, analysis: Dict) -> Dict[str, Any]:
        """Create a reconstruction blueprint from gathered specifications."""
        blueprint = {
            'model_name': 'MythosRecreation',
            'version': '0.1.0',
            'based_on': 'Anthropic Mythos/Glasswing/Capybara',
            'architecture': {
                'type': 'Transformer',
                'parameters': specs['architecture'].get('parameters', {'value': 'Unknown'}),
                'layers': specs['architecture'].get('layers', {'value': 'Unknown'}),
                'hidden_size': specs['architecture'].get('hidden_size', {'value': 'Unknown'}),
                'attention_heads': specs['architecture'].get('attention_heads', {'value': 'Unknown'}),
                'context_length': specs['architecture'].get('context_length', {'value': '8192'}),
                'vocabulary_size': specs['architecture'].get('vocabulary_size', {'value': '50257'})
            },
            'training': {
                'framework': 'PyTorch',  # Default, can be changed
                'optimizer': 'AdamW',
                'learning_rate': '3e-4',
                'batch_size': 'Variable based on resources',
                'epochs': 'Until convergence'
            },
            'data': {
                'sources': analysis.get('github_repos', [])[:5],
                'preprocessing': 'Standard text preprocessing and tokenization'
            },
            'safety': {
                'components': [c.get('component', '') for c in analysis.get('safety_components', [])][:5],
                'framework': 'Constitutional AI'
            },
            'implementation_plan': [
                '1. Set up development environment',
                '2. Implement basic transformer architecture',
                '3. Add model configuration based on specs',
                '4. Implement training pipeline',
                '5. Add safety and alignment components',
                '6. Test with small-scale data',
                '7. Scale up based on available resources'
            ]
        }
        
        return blueprint
    
    def _get_file_paths(self, timestamp: str) -> Dict[str, str]:
        """Get file paths for the research output."""
        return {
            'report': str(self.research_dir / f"deep_research_report_{timestamp}.md"),
            'data': str(self.research_dir / f"research_data_{timestamp}.json"),
            'blueprint': str(self.research_dir / f"reconstruction_blueprint_{timestamp}.json")
        }


def main():
    """Run deep Mythos research."""
    print("="*80)
    print("DEEP MYTHOS RESEARCH FOR RECREATION")
    print("="*80)
    print("\nThis will conduct comprehensive research to gather ALL information")
    print("needed to recreate Anthropic's Mythos/Glasswing/Capybara LLM.")
    print("\nResearch includes:")
    print("1. Architecture specifications and implementation details")
    print("2. Training methodologies and data sources")
    print("3. Safety and alignment components")
    print("4. Source code repositories and examples")
    print("5. Benchmark data and performance metrics")
    print("6. Reconstruction blueprint and implementation plan")
    print("\n" + "="*80)
    
    try:
        researcher = DeepMythosResearch()
        results = researcher.conduct_deep_research()
        
        print("\n" + "="*80)
        print("DEEP RESEARCH COMPLETE!")
        print("="*80)
        
        print(f"\nResearch conducted: {results['timestamp']}")
        print(f"Total search results gathered: {results['total_results']}")
        print(f"Total content analyzed: {results['total_content']}")
        
        print("\nKey findings:")
        if results['reconstruction_specs']['architecture']:
            print("\nArchitecture specifications found:")
            for key, value in results['reconstruction_specs']['architecture'].items():
                if isinstance(value, dict):
                    print(f"  - {key}: {value.get('value', 'N/A')} {value.get('unit', '')}")
        
        analysis = results['technical_analysis']
        if analysis['github_repos']:
            print(f"\nGitHub repositories found: {len(analysis['github_repos'])}")
            for repo in analysis['github_repos'][:3]:
                print(f"  - {repo}")
        
        if analysis['arxiv_papers']:
            print(f"\narXiv papers found: {len(analysis['arxiv_papers'])}")
            for paper in analysis['arxiv_papers'][:3]:
                print(f"  - https://arxiv.org/abs/{paper}")
        
        print("\nFiles created:")
        for name, path in results['files'].items():
            print(f"  - {name}: {Path(path).name}")
        
        print("\n" + "="*80)
        print("NEXT STEP: IMPLEMENTATION")
        print("="*80)
        print("\nWith the gathered specifications, you can now:")
        print("1. Review the reconstruction blueprint")
        print("2. Start implementing the architecture")
        print("3. Set up training infrastructure")
        print("4. Begin with a proof-of-concept model")
        
        print("\nTo start implementation, use the blueprint at:")
        print(f"  {results['files']['blueprint']}")
        
    except Exception as e:
        logger.error(f"Deep research failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()