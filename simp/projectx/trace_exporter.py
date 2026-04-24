"""
ProjectX Trace Exporter — Step 11

Lightweight OpenTelemetry bridge that reads trace events from JSONL trace
directories and converts them to OpenTelemetry spans (or in-memory spans
when OTel is not installed).

Features:
  - TraceExporter: reads JSONL trace files, converts to spans
  - Lazy OTel imports — works WITHOUT opentelemetry installed
  - In-memory Span dataclass for no-OTel fallback
  - File export fallback writes spans to JSONL
  - Jaeger/Tempo OTLP export when opentelemetry is available
  - Thread safety with threading.Lock()
  - Module-level get_trace_exporter() singleton
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy OTel imports — no crash if not installed
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider as OTelTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    logger.debug("opentelemetry not installed — using in-memory span fallback")


def _otel_available() -> bool:
    """Check if OTel is available AND we've verified a working connection.

    Returns False if OTel imports exist but we've already failed to connect.
    """
    if not _OTEL_AVAILABLE:
        return False
    try:
        # Quick connectivity check — don't crash if Jaeger/Tempo isn't up
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        result = s.connect_ex(("localhost", 4318))
        s.close()
        return result == 0
    except Exception:
        return False

_OTEL_LOCK = threading.Lock()

# Default trace directory
_DEFAULT_TRACE_DIR = Path("traces")
_DEFAULT_EXPORT_DIR = Path("projectx_logs/traces/export")

# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class Span:
    """In-memory span representation — used when OTel is not available."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str = "unknown"
    kind: str = "INTERNAL"
    status: str = "OK"
    start_time: str = ""
    end_time: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_trace_event(cls, event: Dict[str, Any]) -> "Span":
        """Convert a JSONL trace event dict into a Span."""
        trace_id = event.get("trace_id", str(uuid.uuid4()))
        span_id = str(uuid.uuid4())
        parent_span_id = event.get("parent_trace_id")
        name = event.get("action", event.get("step", "unknown"))
        kind = "INTERNAL"
        status = "OK" if event.get("status") in ("completed", "started") else "ERROR"
        start_time = event.get("timestamp", datetime.now(timezone.utc).isoformat())
        end_time = event.get("end_timestamp") if event.get("status") == "completed" else None

        # Flatten event fields into attributes
        attributes: Dict[str, Any] = {}
        for key in ("session_id", "phase", "cycle_number", "goal_id",
                     "prompt_id", "execution_id", "task_id", "retrieval_hits",
                     "algorithm_family", "framework_requested", "verification_status",
                     "error_code", "severity", "reward", "latency_ms",
                     "projectx_judgment", "promotion_decision"):
            val = event.get(key)
            if val is not None:
                attributes[key] = val

        # Include inputs/outputs summary if present
        if event.get("inputs_summary"):
            attributes["inputs_summary"] = json.dumps(event["inputs_summary"], default=str)
        if event.get("outputs_summary"):
            attributes["outputs_summary"] = json.dumps(event["outputs_summary"], default=str)

        # Bubble errors into span events
        events_list: List[Dict[str, Any]] = []
        if event.get("error_code"):
            events_list.append({
                "name": "exception",
                "timestamp": start_time,
                "attributes": {
                    "exception.type": event["error_code"],
                    "exception.message": event.get("error_message", ""),
                },
            })

        return cls(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            status=status,
            start_time=start_time,
            end_time=end_time,
            attributes=attributes,
            events=events_list,
        )


@dataclass
class SpanBatch:
    """Batch of spans ready for export."""
    spans: List[Span] = field(default_factory=list)
    source: str = ""  # e.g. "traces/current_traces.jsonl"
    exported_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── OTel span converter ──────────────────────────────────────────────────────

def _to_otel_span(span: Span) -> Any:
    """Convert an in-memory Span to an OTel ReadableSpan dict-like object.

    Returns a dict compatible with OTel SDK span creation.
    Only called when opentelemetry IS available.
    """
    tracer = otel_trace.get_tracer("projectx.trace_exporter")
    otel_span = tracer.start_span(
        name=span.name,
        kind=_otel_kind(span.kind),
        attributes=span.attributes,
    )
    if span.events:
        for evt in span.events:
            otel_span.add_event(
                name=evt.get("name", "event"),
                attributes=evt.get("attributes", {}),
                timestamp=_parse_timestamp(evt.get("timestamp", span.start_time)),
            )
    if span.status == "ERROR":
        otel_span.set_status(otel_trace.Status(otel_trace.StatusCode.ERROR))
    elif span.status == "OK":
        otel_span.set_status(otel_trace.Status(otel_trace.StatusCode.OK))

    if span.end_time:
        otel_span.end(end_time=_parse_timestamp(span.end_time))
    else:
        otel_span.end()

    return otel_span


