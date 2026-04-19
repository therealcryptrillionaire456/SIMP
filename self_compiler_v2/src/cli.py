#!/usr/bin/env python3
"""
CLI for Sovereign Self Compiler v2.

Command-line interface for running the recursive self-compilation system.
"""

import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import psutil for resource monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - resource monitoring features will be limited")

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.inventory import InventoryScanner
from src.planner import Planner
from src.prompt_compiler import PromptCompiler
from src.executor import Executor
from src.evaluator import Evaluator
from src.promoter import Promoter
from src.trace_logger import TraceLogger

# Try to import resource monitor
try:
    from src.resource_monitor import ResourceMonitor, MonitoringThread
    RESOURCE_MONITOR_AVAILABLE = True
except ImportError:
    RESOURCE_MONITOR_AVAILABLE = False
    logger.warning("Resource monitor not available - resource monitoring feature disabled")

# Try to import watchtower stress test
try:
    from watchtower_stress_test import WatchtowerStressTester
    WATCHTOWER_AVAILABLE = True
except ImportError:
    WATCHTOWER_AVAILABLE = False
    logger.warning("Watchtower stress test not available - stress test feature disabled")


class SelfCompilerCLI:
    """Command-line interface for the self-compiler."""
    
    def __init__(self, config_path: Path):
        """
        Initialize CLI with configuration.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        
        # Load configuration
        with open(config_path) as f:
            self.config = json.load(f)
        
        # Base directories
        self.base_dir = config_path.parent.parent
        self.staging_dir = self.base_dir / "staging"
        self.promotion_dir = self.base_dir / "promoted"
        self.trace_dir = self.base_dir / "traces"
        
        # Create directories
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.promotion_dir.mkdir(parents=True, exist_ok=True)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir = self.base_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.trace_logger = TraceLogger(self.config["observability"])
        self.inventory_scanner = InventoryScanner(self.config.get("inventory", {}))
        self.planner = Planner(self.config.get("planning", {}))
        self.prompt_compiler = PromptCompiler(self.config.get("prompting", {}))
        self.executor = Executor(self.config["execution"], self.staging_dir)
        self.evaluator = Evaluator(self.config["evaluation"])
        self.promoter = Promoter(
            self.config["promotion"],
            self.staging_dir,
            self.promotion_dir
        )
        
        # Initialize resource monitor if available
        if RESOURCE_MONITOR_AVAILABLE:
            self.resource_monitor = ResourceMonitor(
                config=self.config.get("resource_monitoring", {})
            )
            self.monitoring_thread = None
        else:
            self.resource_monitor = None
            self.monitoring_thread = None
        
        logger.info(f"Self Compiler CLI initialized with config: {config_path}")
    
    def run_session(
        self,
        goal: str,
        max_cycles: int = 25,  # Default to 25 cycles for bounded autonomy
        target_directories: Optional[List[str]] = None,
        operator_approval: bool = False,
        continuous: bool = False,
        pause_between_cycles: int = 60,
        max_consecutive_failures: int = 3,
        max_total_time_seconds: int = 3600
    ) -> Dict[str, Any]:
        """
        Run a complete self-compilation session with hardened continuous mode.
        
        Args:
            goal: Goal description for the session
            max_cycles: Maximum recursion cycles (default: 25, scalable to 100)
            target_directories: Directories to inventory (default: current directory)
            operator_approval: Whether operator approval is granted in advance
            continuous: Run in continuous mode (indefinite until stop conditions)
            pause_between_cycles: Pause between cycles in seconds (continuous mode only)
            max_consecutive_failures: Stop after N consecutive failed cycles
            max_total_time_seconds: Maximum total session time in seconds
            
        Returns:
            Session results
        """
        session_id = str(uuid.uuid4())[:8]
        goal_id = str(uuid.uuid4())[:8]
        
        logger.info(f"Starting session {session_id} with goal: {goal}")
        
        # Start tracing
        trace_id = self.trace_logger.start_session(
            session_id,
            goal_id,
            {
                "goal": goal,
                "max_cycles": max_cycles,
                "operator_approval": operator_approval
            }
        )
        
        session_results = {
            "session_id": session_id,
            "goal_id": goal_id,
            "trace_id": trace_id,
            "goal": goal,
            "max_cycles": max_cycles,
            "target_directories": target_directories,
            "operator_approval": operator_approval,
            "start_time": datetime.utcnow().isoformat() + "Z",
            "cycles": [],
            "final_status": "unknown",
            "summary": {},
            "continuous_mode": continuous,
            "pause_between_cycles": pause_between_cycles,
            "max_consecutive_failures": max_consecutive_failures,
            "max_total_time_seconds": max_total_time_seconds,
            "consecutive_failures": 0,
            "stop_reason": None
        }
        
        try:
            cycle_num = 1
            session_start_time = time.time()
            
            while True:  # Loop for continuous mode
                # Check stop conditions
                stop_reason = self._check_stop_conditions(
                    session_results, cycle_num, session_start_time
                )
                if stop_reason:
                    logger.info(f"Stop condition triggered: {stop_reason}")
                    session_results["stop_reason"] = stop_reason
                    break
                    
                logger.info(f"Starting cycle {cycle_num}" + 
                          (f"/{max_cycles}" if not continuous else " (continuous mode)"))
                self.trace_logger.start_cycle(session_id, cycle_num, goal_id)
                
                cycle_result = self._run_cycle(
                    session_id, trace_id, goal_id, goal, cycle_num,
                    target_directories, operator_approval
                )
                
                session_results["cycles"].append(cycle_result)
                
                # Update failure tracking
                if cycle_result.get("status") == "failed":
                    session_results["consecutive_failures"] += 1
                else:
                    session_results["consecutive_failures"] = 0
                
                # Save session state after each cycle
                self.save_session_state(session_id, session_results)
                
                # Check if we should continue based on cycle result
                if cycle_result.get("should_continue", False) is False:
                    logger.info(f"Cycle {cycle_num} indicates no further cycles needed")
                    session_results["stop_reason"] = "cycle_completion"
                    break
                
                # Increment cycle number
                cycle_num += 1
                
                # If not in continuous mode and reached max cycles, break
                if not continuous and cycle_num > max_cycles:
                    session_results["stop_reason"] = "max_cycles_reached"
                    break
                
                # If in continuous mode, pause between cycles
                if continuous:
                    logger.info(f"Continuous mode: pausing for {pause_between_cycles} seconds before next cycle")
                    try:
                        time.sleep(pause_between_cycles)
                    except KeyboardInterrupt:
                        logger.info("Continuous mode interrupted by user")
                        session_results["final_status"] = "interrupted"
                        session_results["stop_reason"] = "user_interrupt"
                        break
            
            # Generate session summary
            session_results["final_status"] = self._generate_session_summary(session_results)
            session_results["end_time"] = datetime.utcnow().isoformat() + "Z"
            
            # End tracing
            self.trace_logger.end_session(
                session_id,
                session_results["final_status"],
                session_results["summary"]
            )
            
            # Save final session state
            self.save_session_state(session_id, session_results)
            
            logger.info(f"Session {session_id} completed with status: {session_results['final_status']}")
            
        except Exception as e:
            logger.error(f"Session {session_id} failed: {e}")
            session_results["final_status"] = "failed"
            session_results["error"] = str(e)
            
            # End tracing with error
            self.trace_logger.end_session(
                session_id,
                "failed",
                {"error": str(e)}
            )
        
        return session_results
    
    def _run_cycle(
        self,
        session_id: str,
        trace_id: str,
        goal_id: str,
        goal: str,
        cycle_num: int,
        target_directories: Optional[List[str]],
        operator_approval: bool
    ) -> Dict[str, Any]:
        """Run a single recursion cycle."""
        cycle_result = {
            "cycle_number": cycle_num,
            "start_time": datetime.utcnow().isoformat() + "Z",
            "phases": {},
            "status": "unknown"
        }
        
        try:
            # Phase 1: Inventory
            logger.info(f"Cycle {cycle_num} - Inventory phase")
            inventory_result = self._run_inventory_phase(
                session_id, trace_id, target_directories
            )
            cycle_result["phases"]["inventory"] = inventory_result
            
            # Phase 2: Planning
            logger.info(f"Cycle {cycle_num} - Planning phase")
            plan_result = self._run_planning_phase(
                session_id, trace_id, goal_id, goal, inventory_result, cycle_num
            )
            cycle_result["phases"]["planning"] = plan_result
            
            # Phase 3: Prompt Compilation
            logger.info(f"Cycle {cycle_num} - Prompt compilation phase")
            prompt_result = self._run_prompt_phase(
                session_id, trace_id, plan_result, cycle_num
            )
            cycle_result["phases"]["prompting"] = prompt_result
            
            # Phase 4: Execution
            logger.info(f"Cycle {cycle_num} - Execution phase")
            execution_result = self._run_execution_phase(
                session_id, trace_id, prompt_result
            )
            cycle_result["phases"]["execution"] = execution_result
            
            # Phase 5: Evaluation
            logger.info(f"Cycle {cycle_num} - Evaluation phase")
            evaluation_result = self._run_evaluation_phase(
                session_id, trace_id, execution_result, prompt_result
            )
            cycle_result["phases"]["evaluation"] = evaluation_result
            
            # Phase 6: Promotion
            logger.info(f"Cycle {cycle_num} - Promotion phase")
            promotion_result = self._run_promotion_phase(
                session_id, trace_id, evaluation_result, execution_result,
                prompt_result, operator_approval
            )
            cycle_result["phases"]["promotion"] = promotion_result
            
            # Determine if we should continue
            cycle_result["should_continue"] = self._should_continue_cycle(
                promotion_result, evaluation_result, cycle_num
            )
            
            cycle_result["status"] = "completed"
            cycle_result["end_time"] = datetime.utcnow().isoformat() + "Z"
            
            logger.info(f"Cycle {cycle_num} completed successfully")
            
        except Exception as e:
            logger.error(f"Cycle {cycle_num} failed: {e}")
            cycle_result["status"] = "failed"
            cycle_result["error"] = str(e)
            cycle_result["should_continue"] = False
        
        return cycle_result
    
    def _run_inventory_phase(
        self, session_id: str, trace_id: str, target_directories: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Run inventory phase."""
        # Default to current directory if none specified
        if not target_directories:
            target_directories = [str(Path.cwd())]
        
        # Run inventory
        inventory = self.inventory_scanner.scan_directories(target_directories)
        
        # Save inventory
        inventory_path = self.staging_dir / f"inventory_{session_id}.json"
        with open(inventory_path, 'w') as f:
            json.dump(inventory.to_dict(), f, indent=2)
        
        # Log trace
        self.trace_logger.log_inventory(session_id, trace_id, {
            "root_directories": target_directories,
            "total_components": inventory.total_components,
            "components_by_type": inventory.components_by_type,
            "inventory_path": str(inventory_path)
        })
        
        return {
            "status": "completed",
            "inventory_path": str(inventory_path),
            "total_components": inventory.total_components,
            "components_by_type": inventory.components_by_type
        }
    
    def _run_planning_phase(
        self, session_id: str, trace_id: str, goal_id: str, goal: str,
        inventory_result: Dict[str, Any], cycle_num: int
    ) -> Dict[str, Any]:
        """Run planning phase."""
        # Load inventory
        inventory_path = inventory_result.get("inventory_path")
        with open(inventory_path) as f:
            inventory_data = json.load(f)
        
        # Create plan
        plan = self.planner.create_plan(
            goal=goal,
            inventory=inventory_data,
            constraints={
                "max_recursion_depth": self.config["recursion"]["max_depth"],
                "cycle_number": cycle_num
            }
        )
        
        # Save plan
        plan_path = self.staging_dir / f"plan_{session_id}_cycle{cycle_num}.json"
        with open(plan_path, 'w') as f:
            json.dump(plan.to_dict(), f, indent=2)
        
        # Log trace
        self.trace_logger.log_planning(session_id, trace_id, {
            "goal": goal,
            "constraints": {"cycle": cycle_num},
            "tasks": [t.get("summary", "") for t in plan.tasks],
            "estimated_duration": plan.estimated_duration_minutes,
            "plan_path": str(plan_path)
        })
        
        return {
            "status": "completed",
            "plan_path": str(plan_path),
            "task_count": len(plan.tasks),
            "estimated_duration": plan.estimated_duration_minutes
        }
    
    def _run_prompt_phase(
        self, session_id: str, trace_id: str, plan_result: Dict[str, Any], cycle_num: int
    ) -> Dict[str, Any]:
        """Run prompt compilation phase."""
        # Load plan
        plan_path = plan_result.get("plan_path")
        with open(plan_path) as f:
            plan_data = json.load(f)
        
        # Get first task (for simplicity - in production would handle all tasks)
        if not plan_data.get("tasks"):
            raise ValueError("Plan has no tasks")
        
        task = plan_data["tasks"][0]
        
        # Compile prompt
        prompt = self.prompt_compiler.compile_prompt(
            task=task,
            context={
                "cycle_number": cycle_num,
                "session_id": session_id,
                "max_recursion_depth": self.config["recursion"]["max_depth"]
            }
        )
        
        # Save prompt
        prompt_path = self.staging_dir / f"prompt_{session_id}_cycle{cycle_num}.json"
        with open(prompt_path, 'w') as f:
            json.dump(prompt.to_dict(), f, indent=2)
        
        # Log trace
        self.trace_logger.log_prompting(session_id, trace_id, {
            "prompt_id": prompt.prompt_id,
            "task_summary": prompt.task_summary,
            "execution_mode": prompt.execution_mode,
            "expected_artifacts": prompt.expected_artifacts,
            "max_recursion_depth": prompt.max_recursion_depth,
            "prompt_path": str(prompt_path)
        })
        
        return {
            "status": "completed",
            "prompt_path": str(prompt_path),
            "prompt_id": prompt.prompt_id,
            "task_summary": prompt.task_summary,
            "execution_mode": prompt.execution_mode
        }
    
    def _run_execution_phase(
        self, session_id: str, trace_id: str, prompt_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run execution phase."""
        # Load prompt
        prompt_path = prompt_result.get("prompt_path")
        with open(prompt_path) as f:
            prompt_data = json.load(f)
        
        # Execute
        execution_result = self.executor.execute_task(prompt_data)
        
        # Convert to dict for logging
        exec_dict = execution_result.to_dict()
        
        # Log trace
        self.trace_logger.log_execution(session_id, trace_id, exec_dict)
        
        return {
            "status": "completed",
            "execution_result": exec_dict,
            "execution_id": execution_result.execution_id,
            "exit_code": execution_result.exit_code,
            "artifacts_created": execution_result.artifacts_created
        }
    
    def _run_evaluation_phase(
        self, session_id: str, trace_id: str,
        execution_result: Dict[str, Any], prompt_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run evaluation phase."""
        # Load prompt
        prompt_path = prompt_result.get("prompt_path")
        with open(prompt_path) as f:
            prompt_data = json.load(f)
        
        # Evaluate
        eval_result = self.evaluator.evaluate(
            execution_result["execution_result"],
            prompt_data
        )
        
        # Save evaluation
        eval_path = self.staging_dir / f"evaluation_{eval_result.evaluation_id}.json"
        eval_result.save(eval_path)
        
        # Convert to dict for logging
        eval_dict = eval_result.to_dict()
        
        # Log trace
        self.trace_logger.log_evaluation(session_id, trace_id, eval_dict)
        
        return {
            "status": "completed",
            "evaluation_result": eval_dict,
            "evaluation_id": eval_result.evaluation_id,
            "overall_score": eval_result.overall_score,
            "promotion_recommendation": eval_result.promotion_recommendation
        }
    
    def _run_promotion_phase(
        self, session_id: str, trace_id: str,
        evaluation_result: Dict[str, Any], execution_result: Dict[str, Any],
        prompt_result: Dict[str, Any], operator_approval: bool
    ) -> Dict[str, Any]:
        """Run promotion phase."""
        # Load prompt
        prompt_path = prompt_result.get("prompt_path")
        with open(prompt_path) as f:
            prompt_data = json.load(f)
        
        # Make promotion decision
        promotion_result = self.promoter.make_promotion_decision(
            evaluation_result["evaluation_result"],
            execution_result["execution_result"],
            prompt_data,
            operator_approved=operator_approval
        )
        
        # Save promotion result
        promo_path = self.staging_dir / f"promotion_{promotion_result.promotion_id}.json"
        promotion_result.save(promo_path)
        
        # Convert to dict for logging
        promo_dict = promotion_result.to_dict()
        
        # Log trace
        self.trace_logger.log_promotion(session_id, trace_id, promo_dict)
        
        # Log ProjectX judgment if present
        if promotion_result.projectx_judgment:
            self.trace_logger.log_projectx_review(
                session_id, trace_id,
                promotion_result.projectx_judgment,
                promotion_result.projectx_reason or ""
            )
        
        return {
            "status": "completed",
            "promotion_result": promo_dict,
            "promotion_id": promotion_result.promotion_id,
            "outcome": promotion_result.outcome,
            "artifacts_promoted": promotion_result.artifacts_promoted
        }
    
    def _should_continue_cycle(
        self, promotion_result: Dict[str, Any],
        evaluation_result: Dict[str, Any], cycle_num: int
    ) -> bool:
        """Determine if another cycle should run."""
        max_cycles = self.config["recursion"]["max_depth"]
        
        # Check max cycles
        if cycle_num >= max_cycles:
            logger.info(f"Reached max cycles ({max_cycles})")
            return False
        
        # Check promotion outcome
        outcome = promotion_result.get("outcome", "REJECT")
        if outcome == "REJECT":
            logger.info("Promotion rejected, stopping cycles")
            return False
        
        # Check evaluation score
        score = evaluation_result.get("overall_score", 0.0)
        min_score = self.config["evaluation"]["minimum_score"]
        
        if score < min_score * 0.7:  # If score is significantly below minimum
            logger.info(f"Low evaluation score ({score:.2f}), stopping cycles")
            return False
        
        # Default: continue if promotion was successful
        return outcome == "PROMOTE"
    
    def _generate_session_summary(self, session_results: Dict[str, Any]) -> str:
        """Generate summary of session results."""
        cycles = session_results.get("cycles", [])
        
        if not cycles:
            return "no_cycles"
        
        # Count statuses
        completed = sum(1 for c in cycles if c.get("status") == "completed")
        failed = sum(1 for c in cycles if c.get("status") == "failed")
        
        # Check final promotion outcome
        final_outcome = None
        for cycle in reversed(cycles):
            promotion = cycle.get("phases", {}).get("promotion", {})
            if promotion:
                final_outcome = promotion.get("outcome")
                break
        
        # Determine overall status
        if failed > 0:
            return "partial_failure"
        elif completed == len(cycles) and final_outcome == "PROMOTE":
            return "success"
        elif completed == len(cycles):
            return "completed_no_promotion"
        else:
            return "unknown"
    
    def _check_stop_conditions(
        self,
        session_results: Dict[str, Any],
        current_cycle: int,
        session_start_time: float
    ) -> Optional[str]:
        """
        Check if any stop conditions have been met.
        
        Args:
            session_results: Current session results
            current_cycle: Current cycle number
            session_start_time: Session start time (time.time())
            
        Returns:
            Stop reason string if should stop, None otherwise
        """
        max_cycles = session_results.get("max_cycles", 25)
        max_consecutive_failures = session_results.get("max_consecutive_failures", 3)
        max_total_time_seconds = session_results.get("max_total_time_seconds", 3600)
        consecutive_failures = session_results.get("consecutive_failures", 0)
        continuous = session_results.get("continuous_mode", False)
        
        # Check max cycles (for non-continuous mode)
        if not continuous and current_cycle > max_cycles:
            return f"max_cycles_reached ({current_cycle-1}/{max_cycles})"
        
        # Check consecutive failures
        if consecutive_failures >= max_consecutive_failures:
            return f"max_consecutive_failures_reached ({consecutive_failures}/{max_consecutive_failures})"
        
        # Check total time
        elapsed_time = time.time() - session_start_time
        if elapsed_time > max_total_time_seconds:
            return f"max_total_time_exceeded ({elapsed_time:.0f}s/{max_total_time_seconds}s)"
        
        return None
    
    def show_traces(self, session_id: Optional[str] = None, limit: int = 20) -> None:
        """Show trace events."""
        if session_id:
            traces = self.trace_logger.get_session_traces(session_id)
            print(f"\nTraces for session {session_id}:")
        else:
            traces = self.trace_logger.search_traces({}, limit)
            print(f"\nRecent traces (limit: {limit}):")
        
        for trace in traces[-limit:]:  # Show most recent
            phase = trace.get("phase", "unknown")
            action = trace.get("action", "unknown")
            status = trace.get("status", "unknown")
            timestamp = trace.get("timestamp", "")[:19]  # Trim milliseconds
            
            print(f"  {timestamp} [{phase:12}] {action:25} {status:10}")
            
            # Show error if present
            if trace.get("error_message"):
                print(f"    ERROR: {trace['error_message']}")
    
    def show_session_report(self, session_id: str) -> None:
        """Show detailed session report."""
        report = self.trace_logger.generate_session_report(session_id)
        
        print(f"\nSession Report: {session_id}")
        print("=" * 60)
        
        print(f"Trace ID: {report.get('trace_id', 'unknown')}")
        print(f"Event Count: {report.get('event_count', 0)}")
        print(f"Duration: {report.get('duration_seconds', 0):.1f}s")
        print(f"Average Latency: {report.get('average_latency_ms', 0):.1f}ms")
        
        print(f"\nPhase Distribution:")
        for phase, count in report.get("phase_distribution", {}).items():
            print(f"  {phase:15}: {count}")
        
        print(f"\nStatus Distribution:")
        for status, count in report.get("status_distribution", {}).items():
            print(f"  {status:15}: {count}")
        
        print(f"\nErrors: {report.get('error_count', 0)}")
        if report.get("errors"):
            for error in report["errors"][:3]:  # Show first 3 errors
                print(f"  - {error.get('error_code', 'unknown')}: {error.get('error_message', '')}")
        
        print(f"\nPromotion Decisions:")
        for decision in report.get("promotion_decisions", []):
            print(f"  - {decision.get('promotion_decision', 'unknown')}")
    
    def generate_enhanced_report(self, session_id: str, output_format: str = "text") -> Dict[str, Any]:
        """
        Generate enhanced session report with metrics and analysis.
        
        Args:
            session_id: Session ID
            output_format: Report format (text, json, html)
            
        Returns:
            Enhanced report data
        """
        # Load session data
        session_data = self.load_session_state(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")
        
        # Get trace report
        trace_report = self.trace_logger.generate_session_report(session_id)
        
        # Calculate enhanced metrics
        cycles = session_data.get("cycles", [])
        total_cycles = len(cycles)
        
        # Calculate phase durations
        phase_durations = {}
        phase_success_rates = {}
        
        for cycle in cycles:
            for phase_name, phase_result in cycle.get("phases", {}).items():
                if phase_name not in phase_durations:
                    phase_durations[phase_name] = []
                    phase_success_rates[phase_name] = []
                
                # Estimate duration from timestamps if available
                start_time = phase_result.get("start_time")
                end_time = phase_result.get("end_time")
                if start_time and end_time:
                    try:
                        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                        duration = (end_dt - start_dt).total_seconds()
                        phase_durations[phase_name].append(duration)
                    except:
                        pass
                
                # Track success
                status = phase_result.get("status", "unknown")
                phase_success_rates[phase_name].append(1 if status == "completed" else 0)
        
        # Calculate averages
        avg_phase_durations = {}
        avg_phase_success = {}
        
        for phase, durations in phase_durations.items():
            if durations:
                avg_phase_durations[phase] = sum(durations) / len(durations)
        
        for phase, successes in phase_success_rates.items():
            if successes:
                avg_phase_success[phase] = sum(successes) / len(successes) * 100
        
        # Calculate promotion metrics
        promotion_outcomes = []
        artifacts_promoted = 0
        
        for cycle in cycles:
            promotion = cycle.get("phases", {}).get("promotion", {})
            if promotion:
                outcome = promotion.get("outcome", "unknown")
                promotion_outcomes.append(outcome)
                artifacts_promoted += len(promotion.get("artifacts_promoted", []))
        
        # Build enhanced report
        enhanced_report = {
            "session_id": session_id,
            "basic_metrics": {
                "total_cycles": total_cycles,
                "session_status": session_data.get("final_status", "unknown"),
                "goal": session_data.get("goal", "")[:200],
                "start_time": session_data.get("start_time"),
                "end_time": session_data.get("end_time"),
                "continuous_mode": session_data.get("continuous_mode", False),
                "max_cycles": session_data.get("max_cycles", 25),
                "stop_reason": session_data.get("stop_reason", "unknown"),
                "consecutive_failures": session_data.get("consecutive_failures", 0),
                "max_consecutive_failures": session_data.get("max_consecutive_failures", 3),
                "max_total_time_seconds": session_data.get("max_total_time_seconds", 3600)
            },
            "performance_metrics": {
                "avg_phase_durations_seconds": avg_phase_durations,
                "avg_phase_success_rates_percent": avg_phase_success,
                "promotion_outcomes": {
                    "total": len(promotion_outcomes),
                    "promote_count": promotion_outcomes.count("PROMOTE"),
                    "reject_count": promotion_outcomes.count("REJECT"),
                    "pending_count": promotion_outcomes.count("PENDING"),
                    "promote_rate": (promotion_outcomes.count("PROMOTE") / len(promotion_outcomes) * 100) if promotion_outcomes else 0
                },
                "artifacts_promoted": artifacts_promoted
            },
            "trace_metrics": trace_report,
            "recommendations": self._generate_recommendations(session_data, trace_report)
        }
        
        # Generate output based on format
        if output_format == "json":
            return enhanced_report
        elif output_format == "html":
            return self._generate_html_report(enhanced_report)
        else:  # text format (default)
            self._print_enhanced_report(enhanced_report)
            return enhanced_report
    
    def _generate_recommendations(self, session_data: Dict[str, Any], trace_report: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on session analysis."""
        recommendations = []
        
        # Check for errors
        error_count = trace_report.get("error_count", 0)
        if error_count > 0:
            recommendations.append(f"Address {error_count} errors in the session logs")
        
        # Check promotion success rate
        cycles = session_data.get("cycles", [])
        if cycles:
            promotion_count = 0
            promotion_success = 0
            
            for cycle in cycles:
                promotion = cycle.get("phases", {}).get("promotion", {})
                if promotion:
                    promotion_count += 1
                    if promotion.get("outcome") == "PROMOTE":
                        promotion_success += 1
            
            if promotion_count > 0:
                success_rate = (promotion_success / promotion_count) * 100
                if success_rate < 50:
                    recommendations.append(f"Low promotion success rate ({success_rate:.1f}%) - review evaluation criteria")
        
        # Check cycle count
        if len(cycles) > 5:
            recommendations.append("High number of cycles - consider optimizing recursion depth")
        
        # Check for continuous mode without pause
        if session_data.get("continuous_mode", False) and session_data.get("pause_between_cycles", 0) < 10:
            recommendations.append("Continuous mode with short pauses may cause system strain")
        
        return recommendations
    
    def _print_enhanced_report(self, report: Dict[str, Any]) -> None:
        """Print enhanced report in text format."""
        print(f"\n{'='*80}")
        print(f"ENHANCED SESSION REPORT: {report['session_id']}")
        print(f"{'='*80}")
        
        # Basic metrics
        basic = report["basic_metrics"]
        print(f"\n📊 BASIC METRICS")
        print(f"  Goal: {basic['goal']}")
        print(f"  Status: {basic['session_status']}")
        print(f"  Cycles: {basic['total_cycles']}")
        print(f"  Start: {basic['start_time']}")
        print(f"  End: {basic['end_time']}")
        print(f"  Continuous Mode: {'Yes' if basic['continuous_mode'] else 'No'}")
        
        # Performance metrics
        perf = report["performance_metrics"]
        print(f"\n⚡ PERFORMANCE METRICS")
        
        if perf["avg_phase_durations_seconds"]:
            print(f"  Phase Durations (avg seconds):")
            for phase, duration in perf["avg_phase_durations_seconds"].items():
                print(f"    • {phase:15}: {duration:.2f}s")
        
        if perf["avg_phase_success_rates_percent"]:
            print(f"  Phase Success Rates:")
            for phase, rate in perf["avg_phase_success_rates_percent"].items():
                print(f"    • {phase:15}: {rate:.1f}%")
        
        promo = perf["promotion_outcomes"]
        print(f"  Promotion Outcomes:")
        print(f"    • Total decisions: {promo['total']}")
        print(f"    • Promoted: {promo['promote_count']} ({promo['promote_rate']:.1f}%)")
        print(f"    • Rejected: {promo['reject_count']}")
        print(f"    • Pending: {promo['pending_count']}")
        print(f"    • Artifacts promoted: {perf['artifacts_promoted']}")
        
        # Trace metrics
        trace = report["trace_metrics"]
        print(f"\n📈 TRACE METRICS")
        print(f"  Events: {trace.get('event_count', 0)}")
        print(f"  Duration: {trace.get('duration_seconds', 0):.1f}s")
        print(f"  Avg Latency: {trace.get('average_latency_ms', 0):.1f}ms")
        print(f"  Errors: {trace.get('error_count', 0)}")
        
        # Recommendations
        recs = report["recommendations"]
        if recs:
            print(f"\n💡 RECOMMENDATIONS")
            for i, rec in enumerate(recs, 1):
                print(f"  {i}. {rec}")
        
        print(f"\n{'='*80}")
    
    def _generate_html_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate HTML report (placeholder - returns JSON for now)."""
        # For now, return the JSON data
        # In a full implementation, this would generate an HTML file
        return {
            "html_available": False,
            "message": "HTML report generation not yet implemented",
            "data": report
        }
    
    def show_real_time_progress(self, session_id: str, refresh_interval: int = 2, 
                              include_resources: bool = False) -> None:
        """
        Show real-time progress updates for a session with optional resource monitoring.
        
        Args:
            session_id: Session ID to monitor
            refresh_interval: Refresh interval in seconds
            include_resources: Whether to include system resource monitoring
        """
        import time
        import os
        
        print(f"\n🔍 Real-time Progress Monitor: {session_id}")
        print("Press Ctrl+C to stop monitoring\n")
        
        last_event_count = 0
        monitoring_thread = None
        
        try:
            # Start resource monitoring if requested and available
            if include_resources and RESOURCE_MONITOR_AVAILABLE:
                print("📊 Resource monitoring enabled")
                from threading import Event
                
                # Start monitoring thread
                stop_event = Event()
                monitoring_thread = MonitoringThread(
                    self.resource_monitor,
                    interval=refresh_interval,
                    stop_event=stop_event
                )
                monitoring_thread.start()
            
            while True:
                # Clear screen for better display
                os.system('clear' if os.name == 'posix' else 'cls')
                
                print(f"\n{'='*80}")
                print(f"🔍 Real-time Progress Monitor: {session_id}")
                print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*80}\n")
                
                # Load session data
                session_data = self.load_session_state(session_id)
                
                if not session_data:
                    print("❌ Session not found or cannot be loaded")
                    break
                
                # Get latest traces
                traces = self.trace_logger.get_session_traces(session_id)
                
                # Show session summary
                cycles = session_data.get("cycles", [])
                status = session_data.get("final_status", "running")
                
                print(f"📊 SESSION SUMMARY")
                print(f"  Status: {status}")
                print(f"  Cycles completed: {len(cycles)}")
                print(f"  Goal: {session_data.get('goal', 'Unknown')[:80]}")
                
                if cycles:
                    last_cycle = cycles[-1]
                    current_phase = None
                    
                    # Find current phase in last cycle
                    for phase_name, phase_result in last_cycle.get("phases", {}).items():
                        if phase_result.get("status") == "running":
                            current_phase = phase_name
                            break
                    
                    if current_phase:
                        print(f"  Current phase: {current_phase}")
                
                # Show recent events
                if traces:
                    # Show new events since last check
                    new_traces = traces[last_event_count:]
                    
                    if new_traces:
                        print(f"\n📋 RECENT EVENTS (last {len(new_traces)} new)")
                        for trace in new_traces[-10:]:  # Show last 10 new events
                            phase = trace.get("phase", "unknown")
                            action = trace.get("action", "unknown")
                            status = trace.get("status", "unknown")
                            timestamp = trace.get("timestamp", "")[11:19]  # Time only
                            
                            status_symbol = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
                            print(f"  {timestamp} {status_symbol} [{phase:12}] {action[:60]}")
                    
                    last_event_count = len(traces)
                
                # Show resource monitoring if enabled
                if include_resources and RESOURCE_MONITOR_AVAILABLE and self.resource_monitor and PSUTIL_AVAILABLE:
                    print(f"\n💻 SYSTEM RESOURCES")
                    
                    try:
                        # Collect current metrics
                        metrics = self.resource_monitor.collect_metrics()
                        
                        # Show CPU
                        cpu_bar = self._create_progress_bar(metrics.cpu_percent, 100)
                        print(f"  CPU:    {cpu_bar} {metrics.cpu_percent:5.1f}%")
                        
                        # Show Memory
                        mem_bar = self._create_progress_bar(metrics.memory_percent, 100)
                        print(f"  Memory: {mem_bar} {metrics.memory_percent:5.1f}% ({metrics.memory_used_gb:.1f}/{metrics.memory_total_gb:.1f} GB)")
                        
                        # Show Disk
                        disk_bar = self._create_progress_bar(metrics.disk_percent, 100)
                        print(f"  Disk:   {disk_bar} {metrics.disk_percent:5.1f}% ({metrics.disk_used_gb:.1f}/{metrics.disk_total_gb:.1f} GB)")
                        
                        # Show Load Average
                        cpu_count = psutil.cpu_count()
                        load_per_core = metrics.load_average_1m / cpu_count if cpu_count > 0 else metrics.load_average_1m
                        load_status = "🟢" if load_per_core < 1.0 else "🟡" if load_per_core < 2.0 else "🔴"
                        print(f"  Load:   {load_status} {metrics.load_average_1m:.2f} (1m) | {metrics.load_average_5m:.2f} (5m) | {metrics.load_average_15m:.2f} (15m)")
                        
                        # Show network
                        print(f"  Network: ↑{metrics.network_sent_mb:.1f} MB | ↓{metrics.network_recv_mb:.1f} MB")
                        
                        # Check for alerts
                        alerts = self.resource_monitor.check_alerts(metrics)
                        if alerts:
                            print(f"\n⚠️  RESOURCE ALERTS")
                            for alert in alerts[-3:]:  # Show last 3 alerts
                                alert_symbol = "🔴" if alert.level.value == "critical" else "🟡" if alert.level.value == "high" else "🟢"
                                print(f"  {alert_symbol} {alert.message}")
                    except Exception as e:
                        print(f"  ❌ Resource monitoring error: {e}")
                elif include_resources and not PSUTIL_AVAILABLE:
                    print(f"\n💻 SYSTEM RESOURCES")
                    print(f"  ⚠️  psutil not available - install with 'pip install psutil' for resource monitoring")
                
                # Check if session is complete
                if status not in ["unknown", "running"]:
                    print(f"\n{'='*80}")
                    print(f"✅ Session completed with status: {status}")
                    print(f"{'='*80}")
                    break
                
                # Show refresh info
                print(f"\n{'='*80}")
                print(f"🔄 Refreshing in {refresh_interval} seconds... (Press Ctrl+C to stop)")
                print(f"{'='*80}")
                
                # Wait for next refresh
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print(f"\n\n{'='*80}")
            print("🛑 Monitoring stopped by user")
            print(f"{'='*80}")
        except Exception as e:
            print(f"\n❌ Error monitoring session: {e}")
        finally:
            # Stop monitoring thread if running
            if monitoring_thread and monitoring_thread.running:
                monitoring_thread.stop()
                monitoring_thread.join(timeout=5.0)
                print("📊 Resource monitoring stopped")
    
    def _create_progress_bar(self, value: float, max_value: float, width: int = 20) -> str:
        """
        Create a text-based progress bar.
        
        Args:
            value: Current value
            max_value: Maximum value
            width: Bar width in characters
            
        Returns:
            Progress bar string
        """
        filled = int((value / max_value) * width)
        bar = "█" * filled + "░" * (width - filled)
        
        # Add color based on percentage
        percentage = (value / max_value) * 100
        if percentage < 50:
            color_code = "32"  # Green
        elif percentage < 75:
            color_code = "33"  # Yellow
        else:
            color_code = "31"  # Red
        
        return f"\033[{color_code}m{bar}\033[0m"
    
    def cleanup(self, older_than_hours: int = 24) -> None:
        """Clean up old staging directories and backups."""
        logger.info(f"Cleaning up files older than {older_than_hours} hours")
        
        # Clean executor staging
        exec_removed = self.executor.cleanup_staging(older_than_hours)
        logger.info(f"Removed {exec_removed} old staging directories")
        
        # Clean promoter backups
        backup_removed = self.promoter.cleanup_backups(older_than_hours // 24)  # Convert to days
        logger.info(f"Removed {backup_removed} old backup directories")
        
        # Clean old trace files (keep last 7 days)
        self._cleanup_old_traces(7)
    
    def _cleanup_old_traces(self, keep_days: int = 7) -> None:
        """Clean up old trace files."""
        import time
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        cutoff_timestamp = cutoff_date.timestamp()
        
        removed_count = 0
        
        # Clean archived trace files
        for trace_file in self.trace_dir.glob("traces_*.jsonl.gz"):
            if trace_file.stat().st_mtime < cutoff_timestamp:
                try:
                    trace_file.unlink()
                    removed_count += 1
                    logger.info(f"Removed old trace file: {trace_file}")
                except Exception as e:
                    logger.error(f"Failed to remove {trace_file}: {e}")
        
        logger.info(f"Removed {removed_count} old trace files")
    
    def save_session_state(self, session_id: str, session_data: Dict[str, Any]) -> str:
        """
        Save session state to disk.
        
        Args:
            session_id: Session ID
            session_data: Session data to save
            
        Returns:
            Path to saved session file
        """
        session_file = self.sessions_dir / f"session_{session_id}.json"
        
        # Add metadata
        session_data["_persisted_at"] = datetime.utcnow().isoformat() + "Z"
        session_data["_persisted_version"] = "1.0"
        
        # Save to file
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        logger.info(f"Session {session_id} state saved to: {session_file}")
        return str(session_file)
    
    def load_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session state from disk.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data or None if not found
        """
        session_file = self.sessions_dir / f"session_{session_id}.json"
        
        if not session_file.exists():
            logger.warning(f"Session file not found: {session_file}")
            return None
        
        try:
            with open(session_file) as f:
                session_data = json.load(f)
            
            logger.info(f"Session {session_id} state loaded from: {session_file}")
            return session_data
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def list_sessions(self, include_inactive: bool = True) -> List[Dict[str, Any]]:
        """
        List all saved sessions.
        
        Args:
            include_inactive: Include completed/failed sessions
            
        Returns:
            List of session metadata
        """
        sessions = []
        
        for session_file in self.sessions_dir.glob("session_*.json"):
            try:
                with open(session_file) as f:
                    session_data = json.load(f)
                
                session_id = session_data.get("session_id", "unknown")
                status = session_data.get("final_status", "unknown")
                start_time = session_data.get("start_time", "")
                cycles = len(session_data.get("cycles", []))
                
                # Skip inactive sessions if requested
                if not include_inactive and status in ["success", "failed", "completed_no_promotion"]:
                    continue
                
                sessions.append({
                    "session_id": session_id,
                    "status": status,
                    "start_time": start_time,
                    "cycles": cycles,
                    "file": str(session_file),
                    "goal": session_data.get("goal", "")[:100]  # Truncate long goals
                })
            except Exception as e:
                logger.error(f"Failed to read session file {session_file}: {e}")
        
        # Sort by start time (newest first)
        sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        
        return sessions
    
    def resume_session(self, session_id: str) -> Dict[str, Any]:
        """
        Resume an interrupted session.
        
        Args:
            session_id: Session ID to resume
            
        Returns:
            Updated session results
        """
        # Load session state
        session_data = self.load_session_state(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found or cannot be loaded")
        
        # Check if session can be resumed
        status = session_data.get("final_status", "unknown")
        if status not in ["unknown", "interrupted", "partial_failure"]:
            raise ValueError(f"Session {session_id} has status '{status}' and cannot be resumed")
        
        logger.info(f"Resuming session {session_id}")
        
        # Extract session parameters
        goal = session_data.get("goal", "")
        target_directories = session_data.get("target_directories")
        operator_approval = session_data.get("operator_approval", False)
        continuous = session_data.get("continuous_mode", False)
        pause_between_cycles = session_data.get("pause_between_cycles", 60)
        
        # Get existing cycles
        existing_cycles = session_data.get("cycles", [])
        last_cycle_num = len(existing_cycles)
        
        # Update trace logger with existing session
        trace_id = session_data.get("trace_id")
        goal_id = session_data.get("goal_id")
        
        # Continue from where we left off
        session_results = session_data.copy()
        session_results["resumed_at"] = datetime.utcnow().isoformat() + "Z"
        
        try:
            cycle_num = last_cycle_num + 1
            session_start_time = time.time()
            
            while True:  # Loop for continuous mode
                # Check stop conditions
                stop_reason = self._check_stop_conditions(
                    session_results, cycle_num, session_start_time
                )
                if stop_reason:
                    logger.info(f"Stop condition triggered: {stop_reason}")
                    session_results["stop_reason"] = stop_reason
                    break
                    
                logger.info(f"Resuming cycle {cycle_num}")
                self.trace_logger.start_cycle(session_id, cycle_num, goal_id)
                
                cycle_result = self._run_cycle(
                    session_id, trace_id, goal_id, goal, cycle_num,
                    target_directories, operator_approval
                )
                
                session_results["cycles"].append(cycle_result)
                
                # Update failure tracking
                if cycle_result.get("status") == "failed":
                    session_results["consecutive_failures"] = session_results.get("consecutive_failures", 0) + 1
                else:
                    session_results["consecutive_failures"] = 0
                
                # Check if we should continue based on cycle result
                if cycle_result.get("should_continue", False) is False:
                    logger.info(f"Cycle {cycle_num} indicates no further cycles needed")
                    session_results["stop_reason"] = "cycle_completion"
                    break
                
                # Increment cycle number
                cycle_num += 1
                
                # If in continuous mode, pause between cycles
                if continuous:
                    logger.info(f"Continuous mode: pausing for {pause_between_cycles} seconds before next cycle")
                    try:
                        time.sleep(pause_between_cycles)
                    except KeyboardInterrupt:
                        logger.info("Continuous mode interrupted by user")
                        session_results["final_status"] = "interrupted"
                        session_results["stop_reason"] = "user_interrupt"
                        break
            
            # Update session summary
            session_results["final_status"] = self._generate_session_summary(session_results)
            session_results["end_time"] = datetime.utcnow().isoformat() + "Z"
            
            # Save updated state
            self.save_session_state(session_id, session_results)
            
            logger.info(f"Session {session_id} resumed and completed with status: {session_results['final_status']}")
            
        except Exception as e:
            logger.error(f"Failed to resume session {session_id}: {e}")
            session_results["final_status"] = "failed"
            session_results["error"] = str(e)
            
            # Save error state
            self.save_session_state(session_id, session_results)
        
        return session_results
    
    def run_stress_test(
        self,
        agents: Optional[List[str]] = None,
        concurrent_workers: int = 5,
        duration_seconds: int = 30,
        intent_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run a stress test on the SIMP system.
        
        Args:
            agents: List of agent IDs to test (None = all registered)
            concurrent_workers: Number of concurrent workers
            duration_seconds: Test duration in seconds
            intent_types: Intent types to test (None = use defaults)
            
        Returns:
            Stress test results
        """
        if not WATCHTOWER_AVAILABLE:
            raise ImportError("Watchtower stress test module not available")
        
        logger.info(f"Starting stress test with {concurrent_workers} concurrent workers for {duration_seconds} seconds")
        
        # Create stress tester
        tester = WatchtowerStressTester()
        
        # Run test
        summary = tester.run_concurrent_test(
            agents=agents,
            concurrent_workers=concurrent_workers,
            duration_seconds=duration_seconds,
            intent_types=intent_types
        )
        
        # Print summary
        tester.print_summary(summary)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.base_dir / f"stress_test_results_{timestamp}.json"
        tester.save_results(summary, str(results_file))
        
        logger.info(f"Stress test results saved to: {results_file}")
        
        return {
            "test_id": summary.test_id,
            "duration_seconds": summary.duration_seconds,
            "total_requests": summary.total_requests,
            "success_rate": summary.overall_success_rate,
            "avg_response_time_ms": summary.avg_response_time_ms,
            "results_file": str(results_file),
            "recommendations": summary.recommendations
        }
    
    def shutdown(self) -> None:
        """Shutdown the CLI and all components."""
        logger.info("Shutting down Self Compiler CLI")
        self.trace_logger.shutdown()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sovereign Self Compiler v2 - Recursive self-compilation system"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a self-compilation session")
    run_parser.add_argument("goal", help="Goal description for the session")
    run_parser.add_argument("--cycles", type=int, default=25,
                          help="Maximum recursion cycles (default: 25, scalable to 100)")
    run_parser.add_argument("--directories", nargs="+",
                          help="Directories to inventory (default: current directory)")
    run_parser.add_argument("--auto-approve", action="store_true",
                          help="Auto-approve promotions (use with caution)")
    run_parser.add_argument("--output", help="Output file for session results")
    run_parser.add_argument("--continuous", action="store_true",
                          help="Run in continuous mode (indefinitely until interrupted)")
    run_parser.add_argument("--pause", type=int, default=60,
                          help="Pause between cycles in seconds (continuous mode only, default: 60)")
    run_parser.add_argument("--max-failures", type=int, default=3,
                          help="Stop after N consecutive failed cycles (default: 3)")
    run_parser.add_argument("--max-time", type=int, default=3600,
                          help="Maximum total session time in seconds (default: 3600)")
    
    # Traces command
    traces_parser = subparsers.add_parser("traces", help="Show trace events")
    traces_parser.add_argument("--session", help="Session ID to filter by")
    traces_parser.add_argument("--limit", type=int, default=20,
                             help="Maximum number of traces to show")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Show session report")
    report_parser.add_argument("session_id", help="Session ID to report on")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old files")
    cleanup_parser.add_argument("--hours", type=int, default=24,
                              help="Clean files older than N hours (default: 24)")
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Show configuration")
    config_parser.add_argument("--section", help="Show specific config section")
    
    # Stress test command (only if watchtower is available)
    if WATCHTOWER_AVAILABLE:
        stress_parser = subparsers.add_parser("stress-test", help="Run stress test on SIMP system")
        stress_parser.add_argument("--agents", nargs="+",
                                 help="Agent IDs to test (default: all registered)")
        stress_parser.add_argument("--concurrent", type=int, default=5,
                                 help="Number of concurrent workers (default: 5)")
        stress_parser.add_argument("--duration", type=int, default=30,
                                 help="Test duration in seconds (default: 30)")
        stress_parser.add_argument("--intents", nargs="+",
                                 help="Intent types to test (default: ping, health_check)")
    
    # Session management commands
    sessions_parser = subparsers.add_parser("sessions", help="Manage saved sessions")
    sessions_subparsers = sessions_parser.add_subparsers(dest="sessions_command", help="Session commands")
    
    # List sessions
    list_parser = sessions_subparsers.add_parser("list", help="List saved sessions")
    list_parser.add_argument("--all", action="store_true",
                           help="Include completed/failed sessions")
    
    # Show session details
    show_parser = sessions_subparsers.add_parser("show", help="Show session details")
    show_parser.add_argument("session_id", help="Session ID to show")
    
    # Resume session
    resume_parser = sessions_subparsers.add_parser("resume", help="Resume a session")
    resume_parser.add_argument("session_id", help="Session ID to resume")
    
    # Enhanced report command
    report_parser = subparsers.add_parser("enhanced-report", help="Generate enhanced session report")
    report_parser.add_argument("session_id", help="Session ID to report on")
    report_parser.add_argument("--format", choices=["text", "json", "html"], default="text",
                             help="Report format (default: text)")
    report_parser.add_argument("--output", help="Output file (for json/html formats)")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor session in real-time")
    monitor_parser.add_argument("session_id", help="Session ID to monitor")
    monitor_parser.add_argument("--interval", type=int, default=2,
                              help="Refresh interval in seconds (default: 2)")
    monitor_parser.add_argument("--resources", action="store_true",
                              help="Include system resource monitoring (requires psutil)")
    
    args = parser.parse_args()
    
    # Default config path
    config_path = Path(__file__).parent.parent / "config" / "self_compiler_config.json"
    
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        sys.exit(1)
    
    # Create CLI
    cli = SelfCompilerCLI(config_path)
    
    try:
        if args.command == "run":
            # Run session
            results = cli.run_session(
                goal=args.goal,
                max_cycles=args.cycles,
                target_directories=args.directories,
                operator_approval=args.auto_approve,
                continuous=args.continuous,
                pause_between_cycles=args.pause,
                max_consecutive_failures=args.max_failures,
                max_total_time_seconds=args.max_time
            )
            
            # Print summary
            print(f"\nSession {results['session_id']} completed!")
            print(f"Status: {results['final_status']}")
            print(f"Cycles run: {len(results['cycles'])}")
            
            # Show promotion results from last cycle
            if results['cycles']:
                last_cycle = results['cycles'][-1]
                promotion = last_cycle.get('phases', {}).get('promotion', {})
                if promotion:
                    print(f"Promotion outcome: {promotion.get('outcome', 'unknown')}")
                    promoted = promotion.get('artifacts_promoted', [])
                    if promoted:
                        print(f"Artifacts promoted: {len(promoted)}")
            
            # Save results if requested
            if args.output:
                output_path = Path(args.output)
                with open(output_path, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"\nResults saved to: {output_path}")
        
        elif args.command == "traces":
            # Show traces
            cli.show_traces(args.session, args.limit)
        
        elif args.command == "report":
            # Show session report
            cli.show_session_report(args.session_id)
        
        elif args.command == "cleanup":
            # Cleanup old files
            cli.cleanup(args.hours)
            print(f"Cleanup completed (files older than {args.hours} hours)")
        
        elif args.command == "config":
            # Show configuration
            with open(config_path) as f:
                config = json.load(f)
            
            if args.section:
                # Show specific section
                if args.section in config:
                    print(json.dumps(config[args.section], indent=2))
                else:
                    print(f"Section '{args.section}' not found in config")
                    print(f"Available sections: {', '.join(config.keys())}")
            else:
                # Show all sections
                for section, data in config.items():
                    print(f"\n[{section}]")
                    if isinstance(data, dict):
                        print(f"  Keys: {', '.join(data.keys())}")
                    else:
                        print(f"  Type: {type(data).__name__}")
        
        elif args.command == "stress-test" and WATCHTOWER_AVAILABLE:
            # Run stress test
            results = cli.run_stress_test(
                agents=args.agents,
                concurrent_workers=args.concurrent,
                duration_seconds=args.duration,
                intent_types=args.intents
            )
            
            print(f"\nStress test completed!")
            print(f"Test ID: {results['test_id']}")
            print(f"Duration: {results['duration_seconds']}s")
            print(f"Total requests: {results['total_requests']}")
            print(f"Success rate: {results['success_rate']:.1%}")
            print(f"Avg response time: {results['avg_response_time_ms']:.1f}ms")
            print(f"Results saved to: {results['results_file']}")
            
            if results['recommendations']:
                print(f"\nRecommendations:")
                for rec in results['recommendations']:
                    print(f"  • {rec}")
        
        elif args.command == "stress-test" and not WATCHTOWER_AVAILABLE:
            print("Error: Watchtower stress test module not available")
            print("Make sure watchtower_stress_test.py is in the SIMP directory")
        
        elif args.command == "sessions":
            if not args.sessions_command or args.sessions_command == "list":
                # List sessions
                sessions = cli.list_sessions(include_inactive=args.all if hasattr(args, 'all') else False)
                
                if not sessions:
                    print("No sessions found")
                else:
                    print(f"\nSaved Sessions ({len(sessions)}):")
                    print("=" * 100)
                    print(f"{'Session ID':<12} {'Status':<20} {'Start Time':<20} {'Cycles':<8} {'Goal'}")
                    print("-" * 100)
                    
                    for session in sessions:
                        status = session.get("status", "unknown")
                        start_time = session.get("start_time", "")[:19]  # Trim milliseconds
                        goal_preview = session.get("goal", "")[:50]
                        if len(session.get("goal", "")) > 50:
                            goal_preview += "..."
                        
                        print(f"{session['session_id']:<12} {status:<20} {start_time:<20} {session['cycles']:<8} {goal_preview}")
            
            elif args.sessions_command == "show":
                # Show session details
                session_data = cli.load_session_state(args.session_id)
                
                if not session_data:
                    print(f"Session {args.session_id} not found")
                else:
                    print(f"\nSession Details: {args.session_id}")
                    print("=" * 60)
                    print(f"Goal: {session_data.get('goal', 'Unknown')}")
                    print(f"Status: {session_data.get('final_status', 'unknown')}")
                    print(f"Start Time: {session_data.get('start_time', '')}")
                    print(f"End Time: {session_data.get('end_time', 'Not completed')}")
                    print(f"Cycles: {len(session_data.get('cycles', []))}")
                    print(f"Continuous Mode: {session_data.get('continuous_mode', False)}")
                    
                    if session_data.get('error'):
                        print(f"Error: {session_data['error']}")
            
            elif args.sessions_command == "resume":
                # Resume session
                try:
                    results = cli.resume_session(args.session_id)
                    
                    print(f"\nSession {args.session_id} resumed!")
                    print(f"Status: {results['final_status']}")
                    print(f"Total cycles: {len(results['cycles'])}")
                    
                    # Show promotion results from last cycle
                    if results['cycles']:
                        last_cycle = results['cycles'][-1]
                        promotion = last_cycle.get('phases', {}).get('promotion', {})
                        if promotion:
                            print(f"Promotion outcome: {promotion.get('outcome', 'unknown')}")
                            promoted = promotion.get('artifacts_promoted', [])
                            if promoted:
                                print(f"Artifacts promoted: {len(promoted)}")
                
                except Exception as e:
                    print(f"Error resuming session: {e}")
        
        elif args.command == "enhanced-report":
            # Generate enhanced report
            try:
                report = cli.generate_enhanced_report(args.session_id, args.format)
                
                # Save to file if requested
                if args.output:
                    output_path = Path(args.output)
                    if args.format == "json":
                        with open(output_path, 'w') as f:
                            json.dump(report, f, indent=2)
                        print(f"\nJSON report saved to: {output_path}")
                    elif args.format == "html":
                        # For now, save as JSON since HTML generation is not implemented
                        with open(output_path, 'w') as f:
                            json.dump(report, f, indent=2)
                        print(f"\nReport data saved to: {output_path} (HTML not yet implemented)")
                
            except Exception as e:
                print(f"Error generating enhanced report: {e}")
        
        elif args.command == "monitor":
            # Monitor session in real-time
            try:
                cli.show_real_time_progress(
                    args.session_id, 
                    args.interval,
                    include_resources=getattr(args, 'resources', False)
                )
            except Exception as e:
                print(f"Error monitoring session: {e}")
        
        else:
            # No command specified, show help
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        logger.error(f"CLI error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        cli.shutdown()


if __name__ == "__main__":
    main()