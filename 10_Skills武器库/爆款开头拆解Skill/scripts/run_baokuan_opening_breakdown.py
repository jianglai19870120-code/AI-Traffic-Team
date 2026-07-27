from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from brand_footer import append_brand_footer

REQUIRED_FIELDS = ["视频信息", "点赞数", "文案"]
SELECTION_FIELDS = ["博主名", "视频信息", "链接", "状态", "备注"]
FUNCTION_LABELS = [
    "利益承诺",
    "结果承诺",
    "危机提醒",
    "风险警告",
    "人群点名",
    "身份代入",
    "痛点描述",
    "现象描述",
    "场景引入",
    "认知提问",
    "悬念追问",
    "反常识判断",
    "数据引入",
    "数据证明",
    "案例引入",
    "案例证明",
    "连续确认",
    "时间对比",
    "结果对比",
    "权威背书",
    "降低门槛",
    "放大后果",
    "趋势推演",
    "方法预告",
    "内容预告",
    "降低防备",
    "观点收束",
    "冲突制造",
    "故事引入",
    "结果悬念",
]
ARG_ONLY_TOKENS = {"能", "对", "是", "没错", "好", "那么", "所以"}
FILLER_PREFIX_RE = re.compile(r"^(呃|嗯|啊|诶|额|那个|就是)[，,、\s]*")
CLAUSE_SPLIT_HINTS = (
    "但",
    "但是",
    "而是",
    "所以",
    "结果",
    "后来",
    "前段时间",
    "最近",
    "如果",
    "那么",
    "好",
)


def clean_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\r\n\t]+', "_", str(value or "")).strip()
    return value[:60] or "未命名"


def normalize_space(value: str) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def normalize_match(value: str) -> str:
    return normalize_space(value).strip().lower()