def _otel_kind(kind: str) -> Any:
    """Map string span kind to OTel SpanKind."""
    if not _OTEL_AVAILABLE:
        return 0  # SpanKind.INTERNAL
    mapping = {
        "INTERNAL": otel_trace.SpanKind.INTERNAL,
        "SERVER": otel_trace.SpanKind.SERVER,
        "CLIENT": otel_trace.SpanKind.CLIENT,
        "PRODUCER": otel_trace.SpanKind.PRODUCER,
        "CONSUMER": otel_trace.SpanKind.CONSUMER,
    }
    return mapping.get(kind.upper(), otel_trace.SpanKind.INTERNAL)


def _parse_timestamp(ts: str) -> int:
    """Parse ISO8601 timestamp string to nanoseconds since epoch."""
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        return int(dt.timestamp() * 1_000_000_000)
    except (ValueError, TypeError):
        return int(time.time() * 1_000_000_000)


# ── TraceExporter ─────────────────────────────────────────────────────────────

class TraceExporter:
    """
    Reads JSONL trace events and exports as spans.

    Modes:
      1. In-memory (no OTel): spans stored as Span dataclass instances
      2. OTel (opentelemetry installed): exports to configured OTLP endpoint
      3. File: writes spans to export JSONL directory

    Usage::

        exporter = TraceExporter()
        batch = exporter.read_trace_file("traces/current_traces.jsonl")
        exporter.export(batch)
        exporter.export_to_file(batch, "projectx_logs/traces/export/")
    """

    def __init__(
        self,
        trace_dir: Optional[Path] = None,
        export_dir: Optional[Path] = None,
        otlp_endpoint: Optional[str] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._trace_dir = Path(trace_dir) if trace_dir else _DEFAULT_TRACE_DIR
        self._export_dir = Path(export_dir) if export_dir else _DEFAULT_EXPORT_DIR
        self._export_dir.mkdir(parents=True, exist_ok=True)

        # OTel infrastructure (lazy initialized)
        self._otlp_endpoint = otlp_endpoint
        self._tracer_provider: Optional[Any] = None
        self._span_processor: Optional[Any] = None
        self._otlp_exporter: Optional[Any] = None

        # In-memory span store (for no-OTel fallback)
        self._memory_spans: List[Span] = []

        # Statistics
        self._stats: Dict[str, int] = {
            "files_read": 0,
            "events_read": 0,
            "spans_created": 0,
            "spans_exported_otel": 0,
            "spans_exported_file": 0,
            "errors": 0,
        }

        logger.info(
            "TraceExporter initialized (otel=%s, trace_dir=%s, export_dir=%s)",
            _OTEL_AVAILABLE,
            self._trace_dir,
            self._export_dir,
        )

    # ── Reading ───────────────────────────────────────────────────────

    def read_trace_file(self, path: str) -> SpanBatch:
        """Read a JSONL trace file and convert events to Spans."""
        p = Path(path)
        if not p.exists():
            logger.warning("Trace file not found: %s", path)
            return SpanBatch(spans=[], source=path)

        spans: List[Span] = []
        with self._lock:
            try:
                with open(p, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            span = Span.from_trace_event(event)
                            spans.append(span)
                            self._stats["events_read"] += 1
                            self._stats["spans_created"] += 1
                        except (json.JSONDecodeError, KeyError) as exc:
                            logger.debug("Skipping bad trace line: %s", exc)
                            self._stats["errors"] += 1

                self._stats["files_read"] += 1
            except OSError as exc:
                logger.error("Failed to read trace file %s: %s", path, exc)
                self._stats["errors"] += 1
                return SpanBatch(spans=[], source=path)

        logger.info(
            "Read %d spans from %s", len(spans), path
        )
        return SpanBatch(spans=spans, source=path)

    def read_all(self) -> List[SpanBatch]:
        """Read all JSONL trace files in the configured trace directory."""
        if not self._trace_dir.exists():
            logger.info("Trace directory does not exist: %s", self._trace_dir)
            return []

        batches: List[SpanBatch] = []
        for fpath in sorted(self._trace_dir.glob("*.jsonl")):
            batch = self.read_trace_file(str(fpath))
            if batch.spans:
                batches.append(batch)

        logger.info("Read %d batches from %s", len(batches), self._trace_dir)
        return batches

    # ── Export ────────────────────────────────────────────────────────

    def export(self, batch: SpanBatch) -> int:
        """Export a span batch.

        If OTel is available, exports via OTLP.
        If OTel is NOT available, stores in memory.
        Returns the number of spans exported.
        """
        if not batch.spans:
            return 0

        with self._lock:
            if _otel_available():
                count = self._export_otel(batch)
                self._stats["spans_exported_otel"] += count
            else:
                self._memory_spans.extend(batch.spans)
                count = len(batch.spans)

            logger.debug("Exported %d spans (otel=%s)", count, _otel_available())
            return count

    def export_to_file(
        self, batch: SpanBatch,
        export_dir: Optional[str] = None,
    ) -> str:
        """Export a span batch to a JSONL file in the export directory."""
        if not batch.spans:
            return ""

        export_path = Path(export_dir) if export_dir else self._export_dir
        export_path.mkdir(parents=True, exist_ok=True)

        # Generate a unique export filename with timestamp
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        source_name = Path(batch.source).stem if batch.source else "unknown"
        out_file = export_path / f"spans_{source_name}_{ts}.jsonl"

        with self._lock:
            try:
                with open(out_file, "w") as f:
                    for span in batch.spans:
                        record = asdict(span)
                        f.write(json.dumps(record, default=str) + "\n")
                self._stats["spans_exported_file"] += len(batch.spans)
                logger.info("Exported %d spans to %s", len(batch.spans), out_file)
            except OSError as exc:
                logger.error("Failed to write export file %s: %s", out_file, exc)
                self._stats["errors"] += 1
                return ""

        return str(out_file)

    def export_all(self) -> Tuple[int, int]:
        """Read all trace files and export them.

        Returns (otel_export_count, file_export_count).
        """
        batches = self.read_all()
        if not batches:
            return (0, 0)

        otel_count = 0
        file_count = 0
        for batch in batches:
            otel_count += self.export(batch)
            file_count += len(batch.spans) if not _otel_available() else 0
            self.export_to_file(batch)

        logger.info(
            "Export complete: %d OTel, %d file spans",
            otel_count, file_count,
        )
        return (otel_count, file_count)

    # ── OTel internals ────────────────────────────────────────────────

    def _init_otel(self) -> None:
        """Lazy-init OTel tracer provider and exporter."""
        if not _OTEL_AVAILABLE:
            return
        if self._tracer_provider is not None:
            return

        with _OTEL_LOCK:
            if self._tracer_provider is not None:
                return
            try:
                self._tracer_provider = OTelTracerProvider()
                endpoint = self._otlp_endpoint or "http://localhost:4318/v1/traces"
                self._otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
                self._span_processor = BatchSpanProcessor(self._otlp_exporter)
                self._tracer_provider.add_span_processor(self._span_processor)
                otel_trace.set_tracer_provider(self._tracer_provider)
                logger.info("OTel initialized with endpoint: %s", endpoint)
            except Exception as exc:
                logger.warning("Failed to init OTel exporter: %s — fallback to in-memory", exc)
                self._tracer_provider = None

    def _export_otel(self, batch: SpanBatch) -> int:
        """Export spans via OTLP."""
        self._init_otel()
        if self._tracer_provider is None:
            # Fallback to in-memory
            self._memory_spans.extend(batch.spans)
            return len(batch.spans)

        count = 0
        for span in batch.spans:
            try:
                _to_otel_span(span)
                count += 1
            except Exception as exc:
                logger.debug("Failed to export span to OTel: %s", exc)
                self._stats["errors"] += 1

        if self._span_processor:
            self._span_processor.force_flush()

        return count

    # ── Query ─────────────────────────────────────────────────────────

    def get_spans(
        self,
        trace_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Span]:
        """Retrieve spans from in-memory store, optionally filtered by trace_id."""
        with self._lock:
            if trace_id:
                matches = [s for s in self._memory_spans if s.trace_id == trace_id]
            else:
                matches = list(self._memory_spans)
        return matches[:limit]

    def get_stats(self) -> Dict[str, int]:
        """Return copy of current statistics."""
        with self._lock:
            return dict(self._stats)

    def clear(self) -> None:
        """Clear in-memory span store."""
        with self._lock:
            self._memory_spans.clear()
            logger.debug("In-memory span store cleared")


# ── Module-level singleton ────────────────────────────────────────────────────

_exporter: Optional[TraceExporter] = None
_EXPORTER_LOCK = threading.Lock()


def get_trace_exporter(
    trace_dir: Optional[Path] = None,
    export_dir: Optional[Path] = None,
    otlp_endpoint: Optional[str] = None,
    auto_read: bool = False,
) -> TraceExporter:
    """Get or create the module-level TraceExporter singleton.

    Args:
        trace_dir: Directory containing JSONL trace files.
        export_dir: Directory to write exported span JSONL files.
        otlp_endpoint: OTLP HTTP endpoint (e.g. http://jaeger:4318/v1/traces).
        auto_read: If True, immediately read all trace files on init.

    Usage::

        exporter = get_trace_exporter()
        exporter = get_trace_exporter(otlp_endpoint="http://tempo:4318/v1/traces")
        exporter = get_trace_exporter(auto_read=True)  # read+export all
    """
    global _exporter

    if _exporter is None:
        with _EXPORTER_LOCK:
            if _exporter is None:
                _exporter = TraceExporter(
                    trace_dir=trace_dir,
                    export_dir=export_dir,
                    otlp_endpoint=otlp_endpoint,
                )
                if auto_read:
                    _exporter.export_all()

    return _exporter
