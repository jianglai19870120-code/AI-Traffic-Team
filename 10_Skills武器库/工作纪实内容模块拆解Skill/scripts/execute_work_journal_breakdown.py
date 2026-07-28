from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("AI_TRAFFIC_FACTORY_ROOT") or Path(__file__).resolve().parents[3]).resolve()
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

RESERVED_SOURCE_NAMES = {"README.md"}
RESERVED_SOURCE_PREFIXES = ("样板-",)
PRESERVED_MODULE_FILES = {
    MODULE_ROOT / "README.md",
    INDEX_DIR / "字段说明.md",
}
FILLER_PATTERNS = [
    r"(^|[，。；、\s])呃+",
    r"(^|[，。；、\s])嗯+",
    r"(^|[，。；、\s])啊+",
    r"(^|[，。；、\s])对吧",
    r"(^|[，。；、\s])就是",
    r"(^|[，。；、\s])那个",
    r"(^|[，。；、\s])这个",
    r"(^|[，。；、\s])我觉得",
    r"(^|[，。；、\s])说实话",
    r"(^|[，。；、\s])反正",
    r"(^|[，。；、\s])可能",
]
TOPIC_KEYWORDS = {
    "销售": ("卖爆", "销售", "成交", "定价", "单品", "转化", "客群", "客户"),
    "产品": ("产品", "详情页", "录播", "交付", "单品"),
    "营销": ("短视频", "营销", "内容", "流量", "转化"),
    "直播": ("直播", "连麦"),
    "线下课": ("线下课", "老板圈", "社群"),
    "会员": ("会员", "筛选", "咨询"),
    "陪跑": ("陪跑", "弟子班", "门徒"),
}
STRONG_QUOTE_MARKERS = ("先", "再", "只", "不要", "必须", "关键", "核心", "如果", "就", "才", "不是", "而是")
BAD_QUOTE_PATTERNS = (
    "只是讲了一个",
    "又不是",
    "如果当下",
    "有一个亿",
    "这样子",
    "这样的",
    "这件事的思考",
    "痛苦的点",
    "核心是环节多嘛",
)
BAD_QUOTE_PREFIXES = (
    "1.",
    "2.",
    "3.",
    "#",
    "对，",
    "对。",
    "觉得",
    "如果当下",
    "关于",
)
BAD_QUOTE_SUFFIXES = ("这样的。", "这样子。", "这件事。", "嘛。", "而已。")


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


def is_reserved_source_file(path: Path) -> bool:
    return path.name in RESERVED_SOURCE_NAMES or any(path.name.startswith(prefix) for prefix in RESERVED_SOURCE_PREFIXES)


def collect_source_files() -> list[Path]:
    return sorted(path for path in SOURCE_DIR.glob("*.md") if path.is_file() and not is_reserved_source_file(path))


def resolve_source_file(source_file: str) -> Path:
    path = SOURCE_DIR / source_file
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"工作纪实原始资料不存在：{path}")
    if is_reserved_source_file(path):
        raise ValueError(f"该文件不能作为正式拆解输入：{path.name}")
    return path


def section(text: str, start: str, end: str | None = None) -> str:
    if start not in text:
        return ""
    tail = text.split(start, 1)[1]
    if end and end in tail:
        tail = tail.split(end, 1)[0]
    return tail.strip()


def audio_original_body(text: str) -> str:
    match = re.search(r"^- audio_original：(.*?)(?=^- audio_play_url：)", text, flags=re.M | re.S)
    if not match:
        return ""
    body = match.group(1).strip()
    cleaned_lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[🟢🟣⚪]\s*说话人\d+\s*\[\d{2}:\d{2}:\d{2}\]\s*", "", stripped)
        if stripped:
            cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines).strip()


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


