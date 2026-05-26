from __future__ import annotations

from fcc.modules.docker import service
from fcc.runtime.adapters.docker_adapter import DockerCommandResult


def test_docker_safe_name_validation():
    assert service.safe_name("qbittorrent") == "qbittorrent"
    assert service.safe_name("qbit_1") == "qbit_1"
    assert service.safe_name("") == ""
    assert service.safe_name("bad name") == ""
    assert service.safe_name("-invalid") == ""


def test_docker_create_container_executes_expected_command(monkeypatch):
    captured: list[list[str]] = []

    def _fake_execute(args, timeout=None):
        captured.append(list(args))
        return DockerCommandResult(
            ok=True,
            argv=["docker"] + list(args),
            returncode=0,
            stdout="container-id\n",
            stderr="",
            message="",
        )

    monkeypatch.setattr(service.docker_adapter, "execute_docker", _fake_execute)
    ok, msg = service.create_container(
        {
            "name": "qbt",
            "image": "lscr.io/linuxserver/qbittorrent:latest",
            "ports": ["8080:8080"],
            "volumes": ["/data:/data"],
            "env": ["TZ=UTC"],
            "restart": "unless-stopped",
            "network": "bridge",
        }
    )
    assert ok is True
    assert msg == "container-id"
    assert captured
    argv = captured[0]
    assert argv[:4] == ["run", "-d", "--name", "qbt"]
    assert "--restart" in argv
    assert "-p" in argv
    assert "-v" in argv
    assert "-e" in argv


def test_docker_status_payload_when_disabled():
    payload = service.status_payload(app_cfg={}, include_stats=True, module_enabled=False)
    assert payload["ok"] is True
    assert payload["available"] is False
    assert payload["disabled"] is True
    assert payload["summary"]["total"] == 0


def test_docker_status_payload_parses_ps_stats(monkeypatch):
    def _fake_execute(args, timeout=None):
        if args[:3] == ["ps", "-a", "--format"]:
            return DockerCommandResult(
                ok=True,
                argv=["docker"] + list(args),
                returncode=0,
                stdout='{"ID":"abc","Names":"qbt","Image":"img","State":"running","Status":"Up 2m","Ports":"8080/tcp","RunningFor":"2 minutes"}\n',
                stderr="",
                message="",
            )
        if args[:4] == ["stats", "--no-stream", "--format", "{{json .}}"]:
            return DockerCommandResult(
                ok=True,
                argv=["docker"] + list(args),
                returncode=0,
                stdout='{"Name":"qbt","CPUPerc":"1.2%","MemPerc":"3.4%","MemUsage":"1MiB / 10MiB","NetIO":"1kB / 2kB","BlockIO":"0B / 0B","PIDs":"4"}\n',
                stderr="",
                message="",
            )
        if args == ["images", "-q"]:
            return DockerCommandResult(
                ok=True,
                argv=["docker"] + list(args),
                returncode=0,
                stdout="sha256:1\nsha256:2\n",
                stderr="",
                message="",
            )
        return DockerCommandResult(
            ok=False,
            argv=["docker"] + list(args),
            returncode=1,
            stdout="",
            stderr="bad",
            message="bad",
        )

    monkeypatch.setattr(service.docker_adapter, "execute_docker", _fake_execute)
    payload = service.status_payload(app_cfg={"qbt": {"docker_container": "qbt"}})
    assert payload["ok"] is True
    assert payload["summary"]["running"] == 1
    assert payload["summary"]["images"] == 2
    assert payload["containers"][0]["name"] == "qbt"
    assert payload["containers"][0]["cpu_pct"] == 1.2
    assert "BitTorrent" in payload["containers"][0]["roles"]


