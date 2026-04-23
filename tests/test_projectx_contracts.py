from __future__ import annotations

import pytest

from simp.compat.projectx_contracts import (
    append_contract,
    contract_summary,
    normalize_contract,
    read_contracts,
)
from simp.compat.projectx_phase_status import (
    append_phase_status,
    normalize_phase_status,
    read_latest_phase_status,
)


def test_normalize_contract_rejects_unknown_type() -> None:
    with pytest.raises(ValueError):
        normalize_contract({"contract_type": "unknown"})


def test_append_and_read_projectx_contracts(tmp_path) -> None:
    log_path = tmp_path / "projectx_contracts.jsonl"

    first = append_contract(
        {
            "contract_type": "mission_lifecycle_event",
            "mission_id": "mission-1",
            "event_type": "mission_created",
            "status": "planned",
        },
        log_path=log_path,
    )
    append_contract(
        {
            "contract_type": "validation_evidence",
            "mission_id": "mission-1",
            "validation_id": "validation-1",
            "result": "passed",
        },
        log_path=log_path,
    )

    rows = read_contracts(log_path=log_path, limit=10, mission_id="mission-1")

    assert rows[0]["contract_type"] == "validation_evidence"
    assert rows[1]["record_id"] == first["record_id"]
    assert rows[0]["source_agent"] == "projectx_native"


def test_contract_summary_counts_types(tmp_path) -> None:
    log_path = tmp_path / "projectx_contracts.jsonl"
    append_contract(
        {
            "contract_type": "scoreboard_metric",
            "metric_name": "validation_pass_rate",
            "value": 1.0,
        },
        log_path=log_path,
    )

    summary = contract_summary(log_path=log_path)

    assert summary["status"] == "ok"
    assert summary["counts"]["scoreboard_metric"] == 1
    assert "validation_evidence" in summary["missing_contract_types"]


def test_phase_status_append_and_read(tmp_path) -> None:
    log_path = tmp_path / "projectx_phase_status.jsonl"

    record = append_phase_status(
        {
            "status": "ok",
            "phase_range": "8-20",
            "phases": {
                "8_world_model": {"status": "ok"},
                "20_constitution": {"status": "ok"},
            },
        },
        log_path=log_path,
    )

    latest = read_latest_phase_status(log_path=log_path)

    assert record["phase_range"] == "8-20"
    assert latest is not None
    assert latest["phases"]["8_world_model"]["status"] == "ok"


def test_normalize_phase_status_rejects_non_mapping_phases() -> None:
    with pytest.raises(ValueError):
        normalize_phase_status({"phases": ["bad"]})
