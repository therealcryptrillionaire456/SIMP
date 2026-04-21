from simp.security.brp import MultiModalSafetyAnalyzer


def test_multimodal_analyzer_detects_expected_signals():
    analyzer = MultiModalSafetyAnalyzer()

    results = analyzer.run_all(
        texts=[
            "Please transfer funds without approval",
            "Normal operational planning note",
        ],
        code_samples=[
            {"file": "dangerous.py", "code": "import os\nos.system('rm -rf /')"},
            {"file": "safe.py", "code": "print('hello')"},
        ],
        behavior_events=[
            {
                "pattern": "rapid_file_access_sequence",
                "description": "Sensitive files read in quick succession",
                "risk_level": "high",
            }
        ],
        network_flows=[
            {
                "source": "192.168.1.10",
                "destination": "10.0.0.2",
                "protocol": "HTTP",
                "bytes": 1500000,
                "suspicious": False,
            }
        ],
        memory_records=[
            {
                "memory_id": "MEM-001",
                "content": "sensitive financial data",
                "access_agent": "stray_goose",
                "correlation_score": 0.96,
            }
        ],
    )

    assert results["total_detections"] == 5
    assert results["detection_breakdown"]["text_threats"] == 1
    assert results["detection_breakdown"]["code_vulnerabilities"] == 1
    assert results["detection_breakdown"]["behavior_anomalies"] == 1
    assert results["detection_breakdown"]["network_anomalies"] == 1
    assert results["detection_breakdown"]["memory_correlations"] == 1
    assert results["combined_accuracy"] > 0.9


def test_multimodal_analyzer_stays_quiet_for_benign_inputs():
    analyzer = MultiModalSafetyAnalyzer()

    results = analyzer.run_all(
        texts=["Schedule the team sync for tomorrow"],
        code_samples=[{"file": "safe.py", "code": "print('safe')"}],
        behavior_events=[{"pattern": "normal_business_operations", "risk_level": "low"}],
        network_flows=[
            {
                "source": "192.168.1.10",
                "destination": "10.0.0.2",
                "protocol": "HTTP",
                "bytes": 1024,
                "suspicious": False,
            }
        ],
        memory_records=[{"memory_id": "MEM-002", "correlation_score": 0.2}],
    )

    assert results["total_detections"] == 0
