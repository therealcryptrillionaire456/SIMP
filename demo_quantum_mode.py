#!/usr/bin/env python3
"""
Demonstration of Stray Goose Quantum Mode.

Shows the complete workflow of the Quantum Mode system:
1. Query classification
2. Dataset retrieval
3. Verification
4. Risk assessment
5. Execution with safety checks
6. Learning signal generation
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def print_header(text):
    """Print section header."""
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)


def print_step(step_num, title):
    """Print step header."""
    print(f"\n{'─' * 40}")
    print(f"STEP {step_num}: {title}")
    print(f"{'─' * 40}")


def demo_basic_workflow():
    """Demonstrate basic quantum mode workflow."""
    print_header("Stray Goose Quantum Mode - Basic Workflow Demo")
    
    # Create temporary directory for demo
    temp_dir = tempfile.mkdtemp()
    dataset_dir = Path(temp_dir) / "quantum_dataset"
    
    print(f"Using temporary directory: {temp_dir}")
    
    try:
        # Step 1: Initialize Quantum Mode Engine
        print_step(1, "Initializing Quantum Mode Engine")
        
        from quantum_mode_engine import QuantumModeEngine
        
        engine = QuantumModeEngine(
            dataset_dir=dataset_dir,
            enable_learning=True,
            enable_risk_scoring=True
        )
        
        print("✅ Engine initialized")
        print(f"   • Dataset directory: {dataset_dir}")
        print(f"   • Learning enabled: Yes")
        print(f"   • Risk scoring enabled: Yes")
        
        # Step 2: Show initial metrics
        print_step(2, "Initial System Metrics")
        
        metrics = engine.get_metrics()
        print(f"   • Dataset examples: {metrics['dataset_stats'].get('total_examples', 0)}")
        print(f"   • Task types: {len(metrics['dataset_stats'].get('by_task_type', {}))}")
        print(f"   • Frameworks: {len(metrics['dataset_stats'].get('by_framework', {}))}")
        
        # Step 3: Process a non-quantum query
        print_step(3, "Processing Non-Quantum Query")
        
        non_quantum_query = "What is the capital of France?"
        print(f"   Query: '{non_quantum_query}'")
        
        result = engine.process_query(non_quantum_query)
        
        if result.get("should_exit_quantum_mode", False):
            print("   ✅ Correctly identified as non-quantum query")
            print(f"   Action: Exit quantum mode, handle normally")
        else:
            print("   ⚠️  Might be incorrectly classified as quantum")
        
        # Step 4: Process a simple quantum query
        print_step(4, "Processing Simple Quantum Query")
        
        simple_quantum_query = "Create a Bell state circuit"
        print(f"   Query: '{simple_quantum_query}'")
        
        result = engine.process_query(simple_quantum_query)
        
        if result.get("success", False):
            print("   ✅ Successfully processed quantum query")
            print(f"   Task type: {result['task']['task_type']}")
            print(f"   Examples found: {len(result['retrieval_result']['examples'])}")
            print(f"   Verification score: {result['verification_result']['overall_score']:.2f}")
            print(f"   Execution mode: {result['execution_result'].get('execution_mode', 'unknown')}")
        else:
            print(f"   ❌ Processing failed: {result.get('error', 'Unknown error')}")
            if "error_code" in result:
                print(f"   Error code: {result['error_code']}")
        
        # Step 5: Process a complex quantum query
        print_step(5, "Processing Complex Quantum Query")
        
        complex_quantum_query = "Implement Grover's search algorithm for database lookup"
        print(f"   Query: '{complex_quantum_query}'")
        
        result = engine.process_query(complex_quantum_query)
        
        print(f"   Success: {result.get('success', False)}")
        if "error" in result:
            print(f"   Error: {result['error']}")
        if "retrieval_result" in result:
            print(f"   Examples retrieved: {len(result['retrieval_result']['examples'])}")
        
        # Step 6: Show final metrics
        print_step(6, "Final System Metrics")
        
        final_metrics = engine.get_metrics()
        traces = final_metrics['traces']
        
        print(f"   Total traces: {traces.get('total_traces', 0)}")
        print(f"   Completed traces: {traces.get('completed_traces', 0)}")
        print(f"   Failed traces: {traces.get('failed_traces', 0)}")
        print(f"   Active traces: {traces.get('active_traces', 0)}")
        
        # Step 7: Export training data
        print_step(7, "Exporting Training Data")
        
        export_dir = Path(temp_dir) / "export"
        export_data = engine.export_training_data(export_dir)
        
        print(f"   Export directory: {export_dir}")
        print(f"   Traces exported: {len(export_data['traces'].get('traces', []))}")
        print(f"   Risk assessments: {len(export_data['risk_assessments'].get('assessments', []))}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        print(f"\nCleaning up temporary directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


def demo_individual_components():
    """Demonstrate individual components of the system."""
    print_header("Stray Goose Quantum Mode - Component Demo")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 1. Dataset Manager Demo
        print_step(1, "Quantum Dataset Manager")
        
        from quantum_dataset_manager import QuantumDatasetManager
        
        dataset_dir = Path(temp_dir) / "dataset"
        manager = QuantumDatasetManager(dataset_dir=dataset_dir)
        
        stats = manager.get_stats()
        print(f"   • Total examples: {stats['total_examples']}")
        print(f"   • Task types: {list(stats['by_task_type'].keys())}")
        
        # Test retrieval
        retrieval = manager.retrieve_examples(
            query="Quantum entanglement circuit",
            task_type="quantum_circuit"
        )
        print(f"   • Examples retrieved: {len(retrieval.examples)}")
        
        # Test verification
        verification = manager.verify_examples(retrieval, "quantum_circuit")
        print(f"   • Verification status: {verification.verification_status}")
        print(f"   • Verification score: {verification.overall_score:.2f}")
        
        # 2. Trace Logger Demo
        print_step(2, "Quantum Trace Logger")
        
        from quantum_trace_logger import QuantumTraceLogger
        from quantum_mode_schema import TraceStep
        
        trace_dir = Path(temp_dir) / "traces"
        trace_logger = QuantumTraceLogger(log_dir=trace_dir)
        
        # Create a trace
        trace = trace_logger.start_trace(
            task_id="demo_trace_001",
            step=TraceStep.CLASSIFICATION.value,
            query="Test query",
            context={"demo": True},
            source="demo"
        )
        print(f"   • Trace created: {trace.trace_id}")
        
        # Update trace
        trace_logger.update_trace(
            trace_id=trace.trace_id,
            demo_field="test_value"
        )
        
        # Complete trace
        trace_logger.complete_trace(
            trace_id=trace.trace_id,
            success=True,
            execution_result={"result": "demo_success"}
        )
        
        # Get metrics
        metrics = trace_logger.get_session_metrics()
        trace_counts = metrics.get('trace_counts', {})
        print(f"   • Total traces: {trace_counts.get('traces_started', 0)}")
        
        # 3. Risk Scorer Demo
        print_step(3, "Predictive Risk Scorer")
        
        from predictive_risk_scorer import PredictiveRiskScorer
        
        risk_scorer = PredictiveRiskScorer()
        
        # Assess risk
        task_data = {
            "query": "Quantum algorithm with system access",
            "task_type": "quantum_algorithm",
            "confidence": 0.6,
            "context": {"user": "demo"},
            "trace_id": "demo_trace"
        }
        
        assessment = risk_scorer.assess_task_risk(task_data)
        print(f"   • Risk band: {assessment.risk_band}")
        print(f"   • Risk score: {assessment.score:.2f}")
        print(f"   • Risk factors: {len(assessment.factors)}")
        
        # 4. Executor Demo
        print_step(4, "Quantum Executor")
        
        from quantum_executor import QuantumExecutor
        from quantum_mode_schema import QuantumModeConfig
        
        config = QuantumModeConfig()
        executor = QuantumExecutor(config=config, trace_logger=trace_logger)
        
        # Test safety analysis
        safe_code = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(2)"
        
        from quantum_mode_schema import QuantumTask, RetrievalResult
        
        task = QuantumTask(
            task_id="demo_task",
            query="Demo task",
            task_type="quantum_circuit",
            algorithm_family="demo",
            framework_requested="qiskit",
            parameters={"demo": True},
            required_fields=["framework", "solution"]
        )
        
        retrieval_result = RetrievalResult(
            query="Demo",
            task_type="quantum_circuit",
            examples=[{"id": "demo", "solution": safe_code, "framework": "qiskit"}],
            match_scores=[1.0],
            confidence_level="high",
            retrieval_time=datetime.now().isoformat()
        )
        
        safety = executor._analyze_safety(task, retrieval_result)
        print(f"   • Code safety: {'✅ Safe' if safety['safe'] else '❌ Unsafe'}")
        if not safety['safe']:
            print(f"   • Safety issues: {len(safety['issues'])}")
        
        print("\n✅ All components demonstrated successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Component demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def demo_cli_interface():
    """Demonstrate CLI interface."""
    print_header("Stray Goose Quantum Mode - CLI Interface Demo")
    
    temp_dir = tempfile.mkdtemp()
    
    print("The CLI provides access to all Quantum Mode functionality:")
    print()
    print("Available commands:")
    print("  init                    - Initialize Quantum Mode Engine")
    print("  process <query>         - Process a quantum query")
    print("  metrics                 - Get system metrics")
    print("  dataset-stats           - Get dataset statistics")
    print("  retrieve <query>        - Retrieve examples")
    print("  verify <query>          - Verify examples")
    print("  execute <file>          - Execute quantum code")
    print("  export                  - Export training data")
    print()
    print("Example usage:")
    print(f"  python quantum_mode_cli.py init --dataset-dir {temp_dir}/dataset")
    print('  python quantum_mode_cli.py process "Implement quantum algorithm"')
    print('  python quantum_mode_cli.py dataset-stats')
    print()
    print("For more details, run: python quantum_mode_cli.py --help")
    
    shutil.rmtree(temp_dir, ignore_errors=True)
    return True


def main():
    """Main demo function."""
    print("\n" + "=" * 80)
    print("STRAY GOOSE QUANTUM MODE - COMPREHENSIVE DEMONSTRATION")
    print("=" * 80)
    print("\nThis demo shows the complete Quantum Mode system for Stray Goose.")
    print("The system implements retrieval-first quantum algorithm handling")
    print("with safety checks, verification, and learning signals.")
    print()
    
    # Run demos
    demos = [
        ("Basic Workflow", demo_basic_workflow),
        ("Individual Components", demo_individual_components),
        ("CLI Interface", demo_cli_interface)
    ]
    
    results = []
    for name, demo_func in demos:
        print(f"\n{'=' * 60}")
        print(f"Running: {name}")
        print(f"{'=' * 60}")
        
        try:
            success = demo_func()
            results.append((name, success))
        except KeyboardInterrupt:
            print("\n⚠️  Demo interrupted by user")
            results.append((name, False))
            break
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            results.append((name, False))
    
    # Print summary
    print_header("Demo Summary")
    
    all_passed = all(success for _, success in results)
    
    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {name:30} {status}")
    
    print()
    if all_passed:
        print("🎉 All demos completed successfully!")
        print("\nThe Quantum Mode system is ready for integration with Stray Goose.")
        print("Key features implemented:")
        print("  • Retrieval-first quantum algorithm handling")
        print("  • Multi-layer verification system")
        print("  • Predictive risk scoring")
        print("  • Safety-checked execution modes")
        print("  • ProjectX integration for escalation")
        print("  • Comprehensive tracing and learning")
    else:
        print("⚠️  Some demos failed. Check the output above for details.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())