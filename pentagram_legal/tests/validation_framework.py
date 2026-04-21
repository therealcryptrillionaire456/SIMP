"""
Validation Framework - Build 17
Accuracy validation, benchmarking, and quality assurance.
"""

import sys
import os
import json
import time
import statistics
import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import numpy as np
from collections import defaultdict

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ValidationType(Enum):
    """Types of validation."""
    ACCURACY = "accuracy"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    REGRESSION = "regression"
    LOAD = "load"
    STRESS = "stress"


class ValidationStatus(Enum):
    """Validation status levels."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


class BenchmarkMetric(Enum):
    """Benchmark metrics."""
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    ERROR_RATE = "error_rate"
    AVAILABILITY = "availability"
    RELIABILITY = "reliability"
    SCALABILITY = "scalability"


@dataclass
class ValidationDataset:
    """Validation dataset."""
    dataset_id: str
    name: str
    description: str
    type: ValidationType
    data_path: str
    schema: Dict[str, Any]
    size: int
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationRule:
    """Validation rule."""
    rule_id: str
    name: str
    description: str
    component: str
    condition: str
    expected_value: Any
    tolerance: float = 0.0
    severity: str = "high"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationResult:
    """Validation execution result."""
    validation_id: str
    dataset_id: str
    rule_id: str
    status: ValidationStatus
    actual_value: Any
    expected_value: Any
    difference: float
    within_tolerance: bool
    execution_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class BenchmarkResult:
    """Benchmark execution result."""
    benchmark_id: str
    component: str
    metric: BenchmarkMetric
    value: float
    unit: str
    iterations: int
    confidence_interval: Tuple[float, float]
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class QualityMetric:
    """Quality metric."""
    metric_id: str
    name: str
    description: str
    value: float
    target: float
    unit: str
    trend: str  # improving, stable, declining
    last_updated: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)


class ValidationFramework:
    """
    Validation Framework for accuracy validation and benchmarking.
    """
    
    def __init__(self, framework_id: str = "validation_framework_001"):
        """
        Initialize Validation Framework.
        
        Args:
            framework_id: Unique framework identifier
        """
        self.framework_id = framework_id
        self.validation_datasets: Dict[str, ValidationDataset] = {}
        self.validation_rules: Dict[str, ValidationRule] = {}
        self.validation_results: Dict[str, ValidationResult] = {}
        self.benchmark_results: Dict[str, BenchmarkResult] = {}
        self.quality_metrics: Dict[str, QualityMetric] = {}
        
        # Load default validation rules
        self._load_default_rules()
        
        # Load default quality metrics
        self._load_default_metrics()
        
        # Metrics
        self.metrics = {
            "total_datasets": len(self.validation_datasets),
            "total_rules": len(self.validation_rules),
            "total_validations": 0,
            "passed_validations": 0,
            "failed_validations": 0,
            "total_benchmarks": 0,
            "quality_score": 100.0
        }
        
        logger.info(f"Initialized Validation Framework {framework_id}")
    
    def _load_default_rules(self):
        """Load default validation rules."""
        default_rules = [
            # Agent validation rules
            ValidationRule(
                rule_id="rule_agent_response_time",
                name="Agent Response Time",
                description="Agent should respond within 2 seconds",
                component="agents",
                condition="response_time <= 2.0",
                expected_value=2.0,
                tolerance=0.5,
                severity="high"
            ),
            ValidationRule(
                rule_id="rule_agent_accuracy",
                name="Agent Accuracy",
                description="Agent should have at least 95% accuracy",
                component="agents",
                condition="accuracy >= 0.95",
                expected_value=0.95,
                tolerance=0.05,
                severity="high"
            ),
            
            # Document processing rules
            ValidationRule(
                rule_id="rule_document_processing_time",
                name="Document Processing Time",
                description="Document should be processed within 30 seconds",
                component="document_processing",
                condition="processing_time <= 30.0",
                expected_value=30.0,
                tolerance=5.0,
                severity="medium"
            ),
            ValidationRule(
                rule_id="rule_document_accuracy",
                name="Document Classification Accuracy",
                description="Document classification should be at least 90% accurate",
                component="document_processing",
                condition="classification_accuracy >= 0.90",
                expected_value=0.90,
                tolerance=0.10,
                severity="high"
            ),
            
            # Knowledge graph rules
            ValidationRule(
                rule_id="rule_knowledge_graph_query_time",
                name="Knowledge Graph Query Time",
                description="Graph queries should complete within 1 second",
                component="knowledge_graph",
                condition="query_time <= 1.0",
                expected_value=1.0,
                tolerance=0.2,
                severity="medium"
            ),
            ValidationRule(
                rule_id="rule_knowledge_graph_accuracy",
                name="Knowledge Graph Accuracy",
                description="Graph queries should have at least 98% accuracy",
                component="knowledge_graph",
                condition="query_accuracy >= 0.98",
                expected_value=0.98,
                tolerance=0.02,
                severity="high"
            ),
            
            # Compliance rules
            ValidationRule(
                rule_id="rule_compliance_monitoring_latency",
                name="Compliance Monitoring Latency",
                description="Compliance checks should complete within 5 seconds",
                component="compliance",
                condition="monitoring_latency <= 5.0",
                expected_value=5.0,
                tolerance=1.0,
                severity="medium"
            ),
            ValidationRule(
                rule_id="rule_compliance_accuracy",
                name="Compliance Check Accuracy",
                description="Compliance checks should be 99% accurate",
                component="compliance",
                condition="check_accuracy >= 0.99",
                expected_value=0.99,
                tolerance=0.01,
                severity="high"
            )
        ]
        
        for rule in default_rules:
            self.validation_rules[rule.rule_id] = rule
        
        logger.info(f"Loaded {len(default_rules)} default validation rules")
    
    def _load_default_metrics(self):
        """Load default quality metrics."""
        default_metrics = [
            QualityMetric(
                metric_id="metric_system_availability",
                name="System Availability",
                description="Percentage of time system is available",
                value=99.9,
                target=99.9,
                unit="%",
                trend="stable"
            ),
            QualityMetric(
                metric_id="metric_response_time",
                name="Average Response Time",
                description="Average system response time",
                value=1.2,
                target=2.0,
                unit="seconds",
                trend="improving"
            ),
            QualityMetric(
                metric_id="metric_error_rate",
                name="Error Rate",
                description="Percentage of requests with errors",
                value=0.1,
                target=1.0,
                unit="%",
                trend="stable"
            ),
            QualityMetric(
                metric_id="metric_user_satisfaction",
                name="User Satisfaction",
                description="User satisfaction score",
                value=4.5,
                target=4.0,
                unit="score",
                trend="improving"
            ),
            QualityMetric(
                metric_id="metric_data_accuracy",
                name="Data Accuracy",
                description="Accuracy of processed data",
                value=98.5,
                target=95.0,
                unit="%",
                trend="stable"
            )
        ]
        
        for metric in default_metrics:
            self.quality_metrics[metric.metric_id] = metric
        
        logger.info(f"Loaded {len(default_metrics)} default quality metrics")
    
    def add_validation_dataset(self, dataset: ValidationDataset) -> str:
        """
        Add a validation dataset.
        
        Args:
            dataset: Validation dataset
            
        Returns:
            Dataset ID
        """
        self.validation_datasets[dataset.dataset_id] = dataset
        self.metrics["total_datasets"] = len(self.validation_datasets)
        
        logger.info(f"Added validation dataset {dataset.dataset_id}: {dataset.name}")
        return dataset.dataset_id
    
    def add_validation_rule(self, rule: ValidationRule) -> str:
        """
        Add a validation rule.
        
        Args:
            rule: Validation rule
            
        Returns:
            Rule ID
        """
        self.validation_rules[rule.rule_id] = rule
        self.metrics["total_rules"] = len(self.validation_rules)
        
        logger.info(f"Added validation rule {rule.rule_id}: {rule.name}")
        return rule.rule_id
    
    def validate_rule(self, rule_id: str, actual_value: Any, 
                     metadata: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate against a rule.
        
        Args:
            rule_id: Rule ID
            actual_value: Actual measured value
            metadata: Additional metadata
            
        Returns:
            Validation result
        """
        if rule_id not in self.validation_rules:
            raise ValueError(f"Validation rule {rule_id} not found")
        
        rule = self.validation_rules[rule_id]
        start_time = time.time()
        
        # Calculate difference
        try:
            expected = float(rule.expected_value)
            actual = float(actual_value)
            difference = abs(actual - expected)
            within_tolerance = difference <= rule.tolerance
            
            # Determine status
            if within_tolerance:
                status = ValidationStatus.PASSED
            elif difference <= rule.tolerance * 2:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.FAILED
                
        except (ValueError, TypeError):
            # For non-numeric comparisons
            difference = 0
            within_tolerance = (actual_value == rule.expected_value)
            status = ValidationStatus.PASSED if within_tolerance else ValidationStatus.FAILED
        
        execution_time = time.time() - start_time
        
        # Create validation result
        validation_id = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = ValidationResult(
            validation_id=validation_id,
            dataset_id="direct_validation",
            rule_id=rule_id,
            status=status,
            actual_value=actual_value,
            expected_value=rule.expected_value,
            difference=difference,
            within_tolerance=within_tolerance,
            execution_time=execution_time,
            details={
                "rule_name": rule.name,
                "component": rule.component,
                "condition": rule.condition,
                "severity": rule.severity,
                "metadata": metadata or {}
            }
        )
        
        self.validation_results[validation_id] = result
        
        # Update metrics
        self.metrics["total_validations"] += 1
        if status == ValidationStatus.PASSED:
            self.metrics["passed_validations"] += 1
        elif status in [ValidationStatus.FAILED, ValidationStatus.ERROR]:
            self.metrics["failed_validations"] += 1
        
        # Update quality score
        if self.metrics["total_validations"] > 0:
            self.metrics["quality_score"] = (
                self.metrics["passed_validations"] / self.metrics["total_validations"] * 100
            )
        
        logger.info(f"Validation {validation_id}: {rule.name} - {status.value}")
        
        return result
    
    def run_benchmark(self, component: str, metric: BenchmarkMetric,
                     test_function: Callable, iterations: int = 10,
                     metadata: Dict[str, Any] = None) -> BenchmarkResult:
        """
        Run a benchmark test.
        
        Args:
            component: Component being benchmarked
            metric: Benchmark metric
            test_function: Function to benchmark
            iterations: Number of iterations
            metadata: Additional metadata
            
        Returns:
            Benchmark result
        """
        logger.info(f"Running benchmark for {component} - {metric.value}")
        
        values = []
        start_time = time.time()
        
        # Run iterations
        for i in range(iterations):
            iter_start = time.time()
            
            try:
                # Execute test function
                result = test_function()
                
                # Extract value based on metric
                if metric == BenchmarkMetric.RESPONSE_TIME:
                    value = time.time() - iter_start
                elif metric == BenchmarkMetric.THROUGHPUT:
                    value = result.get("throughput", 0)
                elif metric == BenchmarkMetric.ACCURACY:
                    value = result.get("accuracy", 0)
                elif metric == BenchmarkMetric.ERROR_RATE:
                    value = result.get("error_rate", 0)
                else:
                    value = result if isinstance(result, (int, float)) else 0
                
                values.append(value)
                
            except Exception as e:
                logger.error(f"Benchmark iteration {i+1} failed: {str(e)}")
                values.append(0)  # Use 0 for failed iterations
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        if values:
            mean_value = statistics.mean(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0
            
            # Confidence interval (95%)
            if len(values) > 1:
                confidence_interval = (
                    mean_value - 1.96 * std_dev / np.sqrt(len(values)),
                    mean_value + 1.96 * std_dev / np.sqrt(len(values))
                )
            else:
                confidence_interval = (mean_value, mean_value)
        else:
            mean_value = 0
            confidence_interval = (0, 0)
        
        # Determine unit
        unit_map = {
            BenchmarkMetric.RESPONSE_TIME: "seconds",
            BenchmarkMetric.THROUGHPUT: "requests/second",
            BenchmarkMetric.ACCURACY: "%",
            BenchmarkMetric.PRECISION: "%",
            BenchmarkMetric.RECALL: "%",
            BenchmarkMetric.F1_SCORE: "score",
            BenchmarkMetric.ERROR_RATE: "%",
            BenchmarkMetric.AVAILABILITY: "%",
            BenchmarkMetric.RELIABILITY: "%",
            BenchmarkMetric.SCALABILITY: "scale_factor"
        }
        unit = unit_map.get(metric, "units")
        
        # Create benchmark result
        benchmark_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = BenchmarkResult(
            benchmark_id=benchmark_id,
            component=component,
            metric=metric,
            value=mean_value,
            unit=unit,
            iterations=iterations,
            confidence_interval=confidence_interval,
            metadata={
                "total_time": total_time,
                "iterations_per_second": iterations / total_time if total_time > 0 else 0,
                "values": values,
                "additional_metadata": metadata or {}
            }
        )
        
        self.benchmark_results[benchmark_id] = result
        self.metrics["total_benchmarks"] += 1
        
        logger.info(f"Benchmark {benchmark_id} completed: {mean_value:.2f} {unit}")
        
        return result
    
    def validate_component(self, component: str, 
                          validation_data: Dict[str, Any]) -> List[ValidationResult]:
        """
        Validate a component against all relevant rules.
        
        Args:
            component: Component to validate
            validation_data: Validation data for the component
            
        Returns:
            List of validation results
        """
        results = []
        
        # Find rules for this component
        component_rules = [
            rule for rule in self.validation_rules.values() 
            if rule.component == component
        ]
        
        logger.info(f"Validating component {component} with {len(component_rules)} rules")
        
        for rule in component_rules:
            try:
                # Extract value from validation data based on rule condition
                # This is a simplified implementation
                value_key = rule.condition.split()[0]
                actual_value = validation_data.get(value_key, 0)
                
                # Validate rule
                result = self.validate_rule(rule.rule_id, actual_value, {
                    "component": component,
                    "validation_data": validation_data
                })
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error validating rule {rule.rule_id}: {str(e)}")
                
                # Create error result
                validation_id = f"validation_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                error_result = ValidationResult(
                    validation_id=validation_id,
                    dataset_id="component_validation",
                    rule_id=rule.rule_id,
                    status=ValidationStatus.ERROR,
                    actual_value=None,
                    expected_value=rule.expected_value,
                    difference=0,
                    within_tolerance=False,
                    execution_time=0,
                    details={
                        "error": str(e),
                        "component": component,
                        "rule_name": rule.name
                    }
                )
                
                self.validation_results[validation_id] = error_result
                results.append(error_result)
        
        return results
    
    def update_quality_metric(self, metric_id: str, value: float, 
                             trend: str = None) -> bool:
        """
        Update a quality metric.
        
        Args:
            metric_id: Metric ID
            value: New value
            trend: Trend direction
            
        Returns:
            Success status
        """
        if metric_id not in self.quality_metrics:
            return False
        
        metric = self.quality_metrics[metric_id]
        metric.value = value
        metric.last_updated = datetime.now()
        
        if trend:
            metric.trend = trend
        else:
            # Auto-determine trend
            if value > metric.target * 1.1:
                metric.trend = "improving"
            elif value < metric.target * 0.9:
                metric.trend = "declining"
            else:
                metric.trend = "stable"
        
        logger.info(f"Updated quality metric {metric_id}: {value} {metric.unit}")
        return True
    
    def generate_validation_report(self, component: str = None) -> Dict[str, Any]:
        """
        Generate validation report.
        
        Args:
            component: Optional component filter
            
        Returns:
            Validation report
        """
        # Filter results by component if specified
        if component:
            filtered_results = [
                r for r in self.validation_results.values()
                if r.details.get("component") == component
            ]
            filtered_rules = [
                r for r in self.validation_rules.values()
                if r.component == component
            ]
        else:
            filtered_results = list(self.validation_results.values())
            filtered_rules = list(self.validation_rules.values())
        
        # Calculate statistics
        total_results = len(filtered_results)
        passed_results = sum(1 for r in filtered_results if r.status == ValidationStatus.PASSED)
        failed_results = sum(1 for r in filtered_results if r.status == ValidationStatus.FAILED)
        warning_results = sum(1 for r in filtered_results if r.status == ValidationStatus.WARNING)
        error_results = sum(1 for r in filtered_results if r.status == ValidationStatus.ERROR)
        
        # Calculate pass rate
        pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0
        
        # Group by component
        component_stats = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
        for result in filtered_results:
            comp = result.details.get("component", "unknown")
            component_stats[comp]["total"] += 1
            if result.status == ValidationStatus.PASSED:
                component_stats[comp]["passed"] += 1
            elif result.status in [ValidationStatus.FAILED, ValidationStatus.ERROR]:
                component_stats[comp]["failed"] += 1
        
        # Get recent benchmarks
        recent_benchmarks = list(self.benchmark_results.values())[-5:]
        
        # Get quality metrics
        quality_summary = {}
        for metric_id, metric in self.quality_metrics.items():
            quality_summary[metric_id] = {
                "name": metric.name,
                "value": metric.value,
                "target": metric.target,
                "unit": metric.unit,
                "trend": metric.trend,
                "status": "met" if metric.value >= metric.target else "below"
            }
        
        # Generate recommendations
        recommendations = []
        
        if failed_results > 0:
            recommendations.append(f"Address {failed_results} failed validations")
        
        if error_results > 0:
            recommendations.append(f"Investigate {error_results} validation errors")
        
        if pass_rate < 90:
            recommendations.append(f"Improve validation pass rate (currently {pass_rate:.1f}%)")
        
        # Check quality metrics
        for metric_id, summary in quality_summary.items():
            if summary["status"] == "below":
                recommendations.append(f"Improve {summary['name']} (current: {summary['value']}{summary['unit']}, target: {summary['target']}{summary['unit']})")
        
        # Create report
        report = {
            "report_id": f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "component_filter": component,
            "summary": {
                "total_results": total_results,
                "passed_results": passed_results,
                "failed_results": failed_results,
                "warning_results": warning_results,
                "error_results": error_results,
                "pass_rate": pass_rate,
                "quality_score": self.metrics["quality_score"]
            },
            "component_statistics": dict(component_stats),
            "recent_benchmarks": [
                {
                    "component": b.component,
                    "metric": b.metric.value,
                    "value": b.value,
                    "unit": b.unit,
                    "iterations": b.iterations
                }
                for b in recent_benchmarks
            ],
            "quality_metrics": quality_summary,
            "recommendations": recommendations,
            "metadata": {
                "total_rules": len(filtered_rules),
                "total_benchmarks": len(self.benchmark_results),
                "framework_id": self.framework_id
            }
        }
        
        logger.info(f"Generated validation report for component: {component or 'all'}")
        
        return report
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get validation dashboard data.
        
        Returns:
            Dashboard data
        """
        # Calculate recent validation statistics (last 24 hours)
        one_day_ago = datetime.now() - timedelta(days=1)
        recent_results = [
            r for r in self.validation_results.values()
            if r.timestamp > one_day_ago
        ]
        
        recent_stats = {
            "total": len(recent_results),
            "passed": sum(1 for r in recent_results if r.status == ValidationStatus.PASSED),
            "failed": sum(1 for r in recent_results if r.status == ValidationStatus.FAILED),
            "pass_rate": (sum(1 for r in recent_results if r.status == ValidationStatus.PASSED) / len(recent_results) * 100) 
                         if recent_results else 0
        }
        
        # Get top components by validation count
        component_counts = defaultdict(int)
        for result in self.validation_results.values():
            component = result.details.get("component", "unknown")
            component_counts[component] += 1
        
        top_components = sorted(
            [(comp, count) for comp, count in component_counts.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Get benchmark trends
        benchmark_trends = {}
        for benchmark in list(self.benchmark_results.values())[-10:]:
            metric_key = f"{benchmark.component}_{benchmark.metric.value}"
            if metric_key not in benchmark_trends:
                benchmark_trends[metric_key] = []
            benchmark_trends[metric_key].append({
                "timestamp": benchmark.timestamp.isoformat(),
                "value": benchmark.value
            })
        
        return {
            "framework_id": self.framework_id,
            "metrics": self.metrics,
            "recent_validation_stats": recent_stats,
            "top_components": top_components,
            "benchmark_trends": benchmark_trends,
            "quality_metrics_count": len(self.quality_metrics),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get framework status.
        
        Returns:
            Status information
        """
        return {
            "framework_id": self.framework_id,
            "datasets_count": len(self.validation_datasets),
            "rules_count": len(self.validation_rules),
            "results_count": len(self.validation_results),
            "benchmarks_count": len(self.benchmark_results),
            "quality_metrics_count": len(self.quality_metrics),
            "metrics": self.metrics,
            "timestamp": datetime.now().isoformat()
        }


