"""Tests for Sprint 28: operator docs surface and ProjectX overview UI."""

import os


def test_system_overview_ui_elements_exist():
    root = os.path.join(os.path.dirname(__file__), "..", "dashboard", "static")
    with open(os.path.join(root, "index.html"), encoding="utf-8") as fh:
        html = fh.read()
    with open(os.path.join(root, "app.js"), encoding="utf-8") as fh:
        js = fh.read()

    assert "system-overview-section" in html
    assert "system-overview-summary" in html
    assert "system-overview-cards" in html
    assert "system-overview-actions" in html
    assert "renderSystemOverview" in js
    assert "answer_source_path" in js