def clean_script(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    replacements = {
        "cloud code": "Claude Code",
        "Cloud code": "Claude Code",
        "claude code": "Claude Code",
        "gemini": "Gemini",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def title_from(info: str) -> str:
    text = normalize_space(info)
    text = re.sub(r"#\S+", "", text).strip()
    if not text:
        return "待补选题"
    title = re.split(r"[。！？!?\n]", text)[0].strip()
    return title[:40] if title else text[:40]


def read_xlsx(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    import openpyxl

    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception as exc:
        raise RuntimeError(f"{path.name} 不是可读取的标准 xlsx 文件: {exc}") from exc
    if not rows:
        return [], []
    headers = [str(value or "").strip() for value in rows[0]]
    data: list[dict[str, str]] = []
    for row in rows[1:]:
        if not any(cell not in (None, "") for cell in row):
            continue
        data.append({headers[idx]: str(value or "").strip() for idx, value in enumerate(row) if idx < len(headers)})
    return headers, data


def split_markdown_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in text:
        if char == "\\" and not escaped:
            escaped = True
            current.append(char)
            continue
        if char == "|" and not escaped:
            cells.append("".join(current).strip().replace("\\|", "|"))
            current = []
        else:
            current.append(char)
        escaped = False
    cells.append("".join(current).strip().replace("\\|", "|"))
    return cells


def is_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells if cell.strip())


def read_selection_file(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise RuntimeError(f"选中清单不存在: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    table_rows = [split_markdown_row(line) for line in lines if line.strip().startswith("|")]
    if len(table_rows) < 2:
        raise RuntimeError(f"选中清单未找到标准 markdown 表格: {path}")
    headers = [cell.strip() for cell in table_rows[0]]
    missing = [field for field in SELECTION_FIELDS if field not in headers]
    if missing:
        raise RuntimeError(f"选中清单缺少字段: {missing}")
    records: list[dict[str, str]] = []
    for cells in table_rows[1:]:
        if is_separator_row(cells):
            continue
        row = {headers[idx]: (cells[idx].strip() if idx < len(cells) else "") for idx in range(len(headers))}
        if not any(row.values()):
            continue
        records.append(row)
    if not records:
        raise RuntimeError(f"选中清单没有有效记录: {path}")
    return records


def resolve_blogger_xlsx(input_dir: Path, blogger_name: str) -> Path:
    if not blogger_name:
        raise RuntimeError("选中清单存在缺少 `博主名` 的记录")
    expected = input_dir / f"{blogger_name}.xlsx"
    if expected.exists() and not expected.name.startswith("~$"):
        return expected
    normalized = normalize_match(clean_filename(blogger_name))
    matches = [
        path
        for path in input_dir.glob("*.xlsx")
        if not path.name.startswith("~$") and normalize_match(clean_filename(path.stem)) == normalized
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"找不到博主表格: {blogger_name}，目录: {input_dir}")
    raise RuntimeError(f"博主名 `{blogger_name}` 命中多个 xlsx: {[path.name for path in matches]}")


def find_source_row(source_path: Path, selection: dict[str, str]) -> tuple[dict[str, str], int]:
    headers, rows = read_xlsx(source_path)
    missing = [field for field in REQUIRED_FIELDS if field not in headers]
    if missing:
        raise RuntimeError(f"{source_path.name} 缺少字段: {missing}")
    link = normalize_space(selection.get("链接", ""))
    video_info = normalize_space(selection.get("视频信息", ""))
    if not link and not video_info:
        raise RuntimeError(f"选中清单记录无效，`链接` 和 `视频信息` 不能同时为空: {selection}")
    if link:
        matches = [
            (idx, row)
            for idx, row in enumerate(rows, start=2)
            if normalize_match(row.get("链接", "")) == normalize_match(link)
        ]
        if len(matches) == 1:
            return matches[0][1], matches[0][0]
        if len(matches) > 1:
            raise RuntimeError(f"{source_path.name} 中链接重复，无法自动判断: {link}")
        raise RuntimeError(f"{source_path.name} 未按链接命中记录: {link}")
    matches = [
        (idx, row)
        for idx, row in enumerate(rows, start=2)
        if normalize_match(row.get("视频信息", "")) == normalize_match(video_info)
    ]
    if len(matches) == 1:
        return matches[0][1], matches[0][0]
    if len(matches) > 1:
        raise RuntimeError(f"{source_path.name} 中 `视频信息` 重复，必须在清单补充链接: {video_info}")
    raise RuntimeError(f"{source_path.name} 未按视频信息命中记录: {video_info}")


def strip_leading_title_lines(text: str) -> str:
    parts = [part.strip() for part in re.split(r"(?<=[。！？!?\n])", text) if part.strip()]
    cleaned_parts: list[str] = []
    skipped = False
    for part in parts:
        normalized = part.strip()
        if not skipped and (
            normalized.startswith("选题：")
            or normalized.startswith("标题：")
            or normalized.startswith("备注：")
            or normalized.startswith("主题：")
            or normalized.startswith("# ")
            or normalized.startswith("【标题】")
        ):
            skipped = True
            continue
        cleaned_parts.append(normalized)
    return " ".join(cleaned_parts).strip()


def split_base_sentences(text: str) -> list[str]:
    text = strip_leading_title_lines(clean_script(text))
    return [part.strip() for part in re.split(r"(?<=[。！？!?])", text) if part.strip()]


def clean_function_sentence(sentence: str) -> str:
    text = normalize_space(sentence).strip("，,。 ")
    previous = None
    while previous != text:
        previous = text
        text = FILLER_PREFIX_RE.sub("", text).strip("，,。 ")
    if text and text[-1] not in "。！？!?":
        if re.search(r"(吗|呢|么|什么|为什么|怎么办|能不能|是不是|有没有|到底)$", text):
            text += "？"
        else:
            text += "。"
    return text


def is_connector_only(text: str) -> bool:
    normalized = clean_function_sentence(text).strip("。！？!?")
    return normalized in ARG_ONLY_TOKENS


def maybe_split_by_comma(sentence: str) -> list[str]:
    if "，" not in sentence and "," not in sentence:
        return [sentence.strip()]
    text = sentence.replace(",", "，")
    parts = [part.strip() for part in text.split("，") if part.strip()]
    if len(parts) < 2:
        return [sentence.strip()]
    if is_connector_only(parts[0]):
        return [sentence.strip()]
    if len(parts) == 2:
        first, second = parts
        if any(second.startswith(token) for token in ("说", "就是", "其实", "也就是", "比如")):
            return [sentence.strip()]
        if any(first.endswith(token) for token in ("报告", "数据", "案例")):
            return [sentence.strip()]
        if any(second.startswith(token) for token in ("因为", "也就是说", "换句话说")):
            return [sentence.strip()]
    built: list[str] = []
    current = parts[0]
    for part in parts[1:]:
        should_split = any(part.startswith(hint) for hint in CLAUSE_SPLIT_HINTS)
        if part.startswith("因为") and len(current) <= 16:
            should_split = False
        if should_split:
            built.append(current.strip("，"))
            current = part
        else:
            current = f"{current}，{part}"
    built.append(current.strip("，"))
    return [item.strip() for item in built if item.strip()]


def extract_function_sentences(script: str, limit: int = 5) -> list[str]:
    function_sentences: list[str] = []
    for base in split_base_sentences(script):
        for item in maybe_split_by_comma(base):
            normalized = clean_function_sentence(item)
            if not normalized or is_connector_only(normalized):
                continue
            function_sentences.append(normalized)
            if len(function_sentences) >= limit:
                return function_sentences
    return function_sentences


def detect_core_function(sentence: str, index: int, total: int) -> str:
    text = sentence.strip()
    if re.search(r"(不是.+而是|恰恰相反|真正的问题|可以作弊|正大光明的作弊|不是你|而是你)", text):
        return "反常识判断"
    if re.search(r"(我们真的要|提前为自己想想出路|来不及|已经晚了|别再|一定要小心)", text):
        return "危机提醒"
    if re.search(r"(什么概念|你猜|你知道吗|这还没完|更狠的是)", text):
        return "悬念追问"
    if index > 1 and re.search(r"^(能|对|是|没错)[，,， ]*(那|如果|再|而且)", text):
        return "连续确认"
    if re.search(r"(内容会很长|没打草稿|聊到哪儿|数据呢.*无所谓|随时可能会把它删|简单分享)", text):
        return "降低防备"
    if re.search(r"(报告|数据|统计|研究|显示|公布|预测|达到|同比|增长到|下降到)", text):
        if re.search(r"(在\d{2,4}年|到了\d{2,4}年|过去|现在|今年|去年|前年|年底|下半年)", text) and re.search(r"\d", text):
            return "时间对比" if index >= 4 else "数据证明"
        return "数据证明"
    if re.search(r"(如果.*再过|按照这个速度|继续.*发展|意味着|会有一半|未来|越来越)", text):
        return "趋势推演"
    if re.search(r"(怎么|如何|为什么|是不是|能不能|靠.+还是靠|主要是靠|到底)", text):
        return "认知提问"
    if re.search(r"(你想在|想要|想.*赚|赚点|赚到|做到|拿到|跑通|过万粉|翻了|多赚)", text):
        return "利益承诺" if index == 1 else "结果对比"
    if re.search(r"(危险|风险|致命|后果|代价|会越来越难)", text):
        return "风险警告"
    if re.search(r"(很多人|大多数人|普通人|现在的问题|最容易)", text):
        return "现象描述"
    if re.search(r"(比如说|举个例子|如果你在|我有个朋友|学生|学员|有个人|有人)", text):
        return "案例引入"
    if re.search(r"(以前|现在|过去|今天|今年|前几年|前段时间)", text):
        return "时间对比"
    if re.search(r"(接下来|下面|这条视频|我只讲|我会讲|今天讲)", text):
        return "内容预告" if index == total or index >= 3 else "方法预告"
    if re.search(r"(先别急|不要急|别急着|先说结论)", text):
        return "降低防备"
    if re.search(r"(痛点|卡住|不会|不知道|难点|做不成)", text):
        return "痛点描述"
    if index == 1:
        return "结果承诺"
    return "内容预告"


def build_structure(sentence: str, core_function: str) -> str:
    text = sentence.strip()
    if core_function == "认知提问":
        if re.search(r"(靠.+还是靠|主要是靠)", text):
            return "目标结果＋两个认知选项＋直接提问"
        return "核心问题＋限制条件＋直接提问"
    if core_function == "悬念追问":
        return "前置信息＋意义追问＋等待解释"
    if core_function == "结果承诺":
        return "明确结果＋目标对象＋结果承诺"
    if core_function == "危机提醒":
        return "共同人群＋未来风险＋行动提醒"
    if core_function == "风险警告":
        return "问题升级＋风险放大＋后果提醒"
    if core_function == "现象描述":
        return "常见人群＋普遍现象＋问题定位"
    if core_function == "数据证明":
        return "信息来源＋现实趋势＋具体数据"
    if core_function == "案例引入":
        if re.search(r"(如果你在|时候|年)", text):
            return "历史时间节点＋具体机会＋结果追问"
        return "人物或场景＋具体事件＋案例引入"
    if core_function == "连续确认":
        return "确认上一答案＋第二案例＋继续追问"
    if core_function == "时间对比":
        return "过去时间与数据＋当前时间与数据＋增长对比"
    if core_function == "结果对比":
        return "两种结果＋差异放大＋结果对比"
    if core_function == "反常识判断":
        return "常识对象＋反常识判断＋强化表达"
    if core_function == "方法预告":
        return "目标问题＋方法数量＋方法预告"
    if core_function == "内容预告":
        return "主题限定＋后文安排＋内容预告"
    if core_function == "降低防备":
        if re.search(r"(数据呢|无所谓|删了)", text):
            return "弱化数据导向＋随时删除预告＋降低功利期待"
        if re.search(r"(内容会很长|没打草稿)", text):
            return "长内容预期＋随口表达＋降低防备"
        return "弱化说教＋聊天口吻＋继续展开"
    if core_function == "痛点描述":
        return "目标人群＋现实卡点＋痛点描述"
    if core_function == "利益承诺":
        if re.search(r"(年|月|下半年|今天|现在)", text):
            return "明确时间＋低门槛结果＋机会方法预告"
        return "目标对象＋明确收益＋利益承诺"
    if core_function == "趋势推演":
        return "当前预测＋延续速度＋未来结果"
    if core_function == "权威背书":
        return "权威来源＋核心观点＋现实关联"
    if core_function == "故事引入":
        return "人物出现＋特殊处境＋故事开场"
    if core_function == "结果悬念":
        return "异常结果＋原因留白＋结果悬念"
    return "关键信息＋表达动作＋句内承诺"


def detect_argument_pattern(sentences: list[str], functions: list[str]) -> str:
    joined = " ".join(sentences)
    function_set = set(functions)
    if "连续确认" in function_set or ("案例引入" in function_set and "认知提问" in function_set):
        return "历史案例＋连续追问"
    if "数据证明" in function_set and "时间对比" in function_set:
        return "数据＋时间对比＋趋势推演"
    if "认知提问" in function_set and "痛点描述" in function_set:
        return "现实痛点＋连续提问"
    if "案例引入" in function_set and ("悬念追问" in function_set or "危机提醒" in function_set):
        return "个人故事＋冲突悬念"
    if "反常识判断" in function_set:
        return "旧认知＋直接纠偏"
    if "结果对比" in function_set:
        return "两种路径＋结果对比"
    if "结果承诺" in function_set and ("方法预告" in function_set or "内容预告" in function_set):
        return "结果承诺＋方法预告"
    if re.search(r"(报告|研究|专家|CEO|作者|采访|播客)", joined):
        return "权威观点＋现实解释"
    if re.search(r"(场景|你在|如果你是|对普通人来说)", joined):
        return "场景代入＋身份共鸣"
    return "历史案例＋连续追问"


def build_skeleton(argument_pattern: str, functions: list[str], structures: list[str]) -> tuple[list[str], list[str]]:
    if argument_pattern == "数据＋时间对比＋趋势推演":
        return (
            [
                "先给出一个关于个人未来的警告",
                "引用一份报告或数据，抛出异常变化",
                "追问这个数字意味着什么",
                "用过去和现在的数据进行对比",
                "按照当前速度推演未来，得出一个严重结果",
            ],
            [
                "我们真的要提前为自己想想【出路／应对办法】了。",
                "前段时间我看到一份报告，说【某个群体／某种现象】在今年很有可能达到【惊人数据】。",
                "这是什么概念呢？",
                "这个数字在【过去时间】才只有【过去数据】，到了【最近时间】已经达到【当前数据】。",
                "如果今年真的达到【目标数据】，那么按照这个速度继续发展，再过【时间】，就意味着【与普通人密切相关的严重结果】。",
            ],
        )
    if argument_pattern == "历史案例＋连续追问":
        return (
            [
                "提出一个当下相关的低门槛利益问题",
                "用聊天式表达降低说教感",
                "抛出一个认知二选一问题",
                "列举第一个历史机会并追问结果",
                "确认上一答案，再列举第二个历史机会继续追问",
            ],
            [
                "如果你想在【时间范围】获得【低门槛结果】，有哪些【机会或方法】？",
                "这条视频我简单分享一下。",
                "我先问你个问题，你觉得【目标结果】主要靠【选项A】，还是靠【选项B】？",
                "比如说，如果你在【历史时间节点1】做了【具体机会1】，你觉得能不能获得【结果】？",
                "能，那如果你在【历史时间节点2】做了【具体机会2】，能不能获得【结果】？",
            ],
        )
    if argument_pattern == "旧认知＋直接纠偏":
        return (
            [
                "先抛出一个反常识判断",
                "降低用户对长内容或强观点的防备",
                "继续使用口语化表达制造聊天感",
                "预告后面会继续展开",
                "弱化功利期待，让用户愿意继续听原因",
            ],
            [
                "【大家习惯理解的事情】其实是可以【反常识动作】的，而且可以【强化表达】。",
                "这条内容可能会【内容长度或表达状态】，我也不一定会【标准化准备】。",
                "我们就【轻松口语化推进方式】。",
                "但这件事一定会【继续展开或强调长度】。",
                "至于【外部数据或表面指标】，我没那么在意，因为【降低功利期待的理由】。",
            ],
        )
    if argument_pattern == "结果承诺＋方法预告":
        return (
            [
                "先给出用户想要的明确结果",
                "限定目标人群或当前处境",
                "降低实现门槛",
                "预告接下来会讲方法",
                "给出继续听下去的理由",
            ],
            [
                "如果你想获得【明确结果】，这条内容先讲清楚【关键前提】。",
                "尤其是【目标人群】现在最容易卡在【现实处境】。",
                "这件事没有你想得那么复杂，关键是先做到【低门槛动作】。",
                "接下来我会讲【方法数量】个最重要的方法。",
                "你只要把这几个点听完，就知道【后续可获得的具体判断】。",
            ],
        )
    if argument_pattern == "现实痛点＋连续提问":
        return (
            [
                "点名目标人群的现实处境",
                "抛出第一个高频痛点",
                "继续追问第二个相邻痛点",
                "把多个痛点收束成同一个问题",
                "预告后面会解释真正原因",
            ],
            [
                "如果你是【目标人群】，你最近一定会遇到一个问题。",
                "你是不是经常【痛点场景1】？",
                "你是不是也发现【痛点场景2】？",
                "这些表面上是【表层问题】，本质上其实是【核心问题】。",
                "接下来我想把这个问题一次讲透。",
            ],
        )
    abstract = [f"第{idx}句保留 `{function}` 功能，按 `{structure}` 组织表达" for idx, (function, structure) in enumerate(zip(functions, structures), start=1)]
    templates = [f"第{idx}句模板：【按{structure}替换为新正文素材】。" for idx, structure in enumerate(structures, start=1)]
    return abstract, templates


def build_matching_rules(argument_pattern: str, functions: list[str]) -> dict[str, list[str] | str]:
    if argument_pattern == "数据＋时间对比＋趋势推演":
        return {
            "适合的新正文": "正文核心结论依靠数据变化、时间对比或趋势推演成立。",
            "需要具备的素材条件": [
                "至少有一个当前数据",
                "至少有一个过去数据或对照数据",
                "数据之间存在明显变化",
                "能从变化推演出一个与普通人有关的未来结果",
            ],
            "不适合的新正文": [
                "只有观点，没有数据",
                "只有故事，没有趋势",
                "只有方法步骤，没有时间变化",
                "需要编造数据才能填满模板",
            ],
            "复刻时必须保留": [
                "第1句先给风险或提醒",
                "第2句抛出数据",
                "第3句追问数据含义",
                "第4句做时间对比",
                "第5句推演未来结果",
            ],
            "复刻时禁止": [
                "没有数据却硬写“有报告显示”",
                "把数据句改成故事句",
                "把趋势推演改成方法预告",
            ],
        }
    if argument_pattern == "历史案例＋连续追问":
        return {
            "适合的新正文": "正文核心结论需要靠多个历史机会、历史案例或同类案例连续证明。",
            "需要具备的素材条件": [
                "至少有两个可以成立的案例",
                "案例之间具有同一个证明方向",
                "案例可以通过“能不能”“是不是”等方式连续追问",
                "案例能共同证明正文核心结论",
            ],
            "不适合的新正文": [
                "正文没有案例",
                "只有一个孤立案例",
                "案例之间证明方向不一致",
                "需要临时编造历史机会才能填满模板",
            ],
            "复刻时必须保留": [
                "第1句提出利益或结果问题",
                "第2句降低防备",
                "第3句提出认知二选一",
                "第4句用第一个案例追问",
                "第5句确认上一答案并继续追问第二个案例",
            ],
            "复刻时禁止": [
                "只按关键词替换原案例",
                "把连续追问改成直接讲道理",
                "没有第二个案例仍强行使用这套结构",
            ],
        }
    if argument_pattern == "旧认知＋直接纠偏":
        return {
            "适合的新正文": "正文核心结论要推翻一个常见旧认知，并给出新的理解方式。",
            "需要具备的素材条件": [
                "存在一个明确旧认知或常识判断",
                "正文会直接否定或修正这个旧认知",
                "正文能解释为什么新判断成立",
                "后续内容能承接反常识开头继续展开",
            ],
            "不适合的新正文": [
                "正文只是方法步骤，没有认知冲突",
                "正文没有明确旧认知",
                "正文无法解释反常识判断",
                "需要为了开头额外制造冲突",
            ],
            "复刻时必须保留": [
                "第1句先抛反常识判断",
                "中间句保留口语化降防备节奏",
                "第5句为后续解释留出空间",
            ],
            "复刻时禁止": [
                "把反常识判断写成普通结论",
                "为了夸张改变正文核心结论",
                "把降防备句改成密集信息句",
            ],
        }
    if argument_pattern == "结果承诺＋方法预告":
        return {
            "适合的新正文": "正文有明确目标结果，并且会给出可执行的方法、步骤或路径。",
            "需要具备的素材条件": [
                "有明确目标结果",
                "有至少两个方法或步骤",
                "正文能兑现开头承诺",
                "目标人群和收益边界清楚",
            ],
            "不适合的新正文": [
                "只有观点，没有方法",
                "只有故事，没有步骤",
                "承诺结果无法被正文兑现",
            ],
            "复刻时必须保留": [
                "第1句给出结果承诺",
                "中间句降低门槛或限定人群",
                "后续句预告方法和继续观看理由",
            ],
            "复刻时禁止": [
                "承诺正文没有的方法数量",
                "夸大结果",
                "把方法预告改成情绪宣泄",
            ],
        }
    if argument_pattern == "现实痛点＋连续提问":
        return {
            "适合的新正文": "正文主要解决目标人群的真实痛点，并能通过连续提问让用户代入。",
            "需要具备的素材条件": [
                "目标人群明确",
                "至少有两个真实痛点或高频场景",
                "痛点属于同一类问题",
                "正文会解释痛点背后的原因或解决方法",
            ],
            "不适合的新正文": [
                "目标人群模糊",
                "没有具体痛点场景",
                "正文主要靠数据或故事证明",
            ],
            "复刻时必须保留": [
                "连续提问节奏",
                "目标人群代入",
                "痛点之间的递进关系",
            ],
            "复刻时禁止": [
                "把痛点写成泛泛焦虑",
                "连续追问但正文不回答",
                "临时编造用户场景",
            ],
        }
    return {
        "适合的新正文": f"正文主要论证方式与 `{argument_pattern}` 接近，且能自然承接这条五句功能链。",
        "需要具备的素材条件": [
            "新正文素材能逐句填满原开头功能链",
            "不需要额外编造数据、案例或故事",
            "第5句能自然接上正文第一段",
        ],
        "不适合的新正文": [
            "正文主要证明路径与这条开头不一致",
            "五句模板中有关键素材缺失",
            "需要大幅改变原开头功能顺序",
        ],
        "复刻时必须保留": [f"保留第{idx}句的 `{function}` 功能" for idx, function in enumerate(functions, start=1)],
        "复刻时禁止": [
            "只做关键词替换",
            "改变五句推进顺序",
            "编造正文不存在的素材",
        ],
    }


def get_existing_card_map(output_dir: Path) -> dict[tuple[str, str], Path]:
    mapping: dict[tuple[str, str], Path] = {}
    for path in output_dir.glob("BK*_*.md"):
        parts = path.stem.split("_", 2)
        if len(parts) < 3:
            continue
        _, blogger, topic = parts
        mapping[(blogger, topic)] = path
    return mapping


def next_bk_number(output_dir: Path) -> int:
    max_num = 0
    for path in output_dir.glob("BK*.md"):
        match = re.match(r"BK(\d{3,})_", path.stem)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def build_output_path(output_dir: Path, blogger: str, topic: str, existing_map: dict[tuple[str, str], Path], next_num: int) -> tuple[Path, int]:
    key = (clean_filename(blogger), clean_filename(topic))
    existing = existing_map.get(key)
    if existing:
        return existing, next_num
    filename = f"BK{next_num:03d}_{key[0]}_{key[1]}.md"
    path = output_dir / filename
    existing_map[key] = path
    return path, next_num + 1


def render_output(path: Path, row: dict[str, str], function_sentences: list[str]) -> None:
    functions = [detect_core_function(sentence, idx, len(function_sentences)) for idx, sentence in enumerate(function_sentences, start=1)]
    structures = [build_structure(sentence, function) for sentence, function in zip(function_sentences, functions)]
    argument_pattern = detect_argument_pattern(function_sentences, functions)
    skeleton_lines, template_lines = build_skeleton(argument_pattern, functions, structures)
    matching_rules = build_matching_rules(argument_pattern, functions)
    lines = [
        "# 爆款开头卡片",
        "",
        f"- 开头编号：{path.stem.split('_', 1)[0]}",
        f"- 博主名：{row['博主名']}",
        f"- 选题：{row['选题']}",
        f"- 点赞数：{row.get('点赞数', '')}",
        f"- 链接：{row.get('链接', '')}",
        f"- 发布时间：{row.get('发布时间', '')}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "### 1. 原文前5句",
        "",
    ]
    for idx, sentence in enumerate(function_sentences, start=1):
        lines.append(f"{idx}. {sentence}")
    lines += [
        "",
        "### 2. 逐句拆解",
        "",
        "|句子|原文|核心功能|写作结构|",
        "|-|-|-|-|",
    ]
    for idx, (sentence, function, structure) in enumerate(zip(function_sentences, functions, structures), start=1):
        lines.append(f"|第{idx}句|{sentence.replace('|', '｜')}|{function}|{structure}|")
    lines += [
        "",
        "### 3. 五句推进逻辑",
        "",
        f"> {' → '.join(functions)}",
        "",
        "### 4. 五句结构骨架",
        "",
    ]
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(skeleton_lines, start=1))
    lines += [
        "",
        "句式模板：",
        "",
    ]
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(template_lines, start=1))
    lines += [
        "",
        "### 5. 适合承载的论证方式",
        "",
        f"> {argument_pattern}",
        "",
        "### 6. 调用匹配规则",
        "",
        "适合的新正文：",
        "",
        f"> {matching_rules['适合的新正文']}",
        "",
        "需要具备的素材条件：",
        "",
    ]
    lines.extend(f"- {item}" for item in matching_rules["需要具备的素材条件"])
    lines += [
        "",
        "不适合的新正文：",
        "",
    ]
    lines.extend(f"- {item}" for item in matching_rules["不适合的新正文"])
    lines += [
        "",
        "复刻时必须保留：",
        "",
    ]
    lines.extend(f"- {item}" for item in matching_rules["复刻时必须保留"])
    lines += [
        "",
        "复刻时禁止：",
        "",
    ]
    lines.extend(f"- {item}" for item in matching_rules["复刻时禁止"])
    lines += [
        "",
    ]
    path.write_text(append_brand_footer("\n".join(lines)), encoding="utf-8")


def run(root: str, blogger_filter: str = "", input_dir: str = "", output_dir: str = "", selection_file: str = "") -> dict:
    root_path = Path(root)
    resolved_input_dir = Path(input_dir) if input_dir else (root_path / "02_资产中心" / "03_对标账号库")
    resolved_output_dir = Path(output_dir) if output_dir else (root_path / "02_资产中心" / "05_爆款开头库")
    resolved_selection_file = Path(selection_file) if selection_file else (resolved_output_dir / "00_爆款开头选中清单.md")
    audit_dir = root_path / "03_工作流中心" / "01_短视频主工作流" / "99_运行记录"
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    selected = 0
    existing_map = get_existing_card_map(resolved_output_dir)
    next_num = next_bk_number(resolved_output_dir)
    selections = read_selection_file(resolved_selection_file)
    for selection in selections:
        blogger = clean_filename(selection.get("博主名", ""))
        if blogger_filter and normalize_match(blogger) != normalize_match(blogger_filter):
            continue
        source_path = resolve_blogger_xlsx(resolved_input_dir, blogger)
        row, row_number = find_source_row(source_path, selection)
        selected += 1
        script = str(row.get("文案") or "").strip()
        if not script:
            raise RuntimeError(f"{source_path.name} 第 {row_number} 行 `文案` 为空，无法拆解")
        video_info = str(row.get("视频信息") or "").strip()
        if not video_info:
            raise RuntimeError(f"{source_path.name} 第 {row_number} 行 `视频信息` 为空，无法作为选题")
        function_sentences = extract_function_sentences(script, limit=5)
        if not function_sentences:
            raise RuntimeError(f"{source_path.name} 第 {row_number} 行未能切出前5个功能句")
        record = {
            "博主名": blogger,
            "选题": title_from(video_info),
            "点赞数": str(row.get("点赞数") or "").strip(),
            "链接": str(row.get("链接") or f"{source_path.name}#row{row_number}").strip(),
            "发布时间": str(row.get("发布时间") or "").strip(),
        }
        output_path, next_num = build_output_path(resolved_output_dir, record["博主名"], record["选题"], existing_map, next_num)
        render_output(output_path, record, function_sentences)
        generated += 1

    audit_path = audit_dir / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_爆款开头拆解审核.md"
    audit_path.write_text(
        append_brand_footer(
            "\n".join(
                [
                    "# 爆款开头拆解Skill运行记录",
                    "",
                    f"- 运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"- 输入目录：`{resolved_input_dir}`",
                    f"- 选中清单：`{resolved_selection_file}`",
                    f"- 输出目录：`{resolved_output_dir}`",
                    f"- 运行范围：`{blogger_filter or '全部博主'}`",
                    f"- 清单命中记录数：{selected}",
                    f"- 生成文件数：{generated}",
                    "- 说明：本轮只读取外部选中清单，不新增、不回写、不修改原始 xlsx。",
                    "",
                ]
            )
        ),
        encoding="utf-8",
    )
    return {"selected_rows": selected, "generated_files": generated, "audit_path": str(audit_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate baokuan opening cards from benchmark-account xlsx files.")
    default_root = Path(__file__).resolve().parents[3]
    parser.add_argument("--root", default=str(default_root), help="AI traffic factory root path")
    parser.add_argument("--blogger", default="", help="Only process one blogger xlsx by file stem.")
    parser.add_argument("--input-dir", default="", help="Override input xlsx directory for public install mode.")
    parser.add_argument("--output-dir", default="", help="Override output card directory for public install mode.")
    parser.add_argument("--selection-file", default="", help="Override external selection markdown file.")
    args = parser.parse_args()
    print(run(args.root, blogger_filter=args.blogger, input_dir=args.input_dir, output_dir=args.output_dir, selection_file=args.selection_file))


if __name__ == "__main__":
    main()
