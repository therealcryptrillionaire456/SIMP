#!/usr/bin/env python3
"""
Executor for Sovereign Self Compiler v2.

Safely executes generated tasks in staged environment with resource limits,
timeout protection, and comprehensive output capture.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import psutil
import signal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes supported by the executor."""
    PYTHON = "python"
    BASH = "bash"
    DOCUMENT_TRANSFORM = "document_transform"
    ANALYSIS_ONLY = "analysis_only"


class ExecutionStatus(Enum):
    """Execution status codes."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RESOURCE_EXCEEDED = "resource_exceeded"


@dataclass
class ResourceUsage:
    """Resource consumption metrics."""
    cpu_time_seconds: float = 0.0
    memory_peak_mb: float = 0.0
    disk_usage_mb: float = 0.0
    network_usage_kb: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ExecutionError:
    """Error encountered during execution."""
    error_code: str
    error_message: str
    timestamp: str
    severity: str = "error"  # info, warning, error, critical
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ExecutionWarning:
    """Warning generated during execution."""
    warning_code: str
    warning_message: str
    timestamp: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ExecutionMetadata:
    """Execution metadata."""
    execution_mode: str
    sandbox_used: str = "local"
    timeout_enforced: bool = False
    resource_limits_exceeded: bool = False
    security_violations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ExecutionResult:
    """Result of executing a self-compilation task."""
    execution_id: str
    prompt_id: str
    status: str
    start_time: str
    end_time: str
    exit_code: int
    stdout_path: str
    stderr_path: str
    artifacts_created: List[str] = field(default_factory=list)
    tests_run: int = 0
    tests_passed: int = 0
    evaluation_status: str = "pending"
    resource_usage: Optional[ResourceUsage] = None
    errors: List[ExecutionError] = field(default_factory=list)
    warnings: List[ExecutionWarning] = field(default_factory=list)
    metadata: Optional[ExecutionMetadata] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        if self.resource_usage:
            result["resource_usage"] = self.resource_usage.to_dict()
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        result["errors"] = [e.to_dict() for e in self.errors]
        result["warnings"] = [w.to_dict() for w in self.warnings]
        return result
    
    def save(self, output_path: Path) -> None:
        """Save execution result to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class ResourceMonitor(threading.Thread):
    """Thread to monitor resource usage of a process."""
    
    def __init__(self, process: subprocess.Popen, interval: float = 0.1):
        super().__init__()
        self.process = process
        self.interval = interval
        self.cpu_times = []
        self.memory_usage = []
        self.running = True
        self.max_memory_mb = 0.0
        self.total_cpu_time = 0.0
        
    def run(self) -> None:
        """Monitor resource usage."""
        while self.running and self.process.poll() is None:
            try:
                # Get process info
                ps_process = psutil.Process(self.process.pid)
                cpu_times = ps_process.cpu_times()
                memory_info = ps_process.memory_info()
                
                # Track metrics
                self.cpu_times.append(cpu_times)
                memory_mb = memory_info.rss / 1024 / 1024
                self.memory_usage.append(memory_mb)
                self.max_memory_mb = max(self.max_memory_mb, memory_mb)
                
                # Calculate CPU time since last check
                if len(self.cpu_times) > 1:
                    last_cpu = self.cpu_times[-2]
                    current_cpu = self.cpu_times[-1]
                    cpu_delta = (current_cpu.user + current_cpu.system) - (last_cpu.user + last_cpu.system)
                    self.total_cpu_time += cpu_delta
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            
            time.sleep(self.interval)
    
    def stop(self) -> Tuple[float, float]:
        """Stop monitoring and return final metrics."""
        self.running = False
        return self.total_cpu_time, self.max_memory_mb


