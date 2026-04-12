"""
Test Runner - Build 17
Comprehensive test execution and reporting framework.
"""

import sys
import os
import json
import time
import traceback
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import concurrent.futures
import threading

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Test execution status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"


class TestCategory(Enum):
    """Test categories."""
    UNIT = "unit"
    INTEGRATION = "integration"
    SYSTEM = "system"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    REGRESSION = "regression"


@dataclass
class TestCase:
    """Individual test case."""
    test_id: str
    name: str
    description: str
    category: TestCategory
    module: str
    function: str
    timeout_seconds: int = 30
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TestResult:
    """Test execution result."""
    test_id: str
    status: TestStatus
    duration_seconds: float
    start_time: datetime
    end_time: datetime
    output: str = ""
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TestSuite:
    """Collection of test cases."""
    suite_id: str
    name: str
    description: str
    test_cases: List[TestCase]
    setup_function: Optional[str] = None
    teardown_function: Optional[str] = None
    timeout_seconds: int = 300
    parallel: bool = False
    max_workers: int = 4
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TestReport:
    """Comprehensive test report."""
    report_id: str
    suite_id: str
    start_time: datetime
    end_time: datetime
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    timeout_tests: int
    duration_seconds: float
    results: Dict[str, TestResult]
    summary: Dict[str, Any]
    recommendations: List[str]
    created_at: datetime = field(default_factory=datetime.now)


