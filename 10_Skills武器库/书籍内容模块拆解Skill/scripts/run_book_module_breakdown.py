from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from dispatch_gate import require_dispatch_record

LEDGER = ROOT / "02_资产中心" / "01_原始知识库" / "00_原始资料输入清单.md"
EXEC_RECORD_DIR = ROOT / "01_Agent系统" / "04_小拆-内容拆解Agent" / "99_执行记录"
EXECUTOR = ROOT / "10_Skills武器库" / "书籍内容模块拆解Skill" / "scripts" / "execute_book_module_breakdown.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="小拆正式受理整本书内容模块拆解")
    parser.add_argument("--title", required=True, help="书名，如 低风险创业")
    parser.add_argument("--write-audit", action="store_true", help="执行完成后自动触发小审审核")
    return parser.parse_args()


def find_ledger_row(title: str) -> tuple[str, str] | None:
    text = LEDGER.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        if f"| {title} |" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 6:
                return cells[4].strip("`"), cells[5]
    return None


def write_accept_record(title: str, source_path: str) -> Path:
    EXEC_RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = EXEC_RECORD_DIR / f"{stamp}_拆书内容模块受理_{title}.md"
    lines = [
        "# 小拆执行记录",
        "",
        "- 任务：整本书内容模块拆解",
        f"- 书名：{title}",
        f"- 来源：`{source_path}`",
        f"- 受理时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 正式执行器：`{EXECUTOR}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    try:
        dispatch = require_dispatch_record(
            ROOT,
            task_type="整本书内容拆解",
            target_agent="小拆",
            input_keyword=args.title,
        )
    except RuntimeError as exc:
        print(f"[受理失败] {exc}")
        return 1
    row = find_ledger_row(args.title)
    if row is None:
        print(f"[受理失败] 找不到书名：{args.title}")
        return 1
    source_rel, status = row
    if status not in ("未拆解", "已拆解", "待重拆"):
        print(f"[受理失败] 当前状态不可执行：{status}")
        return 1
    record = write_accept_record(args.title, source_rel)
    print(f"record\t{record}")
    print(f"dispatch\t{dispatch.path}")
    cmd = [sys.executable, str(EXECUTOR), "--title", args.title]
    if args.write_audit:
        cmd.append("--write-audit")
    result = subprocess.run(cmd, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

