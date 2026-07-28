from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from brand_footer import append_brand_footer
from sync_public_chain import sync_public_chain


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
CANDIDATE_ROOT = ROOT / "01_Agent系统" / "04_小拆-内容拆解Agent" / "99_执行记录" / "候选产物"
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
        if path.name == "00_爆款选题选中清单.md":
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


def extract_line_value(text: str, prefix: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def parse_int(text: str) -> int:
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else 0


def normalize_book_title(text: str) -> str:
    cleaned = text.strip().strip("`")
    cleaned = re.sub(r"\.md$", "", cleaned, flags=re.I)
    cleaned = cleaned.replace("三类干货模块", "").strip()
    match = re.search(r"《([^》]+)》", cleaned)
    if match:
        return match.group(1).strip()
    parts = re.split(r"[_\-—｜|]+", cleaned)
    return parts[0].strip() if parts else cleaned


def infer_audit_type(path: Path, text: str) -> str:
    explicit = extract_line_value(text, "- 审核类型：")
    if explicit:
        return explicit
    name = path.name
    if "撤销通过并退回" in name:
        return "正式模块撤销通过并退回"
    if "候选充分拆解审核" in name:
        return "候选充分拆解审核"
    if "正式充分拆解放行审核" in name:
        return "正式充分拆解放行审核"
    if "成稿放行审核" in name:
        return "成稿放行审核"
    if "机器文案放行审核" in name:
        return "机器文案放行审核"
    if "原始资料入库审核" in name:
        return "原始资料入库审核"
    if "工作纪实原文直拆审核" in name:
        return "工作纪实原文直拆审核"
    if "工作纪实内容模块审核" in name:
        return "工作纪实内容模块审核"
    if "工作纪实原子模块迁移审核" in name:
        return "工作纪实原子模块迁移审核"
    if "工作纪实四段式拆解审核" in name:
        return "工作纪实四段式拆解审核"
    if "同步入库审核" in name:
        return "同步入库审核"
    return "未知审核"


def infer_audit_status(text: str, audit_type: str) -> str:
    explicit = extract_line_value(text, "- 审核结论：")
    if explicit:
        if "部分退回" in explicit:
            return "部分退回"
        if "退回" in explicit:
            return "退回"
        if "通过" in explicit:
            return "通过"

    if "## 审核结论" in text:
        section = text.split("## 审核结论", 1)[1]
        section = section.split("\n## ", 1)[0]
        if "部分退回" in section:
            return "部分退回"
        if "退回" in section:
            return "退回"
        if "通过" in section:
            return "通过"

    if audit_type == "原始资料入库审核":
        passed = parse_int(extract_line_value(text, "- 通过数："))
        failed = parse_int(extract_line_value(text, "- 退回数："))
        if passed > 0 and failed > 0:
            return "部分退回"
        if failed > 0:
            return "退回"
        if passed > 0:
            return "通过"

    return "未知已完成"


def infer_audit_kind(audit_type: str) -> str:
    if audit_type == "机器文案放行审核":
        return "machine_draft"
    if audit_type == "成稿放行审核":
        return "final_draft"
    if audit_type in {
        "候选充分拆解审核",
        "正式充分拆解放行审核",
        "正式模块撤销通过并退回",
        "工作纪实原文直拆审核",
        "工作纪实内容模块审核",
        "工作纪实原子模块迁移审核",
        "工作纪实四段式拆解审核",
    }:
        return "module_candidate"
    if audit_type in {"原始资料入库审核", "同步入库审核"}:
        return "raw_material"
    return "other"


def normalize_audit_subject(subject: str, audit_kind: str, fallback: str) -> str:
    raw = subject.strip().strip("`") or fallback
    if raw == fallback:
        match = re.search(r"审核_(.+)$", fallback)
        if match:
            raw = match.group(1).strip()
    if audit_kind in {"module_candidate", "raw_material"}:
        return normalize_book_title(raw)
    return re.sub(r"\.md$", "", raw, flags=re.I)


def infer_rework_owner(audit_type: str) -> str:
    if audit_type in {"机器文案放行审核", "成稿放行审核"}:
        return "小写"
    if audit_type in {"原始资料入库审核", "同步入库审核"}:
        return "小息"
    if audit_type in {"候选充分拆解审核", "正式充分拆解放行审核", "正式模块撤销通过并退回", "工作纪实原文直拆审核", "工作纪实原子模块迁移审核", "工作纪实四段式拆解审核"}:
        return "小拆"
    return "小姜"


def read_audit_records() -> list[dict[str, object]]:
    if not AUDIT_DIR.exists():
        return []
    records: list[dict[str, object]] = []
    for path in AUDIT_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        audit_type = infer_audit_type(path, text)
        audit_kind = infer_audit_kind(audit_type)
        subject = extract_line_value(text, "- 审核对象：")
        if not subject:
            subject = extract_line_value(text, "- 资料标题：")
        target = normalize_audit_subject(subject, audit_kind, path.stem)
        status = infer_audit_status(text, audit_type)
        records.append(
            {
                "path": path,
                "name": path.name,
                "audit_type": audit_type,
                "audit_kind": audit_kind,
                "subject": target,
                "status": status,
                "timestamp": path.stat().st_mtime,
                "owner": infer_rework_owner(audit_type),
            }
        )
    records.sort(key=lambda item: item["timestamp"], reverse=True)
    return records


def latest_audit_map(records: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, object]]:
    latest: dict[tuple[str, str], dict[str, object]] = {}
    for record in records:
        key = (str(record["audit_kind"]), str(record["subject"]))
        if key not in latest:
            latest[key] = record
    return latest


