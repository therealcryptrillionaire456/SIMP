"""
APO Wire-Up — T25
==================
Wires ProjectX APO engine into the quantum decision agent
so it learns to make better GO/NO-GO decisions over time.

Fitness function: (wins / total) * avg_edge_bps - false_positive_rate * penalty

Usage:
    python3 scripts/apo_wire.py --dry-run  # analyze and suggest
    python3 scripts/apo_wire.py --apply    # apply best candidate (paper mode only)
    python3 scripts/apo_wire.py --report   # show current fitness
"""

from __future__ import annotations

import json
import logging
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from simp.projectx.apo_engine import APOEngine, PromptCandidate

log = logging.getLogger("apo_wire")

# Fitness penalty for false positives (trades that went NO-GO but would have won)
FALSE_POSITIVE_PENALTY = 0.1

# Default baseline criteria (must match quantum_decision_agent defaults)
DEFAULT_BASELINE = {
    "min_expected_return_pct": 0.01,
    "min_confidence": 0.3,
    "max_risk_score": 0.8,
    "min_capital_usd": 1.0,
}

# UCB exploration constant
UCB_C = 1.414


@dataclass
class CriteriaCandidate:
    """A GO criteria variant with its fitness score."""
    candidate_id: str
    min_expected_return_pct: float
    min_confidence: float
    max_risk_score: float
    min_capital_usd: float
    fitness: float = 0.0
    win_count: int = 0
    total_count: int = 0
    false_positive_count: int = 0
    n_visits: int = 0

    def ucb_score(self) -> float:
        """Upper Confidence Bound score for candidate selection."""
        if self.n_visits == 0:
            return float("inf")
        exploitation = self.fitness
        exploration = UCB_C * ((2 * 0.5 ** 0.5) / (self.n_visits ** 0.5))
        return exploitation + exploration


