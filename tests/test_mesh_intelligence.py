"""Tests for Mesh Intelligence — ProjectX mesh analysis and routing."""

import pytest
from simp.projectx.mesh_intelligence import MeshIntelligence, BottleneckReport


class TestMeshIntelligence:
    def test_initialization(self) -> None:
        mi = MeshIntelligence()
        assert mi is not None

    def test_topology_returns_dict(self) -> None:
        mi = MeshIntelligence()
        topo = mi.topology()
        assert isinstance(topo, dict)
        assert "total_agents" in topo

    def test_route_method(self) -> None:
        mi = MeshIntelligence()
        assert hasattr(mi, "route") and callable(mi.route)
        result = mi.route("analyze BTC")
        assert result is None or isinstance(result, str)

    def test_record_call_method(self) -> None:
        mi = MeshIntelligence()
        assert hasattr(mi, "record_call") and callable(mi.record_call)
        mi.record_call("test-agent", latency_ms=45.0)
        # Should not raise

    def test_analyse_method(self) -> None:
        mi = MeshIntelligence()
        assert hasattr(mi, "analyse") and callable(mi.analyse)
        result = mi.analyse()
        assert isinstance(result, BottleneckReport)

    def test_start_stop_methods(self) -> None:
        mi = MeshIntelligence()
        assert hasattr(mi, "start") and callable(mi.start)
        assert hasattr(mi, "stop") and callable(mi.stop)


class TestTopologySnapshot:
    def test_topology_contains_agent_count(self) -> None:
        mi = MeshIntelligence()
        topo = mi.topology()
        assert "total_agents" in topo

    def test_topology_empty_mesh(self) -> None:
        mi = MeshIntelligence()
        topo = mi.topology()
        assert topo.get("total_agents", 0) == 0


class TestMetricsCollection:
    def test_record_call_no_raise(self) -> None:
        mi = MeshIntelligence()
        mi.record_call("test-agent", latency_ms=45.0)

    def test_record_call_with_error(self) -> None:
        mi = MeshIntelligence()
        mi.record_call("error-agent", latency_ms=100.0, error=True)

    def test_analyse_produces_bottleneck_report(self) -> None:
        mi = MeshIntelligence()
        mi.record_call("agent-1", latency_ms=100.0)
        result = mi.analyse()
        assert isinstance(result, BottleneckReport)
        assert hasattr(result, "bottleneck_agents")
        assert hasattr(result, "topology_snapshot")
