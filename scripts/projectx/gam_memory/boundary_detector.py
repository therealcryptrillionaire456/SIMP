"""
GAM Boundary Detector — Phase 7

Semantic closure detection for the event graph. Identifies when an episode
has reached a natural boundary and should be consolidated.

Triggers on:
  - Task completion (explicit signal or detected)
  - Role change in agent execution
  - Topic drift threshold (semantic distance exceeds limit)
  - New context injection (explicit trigger)

Methods:
  - Embedding distance: cosine similarity between recent nodes and current focus
  - Trace_id clustering: nodes with same trace_id form natural episodes
  - Confidence scoring: when confidence stabilizes, consider closure
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .event_buffer import EventBuffer, GAMEdge, GAMEdge, GAMNode, NodeType

logger = logging.getLogger(__name__)


class BoundaryTrigger(str, Enum):
    """Types of boundary detection triggers."""
    TASK_COMPLETE = "task_complete"
    ROLE_CHANGE = "role_change"
    TOPIC_DRIFT = "topic_drift"
    NEW_CONTEXT = "new_context"
    TIME_THRESHOLD = "time_threshold"
    CONFIDENCE_STABILIZED = "confidence_stabilized"


@dataclass
class BoundaryEvent:
    """A detected boundary in the event stream."""
    trigger: BoundaryTrigger
    trace_id: str
    summary_nodes: List[str]  # Node IDs that form the episode
    confidence: float
    explanation: str
    detected_at: float = field(default_factory=time.time)


@dataclass
class ClosureCandidate:
    """An episode that may be ready for consolidation."""
    trace_id: str
    nodes: List[GAMNode]
    edges: List[GAMEdge]
    avg_confidence: float
    node_count: int
    is_complete: bool
    trigger_hints: List[BoundaryTrigger]


class BoundaryDetector:
    """
    Detects semantic boundaries in the event graph to trigger consolidation.

    The detector monitors the event buffer for natural episode boundaries.
    When detected, it emits BoundaryEvent signals that the consolidator
    can process.

    Example::

        detector = BoundaryDetector(event_buffer)
        detector.start()
        for event in detector.watch():
            # process boundary event
    """

    def __init__(
        self,
        event_buffer: EventBuffer,
        topic_drift_threshold: float = 0.35,
        confidence_stability_window: int = 5,
        confidence_stability_delta: float = 0.05,
        time_threshold_seconds: float = 600.0,
        check_interval: float = 5.0,
    ) -> None:
        self._buf = event_buffer
        self._topic_drift_threshold = topic_drift_threshold
        self._confidence_window = confidence_stability_window
        self._confidence_delta = confidence_stability_delta
        self._time_threshold = time_threshold_seconds
        self._check_interval = check_interval

        self._callbacks: List[Callable[[BoundaryEvent], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Tracking state per trace
        self._last_topic: Dict[str, Optional[List[float]]] = {}
        self._confidence_history: Dict[str, List[float]] = {}
        self._last_boundary: Dict[str, float] = {}  # trace_id → last boundary ts

    # ── Public API ─────────────────────────────────────────────────────────

    def register_callback(self, callback: Callable[[BoundaryEvent], None]) -> None:
        """Register a callback to receive boundary events."""
        self._callbacks.append(callback)

    def start(self) -> None:
        """Start background boundary detection."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="GAMBoundary")
        self._thread.start()
        logger.info("BoundaryDetector started")

    def stop(self) -> None:
        """Stop background detection."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("BoundaryDetector stopped")

    def watch(self) -> BoundaryEvent:
        """
        Generator that yields boundary events.
        Use this in a loop or with a coroutine consumer.
        """
        return self._boundary_queue()

    def check_now(self, trace_id: Optional[str] = None) -> List[BoundaryEvent]:
        """
        Run a synchronous boundary check. Returns any detected boundaries.
        If trace_id is provided, only check that trace.
        """
        events: List[BoundaryEvent] = []

        if trace_id:
            nodes = self._buf.get_trace_nodes(trace_id)
            event = self._check_trace(trace_id, nodes)
            if event:
                events.append(event)
        else:
            for tid in list(self._last_topic.keys()):
                nodes = self._buf.get_trace_nodes(tid)
                event = self._check_trace(tid, nodes)
                if event:
                    events.append(event)

        return events

    def detect_closure(
        self,
        trace_id: str,
        force: bool = False,
    ) -> Optional[ClosureCandidate]:
        """
        Determine if a trace is ready for consolidation.
        
        Returns a ClosureCandidate if ready, None otherwise.
        """
        nodes = self._buf.get_trace_nodes(trace_id)
        if not nodes:
            return None

        edges = []
        for n in nodes:
            edges.extend(self._buf.get_outgoing(n.node_id))

        avg_conf = sum(n.confidence for n in nodes) / len(nodes) if nodes else 0.0
        is_complete = self._is_task_complete(nodes)
        triggers = self._detect_triggers(nodes)

        # If force=True or sufficient signals, return candidate
        if force or is_complete or len(triggers) >= 2:
            return ClosureCandidate(
                trace_id=trace_id,
                nodes=nodes,
                edges=edges,
                avg_confidence=avg_conf,
                node_count=len(nodes),
                is_complete=is_complete,
                trigger_hints=triggers,
            )

        # Time-based or single trigger might still qualify
        first_node = min(nodes, key=lambda n: n.created_at)
        last_node = max(nodes, key=lambda n: n.created_at)
        duration = last_node.created_at - first_node.created_at
        if duration > self._time_threshold and len(nodes) >= 3:
            return ClosureCandidate(
                trace_id=trace_id,
                nodes=nodes,
                edges=edges,
                avg_confidence=avg_conf,
                node_count=len(nodes),
                is_complete=False,
                trigger_hints=[BoundaryTrigger.TIME_THRESHOLD],
            )

        return None

    # ── Internal Detection Methods ─────────────────────────────────────────

    def _check_trace(self, trace_id: str, nodes: List[GAMNode]) -> Optional[BoundaryEvent]:
        """Check a single trace for boundary conditions."""
        if len(nodes) < 2:
            return None

        triggers: List[BoundaryTrigger] = []
        summary_ids: List[str] = []

        # 1. Task completion check
        if self._is_task_complete(nodes):
            triggers.append(BoundaryTrigger.TASK_COMPLETE)

        # 2. Role change detection
        role_changes = self._detect_role_changes(nodes)
        if role_changes:
            triggers.append(BoundaryTrigger.ROLE_CHANGE)

        # 3. Topic drift detection
        drift = self._compute_topic_drift(trace_id, nodes)
        if drift > self._topic_drift_threshold:
            triggers.append(BoundaryTrigger.TOPIC_DRIFT)

        # 4. Confidence stabilization
        if self._is_confidence_stable(trace_id):
            triggers.append(BoundaryTrigger.CONFIDENCE_STABILIZED)

        # 5. Time threshold
        first_node = min(nodes, key=lambda n: n.created_at)
        last_node = max(nodes, key=lambda n: n.created_at)
        if last_node.created_at - first_node.created_at > self._time_threshold:
            triggers.append(BoundaryTrigger.TIME_THRESHOLD)

        if not triggers:
            return None

        # Build summary: include key decision nodes
        summary_ids = self._select_summary_nodes(nodes)

        avg_conf = sum(n.confidence for n in nodes) / len(nodes)
        explanation = self._build_explanation(triggers, nodes)

        # Update tracking
        self._last_boundary[trace_id] = time.time()
        if nodes:
            last_node = max(nodes, key=lambda n: n.created_at)
            self._last_topic[trace_id] = last_node.embedding

        return BoundaryEvent(
            trigger=triggers[0],  # Primary trigger
            trace_id=trace_id,
            summary_nodes=summary_ids,
            confidence=avg_conf,
            explanation=explanation,
        )

    def _is_task_complete(self, nodes: List[GAMNode]) -> bool:
        """Detect task completion signals from node content."""
        completion_signals = [
            "done", "complete", "finished", "success", "deployed",
            "merged", "resolved", "implemented", "ready",
        ]
        # Look for explicit completion markers
        for node in nodes:
            content_lower = node.content.lower()
            if any(signal in content_lower for signal in completion_signals):
                return True
            # Check metadata for completion flags
            if node.metadata.get("status") in ("complete", "success", "done"):
                return True
        return False

    def _detect_role_changes(self, nodes: List[GAMNode]) -> List[Tuple[int, str, str]]:
        """Detect role transitions in the node sequence."""
        changes = []
        last_role = None
        for i, node in enumerate(nodes):
            if node.role and last_role and node.role != last_role:
                changes.append((i, last_role, node.role))
            if node.role:
                last_role = node.role
        return changes

    def _compute_topic_drift(self, trace_id: str, nodes: List[GAMNode]) -> float:
        """Compute semantic drift from last checkpoint to current focus."""
        if len(nodes) < 2:
            return 0.0

        current_topic = nodes[-1].embedding
        if current_topic is None:
            return 0.0

        # Compare against last recorded topic
        last_topic = self._last_topic.get(trace_id)
        if last_topic is None:
            # First check: compare first vs last node
            first_topic = nodes[0].embedding
            if first_topic is None:
                return 0.0
            return 1.0 - self._cosine_sim(first_topic, current_topic)

        # Compute drift from last boundary
        return 1.0 - self._cosine_sim(last_topic, current_topic)

    def _is_confidence_stable(self, trace_id: str) -> bool:
        """Check if confidence has stabilized over recent nodes."""
        history = self._confidence_history.get(trace_id, [])
        if len(history) < self._confidence_window:
            return False

        recent = history[-self._confidence_window:]
        max_delta = max(abs(recent[i] - recent[i - 1]) for i in range(1, len(recent)))
        return max_delta < self._confidence_delta

    def _detect_triggers(self, nodes: List[GAMNode]) -> List[BoundaryTrigger]:
        """Detect all applicable triggers for the given nodes."""
        triggers: List[BoundaryTrigger] = []

        if self._is_task_complete(nodes):
            triggers.append(BoundaryTrigger.TASK_COMPLETE)

        if self._detect_role_changes(nodes):
            triggers.append(BoundaryTrigger.ROLE_CHANGE)

        for node in nodes:
            if node.metadata.get("new_context"):
                triggers.append(BoundaryTrigger.NEW_CONTEXT)
                break

        return triggers

    def _select_summary_nodes(self, nodes: List[GAMNode]) -> List[str]:
        """Select representative nodes to summarize the episode."""
        if not nodes:
            return []

        # Include: first node, last node, highest confidence nodes, role-change nodes
        selected: Set[str] = {nodes[0].node_id, nodes[-1].node_id}

        # Add high-confidence nodes
        sorted_by_conf = sorted(nodes, key=lambda n: n.confidence, reverse=True)
        for n in sorted_by_conf[:max(1, len(nodes) // 3)]:
            selected.add(n.node_id)

        # Add role-change boundary nodes
        for i, (idx, old_role, new_role) in enumerate(self._detect_role_changes(nodes)):
            if idx < len(nodes):
                selected.add(nodes[idx].node_id)

        return list(selected)

    def _build_explanation(self, triggers: List[BoundaryTrigger], nodes: List[GAMNode]) -> str:
        """Generate a human-readable explanation of the boundary."""
        parts = [f"Episode with {len(nodes)} nodes ended due to:"]
        for t in triggers:
            parts.append(f"  - {t.value}")

        # Add context
        if nodes:
            first = nodes[0]
            last = nodes[-1]
            parts.append(f"  Duration: {last.created_at - first.created_at:.1f}s")

        return "\n".join(parts)

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        ma = math.sqrt(sum(x * x for x in a)) or 1e-9
        mb = math.sqrt(sum(x * x for x in b)) or 1e-9
        return dot / (ma * mb)

    def _boundary_queue(self) -> BoundaryEvent:
        """Blocking generator for boundary events."""
        while self._running:
            self._stop_event.wait(timeout=self._check_interval)
            if not self._running:
                break

            # Check all active traces
            for tid in list(self._last_topic.keys()):
                nodes = self._buf.get_trace_nodes(tid)
                event = self._check_trace(tid, nodes)
                if event:
                    yield event

    def _run(self) -> None:
        """Background loop for continuous boundary detection."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._check_interval)
            if self._stop_event.is_set():
                break

            # Check all active traces
            for tid in list(self._last_topic.keys()):
                nodes = self._buf.get_trace_nodes(tid)
                event = self._check_trace(tid, nodes)
                if event:
                    self._emit(event)

            # Also check for new traces not yet tracked
            for node in self._buf._nodes.values():
                if node.trace_id and node.trace_id not in self._last_topic:
                    self._last_topic[node.trace_id] = node.embedding

    def _emit(self, event: BoundaryEvent) -> None:
        """Emit a boundary event to all callbacks."""
        logger.debug("Boundary detected: %s for trace %s", event.trigger, event.trace_id)
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as exc:
                logger.warning("Boundary callback failed: %s", exc)

    def get_stats(self) -> Dict[str, Any]:
        """Return detector statistics."""
        return {
            "running": self._running,
            "tracked_traces": len(self._last_topic),
            "confidence_history": {k: len(v) for k, v in self._confidence_history.items()},
            "last_boundaries": self._last_boundary,
        }
