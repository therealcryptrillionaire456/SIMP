import asyncio
import json
from pathlib import Path

from simp.agents.quantumarb_agent_phase4 import QuantumArbAgentPhase4


def test_phase4_executes_queued_ktc_investment(tmp_path: Path):
    config_path = tmp_path / "phase4_config.json"
    config_path.write_text(
        json.dumps(
            {
                "exchanges": {
                    "stub_exec": {
                        "driver": "stub",
                        "sandbox": True,
                        "enabled": True,
                    }
                },
                "monitoring": {"enabled": False},
                "executor": {
                    "allow_live_trading": False,
                    "max_position_size_usd": 10.0,
                    "max_slippage_bps": 50.0,
                },
                "risk": {
                    "max_position_size_usd": 10.0,
                },
            }
        ),
        encoding="utf-8",
    )

    agent = QuantumArbAgentPhase4(poll_interval=0.01, config_path=str(config_path))
    agent.base_dir = tmp_path / "quantumarb_phase4"
    agent.inbox_dir = agent.base_dir / "inbox"
    agent.outbox_dir = agent.base_dir / "outbox"
    agent.inbox_dir.mkdir(parents=True, exist_ok=True)
    agent.outbox_dir.mkdir(parents=True, exist_ok=True)

    intent_id = "ktc-invest-001"
    (agent.inbox_dir / f"{intent_id}.json").write_text(
        json.dumps(
            {
                "intent_id": intent_id,
                "intent_type": "ktc_investment_request",
                "source_agent": "ktc_api",
                "timestamp": "2026-04-20T00:00:00Z",
                "params": {
                    "user_id": "user-1",
                    "amount_usd": 5.0,
                    "asset": "SOL",
                    "auto_approve": True,
                    "review_required": False,
                },
                "payload": {
                    "user_id": "user-1",
                    "amount_usd": 5.0,
                    "asset": "SOL",
                    "review_required": False,
                },
            }
        ),
        encoding="utf-8",
    )

    async def run_once():
        agent._process_inbox()
        await asyncio.sleep(0.05)

    asyncio.run(run_once())

    result_path = agent.outbox_dir / f"investment_{intent_id}.json"
    assert result_path.exists()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["status"] == "executed"
    assert payload["result"]["success"] is True
