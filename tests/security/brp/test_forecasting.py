from simp.security.brp import PredictiveSafetyForecaster


def test_predictive_forecaster_generates_expected_counts():
    forecaster = PredictiveSafetyForecaster()

    forecasts = forecaster.generate_threat_forecasts(
        [
            {"type": "zero_day", "severity": 0.8, "description": "Critical zero-day vulnerability"},
            {"type": "apt", "severity": 0.7, "description": "APT activity"},
            {"type": "malware", "severity": 0.6, "description": "Malware outbreak"},
            {"type": "insider_threat", "severity": 0.5, "description": "Insider anomaly"},
        ],
        forecast_horizon=48,
    )
    predictions = forecaster.generate_safety_predictions(
        [
            {"name": "api_gateway", "load": 0.7, "vulnerability": 0.6},
            {"name": "database", "load": 0.8, "vulnerability": 0.4},
        ]
    )
    accuracy = forecaster.forecast_accuracy_analysis()

    assert len(forecasts) == 32
    assert len(predictions) == 8
    assert accuracy["total_forecasts"] == 32
    assert 0.0 <= accuracy["overall_accuracy"] <= 1.0
    assert 0.0 <= accuracy["average_confidence"] <= 1.0


def test_predictive_forecaster_severity_affects_probability():
    forecaster = PredictiveSafetyForecaster()

    high = forecaster.generate_threat_forecasts(
        [{"type": "zero_day", "severity": 0.9, "description": "Critical zero-day vulnerability"}],
        forecast_horizon=6,
    )[0]
    low = forecaster.generate_threat_forecasts(
        [{"type": "zero_day", "severity": 0.2, "description": "Low concern"}],
        forecast_horizon=6,
    )[0]

    assert high.probability > low.probability
    assert high.predicted_severity > low.predicted_severity


def test_predictive_forecaster_prediction_classes_are_stable():
    forecaster = PredictiveSafetyForecaster()

    predictions = forecaster.generate_safety_predictions(
        [
            {"name": "overloaded", "load": 0.9, "vulnerability": 0.2},
            {"name": "vulnerable", "load": 0.4, "vulnerability": 0.8},
            {"name": "healthy", "load": 0.2, "vulnerability": 0.2},
        ]
    )

    by_prefix = {prediction.prediction_id.split("-")[1]: prediction for prediction in predictions if prediction.time_horizon == "24h"}
    assert by_prefix["overloaded"].predicted_event == "system_overload"
    assert by_prefix["vulnerable"].predicted_event == "security_breach"
    assert by_prefix["healthy"].predicted_event == "normal_operation"
