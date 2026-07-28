#!/usr/bin/env python3
"""Validate active AI流量团队 contracts before public release."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


EXPECTED_TOPIC_HEADER = [
    "序号",
    "文案结构",
    "选题",
    "链接",
    "正文时间",
    "正文状态",
    "成稿时间",
    "成稿状态",
    "视觉时间",
    "视觉状态",
]
REQUIRED_MIGRATION_KEYS = {
    "skillName",
    "installDirName",
    "entry",
    "workspaceRootEnv",
    "workspaceDependencies",
    "defaultOutputPaths",
    "optionalCommands",
}
KNOWN_STATUSES = ("可公开安装", "仅内部使用", "安装契约已锁定")
PUBLIC_REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "输入说明.md",
    "输出说明.md",
    "依赖说明.md",
    "公开状态.md",
    "migration.json",
)
TASK_OWNERS = {
    "整本书内容拆解": "04_小拆-内容拆解Agent",
    "爆款开头拆解": "05_小镜-对标结构研究Agent",
    "爆款选题主题分类": "06_小策-选题策略Agent",
    "干货正文方案生成": "07_小写-文案生产Agent",
    "爆款开头卡片审核": "02_小审-质量审核Agent",
}
SCAN_SUFFIXES = {".md", ".py", ".ps1", ".json", ".yaml", ".yml"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 AI流量团队正式合同一致性")
    parser.add_argument(
        "--root",
        default=os.environ.get("AI_TRAFFIC_FACTORY_ROOT"),
        help="工作区根目录",
    )
    parser.add_argument("--check-installed", action="store_true", help="同时检查 Codex Skill 安装副本")
    parser.add_argument("--install-root", default=str(Path.home() / ".codex" / "skills"))
    parser.add_argument(
        "--public-package",
        action="store_true",
        help="按公开包口径检查；允许仅内部使用 Skill 的本地数据依赖缺失",
    )
    return parser.parse_args()


def markdown_header(path: Path) -> list[str]:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if "序号" in cells and "文案结构" in cells and "选题" in cells:
            return cells
    return []


def active_files(root: Path):
    scan_roots = [
        root / "README.md",
        root / "AGENTS.md",
        root / "00_系统说明",
        root / "01_Agent系统",
        root / "03_工作流中心",
        root / "10_Skills武器库",
        root / "tools",
    ]
    for scan_root in scan_roots:
        paths = [scan_root] if scan_root.is_file() else scan_root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            relative = path.relative_to(root)
            if any(part.startswith("99_") for part in relative.parts):
                continue
            if "__pycache__" in relative.parts:
                continue
            yield path, relative


def parse_status(text: str) -> str:
    for status in KNOWN_STATUSES:
        if status in text:
            return status
    return ""


def check_agent_owners(root: Path, errors: list[str]) -> None:
    ability_files = list((root / "01_Agent系统").glob("*/能力清单.md"))
    for task, expected_dir in TASK_OWNERS.items():
        owners: list[str] = []
        for path in ability_files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if not line.startswith("|"):
                    continue
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if len(cells) >= 2 and cells[0] == task and cells[1] == "是":
                    owners.append(path.parent.name)
        if owners != [expected_dir]:
            errors.append(f"任务归属冲突：{task} -> 实际 {owners}，期望 [{expected_dir}]")


def check_skills(root: Path, errors: list[str], public_package: bool) -> None:
    skill_root = root / "10_Skills武器库"
    matrix_path = skill_root / "Skill公开状态矩阵.md"
    matrix_text = matrix_path.read_text(encoding="utf-8", errors="replace")
    matrix_status: dict[str, str] = {}
    for line in matrix_text.splitlines():
        if not line.startswith("|") or "Skill" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 3 and cells[0].endswith("Skill"):
            matrix_status[cells[0]] = cells[2]

    for skill_dir in sorted(path for path in skill_root.iterdir() if path.is_dir()):
        migration_path = skill_dir / "migration.json"
        if not migration_path.exists():
            continue
        try:
            migration = json.loads(migration_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{migration_path.relative_to(root)} JSON 无效：{exc}")
            continue

        missing_keys = REQUIRED_MIGRATION_KEYS - migration.keys()
        if missing_keys:
            errors.append(f"{migration_path.relative_to(root)} 缺少字段：{sorted(missing_keys)}")
        if migration.get("workspaceRootEnv") != "AI_TRAFFIC_FACTORY_ROOT":
            errors.append(f"{skill_dir.name} 未统一使用 AI_TRAFFIC_FACTORY_ROOT")

        status_path = skill_dir / "公开状态.md"
        status = parse_status(status_path.read_text(encoding="utf-8", errors="replace"))

        dependencies = migration.get("workspaceDependencies", [])
        if len(dependencies) != len(set(dependencies)):
            errors.append(f"{skill_dir.name} migration.json 存在重复依赖")
        for dependency in dependencies:
            if not (root / dependency).exists() and not (
                public_package and status == "仅内部使用"
            ):
                errors.append(f"{skill_dir.name} 依赖路径不存在：{dependency}")
        for command in migration.get("optionalCommands", []):
            if re.search(r"[A-Z]:\\\\", command):
                errors.append(f"{skill_dir.name} 可选命令含绝对路径：{command}")

        matrix_value = matrix_status.get(skill_dir.name, "")
        if not matrix_value:
            errors.append(f"状态矩阵缺少 Skill：{skill_dir.name}")
        elif status and status not in matrix_value:
            errors.append(f"状态不一致：{skill_dir.name} 文件={status}，矩阵={matrix_value}")
        if status == "可公开安装":
            for filename in PUBLIC_REQUIRED_FILES:
                if not (skill_dir / filename).is_file():
                    errors.append(f"{skill_dir.name} 可公开安装但缺少 {filename}")


def check_contract_terms(root: Path, errors: list[str]) -> None:
    legacy_terms = ("00_总选题输入表.md", "手动输入选题表")
    forbidden_envs = ("GANHUO_AI_TRAFFIC_FACTORY_ROOT", "REMEN_BOKE_AI_TRAFFIC_FACTORY_ROOT")
    brand_phrase = "带你用AI，把你的能力变成你的生意"

    for path, relative in active_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative_text = relative.as_posix()
        if relative_text == "tools/check_system_consistency.py":
            continue
        is_compat_script = relative_text.endswith(
            "爆款选题分类Skill/scripts/classify_benchmark_topics.py"
        )
        if not is_compat_script:
            for term in legacy_terms:
                if term in text:
                    errors.append(f"现役合同残留旧名称：{relative_text} -> {term}")
        for env_name in forbidden_envs:
            if env_name in text and not relative_text.endswith(
                "得到大脑工作纪实同步Skill/scripts/sync_dedao_brain.py"
            ):
                errors.append(f"现役合同残留旧环境变量：{relative_text} -> {env_name}")
        if re.search(r"E:\\AI流量工厂(?:\\|`|\s|$)", text) and not relative_text.startswith("tools/"):
            errors.append(f"现役合同含作者绝对路径：{relative_text}")
        if path.suffix == ".py" and brand_phrase in text and relative_text != "tools/brand_footer.py":
            errors.append(f"脚本重复硬编码品牌尾注：{relative_text}")


def check_topic_table(root: Path, errors: list[str]) -> None:
    path = root / "02_资产中心/04_爆款选题库/00_爆款选题选中清单.md"
    if not path.is_file():
        errors.append("缺少 00_爆款选题选中清单.md")
        return
    actual = markdown_header(path)
    if actual != EXPECTED_TOPIC_HEADER:
        errors.append(f"爆款选题选中清单字段错误：{actual}")


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve() if args.root else Path(__file__).resolve().parents[1]
    errors: list[str] = []

    check_agent_owners(root, errors)
    check_skills(root, errors, args.public_package)
    check_contract_terms(root, errors)
    check_topic_table(root, errors)

    if args.check_installed:
        sync_script = root / "tools/sync_installed_skills.py"
        result = subprocess.run(
            [
                sys.executable,
                str(sync_script),
                "--root",
                str(root),
                "--install-root",
                str(Path(args.install_root).expanduser()),
            ],
            check=False,
        )
        if result.returncode:
            errors.append("Codex Skill 安装副本与工作区源码不一致")

    for error in errors:
        print(f"[FAIL] {error}")
    if errors:
        print(f"一致性检查失败：{len(errors)} 项。")
        return 1

    print("AI流量团队正式合同一致性检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
