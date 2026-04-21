from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import inject_quantum_signal  # noqa: E402
import verify_revenue_path  # noqa: E402


def test_build_signal_uses_gate4_shape() -> None:
    signal = inject_quantum_signal.build_signal(
        asset="BTC-USD",
        side="sell",
        position_usd=2.52,
        source="test_suite",
        metadata={"ticket": "abc123"},
        signal_id="sig-1",
    )

    assert signal["signal_id"] == "sig-1"
    assert signal["signal_type"] == "portfolio_allocation"
    assert signal["assets"]["BTC-USD"]["action"] == "sell"
    assert signal["assets"]["BTC-USD"]["position_usd"] == 2.52
    assert signal["metadata"]["ticket"] == "abc123"


def test_verify_revenue_path_report_uses_latest_trade(monkeypatch) -> None:
    monkeypatch.setattr(
        verify_revenue_path,
        "build_snapshot",
        lambda: {
            "coinbase_dns": {"ok": True, "addresses": ["104.18.35.15"]},
            "services": {
                "broker": {"ok": True},
                "dashboard": {"ok": True},
                "projectx": {"ok": True},
            },
            "processes": {
                "gate4_consumer": 1,
                "quantum_signal_bridge": 1,
            },
            "gate4": {
                "state": {
                    "consecutive_losses": 0,
                    "cooldown_until": None,
                    "transient_errors": 1,
                    "last_error_classification": None,
                },
                "latest_trade": {
                    "ts": "2026-04-21T10:52:00+00:00",
                    "result": "ok",
                    "symbol": "BTC-USD",
                    "side": "SELL",
                    "response": {
                        "success_response": {
                            "order_id": "abc-order",
                        }
                    },
                },
                "latest_successful_trade": {
                    "ts": "2026-04-21T10:52:00+00:00",
                    "result": "ok",
                    "symbol": "BTC-USD",
                    "side": "SELL",
                    "response": {
                        "success_response": {
                            "order_id": "abc-order",
                        }
                    },
                },
            },
        },
    )

    class _FrozenDatetime:
        @classmethod
        def now(cls, tz=None):
            import datetime as _dt

            return _dt.datetime(2026, 4, 21, 10, 55, 0, tzinfo=tz)

        @classmethod
        def fromisoformat(cls, value):
            import datetime as _dt

            return _dt.datetime.fromisoformat(value)

    monkeypatch.setattr(verify_revenue_path, "datetime", _FrozenDatetime)

    report = verify_revenue_path.build_report(max_trade_age_minutes=10)

    assert report["ok"] is True
    assert report["checks"]["latest_successful_trade_has_order_id"]["order_id"] == "abc-order"
    assert report["checks"]["latest_successful_trade_fresh"]["ok"] is True
