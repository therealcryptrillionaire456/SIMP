#!/usr/bin/env python3
"""
Quantum Mode CLI for Stray Goose

Command-line interface for the comprehensive Quantum Mode system.
Provides access to all Quantum Mode functionality through a unified CLI.
"""

import json
import sys
import argparse
import textwrap
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QuantumModeCLI:
    """Command-line interface for Quantum Mode."""
    
    def __init__(self):
        self.engine = None
        self.dataset_manager = None
        self.executor = None
        self.projectx_integration = None
        
    def init_engine(self, config_path: Optional[Path] = None,
                   dataset_dir: Optional[Path] = None,
                   projectx_endpoint: Optional[str] = None):
        """Initialize Quantum Mode Engine."""
        try:
            from quantum_mode_engine import QuantumModeEngine
            
            self.engine = QuantumModeEngine(
                config_path=config_path,
                dataset_dir=dataset_dir,
                projectx_endpoint=projectx_endpoint
            )
            
            # Get references to components
            self.dataset_manager = self.engine._dataset_manager
            self.executor = self.engine._executor
            
            if projectx_endpoint:
                from projectx_integration import ProjectXIntegration
                self.projectx_integration = ProjectXIntegration(projectx_endpoint)
            
            logger.info("Quantum Mode Engine initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize engine: {e}")
            return False
    
    def process_query(self, query: str, context: Optional[Dict] = None) -> Dict:
        """Process a quantum query."""
        if not self.engine:
            return {"error": "Engine not initialized. Run 'init' first."}
        
        return self.engine.process_query(query, context)
    
    def get_metrics(self) -> Dict:
        """Get system metrics."""
        if not self.engine:
            return {"error": "Engine not initialized. Run 'init' first."}
        
        return self.engine.get_metrics()
    
    def export_data(self, output_dir: Optional[Path] = None) -> Dict:
        """Export training data."""
        if not self.engine:
            return {"error": "Engine not initialized. Run 'init' first."}
        
        return self.engine.export_training_data(output_dir)
    
    def dataset_stats(self) -> Dict:
        """Get dataset statistics."""
        if not self.dataset_manager:
            return {"error": "Dataset manager not available"}
        
        return self.dataset_manager.get_stats()
    
    def retrieve_examples(self, query: str, task_type: str = "quantum_algorithm") -> Dict:
        """Retrieve examples from dataset."""
        if not self.dataset_manager:
            return {"error": "Dataset manager not available"}
        
        result = self.dataset_manager.retrieve_examples(query, task_type)
        return result.to_dict()
    
    def verify_examples(self, query: str, task_type: str = "quantum_algorithm") -> Dict:
        """Verify retrieved examples."""
        if not self.dataset_manager:
            return {"error": "Dataset manager not available"}
        
        # First retrieve
        retrieval = self.dataset_manager.retrieve_examples(query, task_type)
        
        # Then verify
        verification = self.dataset_manager.verify_examples(retrieval, task_type)
        
        return {
            "retrieval": retrieval.to_dict(),
            "verification": verification.to_dict()
        }
    
    def execute_code(self, code_file: str, mode: str = "simulation") -> Dict:
        """Execute quantum code."""
        if not self.executor:
            return {"error": "Executor not available"}
        
        # Read code
        with open(code_file, 'r') as f:
            code = f.read()
        
        # Create mock objects for execution
        from quantum_mode_schema import QuantumTask, RetrievalResult
        from quantum_trace_logger import QuantumTraceLogger
        
        task = QuantumTask(
            task_id="cli_execution",
            query="CLI code execution",
            task_type="quantum_algorithm",
            created_at=datetime.now().isoformat()
        )
        
        retrieval_result = RetrievalResult(
            query="CLI execution",
            task_type="quantum_algorithm",
            examples=[{"id": "cli_example", "solution": code, "framework": "qiskit"}],
            match_scores=[1.0],
            confidence_level="high",
            retrieval_time=datetime.now().isoformat()
        )
        
        verification_result = type('obj', (object,), {
            'verification_status': 'passed',
            'overall_score': 0.9
        })()
        
        trace_logger = QuantumTraceLogger()
        trace_id = f"cli_exec_{datetime.now().timestamp()}"
        
        # Execute
        result = self.executor.execute(
            task=task,
            retrieval_result=retrieval_result,
            verification_result=verification_result,
            trace_id=trace_id
        )
        
        return result
    
    def projectx_judgment(self, query: str, task_type: str = "quantum_algorithm") -> Dict:
        """Get ProjectX judgment."""
        if not self.projectx_integration:
            return {"error": "ProjectX integration not available"}
        
        # Create mock objects
        task = type('obj', (object,), {
            'task_id': 'cli_judgment',
            'task_type': task_type,
            'created_at': datetime.now().isoformat()
        })()
        
        retrieval_result = type('obj', (object,), {
            'examples': [
                {
                    "id": "example_1",
                    "framework": "qiskit",
                    "complexity": "intermediate",
                    "verification_status": "verified",
                    "safety_checks": ["no_execution"],
                    "tags": ["test"]
                }
            ],
            'confidence_level': "high",
            'match_scores': [0.9]
        })()
        
        verification_result = type('obj', (object,), {
            'verification_status': "passed",
            'overall_score': 0.85
        })()
        
        trace_id = f"cli_judgment_{datetime.now().timestamp()}"
        
        judgment = self.projectx_integration.request_judgment(
            query=query,
            task=task,
            retrieval_result=retrieval_result,
            verification_result=verification_result,
            trace_id=trace_id
        )
        
        return judgment


