#!/usr/bin/env python3
"""
Specialized research script for Anthropic Mythos/Glasswing/Capybara.
This script conducts comprehensive web research to gather all available information.
"""

import sys
import logging
import json
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.scrapling_query_app.enhanced_processor import run_mythos_research
from tools.scrapling_query_app.targeted_search import TargetedSearch, ResearchTopic
from tools.scrapling_query_app.technical_analyzer import TechnicalAnalyzer


def main():
    """Run comprehensive Mythos research."""
    print("=" * 80)
    print("ANTHROPIC MYTHOS / PROJECT GLASSWING / CAPYBARA RESEARCH")
    print("=" * 80)
    print("\nThis tool will conduct comprehensive web research to gather all available")
    print("information about Anthropic's Mythos LLM (also known as Project Glasswing")
    print("or Capybara). The research will:")
    print("1. Search for official announcements and documentation")
    print("2. Look for technical papers and research")
    print("3. Find source code repositories")
    print("4. Extract technical specifications")
    print("5. Analyze capabilities and benchmarks")
    print("6. Gather community discussions")
    print("7. Generate comprehensive reports")
    print("\n" + "=" * 80)
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"data/mythos_research_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nOutput will be saved to: {output_dir}")
    
    try:
        # Run comprehensive research
        print("\n" + "=" * 80)
        print("STARTING RESEARCH...")
        print("=" * 80)
        
        results = run_mythos_research(str(output_dir))
        
        print("\n" + "=" * 80)
        print("RESEARCH COMPLETE!")
        print("=" * 80)
        
        # Generate additional analysis
        generate_additional_analysis(results, output_dir)
        
        # Create README
        create_readme(output_dir, results)
        
        print(f"\nAll research files saved to: {output_dir}")
        print("\nFiles created:")
        print(f"  - {results['files']['report']}")
        print(f"  - {results['files']['data']}")
        print(f"  - {results['files']['technical']}")
        print(f"  - {output_dir}/additional_analysis.json")
        print(f"  - {output_dir}/README.md")
        
        print("\n" + "=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print("1. Review the research report for key findings")
        print("2. Examine extracted technical specifications")
        print("3. Check GitHub repositories for source code")
        print("4. Read arXiv papers for technical details")
        print("5. Use the gathered information for your Mythos recreation project")
        
    except Exception as e:
        logger.error(f"Research failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def generate_additional_analysis(results: dict, output_dir: Path):
    """Generate additional analysis from research results."""
    logger.info("Generating additional analysis...")
    
    analysis = {
        'summary': {
            'total_queries': results['results']['total_queries'],
            'total_results': results['results']['total_results'],
            'total_content': results['results']['total_content'],
            'successful_extractions': len([c for c in results['results']['content'] if c.status == 'success']),
            'failed_extractions': len([c for c in results['results']['content'] if c.status == 'failed']),
            'research_timestamp': datetime.now().isoformat()
        },
        'top_domains': {},
        'content_types': {},
        'key_findings': []
    }
    
    # Analyze domains
    for result in results['results']['results']:
        try:
            from urllib.parse import urlparse
            domain = urlparse(result.url).netloc
            analysis['top_domains'][domain] = analysis['top_domains'].get(domain, 0) + 1
        except:
            pass
    
    # Analyze content types
    for content in results['results']['content']:
        if content.status == 'success':
            # Check content type by URL
            url = content.url.lower()
            if any(ext in url for ext in ['.pdf', '.pdf?']):
                analysis['content_types']['pdf'] = analysis['content_types'].get('pdf', 0) + 1
            elif 'arxiv.org' in url:
                analysis['content_types']['arxiv'] = analysis['content_types'].get('arxiv', 0) + 1
            elif 'github.com' in url:
                analysis['content_types']['github'] = analysis['content_types'].get('github', 0) + 1
            elif any(site in url for site in ['research.', 'paper', 'publication']):
                analysis['content_types']['research_paper'] = analysis['content_types'].get('research_paper', 0) + 1
            elif any(site in url for site in ['blog.', 'medium.com', 'dev.to']):
                analysis['content_types']['blog'] = analysis['content_types'].get('blog', 0) + 1
            elif any(site in url for site in ['news.', 'article']):
                analysis['content_types']['news'] = analysis['content_types'].get('news', 0) + 1
            else:
                analysis['content_types']['other'] = analysis['content_types'].get('other', 0) + 1
    
    # Extract key findings
    technical_analyzer = TechnicalAnalyzer()
    
    for content in results['results']['content']:
        if content.status == 'success' and content.text_content:
            try:
                # Look for key information
                text = content.text_content.lower()
                
                # Check for model specifications
                if any(term in text for term in ['parameters', 'training', 'architecture', 'model size']):
                    analysis['key_findings'].append({
                        'url': content.url,
                        'title': content.title,
                        'type': 'technical_spec',
                        'preview': content.text_content[:200] + '...'
                    })
                
                # Check for source code
                if any(term in text for term in ['github', 'repository', 'source code', 'implementation']):
                    analysis['key_findings'].append({
                        'url': content.url,
                        'title': content.title,
                        'type': 'source_code',
                        'preview': content.text_content[:200] + '...'
                    })
                
                # Check for benchmarks
                if any(term in text for term in ['benchmark', 'evaluation', 'performance', 'score']):
                    analysis['key_findings'].append({
                        'url': content.url,
                        'title': content.title,
                        'type': 'benchmark',
                        'preview': content.text_content[:200] + '...'
                    })
                
            except Exception as e:
                logger.debug(f"Error analyzing content: {e}")
    
    # Limit key findings
    analysis['key_findings'] = analysis['key_findings'][:20]
    
    # Save analysis
    analysis_file = output_dir / "additional_analysis.json"
    with open(analysis_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    logger.info(f"Additional analysis saved to: {analysis_file}")


def create_readme(output_dir: Path, results: dict):
    """Create a README file for the research output."""
    readme_content = f"""# Anthropic Mythos / Project Glasswing / Capybara Research

## Overview
This directory contains comprehensive web research about Anthropic's Mythos LLM 
(also known as Project Glasswing or Capybara). The research was conducted on 
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

## Research Summary
- **Total search queries executed**: {results['results']['total_queries']}
- **Unique search results found**: {results['results']['total_results']}
- **Content items extracted**: {results['results']['total_content']}
- **Successful extractions**: {len([c for c in results['results']['content'] if c.status == 'success'])}
- **Failed extractions**: {len([c for c in results['results']['content'] if c.status == 'failed'])}

## Files in this Directory

### 1. Research Report (`research_report_*.md`)
Comprehensive markdown report containing:
- Executive summary
- Technical specifications found
- Model capabilities and benchmarks
- Source code repositories
- Research papers
- Community discussions
- Detailed findings

### 2. Raw Research Data (`research_data_*.json`)
Structured JSON data containing all search results and extracted content.
Use this for programmatic analysis or to build your own tools.

### 3. Technical Analysis (`technical_analysis_*.json`)
Detailed technical analysis including:
- Code snippets found
- Technical specifications extracted
- API definitions
- GitHub repositories
- arXiv papers
- Technical relevance scores

### 4. Additional Analysis (`additional_analysis.json`)
Statistical analysis of the research including:
- Top domains found
- Content type distribution
- Key findings summary
- Research metrics

## How to Use This Research

### For Model Recreation
1. **Review technical specifications** in the research report
2. **Examine source code** from GitHub repositories
3. **Study research papers** for architecture details
4. **Analyze benchmarks** for performance targets

### For Further Research
1. **Use the raw data** to build custom analysis tools
2. **Follow the GitHub links** to access source code
3. **Read the arXiv papers** for in-depth technical details
4. **Check the community discussions** for user experiences

### For Development
1. **Implement based on specifications** found in the research
2. **Reference the architecture details** from technical papers
3. **Use the benchmarks** as performance goals
4. **Review the safety and alignment** research for responsible AI development

## Key Areas to Explore

### 1. Model Architecture
- Parameter count and model size
- Transformer architecture variations
- Training methodology
- Fine-tuning approaches

### 2. Capabilities
- Benchmark performance (MMLU, GSM8K, etc.)
- Specialized capabilities (coding, reasoning, etc.)
- Multimodal features (if any)
- Tool use and function calling

### 3. Safety & Alignment
- Constitutional AI approach
- Safety mitigations
- Alignment techniques
- Ethical considerations

### 4. Implementation
- Source code availability
- API design and endpoints
- Deployment requirements
- Integration examples

## Notes and Limitations

1. **Web scraping limitations**: Some sites may block automated access
2. **Information freshness**: Web content changes over time
3. **Source reliability**: Verify critical information from official sources
4. **Technical accuracy**: Cross-reference specifications with official documentation

## Next Steps

1. **Validate findings** with official Anthropic documentation
2. **Experiment with available code** from GitHub repositories
3. **Benchmark against existing models** using published metrics
4. **Contribute to the community** by sharing your implementation

## Contact
For questions about this research or the tools used, refer to the Scrapling Query Tool documentation.

---
*Generated by Scrapling Query Tool - Enhanced Research Module*
"""
    
    readme_file = output_dir / "README.md"
    with open(readme_file, 'w') as f:
        f.write(readme_content)
    
    logger.info(f"README created: {readme_file}")


if __name__ == "__main__":
    main()