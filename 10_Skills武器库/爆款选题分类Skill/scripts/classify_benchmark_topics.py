#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from openpyxl import load_workbook
except ImportError as exc:  # pragma: no cover
    raise SystemExit("缺少依赖 openpyxl，无法读取标准 xlsx。") from exc


CATEGORIES = {
    "科学创业": "01_科学创业选题表.md",
    "能力成长": "02_能力成长选题表.md",
    "赚钱财富": "03_赚钱财富选题表.md",
    "个人IP": "04_个人IP选题表.md",
    "AI科技": "05_AI科技选题表.md",
    "其他类型": "99_其他类型选题表.md",
}

TABLE_HEADER = ["选题", "主题分类", "博主名", "点赞数", "链接", "发布时间", "是否选用"]


@dataclass
class TopicRow:
    topic: str
    category: str
    blogger: str
    likes: str
    link: str
    published_at: str
    selected: str = ""

    def key(self) -> Tuple[str, str]:
        if self.link:
            return ("link", self.link)
        return ("topic", f"{self.blogger}::{self.topic}")

    def to_cells(self) -> List[str]:
        return [
            self.topic,
            self.category,
            self.blogger,
            self.likes,
            self.link,
            self.published_at,
            self.selected,
        ]


def normalize_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip()


def markdown_escape(value: str) -> str:
    value = normalize_cell(value)
    value = value.replace("\\", "\\\\").replace("|", "\\|")
    value = value.replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>")
    return value


def compact_text(raw: str) -> str:
    text = normalize_cell(raw)
    text = text.split("#", 1)[0]
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(展开|收起|复制链接|抖音|DOU\+小助手)$", "", text, flags=re.I).strip()
    return text


def first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[。！？?!])\s*", text)
    for part in parts:
        if part.strip():
            return part.strip()
    return text.strip()


def shorten_long_topic(text: str) -> Tuple[str, bool]:
    if len(text) <= 30:
        return text, False
    sentence = first_sentence(text)
    if sentence and len(sentence) <= 30:
        return sentence, True
    for sep in ["，", "；", "、", ",", ";"]:
        candidate = sentence.split(sep, 1)[0].strip()
        if candidate and len(candidate) <= 30:
            return candidate, True
    return text[:30].strip(), True


def clean_topic(raw: str) -> Tuple[str, bool, str]:
    text = compact_text(raw)
    if not text:
        return "", False, ""
    topic, shortened = shorten_long_topic(text)
    return topic, shortened, text


def score_keywords(text: str, keywords: Iterable[str]) -> int:
    return sum(1 for kw in keywords if kw.lower() in text.lower())


def classify_topic(topic: str) -> Tuple[str, str]:
    text = topic
    topic_text = topic

    ai_keywords = [
        "ai", "人工智能", "大模型", "模型", "agent", "智能体", "自动化", "编程", "代码",
        "claude", "gemini", "gpt", "openai", "cursor", "vibe coding", "芯片", "机器人",
        "科技", "工具", "发布", "产品更新",
    ]
    ip_keywords = [
        "自媒体", "短视频", "内容", "账号", "涨粉", "流量", "私域", "个人ip", "ip",
        "定位", "粉丝", "直播", "小红书", "抖音", "视频号", "公众号", "成交", "获客",
        "爆款", "文案", "选题", "剪辑",
    ]
    money_keywords = [
        "赚钱", "收入", "副业", "财富", "现金流", "变现", "赚到", "赚", "钱",
        "商业机会", "普通人", "搞钱", "财富自由", "咨询", "接单", "投资", "理财",
        "生意", "创业赚钱",
    ]
    growth_keywords = [
        "学习", "认知", "效率", "行动", "行动力", "决策", "表达", "习惯", "复盘",
        "自律", "成长", "能力", "职业", "思考", "心态", "选择", "拖延", "焦虑",
        "知识", "做事", "现卖现学", "闭环",
    ]
    startup_keywords = [
        "创业", "商业模式", "公司", "企业", "产品", "组织", "增长", "战略", "融资",
        "管理", "团队", "企业服务", "创新", "商业化", "老板", "ceo", "客户",
    ]

    topic_scores = {
        "AI科技": score_keywords(topic_text, ai_keywords),
        "个人IP": score_keywords(topic_text, ip_keywords),
        "赚钱财富": score_keywords(topic_text, money_keywords),
        "能力成长": score_keywords(topic_text, growth_keywords),
        "科学创业": score_keywords(topic_text, startup_keywords),
    }
    scores = {
        name: topic_scores[name]
        for name in topic_scores
    }

    # 主承诺边界：账号增长和内容获客优先于一般赚钱；AI 工具如只是赚钱工具则让位赚钱财富。
    if scores["个人IP"] >= 2 and any(k in text.lower() for k in ["涨粉", "流量", "账号", "自媒体", "短视频", "私域", "获客", "爆款", "文案", "选题"]):
        return "个人IP", "主承诺围绕内容账号、流量或个人品牌"

    if scores["赚钱财富"] >= 2 and any(k in text for k in ["赚钱", "副业", "收入", "赚到", "变现", "接单", "财富", "生意"]):
        return "赚钱财富", "主承诺围绕赚钱、收入或变现"

    if topic_scores["AI科技"] > 0 and scores["AI科技"] >= 2:
        return "AI科技", "主承诺围绕 AI、工具、模型或科技产品"

    if topic_scores["AI科技"] > 0 and scores["赚钱财富"] == 0 and scores["个人IP"] == 0:
        return "AI科技", "主承诺围绕 AI、工具、模型或科技产品"

    if topic_scores["能力成长"] > 0 and scores["赚钱财富"] == 0 and scores["个人IP"] == 0:
        return "能力成长", "主承诺围绕能力、认知或自我成长"

    if scores["科学创业"] >= 2 and scores["赚钱财富"] == 0 and scores["个人IP"] == 0:
        return "科学创业", "主承诺围绕创业、公司经营或商业化"

    if scores["能力成长"] >= 2 and scores["赚钱财富"] == 0:
        return "能力成长", "主承诺围绕能力、认知或自我成长"

    best_category, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return "其他类型", "信息不足或不属于当前五类"

    tied = [name for name, score in scores.items() if score == best_score]
    if len(tied) > 1:
        if "AI科技" in tied and topic_scores["AI科技"] > 0 and scores["赚钱财富"] == 0 and scores["个人IP"] == 0:
            return "AI科技", ""
        return "其他类型", "多类关键词冲突，需人工复核：" + "、".join(tied)

    return best_category, ""


