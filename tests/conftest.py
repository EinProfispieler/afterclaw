from __future__ import annotations

import importlib
import types
import sys


def _install_stub_modules_for_non_posix() -> None:
    """Allow importing app.py on non-POSIX runners during test collection."""

    is_windows = sys.platform.startswith("win")

    if is_windows:
        mod = types.ModuleType("fcntl")
        mod.ioctl = lambda *_args, **_kwargs: 0
        sys.modules["fcntl"] = mod
    else:
        try:
            importlib.import_module("fcntl")
        except ModuleNotFoundError:
            mod = types.ModuleType("fcntl")
            mod.ioctl = lambda *_args, **_kwargs: 0
            sys.modules["fcntl"] = mod

    if is_windows:
        mod = types.ModuleType("termios")
        mod.TIOCSWINSZ = 0
        sys.modules["termios"] = mod
    else:
        try:
            importlib.import_module("termios")
        except ModuleNotFoundError:
            mod = types.ModuleType("termios")
            mod.TIOCSWINSZ = 0
            sys.modules["termios"] = mod

    if is_windows:
        mod = types.ModuleType("pwd")

        class _Pw:
            pw_dir = "/tmp"
            pw_uid = 0
            pw_gid = 0

        mod.getpwnam = lambda _user: _Pw()
        sys.modules["pwd"] = mod
    else:
        try:
            importlib.import_module("pwd")
        except ModuleNotFoundError:
            mod = types.ModuleType("pwd")

            class _Pw:
                pw_dir = "/tmp"
                pw_uid = 0
                pw_gid = 0

            mod.getpwnam = lambda _user: _Pw()
            sys.modules["pwd"] = mod

    if is_windows:
        mod = types.ModuleType("pty")

        def _unsupported_openpty():
            raise OSError("pty is not available on this platform")

        mod.openpty = _unsupported_openpty
        sys.modules["pty"] = mod
    else:
        try:
            importlib.import_module("pty")
        except ModuleNotFoundError:
            mod = types.ModuleType("pty")

            def _unsupported_openpty():
                raise OSError("pty is not available on this platform")

            mod.openpty = _unsupported_openpty
            sys.modules["pty"] = mod


_install_stub_modules_for_non_posix()
