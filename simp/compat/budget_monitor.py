"""
SIMP Budget Monitor — Sprint 49

Real-time budget monitoring with alerts and anomaly detection.
WARNING at >=75% of limit, CRITICAL at >=100%.
CRITICAL task/daily alerts block payment execution.
"""

import uuid
import threading
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SIMP.BudgetMonitor")


# ---------------------------------------------------------------------------
# AlertSeverity
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# BudgetAlert
# ---------------------------------------------------------------------------

@dataclass
class BudgetAlert:
    alert_id: str = ""
    severity: str = ""
    category: str = ""  # daily, monthly, task, anomaly
    message: str = ""
    current_value: float = 0.0
    limit_value: float = 0.0
    percentage: float = 0.0
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    created_at: str = ""

    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# BudgetMonitor
# ---------------------------------------------------------------------------

class BudgetMonitor:
    """
    Monitors spending against budget limits and generates alerts.
    WARNING at >=75% of limit, CRITICAL at >=100%.
    """

    def __init__(
        self,
        max_per_task: float = 20.00,
        max_per_day: float = 50.00,
        max_per_month: float = 200.00,
    ):
        self._lock = threading.Lock()
        self.max_per_task = max_per_task
        self.max_per_day = max_per_day
        self.max_per_month = max_per_month
        self._alerts: Dict[str, BudgetAlert] = {}

    def _create_alert(
        self,
        severity: AlertSeverity,
        category: str,
        message: str,
        current_value: float,
        limit_value: float,
    ) -> BudgetAlert:
        pct = (current_value / limit_value * 100) if limit_value > 0 else 0.0
        alert = BudgetAlert(
            severity=severity.value,
            category=category,
            message=message,
            current_value=round(current_value, 2),
            limit_value=round(limit_value, 2),
            percentage=round(pct, 1),
        )
        with self._lock:
            self._alerts[alert.alert_id] = alert
        logger.log(
            logging.CRITICAL if severity == AlertSeverity.CRITICAL else logging.WARNING,
            "Budget alert [%s]: %s (%.1f%% of $%.2f)",
            severity.value, message, pct, limit_value,
        )
        return alert

    def check_daily_budget(self, daily_spend: float) -> List[BudgetAlert]:
        """Check daily spend against limit. Returns new alerts generated."""
        alerts = []
        pct = (daily_spend / self.max_per_day * 100) if self.max_per_day > 0 else 0.0

        if pct >= 100:
            alerts.append(self._create_alert(
                AlertSeverity.CRITICAL, "daily",
                f"Daily budget EXCEEDED: ${daily_spend:.2f} / ${self.max_per_day:.2f}",
                daily_spend, self.max_per_day,
            ))
        elif pct >= 75:
            alerts.append(self._create_alert(
                AlertSeverity.WARNING, "daily",
                f"Daily budget at {pct:.0f}%: ${daily_spend:.2f} / ${self.max_per_day:.2f}",
                daily_spend, self.max_per_day,
            ))

        return alerts

    def check_monthly_budget(self, monthly_spend: float) -> List[BudgetAlert]:
        """Check monthly spend against limit. Returns new alerts generated."""
        alerts = []
        pct = (monthly_spend / self.max_per_month * 100) if self.max_per_month > 0 else 0.0

        if pct >= 100:
            alerts.append(self._create_alert(
                AlertSeverity.CRITICAL, "monthly",
                f"Monthly budget EXCEEDED: ${monthly_spend:.2f} / ${self.max_per_month:.2f}",
                monthly_spend, self.max_per_month,
            ))
        elif pct >= 75:
            alerts.append(self._create_alert(
                AlertSeverity.WARNING, "monthly",
                f"Monthly budget at {pct:.0f}%: ${monthly_spend:.2f} / ${self.max_per_month:.2f}",
                monthly_spend, self.max_per_month,
            ))

        return alerts

    def check_task_limit(self, task_amount: float) -> List[BudgetAlert]:
        """Check a single task amount against per-task limit."""
        alerts = []
        pct = (task_amount / self.max_per_task * 100) if self.max_per_task > 0 else 0.0

        if pct >= 100:
            alerts.append(self._create_alert(
                AlertSeverity.CRITICAL, "task",
                f"Task amount EXCEEDS limit: ${task_amount:.2f} / ${self.max_per_task:.2f}",
                task_amount, self.max_per_task,
            ))
        elif pct >= 75:
            alerts.append(self._create_alert(
                AlertSeverity.WARNING, "task",
                f"Task amount at {pct:.0f}%: ${task_amount:.2f} / ${self.max_per_task:.2f}",
                task_amount, self.max_per_task,
            ))

        return alerts

    def detect_anomalies(self, daily_spend: float, historical_avg: float) -> List[BudgetAlert]:
        """
        Detect spending anomalies by comparing to historical average.
        Alert if daily spend is >2x the historical average.
        """
        alerts = []
        if historical_avg > 0 and daily_spend > (historical_avg * 2):
            alerts.append(self._create_alert(
                AlertSeverity.WARNING, "anomaly",
                f"Anomalous spending: ${daily_spend:.2f} is {daily_spend/historical_avg:.1f}x the average ${historical_avg:.2f}",
                daily_spend, historical_avg * 2,
            ))
        return alerts

    def run_all_checks(
        self,
        daily_spend: float,
        monthly_spend: float,
        task_amount: float = 0.0,
        historical_avg: float = 0.0,
    ) -> List[BudgetAlert]:
        """Run all budget checks and return all alerts generated."""
        alerts = []
        alerts.extend(self.check_daily_budget(daily_spend))
        alerts.extend(self.check_monthly_budget(monthly_spend))
        if task_amount > 0:
            alerts.extend(self.check_task_limit(task_amount))
        if historical_avg > 0:
            alerts.extend(self.detect_anomalies(daily_spend, historical_avg))
        return alerts

    def has_critical_alert(self, categories: Optional[List[str]] = None) -> bool:
        """
        Check if there are any unacknowledged CRITICAL alerts.
        If categories provided, only check those categories.
        """
        with self._lock:
            for alert in self._alerts.values():
                if alert.severity == AlertSeverity.CRITICAL.value and not alert.acknowledged:
                    if categories is None or alert.category in categories:
                        return True
        return False

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "operator") -> BudgetAlert:
        """Acknowledge an alert."""
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                raise ValueError(f"Alert {alert_id!r} not found")
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
        logger.info("Alert %s acknowledged by %s", alert_id, acknowledged_by)
        return alert

    def get_alerts(self, include_acknowledged: bool = False) -> List[Dict[str, Any]]:
        """Get all alerts, optionally including acknowledged ones."""
        with self._lock:
            alerts = list(self._alerts.values())
        if not include_acknowledged:
            alerts = [a for a in alerts if not a.acknowledged]
        return [a.to_dict() for a in alerts]

    def get_budget_summary(
        self,
        daily_spend: float = 0.0,
        monthly_spend: float = 0.0,
    ) -> Dict[str, Any]:
        """Get a summary of budget status."""
        daily_pct = (daily_spend / self.max_per_day * 100) if self.max_per_day > 0 else 0.0
        monthly_pct = (monthly_spend / self.max_per_month * 100) if self.max_per_month > 0 else 0.0

        with self._lock:
            active_alerts = sum(1 for a in self._alerts.values() if not a.acknowledged)
            critical_alerts = sum(
                1 for a in self._alerts.values()
                if a.severity == AlertSeverity.CRITICAL.value and not a.acknowledged
            )

        return {
            "daily": {
                "spent": round(daily_spend, 2),
                "limit": self.max_per_day,
                "percentage": round(daily_pct, 1),
                "status": "critical" if daily_pct >= 100 else "warning" if daily_pct >= 75 else "ok",
            },
            "monthly": {
                "spent": round(monthly_spend, 2),
                "limit": self.max_per_month,
                "percentage": round(monthly_pct, 1),
                "status": "critical" if monthly_pct >= 100 else "warning" if monthly_pct >= 75 else "ok",
            },
            "task_limit": self.max_per_task,
            "active_alerts": active_alerts,
            "critical_alerts": critical_alerts,
            "currency": "USD",
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

BUDGET_MONITOR = BudgetMonitor()