def latest_completed_audits(records: list[dict[str, object]], limit: int = 8) -> list[dict[str, object]]:
    latest = latest_audit_map(records)
    completed = [record for record in latest.values() if str(record["status"]) != "待审核"]
    completed.sort(key=lambda item: float(item["timestamp"]), reverse=True)
    return completed[:limit]


def collect_rework_items(records: list[dict[str, object]], limit: int = 8) -> list[dict[str, object]]:
    latest = latest_audit_map(records)
    items = [record for record in latest.values() if str(record["status"]) in {"退回", "部分退回"}]
    items.sort(key=lambda item: float(item["timestamp"]), reverse=True)
    return items[:limit]


def candidate_dir_mtime(path: Path) -> float:
    times = [path.stat().st_mtime]
    for child in path.rglob("*"):
        times.append(child.stat().st_mtime)
    return max(times)


def scan_candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    if not CANDIDATE_ROOT.exists():
        return dirs
    for skill_dir in CANDIDATE_ROOT.iterdir():
        if not skill_dir.is_dir():
            continue
        for title_dir in skill_dir.iterdir():
            if title_dir.is_dir():
                dirs.append(title_dir)
    return sorted(dirs)


def scan_formal_raw_md_files(raw_rows: list[dict[str, str]]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for row in raw_rows:
        rel = row.get("原始资料文件路径", "").strip().strip("`")
        status = row.get("当前状态", "").strip()
        if not rel or not rel.lower().endswith(".md"):
            continue
        if status == "已拆解":
            continue
        key = rel.lower()
        if key in seen:
            continue
        seen.add(key)
        files.append(ROOT / "02_资产中心" / rel)
    return sorted(path for path in files if path.exists())


def collect_pending_audits(latest_map: dict[tuple[str, str], dict[str, object]], raw_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    pending: list[dict[str, str]] = []

    for candidate_dir in scan_candidate_dirs():
        subject = normalize_book_title(candidate_dir.name)
        latest = latest_map.get(("module_candidate", subject))
        updated_at = candidate_dir_mtime(candidate_dir)
        if latest is None or float(latest["timestamp"]) < updated_at:
            pending.append({"subject": subject, "audit_type": "拆书候选审核", "owner": "小审"})

    for path in sorted(BODY_ROOT.glob("*.md")) if BODY_ROOT.exists() else []:
        subject = path.stem
        latest = latest_map.get(("machine_draft", subject))
        if latest is None or float(latest["timestamp"]) < path.stat().st_mtime:
            pending.append({"subject": subject, "audit_type": "机器文案放行审核", "owner": "小审"})

    for path in sorted(DRAFT_ROOT.glob("*.md")) if DRAFT_ROOT.exists() else []:
        subject = path.stem
        latest = latest_map.get(("final_draft", subject))
        if latest is None or float(latest["timestamp"]) < path.stat().st_mtime:
            pending.append({"subject": subject, "audit_type": "成稿放行审核", "owner": "小审"})

    for path in scan_formal_raw_md_files(raw_rows):
        subject = normalize_book_title(path.stem)
        latest = latest_map.get(("raw_material", subject))
        if latest is None or float(latest["timestamp"]) < path.stat().st_mtime:
            pending.append({"subject": subject, "audit_type": "原始资料入库审核", "owner": "小审"})

    pending.sort(key=lambda item: (item["audit_type"], item["subject"]))
    return pending


def read_raw_rows() -> list[dict[str, str]]:
    return parse_table(RAW_LEDGER)


def scan_uploaded_raw_files() -> list[Path]:
    if not RAW_ROOT.exists():
        return []
    ignored_root_files = {"00_原始资料输入清单.md", "README.md"}
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
    return parse_table(TOPIC_ROOT / "00_爆款选题选中清单.md")


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
    done_openings = [row for row in opening_selection_rows if row.get("状态", "").strip() == "已拆解"]
    failed_openings = [row for row in opening_selection_rows if row.get("状态", "").strip() == "拆解失败"]
    opening_cards = opening_card_rows()

    hand_rows = read_hand_topic_rows()
    generation = summarize_generation(hand_rows)

    audit_records = read_audit_records()
    latest_map = latest_audit_map(audit_records)
    pending_audits = collect_pending_audits(latest_map, raw_rows)
    recent_completed = latest_completed_audits(audit_records)
    rework_items = collect_rework_items(audit_records)

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
        f"- 最近已拆解开头数：{len(done_openings)}",
        f"- 最近拆解失败开头数：{len(failed_openings)}",
        f"- 已生成 BK 开头卡片数：{len(opening_cards)}",
    ]

    if pending_openings:
        lines += ["", "#### 待拆解开头明细", ""]
        for row in pending_openings[:12]:
            lines.append(
                f"- {row.get('序号','')}｜{row.get('选题','未填选题') or '未填选题'}｜{row.get('链接','无链接')}"
            )

    lines += [
        "",
        "## 2. 待生成内容",
        "",
        f"- 爆款选题选中清单条数：{generation['total']}",
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
    if pending_audits:
        lines.append(f"- 待审核总数：{len(pending_audits)}")
        lines.append("- 待审核类型分布：")
        for audit_type, count in Counter(item["audit_type"] for item in pending_audits).items():
            lines.append(f"  - {audit_type}：{count}")
        lines += ["", "### 待审核明细", ""]
        for item in pending_audits[:12]:
            lines.append(f"- {item['subject']}｜{item['audit_type']}｜当前责任人：{item['owner']}")
    else:
        lines.append("- 当前没有新的待审核事项。")

    lines += ["", "## 4. 最近审核结果", ""]
    if recent_completed:
        for record in recent_completed:
            lines.append(f"- {record['subject']}｜{record['audit_type']}｜{record['status']}")
    else:
        lines.append("- 当前没有可读取的已完成审核结果。")

    lines += ["", "## 5. 审核后待处理事项", ""]
    if rework_items:
        for record in rework_items:
            lines.append(f"- {record['subject']}｜{record['audit_type']}｜退回给：{record['owner']}｜结论：{record['status']}")
    else:
        lines.append("- 当前没有新的审核退回事项。")

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

    lines += ["", "## 6. 小姜下一步建议", ""]
    dynamic_actions: list[str] = []
    if pending_audits:
        dynamic_actions.append("先清掉当前待审核事项，再继续推进下游产物。")
    if rework_items:
        first_rework = rework_items[0]
        dynamic_actions.append(f"优先处理最近被退回的 `{first_rework['subject']}`，退回给 {first_rework['owner']}。")
    merged_actions = dynamic_actions + [item for item in next_actions if item not in dynamic_actions]
    if merged_actions:
        for item in merged_actions:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前没有单独建议，优先处理待拆解和待生成事项。")

    if current_state_excerpt:
        lines += ["", "### 当前推进状态摘要", ""]
        for item in current_state_excerpt:
            lines.append(f"- {item}")

    return append_brand_footer("\n".join(lines))


if __name__ == "__main__":
    sync_public_chain()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(OUT)
