"""FCC module registry.

The registry is a Phase 0 foundation so features can be migrated out of
`app.py` incrementally without breaking runtime compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any

HandlerFn = Callable[[Any, Any, dict, Any], None]


@dataclass
class Route:
    method: str
    path_pattern: str
    handler: HandlerFn

    def match(self, method: str, path: str) -> dict | None:
        if method.upper() != self.method.upper():
            return None
        pattern = self.path_pattern
        if "<path>" in pattern:
            prefix = pattern.split("<path>", 1)[0]
            if path.startswith(prefix):
                return {"path": path[len(prefix):]}
            return None
        if path == pattern:
            return {}
        return None


@dataclass
class Module:
    name: str = ""
    display_name: str = ""
    description: str = ""
    platforms: list[str] = field(default_factory=lambda: ["all"])
    routes: list[Route] = field(default_factory=list)

    def add_route(self, method: str, path_pattern: str, handler: HandlerFn) -> None:
        self.routes.append(Route(method=method.upper(), path_pattern=path_pattern, handler=handler))

    def is_enabled(self, config: dict) -> bool:
        if not self.name:
            return False
        mods = (config or {}).get("modules") or {}
        return bool(mods.get(self.name, True))

    def on_start(self) -> None:
        return None

    def on_stop(self) -> None:
        return None


REGISTRY: dict[str, Module] = {}


def register(module: Module) -> None:
    if not module.name:
        raise ValueError("module.name 不能为空")
    REGISTRY[module.name] = module


def unregister(name: str) -> None:
    REGISTRY.pop(name, None)


def list_modules() -> list[Module]:
    return list(REGISTRY.values())
