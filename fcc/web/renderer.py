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


def render_page(title: str, body_content: str, active_nav: str = "") -> str:
    """Render a generic page with navigation and theme support.
    
    Args:
        title: Page title
        body_content: HTML content for the page body
        active_nav: Active navigation item (e.g., "backup", "files")
    
    Returns:
        Complete HTML page
    """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} - AfterClaw</title>
  <script>
    (function(){{
      try {{
        var t = localStorage.getItem("fc-theme");
        if (!t) {{ t = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }}
        document.documentElement.setAttribute("data-theme", t);
      }} catch(e){{}}
    }})();
  </script>
  <link rel="stylesheet" href="/dashboard.css" />
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body>
  <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
    <div class="container-fluid">
      <a class="navbar-brand" href="/">AfterClaw</a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navbarNav">
        <ul class="navbar-nav">
          <li class="nav-item">
            <a class="nav-link {'active' if active_nav == 'dashboard' else ''}" href="/">Dashboard</a>
          </li>
          <li class="nav-item">
            <a class="nav-link {'active' if active_nav == 'backup' else ''}" href="/backup">Backup</a>
          </li>
          <li class="nav-item">
            <a class="nav-link {'active' if active_nav == 'terminal' else ''}" href="/terminal">Terminal</a>
          </li>
          <li class="nav-item">
            <a class="nav-link {'active' if active_nav == 'config' else ''}" href="/config">Config</a>
          </li>
        </ul>
        <ul class="navbar-nav ms-auto">
          <li class="nav-item">
            <button type="button" id="themeToggleBtn" class="btn btn-sm btn-outline-light">🌓</button>
          </li>
        </ul>
      </div>
    </div>
  </nav>
  
  {body_content}
  
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    // Theme toggle
    document.getElementById('themeToggleBtn')?.addEventListener('click', function() {{
      var current = document.documentElement.getAttribute('data-theme') || 'light';
      var next = current === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', next);
      try {{ localStorage.setItem('fc-theme', next); }} catch(e){{}}
    }});
  </script>
</body>
</html>"""
