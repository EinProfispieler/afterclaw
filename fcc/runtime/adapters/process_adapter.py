from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import shutil
import subprocess


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    message: str


def choose_process_tool() -> str:
    if shutil.which("ss"):
        return "ss"
    if shutil.which("netstat"):
        return "netstat"
    return ""


def execute_process_tool(args: list[str], *, tool: str | None = None) -> subprocess.CompletedProcess[str]:
    selected = str(tool or choose_process_tool() or "").strip()
    if not selected:
        raise RuntimeError("no process inspection tool available (ss/netstat)")
    argv = [selected] + [str(x) for x in (args or [])]
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def execute_command(
    argv: list[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> CommandResult:
    args = [str(x) for x in (argv or []) if str(x) != ""]
    if not args:
        return CommandResult(
            ok=False,
            argv=[],
            returncode=127,
            stdout="",
            stderr="",
            message="empty command",
        )
    tool = str(args[0] or "").strip()
    if not shutil.which(tool):
        return CommandResult(
            ok=False,
            argv=args,
            returncode=127,
            stdout="",
            stderr="",
            message=f"{tool} is not available",
        )
    try:
        out = subprocess.run(
            args,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            ok=False,
            argv=args,
            returncode=124,
            stdout="",
            stderr="",
            message=f"{tool} command timed out",
        )
    except Exception as exc:
        return CommandResult(
            ok=False,
            argv=args,
            returncode=1,
            stdout="",
            stderr="",
            message=str(exc),
        )
    msg = (out.stderr or out.stdout or "").strip()
    if out.returncode != 0 and not msg:
        msg = f"command failed (exit {out.returncode})"
    return CommandResult(
        ok=(out.returncode == 0),
        argv=args,
        returncode=int(out.returncode),
        stdout=str(out.stdout or ""),
        stderr=str(out.stderr or ""),
        message=msg,
    )
