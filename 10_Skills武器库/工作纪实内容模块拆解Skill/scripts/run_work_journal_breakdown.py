from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("AI_TRAFFIC_FACTORY_ROOT") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT / "tools"))

from brand_footer import append_brand_footer
from dispatch_gate import require_dispatch_record

SOURCE_DIR = ROOT / "02_资产中心" / "01_原始知识库" / "99_我的工作纪实"
EXEC_DIR = ROOT / "01_Agent系统" / "04_小拆-内容拆解Agent" / "99_执行记录"
SCRIPT_PATH = Path(__file__).with_name("execute_work_journal_breakdown.py")

RESERVED_SOURCE_NAMES = {"README.md"}
RESERVED_SOURCE_PREFIXES = ("样板-",)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def slug(text: str, max_len: int = 46) -> str:
    cleaned = text
    for token in "\\/:*?\"<>|":
        cleaned = cleaned.replace(token, "_")
    cleaned = "".join(cleaned.split()).strip("._ ，,、：:")
    return cleaned[:max_len] or "未命名"


def resolve_source_file(source_file: str) -> Path:
    path = SOURCE_DIR / source_file
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"工作纪实原始资料不存在：{path}")
    if path.name in RESERVED_SOURCE_NAMES or any(path.name.startswith(prefix) for prefix in RESERVED_SOURCE_PREFIXES):
        raise ValueError(f"该文件不能作为正式拆解输入：{path.name}")
    return path


def write_acceptance_record(source_path: Path) -> Path:
    EXEC_DIR.mkdir(parents=True, exist_ok=True)
    subject = source_path.stem
    record = EXEC_DIR / f"{stamp()}_工作纪实内容模块受理_{slug(subject)}.md"
    record.write_text(
        append_brand_footer(
            "\n".join(
                [
                    "# 小拆受理记录",
                    "",
                    f"- 受理时间：{now()}",
                    "- 任务类型：工作纪实内容模块拆解",
                    "- 目标 Agent：小拆",
                    f"- 受理对象：{subject}",
                    f"- 来源文件：`{source_path}`",
                    "- 执行模式：single",
                    "- 下一步：调用 execute_work_journal_breakdown.py 单条正式拆解并交小审审核",
                ]
            )
        ),
        encoding="utf-8",
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="工作纪实内容模块拆解正式受理入口")
    parser.add_argument("--source-file", required=True)
    args = parser.parse_args()

    source_path = resolve_source_file(args.source_file)
    require_dispatch_record(
        ROOT,
        task_type="工作纪实内容模块拆解",
        target_agent="小拆",
        input_keyword=source_path.name,
    )
    acceptance_record = write_acceptance_record(source_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--mode", "single", "--source-file", source_path.name],
        cwd=ROOT,
        check=False,
    )
    print(f"[工作纪实受理] acceptance_record={acceptance_record}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
