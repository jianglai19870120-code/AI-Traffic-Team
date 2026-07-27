from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from brand_footer import append_brand_footer

SOURCE_DIR = ROOT / "02_资产中心" / "01_原始知识库" / "99_我的工作纪实"
MODULE_ROOT = ROOT / "02_资产中心" / "02_内容模块库" / "99_工作纪实模块"
QUOTE_DIR = MODULE_ROOT / "01_金句模块"
MISTAKE_DIR = MODULE_ROOT / "02_误区模块"
STEP_DIR = MODULE_ROOT / "03_步骤模块"
INDEX_DIR = MODULE_ROOT / "05_模块索引"
HISTORY_DIR = MODULE_ROOT / "99_历史处理记录"

EXEC_DIR = ROOT / "01_Agent系统" / "04_小拆-内容拆解Agent" / "99_执行记录"
AUDIT_DIR = ROOT / "01_Agent系统" / "02_小审-质量审核Agent" / "99_审核记录"
SOURCE_RECORD_DIR = ROOT / "01_Agent系统" / "04_小拆-内容拆解Agent" / "99_执行记录" / "正式产物来源"

QUOTE_FILE = QUOTE_DIR / "工作纪实金句模块.md"
INDEX_FILE = INDEX_DIR / "模块索引.jsonl"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def ensure_dirs() -> None:
    for path in (QUOTE_DIR, MISTAKE_DIR, STEP_DIR, INDEX_DIR, HISTORY_DIR, EXEC_DIR, AUDIT_DIR, SOURCE_RECORD_DIR):
        path.mkdir(parents=True, exist_ok=True)


def slug(text: str, max_len: int = 46) -> str:
    text = re.sub(r"[\\/:*?\"<>|]", "_", text)
    text = re.sub(r"\s+", "", text)
    text = text.strip("._ ，,、：:")
    return (text[:max_len] or "未命名")


def sentence_lines(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"([。！？!?])\s*", r"\1\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？!?])\s*", normalized)
    return [part.strip() for part in parts if part.strip()]


def collect_source_files() -> list[Path]:
    return sorted(
        path
        for path in SOURCE_DIR.glob("*.md")
        if path.is_file() and path.name != ".sync-state.json"
    )


