#!/usr/bin/env python3
"""
Comprehensive test suite for Stray Goose Quantum Mode.

Tests all components of the Quantum Mode system:
1. Schema and data structures
2. Dataset manager
3. Trace logger
4. Risk scorer
5. Executor
6. ProjectX integration
7. Engine integration
8. CLI interface
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import logging

# Configure logging for tests
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class TestQuantumModeSchema(unittest.TestCase):
    """Test quantum mode schema and data structures."""
    
    def setUp(self):
        from quantum_mode_schema import (
            TaskType, VerificationStatus, QuantumErrorCode, Severity,
            TraceStep, TraceStatus, QuantumTask, RetrievalResult,
            VerificationResult, ProjectXJudgment, QuantumTrace,
            LearningSignal, PredictiveRiskScore, QuantumModeConfig
        )
        
        self.schema_modules = {
            "TaskType": TaskType,
            "VerificationStatus": VerificationStatus,
            "QuantumErrorCode": QuantumErrorCode,
            "Severity": Severity,
            "TraceStep": TraceStep,
            "TraceStatus": TraceStatus,
            "QuantumTask": QuantumTask,
            "RetrievalResult": RetrievalResult,
            "VerificationResult": VerificationResult,
            "ProjectXJudgment": ProjectXJudgment,
            "QuantumTrace": QuantumTrace,
            "LearningSignal": LearningSignal,
            "PredictiveRiskScore": PredictiveRiskScore,
            "QuantumModeConfig": QuantumModeConfig
        }
    
    def test_enum_values(self):
        """Test enum values are defined."""
        for name, enum_class in self.schema_modules.items():
            if hasattr(enum_class, '__members__'):
                members = list(enum_class.__members__.keys())
                self.assertGreater(len(members), 0, f"{name} should have members")
                print(f"✓ {name}: {members}")
    
    def test_quantum_task_creation(self):
        """Test QuantumTask creation and serialization."""
        from quantum_mode_schema import QuantumTask
        
        task = QuantumTask(
            task_id="test_task_123",
            query="Implement quantum algorithm",
            task_type="quantum_algorithm",
            created_at="2024-01-01T00:00:00Z"
        )
        
        # Test attributes
        self.assertEqual(task.task_id, "test_task_123")
        self.assertEqual(task.query, "Implement quantum algorithm")
        self.assertEqual(task.task_type, "quantum_algorithm")
        
        # Test serialization
        task_dict = task.to_dict()
        self.assertIsInstance(task_dict, dict)
        self.assertEqual(task_dict["task_id"], "test_task_123")
        
        # Test from_query class method
        classification = {
            "task_type": "quantum_circuit",
            "confidence": 0.8,
            "keywords": ["circuit", "gate"]
        }
        task2 = QuantumTask.from_query("Create quantum circuit", classification)
        self.assertEqual(task2.task_type, "quantum_circuit")
        self.assertIsNotNone(task2.task_id)
    
    def test_retrieval_result(self):
        """Test RetrievalResult."""
        from quantum_mode_schema import RetrievalResult
        
        examples = [
            {
                "id": "example_1",
                "query": "Quantum circuit",
                "solution": "qc = QuantumCircuit(2)",
                "framework": "qiskit",
                "verification_status": "verified"
            }
        ]
        
        result = RetrievalResult(
            query="Create quantum circuit",
            task_type="quantum_circuit",
            examples=examples,
            match_scores=[0.9],
            confidence_level="high",
            retrieval_time="2024-01-01T00:00:00Z"
        )
        
        # Test attributes
        self.assertEqual(len(result.examples), 1)
        self.assertEqual(result.match_scores[0], 0.9)
        self.assertEqual(result.confidence_level, "high")
        
        # Test has_verified_examples
        self.assertTrue(result.has_verified_examples())
        
        # Test with no verified examples
        result2 = RetrievalResult(
            query="Test",
            task_type="test",
            examples=[],
            match_scores=[],
            confidence_level="low",
            retrieval_time="2024-01-01T00:00:00Z"
        )
        self.assertFalse(result2.has_verified_examples())
    
    def test_verification_result(self):
        """Test VerificationResult."""
        from quantum_mode_schema import VerificationResult, RetrievalResult, VerificationStatus
        
        retrieval_result = RetrievalResult(
            query="Test",
            task_type="test",
            examples=[],
            match_scores=[],
            confidence_level="low",
            retrieval_time="2024-01-01T00:00:00Z"
        )
        
        verification = VerificationResult(
            retrieval_result=retrieval_result,
            overall_score=0.85,
            verification_status=VerificationStatus.PASSED.value,
            checks=[{"check": "test", "passed": True}],
            failure_reasons=[],
            verification_time="2024-01-01T00:00:00Z"
        )
        
        # Test attributes
        self.assertEqual(verification.overall_score, 0.85)
        self.assertEqual(verification.verification_status, "passed")
        
        # Test passed method
        self.assertTrue(verification.passed())
        
        # Test failed verification
        verification2 = VerificationResult(
            retrieval_result=retrieval_result,
            overall_score=0.3,
            verification_status=VerificationStatus.FAILED.value,
            checks=[{"check": "test", "passed": False}],
            failure_reasons=["Score too low"],
            verification_time="2024-01-01T00:00:00Z"
        )
        self.assertFalse(verification2.passed())


class TestQuantumDatasetManager(unittest.TestCase):
    """Test Quantum Dataset Manager."""
    
    def setUp(self):
        # Create temporary directory for test dataset
        self.temp_dir = tempfile.mkdtemp()
        self.dataset_dir = Path(self.temp_dir) / "quantum_dataset"
        self.dataset_dir.mkdir(parents=True)
    
    def tearDown(self):
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_dataset_creation(self):
        """Test dataset creation and loading."""
        from quantum_dataset_manager import QuantumDatasetManager
        
        # Create manager with empty directory
        manager = QuantumDatasetManager(dataset_dir=self.dataset_dir)
        
        # Should create example dataset
        stats = manager.get_stats()
        self.assertGreater(stats["total_examples"], 0)
        
        # Test retrieval
        result = manager.retrieve_examples(
            query="Implement Grover's algorithm",
            task_type="quantum_algorithm"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.task_type, "quantum_algorithm")
        
        # Test verification
        verification = manager.verify_examples(result, "quantum_algorithm")
        self.assertIsNotNone(verification)
        self.assertIn(verification.verification_status, ["passed", "partial", "failed"])
    
    def test_example_addition(self):
        """Test adding examples to dataset."""
        from quantum_dataset_manager import QuantumDatasetManager
        
        manager = QuantumDatasetManager(dataset_dir=self.dataset_dir)
        
        # Add new example
        new_example = {
            "id": "test_example_001",
            "query": "Test quantum algorithm",
            "solution": "def test():\n    return 'test'",
            "framework": "qiskit",
            "complexity": "beginner",
            "verification_status": "verified",
            "verification_score": 0.9,
            "safety_checks": ["no_execution"],
            "tags": ["test", "example"],
            "created_at": datetime.now().isoformat(),
            "verified_at": datetime.now().isoformat()
        }
        
        success = manager.add_example(new_example, "quantum_algorithm")
        self.assertTrue(success)
        
        # Verify example was added
        stats = manager.get_stats()
        self.assertGreaterEqual(stats["total_examples"], 1)
        
        # Try to retrieve it
        result = manager.retrieve_examples(
            query="Test quantum algorithm",
            task_type="quantum_algorithm"
        )
        
        self.assertGreaterEqual(len(result.examples), 1)
    
    def test_verification_rules(self):
        """Test verification rules."""
        from quantum_dataset_manager import QuantumDatasetManager
        
        manager = QuantumDatasetManager(dataset_dir=self.dataset_dir)
        
        # Test framework check
        example = {
            "id": "test",
            "query": "test",
            "solution": "test",
            "framework": "qiskit",
            "verification_status": "verified"
        }
        
        check_result = manager._check_framework(example, "quantum_algorithm")
        self.assertIsInstance(check_result, dict)
        self.assertIn("passed", check_result)
        self.assertIn("score", check_result)
        
        # Test safety check
        example_safe = {**example, "safety_checks": ["no_execution"]}
        check_result_safe = manager._check_safety(example_safe, "quantum_algorithm")
        self.assertTrue(check_result_safe["passed"])
        
        # Test unsafe example
        example_unsafe = {**example, "safety_checks": ["real_hardware"]}
        check_result_unsafe = manager._check_safety(example_unsafe, "quantum_algorithm")
        self.assertFalse(check_result_unsafe["passed"])


class TestQuantumTraceLogger(unittest.TestCase):
    """Test Quantum Trace Logger."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_trace_lifecycle(self):
        """Test trace creation, update, and completion."""
        from quantum_trace_logger import QuantumTraceLogger
        from quantum_mode_schema import TraceStep, TraceStatus
        
        logger = QuantumTraceLogger(log_dir=Path(self.temp_dir))
        
        # Start trace
        trace = logger.start_trace(
            query="Test query",
            context={"test": True},
            source="test"
        )
        
        self.assertIsNotNone(trace)
        self.assertEqual(trace.query, "Test query")
        self.assertEqual(trace.status, TraceStatus.ACTIVE.value)
        
        # Update trace
        updated = logger.update_trace(
            trace_id=trace.trace_id,
            test_field="test_value",
            step=TraceStep.CLASSIFICATION.value
        )
        
        self.assertIsNotNone(updated)
        self.assertEqual(updated.metadata.get("test_field"), "test_value")
        
        # Complete trace
        completed = logger.complete_trace(
            trace_id=trace.trace_id,
            success=True,
            execution_result={"result": "success"},
            step=TraceStep.EXECUTION.value
        )
        
        self.assertIsNotNone(completed)
        self.assertEqual(completed.status, TraceStatus.COMPLETED.value)
        
        # Get trace summary
        summary = logger.get_trace_summary(trace.trace_id)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["trace_id"], trace.trace_id)
    
    def test_trace_failure(self):
        """Test trace failure handling."""
        from quantum_trace_logger import QuantumTraceLogger
        from quantum_mode_schema import QuantumErrorCode, Severity, TraceStep
        
        logger = QuantumTraceLogger(log_dir=Path(self.temp_dir))
        
        trace = logger.start_trace(
            query="Test query",
            context={},
            source="test"
        )
        
        # Fail trace
        failed = logger.fail_trace(
            trace_id=trace.trace_id,
            error_code=QuantumErrorCode.QMODE_RETRIEVAL_EMPTY.value,
            error_message="No examples found",
            severity=Severity.MEDIUM.value,
            step=TraceStep.RETRIEVAL.value
        )
        
        self.assertIsNotNone(failed)
        self.assertEqual(failed.error_code, QuantumErrorCode.QMODE_RETRIEVAL_EMPTY.value)
    
    def test_session_metrics(self):
        """Test session metrics collection."""
        from quantum_trace_logger import QuantumTraceLogger
        
        logger = QuantumTraceLogger(log_dir=Path(self.temp_dir))
        
        # Create multiple traces
        for i in range(3):
            trace = logger.start_trace(
                query=f"Test query {i}",
                context={},
                source="test"
            )
            
            if i % 2 == 0:
                logger.complete_trace(
                    trace_id=trace.trace_id,
                    success=True,
                    execution_result={},
                    step="test"
                )
            else:
                logger.fail_trace(
                    trace_id=trace.trace_id,
                    error_code="TEST_ERROR",
                    error_message="Test failure",
                    severity="low",
                    step="test"
                )
        
        # Get metrics
        metrics = logger.get_session_metrics()
        
        self.assertIsInstance(metrics, dict)
        self.assertEqual(metrics["total_traces"], 3)
        self.assertEqual(metrics["completed_traces"], 2)
        self.assertEqual(metrics["failed_traces"], 1)


