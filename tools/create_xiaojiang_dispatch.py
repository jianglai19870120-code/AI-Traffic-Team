from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH_DIR = ROOT / "_private" / "agent_records" / "01_小姜-CEO助理Agent" / "调度记录"


def slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text).strip("_")
    return cleaned[:80] or "untitled"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建小姜正式分配记录")
    parser.add_argument("--task-name", required=True, help="任务名称")
    parser.add_argument("--task-type", required=True, help="任务类型，例如 整本书内容拆解")
    parser.add_argument("--target-agent", required=True, help="目标 Agent，例如 小拆")
    parser.add_argument("--input-source", required=True, help="输入来源，例如 书名或文件路径")
    parser.add_argument("--requires-audit", choices=["是", "否"], default="是", help="是否需要小审")
    parser.add_argument("--execution-skill", default="", help="执行 Skill，例如 爆款选题分类Skill")
    parser.add_argument("--audit-agent", default="", help="审核 Agent，例如 小审")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    DISPATCH_DIR.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = DISPATCH_DIR / f"{stamp}_小姜正式分配_{slug(args.task_type)}_{slug(args.input_source)}.md"
    lines = [
        "# 小姜正式分配记录",
        "",
        "## 门禁必填字段",
        "",
        f"- 任务名称：{args.task_name}",
        f"- 任务类型：{args.task_type}",
        f"- 目标 Agent：{args.target_agent}",
        *([f"- 执行 Skill：{args.execution_skill}"] if args.execution_skill else []),
        *([f"- 审核 Agent：{args.audit_agent}"] if args.audit_agent else []),
        f"- 输入来源：{args.input_source}",
        f"- 是否需要小审：{args.requires_audit}",
        f"- 创建时间：{created_at}",
        "",
        "## 分配结论",
        "",
        f"- 小姜将本任务正式分配给：{args.target_agent}",
        "- 专业 Agent 必须先读取自己的能力清单、调用规则、输入合同和输出合同。",
        "- 专业 Agent 执行完成后，正式成果必须按规则交小审审核。",
        "- 小审回读前必须刷新小姜工作台。",
        "",
        "---",
        "",
        "品牌尾注：",
        "",
        "- 带你用AI，把你的能力变成你的生意。",
        "- AI流量工厂作者：姜来已来2046",
        "- 有任何使用问题，可以联系我！微信： lact175",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
