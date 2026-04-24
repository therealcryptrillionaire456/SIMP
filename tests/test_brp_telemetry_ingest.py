"""
Tests for BRP Telemetry Ingestion — TelemetrySample + TelemetryDatasetBuilder.

Validates:
1. TelemetrySample creation, serialization, deserialization
2. JSONL file discovery in test directories
3. Normalization of known record formats (brp.event.v1, brp.observation.v1,
   brp audit, security_audit)
4. Conservative label assignment (confirmed_attack, benign, suspected, unknown)
5. Dataset building with provenance report
6. Thread-safe JSONL append and reload
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

import pytest

from simp.brp.telemetry_ingest import (
    LABEL_BENIGN,
    LABEL_CONFIRMED_ATTACK,
    LABEL_SUSPECTED_ATTACK,
    LABEL_UNKNOWN,
    TelemetrySample,
    TelemetryDatasetBuilder,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_data_dir() -> str:
    """Create a temporary directory with sample JSONL files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # ── BRP events JSONL ────────────────────────────────────
        brp_events = [
            {
                "schema_version": "brp.event.v1",
                "event_id": "evt-001",
                "timestamp": "2026-04-20T12:00:00",
                "source_agent": "test_client",
                "event_type": "peer_intent",
                "action": "code_task",
                "params": {"task": "print hello"},
                "context": {"intent_id": "intent:001"},
                "mode": "shadow",
                "tags": ["broker", "route_intent", "code_task"],
            },
            {
                "schema_version": "brp.event.v1",
                "event_id": "evt-002",
                "timestamp": "2026-04-20T12:01:00",
                "source_agent": "malicious_agent",
                "event_type": "peer_intent",
                "action": "code_task",
                "params": {"task": "rm -rf /"},
                "context": {"intent_id": "intent:002"},
                "mode": "shadow",
                "tags": ["broker", "route_intent", "unauthorized_access"],
            },
        ]
        events_path = Path(tmpdir) / "brp_events.jsonl"
        with open(events_path, "w") as f:
            for rec in brp_events:
                f.write(json.dumps(rec) + "\n")

        # ── BRP audit JSONL ─────────────────────────────────────
        brp_audits = [
            {
                "record_id": "audit_001",
                "alert": {
                    "alert_id": "alert_001",
                    "agent_id": "malicious_agent_001",
                    "threat_level": "high",
                    "confidence": 0.88,
                    "patterns": [
                        {"type": "unauthorized_access", "details": "privilege escalation attempt"},
                        {"type": "suspicious_pattern", "details": "rapid intent firing"},
                    ],
                    "timestamp": "2026-04-20T12:00:00",
                    "blocked": True,
                    "source": "brp_gateway",
                    "quantum_relevance": 0.25,
                },
                "action_taken": "trust_adjusted",
                "action_details": {"trust_adjustment": -0.5},
                "processed_by": "brp_audit_consumer",
                "timestamp": "2026-04-20T12:00:01",
            },
            {
                "record_id": "audit_002",
                "alert": {
                    "alert_id": "alert_002",
                    "agent_id": "test_benign_agent",
                    "threat_level": "low",
                    "confidence": 0.1,
                    "patterns": [],
                    "timestamp": "2026-04-20T12:02:00",
                    "blocked": False,
                    "source": "brp_gateway",
                    "quantum_relevance": 0.0,
                },
                "action_taken": "none",
                "action_details": {},
                "processed_by": "brp_audit_consumer",
                "timestamp": "2026-04-20T12:02:01",
            },
            {
                "record_id": "audit_003",
                "alert": {
                    "alert_id": "alert_003",
                    "agent_id": "test_malicious_001",
                    "threat_level": "medium",
                    "confidence": 0.55,
                    "patterns": [
                        {"type": "suspicious_pattern", "details": "unusual frequency"},
                    ],
                    "timestamp": "2026-04-20T12:03:00",
                    "blocked": False,
                    "source": "brp_gateway",
                    "quantum_relevance": 0.1,
                },
                "action_taken": "flagged",
                "action_details": {},
                "processed_by": "brp_audit_consumer",
                "timestamp": "2026-04-20T12:03:01",
            },
        ]
        audits_path = Path(tmpdir) / "brp_audits.jsonl"
        with open(audits_path, "w") as f:
            for rec in brp_audits:
                f.write(json.dumps(rec) + "\n")

        # ── BRP observations JSONL ───────────────────────────────
        observations = [
            {
                "schema_version": "brp.observation.v1",
                "observation_id": "obs-001",
                "timestamp": "2026-04-20T12:10:00",
                "source_agent": "quantumarb",
                "event_id": "trade-001",
                "action": "ktc_investment_request",
                "outcome": "failed",
                "result_data": {"success": False, "error_message": "limit exceeded"},
                "context": {},
                "mode": "shadow",
                "tags": ["quantumarb", "trade"],
            },
            {
                "schema_version": "brp.observation.v1",
                "observation_id": "obs-002",
                "timestamp": "2026-04-20T12:11:00",
                "source_agent": "test_client",
                "event_id": "test-001",
                "action": "test_action",
                "outcome": "success",
                "result_data": {},
                "context": {},
                "mode": "active",
                "tags": ["test"],
            },
        ]
        obs_path = Path(tmpdir) / "brp_observations.jsonl"
        with open(obs_path, "w") as f:
            for rec in observations:
                f.write(json.dumps(rec) + "\n")

        # ── Security audit JSONL ─────────────────────────────────
        security_audits = [
            {
                "timestamp": "2026-04-10T22:03:29Z",
                "event_type": "agent_registered",
                "severity": "low",
                "details": {"agent_id": "claude_cowork", "agent_type": "llm"},
            },
            {
                "timestamp": "2026-04-10T22:03:30Z",
                "event_type": "unauthorized_access_attempt",
                "severity": "high",
                "details": {"agent_id": "unknown", "ip": "10.0.0.5"},
            },
        ]
        sec_path = Path(tmpdir) / "security_audit.jsonl"
        with open(sec_path, "w") as f:
            for rec in security_audits:
                f.write(json.dumps(rec) + "\n")

        yield tmpdir