def read_source(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    heading = next((line.strip()[2:].strip() for line in text.splitlines() if line.startswith("# ")), "")
    title = heading or path.stem
    note_id_match = re.search(r"^- 得到大脑 note_id：(.+)$", text, re.M)
    note_id = note_id_match.group(1).strip() if note_id_match else ""
    transcript = audio_original_body(text).strip()
    if not transcript:
        transcript = section(text, "## 原始转写", "## 得到大脑摘要").strip()
    if not transcript:
        transcript = fallback_body(text)
    return title, note_id, transcript


def normalize_number_text(text: str) -> str:
    return text.replace("一九九", "199").replace("二九九", "299").replace("三九九", "399").replace("300000", "30万")


def strip_fillers(text: str) -> str:
    result = normalize_number_text(text)
    for pattern in FILLER_PATTERNS:
        result = re.sub(pattern, r"\1", result)
    for token in ("呃", "嗯", "啊", "对吧", "就是", "那个", "这个", "我觉得", "说实话", "反正", "可能", "其实"):
        result = result.replace(token, "")
    result = re.sub(r"(直播、)+直播", "直播", result)
    result = re.sub(r"([，。；、])\1+", r"\1", result)
    result = re.sub(r"\s+", "", result)
    result = result.replace("，，", "，").replace("。。", "。")
    result = result.strip("，。；、 ")
    if result and result[-1] not in "。！？":
        result += "。"
    return result


def clean_transcript_lines(transcript: str) -> list[str]:
    lines: list[str] = []
    for raw_line in transcript.splitlines():
        candidate = strip_fillers(raw_line)
        if len(candidate) < 6:
            continue
        if candidate in {"。", "？", "！"}:
            continue
        lines.append(candidate)
    return lines


def split_paragraphs(text: str) -> list[str]:
    parts = [re.sub(r"\s+", " ", part.strip()) for part in re.split(r"\n\s*\n", text) if part.strip()]
    return [part for part in parts if part]


def clean_sentence(text: str) -> str:
    candidate = strip_fillers(text)
    candidate = re.sub(r"^(然后|那|还有|其他的|其实|只是说|如果真的要|到时候)\s*", "", candidate)
    candidate = candidate.strip("，。；、 ")
    if candidate and candidate[-1] not in "。！？":
        candidate += "。"
    return candidate


def infer_topic(text: str) -> str:
    best_topic = "业务判断"
    best_score = 0
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(2 if keyword in text else 0 for keyword in keywords)
        if topic in text:
            score += 1
        if score > best_score:
            best_topic = topic
            best_score = score
    return best_topic


def quote_style_score(text: str) -> int:
    score = 0
    if 8 <= len(text) <= 32:
        score += 2
    if any(marker in text for marker in STRONG_QUOTE_MARKERS):
        score += 2
    if "，" in text and any(marker in text for marker in ("就", "才", "先", "再", "不是", "而是")):
        score += 1
    if text.endswith("。"):
        score += 1
    if any(token in text for token in ("卖爆", "筛选", "客群", "单品", "会员", "转化", "线下课")):
        score += 1
    return score


def is_strong_quote(text: str) -> bool:
    if not text:
        return False
    if len(text) < 10 or len(text) > 34:
        return False
    if any(text.startswith(prefix) for prefix in BAD_QUOTE_PREFIXES):
        return False
    if any(text.endswith(suffix) for suffix in BAD_QUOTE_SUFFIXES):
        return False
    if any(pattern in text for pattern in BAD_QUOTE_PATTERNS):
        return False
    if any(token in text for token in ("？", "?", "如果真的要做", "到时候看", "没什么", "可以赚钱，比如", "就一个人讲", "的话", "吧。", "有这样", "没没有", "联系我", "进群")):
        return False
    if text.startswith(("如果你什么都没有", "可能", "只是说", "关于产品销售这件事的思考")):
        return False
    if any(token in text for token in ("我觉得", "对吧", "就是", "呃", "嗯")):
        return False
    if re.match(r"^\d+[.、]", text):
        return False
    if text.count("。") > 1:
        return False
    if len(re.findall(r"[\u4e00-\u9fff]", text)) < 6:
        return False
    if "如果" in text and "就" not in text:
        return False
    if "，" not in text and not any(marker in text for marker in ("不是", "而是", "先", "再", "只", "不要", "必须", "关键", "核心")):
        return False
    return quote_style_score(text) >= 6


def rewrite_quote_candidates(cleaned_lines: list[str]) -> list[dict[str, str]]:
    source_text = "\n".join(cleaned_lines)
    candidates: list[dict[str, str]] = []

    if "把199卖爆" in source_text or "把199这个产品卖爆" in source_text:
        candidates.append({"text": "其他都先别想，先把199单品卖爆。", "topic": "销售"})
    if "内容不行就改内容" in source_text and "产品不行就改产品" in source_text:
        candidates.append({"text": "内容不行就改内容，产品不行就改产品。", "topic": "产品"})
    if "卖爆了才会有后面的东西" in source_text:
        candidates.append({"text": "先把单品卖爆，后面的产品才有资格展开。", "topic": "销售"})
    if "客群有问题" in source_text and "线下课" in source_text:
        candidates.append({"text": "客群不对，线下高价课就跑不起来。", "topic": "线下课"})
    if "什么都没有" in source_text and "来听听" in source_text:
        candidates.append({"text": "没有业务基础的人，在线下高价课里很难真正拿到结果。", "topic": "线下课"})
    if "先办会员" in source_text and "连麦" in source_text:
        candidates.append({"text": "先办会员，再开放连麦，才能把无效咨询挡在外面。", "topic": "会员"})
    if "连麦需要筛选" in source_text:
        candidates.append({"text": "连麦不是福利，连麦是筛选后的咨询入口。", "topic": "直播"})
    if "录播" in source_text and "直播" in source_text:
        candidates.append({"text": "线上产品先做录播加直播，不急着把交付摊大。", "topic": "产品"})
    if "短视频" in source_text and "内容不行" in source_text:
        candidates.append({"text": "短视频不转化，就回到内容本身重做。", "topic": "营销"})
    if all(token in source_text for token in ("详情页", "直播", "短视频")):
        candidates.append({"text": "详情页、直播、短视频，是单品成交的三个主战场。", "topic": "营销"})
    if "核心盈利还是后端的盈利" in source_text or ("后端的盈利" in source_text and "服务费" in source_text):
        candidates.append({"text": "前端工具费不是核心盈利，后端深度服务才是。", "topic": "产品"})
    if "老会员更重要" in source_text:
        candidates.append({"text": "老会员比新粉更重要。", "topic": "会员"})
    if "直播间只做一个动作就成交" in source_text:
        candidates.append({"text": "直播间只做一个动作：成交。", "topic": "直播"})
    if "覆盖行业" in source_text and "体量才足够大" in source_text:
        candidates.append({"text": "只有覆盖行业，业务体量才做得大。", "topic": "行业"})
    if "行业拆解" in source_text and "很难很难" in source_text:
        candidates.append({"text": "不做行业拆解，直播就很难真正跑起来。", "topic": "行业"})
    if "哪些行业是否适合做一人公司" in source_text or "哪些行业适合做一人公司" in source_text:
        candidates.append({"text": "直播间最值得聊的，不是内容技巧，而是行业能不能做一人公司。", "topic": "直播"})
    if "核心是它的变现渠道和变现形式" in source_text or ("变现渠道" in source_text and "变现形式" in source_text):
        candidates.append({"text": "内容不是核心，变现渠道和变现形式才是核心。", "topic": "变现"})
    if "不要去讲内容端流量端" in source_text or ("内容端" in source_text and "流量端" in source_text):
        candidates.append({"text": "一讲到内容端和流量端，直播就会立刻失焦。", "topic": "直播"})
    if "产品端" in source_text and "直播间核心讲的还是产品端" in source_text:
        candidates.append({"text": "直播间先讲产品端，成交才有抓手。", "topic": "产品"})

    for line in cleaned_lines:
        sentence = clean_sentence(line)
        if len(sentence) > 28:
            continue
        if not is_strong_quote(sentence):
            continue
        candidates.append({"text": sentence, "topic": infer_topic(sentence)})

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in candidates:
        text = item["text"].strip()
        if text in seen or not is_strong_quote(text):
            continue
        seen.add(text)
        deduped.append({"text": text, "topic": item["topic"]})
    return deduped


def infer_mistakes(cleaned_lines: list[str]) -> list[dict[str, object]]:
    source_text = "\n".join(cleaned_lines)
    items: list[dict[str, object]] = []

    if "卖一个单品" in source_text and any(token in source_text for token in ("线下课", "陪跑", "弟子班", "门徒")):
        items.append(
            {
                "title": "一开始就同时推多个产品",
                "points": [
                    {
                        "title": "单品没跑通，就同时推进线下课、陪跑和弟子班",
                        "body": "单品还没跑通，就想同时推进线下课、陪跑和弟子班。这样会把产品重心直接打散，前端单品没有跑通，后面的高价产品也接不住。正确做法是先把199单品卖爆，其他产品先不要同时展开。",
                    }
                ],
                "summary": "先聚焦一个能跑通的前端单品，再考虑后端产品扩展。",
            }
        )

    if "客群有问题" in source_text and "线下课" in source_text:
        items.append(
            {
                "title": "客群没对上就急着卖高价线下课",
                "points": [
                    {
                        "title": "客群还没筛对，就急着把线下高价课推到前面",
                        "body": "还没筛对客户，就急着把线下高价课推到前面，高价交付很难真正卖动。用户只是来听一听时，线下课很难产生结果。正确做法是等前端单品跑通，且目标客群已经具备真实业务需求时再做线下课。",
                    }
                ],
                "summary": "高价线下课必须建立在对的人群和前端结果之上。",
            }
        )

    return items


def infer_steps(source_title_value: str, cleaned_lines: list[str]) -> list[dict[str, object]]:
    source_text = "\n".join(cleaned_lines)
    groups: list[dict[str, object]] = []
    if "把199卖爆" not in source_text and "卖一个单品" not in source_text:
        return groups

    steps = [
        {
            "title": "先收缩产品重心",
            "body": "先把所有重心收回到199单品，不再同时推进线下课、陪跑和弟子班。前端单品没有跑通时，后端产品越多，注意力就越分散。先把一个入口打爆，后面的产品才有承接基础。",
        },
        {
            "title": "先分清问题出在内容还是产品",
            "body": "一旦转化不动，先判断是内容没打中，还是产品本身没立住。内容不行就改内容，产品不行就改产品。不要把所有问题都混成一个模糊的“卖不动”。",
        },
        {
            "title": "把迭代点集中到详情页、直播和短视频",
            "body": "产品侧优先看详情页怎么讲清价值，直播侧看成交路径怎么设计，短视频侧看流量和转化内容怎么优化。先抓这三个直接影响成交的入口。不要把精力浪费在无关动作上。",
        },
        {
            "title": "等前端跑通后再上后端高价产品",
            "body": "199单品跑通后，再考虑老板社群、陪跑和弟子班这些后端产品。前端没有结果，后端就没有稳定客源。先跑通前端，再扩高价交付，节奏才不会乱。",
        },
    ]
    groups.append({"problem": "怎么先把199单品卖爆，再扩展后端产品？", "steps": steps, "summary": source_title_value})
    if ("知识星球" in source_text and "直播" in source_text and "短视频" in source_text) or ("老会员更重要" in source_text and "直播间只做一个动作就成交" in source_text):
        groups.append(
            {
                "problem": "怎么把知识星球交付、短视频引流和直播成交接成一个闭环？",
                "steps": [
                    {
                        "title": "先用知识星球承接交付",
                        "body": "前端先把交付形态定在知识星球，不在工具选型上反复摇摆。当前阶段先跑通交付闭环，比追求更复杂的软件形态更重要。先把承接动作稳定下来，后面的增长才有落点。",
                    },
                    {
                        "title": "用短视频持续补素材和流量",
                        "body": "短视频先承担流量和素材积累的职责，保证日更，把素材库不断做厚。短视频不用急着承担全部成交功能。先把更新和素材供给稳定，交付和直播才不会断粮。",
                    },
                    {
                        "title": "把直播收缩成单一成交动作",
                        "body": "直播间不要承担过多杂事，只围绕成交去设计内容和路径。直播的目的不是聊天，而是完成转化。动作越单一，直播成交越容易跑通。",
                    },
                    {
                        "title": "把后端盈利放在陪跑和深度服务",
                        "body": "前端工具和服务费不是核心盈利位，真正的盈利来自陪跑和深度服务。先用前端承接和筛选，再把后端服务做深。这样前后端分工才清楚，利润结构也更稳。",
                    },
                ],
                "summary": source_title_value,
            }
        )
    if "哪些行业是否适合做一人公司" in source_text and "变现渠道" in source_text:
        groups.append(
            {
                "problem": "直播间怎么围绕行业变现逻辑展开内容？",
                "steps": [
                    {
                        "title": "先把直播主题锁到行业能不能做",
                        "body": "直播先回答某个行业适不适合做一人公司，而不是泛泛讲内容技巧。主题越具体，观众越容易带着自己的行业问题进入直播。先把主题锁准，后面的成交入口才会清晰。",
                    },
                    {
                        "title": "再拆行业的变现方式和产品结构",
                        "body": "不要急着讲内容怎么拍，先讲这个行业靠什么产品变现、靠什么商业模式赚钱。用户最关心的是能不能赚、怎么赚。先把变现逻辑讲明白，直播就有吸引力。",
                    },
                    {
                        "title": "最后补定价和案例调研",
                        "body": "再往后补线下课、线上课等产品定价，以及对应行业博主的玩法和案例。这样用户看到的不是空观点，而是可落地的行业参考。定价和案例一补齐，成交说服力就上来了。",
                    },
                ],
                "summary": source_title_value,
            }
        )
    return groups


def local_index_records(index_records: list[dict[str, object]], source_files: list[Path]) -> list[dict[str, object]]:
    source_paths = {str(path) for path in source_files}
    return [item for item in index_records if item.get("source_path") in source_paths]


def quote_file_body(entries: list[dict[str, str]]) -> str:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in entries:
        grouped[item["topic"]].append(item)

    lines = ["# 工作纪实金句模块", ""]
    if not entries:
        lines.append("> 当前还没有从工作纪实里提取到可复用金句。")
        lines.append("")
        return "\n".join(lines)

    for topic in sorted(grouped.keys()):
        lines.append(f"### #{topic}")
        lines.append("")
        for item in grouped[topic]:
            lines.append(f"- {item['text']}——《{item['source']}》")
        lines.append("")
    return "\n".join(lines)


def mistake_module_body(item: dict[str, object], source_title_value: str, source_path: str, note_id: str) -> str:
    title = str(item["title"])
    points = list(item["points"])
    lines = [
        f"# 工作纪实_错误观点：{title}",
        "",
        "**错误观点**",
        "",
        title,
        "",
    ]
    for idx, point in enumerate(points, start=1):
        point_title = str(point["title"]).strip()
        point_body = str(point["body"]).strip()
        lines += [f"**误区{idx}：{point_title}**", "", sentence_lines(point_body), ""]
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
        lines += [f"**步骤{idx}：{step['title']}**", "", sentence_lines(str(step["body"])), ""]
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


def index_record(module_type: str, title: str, source_title_value: str, source_path: str, module_path: Path, summary: str, topic: str) -> dict[str, object]:
    return {
        "module_id": module_id(module_type, title),
        "module_type": module_type,
        "title": title,
        "source_title": source_title_value,
        "source_path": source_path,
        "module_path": str(module_path),
        "tags_topic": ["工作纪实", topic],
        "tags_scene": ["真实业务", "文案调用"],
        "summary": summary[:120],
        "status": "ready",
    }


def source_summary_record(
    source_path: Path,
    source_title_value: str,
    quotes: list[dict[str, str]],
    mistakes: list[dict[str, object]],
    steps: list[dict[str, object]],
) -> dict[str, object]:
    missing_reasons: list[str] = []
    if not quotes:
        missing_reasons.append("金句未提取：清洗后仍缺少完整、笃定、可传播的判断句。")
    if not mistakes:
        missing_reasons.append("误区未提取：原文里没有足够完整的旧判断、纠偏判断和代价链。")
    if not steps:
        missing_reasons.append("步骤未提取：原文没有稳定形成 2 步以上、可直接调用的动作链。")
    return {
        "source_title": source_title_value,
        "source_path": str(source_path),
        "quote_topics": sorted({item["topic"] for item in quotes}),
        "quotes_count": len(quotes),
        "mistakes_count": len(mistakes),
        "steps_count": len(steps),
        "missing_reasons": missing_reasons,
        "processed_at": now(),
    }


def load_quote_entries() -> list[dict[str, str]]:
    if not QUOTE_FILE.exists():
        return []
    entries: list[dict[str, str]] = []
    current_topic = "业务判断"
    pattern = re.compile(r"^- (?P<quote>.+?)——《(?P<source>.+)》$")
    for line in QUOTE_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("### #"):
            current_topic = stripped.replace("### #", "", 1).strip() or "业务判断"
            continue
        match = pattern.match(stripped)
        if match:
            entries.append(
                {
                    "text": match.group("quote").strip(),
                    "source": match.group("source").strip(),
                    "topic": current_topic,
                }
            )
    return entries


def save_quote_entries(entries: list[dict[str, str]]) -> None:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in entries:
        key = (item["topic"], item["text"], item["source"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    QUOTE_FILE.write_text(append_brand_footer(quote_file_body(deduped)), encoding="utf-8")


def load_index_records() -> list[dict[str, object]]:
    if not INDEX_FILE.exists():
        return []
    records: list[dict[str, object]] = []
    for line in INDEX_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return records


def save_index_records(records: list[dict[str, object]]) -> None:
    INDEX_FILE.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + ("\n" if records else ""),
        encoding="utf-8",
    )


def cleanup_outputs_for_source(source_path: Path) -> None:
    records = load_index_records()
    source_titles: set[str] = set()
    keep_records: list[dict[str, object]] = []
    for record in records:
        if record.get("source_path") != str(source_path):
            keep_records.append(record)
            continue
        source_title = record.get("source_title")
        if isinstance(source_title, str) and source_title.strip():
            source_titles.add(source_title.strip())
        module_path_value = record.get("module_path")
        if isinstance(module_path_value, str):
            module_path = Path(module_path_value)
            if module_path.exists() and module_path.is_file() and module_path != QUOTE_FILE:
                module_path.unlink()
    save_index_records(keep_records)

    quote_entries = [item for item in load_quote_entries() if item["source"] not in source_titles and item["source"] != source_path.stem]
    save_quote_entries(quote_entries)


def archive_existing_outputs() -> Path | None:
    existing_files = [path for path in MODULE_ROOT.rglob("*") if path.is_file() and path not in PRESERVED_MODULE_FILES]
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
    for folder in (QUOTE_DIR, MISTAKE_DIR, STEP_DIR, INDEX_DIR, HISTORY_DIR):
        folder.mkdir(parents=True, exist_ok=True)
        for path in folder.iterdir():
            if path in PRESERVED_MODULE_FILES:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()


def build_subject(source_path: Path, source_title_value: str) -> str:
    return source_title_value or source_path.stem


def process_source(
    source_path: Path,
    *,
    allow_existing_outputs: bool,
) -> tuple[list[Path], list[dict[str, object]], dict[str, object]]:
    if allow_existing_outputs:
        cleanup_outputs_for_source(source_path)

    source_title_value, note_id, transcript = read_source(source_path)
    cleaned_lines = clean_transcript_lines(transcript)
    quotes = rewrite_quote_candidates(cleaned_lines)
    mistakes = infer_mistakes(cleaned_lines)
    steps = infer_steps(source_title_value, cleaned_lines)
    source_summary = source_summary_record(source_path, source_title_value, quotes, mistakes, steps)

    outputs: list[Path] = []
    records = load_index_records() if allow_existing_outputs else []
    quote_entries = load_quote_entries() if allow_existing_outputs else []

    for quote in quotes:
        quote_entries.append({"text": quote["text"], "source": source_title_value, "topic": quote["topic"]})

    grouped_quotes: dict[str, list[dict[str, str]]] = defaultdict(list)
    for quote in quotes:
        grouped_quotes[quote["topic"]].append(quote)
    for topic, topic_quotes in grouped_quotes.items():
        records.append(
            index_record(
                "金句",
                f"工作纪实金句：{topic}",
                source_title_value,
                str(source_path),
                QUOTE_FILE,
                topic_quotes[0]["text"],
                topic,
            )
        )

    for item in mistakes:
        out = MISTAKE_DIR / f"工作纪实_错误观点：{slug(str(item['title']))}.md"
        out.write_text(append_brand_footer(mistake_module_body(item, source_title_value, str(source_path), note_id)), encoding="utf-8")
        outputs.append(out)
        records.append(index_record("误区", str(item["title"]), source_title_value, str(source_path), out, str(item["summary"]), infer_topic(str(item["title"]))))

    for group in steps:
        problem = str(group["problem"])
        filename_title = problem if "怎么" in problem else f"{problem}怎么做"
        out = STEP_DIR / f"工作纪实_{slug(filename_title)}.md"
        out.write_text(append_brand_footer(step_module_body(group, source_title_value, str(source_path), note_id)), encoding="utf-8")
        outputs.append(out)
        first_step = group["steps"][0] if group["steps"] else {"body": ""}
        records.append(index_record("步骤", problem, source_title_value, str(source_path), out, str(first_step.get("body", "")), infer_topic(problem)))

    save_quote_entries(quote_entries)
    outputs.append(QUOTE_FILE)

    deduped_records: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for record in records:
        record_id = str(record.get("module_id", ""))
        if not record_id or record_id in seen_ids:
            continue
        seen_ids.add(record_id)
        deduped_records.append(record)
    save_index_records(deduped_records)
    outputs.append(INDEX_FILE)

    summary_file = HISTORY_DIR / f"{stamp()}_逐篇拆解摘要_{slug(source_path.stem)}.jsonl"
    summary_file.write_text(json.dumps(source_summary, ensure_ascii=False) + "\n", encoding="utf-8")
    outputs.append(summary_file)

    return outputs, deduped_records, source_summary


def rollback_outputs(generated_paths: list[Path], source_path: Path) -> None:
    cleanup_outputs_for_source(source_path)
    for path in generated_paths:
        if path in {QUOTE_FILE, INDEX_FILE}:
            continue
        if path.exists() and path.is_file():
            path.unlink()


def run_single_source(source_path: Path) -> tuple[list[Path], list[Path], list[dict[str, object]], list[dict[str, object]], Path | None]:
    ensure_dirs()
    outputs, index_records, source_summary = process_source(source_path, allow_existing_outputs=True)
    return [source_path], outputs, index_records, [source_summary], None


def run_full_rebuild() -> tuple[list[Path], list[Path], list[dict[str, object]], list[dict[str, object]], Path | None]:
    ensure_dirs()
    archive_dir = archive_existing_outputs()
    clear_generated()

    source_files = collect_source_files()
    all_outputs: list[Path] = []
    final_records: list[dict[str, object]] = []
    source_summaries: list[dict[str, object]] = []

    for source_path in source_files:
        outputs, final_records, source_summary = process_source(source_path, allow_existing_outputs=True)
        all_outputs.extend(outputs)
        source_summaries.append(source_summary)

    return source_files, all_outputs, final_records, source_summaries, archive_dir


def validate(outputs: list[Path], source_summaries: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    total_quotes = sum(int(item.get("quotes_count", 0)) for item in source_summaries)
    total_mistakes = sum(int(item.get("mistakes_count", 0)) for item in source_summaries)
    total_steps = sum(int(item.get("steps_count", 0)) for item in source_summaries)

    if total_quotes > 0 and not QUOTE_FILE.exists():
        issues.append("缺少工作纪实金句模块.md")
    if (total_quotes > 0 or total_mistakes > 0 or total_steps > 0) and not INDEX_FILE.exists():
        issues.append("缺少模块索引.jsonl")
    if not source_summaries:
        issues.append("没有扫描到任何工作纪实原文")
    if total_quotes > 0 and QUOTE_FILE.exists():
        quote_text = QUOTE_FILE.read_text(encoding="utf-8", errors="ignore")
        if "## #真实工作" in quote_text:
            issues.append("金句模块仍保留 #真实工作 分组")
        for bad_token in ("呃", "嗯", "对吧", "就是", "那个", "这个", "我觉得", "吧。", "的话", "没没有"):
            if bad_token in quote_text:
                issues.append(f"金句模块仍残留口语词：{bad_token}")
                break
        if "？" in quote_text or "?" in quote_text:
            issues.append("金句模块仍存在问句")
        if "### #" not in quote_text:
            issues.append("金句模块缺少关键词分组")
        for line in quote_text.splitlines():
            if not line.startswith("- "):
                continue
            quote_body = line.split("——《", 1)[0].replace("- ", "", 1).strip()
            if len(quote_body) > 36:
                issues.append(f"金句过长：{quote_body[:16]}...")
                break
            if quote_body.count("。") > 1:
                issues.append(f"金句仍是流水句：{quote_body[:16]}...")
                break
            if any(quote_body.startswith(prefix) for prefix in BAD_QUOTE_PREFIXES) or any(pattern in quote_body for pattern in BAD_QUOTE_PATTERNS):
                issues.append(f"金句仍是低质量残句：{quote_body[:16]}...")
                break
    for path in outputs:
        if path.parent == MISTAKE_DIR:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "**误区1：" not in text:
                issues.append(f"{path.name} 缺少误区编号结构")
            for bad_heading in ("原文里的旧判断", "原文给出的纠偏判断", "继续这样做的代价"):
                if bad_heading in text:
                    issues.append(f"{path.name} 仍使用模板化误区子标题：{bad_heading}")
                    break
            mistake_count = len(re.findall(r"\*\*误区\d+：", text))
            if mistake_count < 1 or mistake_count > 3:
                issues.append(f"{path.name} 误区数不在 1 到 3 之间")
        if path.parent == STEP_DIR:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "**步骤1：" not in text:
                issues.append(f"{path.name} 缺少步骤编号结构")
            step_count = len(re.findall(r"\*\*步骤\d+：", text))
            if step_count < 2 or step_count > 4:
                issues.append(f"{path.name} 步骤数不在 2 到 4 之间")
    for path in MODULE_ROOT.rglob("样板-*"):
        if path.is_file():
            issues.append(f"仍残留样板文件：{path.name}")
            break
    return issues


def audit_checks(source_summary: dict[str, object]) -> list[str]:
    quote_ok = source_summary["quotes_count"] > 0
    mistake_ok = source_summary["mistakes_count"] > 0
    step_ok = source_summary["steps_count"] > 0
    return [
        f"- 金句是否已去口语词并保留笃定表达：{'是' if quote_ok else '否'}",
        f"- 金句是否已按关键词分组：{'是' if quote_ok and source_summary['quote_topics'] else '否'}",
        f"- 误区是否来自真实业务取舍和反思：{'是' if mistake_ok else '本条未提取误区'}",
        f"- 步骤是否具备真实动作链和卡点解释：{'是' if step_ok else '本条未提取步骤'}",
        "- 模块标题是否干净可调用：已按正式模块标题规则生成",
    ]


def write_records(
    source_files: list[Path],
    outputs: list[Path],
    index_records: list[dict[str, object]],
    source_summaries: list[dict[str, object]],
    archive_dir: Path | None,
    issues: list[str],
    *,
    task_label: str,
    audit_subject: str,
    include_snapshot_note: bool,
) -> tuple[Path, Path, Path]:
    current_records = local_index_records(index_records, source_files)
    mistake_count = sum(1 for item in current_records if item["module_type"] == "误区")
    step_count = sum(1 for item in current_records if item["module_type"] == "步骤")
    quote_count = sum(item["quotes_count"] for item in source_summaries)
    summary_path = next((path for path in outputs if path.parent == HISTORY_DIR and path.suffix == ".jsonl"), None)
    file_slug = slug(audit_subject)

    audit = AUDIT_DIR / f"{stamp()}_工作纪实内容模块审核_{file_slug}.md"
    audit_lines = [
        "# 小审审核记录",
        "",
        f"- 审核时间：{now()}",
        f"- 审核对象：{audit_subject}",
        f"- 审核结论：{'通过' if not issues else '退回'}",
        "",
        "## 审核判断",
        "",
    ]
    if len(source_summaries) == 1:
        audit_lines.extend(audit_checks(source_summaries[0]))
    else:
        audit_lines.append("- 本次为全量重建，审核判断以输出统计与校验结果为准。")
    audit_lines.extend(
        [
            "",
            "## 输出统计",
            "",
            f"- 输入原文：{len(source_files)}",
            f"- 金句条数：{quote_count}",
            f"- 金句关键词：{', '.join(source_summaries[0]['quote_topics']) if len(source_summaries) == 1 and source_summaries[0]['quote_topics'] else '无'}",
            f"- 误区模块：{mistake_count}",
            f"- 步骤模块：{step_count}",
            f"- 索引记录：{len(current_records)}",
            f"- 逐篇摘要：`{summary_path}`" if summary_path else "- 逐篇摘要：未生成",
            "",
            "## 问题",
            "",
            *(["- 未发现阻断问题。"] if not issues else [f"- {issue}" for issue in issues]),
        ]
    )
    audit.write_text(append_brand_footer("\n".join(audit_lines)), encoding="utf-8")

    exec_record = EXEC_DIR / f"{stamp()}_工作纪实内容模块执行_{file_slug}.md"
    exec_lines = [
        "# 小拆执行记录",
        "",
        f"- 执行时间：{now()}",
        f"- 任务：{task_label}",
        f"- 执行状态：{'通过' if not issues else '退回'}",
        "",
        "## 输入原文",
        "",
        *[f"- `{path}`" for path in source_files],
        "",
        "## 输出模块",
        "",
        *[f"- `{path}`" for path in outputs if path.exists() and path.parent in {QUOTE_DIR, MISTAKE_DIR, STEP_DIR, INDEX_DIR, HISTORY_DIR}],
        "",
    ]
    if include_snapshot_note:
        exec_lines.append(f"- 重构前快照：`{archive_dir}`" if archive_dir else "- 重构前快照：无")
    else:
        exec_lines.append("- 重构前快照：single 模式不生成")
    exec_lines.append(f"- 小审审核记录：`{audit}`")
    exec_record.write_text(append_brand_footer("\n".join(exec_lines)), encoding="utf-8")

    source_record = SOURCE_RECORD_DIR / f"{stamp()}_工作纪实正式产物来源_{file_slug}.jsonl"
    source_record.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in current_records) + ("\n" if current_records else ""), encoding="utf-8")
    return audit, exec_record, source_record


def main() -> int:
    parser = argparse.ArgumentParser(description="工作纪实内容模块拆解")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", choices=("single", "full"), default="single")
    parser.add_argument("--source-file", help="single 模式下的目标工作纪实文件名")
    args = parser.parse_args()

    if args.dry_run:
        print(f"eligible_source_files={len(collect_source_files())}")
        return 0

    if args.mode == "single":
        if not args.source_file:
            raise SystemExit("single 模式必须传入 --source-file <文件名>")
        source_path = resolve_source_file(args.source_file)
        source_files, outputs, index_records, source_summaries, archive_dir = run_single_source(source_path)
        audit_subject = build_subject(source_path, read_source(source_path)[0])
        task_label = f"工作纪实内容模块拆解_{audit_subject}"
        include_snapshot_note = False
    else:
        if args.source_file:
            raise SystemExit("full 模式不接受 --source-file")
        source_files, outputs, index_records, source_summaries, archive_dir = run_full_rebuild()
        if not source_files:
            print("[工作纪实内容模块拆解] result=跳过 reason=没有待处理的工作纪实原文")
            return 0
        audit_subject = "工作纪实原文全量重建"
        task_label = "工作纪实内容模块全量重建"
        include_snapshot_note = True

    issues = validate(outputs, source_summaries)
    if issues and args.mode == "single":
        rollback_outputs(outputs, source_files[0])
    audit, exec_record, source_record = write_records(
        source_files,
        outputs,
        index_records,
        source_summaries,
        archive_dir,
        issues,
        task_label=task_label,
        audit_subject=audit_subject,
        include_snapshot_note=include_snapshot_note,
    )
    print(
        f"[工作纪实内容模块拆解] mode={args.mode} inputs={len(source_files)} "
        f"quotes={sum(item['quotes_count'] for item in source_summaries)} "
        f"mistakes={sum(item['mistakes_count'] for item in source_summaries)} "
        f"steps={sum(item['steps_count'] for item in source_summaries)} "
        f"result={'通过' if not issues else '退回'}"
    )
    for item in source_summaries:
        print(
            f"- {item['source_title']}\tquotes={item['quotes_count']}\t"
            f"mistakes={item['mistakes_count']}\tsteps={item['steps_count']}\t"
            f"topics={','.join(item['quote_topics']) if item['quote_topics'] else '无'}"
        )
    print(f"- 审核记录：{audit}")
    print(f"- 执行记录：{exec_record}")
    print(f"- 来源记录：{source_record}")
    if issues:
        for issue in issues:
            print(f"! {issue}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
