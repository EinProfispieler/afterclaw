from __future__ import annotations

import pytest

import app


def test_normalize_upgrade_script_source_supports_github_and_https():
    assert (
        app._normalize_upgrade_script_source(" github:afterclaw-org/afterclaw/upgrade-scripts ")
        == "github:afterclaw-org/afterclaw/upgrade-scripts"
    )
    assert (
        app._normalize_upgrade_script_source("https://updates.example.com/afterclaw")
        == "https://updates.example.com/afterclaw"
    )


def test_normalize_upgrade_script_source_rejects_invalid_values():
    with pytest.raises(ValueError):
        app._normalize_upgrade_script_source("github:afterclaw-org/afterclaw")
    with pytest.raises(ValueError):
        app._normalize_upgrade_script_source("ftp://updates.example.com/hooks")


def test_upgrade_script_candidate_urls_github_dir_order():
    urls = app._upgrade_script_candidate_urls(
        "github:afterclaw-org/afterclaw/upgrade-scripts",
        "nightly",
        "v1.2.3",
    )
    assert urls == [
        "https://raw.githubusercontent.com/afterclaw-org/afterclaw/nightly/upgrade-scripts/v1.2.3.sh",
        "https://raw.githubusercontent.com/afterclaw-org/afterclaw/nightly/upgrade-scripts/nightly.sh",
        "https://raw.githubusercontent.com/afterclaw-org/afterclaw/nightly/upgrade-scripts/latest.sh",
        "https://raw.githubusercontent.com/afterclaw-org/afterclaw/nightly/upgrade-scripts/upgrade.sh",
    ]


def test_upgrade_script_candidate_urls_http_dir_order():
    urls = app._upgrade_script_candidate_urls(
        "https://updates.example.com/afterclaw/hooks",
        "main",
        "v2.0.0",
    )
    assert urls == [
        "https://updates.example.com/afterclaw/hooks/v2.0.0.sh",
        "https://updates.example.com/afterclaw/hooks/main.sh",
        "https://updates.example.com/afterclaw/hooks/latest.sh",
        "https://updates.example.com/afterclaw/hooks/upgrade.sh",
    ]


def test_fetch_upgrade_script_payload_falls_back_to_next_candidate(monkeypatch):
    def fake_fetch(url, timeout=0, headers=None):  # noqa: ARG001
        if url.endswith("/main.sh"):
            raise RuntimeError("404")
        if url.endswith("/latest.sh"):
            return "#!/usr/bin/env bash\necho ok\n"
        raise RuntimeError("unexpected url")

    monkeypatch.setattr(app, "_http_fetch_text", fake_fetch)
    payload = app._fetch_upgrade_script_payload(
        "https://updates.example.com/afterclaw/hooks",
        "main",
        "",
    )
    assert payload == {
        "url": "https://updates.example.com/afterclaw/hooks/latest.sh",
        "script": "#!/usr/bin/env bash\necho ok\n",
    }
