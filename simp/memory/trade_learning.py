"""
Trade Learning

Turns raw Gate4 trade logs and PnL ledger records into structured episodes,
lessons, and policy candidates so the system can evolve from execution history.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from simp.memory.knowledge_index import KnowledgeIndex
from simp.memory.system_memory import Episode, Lesson, PolicyCandidate, SystemMemoryStore


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


@dataclass
class TradeLearningReport:
    total_trade_records: int
    live_trade_records: int
    successful_live_trades: int
    insufficient_balance_events: int
    dry_run_records: int
    symbols_with_success: List[str]
    lessons: List[Dict[str, Any]]
    policy_candidates: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trade_records": self.total_trade_records,
            "live_trade_records": self.live_trade_records,
            "successful_live_trades": self.successful_live_trades,
            "insufficient_balance_events": self.insufficient_balance_events,
            "dry_run_records": self.dry_run_records,
            "symbols_with_success": self.symbols_with_success,
            "lessons": self.lessons,
            "policy_candidates": self.policy_candidates,
        }


class TradeLearningEngine:
    """Extracts learning from trade execution artifacts."""

    def __init__(
        self,
        trade_log_path: str = "logs/gate4_trades.jsonl",
        pnl_ledger_path: str = "data/phase4_pnl_ledger.jsonl",
        knowledge_index: Optional[KnowledgeIndex] = None,
    ):
        self.trade_log_path = Path(trade_log_path)
        self.pnl_ledger_path = Path(pnl_ledger_path)
        self.knowledge_index = knowledge_index or KnowledgeIndex()

    def load_artifacts(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        return _load_jsonl(self.trade_log_path), _load_jsonl(self.pnl_ledger_path)

    def analyze(
        self,
        trade_records: Optional[List[Dict[str, Any]]] = None,
        pnl_records: Optional[List[Dict[str, Any]]] = None,
    ) -> TradeLearningReport:
        trades = trade_records if trade_records is not None else _load_jsonl(self.trade_log_path)
        pnl = pnl_records if pnl_records is not None else _load_jsonl(self.pnl_ledger_path)

        live_trades = [record for record in trades if not record.get("dry_run")]
        successful_live = [record for record in live_trades if record.get("result") == "ok"]
        insufficient = [
            record
            for record in live_trades
            if record.get("result") == "insufficient_balance"
        ]
        symbols_with_success = sorted({record.get("symbol") for record in successful_live if record.get("symbol")})

        lessons, policy_candidates = self._derive_lessons(
            trades=trades,
            live_trades=live_trades,
            successful_live=successful_live,
            insufficient_balance=insufficient,
            pnl_records=pnl,
        )

        return TradeLearningReport(
            total_trade_records=len(trades),
            live_trade_records=len(live_trades),
            successful_live_trades=len(successful_live),
            insufficient_balance_events=len(insufficient),
            dry_run_records=sum(1 for record in trades if record.get("dry_run")),
            symbols_with_success=symbols_with_success,
            lessons=lessons,
            policy_candidates=policy_candidates,
        )

    def persist(self, store: SystemMemoryStore) -> TradeLearningReport:
        trades, pnl = self.load_artifacts()
        report = self.analyze(trades, pnl)

        source_episode_ids = self._persist_episodes(store, trades, pnl)

        lesson_ids: List[str] = []
        for lesson_data in report.lessons:
            lesson = Lesson(
                title=lesson_data["title"],
                summary=lesson_data["summary"],
                lesson_type=lesson_data["lesson_type"],
                confidence=lesson_data["confidence"],
                evidence=lesson_data["evidence"],
                source_episode_ids=source_episode_ids,
            )
            lesson_id = store.upsert_lesson(lesson)
            lesson_ids.append(lesson_id)
            self.knowledge_index.add_entry("trade_lessons", {
                "title": lesson.title,
                "summary": lesson.summary,
                "confidence": lesson.confidence,
                "lesson_type": lesson.lesson_type,
                "evidence": lesson.evidence,
            })

        for candidate_data in report.policy_candidates:
            candidate = PolicyCandidate(
                title=candidate_data["title"],
                rationale=candidate_data["rationale"],
                priority=candidate_data["priority"],
                payload=candidate_data["payload"],
                source_lesson_ids=lesson_ids,
            )
            store.upsert_policy_candidate(candidate)
            self.knowledge_index.add_entry("policy_candidates", {
                "title": candidate.title,
                "rationale": candidate.rationale,
                "priority": candidate.priority,
                "payload": candidate.payload,
            })

        self.knowledge_index.update_topic(
            "gate4_trade_learning",
            {
                "code_locations": [
                    "simp/memory/system_memory.py",
                    "simp/memory/trade_learning.py",
                    "scripts/learn_from_trades.py",
                ],
                "decisions": [
                    "Trade outcomes are promoted into structured lessons and policy candidates.",
                ],
                "tags": [
                    "memory",
                    "trade-learning",
                    "gate4",
                    "policy",
                ],
            },
        )

        return report

    def _persist_episodes(
        self,
        store: SystemMemoryStore,
        trade_records: Iterable[Dict[str, Any]],
        pnl_records: Iterable[Dict[str, Any]],
    ) -> List[str]:
        episode_ids: List[str] = []
        for trade in trade_records:
            result = trade.get("result", "unknown")
            summary = (
                f"{trade.get('symbol', 'unknown')} {trade.get('side', 'unknown')} "
                f"result={result}"
            )
            episode = Episode(
                episode_type="trade_execution",
                source="gate4_trades",
                entity=trade.get("client_order_id", trade.get("signal_id", "unknown")),
                summary=summary,
                occurred_at=trade.get("ts", ""),
                payload=trade,
                tags=[
                    "trade",
                    trade.get("symbol", "unknown"),
                    trade.get("side", "unknown").lower(),
                    result,
                ],
            )
            episode_ids.append(store.add_episode(episode))

        for pnl in pnl_records:
            summary = (
                f"{pnl.get('symbol', 'unknown')} {pnl.get('side', 'unknown')} "
                f"ledger exec={pnl.get('exec_usd')}"
            )
            episode = Episode(
                episode_type="pnl_ledger_update",
                source="phase4_pnl_ledger",
                entity=pnl.get("client_order_id", pnl.get("signal_id", "unknown")),
                summary=summary,
                occurred_at=pnl.get("exec_ts", pnl.get("ts", "")),
                payload=pnl,
                tags=["pnl", pnl.get("symbol", "unknown"), pnl.get("side", "unknown").lower()],
            )
            episode_ids.append(store.add_episode(episode))

        return episode_ids

    def _derive_lessons(
        self,
        *,
        trades: List[Dict[str, Any]],
        live_trades: List[Dict[str, Any]],
        successful_live: List[Dict[str, Any]],
        insufficient_balance: List[Dict[str, Any]],
        pnl_records: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        lessons: List[Dict[str, Any]] = []
        policy_candidates: List[Dict[str, Any]] = []

        insufficient_by_signal: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for record in insufficient_balance:
            insufficient_by_signal[record.get("signal_id", "unknown")].append(record)

        clustered_insufficient = {
            signal_id: records
            for signal_id, records in insufficient_by_signal.items()
            if len(records) >= 2
        }
        if clustered_insufficient:
            lessons.append({
                "title": "Capital allocation must be gated before multi-asset fan-out",
                "summary": (
                    "A single signal can emit multiple asset orders that collectively exceed "
                    "available buying power, producing repeated insufficient-fund failures."
                ),
                "lesson_type": "risk_control",
                "confidence": 0.91,
                "evidence": {
                    "clustered_signal_count": len(clustered_insufficient),
                    "sample_signal_ids": sorted(clustered_insufficient.keys())[:5],
                    "insufficient_balance_events": len(insufficient_balance),
                },
            })
            policy_candidates.append({
                "title": "Pre-fan-out capital budget check",
                "rationale": (
                    "Before broadcasting a multi-asset BUY basket, reserve or allocate total "
                    "available quote balance so later legs do not fail operationally."
                ),
                "priority": "high",
                "payload": {
                    "target": "gate4_inbox_consumer",
                    "action": "budget_assets_before_submit",
                    "evidence": sorted(clustered_insufficient.keys())[:5],
                },
            })

        if successful_live:
            symbol_counter = Counter(record.get("symbol") for record in successful_live if record.get("symbol"))
            lessons.append({
                "title": "Live Gate4 execution path is proven on a constrained notional band",
                "summary": (
                    "The Gate4 live path is no longer hypothetical. It is producing confirmed "
                    "Coinbase fills on small BTC and ETH tickets, which means learning should "
                    "optimize execution quality instead of proving basic connectivity."
                ),
                "lesson_type": "execution_validation",
                "confidence": 0.95,
                "evidence": {
                    "successful_live_trades": len(successful_live),
                    "successful_symbols": dict(symbol_counter),
                },
            })

        if pnl_records and successful_live:
            pnl_order_ids = {record.get("client_order_id") for record in pnl_records}
            successful_order_ids = {record.get("client_order_id") for record in successful_live}
            coverage_ratio = (
                len(pnl_order_ids & successful_order_ids) / len(successful_order_ids)
                if successful_order_ids else 0.0
            )
            lessons.append({
                "title": "Execution learning should anchor to the PnL ledger, not just raw trade logs",
                "summary": (
                    "Raw trade logs tell you what the broker tried to do. The PnL ledger tells "
                    "you what the system can learn from economically. Reflection should use both."
                ),
                "lesson_type": "memory_design",
                "confidence": round(max(0.5, coverage_ratio), 2),
                "evidence": {
                    "successful_live_order_ids": len(successful_order_ids),
                    "covered_in_pnl_ledger": len(pnl_order_ids & successful_order_ids),
                    "coverage_ratio": round(coverage_ratio, 3),
                },
            })
            policy_candidates.append({
                "title": "Nightly trade reflection and lesson promotion",
                "rationale": (
                    "A scheduled reflection pass should ingest trade logs and the PnL ledger, "
                    "emit lessons, and promote only high-confidence policy candidates."
                ),
                "priority": "high",
                "payload": {
                    "target": "memory/reflection",
                    "action": "run_trade_reflection",
                    "minimum_confidence": 0.8,
                },
            })

        if trades and sum(1 for record in trades if record.get("dry_run")) > len(live_trades):
            lessons.append({
                "title": "Historical dry-run saturation can distort naive performance learning",
                "summary": (
                    "The archive contains a large dry-run era. Learning loops must separate "
                    "simulation evidence from live execution evidence to avoid false confidence."
                ),
                "lesson_type": "evaluation_hygiene",
                "confidence": 0.88,
                "evidence": {
                    "dry_run_records": sum(1 for record in trades if record.get("dry_run")),
                    "live_trade_records": len(live_trades),
                },
            })

        return lessons, policy_candidates