def read_source(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    heading = next((line.strip()[2:].strip() for line in text.splitlines() if line.startswith("# ")), "")
    title = heading or path.stem
    note_id_match = re.search(r"^- 得到大脑 note_id：(.+)$", text, re.M)
    note_id = note_id_match.group(1).strip() if note_id_match else ""
    transcript = section(text, "## 原始转写", "## 得到大脑摘要").strip()
    if not transcript:
        transcript = fallback_body(text)
    return title, note_id, transcript


def section(text: str, start: str, end: str | None = None) -> str:
    if start not in text:
        return ""
    tail = text.split(start, 1)[1]
    if end and end in tail:
        tail = tail.split(end, 1)[0]
    return tail.strip()


def fallback_body(text: str) -> str:
    lines: list[str] = []
    body_started = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            body_started = True
            continue
        if not body_started:
            continue
        if stripped.startswith("- ") and "：" in stripped:
            continue
        if stripped:
            lines.append(stripped)
    return "\n".join(lines).strip()


def split_paragraphs(text: str) -> list[str]:
    parts = [re.sub(r"\s+", " ", part.strip()) for part in re.split(r"\n\s*\n", text) if part.strip()]
    return [part for part in parts if part]


def normalize_list_line(line: str) -> str:
    value = line.strip()
    value = re.sub(r"^#+\s*", "", value)
    value = re.sub(r"^[\-\*\u2022]\s*", "", value)
    value = re.sub(r"^\d+[\.、]\s*", "", value)
    value = re.sub(r"^第[一二三四1234]+[步点、：:\.]?\s*", "", value)
    value = value.replace("**", "").replace("*", "").replace("`", "").strip()
    return value.strip()


def quote_score(text: str) -> int:
    score = 0
    if 6 <= len(text) <= 36:
        score += 1
    if any(token in text for token in ("才", "就", "一定", "不要", "不能", "未来", "关键", "重要", "真正", "核心", "先", "只", "总之")):
        score += 1
    if any(token in text for token in ("，", "。", "？", "！")):
        score += 1
    if any(token in text for token in ("不是", "而是", "越", "少", "多", "难", "焦虑")):
        score += 1
    return score


def is_clean_quote_candidate(text: str) -> bool:
    if not text:
        return False
    if any(token in text for token in ("###", "##", "✨", "录音者：", "用户：", "audio_original", "得到大脑")):
        return False
    if text.startswith((">", "”", "：", "(", "（", "-", "*")):
        return False
    if text.count("“") != text.count("”"):
        return False
    if len(re.findall(r"[\u4e00-\u9fff]", text)) < 4:
        return False
    return True


def extract_quotes(transcript: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    line_candidates = [normalize_list_line(line) for line in transcript.splitlines() if normalize_list_line(line)]
    sentence_candidates = split_sentences(transcript)
    for candidate in line_candidates + sentence_candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if len(candidate) > 42:
            continue
        if not is_clean_quote_candidate(candidate):
            continue
        if quote_score(candidate) >= 3:
            candidates.append(candidate)
    return candidates


def old_clause(sentence: str) -> str:
    for marker in ("其实", "重要的是", "问题在于", "真正", "而是"):
        if marker in sentence:
            return sentence.split(marker, 1)[0].strip(" ，。；")
    return sentence.strip(" ，。；")


def correction_clause(sentence: str) -> str:
    for marker in ("重要的是", "其实", "问题在于", "真正", "不是", "而是", "关键是"):
        if marker in sentence:
            return marker + sentence.split(marker, 1)[1].strip(" ，。；")
    return sentence.strip(" ，。；")


def infer_mistake_title(text: str) -> str:
    if "只卖一个" in text and any(token in text for token in ("三个产品", "咨询", "陪跑", "课程", "多个产品")):
        return "一开始就同时卖多个产品"
    for pattern in (
        r"(?:以为|误以为|总觉得|觉得)([^，。；]{4,28})",
        r"很多人(?:会|总|都)?(?:想|觉得|以为|考虑)?([^，。；]{4,28})",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" ，。；")
    sentence = split_sentences(text)[0] if split_sentences(text) else text
    return sentence[:24].strip(" ，。；")


def extract_mistakes(paragraphs: list[str]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for idx, paragraph in enumerate(paragraphs):
        sentences = split_sentences(paragraph)
        if len(sentences) < 2:
            continue
        raw_old_sentence = next(
            (
                s for s in sentences
                if any(token in s for token in ("很多人", "以为", "误以为", "总觉得", "会考虑", "习惯", "容易"))
            ),
            "",
        )
        raw_correction_sentence = next(
            (
                s for s in sentences
                if any(token in s for token in ("其实", "重要的是", "问题在于", "真正", "不是", "而是", "关键"))
            ),
            "",
        )
        old_sentence = old_clause(raw_old_sentence)
        correction_sentence = correction_clause(raw_correction_sentence)
        consequence_sentence = next(
            (
                s for s in sentences
                if any(token in s for token in ("困难", "成本", "代价", "损耗", "来不及", "变得", "会", "很难"))
                and s != raw_old_sentence
                and s != raw_correction_sentence
            ),
            "",
        )
        if not old_sentence or not correction_sentence:
            continue
        if not consequence_sentence and idx + 1 < len(paragraphs):
            next_sentences = split_sentences(paragraphs[idx + 1])
            consequence_sentence = next(
                (
                    s for s in next_sentences
                    if any(token in s for token in ("困难", "成本", "代价", "损耗", "来不及", "变得", "会", "很难"))
                ),
                "",
            )
        evidence: list[tuple[str, str]] = [
            ("原文里的旧判断", old_sentence),
            ("原文给出的纠偏判断", correction_sentence),
        ]
        if consequence_sentence:
            evidence.append(("继续这样做的代价", consequence_sentence))
        title = infer_mistake_title(paragraph)
        if title:
            items.append({"title": title, "evidence": evidence, "summary": paragraph})
    return dedupe_items(items, "title")


def extract_step_groups(title: str, transcript: str) -> list[dict[str, object]]:
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    numbered: list[str] = []
    for line in lines:
        if re.match(r"^\d+[\.、]\s*", line):
            numbered.append(normalize_list_line(line))
    groups: list[dict[str, object]] = []
    if 2 <= len(numbered) <= 4:
        steps = []
        for item in numbered:
            step_title = re.split(r"[，。：:；]", item, maxsplit=1)[0].strip()
            steps.append({"title": step_title or item[:12], "body": item})
        groups.append({"problem": title, "steps": steps})
        return groups

    inline_markers = re.findall(r"第([一二三四1234])步", transcript)
    if len(inline_markers) >= 2:
        parts = re.split(r"第[一二三四1234]步[：:，,]?", transcript)
        step_bodies = [part.strip(" ，。；\n") for part in parts[1:] if part.strip(" ，。；\n")]
        steps = []
        for body in step_bodies[:4]:
            first_clause = re.split(r"[，。：:；]", body, maxsplit=1)[0].strip()
            steps.append({"title": first_clause or body[:12], "body": body})
        if 2 <= len(steps) <= 4:
            groups.append({"problem": title, "steps": steps})
    return groups


def dedupe_items(items: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for item in items:
        value = str(item[key]).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def quote_file_body(entries: list[tuple[str, str]]) -> str:
    lines = ["# 工作纪实金句模块", "", "## #真实工作", ""]
    if not entries:
        lines.append("> 当前还没有从工作纪实里提取到可复用金句。")
    else:
        for quote, source_title in entries:
            lines.append(f"- {quote}——《{source_title}》")
    lines.append("")
    return "\n".join(lines)


def mistake_module_body(item: dict[str, object], source_title_value: str, source_path: str, note_id: str) -> str:
    title = str(item["title"])
    evidence = list(item["evidence"])
    lines = [
        f"# 工作纪实_错误观点：{title}",
        "",
        "**错误观点**",
        "",
        title,
        "",
    ]
    for idx, (heading, body) in enumerate(evidence, start=1):
        lines += [f"**误区{idx}：{heading}**", "", sentence_lines(str(body)), ""]
    lines += [
        "## 来源信息",
        "",
        f"- 来源工作纪实：{source_title_value}",
        f"- 来源文件：`{source_path}`",
        f"- 得到大脑 note_id：{note_id}",
        f"- 拆解时间：{now()}",
        "- 拆解 Skill：工作纪实内容模块拆解Skill",
        "",
    ]
    return "\n".join(lines)


def step_module_body(group: dict[str, object], source_title_value: str, source_path: str, note_id: str) -> str:
    problem = str(group["problem"])
    lines = [
        f"# 工作纪实_{problem}",
        "",
        "**具体问题**",
        "",
        problem,
        "",
    ]
    for idx, step in enumerate(group["steps"], start=1):
        step_title = str(step["title"]).strip()
        body = str(step["body"]).strip()
        lines += [f"**步骤{idx}：{step_title}**", "", sentence_lines(body), ""]
    lines += [
        "## 来源信息",
        "",
        f"- 来源工作纪实：{source_title_value}",
        f"- 来源文件：`{source_path}`",
        f"- 得到大脑 note_id：{note_id}",
        f"- 拆解时间：{now()}",
        "- 拆解 Skill：工作纪实内容模块拆解Skill",
        "",
    ]
    return "\n".join(lines)


def module_id(module_type: str, title: str) -> str:
    digest = hashlib.sha1(f"{module_type}:{title}".encode("utf-8")).hexdigest()[:8]
    return f"work_journal__{module_type}__{digest}"


def index_record(module_type: str, title: str, source_title_value: str, source_path: str, module_path: Path, summary: str) -> dict[str, object]:
    return {
        "module_id": module_id(module_type, title),
        "module_type": module_type,
        "title": title,
        "source_title": source_title_value,
        "source_path": source_path,
        "module_path": str(module_path),
        "tags_topic": ["工作纪实", source_title_value[:12]],
        "tags_scene": ["真实业务", "文案调用"],
        "summary": summary[:120],
        "status": "ready",
    }


def source_summary_record(
    source_path: Path,
    source_title_value: str,
    quotes: list[str],
    mistakes: list[dict[str, object]],
    steps: list[dict[str, object]],
    transcript: str,
) -> dict[str, object]:
    missing_reasons: list[str] = []
    if not quotes:
        missing_reasons.append(missing_quote_reason(transcript))
    if not mistakes:
        missing_reasons.append(missing_mistake_reason(transcript))
    if not steps:
        missing_reasons.append(missing_step_reason(transcript))
    return {
        "source_title": source_title_value,
        "source_path": str(source_path),
        "quotes_count": len(quotes),
        "mistakes_count": len(mistakes),
        "steps_count": len(steps),
        "missing_reasons": missing_reasons,
        "processed_at": now(),
    }


def missing_quote_reason(transcript: str) -> str:
    if len(re.sub(r"\s+", "", transcript)) < 30:
        return "金句未提取：内容过短"
    return "金句未提取：没有足够完整且可传播的判断句"


def missing_mistake_reason(transcript: str) -> str:
    if "很多人" not in transcript and "以为" not in transcript and "误以为" not in transcript:
        return "误区未提取：只有记录没有明确错误认知"
    return "误区未提取：有观点但没有形成完整纠偏证据"


def missing_step_reason(transcript: str) -> str:
    if not re.search(r"(^\d+[\.、]\s*)|(第[一二三四1234]步)", transcript, re.M):
        return "步骤未提取：只有动作片段但不构成完整步骤"
    return "步骤未提取：步骤证据不完整，未达到 2 到 4 步连续结构"


def archive_existing_outputs() -> Path | None:
    existing_files = [path for path in MODULE_ROOT.rglob("*") if path.is_file()]
    if not existing_files:
        return None
    archive_dir = HISTORY_DIR / f"{stamp()}_重构前快照"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for path in existing_files:
        relative = path.relative_to(MODULE_ROOT)
        target = archive_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return archive_dir


def clear_generated() -> None:
    for folder in (QUOTE_DIR, MISTAKE_DIR, STEP_DIR, INDEX_DIR):
        folder.mkdir(parents=True, exist_ok=True)
        for path in folder.glob("*"):
            if path.is_file():
                path.unlink()


def rebuild() -> tuple[list[Path], list[Path], list[dict[str, object]], list[dict[str, object]], Path | None]:
    ensure_dirs()
    archive_dir = archive_existing_outputs()
    clear_generated()

    source_files = collect_source_files()
    outputs: list[Path] = []
    index_records: list[dict[str, object]] = []
    source_summaries: list[dict[str, object]] = []
    quote_entries: list[tuple[str, str]] = []

    for source_path in source_files:
        source_title_value, note_id, transcript = read_source(source_path)
        quotes = extract_quotes(transcript)
        paragraphs = split_paragraphs(transcript)
        mistakes = extract_mistakes(paragraphs)
        steps = extract_step_groups(source_title_value, transcript)

        source_summaries.append(source_summary_record(source_path, source_title_value, quotes, mistakes, steps, transcript))

        for quote in quotes:
            quote_entries.append((quote, source_title_value))

        for item in mistakes:
            out = MISTAKE_DIR / f"工作纪实_错误观点：{slug(str(item['title']))}.md"
            out.write_text(append_brand_footer(mistake_module_body(item, source_title_value, str(source_path), note_id)), encoding="utf-8")
            outputs.append(out)
            index_records.append(index_record("误区", str(item["title"]), source_title_value, str(source_path), out, str(item["summary"])))

        for group in steps:
            problem = str(group["problem"])
            filename_title = problem if "怎么" in problem else f"{problem}怎么做"
            out = STEP_DIR / f"工作纪实_{slug(filename_title)}.md"
            out.write_text(append_brand_footer(step_module_body(group, source_title_value, str(source_path), note_id)), encoding="utf-8")
            outputs.append(out)
            first_step = group["steps"][0] if group["steps"] else {"body": ""}
            index_records.append(index_record("步骤", problem, source_title_value, str(source_path), out, str(first_step.get("body", ""))))

    QUOTE_FILE.write_text(append_brand_footer(quote_file_body(quote_entries)), encoding="utf-8")
    outputs.append(QUOTE_FILE)
    if quote_entries:
        index_records.append(index_record("金句", "工作纪实金句模块", "多篇工作纪实", "工作纪实聚合", QUOTE_FILE, "工作纪实高传播表达聚合"))

    INDEX_FILE.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in index_records) + ("\n" if index_records else ""), encoding="utf-8")

    summary_file = HISTORY_DIR / f"{stamp()}_逐篇拆解摘要.jsonl"
    summary_file.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in source_summaries) + ("\n" if source_summaries else ""), encoding="utf-8")
    outputs.append(summary_file)
    outputs.append(INDEX_FILE)

    return source_files, outputs, index_records, source_summaries, archive_dir


