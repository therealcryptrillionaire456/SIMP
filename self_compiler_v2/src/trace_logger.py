#!/usr/bin/env python3
"""
Trace Logger for Sovereign Self Compiler v2.

Structured logging for the entire recursive pipeline with JSONL output,
correlation IDs, and integration with Agent Lightning concepts.
"""

import gzip
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, List, Optional, Any, Union
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TracePhase(Enum):
    """Phases of the recursive pipeline."""
    INVENTORY = "inventory"
    PLANNING = "planning"
    PROMPTING = "prompting"
    EXECUTION = "execution"
    EVALUATION = "evaluation"
    PROMOTION = "promotion"
    CONTROLLER = "controller"
    INTEGRATION = "integration"


class TraceStatus(Enum):
    """Trace status codes."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    WARNING = "warning"
    INFO = "info"


@dataclass
class TraceEvent:
    """A single trace event."""
    trace_id: str
    session_id: str
    phase: str
    action: str
    status: str
    timestamp: str
    latency_ms: Optional[int] = None
    cycle_number: Optional[int] = None
    goal_id: Optional[str] = None
    prompt_id: Optional[str] = None
    execution_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    promotion_id: Optional[str] = None
    inputs_summary: Dict[str, Any] = field(default_factory=dict)
    outputs_summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    projectx_judgment: Optional[str] = None
    promotion_decision: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_jsonl(self) -> str:
        """Convert to JSONL string."""
        return json.dumps(self.to_dict()) + "\n"


class TraceBuffer:
    """Thread-safe buffer for trace events."""
    
    def __init__(self, max_size: int = 1000):
        self.buffer: List[TraceEvent] = []
        self.max_size = max_size
        self.lock = threading.Lock()
    
    def add(self, event: TraceEvent) -> None:
        """Add event to buffer."""
        with self.lock:
            self.buffer.append(event)
            # Trim if buffer too large
            if len(self.buffer) > self.max_size:
                self.buffer = self.buffer[-self.max_size:]
    
    def flush(self) -> List[TraceEvent]:
        """Get all events and clear buffer."""
        with self.lock:
            events = self.buffer.copy()
            self.buffer.clear()
            return events
    
    def size(self) -> int:
        """Get current buffer size."""
        with self.lock:
            return len(self.buffer)


class TraceWriter(threading.Thread):
    """Background thread for writing traces to disk."""
    
    def __init__(self, trace_dir: Path, buffer: TraceBuffer, flush_interval: float = 5.0):
        super().__init__()
        self.trace_dir = trace_dir
        self.buffer = buffer
        self.flush_interval = flush_interval
        self.running = True
        self.daemon = True
        
        # Ensure trace directory exists
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        
        # Current trace file
        self.current_file = self._get_trace_file_path()
        
        logger.info(f"Trace writer initialized with directory: {trace_dir}")
    
    def run(self) -> None:
        """Main writer loop."""
        while self.running:
            try:
                # Flush buffer to disk
                self._flush_buffer()
                
                # Sleep until next flush
                time.sleep(self.flush_interval)
                
            except Exception as e:
                logger.error(f"Trace writer error: {e}")
                time.sleep(1)  # Avoid tight error loop
    
    def stop(self) -> None:
        """Stop the writer thread."""
        self.running = False
        # Final flush
        self._flush_buffer()
    
    def _flush_buffer(self) -> None:
        """Flush buffer to current trace file."""
        events = self.buffer.flush()
        
        if not events:
            return
        
        try:
            # Write events to file
            with open(self.current_file, 'a') as f:
                for event in events:
                    f.write(event.to_jsonl())
            
            logger.debug(f"Wrote {len(events)} trace events to {self.current_file}")
            
            # Rotate file if it's getting large (>10MB)
            if self.current_file.stat().st_size > 10 * 1024 * 1024:
                self._rotate_trace_file()
                
        except Exception as e:
            logger.error(f"Failed to write trace events: {e}")
            # Put events back in buffer (except the ones that might have been written)
            for event in events:
                self.buffer.add(event)
    
    def _rotate_trace_file(self) -> None:
        """Rotate to a new trace file."""
        # Close current file and create new one
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_file = self.trace_dir / f"traces_{timestamp}.jsonl.gz"
        
        try:
            # Compress old file
            with open(self.current_file, 'rb') as f_in:
                with gzip.open(archive_file, 'wb') as f_out:
                    f_out.write(f_in.read())
            
            # Delete original
            self.current_file.unlink()
            
            # Create new file
            self.current_file = self._get_trace_file_path()
            
            logger.info(f"Rotated trace file to {self.current_file}, archived to {archive_file}")
            
        except Exception as e:
            logger.error(f"Failed to rotate trace file: {e}")
    
    def _get_trace_file_path(self) -> Path:
        """Get path for current trace file."""
        return self.trace_dir / "current_traces.jsonl"


class TraceLogger:
    """Main trace logger for the self-compiler."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize trace logger with configuration.
        
        Args:
            config: Observability configuration from self_compiler_config.json
        """
        self.config = config
        
        # Trace settings
        self.trace_format = config.get("trace_format", "jsonl")
        trace_dir = config.get("trace_directory", "./traces")
        self.trace_dir = Path(trace_dir)
        
        # Trace surfaces
        self.trace_surfaces = config.get("trace_surfaces", {})
        
        # Metrics collection
        self.metrics_config = config.get("metrics", {})
        
        # Initialize buffer and writer
        self.buffer = TraceBuffer()
        self.writer = TraceWriter(self.trace_dir, self.buffer)
        self.writer.start()
        
        # Session tracking
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_lock = threading.Lock()
        
        logger.info(f"Trace logger initialized with directory: {self.trace_dir}")
    
    def start_session(self, session_id: str, goal_id: str, config: Dict[str, Any]) -> str:
        """
        Start a new tracing session.
        
        Args:
            session_id: Session identifier
            goal_id: Goal identifier
            config: Session configuration
            
        Returns:
            Trace ID for the session
        """
        trace_id = str(uuid.uuid4())
        
        with self.session_lock:
            self.active_sessions[session_id] = {
                "trace_id": trace_id,
                "goal_id": goal_id,
                "start_time": datetime.utcnow(),
                "config": config,
                "cycle_count": 0,
                "events": []
            }
        
        # Log session start
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.CONTROLLER.value,
            action="session_started",
            status=TraceStatus.STARTED.value,
            goal_id=goal_id,
            inputs_summary={"config": config}
        )
        
        logger.info(f"Started trace session {session_id} with trace ID {trace_id}")
        return trace_id
    
    def end_session(self, session_id: str, status: str, summary: Dict[str, Any]) -> None:
        """
        End a tracing session.
        
        Args:
            session_id: Session identifier
            status: Final status (completed, failed, cancelled)
            summary: Session summary
        """
        with self.session_lock:
            if session_id not in self.active_sessions:
                logger.warning(f"Session {session_id} not found")
                return
            
            session = self.active_sessions[session_id]
            trace_id = session["trace_id"]
            start_time = session["start_time"]
            
            # Calculate duration
            duration = datetime.utcnow() - start_time
            latency_ms = int(duration.total_seconds() * 1000)
            
            # Log session end
            self.log_event(
                trace_id=trace_id,
                session_id=session_id,
                phase=TracePhase.CONTROLLER.value,
                action="session_ended",
                status=status,
                latency_ms=latency_ms,
                inputs_summary=summary,
                outputs_summary={
                    "duration_seconds": duration.total_seconds(),
                    "cycle_count": session["cycle_count"],
                    "event_count": len(session["events"])
                }
            )
            
            # Remove from active sessions
            del self.active_sessions[session_id]
        
        logger.info(f"Ended trace session {session_id} with status {status}")
    
    def start_cycle(self, session_id: str, cycle_number: int, goal_id: str) -> None:
        """
        Start a new recursion cycle.
        
        Args:
            session_id: Session identifier
            cycle_number: Cycle number (1-based)
            goal_id: Goal identifier
        """
        with self.session_lock:
            if session_id not in self.active_sessions:
                logger.warning(f"Session {session_id} not found")
                return
            
            session = self.active_sessions[session_id]
            session["cycle_count"] += 1
            trace_id = session["trace_id"]
        
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.CONTROLLER.value,
            action="cycle_started",
            status=TraceStatus.STARTED.value,
            cycle_number=cycle_number,
            goal_id=goal_id,
            inputs_summary={"cycle_number": cycle_number}
        )
        
        logger.debug(f"Started cycle {cycle_number} for session {session_id}")
    
    def log_event(
        self,
        trace_id: str,
        session_id: str,
        phase: str,
        action: str,
        status: str,
        cycle_number: Optional[int] = None,
        goal_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        evaluation_id: Optional[str] = None,
        promotion_id: Optional[str] = None,
        inputs_summary: Optional[Dict[str, Any]] = None,
        outputs_summary: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[str]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        projectx_judgment: Optional[str] = None,
        promotion_decision: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[int] = None
    ) -> None:
        """
        Log a trace event.
        
        Args:
            trace_id: Trace identifier
            session_id: Session identifier
            phase: Pipeline phase
            action: Action performed
            status: Action status
            cycle_number: Optional cycle number
            goal_id: Optional goal identifier
            prompt_id: Optional prompt identifier
            execution_id: Optional execution identifier
            evaluation_id: Optional evaluation identifier
            promotion_id: Optional promotion identifier
            inputs_summary: Optional inputs summary
            outputs_summary: Optional outputs summary
            artifacts: Optional list of artifacts
            error_code: Optional error code
            error_message: Optional error message
            projectx_judgment: Optional ProjectX judgment
            promotion_decision: Optional promotion decision
            metadata: Optional metadata
            latency_ms: Optional latency in milliseconds
        """
        # Create trace event
        event = TraceEvent(
            trace_id=trace_id,
            session_id=session_id,
            phase=phase,
            action=action,
            status=status,
            timestamp=datetime.utcnow().isoformat() + "Z",
            latency_ms=latency_ms,
            cycle_number=cycle_number,
            goal_id=goal_id,
            prompt_id=prompt_id,
            execution_id=execution_id,
            evaluation_id=evaluation_id,
            promotion_id=promotion_id,
            inputs_summary=inputs_summary or {},
            outputs_summary=outputs_summary or {},
            artifacts=artifacts or [],
            error_code=error_code,
            error_message=error_message,
            projectx_judgment=projectx_judgment,
            promotion_decision=promotion_decision,
            metadata=metadata or {}
        )
        
        # Add to session tracking
        with self.session_lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["events"].append(event)
        
        # Add to buffer for writing
        self.buffer.add(event)
        
        # Also log to console for important events
        if status == TraceStatus.FAILED.value or error_code:
            logger.error(f"Trace event: {phase}.{action} failed - {error_message}")
        elif status == TraceStatus.WARNING.value:
            logger.warning(f"Trace event: {phase}.{action} warning")
    
    def log_inventory(self, session_id: str, trace_id: str, inventory_result: Dict[str, Any]) -> None:
        """Log inventory phase event."""
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.INVENTORY.value,
            action="inventory_completed",
            status=TraceStatus.COMPLETED.value,
            inputs_summary={"directories_scanned": inventory_result.get("root_directories", [])},
            outputs_summary={
                "total_components": inventory_result.get("total_components", 0),
                "components_by_type": inventory_result.get("components_by_type", {})
            },
            artifacts=[inventory_result.get("inventory_path", "")]
        )
    
    def log_planning(self, session_id: str, trace_id: str, plan: Dict[str, Any]) -> None:
        """Log planning phase event."""
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.PLANNING.value,
            action="plan_created",
            status=TraceStatus.COMPLETED.value,
            inputs_summary={
                "goal": plan.get("goal", {}),
                "constraints": plan.get("constraints", {})
            },
            outputs_summary={
                "task_count": len(plan.get("tasks", [])),
                "estimated_duration": plan.get("estimated_duration", 0)
            },
            artifacts=[plan.get("plan_path", "")]
        )
    
    def log_prompting(self, session_id: str, trace_id: str, prompt: Dict[str, Any]) -> None:
        """Log prompting phase event."""
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.PROMPTING.value,
            action="prompt_generated",
            status=TraceStatus.COMPLETED.value,
            prompt_id=prompt.get("prompt_id"),
            inputs_summary={
                "task_summary": prompt.get("task_summary", ""),
                "execution_mode": prompt.get("execution_mode", "")
            },
            outputs_summary={
                "expected_artifacts": prompt.get("expected_artifacts", []),
                "max_recursion_depth": prompt.get("max_recursion_depth", 1)
            },
            artifacts=[prompt.get("prompt_path", "")]
        )
    
    def log_execution(self, session_id: str, trace_id: str, execution_result: Dict[str, Any]) -> None:
        """Log execution phase event."""
        status = TraceStatus.COMPLETED.value
        if execution_result.get("status") != "success":
            status = TraceStatus.FAILED.value
        
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.EXECUTION.value,
            action="execution_completed",
            status=status,
            execution_id=execution_result.get("execution_id"),
            prompt_id=execution_result.get("prompt_id"),
            inputs_summary={
                "execution_mode": execution_result.get("metadata", {}).get("execution_mode", "")
            },
            outputs_summary={
                "exit_code": execution_result.get("exit_code", -1),
                "artifacts_created": len(execution_result.get("artifacts_created", [])),
                "tests_passed": execution_result.get("tests_passed", 0),
                "tests_run": execution_result.get("tests_run", 0)
            },
            artifacts=execution_result.get("artifacts_created", []),
            error_code=execution_result.get("errors", [{}])[0].get("error_code") if execution_result.get("errors") else None,
            error_message=execution_result.get("errors", [{}])[0].get("error_message") if execution_result.get("errors") else None,
            latency_ms=execution_result.get("resource_usage", {}).get("cpu_time_seconds", 0) * 1000
        )
    
    def log_evaluation(self, session_id: str, trace_id: str, evaluation_result: Dict[str, Any]) -> None:
        """Log evaluation phase event."""
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.EVALUATION.value,
            action="evaluation_completed",
            status=TraceStatus.COMPLETED.value,
            evaluation_id=evaluation_result.get("evaluation_id"),
            execution_id=evaluation_result.get("execution_id"),
            inputs_summary={
                "gates_evaluated": len(evaluation_result.get("gate_results", []))
            },
            outputs_summary={
                "overall_score": evaluation_result.get("overall_score", 0.0),
                "passed_gates": evaluation_result.get("passed_gates", []),
                "failed_gates": evaluation_result.get("failed_gates", [])
            },
            promotion_decision=evaluation_result.get("promotion_recommendation")
        )
    
    def log_promotion(self, session_id: str, trace_id: str, promotion_result: Dict[str, Any]) -> None:
        """Log promotion phase event."""
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.PROMOTION.value,
            action="promotion_decided",
            status=TraceStatus.COMPLETED.value,
            promotion_id=promotion_result.get("promotion_id"),
            evaluation_id=promotion_result.get("evaluation_id"),
            inputs_summary={
                "artifacts_considered": len(promotion_result.get("artifacts_rejected", [])) + 
                                      len(promotion_result.get("artifacts_promoted", []))
            },
            outputs_summary={
                "artifacts_promoted": len(promotion_result.get("artifacts_promoted", [])),
                "artifacts_rejected": len(promotion_result.get("artifacts_rejected", []))
            },
            projectx_judgment=promotion_result.get("projectx_judgment"),
            promotion_decision=promotion_result.get("outcome")
        )
    
    def log_projectx_review(self, session_id: str, trace_id: str, judgment: str, reason: str) -> None:
        """Log ProjectX review event."""
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.INTEGRATION.value,
            action="projectx_review",
            status=TraceStatus.COMPLETED.value,
            inputs_summary={"review_type": "promotion"},
            outputs_summary={"judgment": judgment, "reason": reason},
            projectx_judgment=judgment
        )
    
    def log_mesh_bus_event(self, session_id: str, trace_id: str, channel: str, event: str, data: Dict[str, Any]) -> None:
        """Log Mesh Bus event."""
        self.log_event(
            trace_id=trace_id,
            session_id=session_id,
            phase=TracePhase.INTEGRATION.value,
            action=f"mesh_bus_{channel}",
            status=TraceStatus.INFO.value,
            inputs_summary={"channel": channel, "event": event},
            outputs_summary=data,
            metadata={"mesh_bus": True}
        )
    
    def get_session_traces(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all traces for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of trace events
        """
        with self.session_lock:
            if session_id in self.active_sessions:
                return [e.to_dict() for e in self.active_sessions[session_id]["events"]]
        
        # Try to read from disk
        return self._search_traces({"session_id": session_id})
    
    def search_traces(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search traces with filters.
        
        Args:
            filters: Dictionary of field filters
            limit: Maximum number of results
            
        Returns:
            List of matching trace events
        """
        return self._search_traces(filters, limit)
    
    def _search_traces(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Search trace files on disk."""
        results = []
        
        try:
            # Search current file
            if self.writer.current_file.exists():
                with open(self.writer.current_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                event = json.loads(line)
                                if self._matches_filters(event, filters):
                                    results.append(event)
                                    if len(results) >= limit:
                                        break
                            except json.JSONDecodeError:
                                continue
            
            # Search archived files (most recent first)
            archive_files = sorted(self.trace_dir.glob("traces_*.jsonl.gz"), reverse=True)
            
            for archive_file in archive_files:
                if len(results) >= limit:
                    break
                
                try:
                    with gzip.open(archive_file, 'rt') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    event = json.loads(line)
                                    if self._matches_filters(event, filters):
                                        results.append(event)
                                        if len(results) >= limit:
                                            break
                                except json.JSONDecodeError:
                                    continue
                except Exception as e:
                    logger.warning(f"Failed to read archive {archive_file}: {e}")
        
        except Exception as e:
            logger.error(f"Trace search failed: {e}")
        
        return results
    
    def _matches_filters(self, event: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if event matches all filters."""
        for key, value in filters.items():
            if key not in event:
                return False
            
            event_value = event[key]
            
            # Handle nested keys
            if '.' in key:
                parts = key.split('.')
                event_value = event
                for part in parts:
                    if isinstance(event_value, dict) and part in event_value:
                        event_value = event_value[part]
                    else:
                        return False
            
            # Compare values
            if isinstance(value, (list, tuple)):
                if event_value not in value:
                    return False
            elif event_value != value:
                return False
        
        return True
    
    def generate_session_report(self, session_id: str) -> Dict[str, Any]:
        """
        Generate a report for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session report
        """
        traces = self.get_session_traces(session_id)
        
        if not traces:
            return {"error": "Session not found"}
        
        # Calculate statistics
        phases = {}
        status_counts = {}
        total_latency = 0
        event_count = len(traces)
        
        for trace in traces:
            phase = trace.get("phase", "unknown")
            status = trace.get("status", "unknown")
            latency = trace.get("latency_ms", 0)
            
            phases[phase] = phases.get(phase, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1
            total_latency += latency
        
        # Find first and last event
        first_event = min(traces, key=lambda x: x.get("timestamp", ""))
        last_event = max(traces, key=lambda x: x.get("timestamp", ""))
        
        # Calculate duration
        try:
            start_time = datetime.fromisoformat(first_event["timestamp"].replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(last_event["timestamp"].replace("Z", "+00:00"))
            duration_seconds = (end_time - start_time).total_seconds()
        except:
            duration_seconds = 0
        
        # Find errors
        errors = [t for t in traces if t.get("status") == "failed" or t.get("error_code")]
        
        report = {
            "session_id": session_id,
            "trace_id": traces[0].get("trace_id") if traces else None,
            "event_count": event_count,
            "duration_seconds": duration_seconds,
            "average_latency_ms": total_latency / event_count if event_count > 0 else 0,
            "phase_distribution": phases,
            "status_distribution": status_counts,
            "error_count": len(errors),
            "errors": errors[:10],  # First 10 errors
            "first_event": first_event.get("timestamp"),
            "last_event": last_event.get("timestamp"),
            "promotion_decisions": [
                t for t in traces if t.get("promotion_decision")
            ],
            "projectx_judgments": [
                t for t in traces if t.get("projectx_judgment")
            ]
        }
        
        return report
    
    def shutdown(self) -> None:
        """Shutdown trace logger."""
        logger.info("Shutting down trace logger")
        self.writer.stop()
        self.writer.join(timeout=5.0)


# Example usage
if __name__ == "__main__":
    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "self_compiler_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    # Create trace logger
    trace_logger = TraceLogger(config["observability"])
    
    # Start a session
    session_id = "test_session_001"
    goal_id = "test_goal_001"
    trace_id = trace_logger.start_session(session_id, goal_id, {"test": True})
    
    # Log some events
    trace_logger.start_cycle(session_id, 1, goal_id)
    
    trace_logger.log_inventory(session_id, trace_id, {
        "root_directories": ["/test"],
        "total_components": 10,
        "components_by_type": {"python": 8, "config": 2},
        "inventory_path": "/tmp/inventory.json"
    })
    
    trace_logger.log_planning(session_id, trace_id, {
        "goal": "test goal",
        "constraints": {"time": 60},
        "tasks": ["task1", "task2"],
        "estimated_duration": 30,
        "plan_path": "/tmp/plan.json"
    })
    
    # Simulate some processing time
    time.sleep(0.1)
    
    # End session
    trace_logger.end_session(session_id, "completed", {"result": "success"})
    
    # Generate report
    report = trace_logger.generate_session_report(session_id)
    print(f"Session report: {json.dumps(report, indent=2)}")
    
    # Shutdown
    trace_logger.shutdown()