"""Test dashboard observability enhancements."""

import os
import pytest


def test_dashboard_has_agent_observability_section():
    """Verify the dashboard HTML includes the agent observability section."""
    html_path = os.path.join(
        os.path.dirname(__file__), "..", "dashboard", "static", "index.html"
    )
    with open(html_path, "r") as f:
        html = f.read()
    
    # Check for the new section
    assert 'id="agent-observability-section"' in html
    assert "Agent Observability" in html
    assert 'id="agent-observability-cards"' in html


def test_app_js_has_agent_observability_function():
    """Verify app.js includes the agent observability rendering function."""
    js_path = os.path.join(
        os.path.dirname(__file__), "..", "dashboard", "static", "app.js"
    )
    with open(js_path, "r") as f:
        js = f.read()
    
    # Check for the function
    assert "function renderAgentObservability" in js
    assert "agentObservabilityCards" in js


def test_css_has_card_status_styling():
    """Verify CSS includes styling for card status indicators."""
    css_path = os.path.join(
        os.path.dirname(__file__), "..", "dashboard", "static", "style.css"
    )
    with open(css_path, "r") as f:
        css = f.read()
    
    # Check for card status styling
    assert ".card-status" in css
    assert ".card-status.online" in css
    assert ".card-status.offline" in css


def test_dashboard_server_compiles():
    """Verify the dashboard server still compiles."""
    import subprocess
    import sys
    
    server_path = os.path.join(
        os.path.dirname(__file__), "..", "dashboard", "server.py"
    )
    
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", server_path],
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0, f"Dashboard server compilation failed: {result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])