def test_validation_framework():
    """Test function for Validation Framework."""
    print("Testing Validation Framework...")
    
    # Create framework instance
    framework = ValidationFramework("test_framework_001")
    
    # Test 1: Initial status
    print("\n1. Initial Status:")
    status = framework.get_status()
    print(f"   Framework ID: {status['framework_id']}")
    print(f"   Validation rules: {status['rules_count']}")
    print(f"   Quality metrics: {status['quality_metrics_count']}")
    
    # Test 2: Add validation dataset
    print("\n2. Adding validation dataset...")
    dataset = ValidationDataset(
        dataset_id="dataset_test_001",
        name="Test Validation Dataset",
        description="Test dataset for validation framework",
        type=ValidationType.ACCURACY,
        data_path="/data/test",
        schema={"fields": ["id", "value", "expected"]},
        size=1000
    )
    framework.add_validation_dataset(dataset)
    print(f"   Added dataset: {dataset.name}")
    
    # Test 3: Add validation rule
    print("\n3. Adding validation rule...")
    rule = ValidationRule(
        rule_id="rule_test_001",
        name="Test Validation Rule",
        description="Test rule for validation framework",
        component="test_component",
        condition="test_value >= 0.95",
        expected_value=0.95,
        tolerance=0.05
    )
    framework.add_validation_rule(rule)
    print(f"   Added rule: {rule.name}")
    
    # Test 4: Validate rule
    print("\n4. Validating rule...")
    result = framework.validate_rule("rule_test_001", 0.97, {"test": "data"})
    print(f"   Validation result: {result.status.value}")
    print(f"   Actual value: {result.actual_value}")
    print(f"   Expected value: {result.expected_value}")
    print(f"   Within tolerance: {result.within_tolerance}")
    
    # Test 5: Run benchmark
    print("\n5. Running benchmark...")
    
    def benchmark_test_function():
        """Test function for benchmarking."""
        time.sleep(0.01)  # Simulate work
        return {"accuracy": 0.98, "throughput": 100}
    
    benchmark = framework.run_benchmark(
        component="test_component",
        metric=BenchmarkMetric.RESPONSE_TIME,
        test_function=benchmark_test_function,
        iterations=5,
        metadata={"test": "benchmark"}
    )
    print(f"   Benchmark result: {benchmark.value:.4f} {benchmark.unit}")
    print(f"   Confidence interval: {benchmark.confidence_interval}")
    
    # Test 6: Validate component
    print("\n6. Validating component...")
    validation_data = {
        "response_time": 1.5,
        "accuracy": 0.96,
        "processing_time": 25.0,
        "classification_accuracy": 0.92
    }
    results = framework.validate_component("agents", validation_data)
    print(f"   Component validation results: {len(results)}")
    for r in results:
        print(f"     - {r.details.get('rule_name', 'Unknown')}: {r.status.value}")
    
    # Test 7: Update quality metric
    print("\n7. Updating quality metric...")
    success = framework.update_quality_metric("metric_response_time", 1.1, "improving")
    print(f"   Update successful: {success}")
    
    # Test 8: Generate validation report
    print("\n8. Generating validation report...")
    report = framework.generate_validation_report()
    print(f"   Report generated: {report['report_id']}")
    print(f"   Total results: {report['summary']['total_results']}")
    print(f"   Pass rate: {report['summary']['pass_rate']:.1f}%")
    print(f"   Quality score: {report['summary']['quality_score']:.1f}")
    
    # Test 9: Get dashboard data
    print("\n9. Getting dashboard data...")
    dashboard = framework.get_dashboard_data()
    print(f"   Recent validations: {dashboard['recent_validation_stats']['total']}")
    print(f"   Recent pass rate: {dashboard['recent_validation_stats']['pass_rate']:.1f}%")
    print(f"   Top components: {len(dashboard['top_components'])}")
    
    # Final status
    print("\n10. Final Status:")
    final_status = framework.get_status()
    print(f"   Total results: {final_status['results_count']}")
    print(f"   Total benchmarks: {final_status['benchmarks_count']}")
    print(f"   Quality score: {final_status['metrics']['quality_score']:.1f}")
    
    print("\nValidation Framework test completed successfully!")


if __name__ == "__main__":
    test_validation_framework()