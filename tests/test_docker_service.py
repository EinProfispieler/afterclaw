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
