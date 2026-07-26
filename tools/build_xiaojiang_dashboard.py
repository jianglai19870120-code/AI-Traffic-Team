from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from sync_public_templates import SUMMARY_JSON, sync_public_templates


ROOT = Path(__file__).resolve().parents[1]
RAW_LEDGER = ROOT / "_private" / "assets" / "01_原始知识库" / "00_原始资料输入清单.md"
RAW_LIBRARY = ROOT / "_private" / "assets" / "01_原始知识库" / "01_好书原始资料"
TOPIC_ROOT = ROOT / "_private" / "assets" / "04_爆款选题库"
AUDIT_DIR = ROOT / "_private" / "agent_records" / "02_小审-质量审核Agent" / "审核记录"
GATE_FAILURE_DIR = ROOT / "_private" / "agent_records" / "01_小姜-CEO助理Agent" / "门禁失败事项"
WORK_STATE = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent" / "01_工作记忆" / "当前推进状态.md"
NEXT_STEP = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent" / "01_工作记忆" / "下一步建议.md"
OUT = ROOT / "_private" / "agent_records" / "01_小姜-CEO助理Agent" / "00_小姜工作台.md"


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
        if not cells or all(set(cell) <= {"-"} for cell in cells):
            continue
        if headers is None:
            headers = cells
            continue
        if headers and len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def load_baokuan_topic_rows(topic_root: Path) -> list[dict[str, str]]:
    if not topic_root.exists():
        return []
    rows: list[dict[str, str]] = []
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


