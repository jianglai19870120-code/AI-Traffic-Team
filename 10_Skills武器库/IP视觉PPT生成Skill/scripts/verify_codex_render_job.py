#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

from common import SKILL_ROOT


def sanitize_windows_name(name: str) -> str:
    invalid = '<>:"/\\|?*'
    cleaned = "".join(ch for ch in name if ch not in invalid).strip().rstrip(".")
    return " ".join(cleaned.split())


def find_existing_workdir_by_title(deck_title: str, outputs_root: pathlib.Path) -> pathlib.Path | None:
    title_folder = sanitize_windows_name(deck_title)
    preferred_names = [
        f"{title_folder}（成稿）-work",
        f"{title_folder}-work",
    ]
    for name in preferred_names:
        candidate = outputs_root / name
        if candidate.exists():
            return candidate.resolve()
    if not outputs_root.exists():
        return None
    for candidate in sorted(outputs_root.iterdir()):
        if candidate.is_dir() and candidate.name.startswith(title_folder) and candidate.name.endswith("-work"):
            return candidate.resolve()
    return None


def load_render_job(workdir: pathlib.Path) -> dict[str, Any]:
    job_path = workdir / "codex-render-job.json"
    if not job_path.exists():
        raise FileNotFoundError(f"找不到 render job 文件: {job_path}")
    return json.loads(job_path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description="核对 Codex render job 对应的正式成品目录是否已写齐目标 PNG")
    ap.add_argument("--workdir", default=None, help="显式指定工作包目录")
    ap.add_argument("--deck-title", default=None, help="按选题标题匹配现有工作包")
    args = ap.parse_args()

    outputs_root = SKILL_ROOT / "outputs"
    if args.workdir:
        workdir = pathlib.Path(args.workdir).expanduser().resolve()
    elif args.deck_title:
        workdir = find_existing_workdir_by_title(args.deck_title, outputs_root)
        if workdir is None:
            raise FileNotFoundError(f"未找到与选题标题匹配的工作包: {args.deck_title}")
    else:
        raise ValueError("必须传 --workdir 或 --deck-title")

    job = load_render_job(workdir)
    expected_outputs = [pathlib.Path(item).resolve() for item in job.get("expected_outputs", [])]
    missing = [str(path) for path in expected_outputs if not path.exists()]
    result = {
        "job_type": job.get("job_type"),
        "deck_title": job.get("deck_title"),
        "work_package_dir": str(workdir),
        "archive_dir": job.get("archive_dir"),
        "expected_output_count": len(expected_outputs),
        "complete": not missing,
        "missing_outputs": missing,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
