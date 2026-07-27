from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


DISPATCH_DIR = Path("01_Agent系统") / "01_小姜-CEO助理Agent" / "99_本地运行记录" / "调度记录"


@dataclass(frozen=True)
class DispatchRecord:
    path: Path
    task_name: str
    task_type: str
    target_agent: str
    input_source: str
    requires_audit: str
    created_at: str


def _read_field(text: str, label: str) -> str:
    patterns = [
        rf"^- {re.escape(label)}：\s*(?P<value>.+?)\s*$",
        rf"^{re.escape(label)}：\s*(?P<value>.+?)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match:
            return match.group("value").strip().strip("`")
    return ""


def find_dispatch_record(root: Path, *, task_type: str, target_agent: str, input_keyword: str) -> DispatchRecord | None:
    dispatch_dir = root / DISPATCH_DIR
    if not dispatch_dir.exists():
        return None

    candidates: list[tuple[float, DispatchRecord]] = []
    for path in dispatch_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        record = DispatchRecord(
            path=path,
            task_name=_read_field(text, "任务名称"),
            task_type=_read_field(text, "任务类型"),
            target_agent=_read_field(text, "目标 Agent"),
            input_source=_read_field(text, "输入来源"),
            requires_audit=_read_field(text, "是否需要小审"),
            created_at=_read_field(text, "创建时间"),
        )
        required_values = [
            record.task_name,
            record.task_type,
            record.target_agent,
            record.input_source,
            record.requires_audit,
            record.created_at,
        ]
        if not all(required_values):
            continue
        if task_type not in record.task_type:
            continue
        if target_agent not in record.target_agent:
            continue
        if input_keyword not in record.input_source and input_keyword not in record.task_name and input_keyword not in path.name:
            continue
        candidates.append((path.stat().st_mtime, record))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def require_dispatch_record(root: Path, *, task_type: str, target_agent: str, input_keyword: str) -> DispatchRecord:
    record = find_dispatch_record(
        root,
        task_type=task_type,
        target_agent=target_agent,
        input_keyword=input_keyword,
    )
    if record is None:
        raise RuntimeError(
            "缺小姜正式分配：正式 Agent 执行器启动前，必须先在 "
            f"{root / DISPATCH_DIR} 写入包含任务名称、任务类型、目标 Agent、输入来源、是否需要小审、创建时间的小姜调度记录。"
        )
    return record
