#!/usr/bin/env python3
"""
Evaluator for Sovereign Self Compiler v2.

Scores and gates candidate outputs against evaluation criteria,
including syntax validation, policy compliance, and baseline comparison.
"""

import ast
import json
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import difflib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EvaluationStatus(Enum):
    """Evaluation status codes."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class GateStatus(Enum):
    """Gate evaluation status."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class GateResult:
    """Result of evaluating a single gate."""
    gate_name: str
    status: str  # pass, fail, warning, skipped
    score: float  # 0.0 to 1.0
    details: Dict[str, Any] = field(default_factory=dict)
    feedback: str = ""
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class EvaluationResult:
    """Complete evaluation result."""
    evaluation_id: str
    execution_id: str
    prompt_id: str
    status: str  # pending, in_progress, completed, failed
    overall_score: float  # 0.0 to 1.0
    gate_results: List[GateResult] = field(default_factory=list)
    passed_gates: List[str] = field(default_factory=list)
    failed_gates: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    feedback_summary: str = ""
    promotion_recommendation: str = ""  # PROMOTE, REJECT, REVISE, ESCALATE
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["gate_results"] = [g.to_dict() for g in self.gate_results]
        return result
    
    def save(self, output_path: Path) -> None:
        """Save evaluation result to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class Evaluator:
    """Evaluator for scoring and gating candidate outputs."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize evaluator with configuration.
        
        Args:
            config: Evaluator configuration from self_compiler_config.json
        """
        self.config = config
        self.score_weights = config.get("score_weights", {})
        self.required_gates = config.get("required_gates", [])
        self.optional_gates = config.get("optional_gates", [])
        self.sensitive_paths = config.get("sensitive_paths", [])
        self.policy_rules = config.get("policy_rules", {})
        
        # Minimum score for promotion
        self.minimum_score = config.get("minimum_score", 0.8)
        
        logger.info(f"Evaluator initialized with {len(self.required_gates)} required gates")
    
    def evaluate(
        self,
        execution_result: Dict[str, Any],
        prompt: Dict[str, Any],
        baseline_artifact: Optional[Path] = None
    ) -> EvaluationResult:
        """
        Evaluate execution results against criteria.
        
        Args:
            execution_result: Execution result from executor
            prompt: Original prompt specification
            baseline_artifact: Optional baseline artifact for comparison
            
        Returns:
            EvaluationResult with scores and recommendations
        """
        evaluation_id = str(hashlib.md5(
            f"{execution_result['execution_id']}_{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16])
        
        execution_id = execution_result.get("execution_id", "unknown")
        prompt_id = prompt.get("prompt_id", "unknown")
        
        logger.info(f"Starting evaluation {evaluation_id} for execution {execution_id}")
        
        # Create evaluation result
        result = EvaluationResult(
            evaluation_id=evaluation_id,
            execution_id=execution_id,
            prompt_id=prompt_id,
            status=EvaluationStatus.IN_PROGRESS.value,
            overall_score=0.0,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        
        try:
            # Get evaluation requirements from prompt
            eval_requirements = prompt.get("evaluation_requirements", {})
            
            # Run all gates
            gate_results = []
            
            # 1. Schema validation gate
            if self._should_run_gate("schema_validation", eval_requirements):
                schema_result = self._run_schema_validation_gate(execution_result, prompt)
                gate_results.append(schema_result)
            
            # 2. Syntax check gate
            if self._should_run_gate("syntax_check", eval_requirements):
                syntax_result = self._run_syntax_check_gate(execution_result, prompt)
                gate_results.append(syntax_result)
            
            # 3. Tests passed gate
            if self._should_run_gate("tests_passed", eval_requirements):
                tests_result = self._run_tests_passed_gate(execution_result, prompt)
                gate_results.append(tests_result)
            
            # 4. Policy compliance gate
            if self._should_run_gate("policy_compliance", eval_requirements):
                policy_result = self._run_policy_compliance_gate(execution_result, prompt)
                gate_results.append(policy_result)
            
            # 5. Baseline comparison gate
            if self._should_run_gate("baseline_comparison", eval_requirements) and baseline_artifact:
                baseline_result = self._run_baseline_comparison_gate(
                    execution_result, prompt, baseline_artifact
                )
                gate_results.append(baseline_result)
            
            # 6. Performance check gate (optional)
            if "performance_check" in self.optional_gates:
                perf_result = self._run_performance_check_gate(execution_result, prompt)
                gate_results.append(perf_result)
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(gate_results)
            
            # Determine which gates passed/failed
            passed_gates = [g.gate_name for g in gate_results if g.status == GateStatus.PASS.value]
            failed_gates = [g.gate_name for g in gate_results if g.status == GateStatus.FAIL.value]
            
            # Check required gates
            required_passed = all(
                gate_name in passed_gates 
                for gate_name in self.required_gates 
                if self._should_run_gate(gate_name, eval_requirements)
            )
            
            # Generate feedback summary
            feedback_summary = self._generate_feedback_summary(gate_results, overall_score)
            
            # Determine promotion recommendation
            promotion_recommendation = self._determine_promotion_recommendation(
                overall_score, required_passed, gate_results, prompt
            )
            
            # Update result
            result.status = EvaluationStatus.COMPLETED.value
            result.overall_score = overall_score
            result.gate_results = gate_results
            result.passed_gates = passed_gates
            result.failed_gates = failed_gates
            result.feedback_summary = feedback_summary
            result.promotion_recommendation = promotion_recommendation
            
            logger.info(f"Evaluation {evaluation_id} completed. Score: {overall_score:.2f}, "
                       f"Recommendation: {promotion_recommendation}")
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            result.status = EvaluationStatus.FAILED.value
            result.feedback_summary = f"Evaluation failed: {str(e)}"
            result.promotion_recommendation = "REJECT"
        
        return result
    
    def _should_run_gate(self, gate_name: str, eval_requirements: Dict[str, Any]) -> bool:
        """Determine if a gate should be run based on requirements."""
        # Check if gate is explicitly disabled
        if gate_name in eval_requirements and eval_requirements[gate_name] is False:
            return False
        
        # Check if gate is required
        if gate_name in self.required_gates:
            return True
        
        # Check if gate is optional but requested
        if gate_name in eval_requirements and eval_requirements[gate_name] is True:
            return True
        
        # Default for optional gates
        return False
    
    def _run_schema_validation_gate(
        self, execution_result: Dict[str, Any], prompt: Dict[str, Any]
    ) -> GateResult:
        """Validate artifacts against expected schemas."""
        gate_name = "schema_validation"
        artifacts_created = execution_result.get("artifacts_created", [])
        expected_artifacts = prompt.get("expected_artifacts", [])
        
        details = {
            "artifacts_checked": len(artifacts_created),
            "expected_artifacts": expected_artifacts,
            "validation_results": []
        }
        
        # Check if expected artifacts were created
        missing_artifacts = []
        for expected in expected_artifacts:
            # Simple check for now - in production would use schema validation
            found = any(expected in artifact for artifact in artifacts_created)
            if not found:
                missing_artifacts.append(expected)
            
            details["validation_results"].append({
                "expected": expected,
                "found": found,
                "artifact_path": next((a for a in artifacts_created if expected in a), None)
            })
        
        # Calculate score
        if not expected_artifacts:
            score = 1.0  # No expectations means automatic pass
            status = GateStatus.PASS.value
            feedback = "No schema validation required"
        elif not missing_artifacts:
            score = 1.0
            status = GateStatus.PASS.value
            feedback = f"All {len(expected_artifacts)} expected artifacts created"
        else:
            score = (len(expected_artifacts) - len(missing_artifacts)) / len(expected_artifacts)
            status = GateStatus.FAIL.value if score < 0.8 else GateStatus.WARNING.value
            feedback = f"Missing {len(missing_artifacts)} of {len(expected_artifacts)} artifacts: {missing_artifacts}"
        
        return GateResult(
            gate_name=gate_name,
            status=status,
            score=score,
            details=details,
            feedback=feedback,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    def _run_syntax_check_gate(
        self, execution_result: Dict[str, Any], prompt: Dict[str, Any]
    ) -> GateResult:
        """Check syntax of generated code artifacts."""
        gate_name = "syntax_check"
        artifacts_created = execution_result.get("artifacts_created", [])
        execution_mode = prompt.get("execution_mode", "python")
        
        details = {
            "artifacts_checked": 0,
            "syntax_errors": [],
            "valid_files": []
        }
        
        syntax_errors = []
        valid_files = []
        
        for artifact_path in artifacts_created:
            artifact = Path(artifact_path)
            if not artifact.exists():
                continue
            
            # Check based on file extension
            if artifact.suffix == '.py':
                try:
                    with open(artifact, 'r') as f:
                        content = f.read()
                    
                    # Parse Python syntax
                    ast.parse(content)
                    valid_files.append(str(artifact))
                    details["valid_files"].append(str(artifact))
                    
                except SyntaxError as e:
                    error_info = {
                        "file": str(artifact),
                        "line": e.lineno,
                        "column": e.offset,
                        "message": str(e)
                    }
                    syntax_errors.append(error_info)
                    details["syntax_errors"].append(error_info)
            
            elif artifact.suffix == '.json':
                try:
                    with open(artifact, 'r') as f:
                        json.load(f)
                    valid_files.append(str(artifact))
                    details["valid_files"].append(str(artifact))
                    
                except json.JSONDecodeError as e:
                    error_info = {
                        "file": str(artifact),
                        "line": e.lineno,
                        "column": e.colno,
                        "message": str(e)
                    }
                    syntax_errors.append(error_info)
                    details["syntax_errors"].append(error_info)
        
        details["artifacts_checked"] = len(valid_files) + len(syntax_errors)
        
        # Calculate score
        total_checked = details["artifacts_checked"]
        if total_checked == 0:
            score = 1.0  # Nothing to check
            status = GateStatus.PASS.value
            feedback = "No code artifacts to check"
        elif not syntax_errors:
            score = 1.0
            status = GateStatus.PASS.value
            feedback = f"All {total_checked} artifacts have valid syntax"
        else:
            score = len(valid_files) / total_checked
            status = GateStatus.FAIL.value
            feedback = f"{len(syntax_errors)} syntax errors in {total_checked} artifacts"
        
        return GateResult(
            gate_name=gate_name,
            status=status,
            score=score,
            details=details,
            feedback=feedback,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    def _run_tests_passed_gate(
        self, execution_result: Dict[str, Any], prompt: Dict[str, Any]
    ) -> GateResult:
        """Check test results from execution."""
        gate_name = "tests_passed"
        
        tests_run = execution_result.get("tests_run", 0)
        tests_passed = execution_result.get("tests_passed", 0)
        
        details = {
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "test_coverage": 0.0
        }
        
        # Calculate test coverage if we have expected tests
        eval_requirements = prompt.get("evaluation_requirements", {})
        expected_tests = eval_requirements.get("tests_run", [])
        
        if expected_tests:
            details["expected_tests"] = expected_tests
            details["test_coverage"] = min(tests_run / len(expected_tests), 1.0) if expected_tests else 0.0
        
        # Calculate score
        if tests_run == 0:
            score = 0.5  # Neutral score for no tests
            status = GateStatus.WARNING.value
            feedback = "No tests were run"
        elif tests_passed == tests_run:
            score = 1.0
            status = GateStatus.PASS.value
            feedback = f"All {tests_passed}/{tests_run} tests passed"
        else:
            score = tests_passed / tests_run
            status = GateStatus.FAIL.value if score < 0.8 else GateStatus.WARNING.value
            feedback = f"{tests_passed}/{tests_run} tests passed ({score:.1%})"
        
        return GateResult(
            gate_name=gate_name,
            status=status,
            score=score,
            details=details,
            feedback=feedback,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    def _run_policy_compliance_gate(
        self, execution_result: Dict[str, Any], prompt: Dict[str, Any]
    ) -> GateResult:
        """Check compliance with security and policy rules."""
        gate_name = "policy_compliance"
        artifacts_created = execution_result.get("artifacts_created", [])
        policy_level = prompt.get("evaluation_requirements", {}).get("policy_check", "basic")
        
        details = {
            "policy_level": policy_level,
            "violations": [],
            "warnings": [],
            "checks_performed": []
        }
        
        violations = []
        warnings = []
        
        for artifact_path in artifacts_created:
            artifact = Path(artifact_path)
            if not artifact.exists():
                continue
            
            # Check file size
            max_file_size_kb = self.policy_rules.get("max_file_size_kb", 100)
            file_size_kb = artifact.stat().st_size / 1024
            
            if file_size_kb > max_file_size_kb:
                violation = {
                    "file": str(artifact),
                    "rule": "max_file_size_kb",
                    "value": file_size_kb,
                    "limit": max_file_size_kb,
                    "severity": "warning" if policy_level == "basic" else "error"
                }
                if violation["severity"] == "error":
                    violations.append(violation)
                else:
                    warnings.append(violation)
                details["checks_performed"].append({
                    "file": str(artifact),
                    "check": "file_size",
                    "result": f"exceeds limit ({file_size_kb:.1f}KB > {max_file_size_kb}KB)"
                })
            
            # Check for sensitive paths in code (basic check)
            if artifact.suffix == '.py':
                with open(artifact, 'r') as f:
                    content = f.read()
                
                # Check for direct production writes
                if self.policy_rules.get("no_direct_production_writes", True):
                    prod_write_patterns = [
                        r'open\(["\'][^"\']*production[^"\']*["\']',
                        r'write\(["\'][^"\']*production[^"\']*["\']',
                        r'shutil\.(copy|move)\([^)]*production[^)]*\)'
                    ]
                    
                    for pattern in prod_write_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            violation = {
                                "file": str(artifact),
                                "rule": "no_direct_production_writes",
                                "pattern": pattern,
                                "severity": "error"
                            }
                            violations.append(violation)
                            details["checks_performed"].append({
                                "file": str(artifact),
                                "check": "production_writes",
                                "result": "found potential production write"
                            })
                            break
                
                # Check for dangerous imports
                if self.policy_rules.get("require_explicit_imports", True):
                    dangerous_imports = ["os", "sys", "subprocess", "shutil"]
                    for imp in dangerous_imports:
                        if f"import {imp}" in content or f"from {imp} import" in content:
                            warning = {
                                "file": str(artifact),
                                "rule": "dangerous_import",
                                "import": imp,
                                "severity": "warning"
                            }
                            warnings.append(warning)
                            details["checks_performed"].append({
                                "file": str(artifact),
                                "check": "dangerous_imports",
                                "result": f"found import of {imp}"
                            })
        
        details["violations"] = violations
        details["warnings"] = warnings
        
        # Calculate score based on policy level
        if policy_level == "none":
            score = 1.0
            status = GateStatus.PASS.value
            feedback = "Policy checking disabled"
        elif not violations:
            if not warnings:
                score = 1.0
                status = GateStatus.PASS.value
                feedback = "No policy violations or warnings"
            else:
                score = 0.9
                status = GateStatus.WARNING.value
                feedback = f"{len(warnings)} policy warnings, no violations"
        else:
            # Penalize based on number of violations
            severity_weights = {"error": 0.7, "warning": 0.3}
            total_severity = sum(severity_weights.get(v.get("severity", "error"), 0.5) 
                               for v in violations)
            score = max(0.0, 1.0 - (total_severity / max(len(violations), 1)))
            status = GateStatus.FAIL.value
            feedback = f"{len(violations)} policy violations, {len(warnings)} warnings"
        
        return GateResult(
            gate_name=gate_name,
            status=status,
            score=score,
            details=details,
            feedback=feedback,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    def _run_baseline_comparison_gate(
        self, execution_result: Dict[str, Any], prompt: Dict[str, Any],
        baseline_artifact: Path
    ) -> GateResult:
        """Compare generated artifact against baseline."""
        gate_name = "baseline_comparison"
        artifacts_created = execution_result.get("artifacts_created", [])
        
        details = {
            "baseline_path": str(baseline_artifact),
            "comparisons": [],
            "similarity_scores": []
        }
        
        if not baseline_artifact.exists():
            score = 0.5
            status = GateStatus.WARNING.value
            feedback = "Baseline artifact not found"
            
            return GateResult(
                gate_name=gate_name,
                status=status,
                score=score,
                details=details,
                feedback=feedback,
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
        
        # Read baseline
        with open(baseline_artifact, 'r') as f:
            baseline_content = f.read()
        
        similarity_scores = []
        
        for artifact_path in artifacts_created:
            artifact = Path(artifact_path)
            if not artifact.exists() or artifact.suffix != baseline_artifact.suffix:
                continue
            
            with open(artifact, 'r') as f:
                artifact_content = f.read()
            
            # Calculate similarity
            similarity = self._calculate_similarity(baseline_content, artifact_content)
            similarity_scores.append(similarity)
            
            # Generate diff
            diff = list(difflib.unified_diff(
                baseline_content.splitlines(keepends=True),
                artifact_content.splitlines(keepends=True),
                fromfile=str(baseline_artifact),
                tofile=str(artifact),
                lineterm='\n'
            ))
            
            details["comparisons"].append({
                "artifact": str(artifact),
                "similarity": similarity,
                "diff_lines": len(diff),
                "is_improvement": similarity > 0.7  # Simple heuristic
            })
        
        details["similarity_scores"] = similarity_scores
        
        # Calculate overall score
        if not similarity_scores:
            score = 0.5
            status = GateStatus.WARNING.value
            feedback = "No comparable artifacts found for baseline comparison"
        else:
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            score = avg_similarity
            
            if avg_similarity >= 0.9:
                status = GateStatus.PASS.value
                feedback = f"High similarity to baseline ({avg_similarity:.1%})"
            elif avg_similarity >= 0.7:
                status = GateStatus.WARNING.value
                feedback = f"Moderate similarity to baseline ({avg_similarity:.1%})"
            else:
                status = GateStatus.FAIL.value
                feedback = f"Low similarity to baseline ({avg_similarity:.1%})"
        
        return GateResult(
            gate_name=gate_name,
            status=status,
            score=score,
            details=details,
            feedback=feedback,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    def _run_performance_check_gate(
        self, execution_result: Dict[str, Any], prompt: Dict[str, Any]
    ) -> GateResult:
        """Check performance metrics from execution."""
        gate_name = "performance_check"
        
        resource_usage = execution_result.get("resource_usage", {})
        eval_requirements = prompt.get("evaluation_requirements", {})
        perf_reqs = eval_requirements.get("performance_requirements", {})
        
        details = {
            "resource_usage": resource_usage,
            "requirements": perf_reqs,
            "violations": []
        }
        
        violations = []
        
        # Check execution time
        max_time = perf_reqs.get("max_execution_time_seconds", 60)
        cpu_time = resource_usage.get("cpu_time_seconds", 0)
        
        if cpu_time > max_time:
            violations.append({
                "metric": "execution_time",
                "value": cpu_time,
                "limit": max_time,
                "exceeded_by": cpu_time - max_time
            })
        
        # Check memory usage
        max_memory = perf_reqs.get("max_memory_mb", 256)
        memory_used = resource_usage.get("memory_peak_mb", 0)
        
        if memory_used > max_memory:
            violations.append({
                "metric": "memory_usage",
                "value": memory_used,
                "limit": max_memory,
                "exceeded_by": memory_used - max_memory
            })
        
        details["violations"] = violations
        
        # Calculate score
        if not violations:
            score = 1.0
            status = GateStatus.PASS.value
            feedback = "All performance requirements met"
        else:
            # Penalize based on severity of violations
            time_violation = any(v["metric"] == "execution_time" for v in violations)
            memory_violation = any(v["metric"] == "memory_usage" for v in violations)
            
            if time_violation and memory_violation:
                score = 0.3
            elif time_violation:
                score = 0.6
            elif memory_violation:
                score = 0.7
            else:
                score = 0.8
            
            status = GateStatus.FAIL.value
            feedback = f"{len(violations)} performance requirement violations"
        
        return GateResult(
            gate_name=gate_name,
            status=status,
            score=score,
            details=details,
            feedback=feedback,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0.0 to 1.0)."""
        if not text1 or not text2:
            return 0.0
        
        # Use SequenceMatcher for simple similarity
        matcher = difflib.SequenceMatcher(None, text1, text2)
        return matcher.ratio()
    
    def _calculate_overall_score(self, gate_results: List[GateResult]) -> float:
        """Calculate weighted overall score from gate results."""
        if not gate_results:
            return 0.0
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for gate_result in gate_results:
            gate_name = gate_result.gate_name
            weight = self.score_weights.get(gate_name, 0.1)  # Default weight
            
            # Skip gates that were skipped
            if gate_result.status == GateStatus.SKIPPED.value:
                continue
            
            weighted_score += gate_result.score * weight
            total_weight += weight
        
        # Normalize by total weight
        if total_weight > 0:
            return weighted_score / total_weight
        else:
            return 0.0
    
    def _generate_feedback_summary(
        self, gate_results: List[GateResult], overall_score: float
    ) -> str:
        """Generate human-readable feedback summary."""
        if not gate_results:
            return "No gates were evaluated."
        
        passed_gates = [g for g in gate_results if g.status == GateStatus.PASS.value]
        failed_gates = [g for g in gate_results if g.status == GateStatus.FAIL.value]
        warning_gates = [g for g in gate_results if g.status == GateStatus.WARNING.value]
        
        summary_parts = []
        
        summary_parts.append(f"Overall score: {overall_score:.1%}")
        
        if passed_gates:
            summary_parts.append(f"Passed gates: {len(passed_gates)}/{len(gate_results)}")
        
        if failed_gates:
            failed_names = [g.gate_name for g in failed_gates]
            summary_parts.append(f"Failed gates: {', '.join(failed_names)}")
        
        if warning_gates:
            warning_names = [g.gate_name for g in warning_gates]
            summary_parts.append(f"Warnings: {', '.join(warning_names)}")
        
        # Add specific feedback for low scores
        if overall_score < self.minimum_score:
            low_scoring = [g for g in gate_results if g.score < 0.7]
            if low_scoring:
                low_names = [g.gate_name for g in low_scoring]
                summary_parts.append(f"Low scores in: {', '.join(low_names)}")
        
        return ". ".join(summary_parts)
    
    def _determine_promotion_recommendation(
        self, overall_score: float, required_passed: bool,
        gate_results: List[GateResult], prompt: Dict[str, Any]
    ) -> str:
        """Determine promotion recommendation based on evaluation."""
        # Check if any gate failed
        has_failed_gates = any(g.status == GateStatus.FAIL.value for g in gate_results)
        
        # Check for sensitive paths
        policy_level = prompt.get("evaluation_requirements", {}).get("policy_check", "basic")
        artifacts_created = []
        for result in gate_results:
            if result.gate_name == "schema_validation":
                artifacts = result.details.get("validation_results", [])
                artifacts_created = [a.get("artifact_path") for a in artifacts if a.get("artifact_path")]
                break
        
        has_sensitive_path = False
        for artifact in artifacts_created:
            if artifact:
                for sensitive_path in self.sensitive_paths:
                    if sensitive_path in artifact:
                        has_sensitive_path = True
                        break
        
        # Decision logic
        if not required_passed:
            return "REJECT"
        
        if has_failed_gates:
            return "REJECT"
        
        if overall_score < self.minimum_score:
            return "REVISE"
        
        if has_sensitive_path and policy_level in ["sensitive", "strict"]:
            return "ESCALATE"  # Needs ProjectX review
        
        # Check for warnings that might need review
        has_warnings = any(g.status == GateStatus.WARNING.value for g in gate_results)
        if has_warnings and overall_score < 0.9:
            return "REVISE"
        
        return "PROMOTE"


