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
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional

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
    ):
        self.agent_id = agent_id
        self.broker_url = broker_url
        self.db_path = db_path
        self.min_savings_usd = min_savings_usd
        self.auto_invest = auto_invest

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()
        self._receipts_processed = 0
        self._savings_accumulated = 0.0
        self._investments_made = 0

        self._message_handlers: List[Callable] = []

        # Ensure DB schema
        _ensure_db(db_path)

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
                source=self.agent_id,
                event_type="agent_online",
                data={
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
                channel="system_alerts",
            )
            self._bus.publish(announce)
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
                messages = self._bus.get_messages(self.agent_id, max_messages=20)
                for msg in messages:
                    self._dispatch(msg)
            except Exception as e:
                logger.warning(f"[KTC] Processing loop error: {e}")
            time.sleep(0.1)

    def _dispatch(self, packet) -> None:
        """Route an inbound mesh packet to the right handler."""
        try:
            channel = getattr(packet, "channel", None)
            msg_type = getattr(packet, "message_type", None)
            data = getattr(packet, "data", {}) or {}

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

        if amount_usd < self.min_savings_usd:
            return

        # Mock crypto conversion (SOL @ $150)
        sol_price = 150.0
        sol_amount = round(amount_usd / sol_price, 6)
        tx_hash = f"mock_tx_{uuid.uuid4().hex[:16]}"

        investment_id = str(uuid.uuid4())
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR IGNORE INTO ktc_investments VALUES (?,?,?,?,?,?,datetime('now'))",
                (investment_id, user_id, amount_usd, "SOL", sol_amount, "completed"),
            )
            conn.execute(
                "UPDATE ktc_users SET total_invested = total_invested + ? WHERE id = ?",
                (amount_usd, user_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[KTC] DB investment write error: {e}")

        self._investments_made += 1

        self._publish_event("investment_confirmed", {
            "investment_id": investment_id,
            "user_id": user_id,
            "amount_usd": amount_usd,
            "crypto_asset": "SOL",
            "crypto_amount": sol_amount,
            "tx_hash": tx_hash,
        }, channel="ktc_investment_confirmations")

        logger.info(
            f"[KTC] Investment  user={user_id}  "
            f"${amount_usd:.4f} → {sol_amount} SOL  tx={tx_hash}"
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
        try:
            from simp.mesh.packet import create_event_packet
            pkt = create_event_packet(
                source=self.agent_id,
                event_type=event_type,
                data=data,
                channel=channel,
            )
            self._bus.publish(pkt)
        except Exception as e:
            logger.warning(f"[KTC] Publish error: {e}")

    # ── status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "running": self._running,
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "receipts_processed": self._receipts_processed,
            "savings_accumulated_usd": round(self._savings_accumulated, 4),
            "investments_made": self._investments_made,
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
) -> KTCMeshAgent:
    global _ktc_agent
    with _ktc_lock:
        if _ktc_agent is None:
            _ktc_agent = KTCMeshAgent(agent_id=agent_id, broker_url=broker_url)
            if autostart:
                _ktc_agent.start()
    return _ktc_agent
