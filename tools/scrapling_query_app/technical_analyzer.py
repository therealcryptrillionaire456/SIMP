"""
Technical content analyzer for detecting and extracting source code, APIs, and technical specifications.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class CodeSnippet:
    """A detected code snippet."""
    language: str
    code: str
    lines: int
    context: str  # Surrounding text/description
    url: str
    score: float  # 0-1 relevance score


@dataclass
class TechnicalSpec:
    """Technical specification extracted from content."""
    spec_type: str  # e.g., "model_architecture", "api_endpoint", "parameters"
    name: str
    value: str
    unit: Optional[str]
    confidence: float


@dataclass
class APIDefinition:
    """API endpoint definition."""
    method: str  # GET, POST, etc.
    endpoint: str
    description: str
    parameters: List[Dict[str, str]]
    response_format: Optional[str]


class TechnicalAnalyzer:
    """Analyzes content for technical details, source code, and specifications."""
    
    def __init__(self):
        self.code_patterns = {
            'python': [
                (r'```python\s*(.*?)```', re.DOTALL),
                (r'```py\s*(.*?)```', re.DOTALL),
                (r'import\s+\w+|def\s+\w+|class\s+\w+|print\(', re.IGNORECASE),
            ],
            'javascript': [
                (r'```javascript\s*(.*?)```', re.DOTALL),
                (r'```js\s*(.*?)```', re.DOTALL),
                (r'function\s+\w+|const\s+\w+|let\s+\w+|console\.log', re.IGNORECASE),
            ],
            'typescript': [
                (r'```typescript\s*(.*?)```', re.DOTALL),
                (r'```ts\s*(.*?)```', re.DOTALL),
                (r'interface\s+\w+|type\s+\w+|export\s+', re.IGNORECASE),
            ],
            'java': [
                (r'```java\s*(.*?)```', re.DOTALL),
                (r'public\s+class|private\s+\w+|System\.out\.println', re.IGNORECASE),
            ],
            'cpp': [
                (r'```cpp\s*(.*?)```', re.DOTALL),
                (r'```c\+\+\s*(.*?)```', re.DOTALL),
                (r'#include\s+<.*?>|std::|cout\s*<<', re.IGNORECASE),
            ],
            'bash': [
                (r'```bash\s*(.*?)```', re.DOTALL),
                (r'```sh\s*(.*?)```', re.DOTALL),
                (r'#!/bin/bash|#!/bin/sh|curl\s+|wget\s+', re.IGNORECASE),
            ],
            'json': [
                (r'```json\s*(.*?)```', re.DOTALL),
                (r'\{\s*"[^"]+"\s*:', re.DOTALL),
            ],
            'yaml': [
                (r'```yaml\s*(.*?)```', re.DOTALL),
                (r'```yml\s*(.*?)```', re.DOTALL),
                (r'apiVersion:|kind:|metadata:', re.IGNORECASE),
            ],
            'dockerfile': [
                (r'```dockerfile\s*(.*?)```', re.DOTALL),
                (r'FROM\s+\w+|RUN\s+|COPY\s+|EXPOSE\s+', re.IGNORECASE),
            ],
            'markdown': [
                (r'```markdown\s*(.*?)```', re.DOTALL),
                (r'#+\s+.*?\n|=+\s*\n|-+\s*\n', re.MULTILINE),
            ]
        }
        
        self.tech_spec_patterns = {
            'model_parameters': [
                (r'(\d+(?:\.\d+)?)\s*(billion|b|trillion|t|million|m)\s*parameters?', re.IGNORECASE),
                (r'parameter(?:s| count)?[:\s]+(\d+(?:\.\d+)?)\s*(b|t|m|billion|trillion|million)', re.IGNORECASE),
            ],
            'training_data': [
                (r'(\d+(?:\.\d+)?)\s*(billion|b|trillion|t|million|m)\s*tokens?', re.IGNORECASE),
                (r'training data[:\s]+(\d+(?:\.\d+)?)\s*(tokens|examples|samples)', re.IGNORECASE),
            ],
            'context_length': [
                (r'(\d+(?:,\d+)*)\s*token context', re.IGNORECASE),
                (r'context length[:\s]+(\d+(?:,\d+)*)\s*tokens?', re.IGNORECASE),
            ],
            'model_size': [
                (r'(\d+(?:\.\d+)?)\s*(GB|gb|TB|tb|MB|mb)\s*model', re.IGNORECASE),
                (r'model size[:\s]+(\d+(?:\.\d+)?)\s*(GB|TB|MB)', re.IGNORECASE),
            ],
            'api_endpoint': [
                (r'(GET|POST|PUT|DELETE|PATCH)\s+([/\w-]+(?:\{[\w-]+\})?)', re.IGNORECASE),
                (r'endpoint[:\s]+([/\w-]+(?:\{[\w-]+\})?)', re.IGNORECASE),
            ],
            'github_repo': [
                (r'github\.com/([\w-]+/[\w-]+(?:/[\w-]+)*)', re.IGNORECASE),
                (r'https://github\.com/([\w-]+/[\w-]+)', re.IGNORECASE),
            ],
            'arxiv_paper': [
                (r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+v?\d*)', re.IGNORECASE),
                (r'arXiv:(\d+\.\d+v?\d*)', re.IGNORECASE),
            ],
            'benchmark_score': [
                (r'(MMLU|GSM8K|HumanEval|HellaSwag)[\s:=]+([\d.]+)%?', re.IGNORECASE),
                (r'score[:\s]+([\d.]+)%?\s+on\s+(\w+)', re.IGNORECASE),
            ]
        }
    
    def analyze_content(self, text: str, url: str = None) -> Dict[str, Any]:
        """Analyze text for technical content."""
        logger.info(f"Analyzing technical content from {url or 'unknown source'}")
        
        analysis = {
            'code_snippets': [],
            'technical_specs': [],
            'api_definitions': [],
            'github_repos': [],
            'arxiv_papers': [],
            'has_source_code': False,
            'has_technical_specs': False,
            'has_api_docs': False,
            'overall_technical_score': 0.0
        }
        
        # Extract code snippets
        code_snippets = self.extract_code_snippets(text, url)
        analysis['code_snippets'] = code_snippets
        analysis['has_source_code'] = len(code_snippets) > 0
        
        # Extract technical specifications
        tech_specs = self.extract_technical_specs(text)
        analysis['technical_specs'] = tech_specs
        analysis['has_technical_specs'] = len(tech_specs) > 0
        
        # Extract API definitions
        api_defs = self.extract_api_definitions(text)
        analysis['api_definitions'] = api_defs
        analysis['has_api_docs'] = len(api_defs) > 0
        
        # Extract GitHub repos
        github_repos = self.extract_github_repos(text)
        analysis['github_repos'] = github_repos
        
        # Extract arXiv papers
        arxiv_papers = self.extract_arxiv_papers(text)
        analysis['arxiv_papers'] = arxiv_papers
        
        # Calculate overall technical score
        analysis['overall_technical_score'] = self.calculate_technical_score(
            code_snippets, tech_specs, api_defs
        )
        
        return analysis
    
    def extract_code_snippets(self, text: str, url: str = None) -> List[CodeSnippet]:
        """Extract code snippets from text."""
        snippets = []
        
        for lang, patterns in self.code_patterns.items():
            for pattern, flags in patterns:
                try:
                    matches = re.findall(pattern, text, flags)
                    for match in matches:
                        if isinstance(match, tuple):
                            code = match[0] if match else ""
                        else:
                            code = match
                        
                        # Clean up code
                        code = code.strip()
                        if not code or len(code) < 10:  # Minimum length
                            continue
                        
                        # Calculate lines
                        lines = code.count('\n') + 1
                        
                        # Find context (text before the code)
                        context_start = text.find(code) - 200
                        if context_start < 0:
                            context_start = 0
                        context = text[context_start:text.find(code)].strip()
                        
                        # Calculate relevance score
                        score = self._calculate_code_relevance(code, lang)
                        
                        snippet = CodeSnippet(
                            language=lang,
                            code=code,
                            lines=lines,
                            context=context[:500],  # Limit context length
                            url=url or '',
                            score=score
                        )
                        snippets.append(snippet)
                        
                except Exception as e:
                    logger.debug(f"Error extracting {lang} code: {e}")
        
        # Deduplicate similar snippets
        unique_snippets = []
        seen_hashes = set()
        
        for snippet in snippets:
            # Create simple hash of first 100 chars
            snippet_hash = hash(snippet.code[:100])
            if snippet_hash not in seen_hashes:
                seen_hashes.add(snippet_hash)
                unique_snippets.append(snippet)
        
        return unique_snippets
    
    def extract_technical_specs(self, text: str) -> List[TechnicalSpec]:
        """Extract technical specifications from text."""
        specs = []
        
        for spec_type, patterns in self.tech_spec_patterns.items():
            for pattern, flags in patterns:
                try:
                    matches = re.findall(pattern, text, flags)
                    for match in matches:
                        if isinstance(match, tuple):
                            if len(match) == 2:
                                value, unit = match
                                name = f"{spec_type}_{value}"
                            else:
                                continue
                        else:
                            value = match
                            unit = None
                            name = f"{spec_type}_{value}"
                        
                        # Clean up
                        value = str(value).strip()
                        if unit:
                            unit = str(unit).strip().lower()
                        
                        # Calculate confidence based on context
                        confidence = self._calculate_spec_confidence(text, match, spec_type)
                        
                        spec = TechnicalSpec(
                            spec_type=spec_type,
                            name=name,
                            value=value,
                            unit=unit,
                            confidence=confidence
                        )
                        specs.append(spec)
                        
                except Exception as e:
                    logger.debug(f"Error extracting {spec_type} specs: {e}")
        
        return specs
    
    def extract_api_definitions(self, text: str) -> List[APIDefinition]:
        """Extract API definitions from text."""
        api_defs = []
        
        # Look for API documentation patterns
        api_sections = re.split(r'(?:API|Endpoints|Routes)\s*[:]?\s*\n', text, re.IGNORECASE)
        
        for section in api_sections[1:]:  # Skip first section (before API heading)
            # Look for method + endpoint patterns
            method_patterns = [
                (r'(GET|POST|PUT|DELETE|PATCH)\s+([/\w-]+(?:\{[\w-]+\})?)', re.IGNORECASE),
                (r'Endpoint:\s*([/\w-]+(?:\{[\w-]+\})?)\s*\((GET|POST|PUT|DELETE|PATCH)\)', re.IGNORECASE),
            ]
            
            for pattern, flags in method_patterns:
                matches = re.findall(pattern, section, flags)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        if match[0] in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                            method, endpoint = match[0], match[1]
                        else:
                            endpoint, method = match[0], match[1]
                        
                        # Extract description (next few lines)
                        desc_start = section.find(match[0] if isinstance(match, str) else match[0])
                        description = section[desc_start:desc_start+500].split('\n')[0].strip()
                        
                        # Extract parameters
                        params = []
                        param_patterns = [
                            r'parameter[:\s]+(\w+)\s*[:\-]\s*(.*?)(?:\n|$)',
                            r'(\w+)\s*[:\-]\s*(required|optional).*?(?:\n|$)',
                        ]
                        
                        for param_pattern in param_patterns:
                            param_matches = re.findall(param_pattern, section, re.IGNORECASE)
                            for param_match in param_matches:
                                if isinstance(param_match, tuple) and len(param_match) >= 2:
                                    param_name, param_desc = param_match[0], param_match[1]
                                    params.append({
                                        'name': param_name,
                                        'description': param_desc,
                                        'required': 'required' in param_desc.lower()
                                    })
                        
                        api_def = APIDefinition(
                            method=method.upper(),
                            endpoint=endpoint,
                            description=description[:200],
                            parameters=params[:10],  # Limit to 10 params
                            response_format=None  # Could extract from "Response:" patterns
                        )
                        api_defs.append(api_def)
        
        return api_defs
    
    def extract_github_repos(self, text: str) -> List[str]:
        """Extract GitHub repository URLs from text."""
        repos = []
        
        patterns = [
            r'github\.com/([\w-]+/[\w-]+(?:/[\w-]+)*)',
            r'https://github\.com/([\w-]+/[\w-]+)',
            r'git@github\.com:([\w-]+/[\w-]+)\.git',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                repo = match.strip('/')
                if repo and repo not in repos:
                    repos.append(repo)
        
        return repos
    
    def extract_arxiv_papers(self, text: str) -> List[str]:
        """Extract arXiv paper IDs from text."""
        papers = []
        
        patterns = [
            r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+v?\d*)',
            r'arXiv:(\d+\.\d+v?\d*)',
            r'arxiv\s*[:\-]\s*(\d+\.\d+v?\d*)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                paper_id = match.strip()
                if paper_id and paper_id not in papers:
                    papers.append(paper_id)
        
        return papers
    
    def _calculate_code_relevance(self, code: str, language: str) -> float:
        """Calculate relevance score for code snippet."""
        score = 0.0
        
        # Score based on length (longer code is more relevant)
        length_score = min(len(code) / 1000, 1.0)  # Cap at 1.0 for 1000+ chars
        score += length_score * 0.3
        
        # Score based on language (some are more relevant for ML/AI)
        lang_scores = {
            'python': 1.0,
            'bash': 0.8,
            'dockerfile': 0.7,
            'yaml': 0.6,
            'json': 0.5,
            'javascript': 0.4,
            'typescript': 0.4,
            'java': 0.3,
            'cpp': 0.3,
            'markdown': 0.2,
        }
        lang_score = lang_scores.get(language, 0.1)
        score += lang_score * 0.3
        
        # Score based on content (look for ML/AI related terms)
        ml_keywords = [
            'transformers', 'tensorflow', 'pytorch', 'torch', 'numpy', 'pandas',
            'model', 'train', 'inference', 'embedding', 'token', 'parameter',
            'gradient', 'loss', 'optimizer', 'dataset', 'dataloader',
            'huggingface', 'openai', 'anthropic', 'claude', 'gpt', 'llm',
            'neural', 'network', 'layer', 'activation', 'backpropagation'
        ]
        
        keyword_count = 0
        code_lower = code.lower()
        for keyword in ml_keywords:
            if keyword in code_lower:
                keyword_count += 1
        
        keyword_score = min(keyword_count / 10, 1.0)
        score += keyword_score * 0.4
        
        return min(score, 1.0)
    
    def _calculate_spec_confidence(self, text: str, match: Any, spec_type: str) -> float:
        """Calculate confidence for extracted specification."""
        confidence = 0.5  # Base confidence
        
        # Check if match is in a technical context
        match_str = str(match[0] if isinstance(match, tuple) else match)
        match_pos = text.find(match_str)
        
        if match_pos > 0:
            # Look at surrounding context
            context_start = max(0, match_pos - 100)
            context_end = min(len(text), match_pos + len(match_str) + 100)
            context = text[context_start:context_end].lower()
            
            # Technical context indicators
            tech_indicators = [
                'parameter', 'specification', 'configuration', 'setting',
                'requires', 'must be', 'should be', 'default', 'value',
                'size', 'length', 'count', 'number', 'capacity'
            ]
            
            for indicator in tech_indicators:
                if indicator in context:
                    confidence += 0.1
            
            # Cap at 1.0
            confidence = min(confidence, 1.0)
        
        return confidence
    
    def calculate_technical_score(self, code_snippets: List[CodeSnippet],
                                 tech_specs: List[TechnicalSpec],
                                 api_defs: List[APIDefinition]) -> float:
        """Calculate overall technical score for content."""
        score = 0.0
        
        # Score from code snippets
        if code_snippets:
            avg_code_score = sum(s.score for s in code_snippets) / len(code_snippets)
            score += avg_code_score * 0.4
        
        # Score from technical specs
        if tech_specs:
            avg_spec_confidence = sum(s.confidence for s in tech_specs) / len(tech_specs)
            score += avg_spec_confidence * 0.3
        
        # Score from API definitions
        if api_defs:
            # Having API docs is highly technical
            score += 0.3
        
        # Bonus for having multiple technical elements
        element_count = len(code_snippets) + len(tech_specs) + len(api_defs)
        if element_count > 5:
            score += 0.1
        if element_count > 10:
            score += 0.1
        
        return min(score, 1.0)
    
    def generate_technical_report(self, analysis: Dict[str, Any]) -> str:
        """Generate a technical report from analysis."""
        report = []
        
        report.append("# Technical Content Analysis Report")
        report.append(f"Overall Technical Score: {analysis['overall_technical_score']:.2%}")
        report.append(f"Has Source Code: {'Yes' if analysis['has_source_code'] else 'No'}")
        report.append(f"Has Technical Specs: {'Yes' if analysis['has_technical_specs'] else 'No'}")
        report.append(f"Has API Docs: {'Yes' if analysis['has_api_docs'] else 'No'}")
        
        # Code snippets
        if analysis['code_snippets']:
            report.append("\n## Code Snippets Found")
            report.append(f"Total snippets: {len(analysis['code_snippets'])}")
            
            by_language = {}
            for snippet in analysis['code_snippets']:
                by_language.setdefault(snippet.language, []).append(snippet)
            
            for lang, snippets in by_language.items():
                report.append(f"\n### {lang.title()} ({len(snippets)} snippets)")
                for i, snippet in enumerate(snippets[:3]):  # Show top 3 per language
                    report.append(f"\n#### Snippet {i+1} (Score: {snippet.score:.2%})")
                    report.append(f"Lines: {snippet.lines}")
                    report.append(f"Context: {snippet.context[:200]}...")
                    report.append("```" + lang)
                    report.append(snippet.code[:500] + ("..." if len(snippet.code) > 500 else ""))
                    report.append("```")
        
        # Technical specifications
        if analysis['technical_specs']:
            report.append("\n## Technical Specifications")
            
            by_type = {}
            for spec in analysis['technical_specs']:
                by_type.setdefault(spec.spec_type, []).append(spec)
            
            for spec_type, specs in by_type.items():
                report.append(f"\n### {spec_type.replace('_', ' ').title()}")
                for spec in specs[:5]:  # Show top 5 per type
                    unit_str = f" {spec.unit}" if spec.unit else ""
                    report.append(f"- {spec.name}: {spec.value}{unit_str} (Confidence: {spec.confidence:.2%})")
        
        # API definitions
        if analysis['api_definitions']:
            report.append("\n## API Definitions")
            for i, api_def in enumerate(analysis['api_definitions'][:5]):  # Show top 5
                report.append(f"\n### API {i+1}: {api_def.method} {api_def.endpoint}")
                report.append(f"Description: {api_def.description}")
                if api_def.parameters:
                    report.append("Parameters:")
                    for param in api_def.parameters:
                        req = " (required)" if param.get('required') else ""
                        report.append(f"  - {param['name']}: {param['description']}{req}")
        
        # GitHub repositories
        if analysis['github_repos']:
            report.append("\n## GitHub Repositories")
            for repo in analysis['github_repos'][:10]:  # Show top 10
                report.append(f"- https://github.com/{repo}")
        
        # arXiv papers
        if analysis['arxiv_papers']:
            report.append("\n## arXiv Papers")
            for paper_id in analysis['arxiv_papers'][:10]:  # Show top 10
                report.append(f"- https://arxiv.org/abs/{paper_id}")
        
        return "\n".join(report)