from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from datetime import datetime
from pathlib import Path


def load_breakdown_module(root: Path):
    script_path = (
        root
        / "10_Skills武器库"
        / "爆款开头拆解Skill"
        / "scripts"
        / "run_baokuan_opening_breakdown.py"
    )
    spec = importlib.util.spec_from_file_location("baokuan_opening_breakdown", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载爆款开头拆解脚本：{script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def section(text: str, heading: str, next_heading: str | None = None) -> str:
    if heading not in text:
        return ""
    body = text.split(heading, 1)[1]
    if next_heading and next_heading in body:
        body = body.split(next_heading, 1)[0]
    return body.strip()


def numbered_lines(body: str) -> list[str]:
    return [
        match.group(1).strip()
        for line in body.splitlines()
        if (match := re.match(r"^\d+\.\s+(.+)$", line.strip()))
    ]


def table_rows(body: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0] in {"句子", "-"}:
            continue
        if all(re.fullmatch(r"-+", cell or "-") for cell in cells):
            continue
        rows.append(cells)
    return rows


def metadata(text: str, key: str) -> str:
    match = re.search(rf"^- {re.escape(key)}：(.*)$", text, re.M)
    return match.group(1).strip() if match else ""


def compact(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()


def audit_candidate(candidate: Path, input_dir: Path, root: Path) -> tuple[list[str], dict[str, str]]:
    module = load_breakdown_module(root)
    text = candidate.read_text(encoding="utf-8", errors="ignore")
    issues: list[str] = []
    info = {
        "编号": metadata(text, "开头编号"),
        "选题": metadata(text, "选题"),
        "来源账号表": metadata(text, "来源账号表"),
        "来源行": metadata(text, "来源行"),
    }

    sentence_body = section(text, "### 1. 原文前5句", "### 2. 逐句拆解")
    sentences = numbered_lines(sentence_body)
    detail_body = section(text, "### 2. 逐句拆解", "### 3. 五句推进逻辑")
    details = table_rows(detail_body)
    skeleton_body = section(text, "### 4. 五句结构骨架", "### 5. 适合承载的论证方式")
    skeleton_part, _, template_part = skeleton_body.partition("句式模板：")
    skeletons = numbered_lines(skeleton_part)
    templates = numbered_lines(template_part)
    argument = section(text, "### 5. 适合承载的论证方式", "### 6. 调用匹配规则").strip("> \n")
    matching = section(text, "### 6. 调用匹配规则")

    if len(sentences) != 5:
        issues.append(f"原文功能句应为5句，当前为{len(sentences)}句")
    if len(details) != len(sentences):
        issues.append("逐句拆解数量与原文功能句不一致")
    functions: list[str] = []
    structures: list[str] = []
    for idx, row in enumerate(details, start=1):
        if len(row) < 4:
            issues.append(f"第{idx}行逐句拆解字段不完整")
            continue
        functions.append(row[2])
        structures.append(row[3])
        if row[1] != sentences[idx - 1]:
            issues.append(f"第{idx}句在原文区与逐句拆解区不一致")

    for idx, sentence in enumerate(sentences, start=1):
        length = module.han_len(sentence)
        if length > module.HARD_SENTENCE_LIMIT:
            issues.append(f"第{idx}句超过{module.HARD_SENTENCE_LIMIT}个汉字")
        elif length > module.SOFT_SENTENCE_LIMIT:
            issues.append(f"第{idx}句超过{module.SOFT_SENTENCE_LIMIT}个汉字，语义边界未通过")
    if module.UNKNOWN_FUNCTION in functions:
        issues.append("存在待人工判断的核心功能")
    for idx in range(len(functions) - 1):
        if functions[idx] == functions[idx + 1] == "内容预告":
            issues.append(f"第{idx + 1}句和第{idx + 2}句连续使用内容预告，疑似兜底")
    for idx, structure in enumerate(structures, start=1):
        if structure in {"关键信息＋表达动作＋句内承诺", "主题限定＋后文安排＋内容预告"}:
            if idx > len(functions) or functions[idx - 1] != "内容预告":
                issues.append(f"第{idx}句使用泛化写作结构")

    if len(skeletons) != 5 or len(templates) != 5:
        issues.append("五句结构骨架和句式模板必须各有5条")
    for idx, line in enumerate(skeletons, start=1):
        if re.search(r"第\d+句保留|按.+组织表达", line):
            issues.append(f"第{idx}条结构骨架是空占位说明")
    for idx, line in enumerate(templates, start=1):
        if "【" not in line or "】" not in line:
            issues.append(f"第{idx}条句式模板缺少可替换变量")
        if re.search(r"按.+替换|替换为新正文素材", line):
            issues.append(f"第{idx}条句式模板是空占位模板")
    if "接近" in matching or "自然承接这条五句功能链" in matching:
        issues.append("调用匹配规则仍为泛化说明")

    if sentences and len(functions) == len(sentences):
        try:
            expected_argument = module.detect_argument_pattern(sentences, functions)
            if expected_argument != argument:
                issues.append(f"论证方式与五句功能链不一致，应为：{expected_argument}")
        except Exception as exc:
            issues.append(str(exc))

    source_name = info["来源账号表"]
    source_row_text = info["来源行"]
    source_path = input_dir / source_name
    if not source_name or not source_path.exists():
        issues.append("无法定位来源账号表")
    elif not source_row_text.isdigit():
        issues.append("来源行不是有效行号")
    else:
        _, source_rows = module.read_excel(source_path)
        source_index = int(source_row_text) - 2
        if source_index < 0 or source_index >= len(source_rows):
            issues.append("来源行超出账号表范围")
        else:
            source_script = module.clean_script(source_rows[source_index].get("文案", ""))
            source_compact = compact(source_script)
            for idx, sentence in enumerate(sentences, start=1):
                probe = compact(sentence)
                if probe and probe not in source_compact:
                    issues.append(f"第{idx}句无法逐字回指清洗后的原文")

    return issues, info


def write_report(root: Path, candidate: Path, issues: list[str], info: dict[str, str]) -> Path:
    report_dir = root / "01_Agent系统" / "02_小审-质量审核Agent" / "99_审核记录"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    bk_id = info.get("编号") or candidate.stem.split("_", 1)[0]
    report_path = report_dir / f"{timestamp}_爆款开头卡片审核_{bk_id}.md"
    conclusion = "通过" if not issues else "退回"
    lines = [
        "# 爆款开头卡片正式放行审核",
        "",
        f"- 审核对象：{info.get('选题', '')}",
        f"- 开头编号：{bk_id}",
        f"- 候选文件：`{candidate}`",
        f"- 审核结论：{conclusion}",
        "",
        "## 审核结果",
        "",
    ]
    if issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- 前5句语义边界、核心功能、结构骨架、句式模板、论证方式和调用规则均通过。")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="小审爆款开头卡片正式放行审核")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    candidate = Path(args.candidate)
    issues, info = audit_candidate(candidate, Path(args.input_dir), root)
    report_path = write_report(root, candidate, issues, info) if args.write_report else None
    if issues:
        print(f"退回｜{issues[0]}｜审核报告={report_path or ''}")
        raise SystemExit(1)
    print(f"通过｜{info.get('编号', candidate.stem)}｜审核报告={report_path or ''}")


if __name__ == "__main__":
    main()