class TestPredictiveRiskScorer(unittest.TestCase):
    """Test Predictive Risk Scorer."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_risk_assessment(self):
        """Test risk assessment functionality."""
        from predictive_risk_scorer import PredictiveRiskScorer
        
        scorer = PredictiveRiskScorer()
        
        # Test task risk assessment
        task_data = {
            "query": "Implement quantum algorithm with system calls",
            "task_type": "quantum_algorithm",
            "confidence": 0.7,
            "context": {"user": "test"},
            "trace_id": "test_trace"
        }
        
        assessment = scorer.assess_task_risk(task_data)
        
        self.assertIsNotNone(assessment)
        self.assertIn("risk_band", assessment.to_dict())
        self.assertIn("score", assessment.to_dict())
        self.assertIn("factors", assessment.to_dict())
        self.assertIn("recommendations", assessment.to_dict())
        
        # Test risk bands
        risk_band = assessment.risk_band
        self.assertIn(risk_band, ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    
    def test_risk_factors(self):
        """Test risk factor collection."""
        from predictive_risk_scorer import PredictiveRiskScorer
        
        scorer = PredictiveRiskScorer()
        
        task_data = {
            "query": "Test",
            "task_type": "quantum_algorithm",
            "confidence": 0.5,
            "context": {},
            "trace_id": "test"
        }
        
        factors = scorer._collect_risk_factors(task_data)
        
        self.assertIsInstance(factors, list)
        self.assertGreater(len(factors), 0)
        
        # Check factor structure
        for factor in factors:
            self.assertIn("name", factor.to_dict())
            self.assertIn("score", factor.to_dict())
            self.assertIn("weight", factor.to_dict())
            self.assertIn("description", factor.to_dict())
    
    def test_trend_analysis(self):
        """Test trend analysis."""
        from predictive_risk_scorer import PredictiveRiskScorer
        
        scorer = PredictiveRiskScorer()
        
        trends = scorer.analyze_trends()
        
        self.assertIsInstance(trends, dict)
        self.assertIn("recent_tasks", trends)
        self.assertIn("error_trends", trends)
        self.assertIn("risk_profile", trends)


class TestQuantumExecutor(unittest.TestCase):
    """Test Quantum Executor."""
    
    def setUp(self):
        from quantum_mode_schema import QuantumModeConfig
        from quantum_trace_logger import QuantumTraceLogger
        
        self.config = QuantumModeConfig()
        self.trace_logger = QuantumTraceLogger()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_safety_analysis(self):
        """Test code safety analysis."""
        from quantum_executor import QuantumExecutor
        
        executor = QuantumExecutor(
            config=self.config,
            trace_logger=self.trace_logger
        )
        
        # Test safe code
        safe_code = """
