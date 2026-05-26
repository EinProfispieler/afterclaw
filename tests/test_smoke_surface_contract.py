from __future__ import annotations

import ast
from pathlib import Path


def _app_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "app.py").read_text(encoding="utf-8")


def _docker_api_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "fcc/modules/docker/api.py").read_text(encoding="utf-8")


def _qbt_api_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "fcc/modules/qbt/api.py").read_text(encoding="utf-8")


def _files_api_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "fcc/modules/files/api.py").read_text(encoding="utf-8")


def _control_api_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "fcc/modules/control/api.py").read_text(encoding="utf-8")


def _status_api_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "fcc/modules/status/api.py").read_text(encoding="utf-8")


def _http_api_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "fcc/modules/http/api.py").read_text(encoding="utf-8")


def _appconfig_api_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "fcc/modules/appconfig/api.py").read_text(encoding="utf-8")


def _api_route_literals_from_source(source: str, prefix: str) -> set[str]:
    routes: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        value = node.value.strip()
        if value.startswith(prefix):
            routes.add(value)
    return routes


def _docker_route_contract() -> set[str]:
    return _api_route_literals_from_source(_app_source(), "/api/docker/") | _api_route_literals_from_source(
        _docker_api_source(), "/api/docker/"
    )


def test_apphandler_http_entrypoints_exist_smoke():
    src = _app_source()
    assert "class AppHandler(BaseHTTPRequestHandler):" in src
    assert "def do_GET(self):" in src
    assert "def do_POST(self):" in src


def test_core_pages_routes_exist_smoke():
    src = _app_source()
    for route in ('"/"', '"/config"', '"/terminal"', '"/member"'):
        assert f'if parsed.path == {route}' in src


def test_docker_routes_exist_smoke():
    routes = _docker_route_contract()
    read_routes = {
        "/api/docker/containers",
        "/api/docker/logs",
        "/api/docker/recommendations",
        "/api/docker/images",
    }
    write_routes = {
        "/api/docker/action",
        "/api/docker/image/pull",
        "/api/docker/container/create",
        "/api/docker/container/remove",
        "/api/docker/image/remove",
    }
    assert read_routes.issubset(routes)
    assert write_routes.issubset(routes)


def test_qbt_routes_exist_smoke():
    routes = _api_route_literals_from_source(_app_source(), "/api/qbt/") | _api_route_literals_from_source(
        _qbt_api_source(), "/api/qbt/"
    )
    required = {
        "/api/qbt/discover",
        "/api/qbt/fix-monitor",
        "/api/qbt/optimize-config",
    }
    assert required.issubset(routes)


def test_files_routes_exist_smoke():
    routes = _api_route_literals_from_source(_app_source(), "/api/") | _api_route_literals_from_source(
        _files_api_source(), "/api/"
    )
    required = {
        "/api/http/path-scan",
        "/api/directories",
        "/api/files",
    }
    assert required.issubset(routes)


def test_control_restart_routes_exist_smoke():
    routes = _api_route_literals_from_source(_app_source(), "/") | _api_route_literals_from_source(
        _control_api_source(), "/"
    )
    required = {
        "/api/control/http-access",
        "/api/control/downloads",
        "/api/control/restart",
        "/healthz/restart",
    }
    assert required.issubset(routes)


def test_status_routes_exist_smoke():
    routes = _api_route_literals_from_source(_app_source(), "/api/") | _api_route_literals_from_source(
        _status_api_source(), "/api/"
    )
    required = {
        "/api/base",
        "/api/speed",
        "/api/metrics/history",
        "/api/process-net",
        "/api/transfers",
        "/api/control/status",
    }
    assert required.issubset(routes)


def test_http_routes_exist_smoke():
    routes = _api_route_literals_from_source(_app_source(), "/api/http/") | _api_route_literals_from_source(
        _http_api_source(), "/api/http/"
    )
    required = {
        "/api/http/source-ip-pools/sync",
    }
    assert required.issubset(routes)


def test_appconfig_routes_exist_smoke():
    routes = _api_route_literals_from_source(_app_source(), "/api/") | _api_route_literals_from_source(
        _appconfig_api_source(), "/api/"
    )
    required = {
        "/api/app-config",
    }
    assert required.issubset(routes)


def test_modular_dispatch_entrypoints_exist_smoke():
    src = _app_source()
    assert "def _dispatch_modular_get_apis(self, parsed) -> bool:" in src
    assert "def _dispatch_modular_post_apis(self, parsed) -> bool:" in src
    assert "if self._dispatch_modular_get_apis(parsed):" in src
    assert "if self._dispatch_modular_post_apis(parsed):" in src
