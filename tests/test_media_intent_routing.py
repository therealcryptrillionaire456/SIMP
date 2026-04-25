"""
Integration tests for Media Center Intent Routing (Tranche 1).

Tests that:
1. MEDIA_INTENT_TYPES all have valid intent_type keys
2. MediaGridOrchestrator.handle_media_intent() routes correctly
3. MediaSignalRouter bridges to orchestrator
4. Full round-trip: intent string → workflow execution
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
async def orchestrator(temp_data_dir):
    """Create a MediaGridOrchestrator with temp data dir for testing."""
    from simp.organs.media.orchestration import MediaGridOrchestrator
    from simp.organs.media.config import get_config

    from simp.organs.media.config import MediaEnvironment

    config = get_config()
    config.data_dir = temp_data_dir
    config.environment = MediaEnvironment.DEVELOPMENT

    orch = MediaGridOrchestrator(config=config)
    success = await orch.initialize()
    assert success, "Orchestrator should initialize successfully"
    return orch


# ── Tests: MEDIA_INTENT_TYPES completeness ───────────────────────────────

def test_media_intent_types_defined():
    """All MEDIA_INTENT_TYPES should be valid non-empty strings with unique keys."""
    from simp.organs.media import MEDIA_INTENT_TYPES

    assert isinstance(MEDIA_INTENT_TYPES, dict)
    assert len(MEDIA_INTENT_TYPES) > 0, "Should have at least one intent type"

    # Check no duplicate keys
    keys = list(MEDIA_INTENT_TYPES.keys())
    assert len(keys) == len(set(keys)), f"Duplicate keys found: {keys}"

    # Each value should be a non-empty description
    for k, v in MEDIA_INTENT_TYPES.items():
        assert k.startswith("media."), f"Key {k} should start with 'media.'"
        assert isinstance(v, str) and len(v) > 0, f"Value for {k} should be non-empty string"


def test_media_intent_types_coverage():
    """All intent types should have a corresponding handler in the orchestrator."""
    from simp.organs.media import MEDIA_INTENT_TYPES
    from simp.organs.media.orchestration import MediaGridOrchestrator

    # Build expected handler map from method names
    intent_to_method = {
        "media.trend_research": "_execute_trend_research_workflow",
        "media.offer_scoring": "_execute_offer_scoring_workflow",
        "media.script_generation": "_execute_script_generation_workflow",
        "media.asset_generation": "_execute_asset_generation_workflow",
        "media.content_packaging": "_execute_content_packaging_workflow",
        "media.content_publishing": "_execute_content_publishing_workflow",
        "media.performance_tracking": "_execute_performance_tracking_workflow",
        "media.landing_page_generation": "_execute_landing_page_workflow",
        "media.optimization_recommendation": "_execute_optimization_workflow",
        "media.simp_news_generation": "_execute_simp_news_workflow",
        "media.offer_intelligence": "_execute_offer_intelligence_workflow",
    }

    for intent_type in MEDIA_INTENT_TYPES:
        method_name = intent_to_method.get(intent_type)
        assert method_name is not None, f"Missing handler mapping for {intent_type}"
        assert hasattr(MediaGridOrchestrator, method_name), \
            f"MediaGridOrchestrator missing method {method_name} for {intent_type}"


# ── Tests: handle_media_intent ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_media_intent_unknown_type(orchestrator):
    """Unknown intent type should return error."""
    result = await orchestrator.handle_media_intent("media.unknown_type", {})
    assert result["status"] == "error"
    assert "unknown" in result["error"].lower() or "Unknown" in result["error"]


@pytest.mark.asyncio
async def test_handle_media_intent_trend_research(orchestrator):
    """Trend research intent should return a structured result."""
    result = await orchestrator.handle_media_intent("media.trend_research", {
        "limit": 3
    })

    assert result["status"] == "success"
    assert result["intent_type"] == "media.trend_research"
    assert "workflow_id" in result
    assert "result" in result


@pytest.mark.asyncio
async def test_handle_media_intent_offer_scoring(orchestrator):
    """Offer scoring intent should route correctly."""
    result = await orchestrator.handle_media_intent("media.offer_scoring", {
        "offers": []
    })
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_handle_media_intent_all_types(orchestrator):
    """All media intent types should route without crashing."""
    from simp.organs.media import MEDIA_INTENT_TYPES

    for intent_type in MEDIA_INTENT_TYPES:
        result = await orchestrator.handle_media_intent(intent_type, {})
        # May succeed or fail gracefully, but should never raise
        assert "intent_type" in result
        assert result["intent_type"] == intent_type


# ── Tests: MediaSignalRouter ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_media_signal_router_creates_orchestrator():
    """MediaSignalRouter should lazy-load an orchestrator."""
    from simp.routing.signal_router import MediaSignalRouter

    router = MediaSignalRouter()
    orch = router.orchestrator
    assert orch is not None, "Should auto-create orchestrator"


@pytest.mark.asyncio
async def test_media_signal_router_routes_intent():
    """MediaSignalRouter should route intents through the orchestrator."""
    from simp.routing.signal_router import MediaSignalRouter

    router = MediaSignalRouter()
    result = await router.route_media_intent("media.trend_research", {"limit": 2})

    assert result is not None
    # May error if no SIMP broker running, but should return structured result
    assert "status" in result or "intent_type" in result


def test_media_signal_router_sync():
    """Synchronous wrapper should work."""
    from simp.routing.signal_router import MediaSignalRouter

    router = MediaSignalRouter()
    result = router.route_media_intent_sync("media.trend_research", {"limit": 1})
    assert result is not None


# ── Tests: Journal persistence ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_media_router_journal_persists():
    """Media router should persist intent records to journal."""
    from simp.routing.signal_router import MediaSignalRouter
    from simp.routing.signal_router import REPO

    journal_path = REPO / "data" / "media_router_journal.jsonl"
    # Remove if exists for clean test
    if journal_path.exists():
        journal_path.unlink()

    router = MediaSignalRouter()
    await router.route_media_intent("media.trend_research", {"limit": 1})

    # Journal should have been created
    assert journal_path.exists(), "Journal file should exist"
    content = journal_path.read_text()
    assert "media.trend_research" in content
    assert "intent_type" in content


# ── Tests: Module exports ─────────────────────────────────────────────────

def test_module_exports_media_classes():
    """Media classes should be importable from the right places."""
    from simp.organs.media import MEDIA_INTENT_TYPES, create_media_grid_agents
    from simp.organs.media.orchestration import MediaGridOrchestrator, run_media_grid
    from simp.organs.media.config import MediaGridConfig, get_config

    assert isinstance(MEDIA_INTENT_TYPES, dict)
    assert callable(create_media_grid_agents)
    assert callable(get_config)


def test_signal_router_exports_media_router():
    """MediaSignalRouter should be exportable from signal_router."""
    from simp.routing.signal_router import MediaSignalRouter

    assert MediaSignalRouter is not None


# ── Run directly ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
