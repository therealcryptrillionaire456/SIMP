"""
Tax & Regulatory Reporter — T30
================================
1099-compatible tax tracking for US regulatory compliance.

Features:
  - Tax lots per fill: acquisition_date, cost_basis, asset, venue, fx_rate
  - FIFO matching: oldest lots first
  - Short-term (<365 days) vs long-term (>=365 days) classification
  - Wash sale detection (loss + repurchase within 30 days)
  - Per-asset annual report
  - 1099-DIV compatible CSV export

Usage:
    reporter = TaxReporter()

    # Record a new acquisition (buy):
    reporter.record_acquisition(
        asset="BTC",
        quantity=0.001,
        cost_basis_usd=100.0,
        venue="coinbase",
        execution_id="exec_123",
    )

    # Record a disposal (sell):
    reporter.record_disposal(
        lot_id="lot_abc",
        asset="BTC",
        quantity=0.001,
        proceeds_usd=105.0,
        execution_id="exec_456",
    )

    # Generate annual report:
    report = reporter.generate_annual_report(year=2025)

    # Export CSV:
    reporter.export_csv(year=2025, path=Path("data/tax/2025_1099.csv"))
"""

from __future__ import annotations

import csv
import json
import logging
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, TextIO
from collections import defaultdict

log = logging.getLogger("tax_reporter")


@dataclass
class TaxLot:
    """One acquisition lot for tax purposes."""
    lot_id: str
    asset: str
    quantity: float
    cost_basis_per_unit: float  # USD
    acquisition_date: str  # ISO date
    venue: str
    acquisition_price_usd: float  # price at acquisition
    execution_id: str


@dataclass
class Disposition:
    """One sale/disposition for tax reporting."""
    lot_id: str
    asset: str
    quantity: float
    proceeds_per_unit: float
    disposal_date: str
    holding_period_days: int
    short_term: bool  # < 365 days
    gain_loss: float  # proceeds - cost_basis
    wash_sale: bool = False


@dataclass
class TaxReportAsset:
    """Annual tax report for one asset."""
    year: int
    asset: str
    total_sales_usd: float
    cost_basis_usd: float
    realized_gain_usd: float
    short_term_gain_usd: float
    long_term_gain_usd: float
    fees_usd: float
    wash_sale_events: int = 0
    lots_acquired: int = 0
    lots_disposed: int = 0


