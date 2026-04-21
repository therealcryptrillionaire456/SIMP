#!/usr/bin/env python3
"""
Quantum Trace Logger for Stray Goose Quantum Mode

Implements structured tracing for quantum mode operations with:
- Consistent trace format
- Predictive risk scoring
- Learning signal emission
- Integration with ProjectX and Agent Lightning
"""

import json
import sys
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import asdict
from datetime import datetime
import hashlib

# Import schema
from quantum_mode_schema import (
    QuantumTrace, LearningSignal, PredictiveRiskScore,
    TraceStep, TraceStatus, QuantumErrorCode, Severity
)

class QuantumTraceLogger:
    """
    Structured trace logger for Quantum Mode.
    
    Implements the tracing requirements from the Quantum Mode specification:
    - 100% trace sampling for quantum mode
    - Structured trace format
    - Predictive risk scoring
    - Learning signal emission
    - Integration with learning systems
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        self.base_dir = Path(__file__).parent
        self.log_dir = log_dir or self.base_dir / "data" / "quantum_traces"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Session tracking
        self.session_id = self._generate_session_id()
        self.active_traces: Dict[str, QuantumTrace] = {}
        self.trace_history: List[Dict] = []
        
        # Statistics
        self.stats = {
            'traces_started': 0,
            'traces_completed': 0,
            'traces_failed': 0,
            'traces_escalated': 0,
            'traces_blocked': 0,
            'errors_by_code': {},
            'learning_signals': {'positive': 0, 'negative': 0, 'corrective': 0},
            'risk_scores': {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        }
        
        print(f"Quantum Trace Logger initialized")
        print(f"  Session ID: {self.session_id}")
        print(f"  Log directory: {self.log_dir}")
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        random_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        return f"session_{timestamp}_{random_hash}"
    
    def start_trace(self, task_id: str, step: str, 
                   parent_trace_id: Optional[str] = None,
                   **kwargs) -> QuantumTrace:
        """Start a new trace."""
        trace = QuantumTrace.create(task_id, step, TraceStatus.STARTED.value, parent_trace_id)
        trace.session_id = self.session_id
        
        # Update with additional fields
        for key, value in kwargs.items():
            if hasattr(trace, key):
                setattr(trace, key, value)
        
        # Store active trace
        self.active_traces[trace.trace_id] = trace
        self.stats['traces_started'] += 1
        
        # Log start
        self._log_trace(trace)
        
        return trace
    
    def update_trace(self, trace_id: str, **kwargs) -> Optional[QuantumTrace]:
        """Update an existing trace."""
        if trace_id not in self.active_traces:
            print(f"Warning: Trace {trace_id} not found in active traces")
            return None
        
        trace = self.active_traces[trace_id]
        trace.update(**kwargs)
        
        # Log update
        self._log_trace(trace)
        
        return trace
    
    def complete_trace(self, trace_id: str, status: str = TraceStatus.COMPLETED.value,
                      **kwargs) -> Optional[QuantumTrace]:
        """Complete a trace."""
        trace = self.update_trace(trace_id, status=status, **kwargs)
        if trace:
            # Update statistics
            self.stats['traces_completed'] += 1
            
            # Remove from active traces
            if trace_id in self.active_traces:
                del self.active_traces[trace_id]
            
            # Calculate final metrics if not provided
            if 'latency_ms' not in kwargs and trace.step == TraceStep.FINALIZE.value:
                # Calculate latency from start to finish
                start_time = datetime.fromisoformat(trace.timestamp.replace('Z', '+00:00'))
                end_time = datetime.utcnow()
                latency_ms = (end_time - start_time).total_seconds() * 1000
                trace.latency_ms = latency_ms
                
                # Calculate predictive risk score
                risk_score = self._calculate_predictive_risk(trace)
                trace.predictive_risk_score = risk_score.score
                
                # Log risk score
                self._log_risk_score(risk_score)
        
        return trace
    
    def fail_trace(self, trace_id: str, error_code: str, error_message: str,
                  severity: str = Severity.ERROR.value, **kwargs) -> Optional[QuantumTrace]:
        """Fail a trace with error information."""
        trace = self.update_trace(
            trace_id,
            status=TraceStatus.FAILED.value,
            error_code=error_code,
            severity=severity,
            notes=error_message,
            **kwargs
        )
        
        if trace:
            self.stats['traces_failed'] += 1
            self.stats['errors_by_code'][error_code] = \
                self.stats['errors_by_code'].get(error_code, 0) + 1
            
            # Emit negative learning signal for failure
            learning_signal = LearningSignal.negative(
                task_id=trace.task_id,
                trace_id=trace.trace_id,
                reason=f"Trace failed: {error_code} - {error_message}",
                value=-1.0,
                metadata={'error_code': error_code, 'severity': severity}
            )
            self._log_learning_signal(learning_signal)
        
        return trace
    
    def escalate_trace(self, trace_id: str, reason: str, **kwargs) -> Optional[QuantumTrace]:
        """Escalate a trace for human review."""
        trace = self.update_trace(
            trace_id,
            status=TraceStatus.ESCALATED.value,
            notes=reason,
            **kwargs
        )
        
        if trace:
            self.stats['traces_escalated'] += 1
            
            # Emit safe escalation learning signal
            learning_signal = LearningSignal.positive(
                task_id=trace.task_id,
                trace_id=trace.trace_id,
                reason=f"Safe escalation: {reason}",
                value=0.2,  # Safe escalation reward
                metadata={'escalation_reason': reason}
            )
            self._log_learning_signal(learning_signal)
        
        return trace
    
    def block_trace(self, trace_id: str, reason: str, **kwargs) -> Optional[QuantumTrace]:
        """Block a trace (safety decision)."""
        trace = self.update_trace(
            trace_id,
            status=TraceStatus.BLOCKED.value,
            notes=reason,
            **kwargs
        )
        
        if trace:
            self.stats['traces_blocked'] += 1
            
            # Emit positive learning signal for respecting safety
            learning_signal = LearningSignal.positive(
                task_id=trace.task_id,
                trace_id=trace.trace_id,
                reason=f"Safety block respected: {reason}",
                value=0.1,  # Safety block respected reward
                metadata={'block_reason': reason}
            )
            self._log_learning_signal(learning_signal)
        
        return trace
    
    def _calculate_predictive_risk(self, trace: QuantumTrace) -> PredictiveRiskScore:
        """Calculate predictive risk score for a trace."""
        factors = []
        
        # Check for risk factors
        if trace.retrieval_hits == 0:
            factors.append({'type': 'retrieval_empty', 'value': True})
        
        if trace.error_code:
            # Certain errors indicate higher risk
            high_risk_errors = [
                QuantumErrorCode.QMODE_RETRIEVAL_EMPTY.value,
                QuantumErrorCode.QMODE_FRAMEWORK_UNSUPPORTED.value,
                QuantumErrorCode.QMODE_IMPORT_FAILURE.value,
                QuantumErrorCode.QMODE_SIMULATOR_FAILURE.value,
                QuantumErrorCode.QMODE_LOGIC_FAILURE.value,
                QuantumErrorCode.QMODE_RESOURCE_LIMIT.value,
                QuantumErrorCode.QMODE_PROJECTX_BLOCK.value
            ]
            
            if trace.error_code in high_risk_errors:
                factors.append({'type': 'verification_failed', 'value': True})
        
        if trace.status == TraceStatus.ESCALATED.value:
            factors.append({'type': 'projectx_escalated', 'value': True})
        
        if trace.latency_ms and trace.latency_ms > 5000:  # 5 seconds
            factors.append({'type': 'high_latency', 'value': trace.latency_ms})
        
        # Check for repeated failures (simplified - would need history)
        # For now, just check if this trace itself failed
        if trace.status == TraceStatus.FAILED.value:
            factors.append({'type': 'repeated_failure', 'value': True})
        
        # Calculate risk score
        risk_score = PredictiveRiskScore.calculate(trace.task_id, trace.trace_id, factors)
        
        # Update statistics
        self.stats['risk_scores'][risk_score.risk_band] = \
            self.stats['risk_scores'].get(risk_score.risk_band, 0) + 1
        
        return risk_score
    
    def _log_trace(self, trace: QuantumTrace):
        """Log trace to file."""
        trace_dict = trace.to_dict()
        self.trace_history.append(trace_dict)
        
        # Save to individual trace file
        trace_file = self.log_dir / f"trace_{trace.trace_id}.json"
        with open(trace_file, 'w') as f:
            json.dump(trace_dict, f, indent=2)
        
        # Append to trace log
        log_file = self.log_dir / "traces_log.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(trace_dict) + '\n')
    
    def _log_learning_signal(self, signal: LearningSignal):
        """Log learning signal to file."""
        signal_dict = asdict(signal)
        
        # Update statistics
        signal_type = signal.signal_type
        if signal_type in self.stats['learning_signals']:
            self.stats['learning_signals'][signal_type] += 1
        
        # Save to learning signals file
        signals_file = self.log_dir / "learning_signals.jsonl"
        with open(signals_file, 'a') as f:
            f.write(json.dumps(signal_dict) + '\n')
        
        # Also save to individual file for easier analysis
        signal_file = self.log_dir / f"signal_{signal.signal_id}.json"
        with open(signal_file, 'w') as f:
            json.dump(signal_dict, f, indent=2)
    
    def _log_risk_score(self, risk_score: PredictiveRiskScore):
        """Log risk score to file."""
        risk_dict = asdict(risk_score)
        
        # Save to risk scores file
        risks_file = self.log_dir / "risk_scores.jsonl"
        with open(risks_file, 'a') as f:
            f.write(json.dumps(risk_dict) + '\n')
    
    def get_trace_summary(self, trace_id: str) -> Optional[Dict]:
        """Get summary of a trace."""
        # Look in active traces first
        if trace_id in self.active_traces:
            trace = self.active_traces[trace_id]
            return {
                'trace_id': trace.trace_id,
                'task_id': trace.task_id,
                'step': trace.step,
                'status': trace.status,
                'active': True,
                'timestamp': trace.timestamp
            }
        
        # Look in trace history
        for trace in self.trace_history:
            if trace['trace_id'] == trace_id:
                return {
                    'trace_id': trace['trace_id'],
                    'task_id': trace['task_id'],
                    'step': trace['step'],
                    'status': trace['status'],
                    'active': False,
                    'timestamp': trace['timestamp']
                }
        
        return None
    
    def get_session_metrics(self) -> Dict:
        """Get metrics for current session."""
        # Calculate rates
        total_traces = self.stats['traces_started']
        
        metrics = {
            'session_id': self.session_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'trace_counts': self.stats,
            'rates': {
                'completion_rate': self.stats['traces_completed'] / total_traces if total_traces > 0 else 0,
                'failure_rate': self.stats['traces_failed'] / total_traces if total_traces > 0 else 0,
                'escalation_rate': self.stats['traces_escalated'] / total_traces if total_traces > 0 else 0,
                'block_rate': self.stats['traces_blocked'] / total_traces if total_traces > 0 else 0
            },
            'learning_signals': self.stats['learning_signals'],
            'risk_distribution': self.stats['risk_scores'],
            'top_errors': sorted(
                self.stats['errors_by_code'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
        
        return metrics
    
    def export_training_data(self, output_dir: Optional[Path] = None) -> Dict:
        """Export traces as training data for ProjectX/Agent Lightning."""
        export_dir = output_dir or self.log_dir / "training_export"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        training_data = []
        
        # Group traces by task
        tasks = {}
        for trace in self.trace_history:
            task_id = trace['task_id']
            if task_id not in tasks:
                tasks[task_id] = []
            tasks[task_id].append(trace)
        
        # Create training examples
        for task_id, task_traces in tasks.items():
            # Sort traces by timestamp
            task_traces.sort(key=lambda x: x['timestamp'])
            
            # Find final trace
            final_trace = None
            for trace in reversed(task_traces):
                if trace['step'] == TraceStep.FINALIZE.value:
                    final_trace = trace
                    break
            
            if not final_trace:
                continue
            
            # Create training example
            example = {
                'task_id': task_id,
                'traces': task_traces,
                'outcome': {
                    'status': final_trace['status'],
                    'verification_status': final_trace.get('verification_status'),
                    'error_code': final_trace.get('error_code'),
                    'predictive_risk_score': final_trace.get('predictive_risk_score'),
                    'reward': final_trace.get('reward')
                },
                'metadata': {
                    'export_timestamp': datetime.utcnow().isoformat() + 'Z',
                    'trace_count': len(task_traces),
                    'session_id': self.session_id
                }
            }
            
            training_data.append(example)
            
            # Save individual example
            example_file = export_dir / f"training_{task_id}.json"
            with open(example_file, 'w') as f:
                json.dump(example, f, indent=2)
        
        # Save all training data
        training_file = export_dir / "training_data.json"
        with open(training_file, 'w') as f:
            json.dump(training_data, f, indent=2)
        
        return {
            'export_dir': str(export_dir),
            'examples_exported': len(training_data),
            'training_file': str(training_file)
        }
    
    def cleanup_old_traces(self, days_old: int = 7):
        """Clean up trace files older than specified days."""
        import time
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(days=days_old)
        
        files_removed = 0
        for file in self.log_dir.glob("*.json"):
            if file.name.startswith("trace_") or file.name.startswith("signal_"):
                file_time = datetime.fromtimestamp(file.stat().st_mtime)
                if file_time < cutoff_time:
                    file.unlink()
                    files_removed += 1
        
        print(f"Cleaned up {files_removed} trace files older than {days_old} days")

def test_trace_logger():
    """Test the trace logger."""
    logger = QuantumTraceLogger()
    
    print("Testing Quantum Trace Logger")
    print("="*60)
    
    # Test 1: Start and complete a trace
    task_id = "test_task_001"
    trace = logger.start_trace(
        task_id,
        TraceStep.DETECTION.value,
        algorithm_family="bell_state",
        framework_requested="qiskit"
    )
    
    print(f"1. Started trace: {trace.trace_id}")
    print(f"   Task: {trace.task_id}, Step: {trace.step}")
    
    # Test 2: Update trace
    trace = logger.update_trace(
        trace.trace_id,
        step=TraceStep.RETRIEVAL.value,
        retrieval_hits=2,
        retrieval_ids=["bell_state_001", "bell_state_002"]
    )
    
    print(f"2. Updated trace: {trace.trace_id}")
    print(f"   Retrieval hits: {trace.retrieval_hits}")
    
    # Test 3: Complete trace successfully
    trace = logger.complete_trace(
        trace.trace_id,
        TraceStatus.COMPLETED.value,
        step=TraceStep.FINALIZE.value,
        verification_status="VERIFIED",
        reward=1.0
    )
    
    print(f"3. Completed trace: {trace.trace_id}")
    print(f"   Status: {trace.status}, Reward: {trace.reward}")
    
    # Test 4: Trace with failure
    task_id_2 = "test_task_002"
    trace2 = logger.start_trace(task_id_2, TraceStep.DETECTION.value)
    
    trace2 = logger.fail_trace(
        trace2.trace_id,
        error_code="QMODE_RETRIEVAL_EMPTY",
        error_message="No examples found for query",
        severity=Severity.MEDIUM.value
    )
    
    print(f"4. Failed trace: {trace2.trace_id}")
    print(f"   Error: {trace2.error_code}, Severity: {trace2.severity}")
    
    # Test 5: Get metrics
    metrics = logger.get_session_metrics()
    print(f"\n5. Session Metrics:")
    print(f"   Total traces: {metrics['trace_counts']['traces_started']}")
    print(f"   Completed: {metrics['trace_counts']['traces_completed']}")
    print(f"   Failed: {metrics['trace_counts']['traces_failed']}")
    print(f"   Learning signals: {metrics['learning_signals']}")
    
    # Test 6: Export training data
    export_result = logger.export_training_data()
    print(f"\n6. Training Data Export:")
    print(f"   Examples exported: {export_result['examples_exported']}")
    print(f"   Export directory: {export_result['export_dir']}")
    
    print("\n" + "="*60)
    print("Trace Logger Test Complete")
    print("="*60)

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Quantum Trace Logger')
    parser.add_argument('--test', action='store_true', help='Run tests')
    parser.add_argument('--metrics', action='store_true', help='Show metrics')
    parser.add_argument('--export', action='store_true', help='Export training data')
    parser.add_argument('--cleanup', type=int, help='Cleanup files older than N days')
    parser.add_argument('--log-dir', type=Path, help='Custom log directory')
    
    args = parser.parse_args()
    
    logger = QuantumTraceLogger(args.log_dir)
    
    if args.test:
        test_trace_logger()
    
    elif args.metrics:
        metrics = logger.get_session_metrics()
        print("Quantum Trace Logger Metrics:")
        print(json.dumps(metrics, indent=2))
    
    elif args.export:
        result = logger.export_training_data()
        print("Training Data Export Complete:")
        print(json.dumps(result, indent=2))
    
    elif args.cleanup:
        logger.cleanup_old_traces(args.cleanup)
        print(f"Cleaned up files older than {args.cleanup} days")
    
    else:
        print("Quantum Trace Logger")
        print("\nUsage:")
        print("  --test      Run tests")
        print("  --metrics   Show metrics")
        print("  --export    Export training data")
        print("  --cleanup N Cleanup files older than N days")
        print("  --log-dir   Custom log directory")

if __name__ == '__main__':
    main()