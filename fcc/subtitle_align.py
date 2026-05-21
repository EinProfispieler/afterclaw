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
TOKEN_SEASON_EP_RE = re.compile(r"(?i)season\W*(\d{1,2})\W*e(?:p)?\W*(\d{1,2})")
TOKEN_3DIGIT_RE = re.compile(r"(?<!\d)(\d)(\d{2})(?!\d)")
SEASON_CN_RE = re.compile(r"第([0-9一二三四五六七八九十]{1,3})季")
EP_2DIGIT_RE = re.compile(r"(?<!\d)(\d{2})(?!\d)")
LANG_TOKEN_RE = re.compile(r"(?i)^(zh|zho|cn|chs|cht|sc|tc|eng|en|ja|jp|jpn|ko|kr|kor|fr|de|es|it|pt|ru|ar|hi|vi|th)$")


@dataclass
class AlignItem:
    old_rel: str
    new_rel: str
    kind: str
    skip: bool
    error: str | None = None


def _cn_season_to_int(raw: str) -> int:
    t = str(raw or "").strip()
    if not t:
        return 0
    if t.isdigit():
        return int(t)
    m = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if t == "十":
        return 10
    if t.startswith("十") and len(t) == 2 and t[1] in m:
        return 10 + m[t[1]]
    if t.endswith("十") and len(t) == 2 and t[0] in m:
        return m[t[0]] * 10
    if len(t) == 3 and t[0] in m and t[1] == "十" and t[2] in m:
        return m[t[0]] * 10 + m[t[2]]
    if len(t) == 1 and t in m:
        return m[t]
    return 0


def _token_parse(stem: str) -> tuple[str, int]:
    text = stem or ""
    m = TOKEN_RE.search(text)
    if m:
        season = m.group(1) or m.group(3)
        episode = m.group(2) or m.group(4)
        if season is not None and episode is not None:
            return f"S{int(season):02d}E{int(episode):02d}", int(m.end())
    # Compatibility: Season3.EP01 / Season 3 EP01
    mse = TOKEN_SEASON_EP_RE.search(text)
    if mse:
        return f"S{int(mse.group(1)):02d}E{int(mse.group(2)):02d}", int(mse.end())
    # Compatibility: 第1季.13 / 第一季.13 -> S01E13
    ms = SEASON_CN_RE.search(text)
    if ms:
        season_num = _cn_season_to_int(ms.group(1))
        if 0 < season_num < 100:
            tail = text[ms.end():]
            me = EP_2DIGIT_RE.search(tail)
            if me:
                ep_num = int(me.group(1))
                return f"S{season_num:02d}E{ep_num:02d}", int(ms.end() + me.end())
    # Compatibility: title.213.xxx => S02E13 (single-season digit + 2-digit episode)
    m3 = TOKEN_3DIGIT_RE.search(text)
    if m3:
        return f"S{int(m3.group(1)):02d}E{int(m3.group(2)):02d}", int(m3.end())
    return "", -1


def _token(stem: str) -> str:
    token, _end = _token_parse(stem)
    return token


def _suffix_after_token(stem: str) -> str:
    _tk, end_idx = _token_parse(stem)
    if end_idx < 0:
        return ""
    tail = (stem or "")[end_idx:].strip()
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
