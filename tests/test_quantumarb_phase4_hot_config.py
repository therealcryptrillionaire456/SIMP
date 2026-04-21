import json

from simp.agents import quantumarb_agent_phase4 as phase4


class DummyConnector:
    def __init__(self, sandbox: bool):
        self.sandbox = sandbox


def test_phase4_supports_live_connector_schema(tmp_path, monkeypatch):
    config_path = tmp_path / "live_phase2.json"
    config_path.write_text(
        json.dumps(
            {
                "connectors": {
                    "coinbase": {
                        "use_sandbox": False,
                        "live_trading": True,
                        "api_key_env": "COINBASE_API_KEY",
                        "api_secret_env": "COINBASE_API_SECRET",
                        "api_passphrase_env": "COINBASE_API_PASSPHRASE",
                    }
                },
                "risk": {
                    "max_position_size_usd": 0.10,
                    "max_daily_loss_usd": 1.0,
                    "min_spread_pct": 0.01,
                    "max_slippage_pct": 0.10,
                    "risk_score_threshold": 0.50,
                },
                "execution": {
                    "max_slippage_bps": 10,
                    "dry_run": False,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("COINBASE_API_KEY", "live-key")
    monkeypatch.setenv("COINBASE_API_SECRET", "live-secret")
    monkeypatch.setenv("COINBASE_API_PASSPHRASE", "live-passphrase")

    created = {}

    def fake_connector(exchange_name: str, **kwargs):
        created["exchange_name"] = exchange_name
        created["kwargs"] = kwargs
        return DummyConnector(sandbox=kwargs["sandbox"])

    monkeypatch.setattr(phase4, "create_exchange_connector", fake_connector)

    engine = phase4.QuantumArbEnginePhase4(str(config_path))

    assert engine.config["executor"]["allow_live_trading"] is True
    assert "coinbase_live" in engine.config["exchanges"]
    assert created["exchange_name"] == "coinbase"
    assert created["kwargs"]["sandbox"] is False
    assert created["kwargs"]["api_key"] == "live-key"
    assert created["kwargs"]["api_secret"] == "live-secret"
    assert created["kwargs"]["passphrase"] == "live-passphrase"
    assert engine.exchange_connectors["coinbase_live"].sandbox is False
