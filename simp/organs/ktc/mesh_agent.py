"""
KTC Mesh Agent — Direct SIMP Mesh Integration
==============================================
Wires Keep the Change directly into the EnhancedMeshBus without Flask.

This is the mesh-native path.  The Flask HTTP API (start_ktc.py) is
still available for external callers, but the agent's core logic lives
here and participates in the mesh immediately on startup.

Channels
--------
  ktc_intents          — inbound receipt / savings / investment requests
  ktc_events           — outbound savings events + investment confirmations
  quantumarb_trades    — listens for completed trades to route change
  system_alerts        — broadcast alerts
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("simp.organs.ktc.mesh_agent")


# ── helpers ───────────────────────────────────────────────────────────────────

def _ensure_db(db_path: str = "ktc.db") -> None:
    """Ensure KTC SQLite schema exists."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS ktc_users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            wallet_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_savings REAL DEFAULT 0.0,
            total_invested REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS ktc_receipts (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            store_name TEXT,
            total_amount REAL,
            savings_amount REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ktc_investments (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            amount_usd REAL,
            crypto_asset TEXT DEFAULT 'SOL',
            crypto_amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ── main class ────────────────────────────────────────────────────────────────

class KTCMeshAgent:
    """
    Keep The Change — mesh-native agent.

    Registers with the EnhancedMeshBus, subscribes to KTC-relevant
    channels, and routes savings-to-investment logic over the mesh.
    """

    SUBSCRIBE_CHANNELS = [
        "ktc_intents",
        "ktc_savings",
        "quantumarb_trades",   # listen for completed arb trades
        "system_alerts",
    ]
    BROADCAST_CHANNELS = [
        "ktc_events",
        "ktc_investment_confirmations",
    ]

    def __init__(
        self,
        agent_id: str = "ktc_agent",
        broker_url: str = "http://127.0.0.1:5555",
        db_path: str = "ktc.db",
        min_savings_usd: float = 0.01,
        auto_invest: bool = True,
        quantumarb_inbox: Optional[str] = None,
        live_execution_enabled: Optional[bool] = None,
    ):
        self.agent_id = agent_id
        self.broker_url = broker_url
        self.db_path = db_path
        self.min_savings_usd = min_savings_usd
        self.auto_invest = auto_invest
        self.live_execution_enabled = (
            _env_flag("KTC_LIVE_EXECUTION_ENABLED", default=False)
            if live_execution_enabled is None
            else live_execution_enabled
        )
        self.quantumarb_inbox = Path(
            quantumarb_inbox
            or os.getenv("KTC_QUANTUMARB_INBOX")
            or "data/quantumarb_phase4/inbox"
        )
        self.legacy_quantumarb_inbox = Path(
            os.getenv("KTC_QUANTUMARB_LEGACY_INBOX", "data/inboxes/quantumarb_real")
        )

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()
        self._receipts_processed = 0
        self._savings_accumulated = 0.0
        self._investments_made = 0
        self._investments_queued = 0
        self._routing_failures = 0
        self._last_routed_request_id: Optional[str] = None

        self._message_handlers: List[Callable] = []

        # Ensure DB schema
        _ensure_db(db_path)
        self.quantumarb_inbox.mkdir(parents=True, exist_ok=True)

        logger.info(f"[KTC] KTCMeshAgent initialized — agent_id={agent_id}")

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> "KTCMeshAgent":
        """Connect to the mesh bus and start listening."""
        from simp.mesh.enhanced_bus import get_enhanced_mesh_bus
        from simp.mesh.packet import create_event_packet

        self._bus = get_enhanced_mesh_bus()
        self._bus.register_agent(self.agent_id)

        for channel in self.SUBSCRIBE_CHANNELS:
            self._bus.subscribe(self.agent_id, channel)
            logger.debug(f"[KTC] Subscribed to channel: {channel}")

        self._running = True
        self._thread = threading.Thread(
            target=self._processing_loop, daemon=True, name="ktc-mesh-loop"
        )
        self._thread.start()

        # Announce presence
        try:
            announce = create_event_packet(
                sender_id=self.agent_id,
                recipient_id="*",
                channel="system_alerts",
                payload={
                    "event_type": "agent_online",
                    "agent_id": self.agent_id,
                    "capabilities": [
                        "receipt_processing",
                        "price_comparison",
                        "savings_calculation",
                        "crypto_investment",
                        "wallet_management",
                    ],
                    "channels": self.SUBSCRIBE_CHANNELS,
                    "timestamp": time.time(),
                },
            )
            self._bus.send(announce)
        except Exception as e:
            logger.warning(f"[KTC] Could not broadcast online announcement: {e}")

        logger.info(f"[KTC] Mesh agent started — listening on {self.SUBSCRIBE_CHANNELS}")
        return self

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[KTC] Mesh agent stopped")

    # ── processing loop ───────────────────────────────────────────────────────

    def _processing_loop(self) -> None:
        while self._running:
            try:
                messages = self._bus.receive(self.agent_id, max_messages=20)
                for msg in messages:
                    self._dispatch(msg)
            except Exception as e:
                logger.warning(f"[KTC] Processing loop error: {e}")
            time.sleep(0.1)

    def _dispatch(self, packet) -> None:
        """Route an inbound mesh packet to the right handler."""
        try:
            channel = getattr(packet, "channel", None)
            msg_type = getattr(packet, "msg_type", getattr(packet, "message_type", None))
            data = getattr(packet, "payload", getattr(packet, "data", {})) or {}

            if channel == "ktc_intents":
                intent_type = data.get("intent_type", "")
                if intent_type == "process_receipt":
                    self._handle_receipt(data)
                elif intent_type == "compare_prices":
                    self._handle_price_comparison(data)
                elif intent_type == "create_investment":
                    self._handle_investment(data)

            elif channel == "quantumarb_trades":
                # A completed trade arrived — route the "change" to savings
                self._handle_trade_change(data)

            elif channel == "system_alerts":
                pass  # monitor only

        except Exception as e:
            logger.warning(f"[KTC] Dispatch error: {e}")

        for handler in self._message_handlers:
            try:
                handler(packet)
            except Exception:
                pass

    # ── intent handlers ───────────────────────────────────────────────────────

    def _handle_receipt(self, data: Dict) -> None:
        user_id = data.get("user_id", "anonymous")
        store = data.get("store_name", "unknown")
        total = float(data.get("total_amount", 0.0))
        items = data.get("items", [])

        # Calculate mock savings (10% baseline for now)
        savings = round(total * 0.10, 2)
        receipt_id = str(uuid.uuid4())

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR IGNORE INTO ktc_receipts VALUES (?,?,?,?,?,datetime('now'))",
                (receipt_id, user_id, store, total, savings),
            )
            conn.execute(
                "UPDATE ktc_users SET total_savings = total_savings + ? WHERE id = ?",
                (savings, user_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[KTC] DB write error: {e}")

        self._receipts_processed += 1
        self._savings_accumulated += savings

        # Broadcast savings event
        self._publish_event("savings_calculated", {
            "receipt_id": receipt_id,
            "user_id": user_id,
            "store": store,
            "total": total,
            "savings": savings,
        })

        logger.info(f"[KTC] Receipt processed  user={user_id}  savings=${savings:.2f}")

        # Auto-invest if threshold met
        if self.auto_invest and savings >= self.min_savings_usd:
            self._handle_investment({"user_id": user_id, "amount_usd": savings})

    def _handle_price_comparison(self, data: Dict) -> None:
        items = data.get("items", [])
        # Mock response — real impl would query price APIs
        opportunities = [
            {
                "item": item.get("name", "item"),
                "current_price": item.get("price", 1.0),
                "cheaper_price": round(item.get("price", 1.0) * 0.85, 2),
                "store": "SaveMart",
                "savings": round(item.get("price", 1.0) * 0.15, 2),
            }
            for item in items[:5]
        ]
        self._publish_event("price_comparison_result", {
            "user_id": data.get("user_id"),
            "opportunities": opportunities,
            "total_potential_savings": sum(o["savings"] for o in opportunities),
        })

    def _handle_investment(self, data: Dict) -> None:
        user_id = data.get("user_id", "anonymous")
        amount_usd = float(data.get("amount_usd", 0.0))
        receipt_id = data.get("receipt_id")
        auto_approve = bool(data.get("auto_approve", True))

        if amount_usd < self.min_savings_usd:
            return

        routing = self.queue_investment_request(
            user_id=user_id,
            amount_usd=amount_usd,
            receipt_id=receipt_id,
            auto_approve=auto_approve,
            source="ktc_mesh_agent",
            metadata=data.get("metadata"),
        )
        logger.info(
            "[KTC] Investment routed  user=%s  amount=$%.4f  status=%s  request=%s",
            user_id,
            amount_usd,
            routing["status"],
            routing["investment_id"],
        )

    def _handle_trade_change(self, data: Dict) -> None:
        """When QuantumArb completes a trade, round up profit and invest the change."""
        profit = float(data.get("profit_usd", 0.0))
        if profit <= 0:
            return
        change = round(profit % 1.0, 4)   # fractional dollar = "the change"
        if change >= self.min_savings_usd:
            logger.info(f"[KTC] Routing trade change  ${change:.4f} → investment")
            self._handle_investment({"user_id": "quantumarb_auto", "amount_usd": change})

    # ── publishing ────────────────────────────────────────────────────────────

    def _publish_event(self, event_type: str, data: Dict, channel: str = "ktc_events") -> None:
        if not hasattr(self, "_bus"):
            return
        try:
            from simp.mesh.packet import create_event_packet
            pkt = create_event_packet(
                sender_id=self.agent_id,
                recipient_id="*",
                channel=channel,
                payload={"event_type": event_type, **data},
            )
            self._bus.send(pkt)
        except Exception as e:
            logger.warning(f"[KTC] Publish error: {e}")

    def _queue_targets(self) -> List[Path]:
        targets = [self.quantumarb_inbox]
        if (
            self.legacy_quantumarb_inbox != self.quantumarb_inbox
            and self.legacy_quantumarb_inbox.exists()
        ):
            targets.append(self.legacy_quantumarb_inbox)
        return targets

    def _write_quantumarb_queue_files(self, payload: Dict[str, Any]) -> List[str]:
        written_paths: List[str] = []
        filename = f"ktc_investment_{payload['intent_id']}.json"
        for target in self._queue_targets():
            target.mkdir(parents=True, exist_ok=True)
            path = target / filename
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            written_paths.append(str(path))
        return written_paths

    def queue_investment_request(
        self,
        user_id: str,
        amount_usd: float,
        receipt_id: Optional[str] = None,
        auto_approve: bool = True,
        source: str = "ktc_api",
        asset: str = "SOL",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        amount_usd = round(float(amount_usd), 2)
        if amount_usd < self.min_savings_usd:
            raise ValueError(
                f"amount_usd must be at least {self.min_savings_usd:.2f}"
            )

        review_required = (not self.live_execution_enabled) or (not auto_approve) or amount_usd >= 50
        status = "pending_review" if review_required else "queued"
        investment_id = str(uuid.uuid4())
        queued_at = datetime.now(timezone.utc).isoformat()

        intent_payload = {
            "intent_id": investment_id,
            "intent_type": "ktc_investment_request",
            "source_agent": source,
            "target_agent": "quantumarb_phase4",
            "timestamp": queued_at,
            "status": status,
            "params": {
                "request_kind": "spot_accumulate",
                "user_id": user_id,
                "amount_usd": amount_usd,
                "asset": asset,
                "quote_asset": "USD",
                "receipt_id": receipt_id,
                "auto_approve": auto_approve,
                "review_required": review_required,
                "live_execution_enabled": self.live_execution_enabled,
            },
            "payload": {
                "user_id": user_id,
                "amount_usd": amount_usd,
                "asset": asset,
                "quote_asset": "USD",
                "receipt_id": receipt_id,
                "review_required": review_required,
            },
            "metadata": {
                "origin": "ktc",
                "observable": True,
                "queue_targets": [str(path) for path in self._queue_targets()],
                **(metadata or {}),
            },
        }

        written_paths = self._write_quantumarb_queue_files(intent_payload)

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO ktc_investments VALUES (?,?,?,?,?,?,datetime('now'))",
                (investment_id, user_id, amount_usd, asset, None, status),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            self._routing_failures += 1
            logger.warning(f"[KTC] DB investment queue write error: {e}")
            raise

        self._investments_queued += 1
        self._last_routed_request_id = investment_id

        event_type = "investment_pending_review" if review_required else "investment_queued"
        self._publish_event(
            event_type,
            {
                "investment_id": investment_id,
                "user_id": user_id,
                "amount_usd": amount_usd,
                "crypto_asset": asset,
                "queue_paths": written_paths,
                "live_execution_enabled": self.live_execution_enabled,
                "review_required": review_required,
            },
            channel="ktc_investment_confirmations",
        )

        return {
            "status": status,
            "investment_id": investment_id,
            "user_id": user_id,
            "amount_usd": amount_usd,
            "asset": asset,
            "queue_paths": written_paths,
            "receipt_id": receipt_id,
            "review_required": review_required,
            "live_execution_enabled": self.live_execution_enabled,
            "queued_at": queued_at,
        }

    # ── status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "running": self._running,
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "receipts_processed": self._receipts_processed,
            "savings_accumulated_usd": round(self._savings_accumulated, 4),
            "investments_made": self._investments_made,
            "investments_queued": self._investments_queued,
            "routing_failures": self._routing_failures,
            "last_routed_request_id": self._last_routed_request_id,
            "quantumarb_inbox": str(self.quantumarb_inbox),
            "live_execution_enabled": self.live_execution_enabled,
            "subscribe_channels": self.SUBSCRIBE_CHANNELS,
            "broadcast_channels": self.BROADCAST_CHANNELS,
        }


# ── singleton ─────────────────────────────────────────────────────────────────

_ktc_agent: Optional[KTCMeshAgent] = None
_ktc_lock = threading.Lock()


def get_ktc_mesh_agent(
    agent_id: str = "ktc_agent",
    broker_url: str = "http://127.0.0.1:5555",
    autostart: bool = True,
    db_path: str = "ktc.db",
    quantumarb_inbox: Optional[str] = None,
    live_execution_enabled: Optional[bool] = None,
) -> KTCMeshAgent:
    global _ktc_agent
    with _ktc_lock:
        if _ktc_agent is None:
            _ktc_agent = KTCMeshAgent(
                agent_id=agent_id,
                broker_url=broker_url,
                db_path=db_path,
                quantumarb_inbox=quantumarb_inbox,
                live_execution_enabled=live_execution_enabled,
            )
            if autostart:
                _ktc_agent.start()
    return _ktc_agent
