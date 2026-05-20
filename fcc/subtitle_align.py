"""Subtitle-to-video filename alignment helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".m4v",
    ".ts",
    ".m2ts",
    ".webm",
}
SUBTITLE_EXTENSIONS = {
    ".srt",
    ".ass",
    ".ssa",
    ".vtt",
    ".sup",
    ".sub",
    ".idx",
}
TOKEN_RE = re.compile(r"(?i)(?:s(\d{1,2})e(\d{1,2})|(\d{1,2})x(\d{1,2}))")
LANG_TOKEN_RE = re.compile(r"(?i)^(zh|zho|cn|chs|cht|sc|tc|eng|en|ja|jp|jpn|ko|kr|kor|fr|de|es|it|pt|ru|ar|hi|vi|th)$")


@dataclass
class AlignItem:
    old_rel: str
    new_rel: str
    kind: str
    skip: bool
    error: str | None = None


def _token(stem: str) -> str:
    m = TOKEN_RE.search(stem or "")
    if not m:
        return ""
    season = m.group(1) or m.group(3)
    episode = m.group(2) or m.group(4)
    if season is None or episode is None:
        return ""
    return f"S{int(season):02d}E{int(episode):02d}"


def _suffix_after_token(stem: str) -> str:
    m = TOKEN_RE.search(stem or "")
    if not m:
        return ""
    tail = stem[m.end():].strip()
    if not tail:
        return ""
    # Keep language/style tail when aligning by SxxExx
    return tail if tail.startswith((".", "-", "_", " ")) else ("." + tail)


def _compact_subtitle_suffix(suffix: str) -> str:
    raw = str(suffix or "").strip()
    if not raw:
        return ""
    text = raw.lstrip("._- ").strip()
    if not text:
        return ""
    # Avoid filename bloat and repeated title segments; only keep compact language-ish tails.
    if len(text) > 24:
        return ""
    parts = [p for p in re.split(r"[._\-\s]+", text) if p]
    if not parts:
        return ""
    if len(parts) > 3:
        return ""
    if not all(LANG_TOKEN_RE.match(p) for p in parts):
        return ""
    return "." + ".".join(parts)


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _is_subtitle(path: Path) -> bool:
    return path.suffix.lower() in SUBTITLE_EXTENSIONS


def _build_video_indexes(files: list[Path]) -> tuple[dict[str, Path], dict[str, list[Path]]]:
    by_stem: dict[str, Path] = {}
    by_token: dict[str, list[Path]] = {}
    for f in files:
        stem_key = f.stem.lower()
        if stem_key not in by_stem:
            by_stem[stem_key] = f
        t = _token(f.stem)
        if t:
            by_token.setdefault(t, []).append(f)
    return by_stem, by_token


def build_alignment_plan(storage: Path, rel_dir: str, *, recursive: bool) -> list[AlignItem]:
    rel_dir = (rel_dir or ".").replace("\\", "/").strip() or "."
    storage = storage.resolve()
    base = (storage / rel_dir).resolve()
    if not base.is_dir():
        raise FileNotFoundError("Directory does not exist")
    try:
        base.relative_to(storage)
    except ValueError as exc:
        raise ValueError("Path is outside allowed root") from exc

    items: list[AlignItem] = []

    if recursive:
        walk_dirs = [Path(dp).resolve() for dp, _d, _f in os.walk(str(base))]
    else:
        walk_dirs = [base]

    for work_dir in walk_dirs:
        if not work_dir.exists() or not work_dir.is_dir():
            continue
        files = []
        try:
            files = [x.resolve() for x in work_dir.iterdir() if x.is_file()]
        except Exception:
            continue
        videos = [x for x in files if _is_video(x)]
        subs = [x for x in files if _is_subtitle(x)]
        if not videos or not subs:
            continue

        by_stem, by_token = _build_video_indexes(videos)

        for sub in subs:
            old_name = sub.name
            old_rel = sub.relative_to(storage).as_posix()

            target_video = by_stem.get(sub.stem.lower())
            reason = ""
            suffix = ""

            if target_video is None:
                tk = _token(sub.stem)
                candidates = by_token.get(tk, []) if tk else []
                if len(candidates) == 1:
                    target_video = candidates[0]
                    reason = "token"
                    suffix = _suffix_after_token(sub.stem)
                elif len(candidates) > 1:
                    items.append(
                        AlignItem(
                            old_rel=old_rel,
                            new_rel=old_rel,
                            kind="subtitle",
                            skip=True,
                            error=f"Multiple videos match {tk}",
                        )
                    )
                    continue
                else:
                    items.append(
                        AlignItem(
                            old_rel=old_rel,
                            new_rel=old_rel,
                            kind="subtitle",
                            skip=True,
                            error="No matching video found",
                        )
                    )
                    continue

            new_stem = target_video.stem
            if reason == "token" and suffix:
                keep = _compact_subtitle_suffix(suffix)
                if keep:
                    new_stem = (new_stem + keep).strip()
            new_name = new_stem + sub.suffix.lower()

            if old_name.lower() == new_name.lower():
                continue

            dest = (work_dir / new_name).resolve()
            try:
                dest.relative_to(storage)
            except ValueError:
                items.append(
                    AlignItem(
                        old_rel=old_rel,
                        new_rel=old_rel,
                        kind="subtitle",
                        skip=True,
                        error="Target path escapes root",
                    )
                )
                continue

            new_rel = dest.relative_to(storage).as_posix()
            skip = dest.exists() and dest != sub
            items.append(
                AlignItem(
                    old_rel=old_rel,
                    new_rel=new_rel,
                    kind="subtitle",
                    skip=skip,
                    error=("Target already exists" if skip else None),
                )
            )

    return items


def simplify_plan(items: list[AlignItem]) -> list[dict[str, Any]]:
    return [
        {
            "old_rel": x.old_rel,
            "new_rel": x.new_rel,
            "kind": x.kind,
            "skip": x.skip,
            "error": x.error,
        }
        for x in items
    ]