def parse_markdown_table(path: Path) -> Dict[Tuple[str, str], TopicRow]:
    rows: Dict[Tuple[str, str], TopicRow] = {}
    if not path.exists():
        return rows
    content = path.read_text(encoding="utf-8-sig")
    if "是否选用" not in content:
        return rows
    for line in content.splitlines():
        if not line.startswith("|") or "---" in line or "选题" in line and "主题分类" in line:
            continue
        cells = [c.strip().replace("\\|", "|") for c in line.strip().strip("|").split("|")]
        if len(cells) != len(TABLE_HEADER):
            continue
        row = TopicRow(
            topic=cells[0],
            category=cells[1],
            blogger=cells[2],
            likes=cells[3],
            link=cells[4],
            published_at=cells[5],
            selected=cells[6],
        )
        rows[row.key()] = row
    return rows


def write_category_table(path: Path, category: str, rows: List[TopicRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {category}选题表",
        "",
        "| " + " | ".join(TABLE_HEADER) + " |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(markdown_escape(v) for v in row.to_cells()) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_xlsx(path: Path) -> Tuple[List[str], List[List[str]]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.active
    iterator = worksheet.iter_rows(values_only=True)
    headers = next(iterator, None)
    if not headers:
        return [], []
    normalized_headers = [normalize_cell(h) for h in headers]
    rows: List[List[str]] = []
    for row in iterator:
        rows.append([normalize_cell(v) for v in row])
    return normalized_headers, rows


def iter_input_files(input_dir: Path, blogger: Optional[str]) -> List[Path]:
    files = sorted(input_dir.glob("*.xlsx"))
    if blogger:
        files = [p for p in files if p.stem == blogger]
    return files


def classify_file(path: Path, audit: Dict[str, List[str]]) -> List[TopicRow]:
    blogger = path.stem
    try:
        headers, data_rows = read_xlsx(path)
    except Exception as exc:
        audit["unreadable"].append(f"{path.name}：{type(exc).__name__} {exc}")
        return []

    if "视频信息" not in headers:
        audit["missing_required"].append(f"{path.name}：缺少 视频信息 列")
        return []

    header_index = {name: i for i, name in enumerate(headers)}
    result: List[TopicRow] = []
    for offset, cells in enumerate(data_rows, start=2):
        def get(name: str) -> str:
            i = header_index.get(name)
            if i is None or i >= len(cells):
                return ""
            return cells[i]

        raw_topic = get("视频信息")
        topic, shortened, classify_basis = clean_topic(raw_topic)
        if not topic:
            audit["missing_topic"].append(f"{path.name} 第{offset}行：视频信息为空")
            continue

        if shortened:
            audit["long_topic"].append(f"{path.name} 第{offset}行：视频信息超过30字，提炼为：{topic}")

        category, _ = classify_topic(classify_basis)
        if category == "其他类型":
            audit["other_reason"].append(f"{path.name} 第{offset}行：仅根据视频信息无法稳定分类 -> {topic}")
        row = TopicRow(
            topic=topic,
            category=category,
            blogger=blogger,
            likes=get("点赞数"),
            link=get("链接"),
            published_at=get("发布时间"),
        )
        if not row.link:
            audit["missing_link"].append(f"{path.name} 第{offset}行：缺少链接，用 博主名+选题 去重")
        result.append(row)
    audit["readable"].append(f"{path.name}：读取 {len(data_rows)} 行，生成候选 {len(result)} 条")
    return result


def load_existing(output_dir: Path) -> Dict[str, Dict[Tuple[str, str], TopicRow]]:
    existing: Dict[str, Dict[Tuple[str, str], TopicRow]] = {}
    for category, filename in CATEGORIES.items():
        existing[category] = parse_markdown_table(output_dir / filename)
    return existing


def find_existing_category(existing: Dict[str, Dict[Tuple[str, str], TopicRow]], key: Tuple[str, str]) -> Optional[str]:
    for category, rows in existing.items():
        if key in rows:
            return category
    return None


def write_audit(audit_dir: Path, audit: Dict[str, List[str]], totals: Dict[str, int], output_dir: Path) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = audit_dir / f"{stamp}_爆款选题分类审核.md"
    lines = [
        "# 爆款选题分类审核",
        "",
        f"- 输出目录：{output_dir}",
        f"- 写入新选题：{totals['inserted']}",
        f"- 跳过重复：{totals['duplicates']}",
        f"- 移动分类：{totals.get('moved', 0)}",
        f"- 进入其他类型：{totals['other']}",
        "",
    ]
    sections = [
        ("可读取账号表", "readable"),
        ("不可读取账号表", "unreadable"),
        ("缺少必需字段", "missing_required"),
        ("缺少视频信息", "missing_topic"),
        ("缺少链接", "missing_link"),
        ("长选题提炼", "long_topic"),
        ("其他类型原因", "other_reason"),
    ]
    for title, key in sections:
        lines.extend([f"## {title}", ""])
        items = audit.get(key, [])
        if not items:
            lines.append("- 无")
        else:
            lines.extend(f"- {item}" for item in items)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def ensure_manual_table_untouched(output_dir: Path) -> Optional[float]:
    manual = output_dir / "00_手动输入选题表.md"
    if manual.exists():
        return manual.stat().st_mtime
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="从对标账号库分类生成爆款选题表")
    parser.add_argument("--root", default=None, help="工作区根目录，默认按脚本位置推导")
    parser.add_argument("--input-dir", default=None, help="账号表目录")
    parser.add_argument("--output-dir", default=None, help="爆款选题库输出目录")
    parser.add_argument("--audit-dir", default=None, help="审核报告目录")
    parser.add_argument("--blogger", default=None, help="只处理指定博主文件名，不含扩展名")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    root = Path(args.root).resolve() if args.root else script_path.parents[3]
    input_dir = Path(args.input_dir).resolve() if args.input_dir else root / "02_资产中心" / "03_对标账号库"
    output_dir = Path(args.output_dir).resolve() if args.output_dir else root / "02_资产中心" / "04_爆款选题库"
    audit_dir = Path(args.audit_dir).resolve() if args.audit_dir else root / "03_工作流中心" / "01_短视频主工作流" / "99_运行记录"

    if not input_dir.exists():
        raise SystemExit(f"输入目录不存在：{input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    manual_mtime_before = ensure_manual_table_untouched(output_dir)
    existing = load_existing(output_dir)
    audit: Dict[str, List[str]] = {
        "readable": [],
        "unreadable": [],
        "missing_required": [],
        "missing_topic": [],
        "missing_link": [],
        "long_topic": [],
        "other_reason": [],
    }
    totals = {"inserted": 0, "duplicates": 0, "other": 0, "moved": 0}

    for file_path in iter_input_files(input_dir, args.blogger):
        for row in classify_file(file_path, audit):
            key = row.key()
            existing_category = find_existing_category(existing, key)
            if existing_category == row.category:
                totals["duplicates"] += 1
                continue
            if existing_category and existing_category != row.category:
                existing[existing_category].pop(key, None)
                totals["moved"] += 1
            bucket = existing.setdefault(row.category, {})
            bucket[key] = row
            if not existing_category:
                totals["inserted"] += 1
            if row.category == "其他类型":
                totals["other"] += 1

    for category, filename in CATEGORIES.items():
        rows = sorted(existing.get(category, {}).values(), key=lambda item: (item.blogger, item.published_at, item.topic))
        write_category_table(output_dir / filename, category, rows)

    manual_mtime_after = ensure_manual_table_untouched(output_dir)
    if manual_mtime_before != manual_mtime_after:
        raise SystemExit("保护失败：00_手动输入选题表.md 被修改")

    audit_path = write_audit(audit_dir, audit, totals, output_dir)
    print({
        "inserted": totals["inserted"],
        "duplicates": totals["duplicates"],
        "moved": totals["moved"],
        "other": totals["other"],
        "audit_path": str(audit_path),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
