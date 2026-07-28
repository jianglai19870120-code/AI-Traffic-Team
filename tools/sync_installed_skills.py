#!/usr/bin/env python3
"""Check or mirror workspace skills into the local Codex skills directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


SKIP_DIRS = {".tmp", "outputs", "__pycache__", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="同步 AI流量团队 Skill 到 Codex 安装目录")
    parser.add_argument(
        "--root",
        default=os.environ.get("AI_TRAFFIC_FACTORY_ROOT"),
        help="AI流量团队工作区；默认读取 AI_TRAFFIC_FACTORY_ROOT 或脚本上级目录",
    )
    parser.add_argument(
        "--install-root",
        default=str(Path.home() / ".codex" / "skills"),
        help="Codex skills 安装根目录",
    )
    parser.add_argument("--apply", action="store_true", help="执行镜像同步；默认只检查")
    parser.add_argument("--skill", action="append", dest="skills", help="只处理指定 Skill，可重复")
    return parser.parse_args()


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.is_file() and path.suffix.lower() not in SKIP_SUFFIXES:
            yield path, relative


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {relative.as_posix(): file_hash(path) for path, relative in iter_files(root)}


def load_skill_specs(root: Path, selected: set[str]) -> list[tuple[str, Path, Path]]:
    skill_root = root / "10_Skills武器库"
    specs: list[tuple[str, Path, Path]] = []
    for source in sorted(path for path in skill_root.iterdir() if path.is_dir()):
        migration = source / "migration.json"
        if not migration.exists():
            continue
        data = json.loads(migration.read_text(encoding="utf-8"))
        skill_name = data.get("skillName")
        install_name = data.get("installDirName")
        if not skill_name or not install_name:
            raise ValueError(f"{migration}: 缺少 skillName 或 installDirName")
        if selected and source.name not in selected and skill_name not in selected:
            continue
        specs.append((source.name, source, Path(install_name)))
    return specs


def safe_target(install_root: Path, install_name: Path) -> Path:
    if install_name.is_absolute() or len(install_name.parts) != 1:
        raise ValueError(f"installDirName 必须是单层目录名：{install_name}")
    target = (install_root / install_name).resolve()
    try:
        target.relative_to(install_root)
    except ValueError as exc:
        raise ValueError(f"安装目标越界：{target}") from exc
    return target


def sync_one(source: Path, target: Path) -> None:
    temp = target.with_name(f".{target.name}.sync-tmp")
    if temp.exists():
        shutil.rmtree(temp)
    shutil.copytree(
        source,
        temp,
        ignore=shutil.ignore_patterns(*SKIP_DIRS, "*.pyc", "*.pyo"),
    )
    if target.exists():
        shutil.rmtree(target)
    temp.replace(target)


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve() if args.root else Path(__file__).resolve().parents[1]
    install_root = Path(args.install_root).expanduser().resolve()
    selected = set(args.skills or [])

    if not (root / "10_Skills武器库").is_dir():
        print(f"[FAIL] 找不到 Skill 源目录：{root}")
        return 2

    specs = load_skill_specs(root, selected)
    if selected and not specs:
        print(f"[FAIL] 没有命中指定 Skill：{sorted(selected)}")
        return 2

    drifted: list[str] = []
    for source_name, source, install_name in specs:
        target = safe_target(install_root, install_name)
        source_manifest = manifest(source)
        target_manifest = manifest(target)
        if source_manifest == target_manifest:
            print(f"[OK] {source_name} -> {target}")
            continue

        added = len(source_manifest.keys() - target_manifest.keys())
        removed = len(target_manifest.keys() - source_manifest.keys())
        changed = sum(
            1
            for key in source_manifest.keys() & target_manifest.keys()
            if source_manifest[key] != target_manifest[key]
        )
        if args.apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            sync_one(source, target)
            if manifest(source) != manifest(target):
                print(f"[FAIL] 同步后仍不一致：{source_name}")
                return 1
            print(f"[SYNCED] {source_name}: +{added} -{removed} ~{changed}")
        else:
            drifted.append(source_name)
            print(f"[DRIFT] {source_name}: +{added} -{removed} ~{changed}")

    if drifted:
        print(f"检测到 {len(drifted)} 个 Skill 安装副本漂移。使用 --apply 同步。")
        return 1
    print(f"Skill 安装副本检查通过：{len(specs)} 个。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
