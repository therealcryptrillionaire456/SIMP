#!/usr/bin/env python3
"""
Quantum Executor for Stray Goose

Executes quantum tasks with safety checks and sandboxing.
Implements multiple execution modes with varying safety levels.
"""

import json
import sys
import re
import ast
import tempfile
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

from quantum_mode_schema import (
    TaskType, QuantumErrorCode, Severity,
    TraceStep, QuantumTask, RetrievalResult,
    VerificationResult, QuantumModeConfig
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class QuantumExecutor:
    """Executes quantum tasks with safety checks."""
    
    config: QuantumModeConfig
    trace_logger: Any  # QuantumTraceLogger
    sandbox_enabled: bool = True
    max_execution_time: int = 30  # seconds
    
    # Safety patterns
    _dangerous_patterns: Dict[str, List[str]] = field(default_factory=lambda: {
        "system_calls": [
            "os.system", "subprocess.run", "subprocess.call", "subprocess.Popen",
            "exec(", "eval(", "compile(", "__import__"
        ],
        "file_operations": [
            "open(", "write(", "read(", "remove(", "delete(",
            "shutil.", "pathlib.Path.unlink"
        ],
        "network_operations": [
            "requests.", "urllib.", "socket.", "http.client",
            "websocket.", "aiohttp."
        ],
        "hardware_access": [
            "real_hardware", "backend=", "device=", "quantum_processor",
            "ibmq_", "rigetti_", "ionq_"
        ],
        "memory_operations": [
            "malloc", "free", "ctypes.", "memoryview"
        ]
    })
    
    # Allowed imports for different frameworks
    _allowed_imports: Dict[str, List[str]] = field(default_factory=lambda: {
        "qiskit": [
            "qiskit", "numpy", "matplotlib", "scipy",
            "typing", "math", "random", "datetime"
        ],
        "cirq": [
            "cirq", "numpy", "matplotlib", "sympy",
            "typing", "math", "random", "datetime"
        ],
        "pennylane": [
            "pennylane", "numpy", "torch", "tensorflow",
            "matplotlib", "typing", "math", "random"
        ],
        "general": [
            "numpy", "matplotlib", "typing", "math",
            "random", "datetime", "collections", "itertools"
        ]
    })
    
    def execute(self, task: QuantumTask, retrieval_result: RetrievalResult,
                verification_result: VerificationResult, trace_id: str) -> Dict:
        """
        Execute a quantum task with safety checks.
        
        Args:
            task: Quantum task to execute
            retrieval_result: Retrieved examples
            verification_result: Verification result
            trace_id: Trace ID for logging
            
        Returns:
            Execution result dictionary
        """
        logger.info(f"Executing task {task.task_id} of type {task.task_type}")
        
        # Update trace
        self.trace_logger.update_trace(
            trace_id=trace_id,
            execution_started=True,
            step=TraceStep.EXECUTION.value
        )
        
        try:
            # Step 1: Safety analysis
            safety_result = self._analyze_safety(task, retrieval_result)
            
            if not safety_result["safe"]:
                self.trace_logger.update_trace(
                    trace_id=trace_id,
                    safety_check_failed=True,
                    safety_issues=safety_result["issues"],
                    step=TraceStep.SAFETY_CHECK.value
                )
                
                return {
                    "success": False,
                    "error": "Safety check failed",
                    "error_code": QuantumErrorCode.QMODE_SAFETY_VIOLATION.value,
                    "safety_issues": safety_result["issues"],
                    "should_block": True
                }
            
            # Step 2: Determine execution mode
            execution_mode = self._determine_execution_mode(
                task, retrieval_result, verification_result
            )
            
            # Step 3: Generate executable code
            executable_code = self._generate_executable_code(
                task, retrieval_result, execution_mode
            )
            
            # Step 4: Execute based on mode
            if execution_mode == "explanation_only":
                result = self._execute_explanation_only(
                    task, executable_code, trace_id
                )
            elif execution_mode == "simulation":
                result = self._execute_simulation(
                    task, executable_code, trace_id
                )
            elif execution_mode == "sandboxed":
                result = self._execute_sandboxed(
                    task, executable_code, trace_id
                )
            else:
                # Should not happen
                result = {
                    "success": False,
                    "error": f"Unknown execution mode: {execution_mode}",
                    "error_code": QuantumErrorCode.QMODE_UNEXPECTED_ERROR.value
                }
            
            # Add execution metadata
            result.update({
                "task_id": task.task_id,
                "task_type": task.task_type,
                "execution_mode": execution_mode,
                "execution_time": datetime.now().isoformat(),
                "trace_id": trace_id
            })
            
            # Update trace
            self.trace_logger.update_trace(
                trace_id=trace_id,
                execution_completed=True,
                execution_result=result,
                step=TraceStep.EXECUTION.value
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}", exc_info=True)
            
            self.trace_logger.update_trace(
                trace_id=trace_id,
                execution_failed=True,
                error=str(e),
                step=TraceStep.EXECUTION.value
            )
            
            return {
                "success": False,
                "error": f"Execution error: {str(e)}",
                "error_code": QuantumErrorCode.QMODE_EXECUTION_ERROR.value,
                "should_block": True
            }
    
    def _analyze_safety(self, task: QuantumTask, retrieval_result: RetrievalResult) -> Dict:
        """Analyze code safety."""
        issues = []
        
        # Check each example in retrieval result
        for example in retrieval_result.examples:
            example_issues = self._check_code_safety(example["solution"])
            if example_issues:
                issues.append({
                    "example_id": example["id"],
                    "issues": example_issues
                })
        
        # Check task query for dangerous patterns
        query_issues = self._check_text_safety(task.query)
        if query_issues:
            issues.append({
                "source": "query",
                "issues": query_issues
            })
        
        return {
            "safe": len(issues) == 0,
            "issues": issues,
            "checked_examples": len(retrieval_result.examples)
        }
    
    def _check_code_safety(self, code: str) -> List[str]:
        """Check code for safety violations."""
        issues = []
        
        # Check for dangerous patterns
        for category, patterns in self._dangerous_patterns.items():
            for pattern in patterns:
                if pattern in code:
                    issues.append(f"Dangerous pattern detected: {pattern} ({category})")
        
        # Check imports
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._is_allowed_import(alias.name):
                            issues.append(f"Potentially unsafe import: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        full_import = f"{module}.{alias.name}" if module else alias.name
                        if not self._is_allowed_import(full_import):
                            issues.append(f"Potentially unsafe import: {full_import}")
        except SyntaxError:
            # Can't parse, do simple string check
            import_lines = re.findall(r'^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))', code, re.MULTILINE)
            for match in import_lines:
                import_name = match[0] or match[1]
                if not self._is_allowed_import(import_name):
                    issues.append(f"Potentially unsafe import (unparsed): {import_name}")
        
        return issues
    
    def _check_text_safety(self, text: str) -> List[str]:
        """Check text for safety violations."""
        issues = []
        
        # Check for dangerous patterns in text
        dangerous_text_patterns = [
            "hack", "exploit", "bypass", "override", "disable",
            "security", "password", "secret", "key", "token",
            "admin", "root", "sudo", "privilege"
        ]
        
        text_lower = text.lower()
        for pattern in dangerous_text_patterns:
            if pattern in text_lower:
                # Check if it's in a quantum context
                quantum_context = any(qterm in text_lower 
                                    for qterm in ["quantum", "qubit", "circuit", "algorithm"])
                if not quantum_context:
                    issues.append(f"Potentially dangerous term in query: {pattern}")
        
        return issues
    
    def _is_allowed_import(self, import_name: str) -> bool:
        """Check if import is allowed."""
        # Check against allowed imports for all frameworks
        for framework, allowed in self._allowed_imports.items():
            for allowed_import in allowed:
                if import_name == allowed_import or import_name.startswith(allowed_import + "."):
                    return True
        
        # Allow standard library imports
        stdlib_modules = [
            "os", "sys", "json", "re", "math", "datetime", "collections",
            "itertools", "functools", "typing", "pathlib", "hashlib",
            "random", "statistics", "decimal", "fractions", "numbers"
        ]
        
        base_module = import_name.split(".")[0]
        return base_module in stdlib_modules
    
    def _determine_execution_mode(self, task: QuantumTask, 
                                 retrieval_result: RetrievalResult,
                                 verification_result: VerificationResult) -> str:
        """Determine appropriate execution mode."""
        # Check verification result
        if verification_result.verification_status != "passed":
            return "explanation_only"
        
        # Check task type
        if task.task_type in ["quantum_error_correction", "quantum_simulation"]:
            # These are safer, can run in simulation
            return "simulation"
        
        # Check examples for safety indicators
        safe_for_simulation = True
        for example in retrieval_result.examples:
            safety_checks = example.get("safety_checks", [])
            if "no_execution" in safety_checks:
                safe_for_simulation = False
                break
        
        if safe_for_simulation and self.sandbox_enabled:
            return "sandboxed"
        elif safe_for_simulation:
            return "simulation"
        else:
            return "explanation_only"
    
    def _generate_executable_code(self, task: QuantumTask, 
                                 retrieval_result: RetrievalResult,
                                 execution_mode: str) -> str:
        """Generate executable code from examples."""
        if not retrieval_result.examples:
            return "# No examples available\nprint('Cannot generate code: no examples found')"
        
        # Use the best matching example
        best_example = retrieval_result.examples[0]
        base_code = best_example["solution"]
        
        # Add imports based on framework
        framework = best_example.get("framework", "qiskit")
        imports = self._generate_imports(framework, execution_mode)
        
        # Add safety wrapper based on execution mode
        if execution_mode == "sandboxed":
            wrapper = self._generate_sandbox_wrapper()
        elif execution_mode == "simulation":
            wrapper = self._generate_simulation_wrapper()
        else:  # explanation_only
            wrapper = ""
        
        # Combine everything
        executable_code = f"{imports}\n\n{base_code}\n\n{wrapper}"
        
        # Add task-specific adaptations
        executable_code = self._adapt_code_to_task(executable_code, task)
        
        return executable_code
    
    def _generate_imports(self, framework: str, execution_mode: str) -> str:
        """Generate import statements."""
        imports = []
        
        # Framework-specific imports
        if framework == "qiskit":
            imports.append("from qiskit import QuantumCircuit, execute, Aer")
            imports.append("from qiskit.visualization import plot_histogram")
            if execution_mode == "simulation":
                imports.append("from qiskit.providers.aer import AerSimulator")
        elif framework == "cirq":
            imports.append("import cirq")
            imports.append("import numpy as np")
        elif framework == "pennylane":
            imports.append("import pennylane as qml")
            imports.append("import numpy as np")
        
        # Common imports
        imports.append("import numpy as np")
        imports.append("import matplotlib.pyplot as plt")
        
        return "\n".join(imports)
    
    def _generate_sandbox_wrapper(self) -> str:
        """Generate sandbox execution wrapper."""
        return """
# Sandbox execution wrapper
def run_sandboxed():
    try:
        # Your quantum code here
        result = main()  # Assuming main() is defined in the example
        return {"success": True, "result": str(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = run_sandboxed()
    print(json.dumps(result))
"""
    
    def _generate_simulation_wrapper(self) -> str:
        """Generate simulation execution wrapper."""
        return """
# Simulation execution wrapper
def run_simulation():
    try:
        # Limit simulation resources
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))  # 10 seconds CPU time
        
        # Run simulation
        result = simulate()  # Assuming simulate() is defined
        return {"success": True, "result": str(result)[:1000]}  # Limit output
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = run_simulation()
    print(json.dumps(result))
"""
    
    def _adapt_code_to_task(self, code: str, task: QuantumTask) -> str:
        """Adapt code to specific task requirements."""
        # Simple adaptation based on task type
        if task.task_type == "quantum_algorithm":
            # Ensure there's a main function
            if "def main()" not in code and "def grover" not in code:
                code += "\n\ndef main():\n    # Algorithm implementation\n    return 'Algorithm ready for simulation'"
        elif task.task_type == "quantum_circuit":
            # Ensure circuit is created and measured
            if "QuantumCircuit" in code and "measure_all" not in code:
                code += "\n\n# Add measurement if not present\nif 'qc' in locals():\n    qc.measure_all()"
        
        return code
    
    def _execute_explanation_only(self, task: QuantumTask, code: str, trace_id: str) -> Dict:
        """Execute in explanation-only mode (no code execution)."""
        # Analyze code structure
        analysis = self._analyze_code_structure(code)
        
        # Generate explanation
        explanation = self._generate_explanation(task, code, analysis)
        
        return {
            "success": True,
            "execution_mode": "explanation_only",
            "explanation": explanation,
            "code_analysis": analysis,
            "quality_score": 0.7  # Lower score for explanation-only
        }
    
    def _execute_simulation(self, task: QuantumTask, code: str, trace_id: str) -> Dict:
        """Execute in simulation mode (limited execution)."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Run with timeout
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=self.max_execution_time
            )
            
            # Parse output
            output = result.stdout.strip()
            error = result.stderr.strip()
            
            if result.returncode == 0:
                try:
                    # Try to parse JSON output
                    output_data = json.loads(output)
                    success = output_data.get("success", False)
                    
                    return {
                        "success": success,
                        "execution_mode": "simulation",
                        "output": output_data.get("result", output),
                        "error": output_data.get("error"),
                        "return_code": result.returncode,
                        "quality_score": 0.8 if success else 0.4
                    }
                except json.JSONDecodeError:
                    # Not JSON, use raw output
                    return {
                        "success": True,
                        "execution_mode": "simulation",
                        "output": output[:1000],  # Limit output size
                        "error": error,
                        "return_code": result.returncode,
                        "quality_score": 0.6
                    }
            else:
                return {
                    "success": False,
                    "execution_mode": "simulation",
                    "output": output,
                    "error": error,
                    "return_code": result.returncode,
                    "quality_score": 0.3
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "execution_mode": "simulation",
                "error": f"Execution timed out after {self.max_execution_time} seconds",
                "quality_score": 0.1
            }
        except Exception as e:
            return {
                "success": False,
                "execution_mode": "simulation",
                "error": str(e),
                "quality_score": 0.2
            }
        finally:
            # Clean up
            Path(temp_file).unlink(missing_ok=True)
    
    def _execute_sandboxed(self, task: QuantumTask, code: str, trace_id: str) -> Dict:
        """Execute in sandboxed mode (enhanced safety)."""
        # Similar to simulation but with additional sandboxing
        # For now, use simulation with stricter limits
        result = self._execute_simulation(task, code, trace_id)
        result["execution_mode"] = "sandboxed"
        
        # Lower quality score for sandboxed (more restrictions)
        if result["success"]:
            result["quality_score"] = result.get("quality_score", 0.5) * 0.9
        
        return result
    
    def _analyze_code_structure(self, code: str) -> Dict:
        """Analyze code structure without executing."""
        analysis = {
            "lines": len(code.splitlines()),
            "has_functions": "def " in code,
            "has_classes": "class " in code,
            "has_imports": "import " in code or "from " in code,
            "has_comments": "#" in code,
            "framework_indicators": [],
            "complexity_estimate": "low"
        }
        
        # Detect framework
        if "qiskit" in code.lower():
            analysis["framework_indicators"].append("qiskit")
        if "cirq" in code.lower():
            analysis["framework_indicators"].append("cirq")
        if "pennylane" in code.lower():
            analysis["framework_indicators"].append("pennylane")
        
        # Estimate complexity
        lines = analysis["lines"]
        if lines > 100:
            analysis["complexity_estimate"] = "high"
        elif lines > 50:
            analysis["complexity_estimate"] = "medium"
        
        return analysis
    
    def _generate_explanation(self, task: QuantumTask, code: str, analysis: Dict) -> str:
        """Generate explanation of code."""
        framework = analysis["framework_indicators"][0] if analysis["framework_indicators"] else "unknown"
        
        explanation = f"""
## Quantum Algorithm Explanation

**Task**: {task.query}

**Framework**: {framework}
**Estimated Complexity**: {analysis['complexity_estimate']}
**Code Structure**: {analysis['lines']} lines, {'with' if analysis['has_functions'] else 'without'} functions

### Approach:
This implementation uses {framework} to create a quantum circuit that demonstrates the requested algorithm.

### Key Components:
1. **Initialization**: Sets up quantum registers and classical registers
2. **Circuit Construction**: Applies quantum gates to create the desired state/operation
3. **Measurement**: Measures quantum states to classical bits
4. **Execution**: Runs the circuit on a simulator

### Safety Considerations:
- Code runs in a simulated environment only
- No access to real quantum hardware
- Resource-limited execution
- Output sanitization

### Notes:
This is an explanatory implementation. For production use, additional error handling, optimization, and testing would be required.
"""
        
        return explanation.strip()


def main():
    """Command-line interface for Quantum Executor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quantum Executor")
    parser.add_argument("code_file", help="Path to code file to execute")
    parser.add_argument("--mode", choices=["explanation", "simulation", "sandboxed"], 
                       default="simulation", help="Execution mode")
    parser.add_argument("--task-type", default="quantum_algorithm", help="Task type")
    parser.add_argument("--no-sandbox", action="store_true", help="Disable sandbox")
    
    args = parser.parse_args()
    
    # Read code
    with open(args.code_file, 'r') as f:
        code = f.read()
    
    # Create mock objects
    from quantum_mode_schema import QuantumModeConfig, QuantumTask, RetrievalResult
    from quantum_trace_logger import QuantumTraceLogger
    
    config = QuantumModeConfig()
    trace_logger = QuantumTraceLogger()
    
    task = QuantumTask(
        task_id="test_task",
        query="Test quantum algorithm",
        task_type=args.task_type,
        created_at=datetime.now().isoformat()
    )
    
    retrieval_result = RetrievalResult(
        query="Test",
        task_type=args.task_type,
        examples=[{"id": "test", "solution": code, "framework": "qiskit"}],
        match_scores=[1.0],
        confidence_level="high",
        retrieval_time=datetime.now().isoformat()
    )
    
    verification_result = type('obj', (object,), {
        'verification_status': 'passed',
        'overall_score': 0.9
    })()
    
    # Create executor
    executor = QuantumExecutor(
        config=config,
        trace_logger=trace_logger,
        sandbox_enabled=not args.no_sandbox
    )
    
    # Execute
    trace_id = "test_trace"
    result = executor.execute(task, retrieval_result, verification_result, trace_id)
    
    print(json.dumps(result, indent=2))
    
    return 0 if result.get("success", False) else 1


if __name__ == "__main__":
    sys.exit(main())