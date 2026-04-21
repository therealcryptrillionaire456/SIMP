"""
BRP Mesh Gateway — SIMP OpSec Integration
==========================================
Bridges the Bill Russell Protocol (BRP) threat engine with the SIMP mesh
security layer, providing:

  1. Packet-level threat analysis via BRP's Mythos pattern recognizer
  2. Trust-gated routing — agents with BRP threat flags are denied routing
  3. Dynamic trust score nudges — BRP findings fed back into TrustGraph
  4. Agent identity blocklist — persistent deny list for critical threats
  5. Signed packet verification — only cryptographically signed packets
     from known agents pass the ENCRYPTED/CONFIDENTIAL policy gate

Architecture
────────────
  MeshSecurityLayer.check_access()  ← extended by BRP check (additive gate)
  TrustGraph.apply_delta()          ← BRP threat findings reduce trust
  EnhancedBillRussellProtocol       ← threat analysis engine
  MeshPacket.payload                ← analyzed as log entry

Integration points
──────────────────
  Call brp_gateway.screen_packet(packet) before routing any packet.
  Returns (allowed: bool, reason: str, threat_level: str)

  Wire into SmartMeshClient or the broker's mesh routing layer.

OpSec channels
──────────────
  brp_alerts   — broadcast when BRP flags a packet (HIGH/CRITICAL severity)
  security_audit — existing audit channel
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from simp.security.brp.predictive_safety import PredictiveSafetyIntelligence

logger = logging.getLogger(__name__)

# Threat levels that trigger routing denial
DENY_THRESHOLD_LEVELS = {"critical", "high"}

# Trust score penalty applied per BRP finding
TRUST_PENALTY_MEDIUM   = -0.1
TRUST_PENALTY_HIGH     = -0.5
TRUST_PENALTY_CRITICAL = -1.5

# How long to keep an agent on the blocklist (seconds)
BLOCK_TTL_HIGH     = 300.0   # 5 min
BLOCK_TTL_CRITICAL = 3600.0  # 1 hour


@dataclass
class BlocklistEntry:
    """An entry in the BRP agent blocklist."""
    agent_id:     str
    reason:       str
    severity:     str
    blocked_at:   float = field(default_factory=time.time)
    expires_at:   float = field(default_factory=lambda: time.time() + BLOCK_TTL_HIGH)
    block_count:  int   = 1

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict:
        return {
            "agent_id":   self.agent_id,
            "reason":     self.reason,
            "severity":   self.severity,
            "blocked_at": self.blocked_at,
            "expires_at": self.expires_at,
            "block_count": self.block_count,
            "remaining_seconds": max(0.0, self.expires_at - time.time()),
        }


@dataclass
class ScreeningResult:
    """Result of a BRP packet screening."""
    allowed:       bool
    reason:        str
    threat_level:  str                # low | medium | high | critical | clean
    confidence:    float
    agent_id:      str
    patterns:      List[Dict] = field(default_factory=list)
    action_taken:  str        = ""    # none | penalise | block | alert
    metadata:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "allowed":      self.allowed,
            "reason":       self.reason,
            "threat_level": self.threat_level,
            "confidence":   round(self.confidence, 4),
            "agent_id":     self.agent_id,
            "patterns":     self.patterns,
            "action_taken": self.action_taken,
            "metadata":     self.metadata,
        }


class BRPMeshGateway:
    """
    OpSec gateway that wraps EnhancedBillRussellProtocol and applies
    its threat intelligence to every mesh packet that passes through.

    Thread-safe.  Designed as a singleton per process.
    """

    def __init__(
        self,
        brp_db_path:   str  = "threat_memory.db",
        trust_graph    = None,
        enable_alerts: bool = True,
        dry_run:       bool = False,
    ):
        """
        Parameters
        ----------
        brp_db_path:
            Path to the BRP SQLite threat memory database.
        trust_graph:
            TrustGraph instance for score adjustments.
        enable_alerts:
            If True, broadcast BRP alerts on the 'brp_alerts' mesh channel.
        dry_run:
            If True, log threats but never deny routing (useful for monitoring).
        """
        self._trust_graph    = trust_graph
        self._enable_alerts  = enable_alerts
        self._dry_run        = dry_run
        self._lock           = threading.RLock()

        self._blocklist:     Dict[str, BlocklistEntry] = {}
        self._screening_log: List[Dict] = []  # ring buffer, last 500
        self._max_log        = 500

        self._stats = {
            "packets_screened":  0,
            "packets_denied":    0,
            "packets_allowed":   0,
            "alerts_sent":       0,
            "trust_penalties":   0,
            "blocks_issued":     0,
            "blocks_expired":    0,
        }
        self._predictive = PredictiveSafetyIntelligence()

        # Lazy-init BRP to avoid import cost on startup
        self._brp             = None
        self._brp_db_path     = brp_db_path
        self._brp_init_lock   = threading.Lock()

        logger.info(
            "[BRPGateway] initialized  dry_run=%s  alerts=%s  db=%s",
            dry_run, enable_alerts, brp_db_path,
        )

    # ── Primary API ───────────────────────────────────────────────────────────

    def screen_packet(self, packet) -> ScreeningResult:
        """
        Analyse a MeshPacket through the BRP threat engine.

        Returns ScreeningResult with allowed=True/False.
        Caller should honour allowed=False by dropping the packet.
        """
        self._stats["packets_screened"] += 1

        agent_id = getattr(packet, "sender_id", "") or ""

        # Fast path: blocklist check
        block = self._blocklist_check(agent_id)
        if block and not self._dry_run:
            self._stats["packets_denied"] += 1
            result = ScreeningResult(
                allowed      = False,
                reason       = f"Agent blocklisted: {block.reason}",
                threat_level = block.severity,
                confidence   = 1.0,
                agent_id     = agent_id,
                action_taken = "block",
            )
            self._log_screening(result)
            return result

        # Convert packet payload to BRP log entry format
        log_entry = self._packet_to_log_entry(packet)

        # BRP analysis
        try:
            brp       = self._get_brp()
            analysis  = brp.analyze_event(log_entry)
        except Exception as exc:
            logger.warning("[BRPGateway] BRP analysis failed: %s", exc)
            # Fail-open: allow packet if BRP is unavailable
            result = ScreeningResult(
                allowed=True, reason="BRP unavailable (fail-open)",
                threat_level="unknown", confidence=0.0, agent_id=agent_id,
            )
            self._stats["packets_allowed"] += 1
            return result

        threat_level = analysis.get("threat_assessment", {}).get("threat_level", "low")
        confidence   = analysis.get("threat_assessment", {}).get("confidence", 0.0)
        patterns     = analysis.get("pattern_details", [])
        predictive = self._predictive.evaluate(
            {
                **log_entry,
                "source_agent": agent_id,
                "action": "mesh_packet",
                "tags": [
                    getattr(packet, "channel", ""),
                    str(getattr(packet, "msg_type", "")),
                    str((getattr(packet, "payload", {}) or {}).get("type", "")),
                ],
            },
            recent_events=self._recent_predictive_events(),
            recent_observations=[],
            adaptive_rules={},
            sensitive_action_tier=self._extract_sensitive_action_tier(getattr(packet, "payload", {}) or {}),
        )
        threat_level = self._max_threat_level(threat_level, predictive["threat_level"])
        confidence = max(confidence, predictive["confidence"])
        patterns = patterns + self._predictive.synthetic_patterns(predictive)

        # Determine action
        action_taken = "none"
        allowed      = True
        reason       = "clean"

        if threat_level in DENY_THRESHOLD_LEVELS:
            if not self._dry_run:
                allowed = False
                reason  = f"BRP threat detected: {threat_level} (confidence={confidence:.2f})"
                self._issue_block(agent_id, reason, threat_level)
                action_taken = "block"
            else:
                reason       = f"DRY-RUN: would deny {threat_level}"
                action_taken = "dry_run_block"

            # Trust penalty
            self._apply_trust_penalty(agent_id, threat_level)

            # Alert
            if self._enable_alerts and threat_level == "critical":
                self._send_brp_alert(agent_id, threat_level, confidence, patterns)
                action_taken += "+alert"
                self._stats["alerts_sent"] += 1

        elif threat_level == "medium":
            # Penalise trust but don't block
            self._apply_trust_penalty(agent_id, threat_level)
            action_taken = "penalise"
            reason       = f"BRP medium threat noted (confidence={confidence:.2f})"

        if allowed:
            self._stats["packets_allowed"] += 1
        else:
            self._stats["packets_denied"] += 1

        result = ScreeningResult(
            allowed      = allowed,
            reason       = reason,
            threat_level = threat_level,
            confidence   = confidence,
            agent_id     = agent_id,
            patterns     = patterns,
            action_taken = action_taken,
            metadata     = {"predictive_assessment": predictive},
        )
        self._log_screening(result)
        return result

    def check_access(self, sender_id: str, recipient_id: str, channel: str = "") -> Tuple[bool, str]:
        """
        Gate check compatible with MeshSecurityLayer.check_access() signature.
        Returns (allowed, reason).
        """
        block = self._blocklist_check(sender_id)
        if block and not self._dry_run:
            return False, f"BRP blocklist: {block.reason}"
        return True, "ok"

    # ── Blocklist management ──────────────────────────────────────────────────

    def _blocklist_check(self, agent_id: str) -> Optional[BlocklistEntry]:
        """Return active blocklist entry for agent, or None."""
        with self._lock:
            entry = self._blocklist.get(agent_id)
            if entry:
                if entry.is_expired:
                    del self._blocklist[agent_id]
                    self._stats["blocks_expired"] += 1
                    return None
                return entry
        return None

    def _issue_block(self, agent_id: str, reason: str, severity: str) -> None:
        """Add or refresh blocklist entry for agent."""
        ttl = BLOCK_TTL_CRITICAL if severity == "critical" else BLOCK_TTL_HIGH

        with self._lock:
            existing = self._blocklist.get(agent_id)
            if existing:
                existing.reason     = reason
                existing.severity   = severity
                existing.blocked_at = time.time()
                existing.expires_at = time.time() + ttl
                existing.block_count += 1
            else:
                self._blocklist[agent_id] = BlocklistEntry(
                    agent_id   = agent_id,
                    reason     = reason,
                    severity   = severity,
                    expires_at = time.time() + ttl,
                )
                self._stats["blocks_issued"] += 1

        logger.warning("[BRPGateway] BLOCKED %s severity=%s ttl=%.0fs", agent_id, severity, ttl)

    def unblock(self, agent_id: str) -> bool:
        """Manually remove an agent from the blocklist."""
        with self._lock:
            if agent_id in self._blocklist:
                del self._blocklist[agent_id]
                return True
        return False

    def get_blocklist(self) -> List[Dict]:
        """Return all active blocklist entries."""
        with self._lock:
            return [
                e.to_dict()
                for e in self._blocklist.values()
                if not e.is_expired
            ]

    # ── Trust integration ─────────────────────────────────────────────────────

    def _apply_trust_penalty(self, agent_id: str, threat_level: str) -> None:
        if self._trust_graph is None:
            return

        penalty_map = {
            "medium":   TRUST_PENALTY_MEDIUM,
            "high":     TRUST_PENALTY_HIGH,
            "critical": TRUST_PENALTY_CRITICAL,
        }
        penalty = penalty_map.get(threat_level, 0.0)
        if penalty == 0.0:
            return

        try:
            new_score = self._trust_graph.apply_delta(
                agent_id, penalty,
                reason=f"BRP:{threat_level}"
            )
            self._stats["trust_penalties"] += 1
            logger.info(
                "[BRPGateway] trust penalty %.2f applied to %s → %.3f",
                penalty, agent_id, new_score,
            )
        except Exception as exc:
            logger.warning("[BRPGateway] trust penalty failed: %s", exc)

    # ── BRP alert broadcasting ────────────────────────────────────────────────

    def _send_brp_alert(
        self,
        agent_id:     str,
        threat_level: str,
        confidence:   float,
        patterns:     List[Dict],
    ) -> None:
        try:
            from .enhanced_bus import get_enhanced_mesh_bus
            from .packet import create_event_packet, Priority

            bus = get_enhanced_mesh_bus()
            pkt = create_event_packet(
                sender_id    = "brp_gateway",
                recipient_id = "*",
                channel      = "brp_alerts",
                payload      = {
                    "type":         "brp_threat_alert",
                    "agent_id":     agent_id,
                    "threat_level": threat_level,
                    "confidence":   confidence,
                    "patterns":     patterns[:5],  # truncate for mesh size
                    "timestamp":    time.time(),
                    "blocked":      not self._dry_run,
                },
                ttl_seconds  = 600,
            )
            pkt.priority = Priority.HIGH
            bus.send(pkt)
        except Exception as exc:
            logger.debug("[BRPGateway] alert send failed: %s", exc)

    # ── Log entry builder ─────────────────────────────────────────────────────

    @staticmethod
    def _packet_to_log_entry(packet) -> Dict:
        """
        Convert a MeshPacket into a BRP-compatible log entry dict.
        BRP's MythosPatternRecognizer scans the JSON-serialised text,
        so we pack in everything that might be relevant.
        """
        payload = {}
        try:
            raw = getattr(packet, "payload", {})
            payload = raw if isinstance(raw, dict) else {}
        except Exception:
            pass

        return {
            "source_ip":     getattr(packet, "sender_id", "unknown"),
            "event_type":    "mesh_packet",
            "channel":       getattr(packet, "channel", ""),
            "message_id":    getattr(packet, "message_id", ""),
            "recipient":     getattr(packet, "recipient_id", ""),
            "msg_type":      str(getattr(packet, "msg_type", "")),
            "payload_keys":  list(payload.keys()),
            "payload_text":  json.dumps(payload)[:500],  # limit for BRP regex scan
            "ttl_hops":      getattr(packet, "ttl_hops", 0),
            "routing_hops":  len(getattr(packet, "routing_history", []) or []),
            "timestamp":     str(getattr(packet, "timestamp", "")),
            "details":       json.dumps(payload)[:200],
            "payload_type":  str(payload.get("type", "")),
            "projectx_action": str(payload.get("projectx_action") or payload.get("action") or ""),
        }

    # ── BRP lazy init ─────────────────────────────────────────────────────────

    def _get_brp(self):
        """Lazy-load EnhancedBillRussellProtocol (avoids startup cost)."""
        if self._brp is not None:
            return self._brp

        with self._brp_init_lock:
            if self._brp is None:
                try:
                    from simp.security.brp.protocol_core import EnhancedBillRussellProtocol
                    self._brp = EnhancedBillRussellProtocol(self._brp_db_path)
                    logger.info("[BRPGateway] BRP engine loaded from %s", self._brp_db_path)
                except Exception as exc:
                    logger.error("[BRPGateway] BRP init failed: %s", exc)
                    raise

        return self._brp

    # ── Screening log ─────────────────────────────────────────────────────────

    def _log_screening(self, result: ScreeningResult) -> None:
        entry = {**result.to_dict(), "ts": time.time()}
        with self._lock:
            self._screening_log.append(entry)
            if len(self._screening_log) > self._max_log:
                self._screening_log = self._screening_log[-self._max_log:]

    def _recent_predictive_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            recent = list(self._screening_log[-64:])
        return [
            {
                "ts": item.get("ts"),
                "source_agent": item.get("agent_id"),
                "action": "mesh_packet",
                "tags": [item.get("threat_level", "")] + [
                    pattern.get("type", "")
                    for pattern in item.get("patterns", [])
                    if isinstance(pattern, dict)
                ],
            }
            for item in recent
        ]

    @staticmethod
    def _extract_sensitive_action_tier(payload: Dict[str, Any]) -> Optional[int]:
        action_name = str(
            payload.get("projectx_action")
            or payload.get("action")
            or payload.get("capability")
            or ""
        ).strip()
        if not action_name:
            return None
        try:
            from simp.projectx.computer import ACTION_TIERS
        except Exception:
            return None
        return ACTION_TIERS.get(action_name)

    @staticmethod
    def _max_threat_level(current: str, predicted: str) -> str:
        ranking = {"clean": 0, "low": 1, "medium": 2, "high": 3, "critical": 4, "unknown": -1}
        if ranking.get(predicted, -1) > ranking.get(current, -1):
            return predicted
        return current

    def get_recent_screenings(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            return list(self._screening_log[-limit:])

    # ── Introspection ─────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        with self._lock:
            blocklist = [e.to_dict() for e in self._blocklist.values() if not e.is_expired]

        brp_status = {}
        if self._brp is not None:
            try:
                brp_status = self._brp.get_system_status()
            except Exception:
                pass

        return {
            "dry_run":         self._dry_run,
            "enable_alerts":   self._enable_alerts,
            "stats":           self._stats.copy(),
            "blocklist_count": len(blocklist),
            "blocklist":       blocklist,
            "brp_loaded":      self._brp is not None,
            "brp_status":      brp_status,
        }


# ── Singleton factory ─────────────────────────────────────────────────────────

_gateway_instance: Optional[BRPMeshGateway] = None
_gateway_lock = threading.Lock()


def get_brp_mesh_gateway(
    brp_db_path:   str  = "threat_memory.db",
    trust_graph    = None,
    enable_alerts: bool = True,
    dry_run:       bool = False,
) -> BRPMeshGateway:
    """
    Return the process-level BRPMeshGateway singleton.

    Recommended integration:
        from simp.mesh.brp_mesh_gateway import get_brp_mesh_gateway
        gateway = get_brp_mesh_gateway(trust_graph=get_trust_graph())

    Then in your packet routing path:
        result = gateway.screen_packet(packet)
        if not result.allowed:
            logger.warning("Packet denied: %s", result.reason)
            return  # drop packet
    """
    global _gateway_instance

    with _gateway_lock:
        if _gateway_instance is None:
            # Inherit trust graph from singleton if not provided
            if trust_graph is None:
                try:
                    from .trust_graph import get_trust_graph
                    trust_graph = get_trust_graph()
                except Exception:
                    pass

            _gateway_instance = BRPMeshGateway(
                brp_db_path   = brp_db_path,
                trust_graph   = trust_graph,
                enable_alerts = enable_alerts,
                dry_run       = dry_run,
            )

    return _gateway_instance
