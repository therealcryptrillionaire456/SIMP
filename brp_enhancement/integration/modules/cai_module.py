#!/usr/bin/env python3
"""
CAI (Cybersecurity AI) integration module for BRP.
Provides AI security evaluation and prompt injection defense capabilities.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import logging

# Add CAI repository to path for potential imports
cai_path = Path(__file__).parent.parent.parent / "repos" / "CAI"
if cai_path.exists():
    sys.path.insert(0, str(cai_path))

from .base_module import IntelligenceModule

logger = logging.getLogger(__name__)

class CAIModule(IntelligenceModule):
    """CAI integration module for AI security intelligence."""
    
    def __init__(self):
        super().__init__("cai", "CAI")
        self.repo_path = cai_path
        self.ai_security_models = {}
        self.prompt_injection_patterns = self._load_prompt_injection_patterns()
        
    def _load_prompt_injection_patterns(self) -> List[Dict[str, Any]]:
        """Load prompt injection detection patterns."""
        # These are based on common prompt injection techniques
        return [
            {
                'name': 'ignore_previous',
                'pattern': r'(?i)ignore (?:previous|all )?instructions',
                'description': 'Attempt to ignore previous instructions'
            },
            {
                'name': 'role_playing',
                'pattern': r'(?i)you are (?:now|acting as)',
                'description': 'Attempt to change AI role/identity'
            },
            {
                'name': 'system_prompt_leak',
                'pattern': r'(?i)(?:system|initial) prompt',
                'description': 'Attempt to access system prompt'
            },
            {
                'name': 'jailbreak',
                'pattern': r'(?i)jailbreak|break.*character',
                'description': 'Jailbreak attempt'
            },
            {
                'name': 'data_extraction',
                'pattern': r'(?i)output.*(?:password|key|secret|token)',
                'description': 'Attempt to extract sensitive data'
            },
            {
                'name': 'code_execution',
                'pattern': r'(?i)execute.*code|run.*command',
                'description': 'Attempt to execute code'
            }
        ]
    
    def initialize(self) -> bool:
        """Initialize CAI module."""
        try:
            # Check if CAI repository exists
            if not self.repo_path.exists():
                logger.warning(f"CAI repository not found at {self.repo_path}")
                self.available = False
                return False
            
            # Check for key CAI files
            required_files = ['README.md', 'tools/', 'tests/']
            missing_files = []
            
            for file in required_files:
                file_path = self.repo_path / file
                if not file_path.exists():
                    missing_files.append(file)
            
            if missing_files:
                logger.warning(f"Missing CAI files: {missing_files}")
                # We'll still try to initialize with partial capabilities
            
            # Initialize capabilities
            self.capabilities = [
                {
                    'name': 'prompt_injection_detection',
                    'description': 'Detect prompt injection attempts in AI interactions',
                    'operations': ['analyze_prompt', 'detect_injection']
                },
                {
                    'name': 'ai_security_assessment',
                    'description': 'Assess AI system security posture',
                    'operations': ['assess_security', 'evaluate_risks']
                },
                {
                    'name': 'threat_intelligence',
                    'description': 'Provide AI-specific threat intelligence',
                    'operations': ['analyze_threat', 'generate_intel']
                },
                {
                    'name': 'security_benchmarking',
                    'description': 'Benchmark AI security against CAIBench standards',
                    'operations': ['run_benchmark', 'compare_results']
                }
            ]
            
            self.available = True
            self.initialized = True
            
            logger.info(f"CAI module initialized with {len(self.capabilities)} capabilities")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize CAI module: {e}")
            self.available = False
            return False
    
    def check_availability(self) -> bool:
        """Check if CAI module is available."""
        return self.repo_path.exists() and any(self.repo_path.iterdir())
    
    def get_capabilities(self) -> List[Dict[str, Any]]:
        """Get CAI module capabilities."""
        return self.capabilities
    
    def execute(self, operation: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute CAI operation."""
        if not self.initialized:
            return {'error': 'CAI module not initialized'}
        
        operation_handlers = {
            'analyze_prompt': self._analyze_prompt,
            'detect_injection': self._detect_injection,
            'assess_security': self._assess_security,
            'evaluate_risks': self._evaluate_risks,
            'analyze_threat': self._analyze_threat,
            'generate_intel': self._generate_intelligence,
            'run_benchmark': self._run_benchmark,
            'compare_results': self._compare_results
        }
        
        handler = operation_handlers.get(operation)
        if not handler:
            return {'error': f'Unknown operation: {operation}'}
        
        try:
            return handler(parameters)
        except Exception as e:
            logger.error(f"Error executing CAI operation {operation}: {e}")
            return {'error': str(e)}
    
    def gather_intelligence(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Gather AI security intelligence."""
        query_type = query.get('type', 'general')
        
        if query_type == 'prompt_injection':
            return self._analyze_prompt_injection_intel(query)
        elif query_type == 'ai_threats':
            return self._gather_ai_threat_intel(query)
        elif query_type == 'security_trends':
            return self._gather_security_trends(query)
        else:
            return {
                'error': f'Unknown intelligence query type: {query_type}',
                'available_types': ['prompt_injection', 'ai_threats', 'security_trends']
            }
    
    def analyze_patterns(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in AI security data."""
        results = {
            'total_samples': len(data),
            'prompt_injection_findings': [],
            'security_patterns': [],
            'recommendations': []
        }
        
        for item in data:
            if 'content' in item:
                content = str(item['content'])
                
                # Check for prompt injection patterns
                injection_result = self._detect_prompt_injection(content)
                if injection_result['detected']:
                    results['prompt_injection_findings'].append({
                        'content_sample': content[:100] + '...' if len(content) > 100 else content,
                        'pattern': injection_result['pattern'],
                        'confidence': injection_result['confidence']
                    })
        
        # Generate recommendations based on findings
        if results['prompt_injection_findings']:
            results['recommendations'].append({
                'type': 'prompt_injection_protection',
                'priority': 'high',
                'action': 'Implement prompt injection detection and filtering',
                'details': f"Found {len(results['prompt_injection_findings'])} potential injection attempts"
            })
        
        return results
    
    def plan_response(self, threat: Dict[str, Any]) -> Dict[str, Any]:
        """Plan response to AI security threat."""
        threat_type = threat.get('type', 'unknown')
        
        response_plan = {
            'threat_type': threat_type,
            'immediate_actions': [],
            'medium_term_actions': [],
            'long_term_actions': [],
            'monitoring_recommendations': []
        }
        
        if threat_type == 'prompt_injection':
            response_plan['immediate_actions'].extend([
                'Isolate affected AI system',
                'Review and filter malicious prompts',
                'Update prompt filtering rules'
            ])
            response_plan['medium_term_actions'].extend([
                'Implement multi-layer prompt validation',
                'Train AI on adversarial examples',
                'Deploy CAI-based monitoring'
            ])
            response_plan['long_term_actions'].extend([
                'Develop custom prompt injection detection models',
                'Integrate with security information and event management (SIEM)',
                'Establish AI security incident response team'
            ])
        
        elif threat_type == 'ai_model_theft':
            response_plan['immediate_actions'].extend([
                'Revoke API keys and access tokens',
                'Monitor for model exfiltration',
                'Alert legal and security teams'
            ])
        
        elif threat_type == 'training_data_poisoning':
            response_plan['immediate_actions'].extend([
                'Pause model training',
                'Analyze training data for anomalies',
                'Restore from clean backup'
            ])
        
        return response_plan
    
    def _analyze_prompt(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze prompt for security issues."""
        prompt = parameters.get('prompt', '')
        
        if not prompt:
            return {'error': 'No prompt provided'}
        
        # Analyze prompt using multiple techniques
        injection_analysis = self._detect_prompt_injection(prompt)
        security_analysis = self._analyze_prompt_security(prompt)
        
        return {
            'prompt_length': len(prompt),
            'injection_analysis': injection_analysis,
            'security_analysis': security_analysis,
            'risk_score': self._calculate_prompt_risk_score(injection_analysis, security_analysis),
            'recommendations': self._generate_prompt_recommendations(injection_analysis, security_analysis)
        }
    
    def _detect_injection(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Detect prompt injection attempts."""
        content = parameters.get('content', '')
        
        if not content:
            return {'error': 'No content provided'}
        
        return self._detect_prompt_injection(content)
    
    def _detect_prompt_injection(self, content: str) -> Dict[str, Any]:
        """Detect prompt injection in content."""
        content_lower = content.lower()
        findings = []
        
        for pattern in self.prompt_injection_patterns:
            import re
            if re.search(pattern['pattern'], content_lower):
                findings.append({
                    'pattern_name': pattern['name'],
                    'description': pattern['description'],
                    'confidence': 0.8  # Base confidence
                })
        
        # Calculate overall confidence
        confidence = min(0.95, 0.3 + len(findings) * 0.2) if findings else 0.0
        
        return {
            'detected': len(findings) > 0,
            'findings': findings,
            'confidence': confidence,
            'content_sample': content[:200] + '...' if len(content) > 200 else content
        }
    
    def _analyze_prompt_security(self, prompt: str) -> Dict[str, Any]:
        """Analyze prompt security characteristics."""
        # Simple security analysis
        issues = []
        
        # Check for sensitive information requests
        sensitive_terms = ['password', 'secret', 'key', 'token', 'credential', 'private']
        for term in sensitive_terms:
            if term in prompt.lower():
                issues.append(f'Requests {term} information')
        
        # Check for code execution requests
        code_terms = ['execute', 'run', 'eval', 'exec', 'system', 'shell']
        for term in code_terms:
            if term in prompt.lower():
                issues.append(f'Requests code execution ({term})')
        
        # Check for role manipulation
        role_terms = ['act as', 'pretend to be', 'you are now', 'ignore your']
        for term in role_terms:
            if term in prompt.lower():
                issues.append(f'Attempts role manipulation ({term})')
        
        return {
            'issues_found': issues,
            'issue_count': len(issues),
            'prompt_complexity': len(prompt.split()),  # Word count as complexity proxy
            'security_level': 'high' if len(issues) == 0 else 'medium' if len(issues) < 3 else 'low'
        }
    
    def _calculate_prompt_risk_score(self, injection_analysis: Dict, security_analysis: Dict) -> float:
        """Calculate prompt risk score (0-1)."""
        base_score = 0.0
        
        # Injection findings contribute to risk
        if injection_analysis['detected']:
            base_score += 0.4 * injection_analysis['confidence']
        
        # Security issues contribute to risk
        base_score += min(0.3, security_analysis['issue_count'] * 0.1)
        
        # Complexity contributes to risk
        complexity_factor = min(0.3, security_analysis['prompt_complexity'] / 1000)
        base_score += complexity_factor
        
        return min(1.0, base_score)
    
    def _generate_prompt_recommendations(self, injection_analysis: Dict, security_analysis: Dict) -> List[str]:
        """Generate prompt security recommendations."""
        recommendations = []
        
        if injection_analysis['detected']:
            recommendations.append('REJECT: Prompt contains injection patterns')
            for finding in injection_analysis['findings']:
                recommendations.append(f"Pattern detected: {finding['pattern_name']}")
        
        if security_analysis['issue_count'] > 0:
            recommendations.append('REVIEW: Prompt requests sensitive actions')
            for issue in security_analysis['issues_found']:
                recommendations.append(f"Issue: {issue}")
        
        if security_analysis['prompt_complexity'] > 500:
            recommendations.append('MONITOR: Complex prompt may indicate sophisticated attack')
        
        if not recommendations:
            recommendations.append('ACCEPT: Prompt appears safe for processing')
        
        return recommendations
    
    def _assess_security(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Assess AI system security."""
        system_type = parameters.get('system_type', 'general_ai')
        
        # Basic security assessment based on system type
        assessments = {
            'general_ai': {
                'prompt_injection_protection': 'check_implementation',
                'model_access_control': 'verify_authentication',
                'data_privacy': 'review_data_handling',
                'api_security': 'test_endpoints'
            },
            'chatbot': {
                'conversation_isolation': 'ensure_session_separation',
                'user_input_validation': 'implement_sanitization',
                'content_filtering': 'deploy_moderation',
                'rate_limiting': 'prevent_abuse'
            },
            'code_generator': {
                'code_sandboxing': 'isolate_execution',
                'output_validation': 'review_generated_code',
                'resource_limits': 'prevent_exhaustion',
                'dependency_checking': 'scan_for_vulnerabilities'
            }
        }
        
        assessment = assessments.get(system_type, assessments['general_ai'])
        
        return {
            'system_type': system_type,
            'assessment_areas': assessment,
            'recommended_checks': list(assessment.values()),
            'security_score': self._calculate_security_score(assessment),
            'next_steps': [
                'Implement missing security controls',
                'Regular security testing',
                'Monitor for new threats'
            ]
        }
    
    def _calculate_security_score(self, assessment: Dict[str, str]) -> float:
        """Calculate security score based on assessment."""
        # Simple scoring based on assessment completeness
        check_status = {
            'check_implementation': 0.8,
            'verify_authentication': 0.7,
            'review_data_handling': 0.6,
            'test_endpoints': 0.9,
            'ensure_session_separation': 0.7,
            'implement_sanitization': 0.8,
            'deploy_moderation': 0.6,
            'prevent_abuse': 0.9,
            'isolate_execution': 0.8,
            'review_generated_code': 0.5,
            'prevent_exhaustion': 0.7,
            'scan_for_vulnerabilities': 0.6
        }
        
        scores = [check_status.get(check, 0.5) for check in assessment.values()]
        return sum(scores) / len(scores) if scores else 0.5
    
    def _evaluate_risks(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate AI security risks."""
        return {
            'common_risks': [
                {'risk': 'Prompt Injection', 'severity': 'high', 'mitigation': 'Input validation, prompt filtering'},
                {'risk': 'Model Theft', 'severity': 'high', 'mitigation': 'Access control, API security'},
                {'risk': 'Data Poisoning', 'severity': 'medium', 'mitigation': 'Data validation, anomaly detection'},
                {'risk': 'Model Inversion', 'severity': 'medium', 'mitigation': 'Output filtering, privacy protection'},
                {'risk': 'Membership Inference', 'severity': 'low', 'mitigation': 'Differential privacy, access logs'}
            ],
            'risk_assessment': 'AI systems face unique security challenges requiring specialized defenses',
            'recommended_actions': [
                'Implement CAI-based monitoring',
                'Regular security assessments',
                'Adversarial testing',
                'Security training for AI teams'
            ]
        }
    
    def _analyze_threat(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze AI security threat."""
        threat_data = parameters.get('threat_data', {})
        
        return {
            'threat_analysis': 'AI-specific threats require specialized detection and response',
            'indicators': [
                'Unusual prompt patterns',
                'Model performance degradation',
                'Unexpected output behavior',
                'Increased resource consumption'
            ],
            'response_recommendations': [
                'Isolate affected components',
                'Analyze with CAI tools',
                'Update security controls',
                'Monitor for similar threats'
            ],
            'threat_intelligence': 'CAI provides frameworks for AI threat analysis and response'
        }
    
    def _generate_intelligence(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI security intelligence."""
        intel_type = parameters.get('intel_type', 'current_threats')
        
        intelligence = {
            'current_threats': {
                'description': 'Current AI security threat landscape',
                'threats': [
                    'Sophisticated prompt injection campaigns',
                    'AI model theft for competitive advantage',
                    'Adversarial attacks on computer vision systems',
                    'Data poisoning in training pipelines'
                ],
                'sources': ['CAI research', 'Security advisories', 'Threat intelligence feeds']
            },
            'emerging_trends': {
                'description': 'Emerging trends in AI security',
                'trends': [
                    'AI-powered security tools',
                    'Federated learning security challenges',
                    'Quantum machine learning threats',
                    'AI in cyber warfare'
                ]
            },
            'defense_innovations': {
                'description': 'Innovations in AI defense',
                'innovations': [
                    'Adversarial training techniques',
                    'Explainable AI for security',
                    'AI-powered threat hunting',
                    'Automated security testing'
                ]
            }
        }
        
        return intelligence.get(intel_type, {'error': f'Unknown intelligence type: {intel_type}'})
    
    def _run_benchmark(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Run security benchmark (simulated)."""
        benchmark_type = parameters.get('benchmark', 'cai_basic')
        
        benchmarks = {
            'cai_basic': {
                'name': 'CAI Basic Security Benchmark',
                'tests': [
                    {'test': 'Prompt Injection Resistance', 'score': 85, 'max_score': 100},
                    {'test': 'Model Access Control', 'score': 90, 'max_score': 100},
                    {'test': 'Data Privacy Compliance', 'score': 75, 'max_score': 100},
                    {'test': 'API Security', 'score': 88, 'max_score': 100}
                ],
                'overall_score': 84.5,
                'rating': 'Good',
                'recommendations': ['Improve data privacy controls', 'Enhance prompt filtering']
            },
            'ai_security_comprehensive': {
                'name': 'AI Security Comprehensive Assessment',
                'tests': [
                    {'test': 'Adversarial Robustness', 'score': 70, 'max_score': 100},
                    {'test': 'Privacy Preservation', 'score': 65, 'max_score': 100},
                    {'test': 'Explainability', 'score': 80, 'max_score': 100},
                    {'test': 'Fairness and Bias', 'score': 75, 'max_score': 100},
                    {'test': 'Security Controls', 'score': 85, 'max_score': 100}
                ],
                'overall_score': 75.0,
                'rating': 'Adequate',
                'recommendations': ['Focus on adversarial training', 'Implement privacy-enhancing technologies']
            }
        }
        
        return benchmarks.get(benchmark_type, {'error': f'Unknown benchmark: {benchmark_type}'})
    
    def _compare_results(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Compare benchmark results."""
        results_a = parameters.get('results_a', {})
        results_b = parameters.get('results_b', {})
        
        # Simple comparison
        score_a = results_a.get('overall_score', 0)
        score_b = results_b.get('overall_score', 0)
        
        return {
            'comparison': {
                'system_a_score': score_a,
                'system_b_score': score_b,
                'difference': abs(score_a - score_b),
                'better_system': 'A' if score_a > score_b else 'B' if score_b > score_a else 'Equal'
            },
            'analysis': f"System {'A' if score_a > score_b else 'B'} has better security posture",
            'improvement_areas': self._identify_improvement_areas(results_a, results_b)
        }
    
    def _identify_improvement_areas(self, results_a: Dict, results_b: Dict) -> List[str]:
        """Identify areas for improvement based on benchmark comparison."""
        areas = []
        
        tests_a = {t['test']: t['score'] for t in results_a.get('tests', [])}
        tests_b = {t['test']: t['score'] for t in results_b.get('tests', [])}
        
        for test_name, score_a in tests_a.items():
            score_b = tests_b.get(test_name)
            if score_b is not None:
                if score_a < score_b:
                    areas.append(f"Improve {test_name} (currently {score_a} vs {score_b})")
        
        return areas
    
    def _analyze_prompt_injection_intel(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze prompt injection intelligence."""
        return {
            'intelligence_type': 'prompt_injection',
            'current_trends': [
                'Multi-stage injection attacks becoming more common',
                'Use of encoded/obfuscated prompts increasing',
                'Attacks targeting specific AI models and applications'
            ],
            'detection_techniques': [
                'Pattern matching for known injection templates',
                'Behavioral analysis of AI responses',
                'Anomaly detection in prompt sequences'
            ],
            'defense_recommendations': [
                'Implement layered prompt validation',
                'Use AI to detect AI attacks',
                'Regular security testing with adversarial examples'
            ],
            'sources': ['CAI research papers', 'Security advisories', 'Threat intelligence']
        }
    
    def _gather_ai_threat_intel(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Gather AI threat intelligence."""
        return {
            'intelligence_type': 'ai_threats',
            'threat_categories': [
                {
                    'category': 'Model Attacks',
                    'threats': ['Model extraction', 'Model inversion', 'Membership inference'],
                    'impact': 'High',
                    'mitigation': 'Access controls, output filtering'
                },
                {
                    'category': 'Data Attacks',
                    'threats': ['Data poisoning', 'Training data extraction', 'Privacy attacks'],
                    'impact': 'Medium-High',
                    'mitigation': 'Data validation, differential privacy'
                },
                {
                    'category': 'Prompt Attacks',
                    'threats': ['Prompt injection', 'Jailbreaking', 'Role manipulation'],
                    'impact': 'Medium',
                    'mitigation': 'Input validation, prompt engineering'
                }
            ],
            'emerging_threats': [
                'AI-powered social engineering',
                'Autonomous attack agents',
                'Supply chain attacks on AI models'
            ]
        }
    
    def _gather_security_trends(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Gather AI security trends."""
        return {
            'intelligence_type': 'security_trends',
            'trends': [
                {
                    'trend': 'AI-Powered Security',
                    'description': 'Using AI to enhance security defenses',
                    'adoption': 'Growing rapidly',
                    'examples': ['AI threat detection', 'Automated vulnerability assessment']
                },
                {
                    'trend': 'Explainable AI for Security',
                    'description': 'Making AI security decisions transparent',
                    'adoption': 'Early stages',
                    'examples': ['Interpretable threat classifications', 'Auditable security decisions']
                },
                {
                    'trend': 'Federated Learning Security',
                    'description': 'Securing distributed AI training',
                    'adoption': 'Research focus',
                    'examples': ['Secure aggregation', 'Privacy-preserving updates']
                }
            ],
            'research_directions': [
                'Adversarial machine learning defenses',
                'Privacy-enhancing technologies for AI',
                'Secure multi-party computation for AI'
            ]
        }