def load_sync_summary() -> dict | None:
    if not SUMMARY_JSON.exists():
        return None
    try:
        import json

        return json.loads(SUMMARY_JSON.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


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


def parse_md_title(md_path: Path) -> str:
    name = md_path.stem.strip()
    m = re.match(r"^《(?P<title>.+?)》$", name)
    if m:
        return m.group("title").strip()
    return name.strip("《》").strip()


def parse_source_title(file_path: Path) -> str:
    stem = file_path.stem.strip()
    m = re.match(r"^《(?P<title>.+?)》(?P<rest>.*)$", stem)
    if m:
        return m.group("title").strip()
    parts = re.split(r"[-_—｜|]+", stem)
    return parts[0].strip() if parts else stem


def build_cleanup_allowed_md_paths(audit_dir: Path) -> set[str]:
    allowed: set[str] = set()
    if not audit_dir.exists():
        return allowed
    for path in sorted(audit_dir.glob("*.md")):
        if "模板" in path.name:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.findall(r"通过：`([^`]+)`", text):
            allowed.add(match.replace("\\", "/"))
    return allowed


def scan_raw_library(
    root: Path,
    cleanup_allowed_md_paths: set[str],
) -> tuple[int, Counter[str], Counter[str], int, int, list[str]]:
    total = 0
    by_category: Counter[str] = Counter()
    by_ext: Counter[str] = Counter()
    recent: list[tuple[float, str]] = []
    if not root.exists():
        return total, by_category, by_ext, 0, 0, []

    md_titles_by_dir: dict[str, set[str]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        total += 1
        by_category[path.parent.name] += 1
        ext = path.suffix.lower() or "无后缀"
        by_ext[ext] += 1
        recent.append((path.stat().st_mtime, path.name))
        if ext == ".md":
            key = str(path.parent).replace("\\", "/")
            md_titles_by_dir.setdefault(key, set()).add(parse_md_title(path))

    pending_input_count = 0
    cleanup_pending_count = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        ext = path.suffix.lower() or "无后缀"
        if ext == ".md":
            continue

        dir_key = str(path.parent).replace("\\", "/")
        source_title = parse_source_title(path)
        expected_md = f"{dir_key}/《{source_title}》.md"

        if source_title not in md_titles_by_dir.get(dir_key, set()):
            pending_input_count += 1
            continue

        if expected_md in cleanup_allowed_md_paths:
            cleanup_pending_count += 1
        else:
            pending_input_count += 1

    recent.sort(reverse=True)
    recent_names = [name for _, name in recent[:8]]
    return total, by_category, by_ext, pending_input_count, cleanup_pending_count, recent_names


def build() -> str:
    raw_rows = parse_table(RAW_LEDGER)
    topic_rows = load_baokuan_topic_rows(TOPIC_ROOT)
    cleanup_allowed_md_paths = build_cleanup_allowed_md_paths(AUDIT_DIR)
    raw_total, raw_by_category, raw_by_ext, pending_input_count, cleanup_pending_count, recent_raw_files = scan_raw_library(
        RAW_LIBRARY,
        cleanup_allowed_md_paths,
    )

    pending_raw = [r for r in raw_rows if r.get("当前状态") == "未拆解"]
    done_raw = [r for r in raw_rows if r.get("当前状态") == "已拆解"]
    raw_by_type = Counter(r.get("资料类型", "未分类") for r in pending_raw)

    topic_counter = Counter(r.get("主题分类", "未分类") for r in topic_rows)
    active_topics = [r for r in topic_rows if r.get("是否选用", "").strip()]

    recent_audits = []
    if AUDIT_DIR.exists():
        recent_audits = sorted(
            [p for p in AUDIT_DIR.glob("*.md") if "模板" not in p.name],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:5]
    recent_gate_failures = load_gate_failures()

    current_state_excerpt = extract_action_lines(WORK_STATE, limit=3)
    next_actions = extract_action_lines(NEXT_STEP, limit=3)
    sync_summary = load_sync_summary()

    lines: list[str] = [
        "# 小姜工作台",
        "",
        "这是你以后问“小姜，我接下来还有什么要做”的唯一正式入口。",
        "",
        "## 1. 原始知识库总览",
        "",
        f"- 原始知识库资料总数：{raw_total}",
        f"- 正式 md 数量：{raw_by_ext.get('.md', 0)}",
        f"- 待标准化输入文件数量：{pending_input_count}",
        f"- 待清理旧原文件数量：{cleanup_pending_count}",
    ]

    if raw_by_category:
        lines.append("- 一级分类分布：")
        for key, value in raw_by_category.items():
            lines.append(f"  - {key}：{value}")
    else:
        lines.append("- 当前原始知识库还没有资料。")

    if raw_by_ext:
        lines.append("- 格式分布：")
        for key, value in raw_by_ext.items():
            lines.append(f"  - {key}：{value}")

    if recent_raw_files:
        lines += ["", "### 最近新增资料", ""]
        for item in recent_raw_files:
            lines.append(f"- {item}")
        lines += ["", "- 新输入但尚未转 md 的文件属于正常输入，不属于残留。"]

    lines += [
        "",
        "## 2. 当前待拆解原始资料",
        "",
        f"- 待拆解总数：{len(pending_raw)}",
        f"- 已拆解总数：{len(done_raw)}",
    ]

    if raw_by_type:
        lines.append("- 待拆解资料类型分布：")
        for key, value in raw_by_type.items():
            lines.append(f"  - {key}：{value}")
    else:
        lines.append("- 当前没有待拆解原始资料。")

    if pending_raw:
        lines += ["", "### 待拆解明细", ""]
        for row in pending_raw[:12]:
            lines.append(
                f"- {row.get('资料标题','未命名')}｜{row.get('作者/来源主体','未知来源')}｜{row.get('资料类型','未分类')}"
            )

    lines += [
        "",
        "## 3. 当前爆款选题库进度",
        "",
        f"- 当前分类选题总数：{len(topic_rows)}",
        f"- 当前已人工选用数：{len(active_topics)}",
    ]

    for category in ["科学创业", "能力成长", "赚钱财富", "个人IP", "AI科技", "其他类型"]:
        lines.append(f"- {category}：{topic_counter.get(category, 0)}")

    if active_topics:
        lines += ["", "### 当前人工选用选题", ""]
        for row in active_topics[:12]:
            lines.append(f"- {row.get('选题','未命名选题')}｜{row.get('主题分类','未分类')}｜{row.get('博主名','未知博主')}")

    lines += ["", "## 4. 当前待审核事项", ""]
    if recent_audits:
        for path in recent_audits:
            lines.append(f"- {path.name}")
    else:
        lines.append("- 当前没有可读取的真实审核记录。")

    lines += ["", "## 5. 当前门禁失败事项", ""]
    if recent_gate_failures:
        for item in recent_gate_failures:
            blocked = [row for row in item.get("results", []) if row.get("status") != "allowed"]
            if not blocked:
                continue
            first = blocked[0]
            lines.append(
                f"- 被拦任务：{first.get('task_name','未知任务')}｜原因：{first.get('status','未知状态')}｜说明：{first.get('message','')}"
            )
    else:
        lines.append("- 当前没有新的门禁失败事项。")

    lines += ["", "## 6. 小姜下一步建议", ""]
    if next_actions:
        for item in next_actions:
            lines.append(f"- {item}")
    else:
        lines.append("- 暂无单独建议，优先查看当前推进状态。")

    if current_state_excerpt:
        lines += ["", "### 当前推进状态摘要", ""]
        for item in current_state_excerpt:
            lines.append(f"- {item}")

    lines += ["", "## 7. 本次公私同步结果", ""]
    if sync_summary:
        lines.append(f"- 同步时间：{sync_summary.get('synced_at', '未知')}")
        lines.append(f"- 自动更新公有模板数量：{sync_summary.get('updated_count', 0)}")
        updated_files = sync_summary.get("updated_files", [])
        if updated_files:
            lines.append("- 本次被覆盖文件：")
            for item in updated_files[:12]:
                lines.append(f"  - {item}")
        else:
            lines.append("- 本次没有模板内容变化。")
        unmapped = sync_summary.get("unmapped_private_control_files", [])
        if unmapped:
            lines.append("- 仍未建立公有映射的私有控制文件：")
            for item in unmapped[:12]:
                lines.append(f"  - {item}")
        else:
            lines.append("- 当前没有新的未映射私有控制文件。")
        lines.append(f"- 因为属于真实资产而被排除的私有文件总数：{sync_summary.get('excluded_real_asset_count', 0)}")
        lines.append(f"- 已纳入受管检查的公开合同/规则/依赖文件数：{sync_summary.get('validated_public_managed_file_count', 0)}")
    else:
        lines.append("- 当前还没有可读取的公私同步结果。")

    lines += [
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


if __name__ == "__main__":
    sync_public_templates()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(OUT)
