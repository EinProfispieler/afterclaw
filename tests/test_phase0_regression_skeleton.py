from __future__ import annotations

import pytest

from pathlib import Path

import app
from fcc.modules.monitor import process_net
from fcc.modules.monitor.process_net import ProcessSourceSpeedSampler


def test_process_net_detailed_snapshot_tracks_delta_bytes_regression():
    sampler = ProcessSourceSpeedSampler(source_rules=[("baidu", ("baidu",))])

    first = {
        "123|10.0.0.2:50000|1.1.1.1:443": {
            "source": "baidu",
            "pid": 123,
            "process": "baidu-netdisk",
            "state": "ESTAB",
            "local_ep": "10.0.0.2:50000",
            "peer_ep": "1.1.1.1:443",
            "acked": 1000,
            "received": 2000,
        }
    }
    second = {
        "123|10.0.0.2:50000|1.1.1.1:443": {
            "source": "baidu",
            "pid": 123,
            "process": "baidu-netdisk",
            "state": "ESTAB",
            "local_ep": "10.0.0.2:50000",
            "peer_ep": "1.1.1.1:443",
            "acked": 9000,
            "received": 18000,
        }
    }

    class TimeSeq:
        def __init__(self):
            self._vals = [1000.0, 1002.0]

        def __call__(self):
            return self._vals.pop(0)

    calls = {"n": 0}

    def fake_collect():
        calls["n"] += 1
        return first if calls["n"] == 1 else second

    sampler._collect_process_socket_counters = fake_collect  # type: ignore[assignment]
    sampler_time_orig = process_net.time.time
    try:
        process_net.time.time = TimeSeq()  # type: ignore[assignment]
        _ = sampler.detailed_snapshot()
        payload = sampler.detailed_snapshot()
    finally:
        process_net.time.time = sampler_time_orig  # type: ignore[assignment]

    assert payload["items"], "expected one connection row"
    row = payload["items"][0]
    assert row["delta_sent_bytes"] > 0
    assert row["delta_received_bytes"] > 0


def test_ui_vendor_missing_assets_trigger_fallback_regression():
    repo_root = Path(__file__).resolve().parent.parent
    required = [
        repo_root / "web/vendor/react/react.development.js",
        repo_root / "web/vendor/react/react-dom.development.js",
        repo_root / "web/vendor/babel/babel.min.js",
    ]
    for p in required:
        assert p.is_file(), f"missing required vendor asset: {p}"
    missing = app._ui_shell_missing_assets(repo_root)
    assert missing == []
    assert app._ui_shell_ready(repo_root) is True
