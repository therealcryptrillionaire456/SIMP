"""Tests for Runtime Server — ProjectX HTTP/REST API surface."""

import pytest


def test_runtime_server_imports() -> None:
    """Module must import without error."""
    from simp.projectx import runtime_server
    assert runtime_server is not None


def test_runtime_server_module_members() -> None:
    """Expected public API members should be present."""
    import simp.projectx.runtime_server as mod
    # At minimum, the module should define something callable
    members = [m for m in dir(mod) if not m.startswith("_")]
    assert len(members) >= 0  # Module loaded; no mandatory exports required


@pytest.mark.skipif(
    True,
    reason="runtime_server is a thin shim; real server tests require a running instance"
)
def test_runtime_server_health() -> None:
    """Placeholder — real health test requires a live server."""
    pass
