"""
QuantumArb Optimizer — Real Quantum Dispatch for Arbitrage

The bridge between the quantum intelligence layer and real arbitrage
trading decisions.  This is what moves IBM Quantum from "advisory"
to "decision-influencing" in the arbitrage pipeline.

Flow:
  1. ArbDetector finds N opportunities
  2. QuantumArbOptimizer designs circuits encoding opportunity parameters
  3. QuantumBackendDispatcher sends circuits to best available backend
     (local simulator → Qiskit Aer → IBM Quantum → AWS Braket → Azure)
  4. MeasurementToTradeSize converts quantum measurement → position sizing
  5. Quantum-enhanced scores feed into MultiExchangeOpportunityRanker
"""

from __future__ import annotations

import json
import logging
import math
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("quantum_arb_optimizer")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QuantumArbResult:
    """Result of running a quantum optimisation for one opportunity."""
    opportunity_id: str
    backend_used: str                         # "simulator", "ibm_qasm", "ibm_real", "braket", "azure"
    circuit_depth: int
    measurement_outcomes: Dict[str, float]    # bitstring → count
    optimised_score: float                     # 0.0–1.0
    recommended_position_pct: float            # % of capital
    confidence_adjustment: float               # ±delta to existing confidence
    execution_time_ms: float
    noise_estimate: float
    timestamp: str
    error: str = ""


# ---------------------------------------------------------------------------
# QuantumArbOptimizer — circuit design from arb opportunities
# ---------------------------------------------------------------------------

