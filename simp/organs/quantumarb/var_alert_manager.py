"""
Real-Time VaR Alerts — T25
============================
Wire risk_reporter VaR breaches to Telegram operator alerts with
position context.

Monitors the RiskReporter's RiskReport and triggers alerts when:
  - Portfolio VaR exceeds configured threshold
  - Max drawdown exceeds configured threshold
  - Win rate drops below configured threshold
  - Fee drag exceeds configured threshold

Alerts are dispatched via:
  - Console logging (always)
  - Telegram alert integration (if configured)
  - JSONL alert log (persistent)

Usage:
    var_alerts = VaRAlertManager(risk_reporter=reporter)
    var_alerts.check_and_alert()  # Called periodically
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

log = logging.getLogger("var_alert_manager")


@dataclass
class VaRAlertConfig:
    """Configuration for VaR alert thresholds."""
    var_threshold_usd: float = 50.0        # Alert if VaR exceeds this
    drawdown_threshold_pct: float = 0.15   # Alert if drawdown exceeds 15%
    win_rate_threshold_24h: float = 0.30   # Alert if win rate drops below 30%
    win_rate_threshold_7d: float = 0.35
    fee_drag_threshold_usd: float = 10.0   # Alert if fee drag exceeds this
    min_sharpe_ratio: float = 0.5          # Alert if Sharpe drops below 0.5
    check_interval_seconds: float = 60.0   # Min time between alerts per metric
    max_alerts_per_hour: int = 10          # Rate limit


@dataclass
class VaRAlert:
    """An alert record for a VaR/metric breach."""
    alert_type: str           # var, drawdown, win_rate, fee_drag, sharpe
    severity: str             # warning, critical
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    position_context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VaRAlertManager:
    """
    Monitors RiskReporter metrics and triggers alerts on breaches.

    Thread-safe. Supports custom alert handlers (e.g., Telegram, Slack).
    Rate-limited to prevent alert storms.
    """

    def __init__(
        self,
        risk_reporter: Any,   # RiskReporter instance
        config: Optional[VaRAlertConfig] = None,
        alert_dir: str = "data/alerts",
        telegram_handler: Optional[Callable[[str], None]] = None,
    ):
        self._risk_reporter = risk_reporter
        self._config = config or VaRAlertConfig()
        self._alert_dir = Path(alert_dir)
        self._alert_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._alerts: List[VaRAlert] = []
        # last_alert_time[alert_type] = timestamp — for rate limiting
        self._last_alert_time: Dict[str, float] = {}
        self._alert_count_hour: int = 0
        self._last_reset_time: float = time.time()
        self._telegram_handler = telegram_handler

        # Load existing alerts
        self._load_alerts()

        log.info(
            "VaRAlertManager initialized (var_threshold=$%.0f, "
            "drawdown_threshold=%.0f%%, check_interval=%.0fs)",
            self._config.var_threshold_usd,
            self._config.drawdown_threshold_pct * 100,
            self._config.check_interval_seconds,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def check_and_alert(self) -> List[VaRAlert]:
        """
        Check all risk metrics and trigger alerts for any breaches.

        Returns:
            List of VaRAlerts triggered this check (empty if none).
        """
        # Rate limit reset
        self._check_rate_limit_reset()

        # Get current risk report
        try:
            report = self._risk_reporter.compute()
        except Exception as e:
            log.error("Failed to compute risk report: %s", e)
            return []

        alerts: List[VaRAlert] = []

        # 1. VaR check
        if report.portfolio_var_95pct > self._config.var_threshold_usd:
            alert = self._create_alert(
                alert_type="var",
                severity="critical" if report.portfolio_var_95pct > self._config.var_threshold_usd * 2 else "warning",
                metric_name="portfolio_var_95pct",
                current_value=report.portfolio_var_95pct,
                threshold_value=self._config.var_threshold_usd,
                message=(
                    f"VaR ${report.portfolio_var_95pct:.2f} exceeds "
                    f"threshold ${self._config.var_threshold_usd:.2f}"
                ),
                position_context={
                    "total_pnl": report.total_pnl_usd,
                    "num_trades": report.num_trades,
                    "exposure": dict(report.exposure_by_venue),
                },
            )
            if self._should_alert("var"):
                self._record_alert(alert)
                alerts.append(alert)

        # 2. Drawdown check
        if report.max_drawdown > self._config.drawdown_threshold_pct:
            alert = self._create_alert(
                alert_type="drawdown",
                severity="critical" if report.max_drawdown > self._config.drawdown_threshold_pct * 1.5 else "warning",
                metric_name="max_drawdown",
                current_value=report.max_drawdown,
                threshold_value=self._config.drawdown_threshold_pct,
                message=(
                    f"Max drawdown {report.max_drawdown:.1%} exceeds "
                    f"threshold {self._config.drawdown_threshold_pct:.0%}"
                ),
                position_context={
                    "total_pnl": report.total_pnl_usd,
                    "num_trades": report.num_trades,
                },
            )
            if self._should_alert("drawdown"):
                self._record_alert(alert)
                alerts.append(alert)

        # 3. Win rate check (24h)
        if report.win_rate_24h < self._config.win_rate_threshold_24h and report.num_trades >= 5:
            alert = self._create_alert(
                alert_type="win_rate",
                severity="warning",
                metric_name="win_rate_24h",
                current_value=report.win_rate_24h,
                threshold_value=self._config.win_rate_threshold_24h,
                message=(
                    f"24h win rate {report.win_rate_24h:.1%} below "
                    f"threshold {self._config.win_rate_threshold_24h:.0%}"
                ),
            )
            if self._should_alert("win_rate"):
                self._record_alert(alert)
                alerts.append(alert)

        # 4. Fee drag check
        if report.fee_drag_usd > self._config.fee_drag_threshold_usd:
            alert = self._create_alert(
                alert_type="fee_drag",
                severity="warning",
                metric_name="fee_drag_usd",
                current_value=report.fee_drag_usd,
                threshold_value=self._config.fee_drag_threshold_usd,
                message=(
                    f"Fee drag ${report.fee_drag_usd:.2f} exceeds "
                    f"threshold ${self._config.fee_drag_threshold_usd:.2f}"
                ),
                position_context={"total_fees": report.total_fees_usd, "total_pnl": report.total_pnl_usd},
            )
            if self._should_alert("fee_drag"):
                self._record_alert(alert)
                alerts.append(alert)

        # 5. Sharpe ratio check
        if report.sharpe_ratio < self._config.min_sharpe_ratio and report.num_trades >= 10:
            alert = self._create_alert(
                alert_type="sharpe",
                severity="warning",
                metric_name="sharpe_ratio",
                current_value=report.sharpe_ratio,
                threshold_value=self._config.min_sharpe_ratio,
                message=(
                    f"Sharpe ratio {report.sharpe_ratio:.3f} below "
                    f"threshold {self._config.min_sharpe_ratio:.2f}"
                ),
                position_context={"num_trades": report.num_trades, "total_pnl": report.total_pnl_usd},
            )
            if self._should_alert("sharpe"):
                self._record_alert(alert)
                alerts.append(alert)

        # Dispatch alerts
        for alert in alerts:
            self._dispatch_alert(alert)

        return alerts

    def get_recent_alerts(
        self, limit: int = 20, alert_type: Optional[str] = None
    ) -> List[VaRAlert]:
        """Get the most recent alerts, optionally filtered by type."""
        with self._lock:
            if alert_type:
                filtered = [a for a in self._alerts if a.alert_type == alert_type]
            else:
                filtered = list(self._alerts)
        return list(reversed(filtered[-limit:]))

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get a summary of alert counts by type and severity."""
        with self._lock:
            alerts = list(self._alerts)

        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for a in alerts:
            by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1

        return {
            "total_alerts": len(alerts),
            "by_type": by_type,
            "by_severity": by_severity,
        }

    def register_telegram_handler(
        self, handler: Callable[[str], None]
    ) -> None:
        """Register a callable to handle alert message dispatching."""
        self._telegram_handler = handler

    # ── Internal ────────────────────────────────────────────────────────

    def _create_alert(
        self, alert_type: str, severity: str, metric_name: str,
        current_value: float, threshold_value: float, message: str,
        position_context: Optional[Dict] = None,
    ) -> VaRAlert:
        return VaRAlert(
            alert_type=alert_type,
            severity=severity,
            metric_name=metric_name,
            current_value=round(current_value, 4),
            threshold_value=threshold_value,
            message=message,
            position_context=position_context or {},
        )

    def _should_alert(self, alert_type: str) -> bool:
        """Rate-limit check: has enough time passed since last alert of this type?"""
        now = time.time()
        last = self._last_alert_time.get(alert_type, 0.0)
        if now - last < self._config.check_interval_seconds:
            return False
        if self._alert_count_hour >= self._config.max_alerts_per_hour:
            return False
        return True

    def _check_rate_limit_reset(self) -> None:
        """Reset hourly alert counter every hour."""
        now = time.time()
        if now - self._last_reset_time > 3600:
            self._alert_count_hour = 0
            self._last_reset_time = now

    def _record_alert(self, alert: VaRAlert) -> None:
        """Record an alert in memory and on disk."""
        with self._lock:
            self._alerts.append(alert)
            self._last_alert_time[alert.alert_type] = time.time()
            self._alert_count_hour += 1

            # Write to JSONL
            alert_path = self._alert_dir / "var_alerts.jsonl"
            with open(alert_path, "a") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")

        log.warning(
            "VAR ALERT [%s/%s]: %s",
            alert.severity.upper(), alert.alert_type, alert.message,
        )

    def _dispatch_alert(self, alert: VaRAlert) -> None:
        """Dispatch alert to registered handlers."""
        if self._telegram_handler:
            try:
                msg = (
                    f"\u26a0\ufe0f SIMP VaR Alert [{alert.severity.upper()}]\n"
                    f"{alert.message}\n"
                    f"Metric: {alert.metric_name}\n"
                    f"Value: {alert.current_value} (threshold: {alert.threshold_value})\n"
                    f"Time: {alert.timestamp[:19]}"
                )
                self._telegram_handler(msg)
            except Exception as e:
                log.error("Telegram dispatch failed: %s", e)

    def _load_alerts(self) -> None:
        """Load existing alerts from disk."""
        alert_path = self._alert_dir / "var_alerts.jsonl"
        if not alert_path.exists():
            return
        try:
            with open(alert_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    alert = VaRAlert(**json.loads(line))
                    self._alerts.append(alert)
        except Exception as e:
            log.warning("Failed to load alerts: %s", e)


# ── Module-level singleton ──────────────────────────────────────────────

VAR_ALERT_MANAGER: Optional[VaRAlertManager] = None


def get_var_alert_manager(risk_reporter: Any = None) -> VaRAlertManager:
    """Get or create the global VaRAlertManager singleton."""
    global VAR_ALERT_MANAGER
    if VAR_ALERT_MANAGER is None:
        if risk_reporter is None:
            from .risk_reporter import RiskReporter
            risk_reporter = RiskReporter()
        VAR_ALERT_MANAGER = VaRAlertManager(risk_reporter=risk_reporter)
    return VAR_ALERT_MANAGER
