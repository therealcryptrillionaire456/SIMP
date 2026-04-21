"""
Deterministic predictive forecasting for BRP.

This ports the useful core of the external Day 4 prototype into a repo-native
module. Forecasts are bounded, deterministic, and suitable for tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence, Tuple


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ThreatForecast:
    forecast_id: str
    threat_type: str
    predicted_severity: float
    confidence_level: float
    time_window_hours: int
    probability: float
    affected_systems: List[str]
    mitigation_recommendations: List[str]
    timestamp: str


@dataclass
class SafetyPrediction:
    prediction_id: str
    predicted_event: str
    confidence_interval: Tuple[float, float]
    likelihood: float
    impact_score: float
    time_horizon: str
    prevention_strategies: List[str]
    timestamp: str


class PredictiveSafetyForecaster:
    """Forecast likely future threats and system safety outcomes."""

    def __init__(self) -> None:
        self.threat_models = self._default_models()
        self.forecast_history: List[Dict[str, Any]] = []

    @staticmethod
    def _default_models() -> Dict[str, Dict[str, Any]]:
        return {
            "zero_day": {
                "base_probability": 0.1,
                "growth_rate": 0.15,
                "seasonal_factor": 1.2,
                "confidence_interval": (0.7, 0.95),
            },
            "apt": {
                "base_probability": 0.2,
                "growth_rate": 0.1,
                "seasonal_factor": 1.1,
                "confidence_interval": (0.8, 0.98),
            },
            "malware": {
                "base_probability": 0.3,
                "growth_rate": 0.05,
                "seasonal_factor": 1.0,
                "confidence_interval": (0.75, 0.9),
            },
            "insider_threat": {
                "base_probability": 0.15,
                "growth_rate": 0.08,
                "seasonal_factor": 1.05,
                "confidence_interval": (0.6, 0.85),
            },
        }

    def generate_threat_forecasts(
        self,
        current_threats: Sequence[Dict[str, Any]],
        forecast_horizon: int = 48,
    ) -> List[ThreatForecast]:
        by_type = {str(item.get("type", "")).strip(): item for item in current_threats}
        forecasts: List[ThreatForecast] = []

        for threat_type, model in self.threat_models.items():
            source = by_type.get(threat_type, {})
            current_severity = float(source.get("severity", model["base_probability"]))
            description = str(source.get("description", "")).lower()
            description_boost = 0.05 if "critical" in description else 0.0

            for hours_ahead in range(6, forecast_horizon + 1, 6):
                time_factor = 1 + (model["growth_rate"] * hours_ahead / 24)
                seasonal_adjustment = self._seasonal_adjustment(
                    model["seasonal_factor"],
                    hours_ahead,
                )
                probability = min(
                    0.99,
                    max(
                        model["base_probability"],
                        current_severity * time_factor * seasonal_adjustment + description_boost,
                    ),
                )
                predicted_severity = min(0.99, 0.55 * probability + 0.45 * current_severity)
                confidence_level = self._confidence_for_probability(
                    probability,
                    model["confidence_interval"],
                )
                forecast = ThreatForecast(
                    forecast_id=f"FORECAST-{threat_type}-{hours_ahead}h",
                    threat_type=threat_type,
                    predicted_severity=round(predicted_severity, 4),
                    confidence_level=round(confidence_level, 4),
                    time_window_hours=hours_ahead,
                    probability=round(probability, 4),
                    affected_systems=self.determine_affected_systems(threat_type, hours_ahead),
                    mitigation_recommendations=self.generate_mitigation_recommendations(
                        threat_type,
                        predicted_severity,
                    ),
                    timestamp=_utc_now(),
                )
                forecasts.append(forecast)

        self.forecast_history.extend(asdict(forecast) for forecast in forecasts)
        return forecasts

    def generate_safety_predictions(self, system_data: Sequence[Dict[str, Any]]) -> List[SafetyPrediction]:
        predictions: List[SafetyPrediction] = []
        for system in system_data:
            system_name = str(system.get("name", "unknown"))
            system_load = float(system.get("load", 0.5))
            system_vulnerability = float(system.get("vulnerability", 0.3))

            for time_horizon in ("24h", "48h", "72h", "1w"):
                horizon_multiplier = {"24h": 1.2, "48h": 1.5, "72h": 1.8, "1w": 2.0}[time_horizon]
                impact_multiplier = {"24h": 0.8, "48h": 0.9, "72h": 0.95, "1w": 1.0}[time_horizon]
                base_likelihood = system_load * system_vulnerability
                likelihood = min(0.99, base_likelihood * horizon_multiplier)
                impact_score = min(0.99, base_likelihood * impact_multiplier)
                confidence_interval = (
                    round(max(0.1, likelihood - 0.2), 4),
                    round(min(0.99, likelihood + 0.2), 4),
                )
                predicted_event = self._predicted_event(system_load, system_vulnerability, likelihood)
                predictions.append(
                    SafetyPrediction(
                        prediction_id=f"PRED-{system_name}-{time_horizon}",
                        predicted_event=predicted_event,
                        confidence_interval=confidence_interval,
                        likelihood=round(likelihood, 4),
                        impact_score=round(impact_score, 4),
                        time_horizon=time_horizon,
                        prevention_strategies=self.generate_prevention_strategies(
                            predicted_event,
                            likelihood,
                            time_horizon,
                        ),
                        timestamp=_utc_now(),
                    )
                )
        return predictions

    def forecast_accuracy_analysis(self) -> Dict[str, Any]:
        total_forecasts = len(self.forecast_history)
        if total_forecasts == 0:
            return {"error": "No forecast history available"}

        accurate_forecasts = sum(
            1 for forecast in self.forecast_history if float(forecast.get("confidence_level", 0)) >= 0.8
        )
        average_confidence = round(
            sum(float(forecast.get("confidence_level", 0)) for forecast in self.forecast_history) / total_forecasts,
            4,
        )

        time_window_accuracy: Dict[int, Dict[str, Any]] = {}
        for forecast in self.forecast_history:
            time_window = int(forecast.get("time_window_hours", 0))
            bucket = time_window_accuracy.setdefault(time_window, {"total": 0, "accurate": 0})
            bucket["total"] += 1
            if float(forecast.get("confidence_level", 0)) >= 0.8:
                bucket["accurate"] += 1

        for bucket in time_window_accuracy.values():
            bucket["accuracy"] = round(bucket["accurate"] / bucket["total"], 4) if bucket["total"] else 0.0

        return {
            "total_forecasts": total_forecasts,
            "accurate_forecasts": accurate_forecasts,
            "overall_accuracy": round(accurate_forecasts / total_forecasts, 4),
            "average_confidence": average_confidence,
            "time_window_accuracy": time_window_accuracy,
            "forecast_horizon": "48h",
            "timestamp": _utc_now(),
        }

    @staticmethod
    def determine_affected_systems(threat_type: str, time_horizon: int) -> List[str]:
        system_mapping = {
            "zero_day": ["api_gateway", "database", "file_system", "network_layer"],
            "apt": ["financial_systems", "data_storage", "authentication_servers", "network_infrastructure"],
            "malware": ["user_workstations", "file_shares", "email_servers", "web_servers"],
            "insider_threat": ["sensitive_data", "admin_systems", "audit_logs", "backup_systems"],
        }
        base_systems = list(system_mapping.get(threat_type, ["all_systems"]))
        if time_horizon > 24:
            base_systems.extend(["cloud_services", "third_party_integrations"])
        return base_systems

    @staticmethod
    def generate_mitigation_recommendations(threat_type: str, severity: float) -> List[str]:
        if threat_type == "zero_day":
            if severity > 0.8:
                return [
                    "Implement immediate network segmentation",
                    "Deploy quantum-resistant encryption",
                    "Enable enhanced monitoring",
                    "Prepare incident response team",
                ]
            return [
                "Update threat intelligence",
                "Review security configurations",
                "Monitor for unusual activity",
            ]
        if threat_type == "apt":
            if severity > 0.8:
                return [
                    "Activate advanced threat detection",
                    "Implement behavioral analysis",
                    "Review access controls",
                    "Prepare for containment",
                ]
            return [
                "Monitor network traffic",
                "Review user activities",
                "Update security policies",
            ]
        if threat_type == "malware":
            if severity > 0.8:
                return [
                    "Activate endpoint protection",
                    "Scan all systems",
                    "Block suspicious connections",
                    "Update antivirus signatures",
                ]
            return [
                "Update antivirus definitions",
                "Review file integrity",
                "Monitor for unusual processes",
            ]
        if severity > 0.8:
            return [
                "Review user access",
                "Monitor privileged activities",
                "Implement data loss prevention",
                "Review audit logs",
            ]
        return [
            "Monitor user behavior",
            "Review access patterns",
            "Update security policies",
        ]

    @staticmethod
    def generate_prevention_strategies(event_type: str, likelihood: float, time_horizon: str) -> List[str]:
        if event_type == "system_overload":
            return [
                "Scale resources",
                "Implement load balancing",
                "Add monitoring alerts",
                "Prepare failover systems",
            ]
        if event_type == "security_breach":
            return [
                "Update security patches",
                "Review access controls",
                "Implement additional monitoring",
                "Prepare incident response",
            ]
        if event_type == "performance_degradation":
            return [
                "Optimize performance",
                "Review resource allocation",
                "Monitor system health",
                "Plan capacity upgrades",
            ]
        return [
            "Maintain current configuration",
            "Continue monitoring",
            "Review performance metrics",
        ]

    @staticmethod
    def _seasonal_adjustment(seasonal_factor: float, hours_ahead: int) -> float:
        cycle = (hours_ahead % 24) / 24
        wave = 1 + (0.1 if cycle in {0.25, 0.5, 0.75} else 0.0)
        return seasonal_factor * wave

    @staticmethod
    def _confidence_for_probability(probability: float, interval: Tuple[float, float]) -> float:
        low, high = interval
        return min(high, max(low, low + ((high - low) * probability)))

    @staticmethod
    def _predicted_event(system_load: float, system_vulnerability: float, likelihood: float) -> str:
        if system_load > 0.8:
            return "system_overload"
        if system_vulnerability > 0.7:
            return "security_breach"
        if likelihood > 0.6:
            return "performance_degradation"
        return "normal_operation"