class Executor:
    """Executor for safe task execution."""
    
    def __init__(self, config: Dict[str, Any], staging_root: Path):
        """
        Initialize executor with configuration.
        
        Args:
            config: Executor configuration from self_compiler_config.json
            staging_root: Root directory for staging artifacts
        """
        self.config = config
        self.staging_root = staging_root
        self.resource_limits = config.get("resource_limits", {})
        self.execution_modes = config.get("execution_modes", {})
        
        # Ensure staging directory exists
        self.staging_root.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Executor initialized with staging root: {self.staging_root}")
    
    def execute_task(self, prompt: Dict[str, Any], execution_id: Optional[str] = None) -> ExecutionResult:
        """
        Execute a task based on prompt specification.
        
        Args:
            prompt: Prompt task specification
            execution_id: Optional execution ID (generated if not provided)
            
        Returns:
            ExecutionResult with execution details
        """
        execution_id = execution_id or str(uuid.uuid4())
        prompt_id = prompt.get("prompt_id", "unknown")
        execution_mode = prompt.get("execution_mode", "python")
        task_summary = prompt.get("task_summary", "Unknown task")
        
        logger.info(f"Starting execution {execution_id} for prompt {prompt_id}: {task_summary}")
        
        # Create execution directory
        exec_dir = self.staging_root / f"exec_{execution_id.replace('-', '_')}"
        exec_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare execution context
        start_time = datetime.utcnow().isoformat() + "Z"
        
        # Execute based on mode
        if execution_mode == ExecutionMode.PYTHON.value:
            result = self._execute_python(prompt, execution_id, exec_dir)
        elif execution_mode == ExecutionMode.BASH.value:
            result = self._execute_bash(prompt, execution_id, exec_dir)
        elif execution_mode == ExecutionMode.DOCUMENT_TRANSFORM.value:
            result = self._execute_document_transform(prompt, execution_id, exec_dir)
        elif execution_mode == ExecutionMode.ANALYSIS_ONLY.value:
            result = self._execute_analysis_only(prompt, execution_id, exec_dir)
        else:
            result = self._create_error_result(
                execution_id, prompt_id, start_time,
                f"Unsupported execution mode: {execution_mode}"
            )
        
        # Save result to file
        result_path = exec_dir / "execution_result.json"
        result.save(result_path)
        
        logger.info(f"Execution {execution_id} completed with status: {result.status}")
        return result
    
    def _execute_python(self, prompt: Dict[str, Any], execution_id: str, exec_dir: Path) -> ExecutionResult:
        """Execute Python code."""
        prompt_id = prompt.get("prompt_id", "unknown")
        prompt_text = prompt.get("prompt_text", "")
        start_time = datetime.utcnow().isoformat() + "Z"
        
        # Create Python script file
        script_path = exec_dir / "generated_script.py"
        stdout_path = exec_dir / "stdout.txt"
        stderr_path = exec_dir / "stderr.txt"
        
        try:
            # Write the prompt text as Python code
            with open(script_path, 'w') as f:
                f.write(prompt_text)
            
            # Prepare command
            python_cmd = ["python3", str(script_path)]
            
            # Execute with resource monitoring
            result = self._execute_command(
                python_cmd, execution_id, prompt_id, start_time,
                exec_dir, stdout_path, stderr_path,
                execution_mode=ExecutionMode.PYTHON.value
            )
            
            # Check for generated artifacts
            expected_artifacts = prompt.get("expected_artifacts", [])
            artifacts_created = self._find_artifacts(exec_dir, expected_artifacts)
            result.artifacts_created = [str(a) for a in artifacts_created]
            
            # Run tests if specified
            test_requirements = prompt.get("evaluation_requirements", {}).get("tests_run", [])
            if test_requirements:
                tests_run, tests_passed = self._run_python_tests(exec_dir, test_requirements)
                result.tests_run = tests_run
                result.tests_passed = tests_passed
            
            return result
            
        except Exception as e:
            logger.error(f"Python execution failed: {e}")
            return self._create_error_result(
                execution_id, prompt_id, start_time,
                f"Python execution failed: {str(e)}"
            )
    
    def _execute_bash(self, prompt: Dict[str, Any], execution_id: str, exec_dir: Path) -> ExecutionResult:
        """Execute bash script."""
        prompt_id = prompt.get("prompt_id", "unknown")
        prompt_text = prompt.get("prompt_text", "")
        start_time = datetime.utcnow().isoformat() + "Z"
        
        # Create bash script file
        script_path = exec_dir / "generated_script.sh"
        stdout_path = exec_dir / "stdout.txt"
        stderr_path = exec_dir / "stderr.txt"
        
        try:
            # Write the prompt text as bash script
            with open(script_path, 'w') as f:
                f.write("#!/bin/bash\n")
                f.write(prompt_text)
            
            # Make script executable
            script_path.chmod(0o755)
            
            # Check for blocked commands
            if self._contains_blocked_commands(prompt_text):
                return self._create_error_result(
                    execution_id, prompt_id, start_time,
                    "Script contains blocked commands"
                )
            
            # Execute command
            bash_cmd = ["bash", str(script_path)]
            
            result = self._execute_command(
                bash_cmd, execution_id, prompt_id, start_time,
                exec_dir, stdout_path, stderr_path,
                execution_mode=ExecutionMode.BASH.value
            )
            
            # Check for generated artifacts
            expected_artifacts = prompt.get("expected_artifacts", [])
            artifacts_created = self._find_artifacts(exec_dir, expected_artifacts)
            result.artifacts_created = [str(a) for a in artifacts_created]
            
            return result
            
        except Exception as e:
            logger.error(f"Bash execution failed: {e}")
            return self._create_error_result(
                execution_id, prompt_id, start_time,
                f"Bash execution failed: {str(e)}"
            )
    
    def _execute_document_transform(self, prompt: Dict[str, Any], execution_id: str, exec_dir: Path) -> ExecutionResult:
        """Execute document transformation."""
        prompt_id = prompt.get("prompt_id", "unknown")
        prompt_text = prompt.get("prompt_text", "")
        start_time = datetime.utcnow().isoformat() + "Z"
        
        stdout_path = exec_dir / "stdout.txt"
        stderr_path = exec_dir / "stderr.txt"
        
        try:
            # For document transform, we treat the prompt as instructions
            # and create the transformed document
            expected_artifacts = prompt.get("expected_artifacts", [])
            
            if not expected_artifacts:
                return self._create_error_result(
                    execution_id, prompt_id, start_time,
                    "Document transform requires expected_artifacts"
                )
            
            # Create the first expected artifact with the prompt text
            # In a real implementation, this would use an LLM or template engine
            first_artifact = exec_dir / expected_artifacts[0]
            first_artifact.parent.mkdir(parents=True, exist_ok=True)
            
            with open(first_artifact, 'w') as f:
                f.write(f"# Generated document\n\n")
                f.write(prompt_text)
            
            # Create success result
            end_time = datetime.utcnow().isoformat() + "Z"
            
            return ExecutionResult(
                execution_id=execution_id,
                prompt_id=prompt_id,
                status=ExecutionStatus.SUCCESS.value,
                start_time=start_time,
                end_time=end_time,
                exit_code=0,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                artifacts_created=[str(first_artifact)],
                metadata=ExecutionMetadata(
                    execution_mode=ExecutionMode.DOCUMENT_TRANSFORM.value
                )
            )
            
        except Exception as e:
            logger.error(f"Document transform failed: {e}")
            return self._create_error_result(
                execution_id, prompt_id, start_time,
                f"Document transform failed: {str(e)}"
            )
    
    def _execute_analysis_only(self, prompt: Dict[str, Any], execution_id: str, exec_dir: Path) -> ExecutionResult:
        """Execute analysis-only task (no code generation)."""
        prompt_id = prompt.get("prompt_id", "unknown")
        start_time = datetime.utcnow().isoformat() + "Z"
        
        stdout_path = exec_dir / "stdout.txt"
        stderr_path = exec_dir / "stderr.txt"
        
        try:
            # For analysis-only, we just create a report
            analysis_path = exec_dir / "analysis_report.json"
            
            with open(analysis_path, 'w') as f:
                analysis_result = {
                    "prompt_id": prompt_id,
                    "execution_id": execution_id,
                    "analysis_timestamp": start_time,
                    "summary": "Analysis completed successfully",
                    "findings": []
                }
                json.dump(analysis_result, f, indent=2)
            
            # Create success result
            end_time = datetime.utcnow().isoformat() + "Z"
            
            return ExecutionResult(
                execution_id=execution_id,
                prompt_id=prompt_id,
                status=ExecutionStatus.SUCCESS.value,
                start_time=start_time,
                end_time=end_time,
                exit_code=0,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                artifacts_created=[str(analysis_path)],
                metadata=ExecutionMetadata(
                    execution_mode=ExecutionMode.ANALYSIS_ONLY.value
                )
            )
            
        except Exception as e:
            logger.error(f"Analysis-only execution failed: {e}")
            return self._create_error_result(
                execution_id, prompt_id, start_time,
                f"Analysis-only execution failed: {str(e)}"
            )
    
    def _execute_command(
        self, cmd: List[str], execution_id: str, prompt_id: str,
        start_time: str, exec_dir: Path, stdout_path: Path,
        stderr_path: Path, execution_mode: str
    ) -> ExecutionResult:
        """Execute a command with resource monitoring and timeout."""
        timeout_seconds = self.resource_limits.get("timeout_seconds", 60)
        max_memory_mb = self.resource_limits.get("memory_mb", 1024)
        
        # Open output files
        stdout_file = open(stdout_path, 'w')
        stderr_file = open(stderr_path, 'w')
        
        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=exec_dir,
                text=True,
                start_new_session=True  # Create new process group for better signal handling
            )
            
            logger.info(f"Started process {process.pid} for execution {execution_id}")
            
            # Start resource monitor
            monitor = ResourceMonitor(process)
            monitor.start()
            
            # Wait for process with timeout
            try:
                exit_code = process.wait(timeout=timeout_seconds)
                status = ExecutionStatus.SUCCESS if exit_code == 0 else ExecutionStatus.FAILED
                
            except subprocess.TimeoutExpired:
                logger.warning(f"Process {process.pid} timed out after {timeout_seconds}s")
                
                # Kill process group
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                
                process.wait()  # Clean up
                exit_code = -1
                status = ExecutionStatus.TIMEOUT
            
            # Stop monitor and get metrics
            cpu_time, max_memory = monitor.stop()
            monitor.join()
            
            # Check resource limits
            resource_limits_exceeded = False
            if max_memory > max_memory_mb:
                logger.warning(f"Memory limit exceeded: {max_memory:.1f}MB > {max_memory_mb}MB")
                resource_limits_exceeded = True
                if status == ExecutionStatus.SUCCESS:
                    status = ExecutionStatus.RESOURCE_EXCEEDED
            
            # Close output files
            stdout_file.close()
            stderr_file.close()
            
            # Create result
            end_time = datetime.utcnow().isoformat() + "Z"
            
            result = ExecutionResult(
                execution_id=execution_id,
                prompt_id=prompt_id,
                status=status.value,
                start_time=start_time,
                end_time=end_time,
                exit_code=exit_code,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                resource_usage=ResourceUsage(
                    cpu_time_seconds=round(cpu_time, 2),
                    memory_peak_mb=round(max_memory, 2)
                ),
                metadata=ExecutionMetadata(
                    execution_mode=execution_mode,
                    timeout_enforced=(status == ExecutionStatus.TIMEOUT),
                    resource_limits_exceeded=resource_limits_exceeded
                )
            )
            
            # Add warnings if resources were high
            if max_memory > max_memory_mb * 0.8:  # 80% of limit
                result.warnings.append(ExecutionWarning(
                    warning_code="WARN_HIGH_MEMORY",
                    warning_message=f"High memory usage: {max_memory:.1f}MB",
                    timestamp=end_time
                ))
            
            if cpu_time > timeout_seconds * 0.8:  # 80% of timeout
                result.warnings.append(ExecutionWarning(
                    warning_code="WARN_SLOW_EXECUTION",
                    warning_message=f"Slow execution: {cpu_time:.1f}s",
                    timestamp=end_time
                ))
            
            return result
            
        except Exception as e:
            # Clean up on error
            stdout_file.close()
            stderr_file.close()
            
            logger.error(f"Command execution failed: {e}")
            
            end_time = datetime.utcnow().isoformat() + "Z"
            
            return ExecutionResult(
                execution_id=execution_id,
                prompt_id=prompt_id,
                status=ExecutionStatus.FAILED.value,
                start_time=start_time,
                end_time=end_time,
                exit_code=-1,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                errors=[ExecutionError(
                    error_code="ERR_EXECUTION_FAILED",
                    error_message=str(e),
                    timestamp=end_time,
                    severity="error"
                )],
                metadata=ExecutionMetadata(
                    execution_mode=execution_mode
                )
            )
    
    def _contains_blocked_commands(self, script_text: str) -> bool:
        """Check if script contains blocked commands."""
        blocked_commands = self.execution_modes.get("bash", {}).get("blocked_commands", [])
        
        for cmd in blocked_commands:
            # Simple check for command presence
            # In production, would use more sophisticated parsing
            if f" {cmd} " in f" {script_text} " or script_text.startswith(cmd):
                return True
        
        return False
    
    def _find_artifacts(self, exec_dir: Path, expected_artifacts: List[str]) -> List[Path]:
        """Find created artifacts in execution directory."""
        artifacts = []
        
        for artifact_pattern in expected_artifacts:
            # Handle relative paths
            artifact_path = exec_dir / artifact_pattern
            
            # Check if file exists
            if artifact_path.exists():
                artifacts.append(artifact_path)
            else:
                # Try glob pattern
                for found_path in exec_dir.glob(artifact_pattern):
                    if found_path.is_file():
                        artifacts.append(found_path)
        
        return artifacts
    
    def _run_python_tests(self, exec_dir: Path, test_requirements: List[str]) -> Tuple[int, int]:
        """Run Python tests in execution directory."""
        tests_run = 0
        tests_passed = 0
        
        # Look for test files
        test_files = list(exec_dir.glob("test_*.py")) + list(exec_dir.glob("*_test.py"))
        
        for test_file in test_files:
            try:
                # Run test with pytest
                test_cmd = ["python3", "-m", "pytest", str(test_file), "-v"]
                
                result = subprocess.run(
                    test_cmd,
                    capture_output=True,
                    text=True,
                    cwd=exec_dir,
                    timeout=30
                )
                
                # Parse pytest output (simplified)
                # In production, would parse XML output or use pytest API
                if result.returncode == 0:
                    tests_passed += 1
                tests_run += 1
                
            except Exception as e:
                logger.warning(f"Test execution failed for {test_file}: {e}")
        
        return tests_run, tests_passed
    
    def _create_error_result(
        self, execution_id: str, prompt_id: str, start_time: str, error_message: str
    ) -> ExecutionResult:
        """Create an error result for failed execution."""
        end_time = datetime.utcnow().isoformat() + "Z"
        
        # Create minimal execution directory for error
        exec_dir = self.staging_root / f"exec_{execution_id.replace('-', '_')}"
        exec_dir.mkdir(parents=True, exist_ok=True)
        
        stdout_path = exec_dir / "stdout.txt"
        stderr_path = exec_dir / "stderr.txt"
        
        # Write error to stderr
        with open(stderr_path, 'w') as f:
            f.write(f"Execution failed: {error_message}\n")
        
        return ExecutionResult(
            execution_id=execution_id,
            prompt_id=prompt_id,
            status=ExecutionStatus.FAILED.value,
            start_time=start_time,
            end_time=end_time,
            exit_code=1,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            errors=[ExecutionError(
                error_code="ERR_EXECUTION_FAILED",
                error_message=error_message,
                timestamp=end_time,
                severity="error"
            )],
            metadata=ExecutionMetadata(
                execution_mode="unknown"
            )
        )
    
    def cleanup_staging(self, older_than_hours: int = 24) -> int:
        """
        Clean up old staging directories.
        
        Args:
            older_than_hours: Remove directories older than this many hours
            
        Returns:
            Number of directories removed
        """
        removed_count = 0
        cutoff_time = time.time() - (older_than_hours * 3600)
        
        for item in self.staging_root.iterdir():
            if item.is_dir() and item.name.startswith("exec_"):
                # Check modification time
                stat = item.stat()
                if stat.st_mtime < cutoff_time:
                    try:
                        shutil.rmtree(item)
                        removed_count += 1
                        logger.info(f"Removed old staging directory: {item}")
                    except Exception as e:
                        logger.error(f"Failed to remove {item}: {e}")
        
        return removed_count


# Example usage
if __name__ == "__main__":
    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "self_compiler_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    # Create executor
    staging_root = Path(__file__).parent.parent / "staging"
    executor = Executor(config["execution"], staging_root)
    
    # Example prompt
    example_prompt = {
        "prompt_id": "550e8400-e29b-41d4-a716-446655440000",
        "execution_mode": "python",
        "prompt_text": "print('Hello from self-compiler!')\nprint('This is a test execution.')",
        "expected_artifacts": ["test_output.txt"],
        "task_summary": "Test execution"
    }
    
    # Execute
    result = executor.execute_task(example_prompt)
    print(f"Execution result: {result.status}")
    print(f"Exit code: {result.exit_code}")
    print(f"Artifacts created: {result.artifacts_created}")