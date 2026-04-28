"""Platform detection for installers/runtime behavior."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform as py_platform


@dataclass(frozen=True)
class PlatformInfo:
    os_name: str
    distro_id: str
    distro_like: str
    init_system: str
    package_manager: str


def _linux_release() -> tuple[str, str]:
    os_release = Path("/etc/os-release")
    distro_id = ""
    distro_like = ""
    if not os_release.exists():
        return distro_id, distro_like
    try:
        lines = os_release.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return distro_id, distro_like
    kv = {}
    for line in lines:
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip().strip('"')
    distro_id = kv.get("ID", "")
    distro_like = kv.get("ID_LIKE", "")
    return distro_id, distro_like


def detect_platform() -> PlatformInfo:
    system = py_platform.system().lower()

    if system == "linux":
        distro_id, distro_like = _linux_release()
        init_system = "systemd" if Path("/run/systemd/system").exists() else "unknown"
        package_manager = "apt" if Path("/usr/bin/apt").exists() else "unknown"
        return PlatformInfo(
            os_name="linux",
            distro_id=distro_id,
            distro_like=distro_like,
            init_system=init_system,
            package_manager=package_manager,
        )

    if system == "darwin":
        return PlatformInfo(
            os_name="darwin",
            distro_id="macos",
            distro_like="darwin",
            init_system="launchd",
            package_manager="brew" if Path("/opt/homebrew/bin/brew").exists() or Path("/usr/local/bin/brew").exists() else "unknown",
        )

    return PlatformInfo(
        os_name=system or "unknown",
        distro_id="",
        distro_like="",
        init_system="unknown",
        package_manager="unknown",
    )
