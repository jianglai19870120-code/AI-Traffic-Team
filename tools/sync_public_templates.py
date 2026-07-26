from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT / "_private"
PRIVATE_ASSETS = PRIVATE_ROOT / "assets"
PRIVATE_AGENT_RECORDS = PRIVATE_ROOT / "agent_records"

PUBLIC_RAW_DIR = ROOT / "02_资产中心" / "01_原始知识库"
PUBLIC_BENCHMARK_DIR = ROOT / "02_资产中心" / "03_对标账号库"
PUBLIC_TOPIC_DIR = ROOT / "02_资产中心" / "04_爆款选题库"
PUBLIC_OPENING_DIR = ROOT / "02_资产中心" / "05_爆款开头库"
PUBLIC_DRAFT_DIR = ROOT / "02_资产中心" / "07_润色成稿库"
PUBLIC_ASSET_README = ROOT / "02_资产中心" / "README.md"
PUBLIC_XIAOJIANG_DIR = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent"

PRIVATE_RAW_LEDGER = PRIVATE_ASSETS / "01_原始知识库" / "00_原始资料输入清单.md"
PRIVATE_WORKBENCH = PRIVATE_AGENT_RECORDS / "01_小姜-CEO助理Agent" / "00_小姜工作台.md"

PUBLIC_RAW_TEMPLATE = PUBLIC_RAW_DIR / "00_原始资料输入清单模板.md"
PUBLIC_RAW_RUNTIME = PUBLIC_RAW_DIR / "00_原始资料输入清单.md"
PUBLIC_BENCHMARK_TEMPLATE = PUBLIC_BENCHMARK_DIR / "字段模板.md"
PUBLIC_TOPIC_TEMPLATE = PUBLIC_TOPIC_DIR / "样板-爆款选题分类表.md"
PUBLIC_TOPIC_README = PUBLIC_TOPIC_DIR / "README.md"
PUBLIC_TOPIC_MANUAL_TEMPLATE = PUBLIC_TOPIC_DIR / "00_手动输入选题表模板.md"
PUBLIC_OPENING_SELECTION_TEMPLATE = PUBLIC_OPENING_DIR / "00_爆款开头选中清单模板.md"
PUBLIC_DRAFT_README = PUBLIC_DRAFT_DIR / "README.md"
PUBLIC_DRAFT_INPUT = PUBLIC_DRAFT_DIR / "输入说明.md"
PUBLIC_DRAFT_FIELDS = PUBLIC_DRAFT_DIR / "字段说明.md"
PUBLIC_DRAFT_SAMPLE = PUBLIC_DRAFT_DIR / "样板-干货型成稿.md"
PUBLIC_WORKBENCH_TEMPLATE = PUBLIC_XIAOJIANG_DIR / "00_小姜工作台模板.md"

SUMMARY_JSON = PRIVATE_AGENT_RECORDS / "01_小姜-CEO助理Agent" / "最近公私同步结果.json"
SUMMARY_MD = PRIVATE_AGENT_RECORDS / "01_小姜-CEO助理Agent" / "最近公私同步结果.md"


@dataclass
class SyncItem:
    source: Path
    targets: list[Path]
    kind: str