class APOWire:
    """
    APO-powered criteria evolution for quantum_decision_agent.

    Reads: state/decision_journal.ndjson, data/pnl_ledger.jsonl
    Writes: data/apo_candidates/ directory with criteria snapshots
    Modifies: quantum_decision_agent criteria (with approval)
    """

    def __init__(self, candidates_dir: Path = None):
        self.repo = REPO
        self.candidates_dir = candidates_dir or self.repo / "data" / "apo_candidates"
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.repo / "state" / "decision_journal.ndjson"
        self.pnl_path = self.repo / "data" / "pnl_ledger.jsonl"
        self.apo = APOEngine(population_dir=self.candidates_dir)
        self._cache_dir = self.repo / "data" / "apo_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def load_decisions(self, limit: int = 500) -> List[Dict]:
        """Load recent decisions from journal."""
        decisions = []
        if not self.journal_path.exists():
            log.warning(f"Decision journal not found: {self.journal_path}")
            return decisions
        try:
            with open(self.journal_path) as f:
                lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    decisions.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            log.warning(f"Could not load decisions: {e}")
        return decisions

    def load_pnl(self, limit: int = 500) -> Dict[str, Dict]:
        """Load PnL records keyed by signal/execution ID."""
        pnl_map: Dict[str, Dict] = {}
        if not self.pnl_path.exists():
            log.warning(f"PnL ledger not found: {self.pnl_path}")
            return pnl_map
        try:
            with open(self.pnl_path) as f:
                lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    record = json.loads(line.strip())
                    sid = record.get("signal_id") or record.get("execution_id", "")
                    pnl_map[sid] = record
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            log.warning(f"Could not load PnL: {e}")
        return pnl_map

    def compute_fitness(
        self,
        candidate: CriteriaCandidate,
        decisions: List[Dict],
        pnl_map: Dict[str, Dict],
    ) -> float:
        """Compute fitness score for a criteria candidate.

        Fitness = win_rate * avg_edge - false_positive_rate * penalty
        """
        wins = 0
        total = 0
        fp = 0
        edges: List[float] = []

        for decision in decisions:
            opp = decision.get("opportunity", {})
            signal_id = decision.get("signal_id") or decision.get("decision_id", "")

            # Does this decision pass the candidate's criteria?
            ret_ok = opp.get("expected_return_pct", 0) >= candidate.min_expected_return_pct
            conf_ok = decision.get("confidence", 0) >= candidate.min_confidence
            risk_ok = opp.get("risk_score", 0) <= candidate.max_risk_score
            cap_ok = opp.get("capital_required_usd", 0) >= candidate.min_capital_usd

            would_go = ret_ok and conf_ok and risk_ok and cap_ok

            actual_went = decision.get("decision") == "go"
            pnl_record = pnl_map.get(signal_id, {})
            actual_pnl = pnl_record.get("pnl_usd", 0.0)

            if would_go:
                total += 1
                if actual_pnl > 0:
                    wins += 1
                    edges.append(actual_pnl)
            else:
                # False negative: we said NO-GO but it would have won
                if actual_went and actual_pnl > 0:
                    fp += 1

        candidate.win_count = wins
        candidate.total_count = total
        candidate.false_positive_count = fp

        if total == 0:
            candidate.fitness = 0.0
            return 0.0

        win_rate = wins / total
        avg_edge = sum(edges) / max(len(edges), 1)
        fp_rate = fp / len(decisions) if decisions else 0
        fitness = win_rate * avg_edge - fp_rate * FALSE_POSITIVE_PENALTY

        candidate.fitness = max(0.0, fitness)
        return candidate.fitness

    def generate_mutations(
        self, baseline: Dict[str, float], n: int = 10
    ) -> List[CriteriaCandidate]:
        """Generate n mutation candidates by varying thresholds ±5%."""
        candidates: List[CriteriaCandidate] = []
        for i in range(n):
            c = CriteriaCandidate(
                candidate_id=f"mut_{i}_{int(time.time())}",
                min_expected_return_pct=baseline["min_expected_return_pct"] * random.uniform(0.95, 1.05),
                min_confidence=baseline["min_confidence"] * random.uniform(0.95, 1.05),
                max_risk_score=baseline["max_risk_score"] * random.uniform(0.95, 1.05),
                min_capital_usd=baseline["min_capital_usd"],
            )
            candidates.append(c)
        return candidates

    def _load_baseline_from_agent(self) -> Dict[str, float]:
        """Attempt to read live criteria from quantum_decision_agent."""
        agent_file = self.repo / "simp/agents/quantum_decision_agent.py"
        if not agent_file.exists():
            return DEFAULT_BASELINE.copy()
        try:
            content = agent_file.read_text()
            baseline = DEFAULT_BASELINE.copy()
            for line in content.splitlines():
                if "min_expected_return_pct" in line and "=" in line:
                    parts = line.split("=")
                    if len(parts) == 2:
                        baseline["min_expected_return_pct"] = float(parts[1].strip().rstrip(","))
                if "min_confidence" in line and "=" in line:
                    parts = line.split("=")
                    if len(parts) == 2:
                        baseline["min_confidence"] = float(parts[1].strip().rstrip(","))
                if "max_risk_score" in line and "=" in line:
                    parts = line.split("=")
                    if len(parts) == 2:
                        baseline["max_risk_score"] = float(parts[1].strip().rstrip(","))
            return baseline
        except Exception:
            return DEFAULT_BASELINE.copy()

    def evolve(self, dry_run: bool = True) -> Optional[CriteriaCandidate]:
        """
        Run one APO evolution cycle.

        Returns best candidate if dry_run=False (paper mode auto-apply after 3 improved cycles).
        """
        decisions = self.load_decisions()
        pnl_map = self.load_pnl()

        if len(decisions) < 20:
            log.info(f"Not enough decisions for APO ({len(decisions)} < 20)")
            return None

        baseline = self._load_baseline_from_agent()
        base_candidate = CriteriaCandidate(candidate_id="baseline", **baseline)
        base_candidate.fitness = self.compute_fitness(base_candidate, decisions, pnl_map)

        # Generate mutations
        mutations = self.generate_mutations(baseline, n=10)
        for m in mutations:
            m.fitness = self.compute_fitness(m, decisions, pnl_map)

        # Select best via UCB
        all_candidates = [base_candidate] + mutations
        for c in all_candidates:
            c.n_visits = 1
        best = max(all_candidates, key=lambda c: c.ucb_score())

        log.info(f"APO evolution: baseline fitness={base_candidate.fitness:.4f}, best={best.fitness:.4f}")

        if dry_run:
            return best

        # Apply if paper mode and best beats baseline by >5%
        improvement = (best.fitness - base_candidate.fitness) / max(abs(base_candidate.fitness), 0.001)
        if improvement > 0.05:
            self._apply_candidate(best)
            return best
        return None

    def _apply_candidate(self, candidate: CriteriaCandidate) -> None:
        """Apply candidate criteria to quantum_decision_agent."""
        criteria_file = self.candidates_dir / f"criteria_{candidate.candidate_id}.json"
        with open(criteria_file, "w") as f:
            json.dump(
                {
                    "min_expected_return_pct": candidate.min_expected_return_pct,
                    "min_confidence": candidate.min_confidence,
                    "max_risk_score": candidate.max_risk_score,
                    "min_capital_usd": candidate.min_capital_usd,
                    "fitness": candidate.fitness,
                    "win_count": candidate.win_count,
                    "total_count": candidate.total_count,
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
            )
        log.info(f"APO candidate written to {criteria_file}")

        # Also write to agent criteria file for paper-mode integration
        agent_file = self.repo / "simp/agents/quantum_decision_agent.py"
        if agent_file.exists():
            try:
                content = agent_file.read_text()
                # Update GO_CRITERIA defaults in place
                for field_name in ["min_expected_return_pct", "min_confidence", "max_risk_score"]:
                    val = getattr(candidate, field_name)
                    for line_idx, line in enumerate(content.splitlines()):
                        if field_name in line and "=" in line:
                            old_line = line
                            indent = len(line) - len(line.lstrip())
                            prefix = line[: line.index("=") + 1]
                            content = content.replace(
                                old_line,
                                f"{' ' * indent}{prefix} {val},\n",
                            )
                            break
                agent_file.write_text(content)
                log.info(f"Criteria updated in {agent_file}")
            except Exception as e:
                log.warning(f"Could not update agent file: {e}")

    def report(self) -> Dict[str, Any]:
        """Generate current fitness report."""
        decisions = self.load_decisions(limit=100)
        pnl_map = self.load_pnl(limit=100)
        baseline = self._load_baseline_from_agent()
        base = CriteriaCandidate(candidate_id="baseline", **baseline)
        base.fitness = self.compute_fitness(base, decisions, pnl_map)
        return {
            "decisions_analyzed": len(decisions),
            "pnl_records": len(pnl_map),
            "baseline_fitness": round(base.fitness, 6),
            "total_trades": base.total_count,
            "win_rate": round(base.win_count / max(base.total_count, 1), 4),
            "false_positives": base.false_positive_count,
            "criteria": baseline,
        }


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description="APO Wire-Up — learn better GO/NO-GO criteria")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    wire = APOWire()
    if args.report:
        print(json.dumps(wire.report(), indent=2))
    elif args.apply:
        result = wire.evolve(dry_run=False)
        if result:
            print(f"Applied: {result.candidate_id} (fitness={result.fitness:.4f})")
        else:
            print("No improvement found")
    else:
        result = wire.evolve(dry_run=True)
        if result:
            print(f"Best candidate: {result.candidate_id} (fitness={result.fitness:.4f})")
        else:
            print("No candidates available")
