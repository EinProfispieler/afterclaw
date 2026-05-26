from __future__ import annotations

import app


def test_self_restart_command_candidates_linux_systemctl(monkeypatch):
    monkeypatch.setattr(app.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        app.shutil, "which", lambda name: "/bin/systemctl" if name == "systemctl" else None
    )
    monkeypatch.setattr(app, "SELF_SYSTEMD_SERVICE_UNIT", "storage-http-link-web")
    commands, reason = app.AppHandler._self_restart_command_candidates()
    assert reason == ""
    assert commands == [["systemctl", "restart", "storage-http-link-web"]]


def test_self_restart_command_candidates_macos_launchctl(monkeypatch):
    monkeypatch.setattr(app.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        app.shutil, "which", lambda name: "/bin/launchctl" if name == "launchctl" else None
    )
    monkeypatch.setattr(app.os, "getuid", lambda: 501)
    monkeypatch.setattr(app, "SELF_LAUNCHD_SERVICE_LABEL", "com.fcc.afterclaw")
    commands, reason = app.AppHandler._self_restart_command_candidates()
    assert reason == ""
    assert commands == [
        ["launchctl", "kickstart", "-k", "system/com.fcc.afterclaw"],
        ["launchctl", "kickstart", "-k", "gui/501/com.fcc.afterclaw"],
    ]


def test_self_restart_command_candidates_unsupported_platform(monkeypatch):
    monkeypatch.setattr(app.platform, "system", lambda: "Windows")
    commands, reason = app.AppHandler._self_restart_command_candidates()
    assert commands == []
    assert "暂不支持自动重启" in reason


def test_schedule_restart_returns_reason_when_unsupported(monkeypatch):
    monkeypatch.setattr(
        app.AppHandler,
        "_self_restart_command_candidates",
        classmethod(lambda cls: ([], "unsupported restart backend")),
    )
    queued, reason = app.AppHandler._schedule_restart()
    assert queued is False
    assert reason == "unsupported restart backend"


def test_upgrade_supported_depends_on_restart_backend(monkeypatch):
    monkeypatch.setattr(app.os, "name", "posix", raising=False)
    monkeypatch.setattr(
        app.AppHandler,
        "_self_restart_command_candidates",
        classmethod(lambda cls: ([], "missing launchctl/systemctl")),
    )
    ok, reason = app.AppHandler._upgrade_supported()
    assert ok is False
    assert "missing launchctl/systemctl" in reason
