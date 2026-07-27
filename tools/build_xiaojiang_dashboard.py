from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from sync_public_templates import sync_public_templates


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "02_资产中心" / "01_原始知识库"
RAW_LEDGER = ROOT / "02_资产中心" / "01_原始知识库" / "00_原始资料输入清单.md"
BENCHMARK_ROOT = ROOT / "02_资产中心" / "03_对标账号库"
TOPIC_ROOT = ROOT / "02_资产中心" / "04_爆款选题库"
OPENING_ROOT = ROOT / "02_资产中心" / "05_爆款开头库"
BODY_ROOT = ROOT / "02_资产中心" / "06_生成正文库" / "01_干货型文案"
DRAFT_ROOT = ROOT / "02_资产中心" / "07_润色成稿库" / "01_干货型成稿"
VISUAL_ROOT = ROOT / "02_资产中心" / "08_视觉配图库" / "01_干货型配图"
AUDIT_DIR = ROOT / "01_Agent系统" / "02_小审-质量审核Agent" / "99_审核记录"
GATE_FAILURE_DIR = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent" / "门禁失败事项"
WORK_STATE = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent" / "01_工作记忆" / "当前推进状态.md"
NEXT_STEP = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent" / "01_工作记忆" / "下一步建议.md"
OUT = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent" / "00_小姜工作台.md"


def parse_table(md_path: Path) -> list[dict[str, str]]:
    if not md_path.exists():
        return []
    lines = md_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        if all(not cell or set(cell) <= {"-"} for cell in cells):
            continue
        if headers is None:
            headers = cells
            continue
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        if all(set(value) <= {"-"} for value in row.values()):
            continue
        rows.append(row)
    return rows


