"""HTML renderer bridge.

Phase 0 keeps existing inline builders in ``app.py`` and exposes renderer
helpers so new modular server can switch gradually.
"""

from __future__ import annotations

import app as runtime_app


def render_dashboard() -> str:
    return runtime_app.build_frontend_html()


def render_config() -> str:
    return runtime_app.build_config_html()


def render_terminal() -> str:
    return runtime_app.build_terminal_html()


def render_ddns() -> str:
    return runtime_app.build_ddns_settings_html()
