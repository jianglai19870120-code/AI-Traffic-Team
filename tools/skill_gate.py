from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class GateResult:
    status: str
    agent_name: str
    task_name: str
    skill_name: str
    skill_dir: str
    skill_exists: bool
    has_skill_md: bool
    has_readme: bool
    has_executor: bool
    executor_path: str
    has_io_contract: bool
    audit_name: str
    has_audit_executor: bool
    audit_executor_path: str
    required_formal_output: bool
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _skill_dir(skill_name: str) -> Path:
    return ROOT / "10_Skills武器库" / skill_name


def _agent_dir(agent_name: str) -> Path:
    return ROOT / "01_Agent系统" / agent_name


def check_skill_gate(
    *,
    agent_name: str,
    task_name: str,
    skill_name: str,
    executor_relative_path: str,
    audit_name: str,
    audit_executor_relative_path: str,
    required_formal_output: bool = True,
) -> GateResult:
    skill_dir = _skill_dir(skill_name)
    skill_exists = skill_dir.exists()
    has_skill_md = (skill_dir / "SKILL.md").exists()
    has_readme = (skill_dir / "README.md").exists()
    executor_path = skill_dir / executor_relative_path
    has_executor = executor_path.exists()
    has_io_contract = all(
        (skill_dir / name).exists()
        for name in ["输入说明.md", "输出说明.md", "依赖说明.md"]
    )

    audit_agent_dir = _agent_dir(audit_name)
    audit_executor_path = audit_agent_dir / audit_executor_relative_path
    has_audit_executor = audit_executor_path.exists()

    if not skill_exists or not has_skill_md:
        return GateResult(
            status="blocked_missing_skill",
            agent_name=agent_name,
            task_name=task_name,
            skill_name=skill_name,
            skill_dir=str(skill_dir),
            skill_exists=skill_exists,
            has_skill_md=has_skill_md,
            has_readme=has_readme,
            has_executor=has_executor,
            executor_path=str(executor_path),
            has_io_contract=has_io_contract,
            audit_name=audit_name,
            has_audit_executor=has_audit_executor,
            audit_executor_path=str(audit_executor_path),
            required_formal_output=required_formal_output,
            message=f"{skill_name} 不存在或缺少 SKILL.md，不能正式执行。",
        )

    if not has_executor:
        return GateResult(
            status="blocked_missing_skill_executor",
            agent_name=agent_name,
            task_name=task_name,
            skill_name=skill_name,
            skill_dir=str(skill_dir),
            skill_exists=skill_exists,
            has_skill_md=has_skill_md,
            has_readme=has_readme,
            has_executor=has_executor,
            executor_path=str(executor_path),
            has_io_contract=has_io_contract,
            audit_name=audit_name,
            has_audit_executor=has_audit_executor,
            audit_executor_path=str(audit_executor_path),
            required_formal_output=required_formal_output,
            message=f"{skill_name} 只有文档或示例，没有正式执行器，不能执行 {task_name}。",
        )

    if not has_io_contract:
        return GateResult(
            status="blocked_missing_io_contract",
            agent_name=agent_name,
            task_name=task_name,
            skill_name=skill_name,
            skill_dir=str(skill_dir),
            skill_exists=skill_exists,
            has_skill_md=has_skill_md,
            has_readme=has_readme,
            has_executor=has_executor,
            executor_path=str(executor_path),
            has_io_contract=has_io_contract,
            audit_name=audit_name,
            has_audit_executor=has_audit_executor,
            audit_executor_path=str(audit_executor_path),
            required_formal_output=required_formal_output,
            message=f"{skill_name} 缺少正式输入输出合同，不能执行 {task_name}。",
        )

    if required_formal_output and not has_audit_executor:
        return GateResult(
            status="blocked_missing_audit_executor",
            agent_name=agent_name,
            task_name=task_name,
            skill_name=skill_name,
            skill_dir=str(skill_dir),
            skill_exists=skill_exists,
            has_skill_md=has_skill_md,
            has_readme=has_readme,
            has_executor=has_executor,
            executor_path=str(executor_path),
            has_io_contract=has_io_contract,
            audit_name=audit_name,
            has_audit_executor=has_audit_executor,
            audit_executor_path=str(audit_executor_path),
            required_formal_output=required_formal_output,
            message=f"{audit_name} 没有正式审核执行器，不能放行 {task_name}。",
        )

    return GateResult(
        status="allowed",
        agent_name=agent_name,
        task_name=task_name,
        skill_name=skill_name,
        skill_dir=str(skill_dir),
        skill_exists=skill_exists,
        has_skill_md=has_skill_md,
        has_readme=has_readme,
        has_executor=has_executor,
        executor_path=str(executor_path),
        has_io_contract=has_io_contract,
        audit_name=audit_name,
        has_audit_executor=has_audit_executor,
        audit_executor_path=str(audit_executor_path),
        required_formal_output=required_formal_output,
        message=f"{skill_name} 与 {audit_name} 审核执行器齐备，允许进入 {task_name}。",
    )


def write_gate_result(path: Path, result: GateResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_gate_results(results: Iterable[GateResult]) -> dict:
    rows = [item.to_dict() for item in results]
    blocked = [item for item in rows if item["status"] != "allowed"]
    return {
        "allowed": len(blocked) == 0,
        "blocked_count": len(blocked),
        "results": rows,
    }


def write_gate_markdown(path: Path, summary: dict, *, title: str, task_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocked = [item for item in summary.get("results", []) if item.get("status") != "allowed"]
    lines = [
        "# 小姜门禁检查结果",
        "",
        f"- 任务：{task_name}",
        f"- 对象：{title}",
        f"- 结论：{'允许执行' if summary.get('allowed') else '门禁拦截'}",
        "",
        "## 检查结果",
        "",
    ]
    for item in summary.get("results", []):
        lines += [
            f"### {item.get('skill_name')}",
            "",
            f"- 状态：{item.get('status')}",
            f"- 执行 Agent：{item.get('agent_name')}",
            f"- Skill 执行器：{item.get('executor_path')}",
            f"- 是否存在执行器：{'是' if item.get('has_executor') else '否'}",
            f"- 是否存在输入输出合同：{'是' if item.get('has_io_contract') else '否'}",
            f"- 审核 Agent：{item.get('audit_name')}",
            f"- 是否存在审核执行器：{'是' if item.get('has_audit_executor') else '否'}",
            f"- 说明：{item.get('message')}",
            "",
        ]
    if blocked:
        lines += [
            "## 当前不能继续的原因",
            "",
        ]
        for item in blocked:
            lines.append(f"- {item.get('skill_name')}：{item.get('message')}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
