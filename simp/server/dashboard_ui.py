"""
Sprint 57 — Serve the SIMP dashboard on the broker port (5555).

Provides helpers to inject configuration into the dashboard HTML and
Flask routes for /dashboard, /dashboard/ui, and /dashboard/static/*.
"""

import os
from pathlib import Path

# Resolve dashboard assets relative to repo root
_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard"
_STATIC_DIR = _DASHBOARD_DIR / "static"


def build_dashboard_html(broker_url: str = "http://127.0.0.1:5555") -> str:
    """Read dashboard/static/index.html and inject ``window.SIMP_BROKER_URL``.

    Returns the full HTML string ready to serve.
    """
    html_path = _STATIC_DIR / "index.html"
    if not html_path.exists():
        # Fallback: try dashboard/index.html (a2a branch layout)
        html_path = _DASHBOARD_DIR / "index.html"
    if not html_path.exists():
        return (
            "<html><body><h1>SIMP Dashboard</h1>"
            "<p>index.html not found.</p></body></html>"
        )
    html = html_path.read_text(encoding="utf-8")
    # Inject broker URL as a global JS variable at the top of <head>
    inject = (
        f'<script>window.SIMP_BROKER_URL = "{broker_url}";</script>\n'
    )
    html = html.replace("<head>", f"<head>\n{inject}", 1)
    return html


def get_dashboard_js() -> str:
    """Return the contents of dashboard/static/app.js (or empty string)."""
    js_path = _STATIC_DIR / "app.js"
    if js_path.exists():
        return js_path.read_text(encoding="utf-8")
    return "// app.js not found"


def get_dashboard_css() -> str:
    """Return the contents of dashboard/static/style.css (or empty string)."""
    css_path = _STATIC_DIR / "style.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return "/* style.css not found */"
