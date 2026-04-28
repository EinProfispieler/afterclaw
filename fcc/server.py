"""FCC server runtime.

Phase 0 keeps a single runtime implementation in top-level ``app.py``.
``fcc`` package only exposes standardized startup/import paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import app as runtime_app


@dataclass(frozen=True)
class ServerInfo:
    host: str
    port: int
    storage_root: Path


def server_info() -> ServerInfo:
    return ServerInfo(
        host="0.0.0.0",
        port=int(runtime_app.DEFAULT_WEB_PORT),
        storage_root=Path(runtime_app.DEFAULT_STORAGE_ROOT),
    )


def main() -> None:
    """Start FCC HTTP server."""
    runtime_app.main()