# ── TelemetrySample Tests ───────────────────────────────────────────────────


class TestTelemetrySample:
    """Tests for TelemetrySample dataclass."""

    def test_create_default(self) -> None:
        """Default creation should auto-generate sample_id and timestamp."""
        sample = TelemetrySample()
        assert sample.sample_id
        assert len(sample.sample_id) == 36  # UUID length
        assert sample.timestamp
        assert sample.label == LABEL_UNKNOWN
        assert sample.source_type == "synthetic"
        assert sample.pipeline_path == "telemetry_ingest"

    def test_create_with_values(self) -> None:
        """Creation with specific values should preserve them."""
        sample = TelemetrySample(
            sample_id="test-001",
            source_type="real",
            source_file="/path/to/file.jsonl",
            raw_event={"key": "value"},
            normalized_scenario={"attack_type": "benign"},
            label=LABEL_BENIGN,
            label_origin="manual",
            timestamp="2026-01-01T00:00:00",
            pipeline_path="custom_pipeline",
        )
        assert sample.sample_id == "test-001"
        assert sample.source_type == "real"
        assert sample.source_file == "/path/to/file.jsonl"
        assert sample.raw_event == {"key": "value"}
        assert sample.normalized_scenario == {"attack_type": "benign"}
        assert sample.label == LABEL_BENIGN
        assert sample.label_origin == "manual"
        assert sample.timestamp == "2026-01-01T00:00:00"
        assert sample.pipeline_path == "custom_pipeline"

    def test_to_dict_roundtrip(self) -> None:
        """Serialization and deserialization should preserve all fields."""
        sample = TelemetrySample(
            sample_id="roundtrip-001",
            source_type="real",
            source_file="test.jsonl",
            raw_event={"event": "test"},
            normalized_scenario={"attack_type": "benign"},
            label=LABEL_BENIGN,
            label_origin="test",
            timestamp="2026-01-01T00:00:00",
            pipeline_path="test",
        )
        d = sample.to_dict()
        restored = TelemetrySample.from_dict(d)
        assert restored.sample_id == sample.sample_id
        assert restored.source_type == sample.source_type
        assert restored.source_file == sample.source_file
        assert restored.raw_event == sample.raw_event
        assert restored.normalized_scenario == sample.normalized_scenario
        assert restored.label == sample.label
        assert restored.label_origin == sample.label_origin
        assert restored.timestamp == sample.timestamp
        assert restored.pipeline_path == sample.pipeline_path


