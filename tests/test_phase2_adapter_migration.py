from __future__ import annotations

from pathlib import Path


def _app_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "app.py").read_text(encoding="utf-8")


def test_app_py_no_direct_service_or_docker_subprocess_runs():
    src = _app_source()
    forbidden = [
        'subprocess.run(["systemctl"',
        'subprocess.run(["docker"',
        'subprocess.run(["launchctl"',
    ]
    for token in forbidden:
        assert token not in src, f"direct call should be moved to adapter: {token}"


def test_app_py_no_direct_subprocess_run_calls():
    src = _app_source()
    assert "subprocess.run(" not in src