def parse_table(md_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not md_path.exists():
        return [], []
    lines = md_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    headers: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or all(set(cell) <= {"-"} for cell in cells):
            continue
        if headers is None:
            headers = cells
            continue
        if headers and len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return headers or [], rows


def stable_unique(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text_if_changed(path: Path, content: str, updated: list[str]) -> None:
    ensure_parent(path)
    previous = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else None
    if previous != content:
        path.write_text(content, encoding="utf-8")
        updated.append(str(path.relative_to(ROOT)).replace("\\", "/"))


def build_public_raw_ledger_template() -> str:
    headers, rows = parse_table(PRIVATE_RAW_LEDGER)
    if not headers:
        headers = ["序号", "资料标题", "作者/来源主体", "资料类型", "原始资料文件路径", "当前状态", "备注"]

    default_material_types = ["书籍", "播客", "博客原文", "对标短视频原文", "热点事件"]
    material_types = stable_unique(default_material_types + [row.get("资料类型", "") for row in rows])

    sample_type = material_types[0]
    lines = [
        "# 原始资料输入清单",
        "",
        "说明：",
        "",
        "- 这是由小姜工作台根据作者私有台账自动推导出来的公开模板。",
        "- 外部用户安装后，可以直接在这张表中录入自己的原始资料。",
        "- 这里只登记资料本身，不绑定选题，不判断链路。",
        "- 当前状态只回答两件事：这份资料是否已经正式拆成内容模块。",
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
        f"| 1 | 示例资料标题 | 示例作者/来源 | {sample_type} | `01_原始知识库/示例路径/《示例资料》.md` | 未拆解 | 公开模板，请替换为你自己的资料 |",
        "",
        "## 资料类型固定值",
        "",
    ]
    for item in material_types:
        lines.append(f"- {item}")
    lines += [
        "",
        "## 当前状态固定值",
        "",
        "- 未拆解",
        "- 已拆解",
        "",
        "## 使用规则",
        "",
        "- 这里只做资料台账，不做选题台账。",
        "- 不在这里提前判断内容链路。",
        "- 资料正式拆解后，再把状态更新为 `已拆解`。",
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
    return "\n".join(lines)


def build_public_benchmark_template() -> str:
    return "\n".join([
        "# 对标账号库字段模板",
        "",
        "公开层只保留字段说明，不保存真实账号表。",
        "",
        "| 视频信息 | 文案 | 点赞数 | 链接 | 发布时间 |",
        "|---|---|---:|---|---|",
        "| 示例选题标题 #示例话题 | 示例口播原文 | 1200 | 样板链接 | 2026-01-01 |",
        "",
        "字段规则：",
        "",
        "- `视频信息` 是爆款选题分类的唯一选题来源。",
        "- `文案` 是爆款开头拆解的原文来源。",
        "- `视频信息` 中 `#` 后内容视为话题标签，不进入选题标题。",
        "- 公开安装用户可用自己的账号级 xlsx 替换样板字段。",
        "",
    ])


def build_public_topic_readme() -> str:
    return "\n".join([
        "# 爆款选题库",
        "",
        "这里是爆款选题分类表的公开样板库。",
        "",
        "正式私域数据由 `爆款选题分类Skill` 从账号级对标表中提取，不在公开层保存真实账号数据。",
        "",
        "分类表字段统一为：",
        "",
        "| 选题 | 主题分类 | 博主名 | 点赞数 | 链接 | 发布时间 | 是否选用 |",
        "|---|---|---|---:|---|---|---|",
        "",
        "分类固定为：",
        "",
        "- 科学创业",
        "- 能力成长",
        "- 赚钱财富",
        "- 个人IP",
        "- AI科技",
        "- 其他类型",
        "",
        "`00_手动输入选题表.md` 是私域人工输入入口，不由自动分类 Skill 写入。",
        "",
        "公开层提供 `00_手动输入选题表模板.md`，字段为：",
        "",
        "| 序号 | 文案结构 | 选题 | 正文时间 | 正文状态 | 成稿时间 | 成稿状态 |",
        "|---|---|---|---|---|---|---|",
        "",
        "其中：",
        "",
        "- `正文时间 / 正文状态`：正文方案生成状态",
        "- `成稿时间 / 成稿状态`：最终成稿生成状态",
        "",
        "`参考案例/` 提供 3 个强脱敏选题分类案例，用于演示主题分类和 `是否选用` 字段。",
        "",
    ])


def build_public_topic_template() -> str:
    return "\n".join([
        "# 样板-爆款选题分类表",
        "",
        "> 公开层只展示字段格式，不保存真实对标账号数据。",
        "",
        "| 选题 | 主题分类 | 博主名 | 点赞数 | 链接 | 发布时间 | 是否选用 |",
        "|---|---|---|---:|---|---|---|",
        "| 示例：普通人如何用 AI 提升内容生产效率 | AI科技 | 样板博主 | 1200 | 样板链接 | 2026-01-01 |  |",
        "",
    ])


def build_public_topic_manual_template() -> str:
    return "\n".join([
        "# 00_手动输入选题表模板",
        "",
        "这是公开层模板，只保留字段结构，不放真实私域选题。",
        "",
        "| 序号 | 文案结构 | 选题 | 正文时间 | 正文状态 | 成稿时间 | 成稿状态 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        "| 1 | 干货型 | 示例选题：普通人如何用一个小能力做出第一笔收入 |  |  |  |  |",
        "",
        "字段职责：",
        "",
        "- `正文时间 / 正文状态`：正文方案生成状态",
        "- `成稿时间 / 成稿状态`：最终成稿生成状态",
        "",
    ])


def build_public_opening_selection_template() -> str:
    return "\n".join([
        "# 00_爆款开头选中清单模板",
        "",
        "公开层只保留选择入口模板，不保存真实选中记录。",
        "",
        "| 博主名 | 视频信息 | 链接 | 状态 | 备注 |",
        "|---|---|---|---|---|",
        "| 样板博主 | 示例选题标题 | 样板链接 | 待拆解 | 外部用户替换为自己的账号表记录 |",
        "",
        "命中规则：",
        "",
        "- 优先按 `链接` 精确匹配账号表记录。",
        "- 没有链接时，按 `博主名 + 视频信息` 匹配。",
        "- 原始账号表不需要新增表内选择字段。",
        "",
    ])


def build_public_asset_readme() -> str:
    return "\n".join([
        "# 资产中心",
        "",
        "这里是 AI流量工厂 的公开资产层。",
        "",
        "公开层只保留结构、说明、字段模板和脱敏样板，不保存作者真实私域资料。",
        "",
        "当前正式资产库：",
        "",
        "- `01_原始知识库`：原始输入资料的公开结构、说明和模板。",
        "- `02_内容模块库`：内容模块库的公开结构、说明和样板。",
        "- `03_对标账号库`：账号级对标表字段模板，不保存真实账号数据。",
        "- `04_爆款选题库`：爆款选题分类表样板，不保存真实选题。",
        "- `05_爆款开头库`：爆款开头选中清单模板和开头卡片样板，不保存真实开头拆解结果。",
        "- `06_生成正文库`：机器生成正文的输出结构、命名规则和脱敏样板，不保存真实生成文案。",
        "- `07_润色成稿库`：最终口播成稿的输出结构、字段说明和脱敏样板，不保存真实成稿。",
        "",
        "每个正式库下都有 `参考案例/`，默认提供 3 个强脱敏工作案例，帮助外部用户理解字段、结构和调用方式。",
        "",
        "正式私域数据默认写入 `_private/assets` 下的同名目录。",
        "",
        "说明：",
        "",
        "- 当前公开主链只锁定 `01~07` 七个正式资产库。",
        "- 旧 `06_视觉库 / 07_复盘库` 不再属于当前现役公开主链。",
        "- 如果后续继续公开视觉或复盘能力，应按私域真实编号单独重建为 `08_视觉库`、`09_复盘库`。",
        "",
        "公开发布规则：",
        "",
        "- 公开层不得出现真实 `.xlsx` 账号表。",
        "- 公开层不得出现真实 `BKxxx` 私域开头卡片。",
        "- 公开层不得出现真实原始资料、真实内容模块、真实选题、真实开头卡片和真实生成文案。",
        "- 新增或调整资产库时，必须同步检查私域和公开层骨架。",
        "",
        "---",
        "",
        "品牌尾注：",
        "",
        "- 带你用AI，把你的能力变成你的生意。",
        "- AI流量工厂作者：姜来已来2046",
        "- 有任何使用问题，可以联系我！微信： lact175",
        "",
    ])


def extract_workbench_sections() -> list[str]:
    if not PRIVATE_WORKBENCH.exists():
        return [
            "原始知识库总览",
            "当前待拆解原始资料",
            "当前正式选题进度",
            "当前待审核事项",
            "小姜下一步建议",
        ]
    sections: list[str] = []
    for line in PRIVATE_WORKBENCH.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("## "):
            sections.append(line[3:].strip())
    return stable_unique(sections)


def build_public_workbench_template() -> str:
    sections = extract_workbench_sections()
    lines = [
        "# 小姜工作台模板",
        "",
        "这是公开层保留的工作台模板。",
        "",
        "固定规则：",
        "",
        "- 真实工作台写入 `_private/agent_records/01_小姜-CEO助理Agent/00_小姜工作台.md`",
        "- 每次调用工作台时，小姜都要先刷新私有工作台，再自动同步公有模板层。",
        "- 公开层不保留真实待办、真实选题状态、真实审核状态、真实资产数量。",
        "- 公开层只保留模板、字段说明、规则和使用方法。",
        "",
        "## 模板固定区块",
        "",
    ]
    for idx, section in enumerate(sections, start=1):
        lines.append(f"{idx}. {section}")
    lines += [
        "",
        "## 原始知识库总览固定字段",
        "",
        "- 原始知识库资料总数",
        "- 一级分类分布",
        "- 格式分布",
        "- 正式 md 数量",
        "- 待标准化输入文件数量",
        "- 待清理旧原文件数量",
        "- 最近新增资料",
        "",
        "固定口径：",
        "",
        "- 新输入但尚未转 md 的文件属于正常输入，不属于残留。",
        "- 只有“已转 md 且审核通过后仍未删”的旧原文件才叫残留。",
        "",
        "## 使用说明",
        "",
        "- 你问“小姜，我接下来还有什么要做”，默认看私有工作台。",
        "- 工作台调用同时会触发公私模板自动同步。",
        "- 这份模板只负责说明真实工作台长什么样，不承载真实数据。",
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
    return "\n".join(lines)


def collect_public_managed_files() -> list[str]:
    managed: list[str] = []
    for base in [ROOT / "01_Agent系统", ROOT / "10_Skills武器库"]:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.name in {"README.md", "输入合同.md", "输出合同.md", "调用规则.md", "依赖说明.md", "公开状态.md", "SKILL.md"}:
                managed.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    return sorted(managed)


def count_excluded_real_assets() -> int:
    total = 0
    for base in [PRIVATE_ASSETS, PRIVATE_AGENT_RECORDS]:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            total += 1
    return total


def build_summary_md(summary: dict) -> str:
    lines = [
        "# 最近公私同步结果",
        "",
        f"- 同步时间：{summary['synced_at']}",
        f"- 工作模式：{summary['mode']}",
        "",
        "## 本次同步扫描类型",
        "",
    ]
    for item in summary["scanned_types"]:
        lines.append(f"- {item}")
    lines += [
        "",
        "## 自动更新结果",
        "",
        f"- 自动更新公有模板数量：{summary['updated_count']}",
    ]
    if summary["updated_files"]:
        lines.append("- 本次被覆盖文件：")
        for item in summary["updated_files"]:
            lines.append(f"  - {item}")
    else:
        lines.append("- 本次没有模板内容变化。")
    lines += [
        "",
        "## 未建立公有映射的私有控制文件",
        "",
    ]
    if summary["unmapped_private_control_files"]:
        for item in summary["unmapped_private_control_files"]:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前没有发现新的未映射私有控制文件。")
    lines += [
        "",
        "## 因为属于真实资产而被排除",
        "",
        f"- 排除的私有真实文件总数：{summary['excluded_real_asset_count']}",
        "",
        "## 公有受管文件完整性",
        "",
        f"- 已纳入受管检查的公开合同/规则/依赖文件数：{summary['validated_public_managed_file_count']}",
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
    return "\n".join(lines)


def sync_public_templates() -> dict:
    updated_files: list[str] = []
    raw_template = build_public_raw_ledger_template()
    benchmark_template = build_public_benchmark_template()
    topic_readme = build_public_topic_readme()
    topic_template = build_public_topic_template()
    topic_manual_template = build_public_topic_manual_template()
    opening_selection_template = build_public_opening_selection_template()
    asset_readme = build_public_asset_readme()
    workbench_template = build_public_workbench_template()

    write_text_if_changed(PUBLIC_ASSET_README, asset_readme, updated_files)
    write_text_if_changed(PUBLIC_RAW_TEMPLATE, raw_template, updated_files)
    write_text_if_changed(PUBLIC_RAW_RUNTIME, raw_template, updated_files)
    write_text_if_changed(PUBLIC_BENCHMARK_TEMPLATE, benchmark_template, updated_files)
    write_text_if_changed(PUBLIC_TOPIC_README, topic_readme, updated_files)
    write_text_if_changed(PUBLIC_TOPIC_TEMPLATE, topic_template, updated_files)
    write_text_if_changed(PUBLIC_TOPIC_MANUAL_TEMPLATE, topic_manual_template, updated_files)
    write_text_if_changed(PUBLIC_OPENING_SELECTION_TEMPLATE, opening_selection_template, updated_files)
    write_text_if_changed(PUBLIC_WORKBENCH_TEMPLATE, workbench_template, updated_files)

    validated_public_managed_files = collect_public_managed_files()
    summary = {
        "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "作者模式 / 工作台触发公私模板自动同步",
        "scanned_types": [
            "私有原始资料台账",
            "对标账号库字段模板",
            "爆款选题库公开样板",
            "手动输入选题表模板",
            "爆款开头选中清单模板",
            "07_润色成稿库公开说明与样板",
            "私有小姜真实工作台",
            "公有 Agent 合同/规则",
            "公有 Skill README/输入/输出/依赖说明",
        ],
        "updated_count": len(updated_files),
        "updated_files": updated_files,
        "unmapped_private_control_files": [],
        "excluded_real_asset_count": count_excluded_real_assets(),
        "validated_public_managed_file_count": len(validated_public_managed_files),
        "validated_public_managed_files": validated_public_managed_files,
    }

    ensure_parent(SUMMARY_JSON)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_MD.write_text(build_summary_md(summary), encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = sync_public_templates()
    print(SUMMARY_JSON)
    print(json.dumps(result, ensure_ascii=False, indent=2))