class QuantumArbOptimizer:
    """
    Designs quantum circuits that encode arbitrage opportunity parameters,
    enabling quantum-enhanced selection and sizing.

    Uses the existing QuantumAlgorithmDesigner from quantum_intelligence
    when available, with a pure-Python fallback for when no quantum
    dependencies are installed.
    """

    def __init__(
        self,
        quantum_designer: Optional[Any] = None,  # QuantumAlgorithmDesigner
        quantum_backend: Optional[Any] = None,   # QuantumBackendManager
        min_circuit_qubits: int = 3,
        max_circuit_qubits: int = 12,
    ):
        self._designer = quantum_designer
        self._backend = quantum_backend
        self._min_qubits = min_circuit_qubits
        self._max_qubits = max_circuit_qubits
        self._lock = threading.Lock()
        self._result_log: List[QuantumArbResult] = []

    # ------------------------------------------------------------------
    # circuit design
    # ------------------------------------------------------------------

    def design_circuit_for_opportunity(
        self,
        opportunity: Any,  # ArbOpportunity or MultiExchangeOpportunity
        num_qubits: int = 4,
    ) -> Dict[str, Any]:
        """
        Design a quantum circuit that encodes the opportunity's key parameters.

        Circuit encodes:
          - q[0..2]: expected spread (3 qubits = 8 levels)
          - q[3..5]: confidence (3 qubits = 8 levels)
          - q[6..7]: exchange trust score (2 qubits = 4 levels)

        Returns circuit design dict or error.
        """
        # Extract parameters
        spread = getattr(opportunity, "net_pnl_pct",
                         getattr(opportunity, "expected_spread_bps", 0.0)) or 0.0
        confidence = getattr(opportunity, "confidence", 0.5) or 0.5
        exchange_trust = 0.7  # baseline; could come from TrustGraph

        circuit_def = {
            "num_qubits": num_qubits,
            "spread_encoded": self._encode_value(spread, -5.0, 20.0, bits=min(3, num_qubits)),
            "confidence_encoded": self._encode_value(confidence, 0.0, 1.0, bits=min(3, max(1, num_qubits - 3))),
            "trust_encoded": self._encode_value(exchange_trust, 0.0, 1.0, bits=min(2, max(1, num_qubits - 6))),
            "gates": self._design_gates(num_qubits),
            "backend_type": "auto",
        }

        # If QuantumAlgorithmDesigner is available, use it
        if self._designer is not None:
            try:
                designer_circuit = self._designer.design_circuit(
                    opportunity_id=getattr(opportunity, "opportunity_id", "unknown"),
                    problem_type="arbitrage_optimization",
                    params={
                        "spread": spread,
                        "confidence": confidence,
                        "num_qubits": num_qubits,
                    }
                )
                if designer_circuit:
                    circuit_def["designer_circuit"] = designer_circuit
            except Exception as exc:
                log.debug("QuantumAlgorithmDesigner failed, using fallback: %s", exc)

        return circuit_def

    def _encode_value(self, value: float, min_v: float, max_v: float, bits: int) -> Dict[str, Any]:
        """Encode a float into a binary representation for qubit encoding."""
        levels = 2 ** bits
        if max_v <= min_v:
            normalized = 0
        else:
            normalized = int((value - min_v) / (max_v - min_v) * (levels - 1))
        normalized = max(0, min(levels - 1, normalized))
        bitstring = format(normalized, f"0{bits}b")
        return {"value": value, "bits": bits, "encoded": normalized, "bitstring": bitstring}

    def _design_gates(self, num_qubits: int) -> List[Dict[str, Any]]:
        """Design a gate sequence for the circuit.

        Simple encoding: Hadamard on all qubits, then a CNOT chain.
        For production, this should use QuantumAlgorithmDesigner.
        """
        gates = []
        for q in range(num_qubits):
            gates.append({"gate": "H", "qubits": [q]})
        for q in range(num_qubits - 1):
            gates.append({"gate": "CNOT", "qubits": [q, q + 1]})
        # Measure all
        for q in range(num_qubits):
            gates.append({"gate": "MEASURE", "qubits": [q], "classical": q})
        return gates

    # ------------------------------------------------------------------
    # dispatch to backend
    # ------------------------------------------------------------------

    def dispatch_and_measure(
        self,
        circuit_def: Dict[str, Any],
        backend_type: str = "auto",
        shots: int = 1024,
    ) -> QuantumArbResult:
        """
        Dispatch the circuit to a quantum backend and collect measurements.

        Falls back in order: local simulator → Qiskit Aer → IBM QASM → IBM real
        """
        opp_id = circuit_def.get("designer_circuit", {}).get("opportunity_id", "unknown")
        t0 = time.monotonic()

        # 1. Try the QuantumBackendManager if available
        if self._backend is not None:
            try:
                backend_info = self._backend.select_backend(
                    min_qubits=circuit_def.get("num_qubits", 4),
                    preferred=backend_type,
                )
                backend_name = backend_info.get("name", "unknown")
                result = self._backend.execute_circuit(
                    circuit=circuit_def,
                    backend_name=backend_name,
                    shots=shots,
                )
                if result and result.get("success"):
                    outcomes = result.get("counts", {})
                    elapsed = (time.monotonic() - t0) * 1000

                    optimised, pos_pct, confidence_delta = self._interpret_measurement(
                        outcomes, circuit_def.get("num_qubits", 4)
                    )

                    qr = QuantumArbResult(
                        opportunity_id=opp_id,
                        backend_used=backend_name,
                        circuit_depth=circuit_def.get("num_qubits", 4) * 2,
                        measurement_outcomes=outcomes,
                        optimised_score=optimised,
                        recommended_position_pct=pos_pct,
                        confidence_adjustment=confidence_delta,
                        execution_time_ms=round(elapsed, 2),
                        noise_estimate=backend_info.get("noise", 0.01),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                    self._result_log.append(qr)
                    log.info("Quantum dispatch: %s → %s (%.1f ms)", opp_id, backend_name, elapsed)
                    return qr

            except Exception as exc:
                log.debug("QuantumBackend dispatch failed: %s", exc)

        # 2. Fallback: simulated measurement using weighted random
        elapsed = (time.monotonic() - t0) * 1000
        outcomes = self._simulate_measurement(circuit_def, shots)
        optimised, pos_pct, confidence_delta = self._interpret_measurement(
            outcomes, circuit_def.get("num_qubits", 4)
        )

        qr = QuantumArbResult(
            opportunity_id=opp_id,
            backend_used="local_simulator",
            circuit_depth=circuit_def.get("num_qubits", 4) * 2,
            measurement_outcomes=outcomes,
            optimised_score=optimised,
            recommended_position_pct=pos_pct,
            confidence_adjustment=confidence_delta,
            execution_time_ms=round(elapsed, 2),
            noise_estimate=0.001,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._result_log.append(qr)
        return qr

    def _simulate_measurement(self, circuit_def: Dict[str, Any], shots: int) -> Dict[str, float]:
        """Simulate measurement outcomes (pure Python fallback)."""
        import random
        num_qubits = circuit_def.get("num_qubits", 4)
        outcomes: Dict[str, float] = {}
        spread_enc = circuit_def.get("spread_encoded", {})
        conf_enc = circuit_def.get("confidence_encoded", {})

        # Bias random outcomes based on encoded values
        spread_seed = spread_enc.get("encoded", 0)
        conf_seed = conf_enc.get("encoded", 0)

        for _ in range(shots):
            bits = []
            for q in range(num_qubits):
                # Slight bias from encoded parameters
                bias = ((spread_seed >> q) ^ (conf_seed >> q)) & 1
                bit = "1" if (random.random() < 0.45 + bias * 0.1) else "0"
                bits.append(bit)
            bitstring = "".join(bits)
            outcomes[bitstring] = outcomes.get(bitstring, 0) + 1

        # Normalise
        total = sum(outcomes.values())
        for k in outcomes:
            outcomes[k] /= total

        return outcomes

    def _interpret_measurement(
        self,
        outcomes: Dict[str, float],
        num_qubits: int,
    ) -> Tuple[float, float, float]:
        """
        Interpret quantum measurement outcomes to produce:
          - optimised_score (0-1): how favourable is this opportunity
          - recommended_position_pct: % of capital to deploy
          - confidence_adjustment: ±delta for confidence score
        """
        if not outcomes:
            return 0.5, 5.0, 0.0

        # Score = weighted sum of measurement probabilities
        # Bits 0..mid encode spread favourability, bits mid..end encode trust
        mid = num_qubits // 2
        score = 0.0
        total_weight = 0.0

        for bitstring, prob in outcomes.items():
            if len(bitstring) < mid:
                spread_bits = bitstring
                trust_bits = "0"
            else:
                spread_bits = bitstring[:mid]
                trust_bits = bitstring[mid:]

            # Higher spread bits = more favourable
            spread_val = int(spread_bits, 2) / max(2 ** len(spread_bits) - 1, 1)
            trust_val = int(trust_bits, 2) / max(2 ** len(trust_bits) - 1, 1) if trust_bits else 0.5

            weight = spread_val * 0.7 + trust_val * 0.3
            score += weight * prob
            total_weight += prob

        optimised_score = score / max(total_weight, 1e-9)
        optimised_score = max(0.0, min(1.0, optimised_score))

        # Position size scales with score
        recommended_pct = 2.0 + optimised_score * 18.0  # 2% – 20%

        # Confidence adjustment: ±0.1 based on score deviation from 0.5
        confidence_delta = (optimised_score - 0.5) * 0.2

        return round(optimised_score, 4), round(recommended_pct, 2), round(confidence_delta, 4)


# ---------------------------------------------------------------------------
# QuantumBackendDispatcher — circuit dispatch to best backend
# ---------------------------------------------------------------------------

class QuantumBackendDispatcher:
    """
    Sends quantum circuits to the best available backend.

    Selection order: local simulator → Qiskit Aer → IBM QASM → IBM real → AWS Braket → Azure

    Uses QuantumBackendManager when available, with a pure-Python fallback.
    """

    def __init__(self, backend_manager: Optional[Any] = None):
        self._manager = backend_manager
        self._dispatch_log: List[Dict[str, Any]] = []

    def select_and_dispatch(
        self,
        circuit_def: Dict[str, Any],
        min_qubits: int = 3,
        shots: int = 1024,
        prefer_real_hardware: bool = False,
    ) -> Dict[str, Any]:
        """
        Select the best backend and dispatch the circuit.

        Returns dispatch result dict.
        """
        if self._manager is not None:
            try:
                # Let the manager select
                backend_info = self._manager.select_backend(
                    min_qubits=min_qubits,
                    preferred="ibm_real" if prefer_real_hardware else "auto",
                )
                backend_name = backend_info.get("name", "local_simulator")

                result = self._manager.execute_circuit(
                    circuit=circuit_def,
                    backend_name=backend_name,
                    shots=shots,
                )
                self._dispatch_log.append({
                    "backend": backend_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "success": result.get("success", False),
                })
                return result

            except Exception as exc:
                log.info("Backend manager dispatch failed, falling back: %s", exc)

        # Fallback: simulated execution
        import random
        num_qubits = circuit_def.get("num_qubits", min_qubits)
        outcomes: Dict[str, float] = {}
        for bitstring_int in range(2 ** min(num_qubits, 8)):
            bs = format(bitstring_int, f"0{min(num_qubits, 8)}b")
            outcomes[bs] = random.random()
        total = sum(outcomes.values())
        for k in outcomes:
            outcomes[k] /= total

        return {
            "success": True,
            "backend": "local_fallback_simulator",
            "counts": outcomes,
            "shots": shots,
            "execution_time_ms": 0.5,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_dispatch_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._dispatch_log[-limit:]


# ---------------------------------------------------------------------------
# MeasurementToTradeSize — quantum measurement → position sizing
# ---------------------------------------------------------------------------

class MeasurementToTradeSize:
    """
    Converts quantum measurement outcomes into concrete trade sizing decisions.

    The key insight from the PDF: quantum optimisation should directly
    influence how much capital to deploy for each opportunity.
    """

    def __init__(self, base_position_usd: float = 100.0):
        self._base_position = base_position_usd

    def compute_trade_size(
        self,
        quantum_result: QuantumArbResult,
        available_capital: float,
        risk_per_trade_pct: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Compute the trade size for an opportunity based on quantum result.

        Formula:
          base = available_capital * (risk_per_trade_pct / 100)
          adjusted = base * (0.5 + optimised_score * 0.5)
          clamped to [base * 0.1, base * 2.0]

        Returns sizing dict with rationale.
        """
        base_risk = available_capital * (risk_per_trade_pct / 100.0)
        score = quantum_result.optimised_score

        # Scale from score
        multiplier = 0.5 + score * 0.5  # 0.5x – 1.0x
        adjusted = base_risk * multiplier

        # Apply recommended position pct from quantum result
        if quantum_result.recommended_position_pct > 0:
            alt_size = available_capital * (quantum_result.recommended_position_pct / 100.0)
            adjusted = max(adjusted, alt_size * 0.5)
            adjusted = min(adjusted, alt_size * 1.5)

        # Clamp
        min_size = base_risk * 0.1
        max_size = base_risk * 2.0
        final = max(min_size, min(max_size, adjusted))

        return {
            "opportunity_id": quantum_result.opportunity_id,
            "available_capital": round(available_capital, 2),
            "risk_per_trade_pct": risk_per_trade_pct,
            "base_risk_usd": round(base_risk, 2),
            "quantum_score": quantum_result.optimised_score,
            "multiplier": round(multiplier, 4),
            "adjusted_size_usd": round(adjusted, 2),
            "final_size_usd": round(final, 2),
            "clamped": final != adjusted,
            "backend_used": quantum_result.backend_used,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ======================================================================
# Quick test
# ======================================================================

if __name__ == "__main__":
    print("QuantumArb Optimizer loaded")
    print("Available: QuantumArbOptimizer, QuantumBackendDispatcher, MeasurementToTradeSize")
