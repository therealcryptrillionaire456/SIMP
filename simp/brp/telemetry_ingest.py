"""
BRP Telemetry Ingestion — Real-event normalization for benchmark-ready samples.

Converts JSONL/log records from SIMP system components (BRP audits, security
audits, system logs) into benchmark-ready AttackScenario-compatible samples
that can be fed into DetectionBenchmark for measurement.

Thread-safe with JSONL append support. Conservative labeling — ambiguous
records are tagged as "unknown" and excluded from headline metrics.
"""

from __future__ import annotations

import json
import os
import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Label constants ─────────────────────────────────────────────────────────

LABEL_CONFIRMED_ATTACK = "confirmed_attack"
LABEL_BENIGN = "benign"
LABEL_SUSPECTED_ATTACK = "suspected_attack"
LABEL_UNKNOWN = "unknown"

# ── TelemetrySample dataclass ───────────────────────────────────────────────


@dataclass
class TelemetrySample:
    """A single normalized telemetry sample ready for benchmark consumption.

    Each sample represents one raw event that has been converted into a
    DetectionBenchmark-compatible scenario format with a conservative label.
    """

    sample_id: str = ""
    source_type: str = "synthetic"  # "synthetic" | "real"
    source_file: str = ""            # provenance: path to origin file
    raw_event: Dict[str, Any] = field(default_factory=dict)
    normalized_scenario: Dict[str, Any] = field(default_factory=dict)
    label: str = LABEL_UNKNOWN
    label_origin: str = ""
    timestamp: str = ""
    pipeline_path: str = "telemetry_ingest"

    def __post_init__(self) -> None:
        if not self.sample_id:
            self.sample_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSONL persistence."""
        return {
            "sample_id": self.sample_id,
            "source_type": self.source_type,
            "source_file": self.source_file,
            "raw_event": self.raw_event,
            "normalized_scenario": self.normalized_scenario,
            "label": self.label,
            "label_origin": self.label_origin,
            "timestamp": self.timestamp,
            "pipeline_path": self.pipeline_path,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> TelemetrySample:
        """Deserialize from a dict (loaded from JSONL)."""
        return cls(
            sample_id=d.get("sample_id", ""),
            source_type=d.get("source_type", "synthetic"),
            source_file=d.get("source_file", ""),
            raw_event=d.get("raw_event", {}),
            normalized_scenario=d.get("normalized_scenario", {}),
            label=d.get("label", LABEL_UNKNOWN),
            label_origin=d.get("label_origin", ""),
            timestamp=d.get("timestamp", ""),
            pipeline_path=d.get("pipeline_path", "telemetry_ingest"),
        )


# ── TelemetryDatasetBuilder ────────────────────────────────────────────────


class TelemetryDatasetBuilder:
    """Scans JSONL files, normalizes records into benchmark-ready samples.

    Discovers JSONL files from a data directory, ingests each record,
    applies conservative labeling, and builds a dataset that can be fed
    into DetectionBenchmark for measurement.
    """

    # Known JSONL schema prefixes used across SIMP data files
    _KNOWN_SCHEMAS = (
        "brp.event.v1",
        "brp.observation.v1",
        "brp.audit.v1",
        "security_audit",
    )

    def __init__(self, data_dir: str) -> None:
        self._data_dir = Path(data_dir)
        self._lock = threading.Lock()
        self._samples: List[TelemetrySample] = []

    # ── Discovery ─────────────────────────────────────────────────────────

    def discover_sources(self) -> List[str]:
        """Find JSONL files in the data directory (recursive, max depth 3)."""
        sources: List[str] = []
        if not self._data_dir.is_dir():
            logger.warning("Data directory does not exist: %s", self._data_dir)
            return sources

        for entry in sorted(self._data_dir.rglob("*.jsonl")):
            sources.append(str(entry.absolute()))

        return sources

    # ── Ingestion ─────────────────────────────────────────────────────────

    def ingest_file(
        self,
        filepath: str,
        source_type: str = "real",
    ) -> List[TelemetrySample]:
        """Read a JSONL file, normalise each record into a TelemetrySample.

        Args:
            filepath: Path to the JSONL file.
            source_type: "real" for production data, "synthetic" for test data.

        Returns:
            List of TelemetrySample objects.
        """
        path = Path(filepath)
        if not path.is_file():
            logger.warning("File not found: %s", filepath)
            return []

        samples: List[TelemetrySample] = []

        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Skipping unparseable line in %s", filepath)
                    continue

                sample = self._normalize_record(record, filepath, source_type)
                samples.append(sample)

        with self._lock:
            self._samples.extend(samples)

        logger.info(
            "Ingested %d samples from %s (source_type=%s)",
            len(samples),
            filepath,
            source_type,
        )
        return samples

    # ── Normalization ─────────────────────────────────────────────────────

    def _normalize_record(
        self,
        record: Dict[str, Any],
        source_file: str = "",
        source_type: str = "real",
    ) -> TelemetrySample:
        """Convert a raw JSONL record into a TelemetrySample.

        The normalization logic:
        1. Detects the schema/event type from the record.
        2. Extracts threat-relevant fields and maps them to scenario format.
        3. Assigns a conservative label based on explicit threat indicators.

        Returns a TelemetrySample with normalized_scenario compatible with
        DetectionBenchmark's AttackScenario expected_detection_sources format.
        """
        sample_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        schema = record.get("schema_version", "")

        # Determine pipeline path based on schema
        if schema.startswith("brp.event.v1"):
            pipeline_path = "brp_event"
        elif schema.startswith("brp.observation.v1"):
            pipeline_path = "brp_observation"
        elif "alert" in record or schema.startswith("brp.audit.v1"):
            pipeline_path = "brp_audit"
        elif record.get("event_type") and record.get("severity"):
            pipeline_path = "security_audit"
        else:
            pipeline_path = "generic_jsonl"

        # Build normalized scenario from the record
        normalized = self._build_scenario_from_record(record, schema, pipeline_path)

        # Assign label
        label, label_origin = self._assign_label(record, schema, pipeline_path)

        # Detect source_type from mode=shadow if present
        detected_source = source_type
        if record.get("mode") == "shadow":
            detected_source = "real"  # shadow mode = real production shadowing

        return TelemetrySample(
            sample_id=sample_id,
            source_type=detected_source,
            source_file=source_file,
            raw_event=record,
            normalized_scenario=normalized,
            label=label,
            label_origin=label_origin,
            timestamp=now_iso,
            pipeline_path=pipeline_path,
        )

    def _build_scenario_from_record(
        self,
        record: Dict[str, Any],
        schema: str,
        pipeline: str,
    ) -> Dict[str, Any]:
        """Build a DetectionBenchmark-compatible scenario dict.

        The output dict uses fields consistent with AttackScenario:
        - attack_type: mapped from threat_level or event context
        - name: descriptive name from the event
        - description: event context description
        - text_inputs / code_inputs / behavior_inputs / network_inputs
        - expected_detection_sources
        """
        scenario: Dict[str, Any] = {
            "attack_type": "unknown",
            "name": "",
            "description": "",
            "text_inputs": [],
            "code_inputs": [],
            "behavior_inputs": [],
            "network_inputs": [],
            "memory_inputs": [],
            "expected_detection_sources": [],
            "expected_detection_count_min": 0,
            "expected_confidence_min": 0.0,
        }

        if pipeline == "brp_event":
            # brp.event.v1 → peer_intent events
            event_type = record.get("event_type", "")
            action = record.get("action", "")
            tags = record.get("tags", [])
            context = record.get("context", {})
            params = record.get("params", {})

            scenario["attack_type"] = self._map_event_type_to_attack_type(
                event_type, action, tags
            )
            scenario["name"] = f"BRP Event: {event_type}/{action}"
            scenario["description"] = (
                f"Agent {record.get('source_agent', 'unknown')} "
                f"issued {action} with tags {tags}"
            )
            scenario["behavior_inputs"].append({
                "event": event_type,
                "action": action,
                "source_agent": record.get("source_agent", ""),
                "tags": tags,
                "context": context,
                "params": params,
                "mode": record.get("mode", "active"),
            })
            # Map tags to expected detection sources
            detection_tags = [t for t in tags if t in (
                "code_task", "research", "strategy_generation",
                "unauthorized_access", "suspicious_pattern",
                "quantum_constraint_violation",
            )]
            scenario["expected_detection_sources"] = detection_tags
            scenario["expected_detection_count_min"] = 1 if detection_tags else 0
            scenario["expected_confidence_min"] = 0.7 if detection_tags else 0.0

        elif pipeline == "brp_observation":
            # brp.observation.v1 → outcome records
            outcome = record.get("outcome", "unknown")
            action = record.get("action", "")
            result_data = record.get("result_data", {})
            tags = record.get("tags", [])

            scenario["attack_type"] = "data_exfiltration" if outcome == "failed" else "benign"
            scenario["name"] = f"BRP Observation: {action}/{outcome}"
            scenario["description"] = (
                f"Agent {record.get('source_agent', 'unknown')} "
                f"action={action} outcome={outcome}"
            )
            scenario["behavior_inputs"].append({
                "event": record.get("event_type", "observation"),
                "action": action,
                "outcome": outcome,
                "source_agent": record.get("source_agent", ""),
                "result_data": result_data,
                "tags": tags,
                "mode": record.get("mode", "active"),
            })
            scenario["expected_detection_sources"] = []
            scenario["expected_detection_count_min"] = 0

        elif pipeline == "brp_audit":
            # BRP audit alert records
            alert = record.get("alert", {})
            action_taken = record.get("action_taken", "")

            threat_level = alert.get("threat_level", "low")
            confidence = alert.get("confidence", 0.0)
            patterns = alert.get("patterns", [])
            blocked = alert.get("blocked", False)
            source = alert.get("source", "")
            agent_id = alert.get("agent_id", "")

            scenario["attack_type"] = self._map_threat_level(threat_level)
            scenario["name"] = f"BRP Audit: {threat_level} alert from {agent_id}"
            scenario["description"] = (
                f"Agent {agent_id} triggered {threat_level} alert from {source}. "
                f"Action: {action_taken}. Blocked: {blocked}."
            )
            # Extract pattern details
            for pat in patterns:
                entry: Dict[str, Any] = {
                    "event": "audit_pattern",
                    "pattern_type": pat.get("type", "unknown"),
                    "details": pat.get("details", ""),
                }
                scenario["behavior_inputs"].append(entry)

            scenario["network_inputs"].append({
                "protocol": "BRP",
                "source": source,
                "destination": agent_id,
                "bytes": 0,
                "suspicious": threat_level in ("high", "quantum", "critical"),
            })
            scenario["expected_detection_sources"] = (
                ["multimodal.behavior", "multimodal.network"]
                if threat_level in ("high", "quantum", "critical")
                else []
            )
            scenario["expected_detection_count_min"] = 1 if threat_level in ("high", "quantum", "critical") else 0
            scenario["expected_confidence_min"] = confidence

        elif pipeline == "security_audit":
            # security_audit.jsonl records
            event_type = record.get("event_type", "")
            severity = record.get("severity", "low")
            details = record.get("details", {})

            scenario["attack_type"] = "benign" if severity == "low" else "privilege_escalation"
            scenario["name"] = f"Security Audit: {event_type}/{severity}"
            scenario["description"] = f"Security event {event_type} with severity {severity}: {details}"
            scenario["behavior_inputs"].append({
                "event": event_type,
                "severity": severity,
                "details": details,
            })
            scenario["expected_detection_sources"] = []
            scenario["expected_detection_count_min"] = 0

        else:
            # Generic JSONL — look for threat indicators
            scenario["attack_type"] = "unknown"
            scenario["name"] = "Generic JSONL record"
            scenario["description"] = (
                f"Raw record with keys: {list(record.keys())}"
            )
            scenario["behavior_inputs"].append({"raw_record": record})

        return scenario

    # ── Label Assignment ──────────────────────────────────────────────────

    def _assign_label(
        self,
        record: Dict[str, Any],
        schema: str,
        pipeline: str,
    ) -> Tuple[str, str]:
        """Assign a conservative label to a record.

        Labeling rules:
        - Explicit BRP assessment (threat_level=high/critical/quantum) → confirmed_attack
        - Explicit clean/benign signal or blocked=False with low threat → benign
        - Suspicious but not confirmed → suspected_attack
        - Test/demo markers, ambiguous, or no signal → unknown
        """
        if pipeline == "brp_event":
            # brp.event.v1 records are generally benign shadow-mode events
            tags = record.get("tags", [])
            action = record.get("action", "")

            # Check for explicit threat tags
            threat_keywords = {"unauthorized_access", "suspicious_pattern",
                               "quantum_constraint_violation", "intent_escalation"}
            if threat_keywords & set(tags):
                return LABEL_CONFIRMED_ATTACK, "brp_event_tags"

            # Test markers → unknown
            source = record.get("source_agent", "")
            if source in ("test_client", "test_agent") or "test" in source.lower():
                return LABEL_UNKNOWN, "test_marker"

            return LABEL_BENIGN, "brp_event_default"

        elif pipeline == "brp_observation":
            # Observations are generally benign operational records
            outcome = record.get("outcome", "")
            source = record.get("source_agent", "")
            if source in ("test_client", "test_agent") or "test" in source.lower():
                return LABEL_UNKNOWN, "test_marker"
            # Failed outcomes from quantumarb are operational, not attacks
            return LABEL_BENIGN, "brp_observation_default"

        elif pipeline == "brp_audit":
            alert = record.get("alert", {})
            threat_level = alert.get("threat_level", "low")
            agent_id = alert.get("agent_id", "")

            if agent_id.startswith("test_"):
                return LABEL_UNKNOWN, "test_marker"

            if threat_level in ("high", "critical", "quantum"):
                return LABEL_CONFIRMED_ATTACK, f"brp_audit_threat_level_{threat_level}"
            elif threat_level == "medium":
                return LABEL_SUSPECTED_ATTACK, "brp_audit_threat_level_medium"
            else:
                return LABEL_BENIGN, "brp_audit_threat_level_low"

        elif pipeline == "security_audit":
            severity = record.get("severity", "low")
            event_type = record.get("event_type", "")
            if severity in ("high", "critical"):
                return LABEL_CONFIRMED_ATTACK, f"security_audit_severity_{severity}"
            elif severity == "medium":
                return LABEL_SUSPECTED_ATTACK, "security_audit_severity_medium"
            else:
                return LABEL_BENIGN, "security_audit_severity_low"

        else:
            return LABEL_UNKNOWN, "unknown_schema"

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _map_threat_level(threat_level: str) -> str:
        """Map BRP threat levels to attack type strings."""
        mapping = {
            "low": "benign",
            "medium": "suspected_attack",
            "high": "privilege_escalation",
            "critical": "data_exfiltration",
            "quantum": "rapid_probe",
        }
        return mapping.get(threat_level, "unknown")

    @staticmethod
    def _map_event_type_to_attack_type(
        event_type: str,
        action: str,
        tags: List[str],
    ) -> str:
        """Map event metadata to an attack type for the scenario."""
        threat_keywords = {"unauthorized_access", "suspicious_pattern",
                           "quantum_constraint_violation", "intent_escalation"}
        if threat_keywords & set(tags):
            return "privilege_escalation"
        if action == "code_task":
            return "code_exploit"
        if action == "research":
            return "text_injection"
        if "strategy" in action:
            return "rapid_probe"
        return "unknown"

    # ── Dataset Building ─────────────────────────────────────────────────

    def build_dataset(
        self,
        source_type: str = "real",
        max_samples: int = 10000,
    ) -> Tuple[List[TelemetrySample], List[Dict[str, Any]]]:
        """Discover and ingest all JSONL files, return samples + scenarios.

        Args:
            source_type: Filter to "real" or "synthetic" samples.
            max_samples: Maximum number of samples to return.

        Returns:
            Tuple of (samples list, scenarios list for benchmark consumption).
        """
        files = self.discover_sources()
        all_samples: List[TelemetrySample] = []

        for filepath in files:
            samples = self.ingest_file(filepath, source_type=source_type)
            all_samples.extend(samples)
            if len(all_samples) >= max_samples:
                all_samples = all_samples[:max_samples]
                break

        # Filter by source_type if requested
        if source_type:
            filtered = [s for s in all_samples if s.source_type == source_type]
        else:
            filtered = all_samples

        scenarios = [s.normalized_scenario for s in filtered]

        self._samples = filtered
        return filtered, scenarios

    # ── Provenance Report ────────────────────────────────────────────────

    def get_provenance_report(self) -> Dict[str, Any]:
        """Return a report of counts by source, type, label, pipeline.

        Returns a dict with:
        - total_samples
        - by_source_file: dict of filepath → count
        - by_source_type: dict of source_type → count
        - by_label: dict of label → count
        - by_pipeline: dict of pipeline_path → count
        """
        with self._lock:
            samples = list(self._samples)

        by_source: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        by_label: Dict[str, int] = {}
        by_pipeline: Dict[str, int] = {}

        for s in samples:
            by_source[s.source_file] = by_source.get(s.source_file, 0) + 1
            by_type[s.source_type] = by_type.get(s.source_type, 0) + 1
            by_label[s.label] = by_label.get(s.label, 0) + 1
            by_pipeline[s.pipeline_path] = by_pipeline.get(s.pipeline_path, 0) + 1

        return {
            "total_samples": len(samples),
            "by_source_file": by_source,
            "by_source_type": by_type,
            "by_label": by_label,
            "by_pipeline": by_pipeline,
        }

    # ── Persistence ──────────────────────────────────────────────────────

    def append_samples_to_jsonl(
        self,
        samples: List[TelemetrySample],
        output_path: str,
    ) -> int:
        """Thread-safe append of TelemetrySamples to a JSONL file.

        Args:
            samples: List of samples to persist.
            output_path: Path to the output JSONL file.

        Returns:
            Number of samples written.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with self._lock:
            with open(path, "a") as f:
                for sample in samples:
                    f.write(json.dumps(sample.to_dict(), default=str) + "\n")
                    count += 1

        return count

    def load_samples_from_jsonl(
        self,
        input_path: str,
    ) -> List[TelemetrySample]:
        """Load TelemetrySamples from a JSONL file.

        Args:
            input_path: Path to the JSONL file.

        Returns:
            List of TelemetrySample objects.
        """
        path = Path(input_path)
        if not path.is_file():
            return []

        samples: List[TelemetrySample] = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    samples.append(TelemetrySample.from_dict(d))
                except json.JSONDecodeError:
                    continue

        with self._lock:
            self._samples.extend(samples)

        return samples

    def get_samples(self) -> List[TelemetrySample]:
        """Return all currently loaded samples."""
        with self._lock:
            return list(self._samples)