def print_result(result: Dict, format: str = "json"):
    """Print result in specified format."""
    if format == "json":
        print(json.dumps(result, indent=2))
    elif format == "pretty":
        _print_pretty(result)
    else:
        print(str(result))


def _print_pretty(result: Dict):
    """Print result in pretty format."""
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return
    
    if "success" in result:
        if result["success"]:
            print("✅ Success!")
        else:
            print("❌ Failed")
    
    # Print key information
    for key, value in result.items():
        if key not in ["success", "error"]:
            if isinstance(value, dict):
                print(f"\n📊 {key.upper()}:")
                for subkey, subvalue in value.items():
                    if isinstance(subvalue, (dict, list)):
                        print(f"  {subkey}: {type(subvalue).__name__}")
                    else:
                        print(f"  {subkey}: {subvalue}")
            elif isinstance(value, list):
                print(f"\n📋 {key.upper()} ({len(value)} items):")
                for i, item in enumerate(value[:3]):  # Show first 3
                    print(f"  {i+1}. {str(item)[:100]}...")
                if len(value) > 3:
                    print(f"  ... and {len(value) - 3} more")
            else:
                print(f"{key}: {value}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Quantum Mode CLI for Stray Goose",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          quantum_mode_cli.py init --config config.json
          quantum_mode_cli.py process "Implement Grover's algorithm"
          quantum_mode_cli.py dataset-stats
          quantum_mode_cli.py retrieve "Quantum circuit for entanglement"
          quantum_mode_cli.py execute my_quantum_code.py --mode simulation
        """)
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize Quantum Mode Engine")
    init_parser.add_argument("--config", help="Path to config file")
    init_parser.add_argument("--dataset-dir", help="Path to dataset directory")
    init_parser.add_argument("--projectx-endpoint", help="ProjectX endpoint URL")
    
    # Process command
    process_parser = subparsers.add_parser("process", help="Process a quantum query")
    process_parser.add_argument("query", help="Quantum query to process")
    process_parser.add_argument("--context", help="JSON context string")
    
    # Metrics command
    metrics_parser = subparsers.add_parser("metrics", help="Get system metrics")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export training data")
    export_parser.add_argument("--output-dir", help="Output directory")
    
    # Dataset commands
    dataset_parser = subparsers.add_parser("dataset-stats", help="Get dataset statistics")
    
    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve examples")
    retrieve_parser.add_argument("query", help="Query for retrieval")
    retrieve_parser.add_argument("--task-type", default="quantum_algorithm", 
                               help="Task type for retrieval")
    
    verify_parser = subparsers.add_parser("verify", help="Verify examples")
    verify_parser.add_argument("query", help="Query for verification")
    verify_parser.add_argument("--task-type", default="quantum_algorithm",
                             help="Task type for verification")
    
    # Execute command
    execute_parser = subparsers.add_parser("execute", help="Execute quantum code")
    execute_parser.add_argument("code_file", help="Path to code file")
    execute_parser.add_argument("--mode", choices=["explanation", "simulation", "sandboxed"],
                              default="simulation", help="Execution mode")
    
    # ProjectX command
    projectx_parser = subparsers.add_parser("projectx", help="Get ProjectX judgment")
    projectx_parser.add_argument("query", help="Query for judgment")
    projectx_parser.add_argument("--task-type", default="quantum_algorithm",
                               help="Task type for judgment")
    
    # Common arguments
    for subparser in [process_parser, metrics_parser, export_parser, dataset_parser,
                     retrieve_parser, verify_parser, execute_parser, projectx_parser]:
        subparser.add_argument("--format", choices=["json", "pretty"], 
                             default="pretty", help="Output format")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize CLI
    cli = QuantumModeCLI()
    
    try:
        if args.command == "init":
            # Initialize engine
            config_path = Path(args.config) if args.config else None
            dataset_dir = Path(args.dataset_dir) if args.dataset_dir else None
            
            success = cli.init_engine(
                config_path=config_path,
                dataset_dir=dataset_dir,
                projectx_endpoint=args.projectx_endpoint
            )
            
            result = {"initialized": success}
            if not success:
                result["error"] = "Failed to initialize engine"
        
        elif args.command == "process":
            # Parse context if provided
            context = json.loads(args.context) if args.context else None
            
            # Initialize engine if not already
            if not cli.engine:
                cli.init_engine()
            
            result = cli.process_query(args.query, context)
        
        elif args.command == "metrics":
            # Initialize engine if not already
            if not cli.engine:
                cli.init_engine()
            
            result = cli.get_metrics()
        
        elif args.command == "export":
            # Initialize engine if not already
            if not cli.engine:
                cli.init_engine()
            
            output_dir = Path(args.output_dir) if args.output_dir else None
            result = cli.export_data(output_dir)
        
        elif args.command == "dataset-stats":
            # Initialize engine if not already
            if not cli.engine:
                cli.init_engine()
            
            result = cli.dataset_stats()
        
        elif args.command == "retrieve":
            # Initialize engine if not already
            if not cli.engine:
                cli.init_engine()
            
            result = cli.retrieve_examples(args.query, args.task_type)
        
        elif args.command == "verify":
            # Initialize engine if not already
            if not cli.engine:
                cli.init_engine()
            
            result = cli.verify_examples(args.query, args.task_type)
        
        elif args.command == "execute":
            # Initialize engine if not already
            if not cli.engine:
                cli.init_engine()
            
            result = cli.execute_code(args.code_file, args.mode)
        
        elif args.command == "projectx":
            # Initialize engine if not already
            if not cli.engine:
                cli.init_engine()
            
            result = cli.projectx_judgment(args.query, args.task_type)
        
        else:
            result = {"error": f"Unknown command: {args.command}"}
        
        # Print result
        print_result(result, args.format)
        
        # Return appropriate exit code
        if "error" in result or result.get("success") is False:
            return 1
        else:
            return 0
        
    except Exception as e:
        logger.error(f"CLI error: {e}", exc_info=True)
        result = {"error": str(e), "command": args.command}
        print_result(result, args.format)
        return 1


if __name__ == "__main__":
    sys.exit(main())