def test_upgrade_container_with_rollback_success(monkeypatch):
    inspect_payload = (
        '[{"Config":{"Image":"old/app:1.0","Env":["TZ=UTC"],"Cmd":["--serve"]},'
        '"HostConfig":{"RestartPolicy":{"Name":"unless-stopped"},"NetworkMode":"bridge",'
        '"PortBindings":{"8080/tcp":[{"HostIp":"0.0.0.0","HostPort":"8080"}]}},'
        '"State":{"Running":true},"Mounts":[{"Source":"/data","Destination":"/app/data","RW":true}]}]\n'
    )
    calls: list[list[str]] = []

    def _fake_execute(args, timeout=None):
        calls.append(list(args))
        if args == ["inspect", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, inspect_payload, "", "")
        if args == ["pull", "inkos/app:latest"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "pulled", "", "")
        if args == ["stop", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args == ["rename", "inkos", "inkos-preupgrade-1234"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args and args[:4] == ["run", "-d", "--name", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "new-container-id\n", "", "")
        if args == ["rm", "-f", "inkos-preupgrade-1234"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        return DockerCommandResult(False, ["docker"] + list(args), 1, "", "bad", "bad")

    monkeypatch.setattr(service.docker_adapter, "execute_docker", _fake_execute)
    monkeypatch.setattr(service.time, "time", lambda: 1234)

    ok, detail = service.upgrade_container_with_rollback(
        name="inkos",
        image="inkos/app:latest",
        restart_after_pull=True,
    )
    assert ok is True
    assert detail["recreated"] is True
    assert detail["rollback_attempted"] is False
    assert detail["backup_id"] == "inkos-preupgrade-1234"
    assert ["rename", "inkos", "inkos-preupgrade-1234"] in calls


def test_upgrade_container_with_rollback_recreate_failure_rolls_back(monkeypatch):
    inspect_payload = (
        '[{"Config":{"Image":"old/app:1.0","Env":["TZ=UTC"],"Cmd":["--serve"]},'
        '"HostConfig":{"RestartPolicy":{"Name":"unless-stopped"},"NetworkMode":"bridge","PortBindings":{}},'
        '"State":{"Running":true},"Mounts":[]}]\n'
    )

    def _fake_execute(args, timeout=None):
        if args == ["inspect", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, inspect_payload, "", "")
        if args == ["pull", "inkos/app:latest"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "pulled", "", "")
        if args == ["stop", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args == ["rename", "inkos", "inkos-preupgrade-1234"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args and args[:4] == ["run", "-d", "--name", "inkos"]:
            return DockerCommandResult(False, ["docker"] + list(args), 1, "", "create fail", "create fail")
        if args == ["rm", "-f", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args == ["rename", "inkos-preupgrade-1234", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args == ["start", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        return DockerCommandResult(False, ["docker"] + list(args), 1, "", "bad", "bad")

    monkeypatch.setattr(service.docker_adapter, "execute_docker", _fake_execute)
    monkeypatch.setattr(service.time, "time", lambda: 1234)

    ok, detail = service.upgrade_container_with_rollback(
        name="inkos",
        image="inkos/app:latest",
        restart_after_pull=True,
    )
    assert ok is False
    assert detail["rollback_attempted"] is True
    assert detail["rollback_ok"] is True
    assert "docker recreate failed" in detail["error"]


def test_upgrade_container_with_rollback_allows_offline_local_when_pull_fails(monkeypatch):
    inspect_payload = (
        '[{"Config":{"Image":"old/app:1.0","Env":["TZ=UTC"],"Cmd":["--serve"]},'
        '"HostConfig":{"RestartPolicy":{"Name":"unless-stopped"},"NetworkMode":"bridge","PortBindings":{}},'
        '"State":{"Running":true},"Mounts":[]}]\n'
    )
    calls: list[list[str]] = []

    def _fake_execute(args, timeout=None):
        calls.append(list(args))
        if args == ["inspect", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, inspect_payload, "", "")
        if args == ["pull", "inkos/app:latest"]:
            return DockerCommandResult(False, ["docker"] + list(args), 1, "", "pull timeout", "pull timeout")
        if args == ["image", "inspect", "inkos/app:latest"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "[]\n", "", "")
        if args == ["stop", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args == ["rename", "inkos", "inkos-preupgrade-1234"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args and args[:4] == ["run", "-d", "--name", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "new-container-id\n", "", "")
        if args == ["rm", "-f", "inkos-preupgrade-1234"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        return DockerCommandResult(False, ["docker"] + list(args), 1, "", "bad", "bad")

    monkeypatch.setattr(service.docker_adapter, "execute_docker", _fake_execute)
    monkeypatch.setattr(service.time, "time", lambda: 1234)

    ok, detail = service.upgrade_container_with_rollback(
        name="inkos",
        image="inkos/app:latest",
        restart_after_pull=True,
        allow_offline_local=True,
    )
    assert ok is True
    assert detail["recreated"] is True
    assert detail["pulled"] is False
    assert detail["pull_skipped"] is True
    assert ["image", "inspect", "inkos/app:latest"] in calls


def test_upgrade_container_with_rollback_respects_recreate_delay(monkeypatch):
    inspect_payload = (
        '[{"Config":{"Image":"old/app:1.0","Env":["TZ=UTC"],"Cmd":["--serve"]},'
        '"HostConfig":{"RestartPolicy":{"Name":"unless-stopped"},"NetworkMode":"bridge","PortBindings":{}},'
        '"State":{"Running":true},"Mounts":[]}]\n'
    )
    sleeps: list[float] = []

    def _fake_execute(args, timeout=None):
        if args == ["inspect", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, inspect_payload, "", "")
        if args == ["pull", "inkos/app:latest"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "pulled", "", "")
        if args == ["stop", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args == ["rename", "inkos", "inkos-preupgrade-1234"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        if args and args[:4] == ["run", "-d", "--name", "inkos"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "new-container-id\n", "", "")
        if args == ["rm", "-f", "inkos-preupgrade-1234"]:
            return DockerCommandResult(True, ["docker"] + list(args), 0, "", "", "")
        return DockerCommandResult(False, ["docker"] + list(args), 1, "", "bad", "bad")

    monkeypatch.setattr(service.docker_adapter, "execute_docker", _fake_execute)
    monkeypatch.setattr(service.time, "time", lambda: 1234)
    monkeypatch.setattr(service, "_UPGRADE_RECREATE_DELAY_SEC", 0.05)
    monkeypatch.setattr(service.time, "sleep", lambda s: sleeps.append(float(s)))

    ok, detail = service.upgrade_container_with_rollback(
        name="inkos",
        image="inkos/app:latest",
        restart_after_pull=True,
    )
    assert ok is True
    assert detail["recreated"] is True
    assert sleeps == [0.05]


def test_docker_operation_history_list_export_clear(monkeypatch, tmp_path):
    path = tmp_path / "docker_ops_history.jsonl"
    monkeypatch.setenv("DOCKER_OPS_HISTORY_FILE", str(path))
    monkeypatch.setattr(service, "_DOCKER_OPS_LOADED", False)
    service._DOCKER_OPS_HISTORY.clear()
    service.clear_operation_history()
    service.record_operation("restart", ok=True, name="qbt", source="/api/docker/action", client_ip="127.0.0.1")
    service.record_operation("upgrade", ok=False, name="inkos", source="/api/docker/basic-op", message="boom")

    hist = service.list_operation_history(limit=10)
    assert hist["count"] >= 2
    assert hist["items"][0]["action"] in {"upgrade", "restart"}

    only_fail = service.list_operation_history(limit=10, ok=False)
    assert only_fail["count"] >= 1
    assert all(bool(x.get("ok")) is False for x in only_fail["items"])

    exported = service.export_operation_history(fmt="json", limit=10)
    assert exported["ok"] is True
    assert exported["format"] == "json"
    assert exported["filename"].endswith(".json")
    assert exported["line_count"] >= 2
    assert exported["content"].strip().startswith("[")

    cleared = service.clear_operation_history()
    assert cleared["ok"] is True
    assert cleared["removed"] >= 2


def test_docker_operation_history_survives_runtime_reload(monkeypatch, tmp_path):
    path = tmp_path / "docker_ops_history.jsonl"
    monkeypatch.setenv("DOCKER_OPS_HISTORY_FILE", str(path))
    monkeypatch.setattr(service, "_DOCKER_OPS_LOADED", False)
    service._DOCKER_OPS_HISTORY.clear()

    service.record_operation("upgrade", ok=True, name="inkos", source="/api/docker/basic-op")
    assert path.is_file()

    service._DOCKER_OPS_HISTORY.clear()
    monkeypatch.setattr(service, "_DOCKER_OPS_LOADED", False)
    reloaded = service.list_operation_history(limit=10)
    assert reloaded["count"] == 1
    assert reloaded["items"][0]["action"] == "upgrade"
    assert reloaded["items"][0]["name"] == "inkos"
