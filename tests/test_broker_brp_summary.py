import json

from simp.security.brp_bridge import BRPBridge
from simp.security.brp_models import BRPEvent, BRPMode


def test_broker_health_and_stats_include_brp_summary(broker, tmp_path):
    brp_dir = tmp_path / "brp"
    bridge = BRPBridge(data_dir=str(brp_dir), default_mode=BRPMode.ADVISORY.value)
    bridge.evaluate_event(
        BRPEvent(
            source_agent="projectx_native",
            action="withdrawal",
            mode=BRPMode.ADVISORY.value,
        )
    )
    broker.brp_bridge = bridge

    health = broker.health_check()
    stats = broker.get_statistics()

    assert "brp" in health
    assert health["brp"]["enabled"] is True
    assert health["brp"]["mode"] == BRPMode.ADVISORY.value
    assert "brp" in stats
    assert stats["brp"]["alert_count"] >= 1
    assert stats["brp"]["open_alert_count"] >= 1
    assert stats["brp"]["acknowledged_alert_count"] == 0
    assert "decision_counts" in stats["brp"]
