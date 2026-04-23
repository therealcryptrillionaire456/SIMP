from simp.security.brp.quantum_defense import QuantumDefenseAdvisor


def test_quantum_defense_posture_is_safe_by_default():
    advisor = QuantumDefenseAdvisor()

    posture = advisor.build_posture_summary()

    assert posture["backend_summary"]["available_backends"] >= 1
    assert posture["backend_summary"]["active_backend"] in {"local_simulator", "qiskit_aer"}
    assert isinstance(posture["backend_summary"]["real_hardware_ready"], bool)
    if posture["backend_summary"]["real_hardware_ready"]:
        assert posture["backend_summary"]["real_hardware_available"] is True
    assert posture["skill_summary"]["skill_count"] >= 4


def test_quantum_defense_assessment_returns_bounded_boost():
    advisor = QuantumDefenseAdvisor()

    assessment = advisor.assess(
        {
            "source_agent": "mesh_gateway",
            "event_type": "mesh_intent",
            "action": "fund_transfer",
            "context": {"route": "external", "token": "present"},
            "tags": ["restricted_action", "cross_domain_signal", "mesh"],
        },
        threat_score=0.86,
        threat_tags=["restricted_action", "cross_domain_signal", "low_mesh_trust"],
    )

    assert assessment["enabled"] is True
    assert assessment["problem_type"] in {"cryptography", "search", "finance"}
    assert 0.0 <= assessment["score_boost"] <= 0.1
    assert "backend_summary" in assessment
    assert "skill_recommendation" in assessment
    assert assessment["skill_gap_counts"]["recommended_development"] >= 0
