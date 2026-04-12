"""
PnL ledger for QuantumArb organ.

Implements append-only P&L tracking with thread-safe operations.
Follows SIMP data persistence patterns using JSONL files.
"""

import json
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import uuid


class PnLType(str, Enum):
    """Type of P&L entry."""
    TRADE = "trade"
    FEE = "fee"
    FUNDING = "funding"
    ADJUSTMENT = "adjustment"
    REALIZED = "realized"
    UNREALIZED = "unrealized"


@dataclass
class PnLEntry:
    """A single P&L entry in the ledger."""
    entry_id: str = field(
        default_factory=lambda: f"pnl-{uuid.uuid4().hex[:12]}"
    )
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    pnl_type: PnLType = PnLType.TRADE
    market: str = ""
    quantity: float = 0.0
    price: float = 0.0
    pnl_amount: float = 0.0  # Positive for profit, negative for loss
    pnl_bps: float = 0.0  # Profit/loss in basis points
    trade_id: Optional[str] = None
    position_before: float = 0.0
    position_after: float = 0.0
    fees: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class PnLLedger:
    """
    Thread-safe, append-only P&L ledger.
    
    Features:
    - Append-only JSONL file storage
    - Thread-safe operations
    - Realized and unrealized P&L tracking
    - Per-market P&L aggregation
    - Query methods for analysis
    - Automatic file rotation (optional)
    """
    
    def __init__(
        self,
        ledger_path: Optional[str] = None,
        max_file_size_mb: float = 100.0,
        backup_count: int = 5,
    ):
        """
        Initialize the P&L ledger.
        
        Args:
            ledger_path: Path to ledger file (default: ~/bullbear/logs/quantumarb/pnl_ledger.jsonl)
            max_file_size_mb: Maximum file size before rotation (MB)
            backup_count: Number of backup files to keep
        """
        if ledger_path is None:
            ledger_path = Path.home() / "bullbear" / "logs" / "quantumarb" / "pnl_ledger.jsonl"
        
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert MB to bytes
        self.backup_count = backup_count
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Cache for performance
        self._entries_cache: Optional[List[PnLEntry]] = None
        self._cache_dirty = True
        
        # Initialize ledger file if it doesn't exist
        self._ensure_ledger_file()
    
    def _ensure_ledger_file(self) -> None:
        """Ensure the ledger file exists and has proper headers."""
        with self.lock:
            if not self.ledger_path.exists():
                # Create empty file
                with open(self.ledger_path, "w") as f:
                    f.write("")  # Empty file
                
                # Write header comment
                header = {
                    "_type": "pnl_ledger_header",
                    "version": "1.0.0",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "description": "QuantumArb P&L Ledger (append-only)",
                    "schema": "PnLEntry",
                }
                self._append_raw(json.dumps(header))
    
    def _append_raw(self, line: str) -> None:
        """Append a raw line to the ledger file."""
        with self.lock:
            # Check file size and rotate if needed
            if self.ledger_path.exists() and self.ledger_path.stat().st_size > self.max_file_size:
                self._rotate_file()
            
            # Append the line
            with open(self.ledger_path, "a") as f:
                f.write(line + "\n")
            
            # Mark cache as dirty
            self._cache_dirty = True
    
    def _rotate_file(self) -> None:
        """Rotate the ledger file when it gets too large."""
        if not self.ledger_path.exists():
            return
        
        # Create backup files
        for i in range(self.backup_count - 1, 0, -1):
            old_file = self.ledger_path.parent / f"{self.ledger_path.stem}.{i}.jsonl"
            new_file = self.ledger_path.parent / f"{self.ledger_path.stem}.{i + 1}.jsonl"
            if old_file.exists():
                old_file.rename(new_file)
        
        # Move current file to backup.1
        backup_file = self.ledger_path.parent / f"{self.ledger_path.stem}.1.jsonl"
        self.ledger_path.rename(backup_file)
        
        # Create new empty file
        self._ensure_ledger_file()
    
    def _load_entries(self) -> List[PnLEntry]:
        """Load all entries from the ledger file."""
        entries = []
        
        if not self.ledger_path.exists():
            return entries
        
        with open(self.ledger_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Skip header lines
                    if "_type" in data and data["_type"] == "pnl_ledger_header":
                        continue
                    
                    # Convert to PnLEntry
                    entry = PnLEntry(
                        entry_id=data.get("entry_id", f"unknown-{line_num}"),
                        timestamp=data.get("timestamp", ""),
                        pnl_type=PnLType(data.get("pnl_type", "trade")),
                        market=data.get("market", ""),
                        quantity=float(data.get("quantity", 0.0)),
                        price=float(data.get("price", 0.0)),
                        pnl_amount=float(data.get("pnl_amount", 0.0)),
                        pnl_bps=float(data.get("pnl_bps", 0.0)),
                        trade_id=data.get("trade_id"),
                        position_before=float(data.get("position_before", 0.0)),
                        position_after=float(data.get("position_after", 0.0)),
                        fees=float(data.get("fees", 0.0)),
                        metadata=data.get("metadata", {}),
                    )
                    entries.append(entry)
                    
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    # Skip malformed lines but log error
                    error_entry = PnLEntry(
                        entry_id=f"error-{line_num}",
                        pnl_type=PnLType.ADJUSTMENT,
                        pnl_amount=0.0,
                        metadata={
                            "error": str(e),
                            "original_line": line[:100] + "..." if len(line) > 100 else line,
                            "line_number": line_num,
                        }
                    )
                    entries.append(error_entry)
        
        return entries
    
    def _get_cached_entries(self) -> List[PnLEntry]:
        """Get entries from cache, loading if necessary."""
        with self.lock:
            if self._cache_dirty or self._entries_cache is None:
                self._entries_cache = self._load_entries()
                self._cache_dirty = False
            return self._entries_cache.copy()
    
    def record_trade_pnl(
        self,
        market: str,
        quantity: float,
        price: float,
        pnl_amount: float,
        trade_id: str,
        position_before: float,
        position_after: float,
        fees: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PnLEntry:
        """
        Record P&L from a trade.
        
        Args:
            market: Market symbol
            quantity: Trade quantity (positive for buy, negative for sell)
            price: Trade price
            pnl_amount: P&L amount (positive for profit, negative for loss)
            trade_id: Associated trade ID
            position_before: Position before trade
            position_after: Position after trade
            fees: Fees paid
            metadata: Additional metadata
            
        Returns:
            The created PnLEntry
        """
        # Calculate P&L in basis points
        trade_value = abs(quantity * price)
        pnl_bps = (pnl_amount / trade_value * 10000) if trade_value > 0 else 0.0
        
        entry = PnLEntry(
            pnl_type=PnLType.TRADE,
            market=market,
            quantity=quantity,
            price=price,
            pnl_amount=pnl_amount,
            pnl_bps=pnl_bps,
            trade_id=trade_id,
            position_before=position_before,
            position_after=position_after,
            fees=fees,
            metadata=metadata or {},
        )
        
        self.append_entry(entry)
        return entry
    
    def record_fee(
        self,
        market: str,
        fee_amount: float,
        trade_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PnLEntry:
        """
        Record a fee payment.
        
        Args:
            market: Market symbol
            fee_amount: Fee amount (negative for cost)
            trade_id: Associated trade ID (if any)
            metadata: Additional metadata
            
        Returns:
            The created PnLEntry
        """
        entry = PnLEntry(
            pnl_type=PnLType.FEE,
            market=market,
            pnl_amount=-abs(fee_amount),  # Fees are always negative P&L
            trade_id=trade_id,
            metadata=metadata or {},
        )
        
        self.append_entry(entry)
        return entry
    
    def record_realized_pnl(
        self,
        market: str,
        pnl_amount: float,
        position_before: float,
        position_after: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PnLEntry:
        """
        Record realized P&L from position closure.
        
        Args:
            market: Market symbol
            pnl_amount: Realized P&L amount
            position_before: Position before realization
            position_after: Position after realization
            metadata: Additional metadata
            
        Returns:
            The created PnLEntry
        """
        entry = PnLEntry(
            pnl_type=PnLType.REALIZED,
            market=market,
            pnl_amount=pnl_amount,
            position_before=position_before,
            position_after=position_after,
            metadata=metadata or {},
        )
        
        self.append_entry(entry)
        return entry
    
    def append_entry(self, entry: PnLEntry) -> None:
        """
        Append a P&L entry to the ledger.
        
        Args:
            entry: P&L entry to append
        """
        # Ensure entry has an ID
        if not entry.entry_id or entry.entry_id.startswith("pnl-"):
            entry.entry_id = f"pnl-{uuid.uuid4().hex[:12]}"
        
        # Ensure timestamp is current if not set
        if not entry.timestamp:
            entry.timestamp = datetime.now(timezone.utc).isoformat()
        
        # Append to file
        self._append_raw(json.dumps(entry.to_dict()))
    
    def get_entries(
        self,
        market: Optional[str] = None,
        pnl_type: Optional[PnLType] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000,
    ) -> List[PnLEntry]:
        """
        Get P&L entries with optional filters.
        
        Args:
            market: Filter by market
            pnl_type: Filter by P&L type
            start_time: ISO timestamp filter (inclusive)
            end_time: ISO timestamp filter (exclusive)
            limit: Maximum number of entries to return
            
        Returns:
            Filtered list of P&L entries
        """
        entries = self._get_cached_entries()
        filtered = []
        
        for entry in entries:
            # Apply filters
            if market is not None and entry.market != market:
                continue
            
            if pnl_type is not None and entry.pnl_type != pnl_type:
                continue
            
            if start_time is not None and entry.timestamp < start_time:
                continue
            
            if end_time is not None and entry.timestamp >= end_time:
                continue
            
            filtered.append(entry)
            
            if len(filtered) >= limit:
                break
        
        return filtered
    
    def get_total_pnl(
        self,
        market: Optional[str] = None,
        pnl_type: Optional[PnLType] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> float:
        """
        Calculate total P&L with optional filters.
        
        Args:
            market: Filter by market
            pnl_type: Filter by P&L type
            start_time: ISO timestamp filter (inclusive)
            end_time: ISO timestamp filter (exclusive)
            
        Returns:
            Total P&L amount
        """
        entries = self.get_entries(
            market=market,
            pnl_type=pnl_type,
            start_time=start_time,
            end_time=end_time,
            limit=0,  # No limit for aggregation
        )
        
        return sum(entry.pnl_amount for entry in entries)
    
    def get_market_pnl_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Get P&L summary by market.
        
        Returns:
            Dictionary mapping market to P&L summary
        """
        entries = self._get_cached_entries()
        summary: Dict[str, Dict[str, float]] = {}
        
        for entry in entries:
            if entry.market not in summary:
                summary[entry.market] = {
                    "total_pnl": 0.0,
                    "trade_count": 0,
                    "fee_total": 0.0,
                    "realized_pnl": 0.0,
                }
            
            market_summary = summary[entry.market]
            market_summary["total_pnl"] += entry.pnl_amount
            
            if entry.pnl_type == PnLType.TRADE:
                market_summary["trade_count"] += 1
            elif entry.pnl_type == PnLType.FEE:
                market_summary["fee_total"] += abs(entry.pnl_amount)
            elif entry.pnl_type == PnLType.REALIZED:
                market_summary["realized_pnl"] += entry.pnl_amount
        
        return summary
    
    def get_recent_activity(self, hours: float = 24.0) -> Dict[str, Any]:
        """
        Get recent trading activity summary.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Activity summary dictionary
        """
        cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        cutoff_iso = datetime.fromtimestamp(cutoff_time, tz=timezone.utc).isoformat()
        
        entries = self.get_entries(start_time=cutoff_iso, limit=0)
        
        total_trades = sum(1 for e in entries if e.pnl_type == PnLType.TRADE)
        total_pnl = sum(e.pnl_amount for e in entries)
        total_fees = sum(abs(e.pnl_amount) for e in entries if e.pnl_type == PnLType.FEE)
        
        return {
            "period_hours": hours,
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "total_fees": total_fees,
            "net_pnl": total_pnl - total_fees,
            "entry_count": len(entries),
        }
    
    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        with self.lock:
            self._entries_cache = None
            self._cache_dirty = True
    
    def get_ledger_info(self) -> Dict[str, Any]:
        """Get information about the ledger."""
        file_exists = self.ledger_path.exists()
        file_size = self.ledger_path.stat().st_size if file_exists else 0
        
        entries = self._get_cached_entries()
        valid_entries = [e for e in entries if not e.entry_id.startswith("error-")]
        
        return {
            "ledger_path": str(self.ledger_path),
            "file_exists": file_exists,
            "file_size_bytes": file_size,
            "file_size_mb": file_size / (1024 * 1024),
            "entry_count": len(valid_entries),
            "error_count": len(entries) - len(valid_entries),
            "first_entry": entries[0].timestamp if entries else None,
            "last_entry": entries[-1].timestamp if entries else None,
            "cache_valid": not self._cache_dirty,
        }


# Singleton instance for easy access
_DEFAULT_LEDGER: Optional[PnLLedger] = None
_LEDGER_LOCK = threading.Lock()

def get_default_ledger() -> PnLLedger:
    """Get or create the default P&L ledger instance."""
    global _DEFAULT_LEDGER
    
    with _LEDGER_LOCK:
        if _DEFAULT_LEDGER is None:
            _DEFAULT_LEDGER = PnLLedger()
        
        return _DEFAULT_LEDGER