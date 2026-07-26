#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

from common import ensure_dir


def verify_png(path: pathlib.Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"正式归档文件不存在: {path}")
    if path.stat().st_size <= 0:
        raise ValueError(f"正式归档文件为空: {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="把 Codex 生成缓存图复制到正式目录，并在成功后删除这张缓存图。")
    ap.add_argument("--source", required=True, help="Codex 生成缓存图路径")
    ap.add_argument("--dest", required=True, help="正式归档目标路径")
    args = ap.parse_args()

    source = pathlib.Path(args.source).expanduser().resolve()
    dest = pathlib.Path(args.dest).expanduser().resolve()

    if not source.exists():
        raise FileNotFoundError(f"找不到缓存图: {source}")

    ensure_dir(dest.parent)
    tmp_dest = dest.with_name(dest.name + ".tmp")
    if tmp_dest.exists():
        tmp_dest.unlink()

    shutil.copy2(source, tmp_dest)
    tmp_dest.replace(dest)
    verify_png(dest)
    source.unlink()

    print(json.dumps({
        "status": "archived-and-cleaned",
        "source_deleted": str(source),
        "dest": str(dest),
        "dest_size": dest.stat().st_size,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(json.dumps({
            "status": "error",
            "error": str(exc),
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
