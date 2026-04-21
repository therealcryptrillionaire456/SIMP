#!/usr/bin/env python3
"""
BullBear Quantum Bridge.

Reads BullBear prediction files, applies a deterministic quantum-weighted
confidence adjustment, and writes enhanced prediction packets for downstream
consumers. This bridge is file-based on purpose so it can operate safely even
when the broker or the external BullBear repo is unavailable.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


logger = logging.getLogger("bullbear_quantum_bridge")


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


DEFAULT_INPUT_DIR = _env_path("BULLBEAR_BRIDGE_INPUT_DIR", str(Path.home() / "bullbear" / "signals" / "output"))
DEFAULT_OUTPUT_DIR = _env_path("BULLBEAR_BRIDGE_OUTPUT_DIR", "data/processed/bullbear_quantum_bridge/output")
DEFAULT_PROCESSED_DIR = _env_path("BULLBEAR_BRIDGE_PROCESSED_DIR", "data/processed/bullbear_quantum_bridge/processed")
DEFAULT_FAILED_DIR = _env_path("BULLBEAR_BRIDGE_FAILED_DIR", "data/processed/bullbear_quantum_bridge/failed")


@dataclass
class BridgePaths:
    input_dir: Path = DEFAULT_INPUT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    processed_dir: Path = DEFAULT_PROCESSED_DIR
    failed_dir: Path = DEFAULT_FAILED_DIR

    def ensure(self) -> None:
        for directory in (self.input_dir, self.output_dir, self.processed_dir, self.failed_dir):
            directory.mkdir(parents=True, exist_ok=True)


class BullBearQuantumBridge:
    def __init__(self, paths: Optional[BridgePaths] = None, *, dry_run: bool = True) -> None:
        self.paths = paths or BridgePaths()
        self.paths.ensure()
        self.dry_run = dry_run

    def iter_prediction_files(self) -> Iterable[Path]:
        return sorted(self.paths.input_dir.glob("*.json"))

    def normalize_prediction(self, payload: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
        params = payload.get("params", {})
        metadata = dict(payload.get("metadata", {}))
        direction = payload.get("direction") or params.get("direction") or payload.get("stance") or "neutral"
        confidence = self._as_float(
            payload.get("confidence", params.get("confidence", payload.get("trust", 0.5))),
            default=0.5,
        )
        contradiction = self._as_float(payload.get("contradiction_score", params.get("contradiction_score", 0.0)), default=0.0)
        delta = self._as_float(payload.get("delta", params.get("delta", 0.0)), default=0.0)
        trust = self._as_float(payload.get("trust", params.get("trust", confidence)), default=confidence)
        ticker = payload.get("ticker") or params.get("ticker") or params.get("symbol") or payload.get("symbol") or "UNKNOWN"
        intent_type = payload.get("intent_type", "prediction_signal")

        metadata.setdefault("source_file", source_file.name)
        metadata.setdefault("bridge_mode", "file")

        return {
            "intent_id": payload.get("intent_id", f"bullbear-{uuid.uuid4().hex[:12]}"),
            "source_agent": payload.get("source_agent", "bullbear_predictor"),
            "target_agent": payload.get("target_agent", "quantumarb"),
            "intent_type": intent_type,
            "params": params,
            "metadata": metadata,
            "direction": direction,
            "delta": delta,
            "trust": trust,
            "contradiction_score": contradiction,
            "ticker": ticker,
            "confidence": confidence,
            "dry_run": bool(payload.get("dry_run", True)),
        }

    def enhance_prediction(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        base_confidence = normalized["confidence"]
        contradiction_penalty = min(0.2, normalized["contradiction_score"] * 0.5)
        trust_boost = min(0.15, normalized["trust"] * 0.1)
        delta_boost = min(0.1, abs(normalized["delta"]) * 0.25)
        quantum_confidence = max(0.0, min(0.99, base_confidence + trust_boost + delta_boost - contradiction_penalty))

        enhanced_params = dict(normalized["params"])
        enhanced_params.update(
            {
                "ticker": normalized["ticker"],
                "direction": normalized["direction"],
                "original_confidence": base_confidence,
                "quantum_confidence": quantum_confidence,
                "quantum_enhanced": True,
                "quantum_delta": round(quantum_confidence - base_confidence, 4),
            }
        )

        return {
            "intent_id": normalized["intent_id"],
            "source_agent": "bullbear_quantum_bridge",
            "target_agent": normalized["target_agent"],
            "intent_type": normalized["intent_type"],
            "params": enhanced_params,
            "metadata": {
                **normalized["metadata"],
                "bridge_id": "bullbear_quantum_bridge",
                "quantum_enhanced": True,
            },
            "direction": normalized["direction"],
            "delta": normalized["delta"],
            "trust": normalized["trust"],
            "contradiction_score": normalized["contradiction_score"],
            "ticker": normalized["ticker"],
            "dry_run": self.dry_run or normalized["dry_run"],
        }

    def process_file(self, source_file: Path) -> Optional[Path]:
        try:
            payload = json.loads(source_file.read_text())
            normalized = self.normalize_prediction(payload, source_file)
            enhanced = self.enhance_prediction(normalized)

            output_path = self.paths.output_dir / f"quantum_{source_file.name}"
            if not self.dry_run:
                output_path.write_text(json.dumps(enhanced, indent=2))
            else:
                output_path.write_text(json.dumps(enhanced, indent=2))

            shutil.move(str(source_file), self.paths.processed_dir / source_file.name)
            logger.info("Enhanced %s -> %s", source_file.name, output_path.name)
            return output_path
        except Exception:
            logger.exception("Failed to process %s", source_file)
            try:
                shutil.move(str(source_file), self.paths.failed_dir / source_file.name)
            except Exception:
                logger.exception("Failed to archive %s into failed dir", source_file)
            return None

    def process_available_once(self) -> List[Path]:
        outputs: List[Path] = []
        for source_file in self.iter_prediction_files():
            output = self.process_file(source_file)
            if output is not None:
                outputs.append(output)
        return outputs

    @staticmethod
    def _as_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


def main() -> None:
    parser = argparse.ArgumentParser(description="File-based BullBear quantum bridge")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--failed-dir", type=Path, default=DEFAULT_FAILED_DIR)
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--live", action="store_true", help="Write non-dry-run bridge artifacts")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [bullbear_bridge] %(levelname)s %(message)s")
    bridge = BullBearQuantumBridge(
        BridgePaths(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            processed_dir=args.processed_dir,
            failed_dir=args.failed_dir,
        ),
        dry_run=not args.live,
    )

    if args.once:
        outputs = bridge.process_available_once()
        print(json.dumps({"outputs": [str(path) for path in outputs]}, indent=2))
        return

    while True:
        bridge.process_available_once()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
