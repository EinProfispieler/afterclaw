"""Terminal service bridge.

Bridges modular layer to shared runtime helpers in ``app.py``.
"""

from __future__ import annotations

import app as runtime_app


def build_terminal_launch_meta(cfg: dict) -> dict:
    return runtime_app._build_terminal_launch_meta(cfg)


def build_terminal_ssh_argv(cfg: dict):
    return runtime_app._build_terminal_ssh_argv(cfg)