def validate(outputs: list[Path], source_summaries: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    if not QUOTE_FILE.exists():
        issues.append("缺少工作纪实金句模块.md")
    if not INDEX_FILE.exists():
        issues.append("缺少模块索引.jsonl")
    if not source_summaries:
        issues.append("没有扫描到任何工作纪实原文")
    for path in outputs:
        if path.parent == MISTAKE_DIR:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "**误区1：" not in text:
                issues.append(f"{path.name} 缺少误区编号结构")
        if path.parent == STEP_DIR:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "**步骤1：" not in text:
                issues.append(f"{path.name} 缺少步骤编号结构")
            step_count = len(re.findall(r"\*\*步骤\d+：", text))
            if step_count < 2 or step_count > 4:
                issues.append(f"{path.name} 步骤数不在 2 到 4 之间")
    return issues


def write_records(
    source_files: list[Path],
    outputs: list[Path],
    index_records: list[dict[str, object]],
    source_summaries: list[dict[str, object]],
    archive_dir: Path | None,
    issues: list[str],
) -> None:
    mistake_count = sum(1 for item in index_records if item["module_type"] == "误区")
    step_count = sum(1 for item in index_records if item["module_type"] == "步骤")
    quote_count = sum(item["quotes_count"] for item in source_summaries)
    summary_path = next((path for path in outputs if path.parent == HISTORY_DIR and path.suffix == ".jsonl"), None)

    audit = AUDIT_DIR / f"{stamp()}_工作纪实原文直拆审核.md"
    audit.write_text(
        append_brand_footer(
            "\n".join(
                [
                    "# 小审审核记录",
                    "",
                    f"- 审核时间：{now()}",
                    "- 审核对象：工作纪实原文直拆",
                    f"- 审核结论：{'通过' if not issues else '退回'}",
                    "",
                    "## 输出统计",
                    "",
                    f"- 输入原文：{len(source_files)}",
                    f"- 金句条数：{quote_count}",
                    f"- 误区模块：{mistake_count}",
                    f"- 步骤模块：{step_count}",
                    f"- 索引记录：{len(index_records)}",
                    f"- 逐篇摘要：`{summary_path}`" if summary_path else "- 逐篇摘要：未生成",
                    "",
                    "## 问题",
                    "",
                    *(["- 未发现阻断问题。"] if not issues else [f"- {issue}" for issue in issues]),
                ]
            )
        ),
        encoding="utf-8",
    )

    exec_record = EXEC_DIR / f"{stamp()}_工作纪实原文直拆执行记录.md"
    exec_record.write_text(
        append_brand_footer(
            "\n".join(
                [
                    "# 小拆执行记录",
                    "",
                    f"- 执行时间：{now()}",
                    "- 任务：工作纪实原文直拆",
                    f"- 执行状态：{'通过' if not issues else '退回'}",
                    "",
                    "## 输入原文",
                    "",
                    *[f"- `{path}`" for path in source_files],
                    "",
                    "## 输出模块",
                    "",
                    *[f"- `{path}`" for path in outputs if path.parent in {QUOTE_DIR, MISTAKE_DIR, STEP_DIR, INDEX_DIR, HISTORY_DIR}],
                    "",
                    f"- 重构前快照：`{archive_dir}`" if archive_dir else "- 重构前快照：无",
                    f"- 小审审核记录：`{audit}`",
                ]
            )
        ),
        encoding="utf-8",
    )

    source_record = SOURCE_RECORD_DIR / f"{stamp()}_工作纪实原文直拆正式产物来源.jsonl"
    source_record.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in index_records) + ("\n" if index_records else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="工作纪实原文直拆")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(f"source_files={len(collect_source_files())}")
        return 0

    source_files, outputs, index_records, source_summaries, archive_dir = rebuild()
    if not source_files:
        print("[工作纪实内容模块拆解] result=跳过 reason=没有待处理的工作纪实原文")
        return 0

    issues = validate(outputs, source_summaries)
    write_records(source_files, outputs, index_records, source_summaries, archive_dir, issues)
    print(
        f"[工作纪实内容模块拆解] inputs={len(source_files)} "
        f"quotes={sum(item['quotes_count'] for item in source_summaries)} "
        f"mistakes={sum(1 for item in index_records if item['module_type'] == '误区')} "
        f"steps={sum(1 for item in index_records if item['module_type'] == '步骤')} "
        f"result={'通过' if not issues else '退回'}"
    )
    for item in source_summaries:
        print(
            f"- {item['source_title']}\tquotes={item['quotes_count']}\t"
            f"mistakes={item['mistakes_count']}\tsteps={item['steps_count']}"
        )
    if issues:
        for issue in issues:
            print(f"! {issue}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