from qiskit import QuantumCircuit
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
"""
        
        # Test unsafe code
        unsafe_code = """
import os
os.system("rm -rf /")
"""
        
        # Mock objects for testing
        from quantum_mode_schema import QuantumTask, RetrievalResult
        
        task = QuantumTask(
            task_id="test",
            query="Test",
            task_type="quantum_algorithm",
            created_at=datetime.now().isoformat()
        )
        
        retrieval_result = RetrievalResult(
            query="Test",
            task_type="quantum_algorithm",
            examples=[{"id": "test", "solution": safe_code, "framework": "qiskit"}],
            match_scores=[1.0],
            confidence_level="high",
            retrieval_time=datetime.now().isoformat()
        )
        
        # Test safety analysis
        safety_result = executor._analyze_safety(task, retrieval_result)
        self.assertTrue(safety_result["safe"])
        
        # Test with unsafe code
        retrieval_result_unsafe = RetrievalResult(
            query="Test",
            task_type="quantum_algorithm",
            examples=[{"id": "test", "solution": unsafe_code, "framework": "qiskit"}],
            match_scores=[1.0],
            confidence_level="high",
            retrieval_time=datetime.now().isoformat()
        )
        
        safety_result_unsafe = executor._analyze_safety(task, retrieval_result_unsafe)
        self.assertFalse(safety_result_unsafe["safe"])
        self.assertGreater(len(safety_result_unsafe["issues"]), 0)
    
    def test_execution_modes(self):
        """Test execution mode determination."""
        from quantum_executor import QuantumExecutor
        from quantum_mode_schema import QuantumTask, RetrievalResult, VerificationResult
        
        executor = QuantumExecutor(
            config=self.config,
            trace_logger=self.trace_logger
        )
        
        task = QuantumTask(
            task_id="test",
            query="Test",
            task_type="quantum_algorithm",
            created_at=datetime.now().isoformat()
        )
        
        retrieval_result = RetrievalResult(
            query="Test",
            task_type="quantum_algorithm",
            examples=[{"id": "test", "solution": "test", "framework": "qiskit"}],
            match_scores=[1.0],
            confidence_level="high",
            retrieval_time=datetime.now().isoformat()
        )
        
        # Test with passed verification
        verification_passed = type('obj', (object,), {
            'verification_status': 'passed',
            'overall_score': 0.9
        })()
        
        mode_passed = executor._determine_execution_mode(
            task, retrieval_result, verification_passed
        )
        self.assertIn(mode_passed, ["simulation", "sandboxed", "explanation_only"])
        
        # Test with failed verification
        verification_failed = type('obj', (object,), {
            'verification_status': 'failed',
            'overall_score': 0.3
        })()
        
        mode_failed = executor._determine_execution_mode(
            task, retrieval_result, verification_failed
        )
        self.assertEqual(mode_failed, "explanation_only")


class TestProjectXIntegration(unittest.TestCase):
    """Test ProjectX Integration."""
    
    def test_mock_integration(self):
        """Test mock ProjectX integration."""
        from projectx_integration import MockProjectXIntegration
        
        mock = MockProjectXIntegration(approval_rate=0.8)
        
        # Create mock objects
        task = type('obj', (object,), {
            'task_id': 'test',
            'task_type': 'quantum_algorithm',
            'created_at': datetime.now().isoformat()
        })()
        
        retrieval_result = type('obj', (object,), {
            'examples': [{"id": "test"}],
            'confidence_level': "high",
            'match_scores': [0.9]
        })()
        
        verification_result = type('obj', (object,), {
            'verification_status': "passed",
            'overall_score': 0.85
        })()
        
        # Request judgment
        judgment = mock.request_judgment(
            query="Test query",
            task=task,
            retrieval_result=retrieval_result,
            verification_result=verification_result,
            trace_id="test_trace"
        )
        
        self.assertIsInstance(judgment, dict)
        self.assertIn("approved", judgment)
        self.assertIn("reasoning", judgment)
        self.assertIn("confidence", judgment)
        self.assertTrue(judgment.get("mock", False))


class TestQuantumModeEngine(unittest.TestCase):
    """Test Quantum Mode Engine integration."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dataset_dir = Path(self.temp_dir) / "quantum_dataset"
        self.dataset_dir.mkdir(parents=True)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        from quantum_mode_engine import QuantumModeEngine
        
        engine = QuantumModeEngine(
            dataset_dir=self.dataset_dir,
            enable_learning=False,
            enable_risk_scoring=False
        )
        
        self.assertIsNotNone(engine)
        self.assertIsNotNone(engine._config)
        self.assertIsNotNone(engine._trace_logger)
        self.assertIsNotNone(engine._dataset_manager)
        self.assertIsNotNone(engine._executor)
    
    def test_query_processing(self):
        """Test query processing flow."""
        from quantum_mode_engine import QuantumModeEngine
        
        engine = QuantumModeEngine(
            dataset_dir=self.dataset_dir,
            enable_learning=False,
            enable_risk_scoring=False
        )
        
        # Test non-quantum query
        result = engine.process_query("What is the weather today?")
        self.assertIsInstance(result, dict)
        
        # Should exit quantum mode for non-quantum query
        if "should_exit_quantum_mode" in result:
            self.assertTrue(result["should_exit_quantum_mode"])
        
        # Test quantum query
        result = engine.process_query("Implement Grover's quantum search algorithm")
        self.assertIsInstance(result, dict)
        
        # Check for expected keys
        if result.get("success", False):
            self.assertIn("task", result)
            self.assertIn("retrieval_result", result)
            self.assertIn("execution_result", result)
        else:
            # Even if failed, should have error information
            self.assertIn("error", result)
    
    def test_engine_metrics(self):
        """Test engine metrics collection."""
        from quantum_mode_engine import QuantumModeEngine
        
        engine = QuantumModeEngine(
            dataset_dir=self.dataset_dir,
            enable_learning=False,
            enable_risk_scoring=False
        )
        
        # Process a query to generate metrics
        engine.process_query("Test quantum algorithm")
        
        # Get metrics
        metrics = engine.get_metrics()
        
        self.assertIsInstance(metrics, dict)
        self.assertIn("traces", metrics)
        self.assertIn("risk_profile", metrics)
        self.assertIn("dataset_stats", metrics)
        self.assertIn("config", metrics)


