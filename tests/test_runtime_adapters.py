from __future__ import annotations

from fcc.runtime.adapters import process_adapter, service_adapter


def test_service_restart_commands_linux(monkeypatch):
    monkeypatch.setattr(service_adapter.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        service_adapter.shutil,
        "which",
        lambda name: "/bin/systemctl" if name == "systemctl" else None,
    )
    commands, reason = service_adapter.self_restart_commands(
        systemd_unit="storage-http-link-web",
        launchd_label="com.fcc.afterclaw",
    )
    assert reason == ""
    assert commands == [["systemctl", "restart", "storage-http-link-web"]]


def test_service_restart_commands_macos(monkeypatch):
    monkeypatch.setattr(service_adapter.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        service_adapter.shutil,
        "which",
        lambda name: "/bin/launchctl" if name == "launchctl" else None,
    )
    monkeypatch.setattr(service_adapter.os, "getuid", lambda: 501, raising=False)
    commands, reason = service_adapter.self_restart_commands(
        systemd_unit="storage-http-link-web",
        launchd_label="com.fcc.afterclaw",
    )
    assert reason == ""
    assert commands == [
        ["launchctl", "kickstart", "-k", "system/com.fcc.afterclaw"],
        ["launchctl", "kickstart", "-k", "gui/501/com.fcc.afterclaw"],
    ]


def test_execute_service_action_rejects_invalid_action():
    try:
        service_adapter.execute_service_action("reload", "storage-http-link-web")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_choose_process_tool_prefers_ss(monkeypatch):
    monkeypatch.setattr(
        process_adapter.shutil,
        "which",
        lambda name: "/usr/sbin/ss" if name == "ss" else None,
    )
    assert process_adapter.choose_process_tool() == "ss"


def test_execute_command_reports_missing_binary(monkeypatch):
    monkeypatch.setattr(process_adapter.shutil, "which", lambda _name: None)
    out = process_adapter.execute_command(["lsblk", "-J"])
    assert out.ok is False
    assert out.returncode == 127
