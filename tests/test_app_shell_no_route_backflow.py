from __future__ import annotations

import ast
from pathlib import Path


def _app_tree() -> ast.AST:
    root = Path(__file__).resolve().parent.parent
    src = (root / "app.py").read_text(encoding="utf-8")
    return ast.parse(src)


def _method_node(tree: ast.AST, class_name: str, method_name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                return item
    raise AssertionError(f"method {class_name}.{method_name} not found")


def _parsed_path_eq_literals(fn_node: ast.FunctionDef) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Compare):
            continue
        if not (
            isinstance(node.left, ast.Attribute)
            and isinstance(node.left.value, ast.Name)
            and node.left.value.id == "parsed"
            and node.left.attr == "path"
        ):
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        rhs = node.comparators[0]
        if isinstance(rhs, ast.Constant) and isinstance(rhs.value, str):
            found.add(rhs.value)
    return found


def test_no_route_backflow_in_do_get_do_post():
    tree = _app_tree()
    do_get = _method_node(tree, "AppHandler", "do_GET")
    do_post = _method_node(tree, "AppHandler", "do_POST")
    route_eq_literals = _parsed_path_eq_literals(do_get) | _parsed_path_eq_literals(do_post)

    migrated_routes = {
        "/api/base",
        "/api/speed",
        "/api/metrics/history",
        "/api/process-net",
        "/api/transfers",
        "/api/control/status",
        "/api/http/path-scan",
        "/api/directories",
        "/api/files",
        "/api/control/http-access",
        "/api/control/downloads",
        "/api/control/restart",
        "/healthz/restart",
        "/api/http/source-ip-pools/sync",
        "/api/app-config",
        "/api/qbt/discover",
        "/api/qbt/fix-monitor",
        "/api/qbt/optimize-config",
    }
    leaked = sorted(migrated_routes & route_eq_literals)
    assert not leaked, f"migrated routes leaked back to app.py main flow: {leaked}"
