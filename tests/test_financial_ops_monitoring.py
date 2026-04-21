"""Tests for Sprint 49 — Budget Monitor."""

import os
import pytest

from simp.compat.budget_monitor import (
    AlertSeverity,
    BudgetAlert,
    BudgetMonitor,
    BUDGET_MONITOR,
)


class TestAlertSeverity:
    def test_info_value(self):
        assert AlertSeverity.INFO.value == "info"

    def test_warning_value(self):
        assert AlertSeverity.WARNING.value == "warning"

    def test_critical_value(self):
        assert AlertSeverity.CRITICAL.value == "critical"


class TestBudgetAlert:
    def test_auto_id(self):
        a = BudgetAlert()
        assert len(a.alert_id) > 0

    def test_auto_timestamp(self):
        a = BudgetAlert()
        assert a.created_at != ""

    def test_to_dict(self):
        a = BudgetAlert(severity="warning", category="daily", message="test")
        d = a.to_dict()
        assert d["severity"] == "warning"
        assert d["category"] == "daily"


class TestBudgetMonitor:
    @pytest.fixture
    def monitor(self):
        return BudgetMonitor(max_per_task=20.0, max_per_day=50.0, max_per_month=200.0)

    def test_no_alert_under_75_daily(self, monitor):
        alerts = monitor.check_daily_budget(30.0)  # 60%
        assert len(alerts) == 0

    def test_warning_at_75_daily(self, monitor):
        alerts = monitor.check_daily_budget(37.5)  # 75%
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING.value

    def test_critical_at_100_daily(self, monitor):
        alerts = monitor.check_daily_budget(50.0)  # 100%
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL.value

    def test_critical_above_100_daily(self, monitor):
        alerts = monitor.check_daily_budget(60.0)  # 120%
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL.value

    def test_warning_at_75_monthly(self, monitor):
        alerts = monitor.check_monthly_budget(150.0)  # 75%
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING.value

    def test_critical_at_100_monthly(self, monitor):
        alerts = monitor.check_monthly_budget(200.0)  # 100%
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL.value

    def test_task_limit_warning(self, monitor):
        alerts = monitor.check_task_limit(15.0)  # 75%
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING.value

    def test_task_limit_critical(self, monitor):
        alerts = monitor.check_task_limit(20.0)  # 100%
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL.value

    def test_anomaly_detection(self, monitor):
        alerts = monitor.detect_anomalies(daily_spend=50.0, historical_avg=10.0)
        assert len(alerts) == 1
        assert alerts[0].category == "anomaly"

    def test_no_anomaly_under_threshold(self, monitor):
        alerts = monitor.detect_anomalies(daily_spend=15.0, historical_avg=10.0)
        assert len(alerts) == 0

    def test_run_all_checks(self, monitor):
        alerts = monitor.run_all_checks(
            daily_spend=50.0,  # 100% daily
            monthly_spend=150.0,  # 75% monthly
            task_amount=20.0,  # 100% task
        )
        # Should have at least daily critical + monthly warning + task critical
        assert len(alerts) >= 3

    def test_acknowledge_alert(self, monitor):
        monitor.check_daily_budget(50.0)  # Generate critical alert
        alerts = monitor.get_alerts()
        assert len(alerts) >= 1
        alert_id = alerts[0]["alert_id"]
        ack = monitor.acknowledge_alert(alert_id, "admin")
        assert ack.acknowledged is True
        assert ack.acknowledged_by == "admin"

    def test_acknowledge_unknown_alert_raises(self, monitor):
        with pytest.raises(ValueError, match="not found"):
            monitor.acknowledge_alert("nonexistent-id", "admin")

    def test_get_alerts_filters_acknowledged(self, monitor):
        monitor.check_daily_budget(50.0)
        alerts = monitor.get_alerts()
        alert_id = alerts[0]["alert_id"]
        monitor.acknowledge_alert(alert_id, "admin")
        # Without include_acknowledged, should be filtered
        filtered = monitor.get_alerts(include_acknowledged=False)
        found = [a for a in filtered if a["alert_id"] == alert_id]
        assert len(found) == 0

    def test_get_alerts_includes_acknowledged(self, monitor):
        monitor.check_daily_budget(50.0)
        alerts = monitor.get_alerts()
        alert_id = alerts[0]["alert_id"]
        monitor.acknowledge_alert(alert_id, "admin")
        all_alerts = monitor.get_alerts(include_acknowledged=True)
        found = [a for a in all_alerts if a["alert_id"] == alert_id]
        assert len(found) == 1

    def test_has_critical_alert(self, monitor):
        assert monitor.has_critical_alert() is False
        monitor.check_daily_budget(50.0)
        assert monitor.has_critical_alert() is True

    def test_has_critical_alert_by_category(self, monitor):
        monitor.check_daily_budget(50.0)
        assert monitor.has_critical_alert(categories=["daily"]) is True
        assert monitor.has_critical_alert(categories=["monthly"]) is False

    def test_get_budget_summary(self, monitor):
        summary = monitor.get_budget_summary(daily_spend=25.0, monthly_spend=100.0)
        assert summary["daily"]["spent"] == 25.0
        assert summary["daily"]["limit"] == 50.0
        assert summary["daily"]["percentage"] == 50.0
        assert summary["daily"]["status"] == "ok"
        assert summary["monthly"]["spent"] == 100.0
        assert summary["monthly"]["percentage"] == 50.0
        assert summary["currency"] == "USD"


class TestBudgetRoutes:
    @pytest.fixture
    def client(self):
        from simp.server.http_server import SimpHttpServer
        os.environ["SIMP_REQUIRE_API_KEY"] = "false"
        server = SimpHttpServer()
        server.broker.start()
        return server.app.test_client()

    def test_budget_route(self, client):
        resp = client.get("/a2a/agents/financial-ops/budget")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "daily" in data
        assert "monthly" in data

    def test_alerts_route(self, client):
        resp = client.get("/alerts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "alerts" in data


class TestSingleton:
    def test_budget_monitor_singleton_exists(self):
        assert BUDGET_MONITOR is not None
