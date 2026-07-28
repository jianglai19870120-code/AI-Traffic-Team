from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("AI_TRAFFIC_FACTORY_ROOT") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT / "tools"))

from brand_footer import append_brand_footer

SOURCE_DIR = ROOT / "02_资产中心" / "01_原始知识库" / "99_我的工作纪实"
MODULE_ROOT = ROOT / "02_资产中心" / "02_内容模块库" / "99_工作纪实模块"
HISTORY_DIR = ROOT / "02_资产中心" / "02_内容模块库" / "99_工作纪实模块" / "99_历史处理记录"
QUOTE_DIR = MODULE_ROOT / "01_金句模块"
MISTAKE_DIR = MODULE_ROOT / "02_误区模块"
STEP_DIR = MODULE_ROOT / "03_步骤模块"
INDEX_DIR = MODULE_ROOT / "05_模块索引"
DISPATCH_DIR = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent" / "99_本地运行记录" / "调度记录"
EXEC_LOG_DIR = ROOT / "01_Agent系统" / "04_小拆-内容拆解Agent" / "99_执行记录" / "执行记录"
RUN_SCRIPT = Path(__file__).with_name("run_work_journal_breakdown.py")
DASHBOARD_SCRIPT = ROOT / "tools" / "build_xiaojiang_dashboard.py"

RESERVED_SOURCE_NAMES = {"README.md", ".sync-state.json"}
RESERVED_SOURCE_PREFIXES = ("样板-",)
PRESERVED_MODULE_FILES = {
    MODULE_ROOT / "README.md",
    INDEX_DIR / "字段说明.md",
}


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


def is_reserved_source(path: Path) -> bool:
    return path.name in RESERVED_SOURCE_NAMES or any(path.name.startswith(prefix) for prefix in RESERVED_SOURCE_PREFIXES)


def collect_source_files() -> list[Path]:
    return sorted(path for path in SOURCE_DIR.glob("*.md") if path.is_file() and not is_reserved_source(path))


def resolve_source_files(names: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for name in names:
        path = SOURCE_DIR / name
        if not path.exists() or not path.is_file() or is_reserved_source(path):
            raise FileNotFoundError(f"工作纪实原始资料不存在或不可受理：{name}")
        resolved.append(path)
    return resolved


def load_processed_sources() -> set[str]:
    processed: set[str] = set()
    if not HISTORY_DIR.exists():
        return processed
    for path in HISTORY_DIR.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            source_path = str(payload.get("source_path", "")).strip()
            if source_path:
                processed.add(source_path)
    return processed


def write_dispatch_record(source_path: Path) -> Path:
    DISPATCH_DIR.mkdir(parents=True, exist_ok=True)
    subject = source_path.stem
    record = DISPATCH_DIR / f"{stamp()}_工作纪实内容模块拆解_{slug(subject)}.md"
    record.write_text(
        append_brand_footer(
            "\n".join(
                [
                    "# 小姜正式分配记录",
                    "",
                    "## 门禁必填字段",
                    "",
                    f"- 任务名称：工作纪实内容模块拆解_{subject}",
                    "- 任务类型：工作纪实内容模块拆解",
                    "- 目标 Agent：小拆",
                    "- 执行 Skill：工作纪实内容模块拆解Skill",
                    "- 审核 Agent：小审",
                    f"- 输入来源：{source_path.name}",
                    "- 是否需要小审：是",
                    f"- 创建时间：{now()}",
                    "",
                    "## 分配结论",
                    "",
                    "- 小姜将本任务正式分配给：小拆",
                    "- 专业 Agent 必须先读取自己的能力清单、调用规则、输入合同和输出合同。",
                    "- 专业 Agent 执行完成后，正式成果必须按规则交小审审核。",
                    "- 小审回读前必须刷新小姜工作台。",
                ]
            )
        ),
        encoding="utf-8",
    )
    return record


def clear_work_journal_outputs() -> None:
    for folder in (QUOTE_DIR, MISTAKE_DIR, STEP_DIR, INDEX_DIR, HISTORY_DIR):
        folder.mkdir(parents=True, exist_ok=True)
        for path in folder.iterdir():
            if path in PRESERVED_MODULE_FILES:
                continue
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()


def run_single(source_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUN_SCRIPT), "--source-file", source_path.name],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def refresh_dashboard() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DASHBOARD_SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def write_batch_record(total: int, skipped: int, results: list[dict[str, object]], dashboard_result: subprocess.CompletedProcess[str]) -> Path:
    EXEC_LOG_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for item in results if item["result"] == "通过")
    returned = sum(1 for item in results if item["result"] == "退回")
    failed = sum(1 for item in results if item["result"] == "执行失败")
    record = EXEC_LOG_DIR / f"{stamp()}_工作纪实内容模块批量执行_增量补齐.md"
    lines = [
        "# 工作纪实批量执行记录",
        "",
        f"- 执行时间：{now()}",
        "- 任务：工作纪实内容模块拆解增量补齐",
        "- 执行模式：batch -> single",
        f"- 原始工作纪实总数：{total}",
        f"- 已处理跳过数：{skipped}",
        f"- 本轮执行数：{len(results)}",
        f"- 审核通过数：{passed}",
        f"- 审核退回数：{returned}",
        f"- 执行失败数：{failed}",
        "",
        "## 本轮明细",
        "",
    ]
    if results:
        for item in results:
            lines.append(
                f"- {item['source_file']}｜{item['result']}｜调度：`{item['dispatch_record']}`"
            )
    else:
        lines.append("- 本轮没有新的待处理工作纪实。")

    lines += [
        "",
        "## 工作台刷新",
        "",
        f"- 刷新结果：{'成功' if dashboard_result.returncode == 0 else '失败'}",
        f"- 输出：{dashboard_result.stdout.strip() or '无'}",
    ]
    record.write_text(append_brand_footer("\n".join(lines)), encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="工作纪实内容模块拆解批量增量受理入口")
    parser.add_argument("--limit", type=int, help="只处理前 N 条待处理工作纪实")
    parser.add_argument("--reprocess-all", action="store_true", help="忽略既有逐篇摘要，按当前正式规则重跑全部工作纪实")
    parser.add_argument("--source-file", action="append", dest="source_files", help="只处理指定工作纪实文件名，可重复传入")
    args = parser.parse_args()

    source_files = collect_source_files()
    processed = load_processed_sources()
    if args.source_files:
        pending = resolve_source_files(args.source_files)
    else:
        pending = list(source_files) if args.reprocess_all else [path for path in source_files if str(path) not in processed]
    if args.reprocess_all:
        clear_work_journal_outputs()
    if args.limit is not None:
        pending = pending[: max(args.limit, 0)]

    results: list[dict[str, object]] = []
    for source_path in pending:
        dispatch_record = write_dispatch_record(source_path)
        result = run_single(source_path)
        if result.returncode == 0:
            status = "通过"
        else:
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            status = "退回" if "result=退回" in stdout or "result=退回" in stderr else "执行失败"
        results.append(
            {
                "source_file": source_path.name,
                "result": status,
                "dispatch_record": str(dispatch_record),
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        )
        print(f"{source_path.name}\t{status}")

    dashboard_result = refresh_dashboard()
    skipped = 0 if (args.reprocess_all or args.source_files) else len(source_files) - len(pending)
    batch_record = write_batch_record(len(source_files), skipped, results, dashboard_result)
    print(f"batch_record={batch_record}")
    print(f"dashboard_refresh={'成功' if dashboard_result.returncode == 0 else '失败'}")
    return 0 if all(item["result"] in {"通过", "退回"} for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
