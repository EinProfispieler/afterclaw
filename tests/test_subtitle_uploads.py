import base64
import gzip
import io
import os
import stat
import zipfile
from pathlib import Path

from fcc.subtitle_uploads import handle_upload_payload


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_direct_subtitle_upload(tmp_path: Path):
    root = tmp_path / "storage"
    target = root / "show"
    target.mkdir(parents=True)
    out = handle_upload_payload(
        root,
        "show",
        {"files": [{"name": "Show.S01E02.ass", "content_b64": b64(b"dialogue")}]},
    )
    assert out["success_count"] == 1
    assert (target / "Show.S01E02.ass").read_bytes() == b"dialogue"


def test_zip_archive_requires_and_extracts_subtitles(tmp_path: Path):
    root = tmp_path / "storage"
    target = root / "show"
    target.mkdir(parents=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Episode.S01E02.srt", "subtitle")
        zf.writestr("notes.txt", "ignored")
    out = handle_upload_payload(
        root,
        "show",
        {"files": [{"name": "subs.zip", "content_b64": b64(buf.getvalue())}]},
    )
    assert out["success_count"] == 1
    assert out["results"][0]["archive_deleted"] is True
    assert (target / "Episode.S01E02.srt").read_text() == "subtitle"
    assert not (target / "subs.zip").exists()
    assert not (target / "notes.txt").exists()


def test_zip_archive_nested_paths_are_flattened_into_current_dir(tmp_path: Path):
    root = tmp_path / "storage"
    target = root / "show"
    target.mkdir(parents=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Season 5/Futurama.S05E10.ass", "subtitle")
    out = handle_upload_payload(
        root,
        "show",
        {"files": [{"name": "nested.zip", "content_b64": b64(buf.getvalue())}]},
    )
    assert out["success_count"] == 1
    assert (target / "Futurama.S05E10.ass").exists()
    assert not (target / "Season 5").exists()


def test_archive_without_subtitles_is_rejected(tmp_path: Path):
    root = tmp_path / "storage"
    target = root / "show"
    target.mkdir(parents=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("notes.txt", "not subtitle")
    out = handle_upload_payload(
        root,
        "show",
        {"files": [{"name": "bad.zip", "content_b64": b64(buf.getvalue())}]},
    )
    assert out["success_count"] == 0
    assert out["failed_count"] == 1
    assert not any(target.iterdir())


def test_gzip_single_subtitle(tmp_path: Path):
    root = tmp_path / "storage"
    target = root / "show"
    target.mkdir(parents=True)
    data = gzip.compress(b"subtitle")
    out = handle_upload_payload(
        root,
        "show",
        {"files": [{"name": "Episode.S01E02.srt.gz", "content_b64": b64(data)}]},
    )
    assert out["success_count"] == 1
    assert (target / "Episode.S01E02.srt").read_bytes() == b"subtitle"


def test_uploaded_file_inherits_parent_write_mode(tmp_path: Path):
    root = tmp_path / "storage"
    target = root / "show"
    target.mkdir(parents=True)
    os.chmod(target, 0o775)
    out = handle_upload_payload(
        root,
        "show",
        {"files": [{"name": "Show.S01E03.srt", "content_b64": b64(b"ok")}]},
    )
    assert out["success_count"] == 1
    mode = stat.S_IMODE((target / "Show.S01E03.srt").stat().st_mode)
    assert mode == 0o664


def test_upload_applies_custom_permission_policy(tmp_path: Path):
    root = tmp_path / "storage"
    target = root / "show"
    target.mkdir(parents=True)
    out = handle_upload_payload(
        root,
        "show",
        {"files": [{"name": "Show.S01E04.srt", "content_b64": b64(b"ok")}]},
        {"owner_uid": os.getuid(), "owner_gid": os.getgid(), "file_mode": "660", "dir_mode": "2775"},
    )
    assert out["success_count"] == 1
    f = target / "Show.S01E04.srt"
    d_mode = stat.S_IMODE(target.stat().st_mode)
    f_mode = stat.S_IMODE(f.stat().st_mode)
    # Some Linux filesystems preserve setgid on directory chmod(0o2775).
    # Accept both plain rwx bits and setgid-preserved mode.
    assert d_mode in (0o775, 0o2775)
    assert f_mode == 0o660
