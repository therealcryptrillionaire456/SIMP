#!/usr/bin/env python3
"""
Predictive Risk Scorer for Quantum Mode

Predicts trouble before it accumulates by analyzing:
- Retrieval patterns
- Verification results
- Framework mismatches
- Repeated failures
- ProjectX escalations
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
import statistics
from collections import defaultdict, Counter

# Import schema
from quantum_mode_schema import QuantumErrorCode

@dataclass
class RiskFactor:
    """A risk factor contributing to overall risk score."""
    factor_type: str
    value: Any
    weight: float
    description: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

@dataclass
class RiskAssessment:
    """Complete risk assessment for a task or session."""
    assessment_id: str
    task_id: Optional[str]
    trace_id: Optional[str]
    session_id: Optional[str]
    score: float  # 0.0 to 1.0
    risk_band: str  # low, medium, high, critical
    factors: List[RiskFactor]
    recommendations: List[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

class PredictiveRiskScorer:
    """
    Predictive risk scorer for Quantum Mode.
    
    Analyzes patterns to predict trouble before it accumulates.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.base_dir = Path(__file__).parent
        self.config = self.load_config(config_path)
        
        # Risk factor weights (from specification)
        self.factor_weights = {
            'retrieval_empty': 0.30,
            'retrieval_low_confidence': 0.20,
            'framework_mismatch': 0.20,
            'verification_failed': 0.25,
            'projectx_escalated': 0.15,
            'repeated_failure': 0.20,
            'high_latency': 0.10
        }
        
        # Risk bands
        self.risk_bands = {
            'low': (0.0, 0.29),
            'medium': (0.3, 0.59),
            'high': (0.6, 0.79),
            'critical': (0.8, 1.0)
        }
        
        # Actions by risk band
        self.actions_by_band = {
            'low': "continue and log",
            'medium': "continue cautiously and mark for review",
            'high': "escalate or require ProjectX review before finalize",
            'critical': "block executable path and escalate"
        }
        
        # History tracking
        self.task_history: Dict[str, List[Dict]] = defaultdict(list)
        self.error_history: List[Dict] = []
        self.risk_history: List[RiskAssessment] = []
        
        # Pattern detection
        self.failure_patterns = self._initialize_failure_patterns()
        
        print("Predictive Risk Scorer initialized")
    
    def load_config(self, config_path: Optional[Path]) -> Dict:
        """Load configuration from file or use defaults."""
        default_config = {
            'window_size': 50,  # Number of recent tasks to analyze
            'time_window_hours': 24,  # Time window for pattern analysis
            'high_latency_threshold_ms': 5000,  # 5 seconds
            'repeated_failure_threshold': 3,  # Same error 3 times
            'risk_update_frequency': 10,  # Update risk every 10 tasks
            'enable_pattern_detection': True,
            'enable_trend_analysis': True
        }
        
        if config_path and config_path.exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _initialize_failure_patterns(self) -> Dict[str, Dict]:
        """Initialize known failure patterns."""
        return {
            'retrieval_problems': {
                'description': 'Persistent retrieval issues',
                'indicators': [
                    'QMODE_RETRIEVAL_EMPTY',
                    'QMODE_RETRIEVAL_LOW_CONFIDENCE'
                ],
                'threshold': 3,  # 3 occurrences in window
                'risk_boost': 0.3
            },
            'framework_issues': {
                'description': 'Framework-related problems',
                'indicators': [
                    'QMODE_FRAMEWORK_UNSUPPORTED',
                    'QMODE_FRAMEWORK_MISMATCH'
                ],
                'threshold': 2,
                'risk_boost': 0.25
            },
            'execution_failures': {
                'description': 'Execution failures',
                'indicators': [
                    'QMODE_IMPORT_FAILURE',
                    'QMODE_SIMULATOR_FAILURE',
                    'QMODE_LOGIC_FAILURE'
                ],
                'threshold': 2,
                'risk_boost': 0.35
            },
            'safety_blocks': {
                'description': 'Safety-related blocks',
                'indicators': [
                    'QMODE_RESOURCE_LIMIT',
                    'QMODE_PROJECTX_BLOCK'
                ],
                'threshold': 1,  # Even one is serious
                'risk_boost': 0.4
            }
        }
    
    def assess_task_risk(self, task_data: Dict) -> RiskAssessment:
        """Assess risk for a single task."""
        import hashlib
        import time
        
        task_id = task_data.get('task_id', 'unknown')
        trace_id = task_data.get('trace_id')
        
        # Generate assessment ID
        assessment_id = f"risk_{hashlib.md5(f'{task_id}_{time.time()}'.encode()).hexdigest()[:8]}"
        
        # Collect risk factors
        factors = self._collect_risk_factors(task_data)
        
        # Calculate base score
        base_score = self._calculate_base_score(factors)
        
        # Apply pattern-based adjustments
        pattern_adjustment = self._detect_patterns(task_data, factors)
        adjusted_score = min(1.0, base_score + pattern_adjustment)
        
        # Determine risk band
        risk_band = self._determine_risk_band(adjusted_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(risk_band, factors)
        
        # Create assessment
        assessment = RiskAssessment(
            assessment_id=assessment_id,
            task_id=task_id,
            trace_id=trace_id,
            session_id=task_data.get('session_id'),
            score=adjusted_score,
            risk_band=risk_band,
            factors=factors,
            recommendations=recommendations
        )
        
        # Store in history
        self.risk_history.append(assessment)
        if task_id != 'unknown':
            self.task_history[task_id].append(task_data)
        
        return assessment
    
    def _collect_risk_factors(self, task_data: Dict) -> List[RiskFactor]:
        """Collect risk factors from task data."""
        factors = []
        
        # Check retrieval
        retrieval_hits = task_data.get('retrieval_hits', 0)
        if retrieval_hits == 0:
            factors.append(RiskFactor(
                factor_type='retrieval_empty',
                value=True,
                weight=self.factor_weights['retrieval_empty'],
                description='No examples retrieved'
            ))
        
        # Check retrieval confidence (simplified)
        retrieval_ids = task_data.get('retrieval_ids', [])
        if retrieval_hits > 0 and len(retrieval_ids) == 0:
            factors.append(RiskFactor(
                factor_type='retrieval_low_confidence',
                value=True,
                weight=self.factor_weights['retrieval_low_confidence'],
                description='Retrieval had low confidence'
            ))
        
        # Check framework mismatch
        framework_requested = task_data.get('framework_requested')
        framework_used = task_data.get('framework_used')
        if framework_requested and framework_used and framework_requested != framework_used:
            factors.append(RiskFactor(
                factor_type='framework_mismatch',
                value=f'{framework_requested} != {framework_used}',
                weight=self.factor_weights['framework_mismatch'],
                description='Framework mismatch detected'
            ))
        
        # Check verification failure
        verification_status = task_data.get('verification_status')
        if verification_status in ['FAILED', 'UNVERIFIED']:
            factors.append(RiskFactor(
                factor_type='verification_failed',
                value=verification_status,
                weight=self.factor_weights['verification_failed'],
                description=f'Verification failed: {verification_status}'
            ))
        
        # Check ProjectX escalation
        status = task_data.get('status', '')
        if status == 'ESCALATED':
            factors.append(RiskFactor(
                factor_type='projectx_escalated',
                value=True,
                weight=self.factor_weights['projectx_escalated'],
                description='Task was escalated'
            ))
        
        # Check latency
        latency_ms = task_data.get('latency_ms', 0)
        if latency_ms > self.config['high_latency_threshold_ms']:
            factors.append(RiskFactor(
                factor_type='high_latency',
                value=latency_ms,
                weight=self.factor_weights['high_latency'],
                description=f'High latency: {latency_ms}ms'
            ))
        
        # Check for repeated failures (needs history)
        error_code = task_data.get('error_code')
        if error_code:
            # Store error in history
            self.error_history.append({
                'error_code': error_code,
                'task_id': task_data.get('task_id'),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            
            # Check if this error is repeating
            recent_errors = self._get_recent_errors(window=self.config['window_size'])
            error_counts = Counter([e['error_code'] for e in recent_errors])
            
            if error_counts.get(error_code, 0) >= self.config['repeated_failure_threshold']:
                factors.append(RiskFactor(
                    factor_type='repeated_failure',
                    value=error_code,
                    weight=self.factor_weights['repeated_failure'],
                    description=f'Repeated failure: {error_code}'
                ))
        
        return factors
    
    def _calculate_base_score(self, factors: List[RiskFactor]) -> float:
        """Calculate base risk score from factors."""
        if not factors:
            return 0.0
        
        # Sum weighted factors
        score = 0.0
        for factor in factors:
            score += factor.weight
        
        # Cap at 1.0
        return min(1.0, score)
    
    def _detect_patterns(self, task_data: Dict, factors: List[RiskFactor]) -> float:
        """Detect failure patterns and return risk adjustment."""
        if not self.config['enable_pattern_detection']:
            return 0.0
        
        adjustment = 0.0
        
        # Get recent history
        recent_tasks = self._get_recent_tasks(self.config['window_size'])
        
        # Check each pattern
        for pattern_name, pattern in self.failure_patterns.items():
            indicator_count = 0
            
            for task in recent_tasks:
                error_code = task.get('error_code')
                if error_code in pattern['indicators']:
                    indicator_count += 1
            
            # Check if pattern threshold is met
            if indicator_count >= pattern['threshold']:
                # Check if current task has any of these indicators
                current_errors = [f.value for f in factors if f.factor_type == 'verification_failed']
                current_error_codes = task_data.get('error_code', '')
                
                if (any(indicator in str(current_errors) for indicator in pattern['indicators']) or
                    current_error_codes in pattern['indicators']):
                    
                    adjustment += pattern['risk_boost']
                    print(f"Pattern detected: {pattern_name} (+{pattern['risk_boost']:.2f} risk)")
        
        return adjustment
    
    def _determine_risk_band(self, score: float) -> str:
        """Determine risk band from score."""
        for band, (low, high) in self.risk_bands.items():
            if low <= score <= high:
                return band
        
        # Default to critical if outside bounds
        return 'critical'
    
    def _generate_recommendations(self, risk_band: str, factors: List[RiskFactor]) -> List[str]:
        """Generate recommendations based on risk band and factors."""
        recommendations = []
        
        # Base recommendation from risk band
        recommendations.append(self.actions_by_band[risk_band])
        
        # Factor-specific recommendations
        for factor in factors:
            if factor.factor_type == 'retrieval_empty':
                recommendations.append("Expand dataset or improve retrieval")
            elif factor.factor_type == 'framework_mismatch':
                recommendations.append("Clarify framework requirements")
            elif factor.factor_type == 'verification_failed':
                recommendations.append("Review algorithm implementation")
            elif factor.factor_type == 'repeated_failure':
                recommendations.append("Investigate root cause of repeated failures")
            elif factor.factor_type == 'high_latency':
                recommendations.append("Optimize performance or increase timeout")
        
        return recommendations
    
    def _get_recent_tasks(self, count: int) -> List[Dict]:
        """Get recent tasks from history."""
        all_tasks = []
        for task_list in self.task_history.values():
            all_tasks.extend(task_list)
        
        # Sort by timestamp (newest first)
        all_tasks.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return all_tasks[:count]
    
    def _get_recent_errors(self, window: int) -> List[Dict]:
        """Get recent errors from history."""
        # Sort by timestamp (newest first)
        sorted_errors = sorted(self.error_history, 
                             key=lambda x: x.get('timestamp', ''),
                             reverse=True)
        
        return sorted_errors[:window]
    
    def analyze_trends(self) -> Dict:
        """Analyze risk trends over time."""
        if not self.config['enable_trend_analysis']:
            return {'trend_analysis': 'disabled'}
        
        if len(self.risk_history) < 10:
            return {'trend_analysis': 'insufficient_data', 'count': len(self.risk_history)}
        
        # Group by time periods
        now = datetime.utcnow()
        periods = {
            'last_hour': [],
            'last_6_hours': [],
            'last_24_hours': []
        }
        
        for assessment in self.risk_history:
            assessment_time = datetime.fromisoformat(assessment.timestamp.replace('Z', '+00:00'))
            time_diff = now - assessment_time
            
            if time_diff < timedelta(hours=1):
                periods['last_hour'].append(assessment)
            if time_diff < timedelta(hours=6):
                periods['last_6_hours'].append(assessment)
            if time_diff < timedelta(hours=24):
                periods['last_24_hours'].append(assessment)
        
        # Calculate trends
        trends = {}
        for period_name, period_assessments in periods.items():
            if len(period_assessments) < 3:
                trends[period_name] = {'count': len(period_assessments), 'trend': 'insufficient_data'}
                continue
            
            scores = [a.score for a in period_assessments]
            
            # Simple trend: compare first half to second half
            midpoint = len(scores) // 2
            first_half = scores[:midpoint]
            second_half = scores[midpoint:]
            
            if not first_half or not second_half:
                trends[period_name] = {'count': len(scores), 'trend': 'stable'}
                continue
            
            avg_first = statistics.mean(first_half)
            avg_second = statistics.mean(second_half)
            
            if avg_second > avg_first + 0.1:
                trend = 'worsening'
            elif avg_second < avg_first - 0.1:
                trend = 'improving'
            else:
                trend = 'stable'
            
            trends[period_name] = {
                'count': len(scores),
                'average_score': statistics.mean(scores),
                'trend': trend,
                'change': avg_second - avg_first
            }
        
        # Most common factors
        all_factors = []
        for assessment in self.risk_history:
            all_factors.extend([f.factor_type for f in assessment.factors])
        
        factor_counts = Counter(all_factors)
        common_factors = factor_counts.most_common(5)
        
        return {
            'total_assessments': len(self.risk_history),
            'period_trends': trends,
            'common_factors': common_factors,
            'current_risk_profile': self._get_current_risk_profile()
        }
    
    def _get_current_risk_profile(self) -> Dict:
        """Get current risk profile from recent assessments."""
        recent_assessments = self.risk_history[-self.config['window_size']:]
        
        if not recent_assessments:
            return {'count': 0, 'profile': 'no_data'}
        
        # Count risk bands
        band_counts = Counter([a.risk_band for a in recent_assessments])
        
        # Average score
        avg_score = statistics.mean([a.score for a in recent_assessments])
        
        # Most common recommendations
        all_recommendations = []
        for assessment in recent_assessments:
            all_recommendations.extend(assessment.recommendations)
        
        common_recommendations = Counter(all_recommendations).most_common(3)
        
        return {
            'count': len(recent_assessments),
            'average_score': avg_score,
            'risk_band_distribution': dict(band_counts),
            'common_recommendations': common_recommendations
        }
    
    def export_risk_data(self, output_dir: Optional[Path] = None) -> Dict:
        """Export risk data for analysis."""
        export_dir = output_dir or self.base_dir / "data" / "risk_analysis"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Export assessments
        assessments_file = export_dir / "risk_assessments.json"
        with open(assessments_file, 'w') as f:
            json.dump([a.to_dict() for a in self.risk_history], f, indent=2)
        
        # Export trends analysis
        trends = self.analyze_trends()
        trends_file = export_dir / "risk_trends.json"
        with open(trends_file, 'w') as f:
            json.dump(trends, f, indent=2)
        
        # Export factor analysis
        factor_analysis = self._analyze_factors()
        factors_file = export_dir / "factor_analysis.json"
        with open(factors_file, 'w') as f:
            json.dump(factor_analysis, f, indent=2)
        
        return {
            'export_dir': str(export_dir),
            'assessments_exported': len(self.risk_history),
            'files': [
                str(assessments_file),
                str(trends_file),
                str(factors_file)
            ]
        }
    
    def _analyze_factors(self) -> Dict:
        """Analyze risk factors across all assessments."""
        if not self.risk_history:
            return {'analysis': 'no_data'}
        
        # Count factor occurrences
        factor_counts = Counter()
        factor_scores = defaultdict(list)
        
        for assessment in self.risk_history:
            for factor in assessment.factors:
                factor_counts[factor.factor_type] += 1
                factor_scores[factor.factor_type].append(assessment.score)
        
        # Calculate impact of each factor
        factor_impact = {}
        for factor_type, scores in factor_scores.items():
            if scores:
                avg_score_with = statistics.mean(scores)
                
                # Get average score without this factor (simplified)
                scores_without = [a.score for a in self.risk_history 
                                if not any(f.factor_type == factor_type for f in a.factors)]
                
                if scores_without:
                    avg_score_without = statistics.mean(scores_without)
                    impact = avg_score_with - avg_score_without
                else:
                    impact = avg_score_with
                
                factor_impact[factor_type] = {
                    'count': factor_counts[factor_type],
                    'average_score_with': avg_score_with,
                    'impact': impact,
                    'weight': self.factor_weights.get(factor_type, 0.0)
                }
        
        return {
            'total_assessments': len(self.risk_history),
            'factor_occurrences': dict(factor_counts),
            'factor_impact': factor_impact,
            'most_impactful_factors': sorted(
                factor_impact.items(),
                key=lambda x: abs(x[1]['impact']),
                reverse=True
            )[:5]
        }

def test_risk_scorer():
    """Test the predictive risk scorer."""
    scorer = PredictiveRiskScorer()
    
    print("Testing Predictive Risk Scorer")
    print("="*60)
    
    # Test 1: Low risk task
    task1 = {
        'task_id': 'test_task_001',
        'trace_id': 'trace_001',
        'retrieval_hits': 2,
        'retrieval_ids': ['bell_state_001', 'bell_state_002'],
        'framework_requested': 'qiskit',
        'framework_used': 'qiskit',
        'verification_status': 'VERIFIED',
        'status': 'COMPLETED',
        'latency_ms': 1000
    }
    
    assessment1 = scorer.assess_task_risk(task1)
    print(f"1. Low risk task:")
    print(f"   Score: {assessment1.score:.2f}")
    print(f"   Risk band: {assessment1.risk_band}")
    print(f"   Factors: {len(assessment1.factors)}")
    
    # Test 2: Medium risk task
    task2 = {
        'task_id': 'test_task_002',
        'trace_id': 'trace_002',
        'retrieval_hits': 0,
        'framework_requested': 'qiskit',
        'framework_used': 'pennylane',
        'verification_status': 'FAILED',
        'status': 'FAILED',
        'error_code': 'QMODE_LOGIC_FAILURE',
        'latency_ms': 6000
    }
    
    assessment2 = scorer.assess_task_risk(task2)
    print(f"\n2. Medium risk task:")
    print(f"   Score: {assessment2.score:.2f}")
    print(f"   Risk band: {assessment2.risk_band}")
    print(f"   Recommendations: {assessment2.recommendations[:2]}")
    
    # Test 3: High risk task (with repeated failures)
    for i in range(3):
        task3 = {
            'task_id': f'test_task_003_{i}',
            'trace_id': f'trace_003_{i}',
            'retrieval_hits': 0,
            'error_code': 'QMODE_RETRIEVAL_EMPTY',
            'status': 'FAILED'
        }
        scorer.assess_task_risk(task3)
    
    # Now assess a similar task
    task3_final = {
        'task_id': 'test_task_003_final',
        'trace_id': 'trace_003_final',
        'retrieval_hits': 0,
        'error_code': 'QMODE_RETRIEVAL_EMPTY',
        'status': 'FAILED'
    }
    
    assessment3 = scorer.assess_task_risk(task3_final)
    print(f"\n3. High risk task (repeated failures):")
    print(f"   Score: {assessment3.score:.2f}")
    print(f"   Risk band: {assessment3.risk_band}")
    print(f"   Pattern detection triggered")
    
    # Test 4: Trend analysis
    trends = scorer.analyze_trends()
    print(f"\n4. Trend analysis:")
    print(f"   Total assessments: {trends.get('total_assessments', 0)}")
    if 'period_trends' in trends:
        for period, data in trends['period_trends'].items():
            print(f"   {period}: {data.get('trend', 'unknown')}")
    
    # Test 5: Export data
    export_result = scorer.export_risk_data()
    print(f"\n5. Data export:")
    print(f"   Assessments exported: {export_result['assessments_exported']}")
    
    print("\n" + "="*60)
    print("Risk Scorer Test Complete")
    print("="*60)

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Predictive Risk Scorer')
    parser.add_argument('--test', action='store_true', help='Run tests')
    parser.add_argument('--analyze', type=Path, help='Analyze trace data from file')
    parser.add_argument('--trends', action='store_true', help='Show trend analysis')
    parser.add_argument('--export', action='store_true', help='Export risk data')
    parser.add_argument('--config', type=Path, help='Configuration file')
    
    args = parser.parse_args()
    
    scorer = PredictiveRiskScorer(args.config)
    
    if args.test:
        test_risk_scorer()
    
    elif args.analyze:
        if args.analyze.exists():
            with open(args.analyze, 'r') as f:
                trace_data = json.load(f)
            
            assessment = scorer.assess_task_risk(trace_data)
            print("Risk Assessment:")
            print(json.dumps(assessment.to_dict(), indent=2))
        else:
            print(f"Error: File not found: {args.analyze}")
    
    elif args.trends:
        trends = scorer.analyze_trends()
        print("Trend Analysis:")
        print(json.dumps(trends, indent=2))
    
    elif args.export:
        result = scorer.export_risk_data()
        print("Risk Data Export Complete:")
        print(json.dumps(result, indent=2))
    
    else:
        print("Predictive Risk Scorer")
        print("\nUsage:")
        print("  --test            Run tests")
        print("  --analyze FILE    Analyze trace data from file")
        print("  --trends          Show trend analysis")
        print("  --export          Export risk data")
        print("  --config FILE     Configuration file")

if __name__ == '__main__':
    main()