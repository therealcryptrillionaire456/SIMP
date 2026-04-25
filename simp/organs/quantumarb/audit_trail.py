"""
Audit Log + Tax Reporter Integration — T28
===========================================
Wire each execution event into tax_reporter + a tamper-evident audit log
for compliance.

Each trade execution creates:
  1. Tax lot record (for cost basis tracking)
  2. Disposition record (for realized gains/losses)
  3. Tamper-evident audit log entry (SHA-256 chained hash)

The audit log uses a hash chain: each entry includes the hash of the
previous entry, making retrospective tampering detectable.

Usage:
    audit = AuditTrail(tax_reporter=reporter)
    audit.record_execution({
        "execution_id": "exec_123",
        "asset": "BTC",
        "quantity": 0.001,
        "price_usd": 65000.0,
        "side": "buy",
        "venue": "coinbase",
        "fees_usd": 0.65,
        "timestamp": "...",
    })
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("audit_trail")


@dataclass
class AuditEntry:
    """A single entry in the tamper-evident audit log."""
    entry_id: str
    execution_id: str
    event_type: str           # acquisition, disposition, rollback, fee_tier_change, etc.
    asset: str
    quantity: float
    price_usd: float
    side: str                  # buy, sell
    venue: str
    fees_usd: float
    pnl_usd: float = 0.0
    previous_hash: str = ""    # Hash of the previous entry (SHA-256)
    entry_hash: str = ""       # Hash of this entry
    extra: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.entry_hash:
            self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry's content."""
        content = json.dumps({
            "entry_id": self.entry_id,
            "execution_id": self.execution_id,
            "event_type": self.event_type,
            "asset": self.asset,
            "quantity": self.quantity,
            "price_usd": self.price_usd,
            "side": self.side,
            "venue": self.venue,
            "fees_usd": self.fees_usd,
            "pnl_usd": self.pnl_usd,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "extra": self.extra,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditTrail:
    """
    Tamper-evident audit log with hash-chain integrity.

    Each new entry includes the SHA-256 hash of the previous entry,
    making it computationally infeasible to modify historical records
    without detection.

    Integrates with TaxReporter for automatic tax lot creation.

    Thread-safe. Persists to append-only JSONL.
    """

    def __init__(
        self,
        log_dir: str = "data/audit",
        tax_reporter: Optional[Any] = None,
    ):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._entries: List[AuditEntry] = []
        self._tax_reporter = tax_reporter
        self._last_hash: str = ""  # SHA-256 of the most recent entry

        # Load existing entries to maintain hash chain
        self._load_entries()

        log.info(
            "AuditTrail initialized (entries=%d, tax_reporter=%s)",
            len(self._entries),
            tax_reporter is not None,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def record_execution(self, execution: Dict[str, Any]) -> AuditEntry:
        """
        Record a trade execution in the audit log.

        If a TaxReporter is configured, also creates tax lots/dispositions.

        Args:
            execution: Dict with keys:
                execution_id, asset, quantity, price_usd, side, venue,
                fees_usd, pnl_usd (optional), extra (optional)

        Returns:
            AuditEntry with hash chain link
        """
        entry_id = self._next_id()

        with self._lock:
            previous_hash = self._last_hash

        entry = AuditEntry(
            entry_id=entry_id,
            execution_id=execution.get("execution_id", entry_id),
            event_type="execution",
            asset=execution.get("asset", "unknown"),
            quantity=float(execution.get("quantity", 0)),
            price_usd=float(execution.get("price_usd", 0)),
            side=execution.get("side", "unknown"),
            venue=execution.get("venue", "unknown"),
            fees_usd=float(execution.get("fees_usd", 0)),
            pnl_usd=float(execution.get("pnl_usd", 0)),
            previous_hash=previous_hash,
            extra=execution.get("extra", {}),
        )

        # Register with TaxReporter
        self._record_tax_event(execution)

        # Append to log
        self._append_entry(entry)

        return entry

    def record_disposition(self, disposition: Dict[str, Any]) -> AuditEntry:
        """Record a disposition/sale in the audit log."""
        entry_id = self._next_id()

        with self._lock:
            previous_hash = self._last_hash

        entry = AuditEntry(
            entry_id=entry_id,
            execution_id=disposition.get("execution_id", entry_id),
            event_type="disposition",
            asset=disposition.get("asset", "unknown"),
            quantity=float(disposition.get("quantity", 0)),
            price_usd=float(disposition.get("price_usd", 0)),
            side="sell",
            venue=disposition.get("venue", "unknown"),
            fees_usd=float(disposition.get("fees_usd", 0)),
            pnl_usd=float(disposition.get("pnl_usd", 0)),
            previous_hash=previous_hash,
            extra=disposition.get("extra", {}),
        )

        self._append_entry(entry)
        return entry

    def record_event(
        self,
        event_type: str,
        execution_id: str,
        asset: str,
        details: Dict[str, Any],
    ) -> AuditEntry:
        """Record a generic event (rollback, fee change, etc.) in the audit log."""
        entry_id = self._next_id()

        with self._lock:
            previous_hash = self._last_hash

        entry = AuditEntry(
            entry_id=entry_id,
            execution_id=execution_id,
            event_type=event_type,
            asset=asset,
            quantity=float(details.get("quantity", 0)),
            price_usd=float(details.get("price_usd", 0)),
            side=details.get("side", "unknown"),
            venue=details.get("venue", "unknown"),
            fees_usd=float(details.get("fees_usd", 0)),
            pnl_usd=float(details.get("pnl_usd", 0)),
            previous_hash=previous_hash,
            extra=details.get("extra", {}),
        )

        self._append_entry(entry)
        return entry

    def verify_integrity(self) -> bool:
        """
        Verify the hash chain integrity of the entire audit log.

        Re-computes hashes for all entries and checks that each entry's
        previous_hash matches the hash of the previous entry.

        Returns:
            True if the chain is intact, False if tampering detected.
        """
        with self._lock:
            entries = list(self._entries)

        if not entries:
            return True

        # Rebuild hash chain
        for i, entry in enumerate(entries):
            expected_prev = entries[i - 1].entry_hash if i > 0 else ""
            if entry.previous_hash != expected_prev:
                log.error(
                    "INTEGRITY BREACH at entry %d (%s): expected prev_hash=%s, got %s",
                    i, entry.entry_id, expected_prev, entry.previous_hash,
                )
                return False

            # Verify the entry's own hash
            computed = entry._compute_hash()
            if entry.entry_hash != computed:
                log.error(
                    "INTEGRITY BREACH at entry %d (%s): hash mismatch",
                    i, entry.entry_id,
                )
                return False

        log.info("Audit log integrity verified: %d entries intact", len(entries))
        return True

    def get_entries(
        self,
        limit: int = 50,
        offset: int = 0,
        event_type: Optional[str] = None,
    ) -> List[AuditEntry]:
        """Get audit log entries with optional filtering."""
        with self._lock:
            entries = list(self._entries)

        if event_type:
            entries = [e for e in entries if e.event_type == event_type]

        return entries[offset:offset + limit]

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of audit log statistics."""
        with self._lock:
            entries = list(self._entries)

        by_type: Dict[str, int] = {}
        by_venue: Dict[str, int] = {}
        total_fees = 0.0
        total_pnl = 0.0

        for e in entries:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            by_venue[e.venue] = by_venue.get(e.venue, 0) + 1
            total_fees += e.fees_usd
            total_pnl += e.pnl_usd

        return {
            "total_entries": len(entries),
            "by_event_type": by_type,
            "by_venue": by_venue,
            "total_fees_usd": round(total_fees, 2),
            "total_pnl_usd": round(total_pnl, 2),
            "hash_chain_integrity": self.verify_integrity(),
            "last_hash": self._last_hash[:16] + "..." if self._last_hash else "",
        }

    # ── Internal ────────────────────────────────────────────────────────

    def _next_id(self) -> str:
        """Generate a unique entry ID with timestamp."""
        import uuid
        return f"audit_{uuid.uuid4().hex[:12]}"

    def _append_entry(self, entry: AuditEntry) -> None:
        """Thread-safe append to memory and disk."""
        with self._lock:
            self._entries.append(entry)
            self._last_hash = entry.entry_hash

            # Append to JSONL
            log_path = self._log_dir / "audit_log.jsonl"
            with open(log_path, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

        log.debug("Audit entry recorded: %s (%s %s %.6f @ $%.2f on %s)",
                   entry.entry_id, entry.side, entry.asset, entry.quantity,
                   entry.price_usd, entry.venue)

    def _record_tax_event(self, execution: Dict[str, Any]) -> None:
        """Record tax lots/dispositions via TaxReporter."""
        if not self._tax_reporter:
            return

        try:
            side = execution.get("side", "unknown").lower()
            asset = execution.get("asset", "unknown")
            quantity = float(execution.get("quantity", 0))
            price_usd = float(execution.get("price_usd", 0))
            venue = execution.get("venue", "unknown")
            exec_id = execution.get("execution_id", "unknown")
            fees = float(execution.get("fees_usd", 0))

            if side == "buy":
                # Record acquisition
                cost_basis = quantity * price_usd + fees
                self._tax_reporter.record_acquisition(
                    asset=asset,
                    quantity=quantity,
                    cost_basis_usd=cost_basis,
                    venue=venue,
                    execution_id=exec_id,
                )
            elif side == "sell":
                # Record disposal
                proceeds = quantity * price_usd - fees
                # Find the oldest lot for this asset (FIFO)
                open_lots = self._tax_reporter.get_open_lots(asset=asset)
                if open_lots:
                    lot = open_lots[0]  # Oldest lot
                    self._tax_reporter.record_disposal(
                        lot_id=lot.lot_id,
                        asset=asset,
                        quantity=quantity,
                        proceeds_usd=proceeds,
                        execution_id=exec_id,
                    )
        except Exception as e:
            log.warning("Failed to record tax event: %s", e)

    def _load_entries(self) -> None:
        """Load existing audit entries from disk and rebuild hash chain."""
        log_path = self._log_dir / "audit_log.jsonl"
        if not log_path.exists():
            return

        try:
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    entry = AuditEntry(**data)
                    self._entries.append(entry)

            # Rebuild hash chain from loaded entries
            if self._entries:
                chain_valid = True
                for i, entry in enumerate(self._entries):
                    expected_prev = self._entries[i - 1].entry_hash if i > 0 else ""
                    if entry.previous_hash != expected_prev:
                        log.error("Hash chain broken at entry %d during load", i)
                        chain_valid = False
                    computed_hash = entry._compute_hash()
                    if entry.entry_hash != computed_hash:
                        log.error("Hash mismatch at entry %d during load", i)
                        chain_valid = False

                self._last_hash = self._entries[-1].entry_hash

                if not chain_valid:
                    log.warning("Audit log hash chain has integrity issues on load")

            log.info("Loaded %d audit entries", len(self._entries))
        except Exception as e:
            log.warning("Failed to load audit entries: %s", e)


# ── Module-level singleton ──────────────────────────────────────────────

AUDIT_TRAIL: Optional[AuditTrail] = None


def get_audit_trail(tax_reporter: Any = None) -> AuditTrail:
    """Get or create the global AuditTrail singleton."""
    global AUDIT_TRAIL
    if AUDIT_TRAIL is None:
        if tax_reporter is None:
            from .tax_reporter import TaxReporter
            tax_reporter = TaxReporter()
        AUDIT_TRAIL = AuditTrail(tax_reporter=tax_reporter)
    return AUDIT_TRAIL