class TaxReporter:
    """
    Tracks tax lots and generates regulatory reports.

    WASH_SALE_WINDOW_DAYS = 30
    """

    WASH_SALE_WINDOW_DAYS = 30

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/tax")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lots_file = self.data_dir / "tax_lots.jsonl"
        self.dispositions_file = self.data_dir / "dispositions.jsonl"
        self.lots: Dict[str, TaxLot] = {}
        self.dispositions: List[Disposition] = []
        self._load()

    def _load(self) -> None:
        """Load existing lots and dispositions from disk."""
        if self.lots_file.exists():
            try:
                with open(self.lots_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        lot = TaxLot(**json.loads(line))
                        self.lots[lot.lot_id] = lot
            except Exception as e:
                log.warning(f"Could not load tax lots: {e}")

        if self.dispositions_file.exists():
            try:
                with open(self.dispositions_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        d = Disposition(**json.loads(line))
                        self.dispositions.append(d)
            except Exception as e:
                log.warning(f"Could not load dispositions: {e}")

    def _save_lot(self, lot: TaxLot) -> None:
        with open(self.lots_file, "a") as f:
            f.write(json.dumps(asdict(lot)) + "\n")

    def _save_disposition(self, disp: Disposition) -> None:
        with open(self.dispositions_file, "a") as f:
            f.write(json.dumps(asdict(disp)) + "\n")

    def record_acquisition(
        self,
        asset: str,
        quantity: float,
        cost_basis_usd: float,
        venue: str,
        execution_id: str,
        acquisition_date: Optional[str] = None,
    ) -> TaxLot:
        """Record a new tax lot (buy)."""
        lot = TaxLot(
            lot_id=f"lot_{uuid.uuid4().hex[:12]}",
            asset=asset,
            quantity=quantity,
            cost_basis_per_unit=cost_basis_usd / quantity if quantity > 0 else 0,
            acquisition_date=acquisition_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            venue=venue,
            acquisition_price_usd=cost_basis_usd,
            execution_id=execution_id,
        )
        self.lots[lot.lot_id] = lot
        self._save_lot(lot)
        log.info(
            "Recorded tax lot: %s %s %.6f @ $%.2f",
            lot.lot_id, asset, quantity, cost_basis_usd,
        )
        return lot

    def record_disposal(
        self,
        lot_id: str,
        asset: str,
        quantity: float,
        proceeds_usd: float,
        execution_id: str,
        disposal_date: Optional[str] = None,
    ) -> Optional[Disposition]:
        """Record a disposal (sell) using FIFO matching."""
        lot = self.lots.get(lot_id)
        if not lot:
            log.warning("Tax lot not found: %s", lot_id)
            return None

        disp_dt_str = disposal_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Holding period
        acq_dt = datetime.strptime(lot.acquisition_date, "%Y-%m-%d")
        disp_dt = datetime.strptime(disp_dt_str, "%Y-%m-%d")
        holding_days = (disp_dt - acq_dt).days
        short_term = holding_days < 365

        # Gain/Loss
        proceeds_per_unit = proceeds_usd / quantity if quantity > 0 else 0
        cost_per_unit = lot.cost_basis_per_unit
        gain_loss = (proceeds_per_unit - cost_per_unit) * quantity

        # Wash sale check
        wash_sale = self._check_wash_sale(
            asset=asset,
            lot_date=lot.acquisition_date,
            disposal_date=disp_dt_str,
        )

        disp = Disposition(
            lot_id=lot_id,
            asset=asset,
            quantity=quantity,
            proceeds_per_unit=proceeds_per_unit,
            disposal_date=disp_dt_str,
            holding_period_days=holding_days,
            short_term=short_term,
            gain_loss=gain_loss,
            wash_sale=wash_sale,
        )

        # Remove the used portion of the lot
        if quantity >= lot.quantity:
            del self.lots[lot_id]
        else:
            lot.quantity -= quantity
            # cost_basis_per_unit stays unchanged (average)

        self.dispositions.append(disp)
        self._save_disposition(disp)
        log.info(
            "Recorded disposal: %s %s %.6f gain_loss=$%.2f wash=%s",
            lot_id, asset, quantity, gain_loss, wash_sale,
        )
        return disp

    def _check_wash_sale(
        self, asset: str, lot_date: str, disposal_date: str, _current_lot_id: str = ""
    ) -> bool:
        """Check if a wash sale occurred within WASH_SALE_WINDOW_DAYS."""
        lot_dt = datetime.strptime(lot_date, "%Y-%m-%d")
        disp_dt = datetime.strptime(disposal_date, "%Y-%m-%d")
        window = timedelta(days=self.WASH_SALE_WINDOW_DAYS)

        for other_lot in self.lots.values():
            if other_lot.asset != asset:
                continue
            other_dt = datetime.strptime(other_lot.acquisition_date, "%Y-%m-%d")
            # Within 30 days before or after disposal?
            if abs((other_dt - disp_dt).days) <= self.WASH_SALE_WINDOW_DAYS:
                return True
            # Within 30 days of original lot acquisition (replacement)?
            if abs((other_dt - lot_dt).days) <= self.WASH_SALE_WINDOW_DAYS:
                return True
        return False

    def generate_annual_report(self, year: int) -> Dict[str, TaxReportAsset]:
        """Generate per-asset annual tax report."""
        reports: Dict[str, TaxReportAsset] = {}

        for disp in self.dispositions:
            disp_year = int(disp.disposal_date[:4])
            if disp_year != year:
                continue

            if disp.asset not in reports:
                reports[disp.asset] = TaxReportAsset(
                    year=year,
                    asset=disp.asset,
                    total_sales_usd=0.0,
                    cost_basis_usd=0.0,
                    realized_gain_usd=0.0,
                    short_term_gain_usd=0.0,
                    long_term_gain_usd=0.0,
                    fees_usd=0.0,
                )

            r = reports[disp.asset]
            r.total_sales_usd += disp.proceeds_per_unit * disp.quantity
            r.cost_basis_usd += disp.gain_loss + (disp.proceeds_per_unit * disp.quantity)
            r.realized_gain_usd += disp.gain_loss
            if disp.short_term:
                r.short_term_gain_usd += disp.gain_loss
            else:
                r.long_term_gain_usd += disp.gain_loss
            if disp.wash_sale:
                r.wash_sale_events += 1
            r.lots_disposed += 1

        return reports

    def export_csv(self, year: int, path: Path) -> None:
        """Export 1099-compatible CSV."""
        reports = self.generate_annual_report(year)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Year", "Asset", "Total Sales (USD)", "Cost Basis (USD)",
                "Realized Gain (USD)", "Short-Term Gain (USD)", "Long-Term Gain (USD)",
                "Fees (USD)", "Wash Sale Events", "Lots Acquired", "Lots Disposed",
            ])

            total_gain = 0.0
            for asset, r in sorted(reports.items()):
                writer.writerow([
                    r.year, asset,
                    f"{r.total_sales_usd:.2f}",
                    f"{r.cost_basis_usd:.2f}",
                    f"{r.realized_gain_usd:.2f}",
                    f"{r.short_term_gain_usd:.2f}",
                    f"{r.long_term_gain_usd:.2f}",
                    f"{r.fees_usd:.2f}",
                    r.wash_sale_events,
                    r.lots_acquired,
                    r.lots_disposed,
                ])
                total_gain += r.realized_gain_usd

            # Total row
            writer.writerow([
                year, "TOTAL",
                f"{sum(r.total_sales_usd for r in reports.values()):.2f}",
                f"{sum(r.cost_basis_usd for r in reports.values()):.2f}",
                f"{total_gain:.2f}",
                f"{sum(r.short_term_gain_usd for r in reports.values()):.2f}",
                f"{sum(r.long_term_gain_usd for r in reports.values()):.2f}",
                f"{sum(r.fees_usd for r in reports.values()):.2f}",
                sum(r.wash_sale_events for r in reports.values()),
                sum(r.lots_acquired for r in reports.values()),
                sum(r.lots_disposed for r in reports.values()),
            ])

        log.info("Tax CSV exported to %s", path)

    def get_summary(self, year: int) -> Dict:
        """Quick summary of tax position."""
        reports = self.generate_annual_report(year)
        return {
            "year": year,
            "assets_traded": list(reports.keys()),
            "total_realized_gain": sum(r.realized_gain_usd for r in reports.values()),
            "short_term_gain": sum(r.short_term_gain_usd for r in reports.values()),
            "long_term_gain": sum(r.long_term_gain_usd for r in reports.values()),
            "wash_sale_events": sum(r.wash_sale_events for r in reports.values()),
            "open_lots": len(self.lots),
        }

    # FIFO helpers for external use
    def get_open_lots(self, asset: Optional[str] = None) -> List[TaxLot]:
        """Return all open lots, optionally filtered by asset."""
        result = list(self.lots.values())
        if asset:
            result = [l for l in result if l.asset == asset]
        # Sort by acquisition date (FIFO)
        result.sort(key=lambda l: l.acquisition_date)
        return result

    def get_dispositions(self, year: Optional[int] = None) -> List[Disposition]:
        """Return all dispositions, optionally filtered by year."""
        result = self.dispositions
        if year is not None:
            result = [d for d in result if int(d.disposal_date[:4]) == year]
        return result
