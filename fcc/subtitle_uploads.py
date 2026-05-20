"""Subtitle upload and archive extraction helpers for AfterClaw."""

from __future__ import annotations

import base64
import gzip
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from fcc.security import ensure_under_root

SUBTITLE_EXTENSIONS = {
    ".srt",
    ".ass",
    ".ssa",
    ".vtt",
    ".sub",
    ".idx",
}
ARCHIVE_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".gz",
    ".tgz",
    ".tar",
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tbz2",
    ".txz",
}
MAX_UPLOAD_FILE_BYTES = int(os.environ.get("SUBTITLE_UPLOAD_MAX_BYTES", str(512 * 1024 * 1024)))
DEFAULT_SUBTITLE_OWNER_UID = int(os.environ.get("SUBTITLE_OWNER_UID", "501"))
DEFAULT_SUBTITLE_OWNER_GID = int(os.environ.get("SUBTITLE_OWNER_GID", "20"))
DEFAULT_SUBTITLE_FILE_MODE = int(os.environ.get("SUBTITLE_FILE_MODE", "664"), 8)
DEFAULT_SUBTITLE_DIR_MODE = int(os.environ.get("SUBTITLE_DIR_MODE", "2775"), 8)


def is_subtitle_name(name: str) -> bool:
    return Path(str(name or "")).suffix.lower() in SUBTITLE_EXTENSIONS


def archive_extension(name: str) -> str:
    lower = str(name or "").strip().lower()
    for ext in sorted(ARCHIVE_EXTENSIONS, key=len, reverse=True):
        if lower.endswith(ext):
            return ext
    return ""


def _safe_name(name: str) -> str:
    raw = str(name or "").replace("\\", "/").split("/")[-1].strip()
    if not raw or raw in {".", ".."}:
        raise ValueError("Invalid file name")
    if "\x00" in raw:
        raise ValueError("Invalid file name")
    return raw


