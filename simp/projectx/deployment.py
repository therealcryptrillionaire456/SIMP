"""
ProjectX deployment/readiness manager.

Turns the ProjectX runtime into something shippable: generates concrete
readiness reports, points at deployment artifacts, and ensures the default
tool suite exists before declaring the system ready.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .benchmark import BenchmarkRunner
from .orchestrator import ProjectXOrchestrator
from .self_test import run_self_test
from .tool_factory import get_tool_factory


_ARTIFACT_ROOT = Path("deployment/projectx")


@dataclass
class DeploymentArtifact:
    name: str
    path: str
    exists: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "exists": self.exists,
        }


@dataclass
class ManifestValidationReport:
    status: str
    checks: Dict[str, bool] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "checks": dict(self.checks),
            "findings": list(self.findings),
        }


@dataclass
class DeploymentReadinessReport:
    status: str
    tool_suite: Dict[str, Any]
    self_test: Dict[str, Any]
    benchmark: Dict[str, Any]
    benchmark_history: Dict[str, Any]
    runtime_status: Dict[str, Any]
    manifest_validation: Dict[str, Any]
    artifacts: List[DeploymentArtifact] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "tool_suite": self.tool_suite,
            "self_test": self.self_test,
            "benchmark": self.benchmark,
            "benchmark_history": self.benchmark_history,
            "runtime_status": self.runtime_status,
            "manifest_validation": self.manifest_validation,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "missing_requirements": self.missing_requirements,
        }


class ProjectXDeploymentManager:
    """Build readiness evidence for the ProjectX runtime."""

    def __init__(self, orchestrator: Optional[ProjectXOrchestrator] = None) -> None:
        self._orchestrator = orchestrator or ProjectXOrchestrator()
        self._benchmark = BenchmarkRunner(executor_id="projectx_deployment")

    def readiness_report(self, fast: bool = True) -> DeploymentReadinessReport:
        tool_report = get_tool_factory(self._orchestrator).ensure_default_tools().to_dict()
        self_test = run_self_test(fast=fast).to_dict()
        benchmark_report = self._benchmark.run(
            self._orchestrator._executor,
            domains=["reasoning", "planning"] if fast else None,
        )
        benchmark = benchmark_report.to_dict()
        benchmark_history = self._benchmark.history_summary(limit=5).to_dict()
        runtime_status = self._orchestrator.get_status()
        artifacts = self._collect_artifacts()
        manifest_validation = self.validate_manifests().to_dict()
        missing: List[str] = []
        if tool_report["tool_count"] < 8:
            missing.append("default_tool_suite")
        if not self_test.get("passed"):
            missing.append("self_test")
        if benchmark.get("overall_score", 0.0) < 0.5:
            missing.append("benchmark_threshold")
        if benchmark_history.get("run_count", 0) < 1:
            missing.append("benchmark_history")
        missing.extend([artifact.name for artifact in artifacts if not artifact.exists])
        if manifest_validation["status"] != "valid":
            missing.append("manifest_validation")
        status = "ready" if not missing else "needs_attention"
        return DeploymentReadinessReport(
            status=status,
            tool_suite=tool_report,
            self_test=self_test,
            benchmark=benchmark,
            benchmark_history=benchmark_history,
            runtime_status=runtime_status,
            manifest_validation=manifest_validation,
            artifacts=artifacts,
            missing_requirements=missing,
        )

    @staticmethod
    def _collect_artifacts() -> List[DeploymentArtifact]:
        artifact_names = [
            ("dockerfile", _ARTIFACT_ROOT / "Dockerfile"),
            ("deployment_yaml", _ARTIFACT_ROOT / "deployment.yaml"),
            ("service_yaml", _ARTIFACT_ROOT / "service.yaml"),
            ("configmap_yaml", _ARTIFACT_ROOT / "configmap.yaml"),
            ("hpa_yaml", _ARTIFACT_ROOT / "hpa.yaml"),
        ]
        return [
            DeploymentArtifact(name=name, path=str(path), exists=path.exists())
            for name, path in artifact_names
        ]

    @staticmethod
    def validate_manifests() -> ManifestValidationReport:
        checks: Dict[str, bool] = {}
        findings: List[str] = []

        def _load_yaml(path: Path) -> Dict[str, Any]:
            if not path.exists():
                findings.append(f"missing:{path.name}")
                return {}
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if not isinstance(data, dict):
                    findings.append(f"invalid_yaml:{path.name}")
                    return {}
                return data
            except Exception as exc:
                findings.append(f"invalid_yaml:{path.name}:{exc}")
                return {}

        deployment = _load_yaml(_ARTIFACT_ROOT / "deployment.yaml")
        service = _load_yaml(_ARTIFACT_ROOT / "service.yaml")
        configmap = _load_yaml(_ARTIFACT_ROOT / "configmap.yaml")
        hpa = _load_yaml(_ARTIFACT_ROOT / "hpa.yaml")

        dep_spec = deployment.get("spec") or {}
        dep_template_spec = ((dep_spec.get("template") or {}).get("spec") or {})
        dep_containers = dep_template_spec.get("containers") or []
        dep_container = dep_containers[0] if dep_containers else {}
        dep_resources = dep_container.get("resources") or {}
        dep_probes = {
            "readiness": ((dep_container.get("readinessProbe") or {}).get("httpGet") or {}),
            "liveness": ((dep_container.get("livenessProbe") or {}).get("httpGet") or {}),
        }

        checks["deployment_kind"] = deployment.get("kind") == "Deployment"
        checks["deployment_replicas"] = int(dep_spec.get("replicas") or 0) >= 2
        checks["deployment_image"] = bool(dep_container.get("image"))
        checks["deployment_probe_paths"] = (
            dep_probes["readiness"].get("path") == "/health"
            and dep_probes["liveness"].get("path") == "/health"
        )
        checks["deployment_resources"] = bool(dep_resources.get("requests")) and bool(dep_resources.get("limits"))

        svc_spec = service.get("spec") or {}
        svc_ports = svc_spec.get("ports") or []
        svc_port = svc_ports[0] if svc_ports else {}
        checks["service_kind"] = service.get("kind") == "Service"
        checks["service_target_port"] = int(svc_port.get("targetPort") or 0) == 5555

        cfg_data = configmap.get("data") or {}
        checks["configmap_kind"] = configmap.get("kind") == "ConfigMap"
        checks["configmap_runtime_keys"] = "PROJECTX_HOST" in cfg_data and "PROJECTX_PORT" in cfg_data

        hpa_spec = hpa.get("spec") or {}
        hpa_metrics = hpa_spec.get("metrics") or []
        resource_targets = {
            ((metric.get("resource") or {}).get("name")): metric
            for metric in hpa_metrics
            if isinstance(metric, dict)
        }
        checks["hpa_kind"] = hpa.get("kind") == "HorizontalPodAutoscaler"
        checks["hpa_target"] = ((hpa_spec.get("scaleTargetRef") or {}).get("name")) == "projectx-runtime"
        checks["hpa_replica_range"] = (
            int(hpa_spec.get("minReplicas") or 0) >= 2
            and int(hpa_spec.get("maxReplicas") or 0) > int(hpa_spec.get("minReplicas") or 0)
        )
        checks["hpa_cpu_metric"] = "cpu" in resource_targets
        checks["hpa_memory_metric"] = "memory" in resource_targets

        for name, ok in checks.items():
            if not ok:
                findings.append(name)

        return ManifestValidationReport(
            status="valid" if all(checks.values()) else "invalid",
            checks=checks,
            findings=findings,
        )
