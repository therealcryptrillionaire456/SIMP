import json
from pathlib import Path

from bullbear_quantum_bridge import BridgePaths, BullBearQuantumBridge


def test_bridge_round_trip(tmp_path):
    paths = BridgePaths(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        processed_dir=tmp_path / "processed",
        failed_dir=tmp_path / "failed",
    )
    bridge = BullBearQuantumBridge(paths=paths, dry_run=True)

    source = paths.input_dir / "intent_test_signal.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        json.dumps(
            {
                "intent_id": "bb-1",
                "source_agent": "bullbear_predictor",
                "target_agent": "quantumarb",
                "intent_type": "prediction_signal",
                "ticker": "BTC-USD",
                "direction": "bull",
                "confidence": 0.62,
                "trust": 0.8,
                "delta": 0.15,
                "contradiction_score": 0.05,
                "dry_run": True,
            }
        )
    )

    outputs = bridge.process_available_once()
    assert len(outputs) == 1

    enhanced = json.loads(outputs[0].read_text())
    assert enhanced["metadata"]["quantum_enhanced"] is True
    assert enhanced["params"]["quantum_confidence"] > enhanced["params"]["original_confidence"]
    assert (paths.processed_dir / source.name).exists()
    assert not (paths.failed_dir / source.name).exists()