class TestRunner:
    """
    Test Runner for executing and managing tests.
    """
    
    def __init__(self, runner_id: str = "test_runner_001"):
        """
        Initialize Test Runner.
        
        Args:
            runner_id: Unique runner identifier
        """
        self.runner_id = runner_id
        self.test_cases: Dict[str, TestCase] = {}
        self.test_suites: Dict[str, TestSuite] = {}
        self.test_results: Dict[str, TestResult] = {}
        
        # Load default test suites
        self._load_default_test_suites()
        
        # Metrics
        self.metrics = {
            "total_test_cases": len(self.test_cases),
            "total_test_suites": len(self.test_suites),
            "tests_executed": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "total_execution_time": 0.0,
            "average_test_time": 0.0
        }
        
        # Execution thread pool
        self.executor = None
        
        logger.info(f"Initialized Test Runner {runner_id}")
    
    def _load_default_test_suites(self):
        """Load default test suites for the Legal Department system."""
        # Agent Test Suite
        agent_tests = [
            TestCase(
                test_id="test_ip_agent",
                name="Intellectual Property Agent Test",
                description="Test IP agent functionality",
                category=TestCategory.UNIT,
                module="agents.intellectual_property_agent",
                function="test_intellectual_property_agent",
                tags=["agent", "ip", "unit"]
            ),
            TestCase(
                test_id="test_regulatory_agent",
                name="Regulatory Compliance Agent Test",
                description="Test regulatory compliance agent functionality",
                category=TestCategory.UNIT,
                module="agents.regulatory_compliance_agent",
                function="test_regulatory_compliance_agent",
                tags=["agent", "compliance", "unit"]
            ),
            TestCase(
                test_id="test_litigation_agent",
                name="Litigation & Dispute Agent Test",
                description="Test litigation agent functionality",
                category=TestCategory.UNIT,
                module="agents.litigation_dispute_agent",
                function="test_litigation_dispute_agent",
                tags=["agent", "litigation", "unit"]
            ),
            TestCase(
                test_id="test_governance_agent",
                name="Corporate Governance Agent Test",
                description="Test corporate governance agent functionality",
                category=TestCategory.UNIT,
                module="agents.corporate_governance_agent",
                function="test_corporate_governance_agent",
                tags=["agent", "governance", "unit"]
            ),
            TestCase(
                test_id="test_ma_agent",
                name="M&A Transaction Agent Test",
                description="Test M&A transaction agent functionality",
                category=TestCategory.UNIT,
                module="agents.ma_transaction_agent",
                function="test_ma_transaction_agent",
                tags=["agent", "m&a", "unit"]
            )
        ]
        
        # Integration Test Suite
        integration_tests = [
            TestCase(
                test_id="test_knowledge_graph",
                name="Legal Knowledge Graph Test",
                description="Test knowledge graph functionality",
                category=TestCategory.INTEGRATION,
                module="knowledge_graph.legal_knowledge_graph",
                function="test_legal_knowledge_graph",
                tags=["integration", "knowledge_graph", "graph"]
            ),
            TestCase(
                test_id="test_document_processor",
                name="Document Processing Test",
                description="Test document processing pipeline",
                category=TestCategory.INTEGRATION,
                module="document_processing.document_processor",
                function="test_document_processor",
                tags=["integration", "document", "processing"]
            ),
            TestCase(
                test_id="test_workflow_orchestrator",
                name="Workflow Orchestration Test",
                description="Test workflow orchestration system",
                category=TestCategory.INTEGRATION,
                module="workflows.workflow_orchestrator",
                function="test_workflow_orchestrator",
                tags=["integration", "workflow", "orchestration"]
            ),
            TestCase(
                test_id="test_external_integration",
                name="External Integration Test",
                description="Test external integration layer",
                category=TestCategory.INTEGRATION,
                module="integrations.external_integration",
                function="test_external_integration",
                tags=["integration", "external", "api"]
            ),
            TestCase(
                test_id="test_security_framework",
                name="Security Framework Test",
                description="Test security and confidentiality framework",
                category=TestCategory.SECURITY,
                module="security.security_framework",
                function="test_security_framework",
                tags=["security", "encryption", "authentication"]
            )
        ]
        
        # Compliance Test Suite
        compliance_tests = [
            TestCase(
                test_id="test_compliance_monitor",
                name="Compliance Monitor Test",
                description="Test compliance monitoring system",
                category=TestCategory.COMPLIANCE,
                module="compliance.compliance_monitor",
                function="test_compliance_monitor",
                tags=["compliance", "monitoring", "regulatory"]
            )
        ]
        
        # Create test suites
        suites = [
            TestSuite(
                suite_id="suite_agents",
                name="Agent Test Suite",
                description="Comprehensive testing of all legal agents",
                test_cases=agent_tests,
                parallel=True,
                max_workers=3
            ),
            TestSuite(
                suite_id="suite_integration",
                name="Integration Test Suite",
                description="Testing of integration systems",
                test_cases=integration_tests,
                parallel=True,
                max_workers=2
            ),
            TestSuite(
                suite_id="suite_compliance",
                name="Compliance Test Suite",
                description="Testing of compliance systems",
                test_cases=compliance_tests,
                parallel=False
            ),
            TestSuite(
                suite_id="suite_system",
                name="System Test Suite",
                description="End-to-end system testing",
                test_cases=agent_tests + integration_tests + compliance_tests,
                parallel=True,
                max_workers=4,
                timeout_seconds=600
            )
        ]
        
        # Register all test cases
        for suite in suites:
            self.test_suites[suite.suite_id] = suite
            for test_case in suite.test_cases:
                self.test_cases[test_case.test_id] = test_case
        
        logger.info(f"Loaded {len(suites)} test suites with {len(self.test_cases)} test cases")
    
    def add_test_case(self, test_case: TestCase) -> str:
        """
        Add a new test case.
        
        Args:
            test_case: Test case to add
            
        Returns:
            Test case ID
        """
        self.test_cases[test_case.test_id] = test_case
        self.metrics["total_test_cases"] = len(self.test_cases)
        
        logger.info(f"Added test case {test_case.test_id}: {test_case.name}")
        return test_case.test_id
    
    def create_test_suite(self, suite: TestSuite) -> str:
        """
        Create a new test suite.
        
        Args:
            suite: Test suite to create
            
        Returns:
            Suite ID
        """
        # Verify all test cases exist
        for test_case in suite.test_cases:
            if test_case.test_id not in self.test_cases:
                raise ValueError(f"Test case {test_case.test_id} not found")
        
        self.test_suites[suite.suite_id] = suite
        self.metrics["total_test_suites"] = len(self.test_suites)
        
        logger.info(f"Created test suite {suite.suite_id}: {suite.name}")
        return suite.suite_id
    
    def execute_test_case(self, test_id: str) -> TestResult:
        """
        Execute a single test case.
        
        Args:
            test_id: Test case ID
            
        Returns:
            Test execution result
        """
        if test_id not in self.test_cases:
            raise ValueError(f"Test case {test_id} not found")
        
        test_case = self.test_cases[test_id]
        start_time = datetime.now()
        
        logger.info(f"Executing test case: {test_case.name}")
        
        try:
            # Import the module and get the test function
            module_parts = test_case.module.split('.')
            module_name = '.'.join(module_parts)
            
            # Dynamic import
            module = __import__(module_name)
            for part in module_parts[1:]:
                module = getattr(module, part)
            
            test_function = getattr(module, test_case.function)
            
            # Execute test with timeout
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(test_function)
                try:
                    output = future.result(timeout=test_case.timeout_seconds)
                    status = TestStatus.PASSED
                    error = None
                    stack_trace = None
                except concurrent.futures.TimeoutError:
                    status = TestStatus.TIMEOUT
                    error = f"Test timed out after {test_case.timeout_seconds} seconds"
                    stack_trace = None
                    output = ""
                    future.cancel()
                except Exception as e:
                    status = TestStatus.ERROR
                    error = str(e)
                    stack_trace = traceback.format_exc()
                    output = ""
        
        except ImportError as e:
            status = TestStatus.ERROR
            error = f"Failed to import module: {str(e)}"
            stack_trace = traceback.format_exc()
            output = ""
        except AttributeError as e:
            status = TestStatus.ERROR
            error = f"Test function not found: {str(e)}"
            stack_trace = traceback.format_exc()
            output = ""
        except Exception as e:
            status = TestStatus.ERROR
            error = f"Unexpected error: {str(e)}"
            stack_trace = traceback.format_exc()
            output = ""
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Create test result
        result = TestResult(
            test_id=test_id,
            status=status,
            duration_seconds=duration,
            start_time=start_time,
            end_time=end_time,
            output=str(output) if output else "",
            error=error,
            stack_trace=stack_trace,
            metrics={
                "category": test_case.category.value,
                "module": test_case.module,
                "function": test_case.function
            }
        )
        
        self.test_results[test_id] = result
        
        # Update metrics
        self.metrics["tests_executed"] += 1
        self.metrics["total_execution_time"] += duration
        
        if status == TestStatus.PASSED:
            self.metrics["tests_passed"] += 1
        else:
            self.metrics["tests_failed"] += 1
        
        if self.metrics["tests_executed"] > 0:
            self.metrics["average_test_time"] = (
                self.metrics["total_execution_time"] / self.metrics["tests_executed"]
            )
        
        logger.info(f"Test {test_id} completed with status: {status.value} "
                   f"(duration: {duration:.2f}s)")
        
        return result
    
    def execute_test_suite(self, suite_id: str) -> TestReport:
        """
        Execute a test suite.
        
        Args:
            suite_id: Test suite ID
            
        Returns:
            Test execution report
        """
        if suite_id not in self.test_suites:
            raise ValueError(f"Test suite {suite_id} not found")
        
        suite = self.test_suites[suite_id]
        start_time = datetime.now()
        
        logger.info(f"Executing test suite: {suite.name}")
        logger.info(f"Total tests: {len(suite.test_cases)}")
        logger.info(f"Parallel execution: {suite.parallel}")
        
        results = {}
        
        if suite.parallel:
            # Execute tests in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=suite.max_workers) as executor:
                # Submit all tests
                future_to_test = {
                    executor.submit(self.execute_test_case, test_case.test_id): test_case
                    for test_case in suite.test_cases
                }
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_test):
                    test_case = future_to_test[future]
                    try:
                        result = future.result()
                        results[test_case.test_id] = result
                    except Exception as e:
                        logger.error(f"Error executing test {test_case.test_id}: {str(e)}")
        else:
            # Execute tests sequentially
            for test_case in suite.test_cases:
                try:
                    result = self.execute_test_case(test_case.test_id)
                    results[test_case.test_id] = result
                except Exception as e:
                    logger.error(f"Error executing test {test_case.test_id}: {str(e)}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Calculate statistics
        total_tests = len(suite.test_cases)
        passed_tests = sum(1 for r in results.values() if r.status == TestStatus.PASSED)
        failed_tests = sum(1 for r in results.values() if r.status == TestStatus.FAILED)
        skipped_tests = sum(1 for r in results.values() if r.status == TestStatus.SKIPPED)
        error_tests = sum(1 for r in results.values() if r.status == TestStatus.ERROR)
        timeout_tests = sum(1 for r in results.values() if r.status == TestStatus.TIMEOUT)
        
        # Calculate durations
        durations = [r.duration_seconds for r in results.values()]
        avg_duration = statistics.mean(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        # Generate recommendations
        recommendations = []
        
        if failed_tests > 0:
            recommendations.append(f"Investigate {failed_tests} failed tests")
        
        if error_tests > 0:
            recommendations.append(f"Fix {error_tests} tests with errors")
        
        if timeout_tests > 0:
            recommendations.append(f"Optimize {timeout_tests} tests that timed out")
        
        if passed_tests == total_tests:
            recommendations.append("All tests passed - system is stable")
        else:
            success_rate = (passed_tests / total_tests) * 100
            recommendations.append(f"Test success rate: {success_rate:.1f}%")
        
        # Create summary
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests,
            "error_tests": error_tests,
            "timeout_tests": timeout_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "duration_statistics": {
                "total": duration,
                "average": avg_duration,
                "minimum": min_duration,
                "maximum": max_duration
            },
            "parallel_execution": suite.parallel,
            "max_workers": suite.max_workers if suite.parallel else 1
        }
        
        # Create report
        report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        report = TestReport(
            report_id=report_id,
            suite_id=suite_id,
            start_time=start_time,
            end_time=end_time,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            error_tests=error_tests,
            timeout_tests=timeout_tests,
            duration_seconds=duration,
            results=results,
            summary=summary,
            recommendations=recommendations
        )
        
        logger.info(f"Test suite {suite_id} completed in {duration:.2f}s")
        logger.info(f"Results: {passed_tests} passed, {failed_tests} failed, "
                   f"{error_tests} errors, {timeout_tests} timeouts")
        
        return report
    
    def generate_html_report(self, report: TestReport, output_file: str) -> str:
        """
        Generate HTML test report.
        
        Args:
            report: Test report
            output_file: Output file path
            
        Returns:
            HTML content
        """
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Test Report - {suite_name}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #eee;
                }}
                .summary {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .summary-card {{
                    padding: 20px;
                    border-radius: 8px;
                    text-align: center;
                }}
                .passed {{ background-color: #d4edda; color: #155724; }}
                .failed {{ background-color: #f8d7da; color: #721c24; }}
                .error {{ background-color: #fff3cd; color: #856404; }}
                .timeout {{ background-color: #cce5ff; color: #004085; }}
                .total {{ background-color: #e2e3e5; color: #383d41; }}
                .results-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                .results-table th,
                .results-table td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                .results-table th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                .status-passed {{ color: green; font-weight: bold; }}
                .status-failed {{ color: red; font-weight: bold; }}
                .status-error {{ color: orange; font-weight: bold; }}
                .status-timeout {{ color: blue; font-weight: bold; }}
                .status-skipped {{ color: gray; font-weight: bold; }}
                .details {{
                    display: none;
                    padding: 10px;
                    background-color: #f8f9fa;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    margin-top: 5px;
                    font-family: monospace;
                    white-space: pre-wrap;
                }}
                .toggle-details {{
                    color: #007bff;
                    cursor: pointer;
                    text-decoration: underline;
                }}
                .recommendations {{
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                }}
                .recommendations h3 {{
                    margin-top: 0;
                }}
                .timestamp {{
                    text-align: right;
                    color: #666;
                    font-size: 0.9em;
                    margin-top: 30px;
                }}
            </style>
            <script>
                function toggleDetails(testId) {{
                    var details = document.getElementById('details-' + testId);
                    if (details.style.display === 'none') {{
                        details.style.display = 'block';
                    }} else {{
                        details.style.display = 'none';
                    }}
                }}
            </script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Test Execution Report</h1>
                    <h2>{suite_name}</h2>
                    <p>Report ID: {report_id}</p>
                </div>
                
                <div class="summary">
                    <div class="summary-card total">
                        <h3>Total Tests</h3>
                        <p style="font-size: 2em; font-weight: bold;">{total_tests}</p>
                    </div>
                    <div class="summary-card passed">
                        <h3>Passed</h3>
                        <p style="font-size: 2em; font-weight: bold;">{passed_tests}</p>
                    </div>
                    <div class="summary-card failed">
                        <h3>Failed</h3>
                        <p style="font-size: 2em; font-weight: bold;">{failed_tests}</p>
                    </div>
                    <div class="summary-card error">
                        <h3>Errors</h3>
                        <p style="font-size: 2em; font-weight: bold;">{error_tests}</p>
                    </div>
                    <div class="summary-card timeout">
                        <h3>Timeouts</h3>
                        <p style="font-size: 2em; font-weight: bold;">{timeout_tests}</p>
                    </div>
                </div>
                
                <div style="text-align: center; margin: 20px 0;">
                    <h3>Success Rate: {success_rate}%</h3>
                    <p>Total Duration: {duration_seconds:.2f} seconds</p>
                </div>
                
                <h3>Test Results</h3>
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Test ID</th>
                            <th>Name</th>
                            <th>Status</th>
                            <th>Duration (s)</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {test_rows}
                    </tbody>
                </table>
                
                <div class="recommendations">
                    <h3>Recommendations</h3>
                    <ul>
                        {recommendation_items}
                    </ul>
                </div>
                
                <div class="timestamp">
                    <p>Report generated: {timestamp}</p>
                    <p>Execution: {start_time} to {end_time}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Get suite name
        suite = self.test_suites.get(report.suite_id, TestSuite(
            suite_id=report.suite_id, name="Unknown Suite", description="", test_cases=[]
        ))
        
        # Generate test rows
        test_rows = ""
        for test_id, result in report.results.items():
            test_case = self.test_cases.get(test_id, TestCase(
                test_id=test_id, name="Unknown Test", description="", 
                category=TestCategory.UNIT, module="", function=""
            ))
            
            status_class = f"status-{result.status.value}"
            
            # Create details content
            details_content = ""
            if result.error:
                details_content += f"Error: {result.error}\\n\\n"
            if result.stack_trace:
                details_content += f"Stack Trace:\\n{result.stack_trace}\\n\\n"
            if result.output:
                details_content += f"Output:\\n{result.output}"
            
            test_rows += f"""
                <tr>
                    <td>{test_id}</td>
                    <td>{test_case.name}</td>
                    <td class="{status_class}">{result.status.value.upper()}</td>
                    <td>{result.duration_seconds:.2f}</td>
                    <td>
                        <span class="toggle-details" onclick="toggleDetails('{test_id}')">
                            Show Details
                        </span>
                        <div id="details-{test_id}" class="details">
                            {details_content}
                        </div>
                    </td>
                </tr>
            """
        
        # Generate recommendation items
        recommendation_items = ""
        for rec in report.recommendations:
            recommendation_items += f"<li>{rec}</li>"
        
        # Fill template
        html_content = html_template.format(
            suite_name=suite.name,
            report_id=report.report_id,
            total_tests=report.total_tests,
            passed_tests=report.passed_tests,
            failed_tests=report.failed_tests,
            error_tests=report.error_tests,
            timeout_tests=report.timeout_tests,
            success_rate=report.summary.get("success_rate", 0),
            duration_seconds=report.duration_seconds,
            test_rows=test_rows,
            recommendation_items=recommendation_items,
            timestamp=report.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            start_time=report.start_time.strftime("%H:%M:%S"),
            end_time=report.end_time.strftime("%H:%M:%S")
        )
        
        # Write to file
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {output_file}")
        return html_content
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get test runner dashboard data.
        
        Returns:
            Dashboard data
        """
        # Calculate category statistics
        category_stats = {}
        for test_case in self.test_cases.values():
            category = test_case.category.value
            if category not in category_stats:
                category_stats[category] = 0
            category_stats[category] += 1
        
        # Calculate recent execution statistics
        recent_results = list(self.test_results.values())[-10:]  # Last 10 results
        recent_stats = {
            "total": len(recent_results),
            "passed": sum(1 for r in recent_results if r.status == TestStatus.PASSED),
            "failed": sum(1 for r in recent_results if r.status == TestStatus.FAILED),
            "average_duration": statistics.mean([r.duration_seconds for r in recent_results]) 
                              if recent_results else 0
        }
        
        return {
            "runner_id": self.runner_id,
            "metrics": self.metrics,
            "category_statistics": category_stats,
            "recent_executions": recent_stats,
            "total_suites": len(self.test_suites),
            "total_cases": len(self.test_cases),
            "total_results": len(self.test_results),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get test runner status.
        
        Returns:
            Status information
        """
        return {
            "runner_id": self.runner_id,
            "test_cases_count": len(self.test_cases),
            "test_suites_count": len(self.test_suites),
            "test_results_count": len(self.test_results),
            "metrics": self.metrics,
            "timestamp": datetime.now().isoformat()
        }


def test_test_runner():
    """Test function for Test Runner."""
    print("Testing Test Runner...")
    
    # Create runner instance
    runner = TestRunner("test_runner_demo")
    
    # Test 1: Initial status
    print("\n1. Initial Status:")
    status = runner.get_status()
    print(f"   Runner ID: {status['runner_id']}")
    print(f"   Test cases: {status['test_cases_count']}")
    print(f"   Test suites: {status['test_suites_count']}")
    
    # Test 2: Add new test case
    print("\n2. Adding new test case...")
    new_test = TestCase(
        test_id="test_custom_001",
        name="Custom Test Case",
        description="Custom test for demonstration",
        category=TestCategory.UNIT,
        module="tests.test_runner",
        function="test_test_runner",
        timeout_seconds=10
    )
    runner.add_test_case(new_test)
    print(f"   Added test case: {new_test.name}")
    
    # Test 3: Execute single test case
    print("\n3. Executing single test case...")
    try:
        result = runner.execute_test_case("test_ip_agent")
        print(f"   Test executed: {result.test_id}")
        print(f"   Status: {result.status.value}")
        print(f"   Duration: {result.duration_seconds:.2f}s")
    except Exception as e:
        print(f"   Test execution failed: {str(e)}")
    
    # Test 4: Execute test suite
    print("\n4. Executing test suite...")
    try:
        report = runner.execute_test_suite("suite_agents")
        print(f"   Suite executed: {report.suite_id}")
        print(f"   Total tests: {report.total_tests}")
        print(f"   Passed tests: {report.passed_tests}")
        print(f"   Duration: {report.duration_seconds:.2f}s")
    except Exception as e:
        print(f"   Suite execution failed: {str(e)}")
    
    # Test 5: Generate HTML report
    print("\n5. Generating HTML report...")
    try:
        # Create a mock report for demonstration
        mock_report = TestReport(
            report_id="mock_report_001",
            suite_id="suite_agents",
            start_time=datetime.now() - timedelta(minutes=5),
            end_time=datetime.now(),
            total_tests=10,
            passed_tests=8,
            failed_tests=1,
            skipped_tests=0,
            error_tests=1,
            timeout_tests=0,
            duration_seconds=45.5,
            results={},
            summary={"success_rate": 80.0},
            recommendations=["Fix failed tests", "Investigate errors"]
        )
        
        html_file = "test_report_demo.html"
        runner.generate_html_report(mock_report, html_file)
        print(f"   HTML report generated: {html_file}")
    except Exception as e:
        print(f"   Report generation failed: {str(e)}")
    
    # Test 6: Dashboard data
    print("\n6. Getting dashboard data...")
    dashboard = runner.get_dashboard_data()
    print(f"   Total cases: {dashboard['total_cases']}")
    print(f"   Total suites: {dashboard['total_suites']}")
    print(f"   Tests executed: {dashboard['metrics']['tests_executed']}")
    print(f"   Tests passed: {dashboard['metrics']['tests_passed']}")
    
    # Final status
    print("\n7. Final Status:")
    final_status = runner.get_status()
    print(f"   Test results: {final_status['test_results_count']}")
    print(f"   Average test time: {final_status['metrics']['average_test_time']:.2f}s")
    
    print("\nTest Runner test completed successfully!")


if __name__ == "__main__":
    test_test_runner()