def load_baokuan_topic_rows(topic_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not topic_root.exists():
        return rows
    for path in sorted(topic_root.glob("*选题表.md")):
        if path.name == "00_手动输入选题表.md":
            continue
        rows.extend(parse_table(path))
    return rows


def extract_action_lines(md_path: Path, limit: int = 3) -> list[str]:
    if not md_path.exists():
        return []
    lines = md_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            out.append(stripped[2:].strip())
        elif re.match(r"^\d+\.\s+", stripped):
            out.append(re.sub(r"^\d+\.\s+", "", stripped))
        if len(out) >= limit:
            break
    return out


def load_gate_failures(limit: int = 5) -> list[dict]:
    if not GATE_FAILURE_DIR.exists():
        return []
    items: list[tuple[float, dict]] = []
    for path in GATE_FAILURE_DIR.glob("*.json"):
        try:
            import json

            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        items.append((path.stat().st_mtime, payload))
    items.sort(key=lambda x: x[0], reverse=True)
    return [payload for _, payload in items[:limit]]


def count_files(root: Path, pattern: str) -> int:
    if not root.exists():
        return 0
    return sum(1 for _ in root.glob(pattern))


def read_raw_rows() -> list[dict[str, str]]:
    return parse_table(RAW_LEDGER)


def scan_uploaded_raw_files() -> list[Path]:
    if not RAW_ROOT.exists():
        return []
    ignored_root_files = {"00_原始资料输入清单.md", "00_原始资料输入清单模板.md", "README.md"}
    files: list[Path] = []
    for path in RAW_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if "99_我的工作纪实" in path.parts:
            continue
        if path.parent == RAW_ROOT and path.name in ignored_root_files:
            continue
        files.append(path)
    return files


def scan_unregistered_raw_files(uploaded_files: list[Path], raw_rows: list[dict[str, str]]) -> list[Path]:
    registered_paths: set[str] = set()
    for row in raw_rows:
        raw_path = row.get("原始资料文件路径", "").strip().strip("`").replace("/", "\\")
        if raw_path:
            registered_paths.add(raw_path.lower())

    unregistered: list[Path] = []
    for path in uploaded_files:
        relative = path.relative_to(ROOT / "02_资产中心").as_posix().replace("/", "\\").lower()
        if relative not in registered_paths:
            unregistered.append(path)
    return sorted(unregistered)


def top_level_raw_bucket(path: Path) -> str:
    try:
        rel_parts = path.relative_to(RAW_ROOT).parts
    except ValueError:
        return "未分类"
    if len(rel_parts) >= 2:
        return f"{rel_parts[0]}/{rel_parts[1]}"
    if rel_parts:
        return rel_parts[0]
    return "未分类"


def read_hand_topic_rows() -> list[dict[str, str]]:
    return parse_table(TOPIC_ROOT / "00_手动输入选题表.md")


def scan_benchmark_accounts() -> list[str]:
    if not BENCHMARK_ROOT.exists():
        return []
    return sorted(path.stem for path in BENCHMARK_ROOT.glob("*.xlsx"))


def scanned_topic_accounts(rows: list[dict[str, str]]) -> set[str]:
    done: set[str] = set()
    for row in rows:
        name = row.get("博主名", "").strip()
        if name and set(name) != {"-"}:
            done.add(name)
    return done


def parse_opening_selection_rows() -> list[dict[str, str]]:
    return parse_table(OPENING_ROOT / "00_爆款开头选中清单.md")


def opening_card_rows() -> list[Path]:
    if not OPENING_ROOT.exists():
        return []
    return sorted(path for path in OPENING_ROOT.glob("BK*.md") if path.is_file())


def summarize_generation(rows: list[dict[str, str]]) -> dict[str, object]:
    total = len(rows)
    pending_body = [row for row in rows if row.get("正文状态", "").strip() != "已生成"]
    pending_draft = [
        row for row in rows
        if row.get("正文状态", "").strip() == "已生成"
        and row.get("成稿状态", "").strip() != "已生成"
    ]
    pending_visual = [
        row for row in rows
        if row.get("成稿状态", "").strip() == "已生成"
        and row.get("视觉状态", "").strip() != "已生成"
    ]
    return {
        "total": total,
        "pending_body": pending_body,
        "pending_draft": pending_draft,
        "pending_visual": pending_visual,
    }


def build() -> str:
    raw_rows = read_raw_rows()
    uploaded_raw_files = scan_uploaded_raw_files()
    unregistered_raw_files = scan_unregistered_raw_files(uploaded_raw_files, raw_rows)
    registered_raw_count = len(raw_rows)
    pending_raw = [r for r in raw_rows if r.get("当前状态", "").strip() == "未拆解"]
    done_raw = [r for r in raw_rows if r.get("当前状态", "").strip() == "已拆解"]
    unregistered_raw_count = len(unregistered_raw_files)
    raw_type_counter = Counter(r.get("资料类型", "未分类") for r in pending_raw)

    benchmark_accounts = scan_benchmark_accounts()
    topic_rows = load_baokuan_topic_rows(TOPIC_ROOT)
    done_accounts = scanned_topic_accounts(topic_rows)
    pending_accounts = [name for name in benchmark_accounts if name not in done_accounts]

    opening_selection_rows = parse_opening_selection_rows()
    pending_openings = [row for row in opening_selection_rows if row.get("状态", "").strip() == "待拆解"]
    opening_cards = opening_card_rows()

    hand_rows = read_hand_topic_rows()
    generation = summarize_generation(hand_rows)

    recent_audits = []
    if AUDIT_DIR.exists():
        recent_audits = sorted(
            [p for p in AUDIT_DIR.glob("*.md") if "模板" not in p.name],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:8]

    recent_gate_failures = load_gate_failures()
    current_state_excerpt = extract_action_lines(WORK_STATE, limit=4)
    next_actions = extract_action_lines(NEXT_STEP, limit=4)

    body_file_count = count_files(BODY_ROOT, "*.md")
    draft_file_count = count_files(DRAFT_ROOT, "*.md")
    visual_topic_dir_count = sum(1 for p in VISUAL_ROOT.iterdir() if p.is_dir()) if VISUAL_ROOT.exists() else 0

    lines: list[str] = [
        "# 小姜工作台",
        "",
        "这是你以后问“小姜，我接下来还有什么要做”的唯一正式入口。",
        "",
        "## 1. 待拆解内容",
        "",
        "### A. 原始资料 -> 内容模块",
        "",
        f"- 已上传原始资料文件数：{len(uploaded_raw_files)}",
        f"- 已登记输入清单条目数：{registered_raw_count}",
        f"- 未登记输入清单文件数：{unregistered_raw_count}",
        f"- 待拆解原始资料条目数：{len(pending_raw)}",
        f"- 已拆解原始资料数：{len(done_raw)}",
    ]

    if raw_type_counter:
        lines.append("- 待拆解资料类型分布：")
        for key, value in raw_type_counter.items():
            lines.append(f"  - {key}：{value}")

    if pending_raw:
        lines += ["", "#### 待拆解原始资料明细", ""]
        for row in pending_raw[:12]:
            lines.append(
                f"- {row.get('资料标题','未命名')}｜{row.get('作者/来源主体','未知来源')}｜{row.get('资料类型','未分类')}"
            )

    if unregistered_raw_files:
        lines += ["", "#### 未登记原始资料明细", ""]
        for path in unregistered_raw_files[:20]:
            lines.append(f"- {path.name}｜{top_level_raw_bucket(path)}")

    lines += [
        "",
        "### B. 对标账号 -> 爆款选题",
        "",
        f"- 已输入对标账号表数：{len(benchmark_accounts)}",
        f"- 已完成选题分类账号表数：{len(done_accounts)}",
        f"- 待分类账号表数：{len(pending_accounts)}",
    ]

    if pending_accounts:
        lines += ["", "#### 待分类账号表明细", ""]
        for name in pending_accounts[:12]:
            lines.append(f"- {name}.xlsx")

    lines += [
        "",
        "### C. 对标账号 -> 爆款开头",
        "",
        f"- 已选中待拆解开头数：{len(pending_openings)}",
        f"- 已生成 BK 开头卡片数：{len(opening_cards)}",
    ]

    if pending_openings:
        lines += ["", "#### 待拆解开头明细", ""]
        for row in pending_openings[:12]:
            lines.append(
                f"- {row.get('博主名','未知博主')}｜{row.get('视频信息','未填视频信息') or '未填视频信息'}｜{row.get('链接','无链接')}"
            )

    lines += [
        "",
        "## 2. 待生成内容",
        "",
        f"- 手动输入选题总数：{generation['total']}",
        f"- 已生成正文文件数：{body_file_count}",
        f"- 已生成成稿文件数：{draft_file_count}",
        f"- 已生成视觉主题目录数：{visual_topic_dir_count}",
        "",
        "### A. 待生成正文",
        "",
        f"- 待生成正文数：{len(generation['pending_body'])}",
    ]

    if generation["pending_body"]:
        lines += ["", "#### 待生成正文明细", ""]
        for row in generation["pending_body"][:12]:
            lines.append(f"- {row.get('选题','未命名选题')}｜{row.get('文案结构','未分类')}")

    lines += [
        "",
        "### B. 待生成成稿",
        "",
        f"- 待生成成稿数：{len(generation['pending_draft'])}",
    ]

    if generation["pending_draft"]:
        lines += ["", "#### 待生成成稿明细", ""]
        for row in generation["pending_draft"][:12]:
            lines.append(f"- {row.get('选题','未命名选题')}｜{row.get('文案结构','未分类')}")

    lines += [
        "",
        "### C. 待生成视觉",
        "",
        f"- 待生成视觉数：{len(generation['pending_visual'])}",
    ]

    if generation["pending_visual"]:
        lines += ["", "#### 待生成视觉明细", ""]
        for row in generation["pending_visual"][:12]:
            lines.append(f"- {row.get('选题','未命名选题')}｜{row.get('文案结构','未分类')}")

    lines += ["", "## 3. 当前待审核事项", ""]
    if recent_audits:
        for path in recent_audits:
            lines.append(f"- {path.name}")
    else:
        lines.append("- 当前没有可读取的真实审核记录。")

    if recent_gate_failures:
        lines += ["", "### 当前门禁失败事项", ""]
        for item in recent_gate_failures:
            blocked = [row for row in item.get("results", []) if row.get("status") != "allowed"]
            if not blocked:
                continue
            first = blocked[0]
            lines.append(
                f"- 被拦任务：{first.get('task_name','未知任务')}｜原因：{first.get('status','未知状态')}｜说明：{first.get('message','')}"
            )

    lines += ["", "## 4. 小姜下一步建议", ""]
    if next_actions:
        for item in next_actions:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前没有单独建议，优先处理待拆解和待生成事项。")

    if current_state_excerpt:
        lines += ["", "### 当前推进状态摘要", ""]
        for item in current_state_excerpt:
            lines.append(f"- {item}")

    lines += [
        "",
        "---",
        "",
        "品牌尾注：",
        "",
        "- 带你用AI，把你的能力变成你的生意。",
        "- AI流量团队作者：姜来已来2046",
        "- 有任何使用问题，可以联系我！微信： lact175",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sync_public_templates()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(OUT)
