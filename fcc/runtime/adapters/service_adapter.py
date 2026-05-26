from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import platform
import shutil
import subprocess

_ACTIONS = {"start", "stop", "restart"}


@dataclass(frozen=True)
class ServiceActionResult:
    ok: bool
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    message: str


def _normalize_action(action: str) -> str:
    value = str(action or "").strip().lower()
    if value not in _ACTIONS:
        raise ValueError("unsupported service action")
    return value


def _platform_name(system: str | None = None) -> str:
    return str(system or platform.system() or "").strip().lower()


def self_restart_commands(
    *,
    systemd_unit: str,
    launchd_label: str,
    system: str | None = None,
) -> tuple[list[list[str]], str]:
    sys_name = _platform_name(system)
    if sys_name == "linux":
        if not shutil.which("systemctl"):
            return [], "systemctl is not available"
        unit = str(systemd_unit or "").strip()
        if not unit:
            return [], "missing systemd unit"
        return [["systemctl", "restart", unit]], ""
    if sys_name == "darwin":
        if not shutil.which("launchctl"):
            return [], "launchctl is not available"
        label = str(launchd_label or "").strip()
        if not label:
            return [], "missing launchd label"
        uid = os.getuid()
        targets: list[str] = []
        daemon_plist = Path("/Library/LaunchDaemons") / f"{label}.plist"
        agent_plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
        if daemon_plist.exists():
            targets.append(f"system/{label}")
        if agent_plist.exists():
            targets.append(f"gui/{uid}/{label}")
        if not targets:
            targets = [f"system/{label}", f"gui/{uid}/{label}"]
        return [["launchctl", "kickstart", "-k", target] for target in targets], ""
    return [], f"unsupported platform: {platform.system() or 'unknown'}"


def _service_command(action: str, unit: str, system: str | None = None) -> tuple[list[str], str]:
    safe_action = _normalize_action(action)
    safe_unit = str(unit or "").strip()
    if not safe_unit:
        return [], "missing service unit"
    sys_name = _platform_name(system)
    if sys_name == "linux":
        if not shutil.which("systemctl"):
            return [], "systemctl is not available"
        return ["systemctl", safe_action, safe_unit], ""
    if sys_name == "darwin":
        if not shutil.which("launchctl"):
            return [], "launchctl is not available"
        if "/" not in safe_unit:
            safe_unit = f"gui/{os.getuid()}/{safe_unit}"
        if safe_action == "restart":
            return ["launchctl", "kickstart", "-k", safe_unit], ""
        if safe_action == "stop":
            return ["launchctl", "bootout", safe_unit], ""
        return [], "launchctl start action requires bootstrap context"
    return [], f"unsupported platform: {platform.system() or 'unknown'}"


def execute_service_action(
    action: str,
    unit: str,
    *,
    system: str | None = None,
) -> ServiceActionResult:
    argv, err = _service_command(action, unit, system=system)
    if err:
        return ServiceActionResult(
            ok=False,
            argv=argv,
            returncode=127,
            stdout="",
            stderr="",
            message=err,
        )
    try:
        out = subprocess.run(argv, capture_output=True, text=True, check=False)
    except Exception as exc:
        return ServiceActionResult(
            ok=False,
            argv=argv,
            returncode=1,
            stdout="",
            stderr="",
            message=str(exc),
        )
    msg = (out.stderr or out.stdout or "").strip()
    if out.returncode != 0 and not msg:
        msg = f"service action failed (exit {out.returncode})"
    return ServiceActionResult(
        ok=(out.returncode == 0),
        argv=list(argv),
        returncode=int(out.returncode),
        stdout=str(out.stdout or ""),
        stderr=str(out.stderr or ""),
        message=msg,
    )


def execute_systemctl(args: list[str], *, timeout: float | None = None) -> ServiceActionResult:
    argv = ["systemctl"] + [str(x) for x in (args or [])]
    if not shutil.which("systemctl"):
        return ServiceActionResult(
            ok=False,
            argv=argv,
            returncode=127,
            stdout="",
            stderr="",
            message="systemctl is not available",
        )
    try:
        out = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ServiceActionResult(
            ok=False,
            argv=argv,
            returncode=124,
            stdout="",
            stderr="",
            message="systemctl command timed out",
        )
    except Exception as exc:
        return ServiceActionResult(
            ok=False,
            argv=argv,
            returncode=1,
            stdout="",
            stderr="",
            message=str(exc),
        )
    msg = (out.stderr or out.stdout or "").strip()
    if out.returncode != 0 and not msg:
        msg = f"systemctl command failed (exit {out.returncode})"
    return ServiceActionResult(
        ok=(out.returncode == 0),
        argv=argv,
        returncode=int(out.returncode),
        stdout=str(out.stdout or ""),
        stderr=str(out.stderr or ""),
        message=msg,
    )


def restart_service(
    *,
    systemd_unit: str,
    launchd_label: str,
    system: str | None = None,
) -> ServiceActionResult:
    commands, reason = self_restart_commands(
        systemd_unit=systemd_unit,
        launchd_label=launchd_label,
        system=system,
    )
    if reason:
        return ServiceActionResult(
            ok=False,
            argv=[],
            returncode=127,
            stdout="",
            stderr="",
            message=reason,
        )
    last = ServiceActionResult(False, [], 1, "", "", "restart failed")
    for argv in commands:
        try:
            out = subprocess.run(argv, capture_output=True, text=True, check=False)
        except Exception as exc:
            last = ServiceActionResult(False, list(argv), 1, "", "", str(exc))
            continue
        if out.returncode == 0:
            return ServiceActionResult(
                ok=True,
                argv=list(argv),
                returncode=0,
                stdout=str(out.stdout or ""),
                stderr=str(out.stderr or ""),
                message="",
            )
        msg = (out.stderr or out.stdout or "").strip() or f"restart failed (exit {out.returncode})"
        last = ServiceActionResult(
            ok=False,
            argv=list(argv),
            returncode=int(out.returncode),
            stdout=str(out.stdout or ""),
            stderr=str(out.stderr or ""),
            message=msg,
        )
    return last