def _decode_b64(content_b64: str) -> bytes:
    try:
        return base64.b64decode(str(content_b64 or ""), validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 content") from exc


def _unique_dest(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for i in range(1, 10000):
        candidate = parent / f"{stem}.{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise ValueError(f"Cannot find available file name for {path.name}")


def _safe_member_rel(name: str) -> Path | None:
    text = str(name or "").replace("\\", "/").lstrip("/")
    if not text or text.endswith("/"):
        return None
    rel = Path(text)
    if any(part in {"", ".", ".."} for part in rel.parts):
        return None
    return rel


def _copy_subtitle_file(src: Path, dest_root: Path, rel: Path, perm: dict[str, int]) -> dict[str, Any]:
    # Flatten archive paths into the selected directory. Users expect uploaded
    # subtitle results to appear in the current folder, not hidden subfolders
    # recreated from archive internals.
    dest = ensure_under_root(dest_root, dest_root / rel.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ensure_dir_permissions(dest.parent, perm)
    dest = _unique_dest(dest)
    shutil.copy2(src, dest)
    _apply_file_permissions(dest, perm)
    return {
        "ok": True,
        "kind": "subtitle",
        "file": dest.relative_to(dest_root).as_posix(),
        "size": int(dest.stat().st_size),
    }


def _save_direct_subtitle(name: str, data: bytes, dest_root: Path, perm: dict[str, int]) -> dict[str, Any]:
    safe = _safe_name(name)
    if not is_subtitle_name(safe):
        raise ValueError("Only subtitle files or supported archives are allowed")
    target = _unique_dest(ensure_under_root(dest_root, dest_root / safe))
    target.parent.mkdir(parents=True, exist_ok=True)
    _ensure_dir_permissions(target.parent, perm)
    target.write_bytes(data)
    _apply_file_permissions(target, perm)
    return {
        "ok": True,
        "kind": "subtitle",
        "file": target.relative_to(dest_root).as_posix(),
        "size": len(data),
    }


def _resolve_permissions(permission_policy: dict[str, Any] | None = None) -> dict[str, int]:
    policy = permission_policy if isinstance(permission_policy, dict) else {}
    uid = int(policy.get("owner_uid", DEFAULT_SUBTITLE_OWNER_UID))
    gid = int(policy.get("owner_gid", DEFAULT_SUBTITLE_OWNER_GID))
    file_mode = int(str(policy.get("file_mode", oct(DEFAULT_SUBTITLE_FILE_MODE))), 8)
    dir_mode = int(str(policy.get("dir_mode", oct(DEFAULT_SUBTITLE_DIR_MODE))), 8)
    return {
        "owner_uid": uid,
        "owner_gid": gid,
        "file_mode": file_mode & 0o7777,
        "dir_mode": dir_mode & 0o7777,
    }


def _ensure_dir_permissions(path: Path, perm: dict[str, int]) -> None:
    try:
        os.chown(path, int(perm["owner_uid"]), int(perm["owner_gid"]))
    except Exception:
        pass
    try:
        os.chmod(path, int(perm["dir_mode"]))
    except Exception:
        pass


def _apply_file_permissions(path: Path, perm: dict[str, int]) -> None:
    try:
        os.chown(path, int(perm["owner_uid"]), int(perm["owner_gid"]))
    except Exception:
        pass
    try:
        os.chmod(path, int(perm["file_mode"]))
    except Exception:
        pass


def _extract_zip(archive: Path, dest_root: Path, perm: dict[str, int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as zf:
        subtitle_names = [n for n in zf.namelist() if is_subtitle_name(n)]
        if not subtitle_names:
            raise ValueError("Archive does not contain subtitle files")
        with tempfile.TemporaryDirectory(prefix="afterclaw-subzip-") as td:
            tmp = Path(td)
            for name in subtitle_names:
                rel = _safe_member_rel(name)
                if rel is None:
                    continue
                src = ensure_under_root(tmp, tmp / rel)
                src.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as rf, src.open("wb") as wf:
                    shutil.copyfileobj(rf, wf)
                rows.append(_copy_subtitle_file(src, dest_root, rel, perm))
    return rows


def _extract_tar(archive: Path, dest_root: Path, perm: dict[str, int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with tarfile.open(archive) as tf:
        members = [m for m in tf.getmembers() if m.isfile() and is_subtitle_name(m.name)]
        if not members:
            raise ValueError("Archive does not contain subtitle files")
        with tempfile.TemporaryDirectory(prefix="afterclaw-subtar-") as td:
            tmp = Path(td)
            for member in members:
                rel = _safe_member_rel(member.name)
                if rel is None:
                    continue
                src_f = tf.extractfile(member)
                if src_f is None:
                    continue
                src = ensure_under_root(tmp, tmp / rel)
                src.parent.mkdir(parents=True, exist_ok=True)
                with src.open("wb") as wf:
                    shutil.copyfileobj(src_f, wf)
                rows.append(_copy_subtitle_file(src, dest_root, rel, perm))
    return rows


def _extract_gzip_single(archive: Path, original_name: str, dest_root: Path, perm: dict[str, int]) -> list[dict[str, Any]]:
    safe = _safe_name(original_name)
    lower = safe.lower()
    out_name = safe[:-3] if lower.endswith(".gz") else safe + ".out"
    if not is_subtitle_name(out_name):
        raise ValueError("Gzip file name must expand to a subtitle file")
    with tempfile.TemporaryDirectory(prefix="afterclaw-subgz-") as td:
        src = Path(td) / out_name
        with gzip.open(archive, "rb") as rf, src.open("wb") as wf:
            shutil.copyfileobj(rf, wf)
        return [_copy_subtitle_file(src, dest_root, Path(out_name), perm)]


def _external_extractor(ext: str) -> list[str] | None:
    if ext == ".rar":
        if shutil.which("unar"):
            return ["unar", "-quiet"]
        if shutil.which("unrar"):
            return ["unrar", "x", "-idq"]
        if shutil.which("7z"):
            return ["7z", "x", "-y"]
        if shutil.which("7zz"):
            return ["7zz", "x", "-y"]
        return None
    if ext == ".7z":
        if shutil.which("7z"):
            return ["7z", "x", "-y"]
        if shutil.which("7zz"):
            return ["7zz", "x", "-y"]
        return None
    return None


def _extract_external(archive: Path, ext: str, dest_root: Path, perm: dict[str, int]) -> list[dict[str, Any]]:
    cmd = _external_extractor(ext)
    if not cmd:
        raise ValueError(f"Cannot extract {ext}: install 7z, 7zz, unar, or unrar")
    with tempfile.TemporaryDirectory(prefix="afterclaw-subext-") as td:
        tmp = Path(td)
        if cmd[0] == "unar":
            run = [*cmd, "-o", str(tmp), str(archive)]
        elif cmd[0] == "unrar":
            run = [*cmd, str(archive), str(tmp)]
        else:
            run = [*cmd, f"-o{tmp}", str(archive)]
        proc = subprocess.run(run, capture_output=True, text=True, timeout=180, check=False)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[-600:]
            raise ValueError(detail or f"Archive extraction failed with exit {proc.returncode}")
        subtitles = [p for p in tmp.rglob("*") if p.is_file() and is_subtitle_name(p.name)]
        if not subtitles:
            raise ValueError("Archive does not contain subtitle files")
        rows = []
        for src in sorted(subtitles):
            rel = src.relative_to(tmp)
            if _safe_member_rel(rel.as_posix()) is None:
                continue
            rows.append(_copy_subtitle_file(src, dest_root, rel, perm))
        return rows


def _extract_archive(name: str, archive: Path, dest_root: Path, perm: dict[str, int]) -> list[dict[str, Any]]:
    ext = archive_extension(name)
    if not ext:
        raise ValueError("Unsupported archive type")
    if ext == ".zip":
        return _extract_zip(archive, dest_root, perm)
    if ext in {".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz"}:
        return _extract_tar(archive, dest_root, perm)
    if ext == ".gz":
        return _extract_gzip_single(archive, name, dest_root, perm)
    if ext in {".rar", ".7z"}:
        return _extract_external(archive, ext, dest_root, perm)
    raise ValueError("Unsupported archive type")


def handle_upload_payload(
    storage_root: Path,
    rel_dir: str,
    payload: dict[str, Any],
    permission_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(storage_root).resolve()
    target_dir = ensure_under_root(root, root / (rel_dir or "."))
    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError("Directory does not exist")
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list) or not files:
        raise ValueError("files must be a non-empty array")
    perm = _resolve_permissions(permission_policy)
    _ensure_dir_permissions(target_dir, perm)
    rows: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict):
            rows.append({"ok": False, "file": "", "message": "Invalid file item"})
            continue
        original_name = str(item.get("name", "") or "")
        try:
            safe_name = _safe_name(original_name)
            data = _decode_b64(str(item.get("content_b64", "") or ""))
            if len(data) > MAX_UPLOAD_FILE_BYTES:
                raise ValueError("File exceeds upload size limit")
            if is_subtitle_name(safe_name):
                rows.append(_save_direct_subtitle(safe_name, data, target_dir, perm))
                continue
            if not archive_extension(safe_name):
                raise ValueError("Only subtitle files or supported archives are allowed")
            with tempfile.TemporaryDirectory(prefix="afterclaw-subupload-") as td:
                archive = Path(td) / safe_name
                archive.write_bytes(data)
                extracted = _extract_archive(safe_name, archive, target_dir, perm)
                rows.append(
                    {
                        "ok": True,
                        "kind": "archive",
                        "file": safe_name,
                        "extracted_count": len(extracted),
                        "extracted": extracted,
                        "archive_deleted": True,
                    }
                )
        except Exception as exc:
            rows.append({"ok": False, "file": original_name, "message": str(exc)})
    return {
        "ok": any(bool(r.get("ok")) for r in rows),
        "results": rows,
        "success_count": sum(1 for r in rows if r.get("ok")),
        "failed_count": sum(1 for r in rows if not r.get("ok")),
    }
