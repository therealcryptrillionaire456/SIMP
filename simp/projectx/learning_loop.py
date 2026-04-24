"""
ProjectX Learning Loop — Phase 3 (Continuous Learning)

Background daemon that runs the full self-improvement pipeline on a
configurable schedule. Ties together every projectx subsystem plus
the SIMP system memory and trade learning layers.

Each iteration:
  1. Ingest new trade/operation logs via TradeLearning
  2. Run MetaLearner cycle (episodes → lessons → policies → RAG)
  3. Trigger APO optimization step
  4. Record evolution snapshot
  5. Run safety health sweep
  6. Broadcast summary to mesh (projectx_learning channel)
  7. Sleep until next cycle

Designed to run as a daemon thread alongside the mesh bridge — it
never blocks the calling thread.

Usage::

    from simp.projectx.learning_loop import LearningLoop
    loop = LearningLoop()
    loop.start()          # starts background thread, returns immediately
    loop.stop()           # graceful shutdown
    status = loop.status()
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 300    # 5 minutes between cycles
MIN_INTERVAL = 60         # never faster than 1 minute


@dataclass
class LoopStatus:
    running: bool = False
    cycles_completed: int = 0
    last_cycle_ts: float = 0.0
    last_cycle_duration_ms: int = 0
    last_error: Optional[str] = None
    total_lessons: int = 0
    total_policies: int = 0
    evolution_trend: str = "unknown"
    on_track_for_2x: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "cycles_completed": self.cycles_completed,
            "last_cycle_ts": self.last_cycle_ts,
            "last_cycle_duration_ms": self.last_cycle_duration_ms,
            "last_error": self.last_error,
            "total_lessons": self.total_lessons,
            "total_policies": self.total_policies,
            "evolution_trend": self.evolution_trend,
            "on_track_for_2x": self.on_track_for_2x,
        }


class LearningLoop:
    """
    Background continuous learning daemon for ProjectX.

    Composes all self-improvement subsystems into a repeating cycle.
    """

    def __init__(
        self,
        interval: float = DEFAULT_INTERVAL,
        executor=None,
        broker_url: str = "http://127.0.0.1:5555",
        config=None,
    ) -> None:
        self._interval = max(interval, MIN_INTERVAL)
        self._executor = executor
        self._broker_url = broker_url
        self._config = config

        # Lazily initialised subsystems
        self._rag = None
        self._safety = None
        self._apo = None
        self._meta_learner = None
        self._tracker = None
        self._orchestrator = None

        self._status = LoopStatus()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._watchdog: Optional[Any] = None  # Watchdog instance

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self, run_immediately: bool = False) -> None:
        """Start the background learning thread (with watchdog restart)."""
        if self._thread and self._thread.is_alive():
            logger.warning("LearningLoop already running")
            return
        self._stop_event.clear()
        self._status.running = True

        def _make_thread() -> threading.Thread:
            t = threading.Thread(
                target=self._run,
                args=(run_immediately,),
                daemon=True,
                name="ProjectXLearningLoop",
            )
            t.start()
            return t

        self._thread = _make_thread()

        # Watchdog monitors the loop thread and restarts on silent death
        try:
            from simp.projectx.hardening import Watchdog
            self._watchdog = Watchdog(
                name="LearningLoop",
                factory=_make_thread,
                check_interval=self._interval * 2,
                max_restarts=5,
                cooldown=10.0,
            )
            self._watchdog.start()
        except Exception as exc:
            logger.debug("Watchdog unavailable: %s", exc)

        logger.info("LearningLoop started (interval=%ds)", int(self._interval))

    def stop(self, timeout: float = 10.0) -> None:
        """Signal the loop to stop and wait for the thread to exit."""
        self._stop_event.set()
        self._status.running = False
        if self._watchdog:
            self._watchdog.stop()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("LearningLoop stopped after %d cycles", self._status.cycles_completed)

    def run_once(self) -> Dict[str, Any]:
        """Run a single learning cycle synchronously (useful for testing)."""
        return self._cycle()

    def status(self) -> Dict[str, Any]:
        return self._status.to_dict()

    # ── Main loop ─────────────────────────────────────────────────────────

    def _run(self, run_immediately: bool) -> None:
        if not run_immediately:
            # Stagger the first run so startup doesn't overload the system
            self._stop_event.wait(timeout=30)
        while not self._stop_event.is_set():
            t0 = time.time()
            try:
                result = self._cycle()
                self._status.cycles_completed += 1
                self._status.last_cycle_ts = t0
                self._status.last_cycle_duration_ms = int((time.time() - t0) * 1000)
                self._status.last_error = None
                self._status.total_lessons += result.get("lessons_promoted", 0)
                self._status.total_policies += result.get("policies_proposed", 0)
                self._status.evolution_trend = result.get("evolution_trend", "unknown")
                self._status.on_track_for_2x = result.get("on_track_for_2x", False)
                logger.info(
                    "LearningLoop cycle %d done in %dms — trend=%s",
                    self._status.cycles_completed,
                    self._status.last_cycle_duration_ms,
                    self._status.evolution_trend,
                )
            except Exception as exc:
                logger.error("LearningLoop cycle error: %s", exc)
                self._status.last_error = str(exc)

            self._stop_event.wait(timeout=self._interval)

    # ── Cycle implementation ──────────────────────────────────────────────

    def _cycle(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        # 1. Initialise subsystems lazily (first call only)
        self._init_subsystems()

        # 2. Ingest trade logs via TradeLearning (if available)
        self._ingest_trade_logs()

        # 3. MetaLearner cycle
        ml_report = None
        if self._meta_learner:
            try:
                ml_report = self._meta_learner.run_cycle()
                result["lessons_promoted"] = ml_report.lessons_promoted
                result["policies_proposed"] = ml_report.policies_proposed
                result["rag_entries_added"] = ml_report.rag_entries_added
                if ml_report.error:
                    logger.warning("MetaLearner error: %s", ml_report.error)
            except Exception as exc:
                logger.warning("MetaLearner cycle failed: %s", exc)

        # 4. APO optimisation step (lightweight — just evolves population)
        if self._apo:
            try:
                self._apo._evolve()
                result["apo_generation"] = self._apo._generation
            except Exception as exc:
                logger.debug("APO evolve failed: %s", exc)

        # 5. Evolution snapshot
        if self._tracker:
            try:
                evo_report = self._tracker.track_cycle(
                    safety_monitor=self._safety,
                    apo_engine=self._apo,
                    rag_memory=self._rag,
                    meta_learner_report=ml_report,
                )
                result["evolution_trend"] = evo_report.trend
                result["on_track_for_2x"] = evo_report.on_track_for_2x
                result["targets_met"] = evo_report.targets_met
            except Exception as exc:
                logger.warning("Evolution tracking failed: %s", exc)

        # 6. Safety health sweep
        if self._safety:
            try:
                alerts = self._safety.check_alerts()
                result["safety_alerts"] = len(alerts)
                for alert in alerts:
                    if alert.severity.value == "CRITICAL":
                        logger.critical("[LearningLoop] Safety alert: %s", alert.message)
            except Exception as exc:
                logger.debug("Safety sweep failed: %s", exc)

        # 7. Broadcast summary to mesh
        self._broadcast_summary(result)

        return result

    def _ingest_trade_logs(self) -> None:
        try:
            from simp.memory.trade_learning import TradeLearner
            from simp.memory.system_memory import SystemMemoryStore
            store = SystemMemoryStore()
            learner = TradeLearner(store=store)
            report = learner.run()
            if self._rag and report:
                for lesson in (report.lessons or []):
                    summary = lesson.get("summary") or lesson.get("title", "")
                    if summary:
                        self._rag.store(summary, source="trade_learning", ttl=30 * 24 * 3600)
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("Trade log ingestion failed: %s", exc)

    def _broadcast_summary(self, result: Dict[str, Any]) -> None:
        try:
            from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
            from simp.mesh.packet import create_event_packet, Priority
            bus = get_enhanced_mesh_bus()
            pkt = create_event_packet(
                sender_id="projectx_learning_loop",
                recipient_id="*",
                channel="projectx_learning",
                payload={
                    "cycle": self._status.cycles_completed,
                    "timestamp": time.time(),
                    **result,
                },
                ttl_seconds=600,
            )
            pkt.priority = Priority.LOW
            bus.send(pkt)
        except Exception as exc:
            logger.debug("Mesh broadcast failed: %s", exc)

    # ── Lazy initialisation ───────────────────────────────────────────────

    def _init_subsystems(self) -> None:
        if self._rag is None:
            try:
                from simp.projectx.rag_memory import get_rag_memory
                self._rag = get_rag_memory()
            except Exception:
                pass

        if self._safety is None:
            try:
                from simp.projectx.safety_monitor import get_safety_monitor
                self._safety = get_safety_monitor()
            except Exception:
                pass

        if self._apo is None:
            try:
                from simp.projectx.apo_engine import APOEngine
                self._apo = APOEngine(
                    base_prompt="Answer the following question thoughtfully: {goal}",
                    task_name="learning_loop",
                    persist_path="./projectx_logs/apo_learning_loop.jsonl",
                )
            except Exception:
                pass

        if self._meta_learner is None:
            try:
                from simp.projectx.meta_learner import MetaLearner
                self._meta_learner = MetaLearner(
                    rag_memory=self._rag,
                    safety_monitor=self._safety,
                    apo_engine=self._apo,
                )
            except Exception as exc:
                logger.debug("MetaLearner init failed: %s", exc)

        if self._tracker is None:
            try:
                from simp.projectx.evolution_tracker import get_evolution_tracker
                self._tracker = get_evolution_tracker()
            except Exception:
                pass


# Module-level singleton
_loop: Optional[LearningLoop] = None
_loop_lock = threading.Lock()


def get_learning_loop(interval: float = DEFAULT_INTERVAL, executor=None) -> LearningLoop:
    global _loop
    with _loop_lock:
        if _loop is None:
            _loop = LearningLoop(interval=interval, executor=executor)
    return _loop


def start_learning_loop(interval: float = DEFAULT_INTERVAL, executor=None) -> LearningLoop:
    """Convenience: get singleton and start if not running."""
    loop = get_learning_loop(interval=interval, executor=executor)
    if not loop._status.running:
        loop.start()
    return loop
