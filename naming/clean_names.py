from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# CJK + 全角
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u3400-\u4dbf]")
_SEASON_RE = re.compile(r"(?i)^S\d{1,2}(E\d{1,2})?$")
_YEAR4_RE = re.compile(r"^20\d{2}$")


def _normalize_stem(s: str) -> str:
    s = s.strip(" .")
    s = re.sub(r"\.{2,}", ".", s)
    s = re.sub(r"[\s_]+", ".", s)
    s = re.sub(r"\.{2,}", ".", s)
    return s.strip(".")


def _remove_substrings(s: str, parts: list[str]) -> str:
    out = s
    for p in sorted((x for x in parts if x), key=len, reverse=True):
        out = out.replace(p, "")
    return out


def _strip_cjk(s: str) -> str:
    return _CJK_RE.sub("", s)


def reorder_season_before_year(stem: str) -> str:
    """将首个 S## / S##E## 节移到首个四位年份 20xx 之前（按「点」分节）。"""
    if "." not in stem:
        return stem
    segs = [p for p in stem.split(".") if p]
    s_idx: int | None = None
    s_val: str | None = None
    for i, seg in enumerate(segs):
        if _SEASON_RE.match(seg):
            s_idx = i
            s_val = seg
            break
    if s_idx is None or s_val is None:
        return stem
    y_idx: int | None = None
    for i, seg in enumerate(segs):
        if _YEAR4_RE.match(seg):
            y_idx = i
            break
    if y_idx is None:
        return stem
    rest = [p for j, p in enumerate(segs) if j != s_idx]
    y = y_idx
    if s_idx < y:
        y -= 1
    rest.insert(y, s_val)
    return ".".join(rest)


def clean_basename(
    name: str,
    *,
    remove_substrings: list[str],
    strip_cjk: bool,
    move_season_before_year: bool,
) -> str:
    """对单个文件/目录的「点分」名称（可含一层扩展名在调用方拼接）做变换。"""
    s = _remove_substrings(name, remove_substrings)
    if strip_cjk:
        s = _strip_cjk(s)
    s = _normalize_stem(s)
    if not s:
        return ""
    if move_season_before_year:
        s = reorder_season_before_year(s)
    s = _normalize_stem(s)
    return s


@dataclass
class RenameItem:
    old_rel: str
    new_rel: str
    kind: Literal["file", "dir"]
    skip: bool
    error: str | None = None


def _target_ok(is_dir: bool, mode: str) -> bool:
    if mode == "both":
        return True
    if mode == "dirs" and is_dir:
        return True
    if mode == "files" and not is_dir:
        return True
    return False


def _stem_suffix(filename: str) -> tuple[str, str]:
    p = Path(filename)
    suf = p.suffix
    if not suf:
        return filename, ""
    return filename[: -len(suf)], suf


def build_rename_plan(
    storage: Path,
    rel_dir: str,
    *,
    target: str,
    recursive: bool,
    remove_substrings: str,
    strip_cjk: bool,
    move_season_before_year: bool,
) -> list[RenameItem]:
    rel_dir = (rel_dir or ".").replace("\\", "/").strip() or "."
    storage = storage.resolve()
    base = (storage / rel_dir).resolve()
    if not base.is_dir():
        raise FileNotFoundError("目录不存在或不是目录")
    try:
        base.relative_to(storage)
    except ValueError as exc:
        raise ValueError("路径不在允许范围内") from exc
    sub_parts = [s.strip() for s in re.split(r"[\r\n]+", remove_substrings) if s.strip()]
    items: list[RenameItem] = []

    def one_entry(path: Path) -> None:
        is_dir = path.is_dir()
        if not is_dir and not path.is_file():
            return
        if not _target_ok(is_dir, target):
            return
        oname = path.name
        if is_dir:
            new_base = clean_basename(
                oname,
                remove_substrings=sub_parts,
                strip_cjk=strip_cjk,
                move_season_before_year=move_season_before_year,
            )
        else:
            stem, ext = _stem_suffix(oname)
            nb = clean_basename(
                stem,
                remove_substrings=sub_parts,
                strip_cjk=strip_cjk,
                move_season_before_year=move_season_before_year,
            )
            if not nb and not ext:
                return
            new_base = f"{nb}{ext}" if nb or ext else ""
        if not new_base or oname == new_base:
            return
        new_rel = (path.parent / new_base).relative_to(storage).as_posix()
        old_rel = path.relative_to(storage).as_posix()
        dest = storage / new_rel
        skip = dest != path and dest.exists()
        err = "目标已存在" if skip else None
        items.append(
            RenameItem(
                old_rel=old_rel,
                new_rel=new_rel,
                kind="dir" if is_dir else "file",
                skip=skip,
                error=err,
            )
        )

    if not recursive:
        for name in sorted(os.listdir(base)):
            p = (base / name).resolve()
            if not p.exists():
                continue
            one_entry(p)
        return items

    for dirpath, _dirnames, filenames in os.walk(str(base), topdown=False):
        p = Path(dirpath).resolve()
        for fn in sorted(filenames):
            one_entry((p / fn).resolve())
        if p == base:
            continue
        if p.is_dir():
            one_entry(p)
    return items


def _rel_depth(relp: str) -> int:
    return 0 if relp in (".", "") else relp.count("/")


def apply_rename_plan(storage: Path, item_payloads: list[dict[str, Any]]) -> list[dict[str, str]]:
    """
    根据预览的 old_rel / new_rel 成对重命名。按路径深度自深到浅，避免父目录名先改导致子路径失效。
    """
    storage = storage.resolve()
    rows: list[dict[str, str]] = []
    pairs: list[tuple[str, str]] = []
    for row in item_payloads:
        old = str(row.get("old_rel", "")).replace("\\", "/")
        new = str(row.get("new_rel", "")).replace("\\", "/")
        if not old or not new or old == new:
            continue
        a = (storage / old).resolve()
        b = (storage / new).resolve()
        try:
            a.relative_to(storage)
            b.relative_to(storage)
        except ValueError:
            rows.append({"old_rel": old, "new_rel": new, "ok": "false", "message": "路径越界"})
            continue
        if not a.exists():
            rows.append({"old_rel": old, "new_rel": new, "ok": "false", "message": "源不存在"})
            continue
        if b != a and b.exists():
            rows.append({"old_rel": old, "new_rel": new, "ok": "false", "message": "目标已存在"})
            continue
        pairs.append((old, new))

    pairs.sort(key=lambda t: -_rel_depth(t[0]))
    for old, new in pairs:
        a = (storage / old).resolve()
        b = (storage / new).resolve()
        if not a.exists():
            rows.append({"old_rel": old, "new_rel": new, "ok": "false", "message": "源已不存在(可能已随父级重命名)"})
            continue
        if b != a and b.exists():
            rows.append({"old_rel": old, "new_rel": new, "ok": "false", "message": "目标已存在"})
            continue
        try:
            a.rename(b)
            rows.append({"old_rel": old, "new_rel": new, "ok": "true", "message": ""})
        except OSError as e:
            rows.append({"old_rel": old, "new_rel": new, "ok": "false", "message": str(e)})
    return rows
