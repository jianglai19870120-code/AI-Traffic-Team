#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import pathlib
from datetime import datetime
from typing import Any

from common import SKILL_ROOT, load_config, read_text, write_json, write_text


TEXT_EXTENSIONS = {".json", ".md", ".txt"}
LEGACY_ROOT = pathlib.Path(r"E:\Skills武器库\PPT 个人IP生成")
LEGACY_SKILL_ROOT = LEGACY_ROOT / "ip-notebook-ppt-skill"
LEGACY_ARCHIVE_ROOT = LEGACY_ROOT / "短视频PPT配图"
LEGACY_AI_ROOT = pathlib.Path("E:\\") / "AI内容工厂" / "05_视频配图大师"
LEGACY_AI_SKILL_ROOT = LEGACY_AI_ROOT / "01_PPT 个人IP生成" / "ip-notebook-ppt-skill"
LEGACY_AI_PROJECT_ROOT = LEGACY_AI_ROOT / "01_PPT 个人IP生成"
LEGACY_AI_ARCHIVE_ROOT = LEGACY_AI_ROOT / "02_短视频PPT配图"
LEGACY_INSTALLED_SKILL_ROOT = pathlib.Path.home() / ".codex" / "skills" / "ip-ppt-skill"


def build_replacements(archive_root: pathlib.Path) -> list[tuple[str, str]]:
    replacements = [
        (str(LEGACY_AI_SKILL_ROOT), str(SKILL_ROOT)),
        (str(LEGACY_AI_ARCHIVE_ROOT), str(archive_root)),
        (str(LEGACY_AI_PROJECT_ROOT), str(SKILL_ROOT)),
        (str(LEGACY_SKILL_ROOT), str(SKILL_ROOT)),
        (str(LEGACY_ARCHIVE_ROOT), str(archive_root)),
        (str(LEGACY_ROOT), str(SKILL_ROOT)),
        (str(LEGACY_INSTALLED_SKILL_ROOT), str(SKILL_ROOT)),
    ]
    replacements.sort(key=lambda item: len(item[0]), reverse=True)
    return replacements


def iter_target_dirs(archive_root: pathlib.Path) -> list[pathlib.Path]:
    targets = [
        SKILL_ROOT / "outputs",
        archive_root,
    ]
    targets.extend(sorted(SKILL_ROOT.glob("tmp-verify*")))
    return [path for path in targets if path.exists()]


def iter_text_files(base_dir: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for path in base_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            files.append(path)
    return files


def rewrite_text(text: str, replacements: list[tuple[str, str]]) -> tuple[str, list[str]]:
    rewritten = text
    matched: list[str] = []
    for old, new in replacements:
        if old in rewritten:
            rewritten = rewritten.replace(old, new)
            matched.append(old)
    return rewritten, matched


def main() -> None:
    cfg = load_config()
    archive_root = pathlib.Path(str(cfg["archive_root"])).expanduser().resolve()
    replacements = build_replacements(archive_root)
    targets = iter_target_dirs(archive_root)

    changed_files: list[dict[str, Any]] = []
    unchanged_files = 0

    for target_dir in targets:
        for file_path in iter_text_files(target_dir):
            original = read_text(file_path)
            rewritten, matched = rewrite_text(original, replacements)
            if rewritten == original:
                unchanged_files += 1
                continue
            write_text(file_path, rewritten)
            changed_files.append({
                "file": str(file_path),
                "matched_legacy_prefixes": matched,
            })

    remaining_legacy_hits: list[str] = []
    for target_dir in targets:
        for file_path in iter_text_files(target_dir):
            text = read_text(file_path)
            if (
                str(LEGACY_ROOT) in text
                or str(LEGACY_AI_PROJECT_ROOT) in text
                or str(LEGACY_AI_ARCHIVE_ROOT) in text
                or str(LEGACY_INSTALLED_SKILL_ROOT) in text
            ):
                remaining_legacy_hits.append(str(file_path))

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "skill_root": str(SKILL_ROOT),
        "archive_root": str(archive_root),
        "scanned_dirs": [str(path) for path in targets],
        "changed_file_count": len(changed_files),
        "unchanged_file_count": unchanged_files,
        "changed_files": changed_files,
        "remaining_legacy_hits": remaining_legacy_hits,
    }

    report_dir = SKILL_ROOT.parent.parent / "05_视频配图大师" / "00_系统说明" / "migration-reports"
    report_path = report_dir / f"path-migration-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    write_json(report_path, report)
    print(json.dumps({"report_file": str(report_path), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