# Example usage
if __name__ == "__main__":
    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "self_compiler_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    # Create evaluator
    evaluator = Evaluator(config["evaluation"])
    
    # Example execution result
    example_execution = {
        "execution_id": "660e8400-e29b-41d4-a716-446655440001",
        "prompt_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "success",
        "artifacts_created": ["/tmp/test_artifact.py"],
        "tests_run": 5,
        "tests_passed": 5,
        "resource_usage": {
            "cpu_time_seconds": 2.5,
            "memory_peak_mb": 45.2
        }
    }
    
    # Example prompt
    example_prompt = {
        "prompt_id": "550e8400-e29b-41d4-a716-446655440000",
        "evaluation_requirements": {
            "schema_validation": True,
            "syntax_check": True,
            "tests_run": ["test_basic"],
            "policy_check": "basic",
            "performance_requirements": {
                "max_execution_time_seconds": 30,
                "max_memory_mb": 256
            }
        },
        "expected_artifacts": ["test_artifact.py"]
    }
    
    # Create a test artifact
    test_artifact = Path("/tmp/test_artifact.py")
    test_artifact.write_text("print('Hello, world!')\n")
    
    # Evaluate
    result = evaluator.evaluate(example_execution, example_prompt)
    
    print(f"Evaluation result: {result.status}")
    print(f"Overall score: {result.overall_score:.2f}")
    print(f"Promotion recommendation: {result.promotion_recommendation}")
    print(f"Feedback: {result.feedback_summary}")
    
    # Clean up
    test_artifact.unlink(missing_ok=True)