from __future__ import annotations

from dataclasses import dataclass
import shutil
import subprocess


@dataclass(frozen=True)
class DockerCommandResult:
    ok: bool
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    message: str


def docker_available() -> bool:
    return bool(shutil.which("docker"))


def execute_docker(args: list[str], *, timeout: float | None = None) -> DockerCommandResult:
    argv = ["docker"] + [str(x) for x in (args or [])]
    if not docker_available():
        return DockerCommandResult(
            ok=False,
            argv=argv,
            returncode=127,
            stdout="",
            stderr="",
            message="docker is not available",
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
        return DockerCommandResult(
            ok=False,
            argv=argv,
            returncode=124,
            stdout="",
            stderr="",
            message="docker command timed out",
        )
    except Exception as exc:
        return DockerCommandResult(
            ok=False,
            argv=argv,
            returncode=1,
            stdout="",
            stderr="",
            message=str(exc),
        )
    msg = (out.stderr or "").strip()
    if out.returncode != 0 and not msg:
        msg = f"docker command failed (exit {out.returncode})"
    return DockerCommandResult(
        ok=(out.returncode == 0),
        argv=argv,
        returncode=int(out.returncode),
        stdout=str(out.stdout or ""),
        stderr=str(out.stderr or ""),
        message=msg,
    )