# ── TelemetryDatasetBuilder Tests ───────────────────────────────────────────


class TestTelemetryDatasetBuilder:
    """Tests for TelemetryDatasetBuilder."""

    def test_discover_sources_finds_jsonl_files(self, temp_data_dir: str) -> None:
        """discover_sources should find all JSONL files in the directory."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        sources = builder.discover_sources()
        # Should find 4 JSONL files
        assert len(sources) == 4
        # All should end with .jsonl
        assert all(s.endswith(".jsonl") for s in sources)

    def test_discover_sources_empty_dir(self) -> None:
        """Empty or non-existent directories should return empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = TelemetryDatasetBuilder(tmpdir)
            sources = builder.discover_sources()
            assert sources == []

    def test_discover_sources_nonexistent_dir(self) -> None:
        """Non-existent data_dir should return empty list."""
        builder = TelemetryDatasetBuilder("/nonexistent/path/xyz")
        sources = builder.discover_sources()
        assert sources == []

    def test_ingest_file_brp_events(self, temp_data_dir: str) -> None:
        """BRP event records should be normalized correctly."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        events_file = os.path.join(temp_data_dir, "brp_events.jsonl")
        samples = builder.ingest_file(events_file, source_type="real")

        assert len(samples) == 2

        # First event: benign test_client code_task
        s0 = samples[0]
        assert s0.source_type == "real"
        assert s0.source_file == events_file
        assert s0.pipeline_path == "brp_event"
        assert s0.label == LABEL_UNKNOWN  # test_client → unknown
        assert s0.label_origin == "test_marker"
        assert s0.normalized_scenario["attack_type"] == "code_exploit"
        assert s0.normalized_scenario["name"] == "BRP Event: peer_intent/code_task"

        # Second event: malicious agent with unauthorized_access tag
        s1 = samples[1]
        assert s1.label == LABEL_CONFIRMED_ATTACK
        assert s1.label_origin == "brp_event_tags"
        assert s1.normalized_scenario["attack_type"] == "privilege_escalation"
        assert "unauthorized_access" in s1.normalized_scenario["expected_detection_sources"]

    def test_ingest_file_brp_audits(self, temp_data_dir: str) -> None:
        """BRP audit records should be labeled by threat_level."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        audits_file = os.path.join(temp_data_dir, "brp_audits.jsonl")
        samples = builder.ingest_file(audits_file, source_type="real")

        assert len(samples) == 3

        # Audit 1: high threat → confirmed_attack
        s0 = samples[0]
        assert s0.label == LABEL_CONFIRMED_ATTACK
        assert s0.label_origin == "brp_audit_threat_level_high"
        assert s0.normalized_scenario["attack_type"] == "privilege_escalation"
        assert s0.normalized_scenario["expected_confidence_min"] == 0.88

        # Audit 2: agent "test_benign_agent" → test_marker (conservative)
        s1 = samples[1]
        assert s1.label == LABEL_UNKNOWN
        assert s1.label_origin == "test_marker"

        # Audit 3: agent "test_malicious_001" → test_marker (conservative)
        s2 = samples[2]
        assert s2.label == LABEL_UNKNOWN
        assert s2.label_origin == "test_marker"

    def test_ingest_file_observations(self, temp_data_dir: str) -> None:
        """BRP observation records should be labeled benign by default."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        obs_file = os.path.join(temp_data_dir, "brp_observations.jsonl")
        samples = builder.ingest_file(obs_file, source_type="real")

        assert len(samples) == 2

        # Observation 1: quantumarb failed trade → benign (operational)
        s0 = samples[0]
        assert s0.label == LABEL_BENIGN
        assert s0.label_origin == "brp_observation_default"
        assert s0.pipeline_path == "brp_observation"

        # Observation 2: test_client → unknown (test_marker)
        s1 = samples[1]
        assert s1.label == LABEL_UNKNOWN
        assert s1.label_origin == "test_marker"

    def test_ingest_file_security_audits(self, temp_data_dir: str) -> None:
        """Security audit records should be labeled by severity."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        sec_file = os.path.join(temp_data_dir, "security_audit.jsonl")
        samples = builder.ingest_file(sec_file, source_type="real")

        assert len(samples) == 2

        # Security audit 1: severity low → benign
        s0 = samples[0]
        assert s0.label == LABEL_BENIGN
        assert s0.label_origin == "security_audit_severity_low"

        # Security audit 2: severity high → confirmed_attack
        s1 = samples[1]
        assert s1.label == LABEL_CONFIRMED_ATTACK
        assert s1.label_origin == "security_audit_severity_high"

    def test_ingest_file_not_found(self, temp_data_dir: str) -> None:
        """Ingesting a non-existent file should return empty list."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        samples = builder.ingest_file("/nonexistent/file.jsonl")
        assert samples == []

    def test_ingest_file_with_empty_lines(self, temp_data_dir: str) -> None:
        """Empty lines in JSONL should be skipped gracefully."""
        filepath = os.path.join(temp_data_dir, "with_blanks.jsonl")
        with open(filepath, "w") as f:
            f.write('{"schema_version": "brp.event.v1", "event_type": "test"}\n')
            f.write("\n")
            f.write('{"schema_version": "brp.event.v1", "event_type": "test2"}\n')

        builder = TelemetryDatasetBuilder(temp_data_dir)
        samples = builder.ingest_file(filepath)
        assert len(samples) == 2

    def test_build_dataset(self, temp_data_dir: str) -> None:
        """build_dataset should discover, ingest, and return samples + scenarios."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        samples, scenarios = builder.build_dataset(source_type="real", max_samples=100)

        # Should have ingested all 9 records
        assert len(samples) >= 9
        assert len(samples) == len(scenarios)

        # All samples should be labeled
        for s in samples:
            assert s.label in (
                LABEL_CONFIRMED_ATTACK,
                LABEL_BENIGN,
                LABEL_SUSPECTED_ATTACK,
                LABEL_UNKNOWN,
            )
            assert s.normalized_scenario is not None

    def test_build_dataset_respects_max_samples(self, temp_data_dir: str) -> None:
        """max_samples should limit the number of samples returned."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        samples, scenarios = builder.build_dataset(source_type="", max_samples=3)
        assert len(samples) == 3
        assert len(scenarios) == 3

    def test_build_dataset_empty_dir(self) -> None:
        """Empty directory should return empty dataset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = TelemetryDatasetBuilder(tmpdir)
            samples, scenarios = builder.build_dataset()
            assert samples == []
            assert scenarios == []

    def test_provenance_report(self, temp_data_dir: str) -> None:
        """Provenance report should have correct counts."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        builder.build_dataset(source_type="", max_samples=100)

        report = builder.get_provenance_report()

        assert report["total_samples"] >= 9
        assert "by_source_file" in report
        assert "by_source_type" in report
        assert "by_label" in report
        assert "by_pipeline" in report

        # Should have entries for all four source files
        assert len(report["by_source_file"]) >= 4

        # Should have by_label breakdown
        total_labeled = sum(report["by_label"].values())
        assert total_labeled >= 9

    def test_provenance_report_before_build(self, temp_data_dir: str) -> None:
        """Provenance report before any ingestion should be empty."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        report = builder.get_provenance_report()
        assert report["total_samples"] == 0

    def test_append_samples_to_jsonl(self, temp_data_dir: str) -> None:
        """Appended samples should be readable back."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        output_path = os.path.join(temp_data_dir, "output_samples.jsonl")

        samples = [
            TelemetrySample(
                sample_id=f"write-{i:03d}",
                source_type="real",
                source_file="test.jsonl",
                raw_event={"idx": i},
                normalized_scenario={"attack_type": "benign"},
                label=LABEL_BENIGN,
                label_origin="test",
                timestamp="2026-01-01T00:00:00",
                pipeline_path="test",
            )
            for i in range(5)
        ]

        written = builder.append_samples_to_jsonl(samples, output_path)
        assert written == 5

        # Verify file exists and has 5 lines
        assert Path(output_path).is_file()
        with open(output_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 5

    def test_append_samples_is_thread_safe(self, temp_data_dir: str) -> None:
        """Concurrent appends should not corrupt the JSONL file."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        output_path = os.path.join(temp_data_dir, "thread_safe.jsonl")

        def writer(prefix: str, count: int) -> None:
            samples = [
                TelemetrySample(
                    sample_id=f"{prefix}-{i:03d}",
                    source_type="real",
                    source_file="thread_test.jsonl",
                    raw_event={"n": i},
                    normalized_scenario={},
                    label=LABEL_BENIGN,
                    label_origin="thread_test",
                    timestamp="2026-01-01T00:00:00",
                    pipeline_path="thread_test",
                )
                for i in range(count)
            ]
            builder.append_samples_to_jsonl(samples, output_path)

        threads = [
            threading.Thread(target=writer, args=("A", 50)),
            threading.Thread(target=writer, args=("B", 50)),
            threading.Thread(target=writer, args=("C", 50)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify file has 150 lines
        with open(output_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 150

        # Verify all lines are valid JSON
        for line in lines:
            d = json.loads(line)
            assert "sample_id" in d

    def test_load_samples_from_jsonl(self, temp_data_dir: str) -> None:
        """Samples written to JSONL should be loadable."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        output_path = os.path.join(temp_data_dir, "load_test.jsonl")

        original = TelemetrySample(
            sample_id="load-001",
            source_type="real",
            source_file="source.jsonl",
            raw_event={"key": "val"},
            normalized_scenario={"attack_type": "benign"},
            label=LABEL_BENIGN,
            label_origin="load_test",
            timestamp="2026-01-01T00:00:00",
            pipeline_path="load_test",
        )
        builder.append_samples_to_jsonl([original], output_path)

        # Fresh builder should reload them
        builder2 = TelemetryDatasetBuilder(temp_data_dir)
        loaded = builder2.load_samples_from_jsonl(output_path)

        assert len(loaded) == 1
        restored = loaded[0]
        assert restored.sample_id == "load-001"
        assert restored.source_type == "real"
        assert restored.raw_event == {"key": "val"}
        assert restored.normalized_scenario == {"attack_type": "benign"}
        assert restored.label == LABEL_BENIGN

    def test_get_samples(self, temp_data_dir: str) -> None:
        """get_samples should return all ingested samples."""
        builder = TelemetryDatasetBuilder(temp_data_dir)
        assert builder.get_samples() == []

        builder.ingest_file(os.path.join(temp_data_dir, "brp_events.jsonl"))
        assert len(builder.get_samples()) == 2

        builder.ingest_file(os.path.join(temp_data_dir, "brp_audits.jsonl"))
        assert len(builder.get_samples()) == 5

    def test_normalize_unknown_schema(self, temp_data_dir: str) -> None:
        """Records with unknown schemas should get 'generic_jsonl' pipeline."""
        builder = TelemetryDatasetBuilder(temp_data_dir)

        # Write a file with an unknown schema
        filepath = os.path.join(temp_data_dir, "unknown.jsonl")
        with open(filepath, "w") as f:
            f.write('{"random_field": "value"}\n')

        samples = builder.ingest_file(filepath)
        assert len(samples) == 1
        assert samples[0].pipeline_path == "generic_jsonl"
        assert samples[0].label == LABEL_UNKNOWN
        assert samples[0].label_origin == "unknown_schema"

    def test_conservative_labeling_test_marker(self, temp_data_dir: str) -> None:
        """Agents with 'test_' prefix should get LABEL_UNKNOWN."""
        builder = TelemetryDatasetBuilder(temp_data_dir)

        # Create a record with test source agent
        filepath = os.path.join(temp_data_dir, "test_marker.jsonl")
        with open(filepath, "w") as f:
            f.write(json.dumps({
                "schema_version": "brp.observation.v1",
                "source_agent": "test_malicious_001",
                "event_type": "test",
                "action": "delete_everything",
                "outcome": "success",
            }) + "\n")

        samples = builder.ingest_file(filepath)
        assert len(samples) == 1
        assert samples[0].label == LABEL_UNKNOWN
        assert samples[0].label_origin == "test_marker"

    def test_non_test_agent_observations(self, temp_data_dir: str) -> None:
        """Non-test agents should get proper labels even on failure."""
        builder = TelemetryDatasetBuilder(temp_data_dir)

        filepath = os.path.join(temp_data_dir, "real_agent.jsonl")
        with open(filepath, "w") as f:
            f.write(json.dumps({
                "schema_version": "brp.observation.v1",
                "source_agent": "quantumarb",
                "event_type": "trade",
                "action": "arb_execution",
                "outcome": "failed",
            }) + "\n")

        samples = builder.ingest_file(filepath)
        assert len(samples) == 1
        assert samples[0].label == LABEL_BENIGN  # operational, not attack
        assert samples[0].pipeline_path == "brp_observation"


# ── Integration Tests ───────────────────────────────────────────────────────


class TestTelemetryIntegration:
    """Integration-level tests for the full pipeline."""

    def test_full_pipeline(self, temp_data_dir: str) -> None:
        """End-to-end: discover → ingest → build → provenance → persist → reload."""
        builder = TelemetryDatasetBuilder(temp_data_dir)

        # Build dataset
        samples, scenarios = builder.build_dataset(source_type="", max_samples=100)
        assert len(samples) >= 9
        assert len(scenarios) == len(samples)

        # Check provenance
        report = builder.get_provenance_report()
        assert report["total_samples"] >= 9

        # Persist all samples
        output_path = os.path.join(temp_data_dir, "final_dataset.jsonl")
        written = builder.append_samples_to_jsonl(samples, output_path)
        assert written >= 9

        # Reload into a fresh builder
        builder2 = TelemetryDatasetBuilder(temp_data_dir)
        reloaded = builder2.load_samples_from_jsonl(output_path)
        assert len(reloaded) >= 9

        # Verify labels are preserved
        labels_seen = {s.label for s in reloaded}
        assert LABEL_BENIGN in labels_seen
        assert LABEL_CONFIRMED_ATTACK in labels_seen
        assert LABEL_UNKNOWN in labels_seen

    def test_thread_safety_concurrent_ingest(self, temp_data_dir: str) -> None:
        """Concurrent ingests should not race."""
        builder = TelemetryDatasetBuilder(temp_data_dir)

        def ingester(filepath: str) -> None:
            builder.ingest_file(filepath, source_type="real")

        files = [
            os.path.join(temp_data_dir, "brp_events.jsonl"),
            os.path.join(temp_data_dir, "brp_audits.jsonl"),
            os.path.join(temp_data_dir, "brp_observations.jsonl"),
            os.path.join(temp_data_dir, "security_audit.jsonl"),
        ]

        threads = [threading.Thread(target=ingester, args=(f,)) for f in files]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(builder.get_samples()) == 9
