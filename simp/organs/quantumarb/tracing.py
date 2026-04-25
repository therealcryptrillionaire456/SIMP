"""
Distributed Tracing — T27
==========================
W3C TraceContext-compatible tracing for quantumarb execution paths.
No external dependencies — pure Python.

Provides span creation, propagation, HTTP header injection,
JSONL export, and dashboard data.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("tracing")

_trace_ctx: Optional["TraceContext"] = None
_trace_lock = threading.Lock()
_active_spans: List["Span"] = []
_span_stack: List["Span"] = []


@dataclass
class Span:
    """Represents a single span in a distributed trace."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    service: str = "quantumarb"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "OK"

    def duration_ms(self) -> float:
        """Calculate span duration in milliseconds."""
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000


@dataclass
class TraceContext:
    """W3C TraceContext-compatible trace context."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    sampled: bool = True

    def to_headers(self) -> Dict[str, str]:
        """
        Convert trace context to HTTP headers (W3C TraceContext format).
        
        Returns
        -------
        Dict[str, str]
            Headers with traceparent and tracestate.
        """
        # W3C traceparent = 00-{trace-id}-{parent-id}-{trace-flags}
        #   parent-id = span_id of the CALLING span (our parent) or "-" (no parent)
        #   trace-flags = "01" (sampled) or "00" (not sampled)
        parent = f"{self.parent_span_id}" if self.parent_span_id else "-"
        trace_flags = "01" if self.sampled else "00"
        return {
            "traceparent": f"00-{self.trace_id}-{parent}-{trace_flags}",
            "tracestate": f"sampled={int(self.sampled)}",
        }

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> Optional["TraceContext"]:
        """
        Extract trace context from HTTP headers (W3C TraceContext format).
        
        Parameters
        ----------
        headers : Dict[str, str]
            HTTP headers containing traceparent.
            
        Returns
        -------
        Optional[TraceContext]
            Trace context or None if headers are invalid.
        """
        tp = headers.get("traceparent", "")
        if not tp or not tp.startswith("00-"):
            return None
        parts = tp.split("-")
        if len(parts) < 4:
            return None
        trace_id, span_id = parts[1], parts[2]
        # Validate trace-id (32 hex chars) and span-id (16 hex chars) per W3C spec
        if len(trace_id) != 32 or not all(c in '0123456789abcdefABCDEF' for c in trace_id):
            return None
        if len(span_id) != 16 or not all(c in '0123456789abcdefABCDEF' for c in span_id):
            return None
        # W3C TraceContext version 00 format:
        # traceparent = 00-{trace-id}-{parent-id}-{trace-flags}
        #   version    = "00"         = parts[0]
        #   trace-id   = 32 hex chars = parts[1]
        #   parent-id  = 16 hex chars or "-" (no parent) = parts[2]
        #   trace-flags = 2 hex chars (bit 0 = sampled)    = parts[3]
        if len(parts) != 4:
            return None
        parent_id_raw = parts[2]
        trace_flags_raw = parts[3]

        if parent_id_raw == "-":
            parent = None
        elif len(parent_id_raw) == 16 and all(c in '0123456789abcdefABCDEF' for c in parent_id_raw):
            parent = parent_id_raw
        else:
            return None  # invalid parent-id format

        # trace-flags: bit 0 = sampled (0x01)
        sampled = bool(int(trace_flags_raw, 16) & 1) if trace_flags_raw else True
        ts = headers.get("tracestate", "")
        if "sampled=0" in ts:
            sampled = False
        return cls(trace_id=trace_id, span_id=span_id, parent_span_id=parent, sampled=sampled)


class QuantumArbTracer:
    """
    Distributed tracer for quantumarb execution paths.
    
    Thread-safe singleton implementation with JSONL export.
    Disabled by default; enable with TRACE=1 environment variable.
    Auto-flushes at 10,000 spans.
    """
    _instance: Optional["QuantumArbTracer"] = None
    _MAX_SPANS = 10_000

    def __init__(self, service_name: str = "quantumarb"):
        """
        Initialize the tracer.
        
        Parameters
        ----------
        service_name : str
            Name of the service being traced.
        """
        self.service_name = service_name
        self._spans: List[Span] = []
        self._lock = threading.Lock()
        self._trace_dir = Path("data/traces")
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        self._enabled = os.environ.get("TRACE", "0") == "1"

    @classmethod
    def get_instance(cls) -> "QuantumArbTracer":
        """
        Get or create the singleton tracer instance.
        
        Returns
        -------
        QuantumArbTracer
            The singleton tracer instance.
        """
        global _trace_ctx
        with _trace_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _new_trace_id(self) -> str:
        """
        Generate a new 32-character hex trace ID.
        
        Returns
        -------
        str
            32-character hex string.
        """
        return uuid.uuid4().hex[:32]

    def _new_span_id(self) -> str:
        """
        Generate a new 16-character hex span ID.
        
        Returns
        -------
        str
            16-character hex string.
        """
        return uuid.uuid4().hex[:16]

    def start_span(
        self,
        name: str,
        parent: Optional[TraceContext] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceContext:
        """
        Start a new span.
        
        Parameters
        ----------
        name : str
            Name of the span.
        parent : Optional[TraceContext]
            Parent context for nested spans.
        attributes : Optional[Dict[str, Any]]
            Initial attributes for the span.
            
        Returns
        -------
        TraceContext
            Context for the created span.
        """
        trace_id = parent.trace_id if parent else self._new_trace_id()
        span_id = self._new_span_id()
        parent_id = parent.span_id if parent else None

        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            name=name,
            attributes=attributes or {},
        )
        with self._lock:
            _active_spans.append(span)
            _span_stack.append(span)

        return TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
        )

    def end_span(self, ctx: TraceContext, status: str = "OK") -> None:
        """
        End a span.
        
        Parameters
        ----------
        ctx : TraceContext
            Context of the span to end.
        status : str
            Status code ("OK", "ERROR", "NO_GO", "GO", "REVIEW").
        """
        with self._lock:
            for span in reversed(_span_stack):
                if span.span_id == ctx.span_id:
                    span.end_time = time.time()
                    span.status = status
                    _active_spans.remove(span)
                    _span_stack.remove(span)
                    self._spans.append(span)
                    break

            if len(self._spans) >= self._MAX_SPANS:
                self._flush()

    def add_event(
        self,
        ctx: TraceContext,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add an event to a span.
        
        Parameters
        ----------
        ctx : TraceContext
            Context of the span.
        name : str
            Event name.
        attributes : Optional[Dict[str, Any]]
            Event attributes.
        """
        with self._lock:
            for span in _span_stack:
                if span.span_id == ctx.span_id:
                    span.events.append({
                        "name": name,
                        "ts": time.time(),
                        "attributes": attributes or {},
                    })
                    break

    def set_attribute(self, ctx: TraceContext, key: str, value: Any) -> None:
        """
        Set an attribute on a span.
        
        Parameters
        ----------
        ctx : TraceContext
            Context of the span.
        key : str
            Attribute key.
        value : Any
            Attribute value.
        """
        with self._lock:
            for span in _span_stack:
                if span.span_id == ctx.span_id:
                    span.attributes[key] = value
                    break

    def _flush(self) -> None:
        """Flush spans to disk as JSONL files."""
        if not self._spans:
            return

        traces: Dict[str, List] = {}
        for span in self._spans:
            traces.setdefault(span.trace_id, []).append(asdict(span))

        for tid, spans in traces.items():
            out_file = self._trace_dir / f"{tid}.jsonl"
            try:
                with open(out_file, "a") as f:
                    for s in spans:
                        f.write(json.dumps(s) + "\n")
            except Exception as e:
                log.warning("Trace flush error: %s", e)

        with self._lock:
            self._spans.clear()

    def get_recent_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent trace summaries.
        
        Parameters
        ----------
        limit : int
            Maximum number of traces to return.
            
        Returns
        -------
        List[Dict[str, Any]]
            List of trace summaries.
        """
        files = sorted(
            self._trace_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]

        traces = []
        for f in files:
            trace_id = f.stem
            try:
                spans = []
                with open(f) as fh:
                    for line in fh:
                        spans.append(json.loads(line.strip()))
                if spans:
                    total_ms = sum(
                        (s.get("end_time", 0) - s.get("start_time", 0)) * 1000
                        for s in spans
                    )
                    traces.append({
                        "trace_id": trace_id,
                        "span_count": len(spans),
                        "total_ms": round(total_ms, 2),
                        "root_span": spans[0].get("name", "?"),
                    })
            except Exception:
                pass
        return traces

    def inject_headers(self, ctx: TraceContext) -> Dict[str, str]:
        """
        Inject trace context into HTTP headers.
        
        Parameters
        ----------
        ctx : TraceContext
            Trace context to inject.
            
        Returns
        -------
        Dict[str, str]
            HTTP headers.
        """
        return ctx.to_headers()

    def extract_headers(self, headers: Dict[str, str]) -> Optional[TraceContext]:
        """
        Extract trace context from HTTP headers.
        
        Parameters
        ----------
        headers : Dict[str, str]
            HTTP headers.
            
        Returns
        -------
        Optional[TraceContext]
            Extracted context or None.
        """
        return TraceContext.from_headers(headers)

    def is_enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable tracing."""
        self._enabled = True

    def disable(self) -> None:
        """Disable tracing."""
        self._enabled = False


def trace(span_name: str) -> Callable:
    """
    Decorator to trace a function.
    
    Parameters
    ----------
    span_name : str
        Name for the span.
        
    Returns
    -------
    Callable
        Decorated function.
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            tracer = QuantumArbTracer.get_instance()
            if not tracer._enabled:
                return fn(*args, **kwargs)
            ctx = tracer.start_span(span_name)
            try:
                result = fn(*args, **kwargs)
                tracer.end_span(ctx, "OK")
                return result
            except Exception as e:
                tracer.add_event(ctx, "error", {"exception": str(e)})
                tracer.end_span(ctx, "ERROR")
                raise
        return wrapper
    return decorator


def reset_tracer() -> None:
    """Reset the singleton tracer instance (for testing)."""
    global _active_spans, _span_stack
    QuantumArbTracer._instance = None
    with _trace_lock:
        _active_spans.clear()
        _span_stack.clear()