class TestQuantumModeCLI(unittest.TestCase):
    """Test Quantum Mode CLI."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dataset_dir = Path(self.temp_dir) / "quantum_dataset"
        self.dataset_dir.mkdir(parents=True)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cli_initialization(self):
        """Test CLI initialization."""
        from quantum_mode_cli import QuantumModeCLI
        
        cli = QuantumModeCLI()
        
        # Initialize engine
        success = cli.init_engine(dataset_dir=self.dataset_dir)
        self.assertTrue(success)
        
        # Check components
        self.assertIsNotNone(cli.engine)
        self.assertIsNotNone(cli.dataset_manager)
        self.assertIsNotNone(cli.executor)
    
    def test_cli_commands(self):
        """Test CLI commands."""
        from quantum_mode_cli import QuantumModeCLI
        
        cli = QuantumModeCLI()
        cli.init_engine(dataset_dir=self.dataset_dir)
        
        # Test dataset stats
        stats = cli.dataset_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("total_examples", stats)
        
        # Test retrieval
        retrieval = cli.retrieve_examples("Quantum algorithm")
        self.assertIsInstance(retrieval, dict)
        
        # Test metrics
        metrics = cli.get_metrics()
        self.assertIsInstance(metrics, dict)


def run_all_tests():
    """Run all tests and return results."""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTest(unittest.makeSuite(TestQuantumModeSchema))
    suite.addTest(unittest.makeSuite(TestQuantumDatasetManager))
    suite.addTest(unittest.makeSuite(TestQuantumTraceLogger))
    suite.addTest(unittest.makeSuite(TestPredictiveRiskScorer))
    suite.addTest(unittest.makeSuite(TestQuantumExecutor))
    suite.addTest(unittest.makeSuite(TestProjectXIntegration))
    suite.addTest(unittest.makeSuite(TestQuantumModeEngine))
    suite.addTest(unittest.makeSuite(TestQuantumModeCLI))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


def main():
    """Main test runner."""
    print("=" * 80)
    print("Stray Goose Quantum Mode - Comprehensive Test Suite")
    print("=" * 80)
    print()
    
    # Run tests
    result = run_all_tests()
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        
        # Print failures
        if result.failures:
            print("\nFAILURES:")
            for test, traceback in result.failures:
                print(f"\n{test}:")
                print(traceback)
        
        # Print errors
        if result.errors:
            print("\nERRORS:")
            for test, traceback in result.errors:
                print(f"\n{test}:")
                print(traceback)
        
        return 1


if __name__ == "__main__":
    sys.exit(main())