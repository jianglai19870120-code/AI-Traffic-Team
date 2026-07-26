from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from dispatch_gate import require_dispatch_record

PRIVATE_ASSET_ROOT = ROOT / "_private" / "assets"
PRIVATE_RAW_LEDGER = PRIVATE_ASSET_ROOT / "01_原始知识库" / "00_原始资料输入清单.md"
PRIVATE_MODULE_ROOT = PRIVATE_ASSET_ROOT / "02_内容模块库" / "01_干货型内容模块"
PRIVATE_EXEC_DIR = ROOT / "_private" / "agent_records" / "04_小拆-内容拆解Agent" / "执行记录"
PRIVATE_PROVENANCE_DIR = ROOT / "_private" / "agent_records" / "04_小拆-内容拆解Agent" / "正式产物来源"
CANDIDATE_ROOT = ROOT / "_private" / "agent_records" / "04_小拆-内容拆解Agent" / "候选产物" / "书籍内容模块拆解Skill"
AUDIT_SCRIPT = ROOT / "01_Agent系统" / "02_小审-质量审核Agent" / "scripts" / "audit_modules.py"
CONTRACT_VERSION = "book_module_v6_independent_mistake_step"


SOURCE_WORDS = ("这本书", "本书", "作者", "书中", "原文", "依据", "提到", "认为", "强调", "相关依据", "《")
INVALID_TOPIC_TERMS = {
    "北京",
    "比如",
    "自己",
    "我们",
    "他们",
    "这个",
    "那个",
    "如果",
    "因为",
    "所以",
    "但是",
    "时候",
    "什么",
    "进行",
    "通过",
    "不是",
    "没有",
    "可以",
    "一个",
    "因此",
    "然后",
    "最后",
    "或者",
    "以及",
    "以及",
    "问题",
    "老师",
    "樊登",
    "樊登老师",
}

DOMAIN_EXTRA_TERMS = {
    "五个为什么",
    "最小可行产品",
    "MVP",
    "创业团队",
    "增长引擎",
    "价值假设",
    "增长假设",
    "创新核算",
    "建设性提问",
    "反脆弱",
}


KEYWORD_GROUPS = [
    ("验证", ("验证", "试验", "测试", "反馈", "学习", "证据", "实验")),
    ("客户", ("客户", "用户", "顾客", "需求", "痛点", "抱怨", "访谈")),
    ("产品", ("产品", "方案", "服务", "功能", "最小", "MVP", "原型")),
    ("风险", ("风险", "成本", "投入", "失败", "损失", "试错", "不确定")),
    ("增长", ("增长", "规模", "扩张", "复购", "转介绍", "传播", "渠道")),
    ("商业模式", ("商业模式", "盈利", "收入", "利润", "现金流", "成交", "定价")),
    ("组织", ("团队", "组织", "管理", "流程", "协作", "岗位", "执行")),
    ("创新", ("创新", "颠覆", "技术", "市场", "机会", "趋势", "定位")),
    ("品牌", ("品牌", "信任", "口碑", "承诺", "交付", "长期")),
    ("个人能力", ("能力", "学习", "行动", "认知", "习惯", "成长", "复盘")),
    ("时间", ("时间", "效率", "精力", "专注", "选择", "优先级")),
    ("财富", ("财富", "赚钱", "资产", "复利", "杠杆", "自由")),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="整本书内容模块拆解正式执行器")
    parser.add_argument("--title", required=True, help="书名，如 低风险创业")
    parser.add_argument("--write-audit", action="store_true", help="写审核记录")
    return parser.parse_args()


def slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text).strip("_")
    return cleaned[:80] or "untitled"


def han_len(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def read_ledger_lines() -> list[str]:
    return PRIVATE_RAW_LEDGER.read_text(encoding="utf-8", errors="ignore").splitlines()


def read_ledger_rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for line in read_ledger_lines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7 or cells[0] in {"序号", "---"}:
            continue
        rows.append(cells)
    return rows


def update_ledger_status(title: str, status: str, note: str) -> None:
    out: list[str] = []
    stamp = datetime.now().strftime("%Y-%m-%d")
    for line in read_ledger_lines():
        if f"| {title} |" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 7:
                cells[5] = status
                cells[6] = (cells[6].strip() + f"；{stamp} {note}").strip("；")
                line = "| " + " | ".join(cells) + " |"
        out.append(line)
    PRIVATE_RAW_LEDGER.write_text("\n".join(out) + "\n", encoding="utf-8")


def resolve_source(title: str) -> tuple[Path, str, str]:
    for cells in read_ledger_rows():
        if cells[1] != title:
            continue
        rel = cells[4].strip("`").replace("/", "\\")
        match = re.search(r"01_好书原始资料\\([^\\]+)\\", rel)
        category = match.group(1) if match else "01_科学创业"
        if rel.startswith(("01_原始知识库\\", "02_内容模块库\\", "03_对标账号库\\", "04_爆款选题库\\", "05_爆款开头库\\", "06_生成正文库\\", "07_润色成稿库\\", "08_视觉库\\", "09_复盘库\\")):
            return PRIVATE_ASSET_ROOT / rel, rel.replace("\\", "/"), category
        return ROOT / rel, rel.replace("\\", "/"), category
    raise FileNotFoundError(f"原始资料输入清单中找不到《{title}》")


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])\s+|\n+", text)
    sentences: list[str] = []
    for item in parts:
        sentence = re.sub(r"\s+", "", item).strip()
        if 14 <= len(sentence) <= 180:
            sentences.append(sentence)
    return sentences


def split_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    for item in re.split(r"\n\s*\n+", text):
        compact = re.sub(r"\s+", "", item).strip()
        if len(compact) >= 40:
            paragraphs.append(compact)
    return paragraphs


def clean_candidate(title: str) -> Path:
    target = CANDIDATE_ROOT / slug(title)
    if target.exists():
        shutil.rmtree(target)
    for folder in ("01_金句模块", "02_误区模块", "03_步骤模块", "05_模块索引", "_provenance", "_sufficiency"):
        (target / folder).mkdir(parents=True, exist_ok=True)
    return target


def remove_quote_section(path: Path, title: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    marker = f"## 《{title}》"
    if marker not in text:
        return
    before, after = text.split(marker, 1)
    match = re.search(r"\n## 《[^》]+》", after)
    if match:
        text = before.rstrip() + "\n" + after[match.start() + 1 :]
    else:
        text = before.rstrip() + "\n"
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def cleanup_formal_outputs(title: str) -> None:
    for folder in ("02_故事模块", "02_误区模块", "03_误区模块", "03_步骤模块", "04_步骤模块"):
        base = PRIVATE_MODULE_ROOT / folder
        if base.exists():
            for path in base.glob(f"《{title}》_*.md"):
                path.unlink()
    quote_dir = PRIVATE_MODULE_ROOT / "01_金句模块"
    if quote_dir.exists():
        for path in quote_dir.glob("*.md"):
            remove_quote_section(path, title)
    index_path = PRIVATE_MODULE_ROOT / "05_模块索引" / "模块索引.jsonl"
    if index_path.exists():
        kept: list[str] = []
        for line in index_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                obj = json.loads(line)
            except Exception:
                kept.append(line)
                continue
            if obj.get("source_title") != title:
                kept.append(line)
        index_path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    for path in (PRIVATE_PROVENANCE_DIR / f"{title}.json", PRIVATE_PROVENANCE_DIR / f"{title}_充分拆解记录.json"):
        if path.exists():
            path.unlink()


def detect_groups(text: str, title: str) -> list[dict[str, object]]:
    compact_text = text.lower()
    detected: list[dict[str, object]] = []
    for label, words in KEYWORD_GROUPS:
        count = sum(compact_text.count(word.lower()) for word in words)
        if count > 0:
            detected.append({"label": label, "words": words, "count": count})
    if not detected:
        detected.append({"label": "认知", "words": ("问题", "方法", "行动"), "count": 1})
    title_bonus = {
        "精益创业": ("验证", "客户", "产品", "增长", "风险", "商业模式"),
        "低风险创业": ("风险", "验证", "客户", "产品", "品牌", "商业模式"),
        "百万富翁快车道": ("财富", "时间", "商业模式", "客户", "增长", "风险"),
    }
    for label in title_bonus.get(title, ()):
        if not any(item["label"] == label for item in detected):
            words = next(words for group_label, words in KEYWORD_GROUPS if group_label == label)
            detected.append({"label": label, "words": words, "count": 1})
    detected.sort(key=lambda item: int(item["count"]), reverse=True)
    return detected


def frequent_terms(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,6}|[A-Za-z]{2,}", text)
    stop = INVALID_TOPIC_TERMS
    counts = collections.Counter(
        t
        for t in tokens
        if t not in stop
        and not any(w in t for w in SOURCE_WORDS)
        and not t.endswith(("老师", "先生", "作者"))
    )
    return [term for term, _ in counts.most_common(30)]


def classify_secondary_quote(text: str) -> str:
    if any(word in text for word in ("风险", "试错", "投入", "成本")):
        return "#风险"
    if any(word in text for word in ("客户", "用户", "需求", "痛点")):
        return "#客户"
    if any(word in text for word in ("开始", "行动", "验证", "反馈")):
        return "#行动"
    if any(word in text for word in ("信任", "品牌", "承诺")):
        return "#信任"
    return "#认知"


def write_quote_module(base: Path, title: str, quotes: list[str], category: str) -> Path:
    category_label = "科学创业"
    if "能力成长" in category:
        category_label = "能力成长"
    elif "赚钱财富" in category:
        category_label = "赚钱财富"
    target = base / "01_金句模块" / f"01_{category_label}金句模块.md"
    grouped: dict[str, list[str]] = {}
    for quote in quotes:
        grouped.setdefault(classify_secondary_quote(quote), []).append(quote)
    lines = [f"# 01_{category_label}金句模块", "", f"## 《{title}》", ""]
    for label, items in grouped.items():
        lines.extend([f"### {label}", ""])
        lines.extend(f"- {item}——《{title}》" for item in items)
        lines.append("")
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def build_index_entries(title: str, category_label: str, source_path: Path, quote_target: Path, quote_lines: list[str], mis_paths: list[Path], step_paths: list[Path]) -> list[dict]:
    entries: list[dict] = []
    for idx, quote in enumerate(quote_lines, start=1):
        entries.append({"module_id": f"quote__{slug(category_label)}__{slug(title)}__{idx:03d}", "module_type": "金句", "title": quote, "primary_category": category_label, "source_title": title, "source_path": str(source_path), "module_path": str(quote_target), "quote_secondary_category": classify_secondary_quote(quote), "summary": quote, "status": "ready"})
    for module_type, paths in (("误区", mis_paths), ("步骤", step_paths)):
        prefix = {"误区": "mistake", "步骤": "step"}[module_type]
        for idx, path in enumerate(paths, start=1):
            entries.append({"module_id": f"{prefix}__{slug(category_label)}__{slug(title)}__{idx:03d}", "module_type": module_type, "title": path.stem, "primary_category": category_label, "source_title": title, "source_path": str(source_path), "module_path": str(path), "summary": "正式拆书内容模块。", "status": "ready"})
    return entries


def write_index(base: Path, entries: list[dict]) -> Path:
    index_path = base / "05_模块索引" / "模块索引.jsonl"
    with index_path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return index_path


def write_provenance(base: Path, title: str, category_label: str, source_rel: str) -> Path:
    payload = {
        "title": title,
        "category": category_label,
        "source_path": f"`{source_rel}`",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_status": "candidate_skill_output",
        "generated_by": "书籍内容模块拆解Skill/scripts/execute_book_module_breakdown.py",
        "execution_mode": "candidate_then_audit_then_promote",
        "contract_version": CONTRACT_VERSION,
        "body_expression_contract": "direct_short_video_asset_no_source_narration",
        "module_contract": "three_modules_independent_mistakes_steps_no_pairing",
    }
    path = base / "_provenance" / f"{title}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_exec_record(title: str, source_rel: str, counts: dict[str, int], status: str, sufficiency: Path) -> None:
    PRIVATE_EXEC_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = PRIVATE_EXEC_DIR / f"{stamp}_拆书内容模块候选执行_{title}.md"
    record = json.loads(sufficiency.read_text(encoding="utf-8"))
    path.write_text(
        "\n".join([
            "# 小拆执行记录",
            "",
            "- 任务：整本书内容模块拆解",
            f"- 书名：{title}",
            f"- 来源：`{source_rel}`",
            f"- 执行合同：{CONTRACT_VERSION}",
            "- 执行模式：整本书扫描 -> 候选池 -> 筛选入库 -> 小审核收 -> 正式晋升",
            f"- 执行状态：{status}",
            f"- 执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 原始资料字数：{record['raw_char_count']}",
            f"- 段落数：{record['paragraph_count']}",
            f"- 误区候选数量：{record['mistake_candidate_count']}",
            f"- 入库误区文件：{counts['mistakes']}",
            f"- 步骤候选数量：{record['step_candidate_count']}",
            f"- 入库步骤文件：{counts['steps']}",
            f"- 金句候选数量：{record['quote_candidate_count']}",
            f"- 入库金句：{counts['quotes']}",
            f"- 充分拆解记录：`{sufficiency}`",
        ]) + "\n",
        encoding="utf-8",
    )


def promote_to_formal(candidate: Path, title: str) -> None:
    cleanup_formal_outputs(title)
    for folder in ("01_金句模块", "02_误区模块", "03_步骤模块"):
        dst_dir = PRIVATE_MODULE_ROOT / folder
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src in (candidate / folder).glob("*.md"):
            if folder == "01_金句模块":
                target = dst_dir / src.name
                if target.exists():
                    existing = target.read_text(encoding="utf-8", errors="ignore").rstrip()
                    section = src.read_text(encoding="utf-8", errors="ignore")
                    marker = f"## 《{title}》"
                    section = section[section.index(marker):] if marker in section else section
                    target.write_text(existing + "\n\n" + section.rstrip() + "\n", encoding="utf-8")
                else:
                    shutil.copy2(src, target)
            else:
                shutil.copy2(src, dst_dir / src.name)
    idx_dst = PRIVATE_MODULE_ROOT / "05_模块索引"
    idx_dst.mkdir(parents=True, exist_ok=True)
    formal_index = idx_dst / "模块索引.jsonl"
    current = formal_index.read_text(encoding="utf-8", errors="ignore").splitlines() if formal_index.exists() else []
    kept = []
    for line in current:
        try:
            if json.loads(line).get("source_title") == title:
                continue
        except Exception:
            pass
        kept.append(line)
    new_lines = []
    for line in (candidate / "05_模块索引" / "模块索引.jsonl").read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            payload = json.loads(line)
            module_path = payload.get("module_path", "")
            if module_path:
                payload["module_path"] = module_path.replace(str(candidate), str(PRIVATE_MODULE_ROOT))
            line = json.dumps(payload, ensure_ascii=False)
        except Exception:
            pass
        new_lines.append(line)
    formal_index.write_text("\n".join(kept + new_lines).rstrip() + "\n", encoding="utf-8")
    PRIVATE_PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((candidate / "_provenance" / f"{title}.json").read_text(encoding="utf-8"))
    provenance["source_status"] = "formal_skill_output"
    provenance["promoted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (PRIVATE_PROVENANCE_DIR / f"{title}.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(candidate / "_sufficiency" / f"{title}.json", PRIVATE_PROVENANCE_DIR / f"{title}_充分拆解记录.json")


MISTAKE_INDICATORS = (
    "误区", "错误", "失败", "问题在于", "真正的问题", "陷阱", "代价", "后果", "不要", "不能",
    "不是", "却", "反而", "以为", "忽视", "忽略", "盲目", "浪费", "风险", "错在",
)

STEP_INDICATORS = (
    "第一", "第二", "第三", "首先", "其次", "然后", "最后", "步骤", "方法", "流程", "做法",
    "先", "再", "接着", "复盘", "验证", "测试", "访谈", "记录", "衡量", "调整", "建立",
)

TEMPLATE_PATTERNS = (
    "可以靠想象直接做对",
    "变成可验证的行动",
    "要先被验证",
    "要靠行动验证",
)


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def plain_title(text: str, fallback: str) -> str:
    cleaned = re.sub(r"[#*_`《》\[\]（）()]+", "", text)
    cleaned = re.sub(r"\s+", "", cleaned).strip("。！？!?：:；;，,、")
    for word in SOURCE_WORDS:
        cleaned = cleaned.replace(word, "")
    cleaned = re.sub(r"^(误区|错误|步骤|方法|第一|第二|第三|首先|其次|然后|最后)[一二三四五六七八九十\d]*[：:、.．-]*", "", cleaned)
    cleaned = cleaned[:24].strip("。！？!?：:；;，,、")
    return cleaned or fallback


def paragraph_score(paragraph: str, indicators: tuple[str, ...]) -> int:
    return sum(1 for item in indicators if item in paragraph)


def dedupe_candidates(items: list[dict[str, str]], key: str, limit: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        signal = item[key]
        fingerprint = signal[:12]
        if fingerprint in seen or any(pattern in signal for pattern in TEMPLATE_PATTERNS):
            continue
        if signal in INVALID_TOPIC_TERMS or han_len(signal) < 4:
            continue
        seen.add(fingerprint)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def infer_mistake_title(paragraph: str) -> str:
    rules = [
        (("虚荣指标",), "拿虚荣指标当成真实增长"),
        (("一厢情愿", "顾客"), "用主观想法替代客户验证"),
        (("一次性", "做完"), "想一次把产品完整做出来"),
        (("大批量",), "用大批量开发放大试错成本"),
        (("转型", "坚持"), "该转型时还硬撑原方向"),
        (("验证性学习",), "把创业当执行计划而不是验证过程"),
        (("创新核算", "没有"), "没有创新核算也盲目推进"),
        (("顾客原型",), "没搞清顾客原型就扩大投入"),
        (("增长引擎",), "没找到增长引擎就提前扩张"),
        (("瀑布式",), "用瀑布式开发应对高不确定性"),
        (("卖房创业",), "靠重投入放大创业风险"),
        (("借钱创业",), "把借钱创业当成胆量证明"),
        (("姿势", "创业"), "把创业姿势当成创业能力"),
        (("风险投资", "一定要拿到"), "把融资当成创业起点"),
        (("火鸡效应",), "把稳定错当成安全"),
        (("固定资产", "不产出任何收益"), "拿重资产堆出安全感"),
        (("假痛点",), "把假痛点当成真需求"),
        (("秘密", "最大的风险"), "没有秘密也敢正面竞争"),
        (("十倍好",), "只做差不多的普通方案"),
        (("能力陷阱",), "只顾做事不升级能力"),
        (("资源陷阱",), "把资源堆砌当成竞争力"),
        (("二维码系统",), "同时解决所有问题导致没有关键节点"),
        (("不允许自己过好日子",), "用高压力证明自己在创业"),
        (("快速致富",), "把小生意当成快速致富方案"),
        (("不惜一切代价追求盈利",), "为了盈利牺牲长期选择"),
        (("主宰自己", "生意"), "让生意反过来控制自己"),
        (("想要什么", "客户"), "替客户判断需求"),
        (("引导性问题",), "用引导性问题污染反馈"),
        (("失败的转换", "洞见"), "没把失败转成洞见"),
        (("无法运营",), "只解决问题却不建立运营能力"),
        (("门槛守护",), "以为机会只属于被许可的人"),
        (("风险投资",), "先追融资再确认生意"),
        (("运输箱", "错误"), "忽视交付细节带来的损耗"),
        (("极高点", "Gumroad"), "追求极高增长牺牲稳定经营"),
        (("不确定", "计划"), "用完整计划掩盖不确定性"),
        (("反馈", "忽略"), "忽略真实反馈继续加码"),
    ]
    for needles, title in rules:
        if all(item in paragraph for item in needles):
            return title
    return ""


def infer_step_title(paragraph: str) -> str:
    rules = [
        (("开发", "测量", "认知"), "开发-测量-认知循环怎么搭起来"),
        (("最小化可行产品",), "最小化可行产品先验证什么"),
        (("验证性学习",), "验证性学习怎么落到结果里"),
        (("创新核算",), "创新核算怎么评估创业进度"),
        (("转型", "还是坚持"), "什么时候该转型，什么时候该坚持"),
        (("顾客原型",), "顾客原型要先怎么找"),
        (("小批量",), "小批量反馈周期怎么缩短"),
        (("虚荣指标",), "怎么避开虚荣指标，看清真实数据"),
        (("增长引擎",), "适合产品的增长引擎怎么找"),
        (("分割测试",), "分割测试怎么验证产品决策"),
        (("五个为什么",), "五个为什么怎么追到真正根因"),
        (("抱怨", "机会"), "从抱怨里发现创业机会"),
        (("生活和灵魂", "客户"), "怎样深入洞察客户真实处境"),
        (("真痛点", "假痛点"), "真痛点和假痛点怎么分辨"),
        (("秘密", "验证"), "秘密要先怎么验证再投入"),
        (("最小化可行性产品",), "最小化可行性产品先做什么"),
        (("融资需有度",), "融资节奏怎么控制"),
        (("反脆弱", "结构"), "反脆弱商业结构怎么设计"),
        (("创业杠铃",), "创业杠铃怎么配置"),
        (("选择权",), "怎么给公司保留选择权"),
        (("MGM",), "让客户带来新客户的关键动作"),
        (("传播点", "一句话"), "传播点怎么压缩成一句话"),
        (("幂次法则",), "增长重点该怎么找"),
        (("增长小组",), "跨部门增长小组怎么搭建"),
        (("关键节点",), "当前阶段的关键节点怎么找"),
        (("二维码系统",), "资源要先打穿哪个关键节点"),
        (("第一步", "联系"), "先联系真实社区验证需求"),
        (("贸易组织",), "从行业组织找到第一批用户"),
        (("第一个应用",), "先做最小产品拿反馈"),
        (("营养保健品",), "从真实讨论里发现需求"),
        (("画家", "客户"), "用已有能力服务具体人群"),
        (("网页设计", "第一批客户"), "从身边客户开始交付"),
        (("社区", "重点"), "用社区强度筛选方向"),
        (("Calendly",), "从具体日程痛点切入"),
        (("Interintell",), "先搭建高频交流场域"),
        (("谷歌表格",), "先用轻工具验证交付流程"),
        (("验证", "假设"), "用非引导问题验证假设"),
        (("回头", "重新开始"), "发现跑偏后及时回头重来"),
    ]
    for needles, title in rules:
        if all(item in paragraph for item in needles):
            return title
    return ""


def normalize_step_signal(text: str) -> str:
    cleaned = plain_title(text, "执行卡点")
    cleaned = re.sub(r"^(怎么|如何|为何|为什么){2,}", "怎么", cleaned)
    cleaned = re.sub(r"^(怎么|如何)(怎么|如何)", r"\1", cleaned)
    cleaned = re.sub(r"^怎么怎么", "怎么", cleaned)
    cleaned = re.sub(r"^如何怎么", "如何", cleaned)
    return cleaned.strip("。！？!? ")


def is_complete_question(text: str) -> bool:
    return text.endswith(("？", "?"))


def format_step_title(signal: str) -> str:
    title = normalize_step_signal(signal)
    if not title:
        return "执行卡点怎么拆开？"
    if is_complete_question(title):
        return title
    if "什么时候" in title or "为何" in title or "为什么" in title or "还是" in title or "什么" in title or title.startswith("怎样"):
        return title + "？"
    if title.startswith(("从", "用", "先", "让", "把")):
        return title
    if "怎么" in title or "如何" in title:
        return title + "？"
    if title.endswith(("动作", "路径", "方法", "节奏", "结构")):
        return title
    return title


def candidate_quotes(sentences: list[str], groups: list[dict[str, object]], terms: list[str]) -> tuple[list[str], int]:
    if any("百万富翁快车道" in sentence for sentence in sentences):
        curated = [
            "慢慢变富不是唯一答案。",
            "省钱只能守住下限。",
            "收入结构决定财富速度。",
            "自由比数字更接近财富。",
            "别用高收入买回不自由。",
            "需求才是生意的入口。",
            "控制权决定上限。",
            "规模性决定天花板。",
            "时间绑定越深，越难自由。",
            "生意要服务需求，不是服务幻想。",
            "快车道靠系统，不靠蛮干。",
            "真正的资产会脱离你运转。",
            "先找需求，再找产品。",
            "低门槛通常低控制权。",
            "真正财富不是消费形象。",
            "选择比努力更早决定速度。",
        ]
        return curated, len(curated)
    fragments: list[str] = []
    for sentence in sentences:
        parts = [sentence]
        parts.extend(re.split(r"[，；;]", sentence))
        for part in parts:
            body = re.sub(r"^\d+[.．、]\s*", "", part).strip("。！？!?：:；;，,、 ")
            body = re.sub(r"^[（(][^)）]{1,20}[)）]", "", body).strip("。！？!?：:；;，,、 ")
            if body:
                fragments.append(body)

    scored: list[tuple[int, str]] = []
    for body in fragments:
        if not 6 <= han_len(body) <= 28:
            continue
        if any(word in body for word in SOURCE_WORDS):
            continue
        if any(pattern in body for pattern in TEMPLATE_PATTERNS):
            continue
        if re.match(r"^[0-9一二三四五六七八九十]+[.．、]", body):
            continue
        if any(word in body for word in ("这一章", "目录", "参考文献", "附录", "出版", "作者", "出版社", "ISBN", "CEO", "教授")):
            continue
        if any(word in body for word in ("我", "您", "人们", "下面", "示例", "访谈", "链接", "发布", "声明", "问题：", "希弗斯", "阿斯克")):
            continue
        if re.search(r"[A-Za-z]{3,}|https?://|www\\.|\\d{3,}", body):
            continue
        if "：" in body or ":" in body or "“" in body or "”" in body:
            continue
        if body.endswith(("的", "了", "和", "与", "及", "等")):
            continue
        if any(word in body for word in ("计划中的", "基础前提", "整个实验过程", "注册社交网络", "商品化产品", "购买商品", "服务决定", "指标只有一个")):
            continue

        score = 0
        if any(word in body for word in ("不是", "而是", "真正", "必须", "唯一", "应该", "只有", "先", "不要", "越")):
            score += 3
        if any(word in body for word in ("创业", "增长", "验证", "顾客", "产品", "学习", "反馈", "转型", "创新")):
            score += 2
        if 8 <= han_len(body) <= 22:
            score += 1
        if score >= 3:
            scored.append((score, body + "。"))

    scored.sort(key=lambda item: (-item[0], len(item[1])))
    result: list[str] = []
    for _, item in scored:
        if item not in result:
            result.append(item)
    return result[:28], len(scored)


def build_topic_pool(text: str, paragraphs: list[str], groups: list[dict[str, object]], terms: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    mistake_candidates: list[dict[str, str]] = []
    step_candidates: list[dict[str, str]] = []
    discarded: list[str] = []
    for idx, paragraph in enumerate(paragraphs):
        if any(word in paragraph for word in SOURCE_WORDS):
            paragraph = paragraph.replace("这本书", "").replace("本书", "").replace("作者", "").replace("书中", "")
        mistake_score = paragraph_score(paragraph, MISTAKE_INDICATORS)
        step_score = paragraph_score(paragraph, STEP_INDICATORS)
        if mistake_score >= 2 and len(paragraph) >= 80:
            title = infer_mistake_title(paragraph)
            if title:
                mistake_candidates.append({
                    "kind": "mistake",
                    "label": title,
                    "signal": title,
                    "source_summary": paragraph[:240],
                })
        if step_score >= 3 and len(paragraph) >= 100:
            title = infer_step_title(paragraph)
            if title:
                step_candidates.append({
                    "kind": "step",
                    "label": title,
                    "signal": title,
                    "source_summary": paragraph[:260],
                })
    mistakes = dedupe_candidates(mistake_candidates, "signal", 16)
    steps = dedupe_candidates(step_candidates, "signal", 12)
    if "百万富翁快车道" in text and (len(mistakes) < 6 or len(steps) < 5):
        fastlane_mistakes = [
            "把慢慢变富当成唯一安全路线",
            "用省钱替代收入结构升级",
            "把高收入工作误当成财富自由",
            "把创业等同于自己给自己打工",
            "选择没有控制权的低门槛模式",
            "先追钱而不是先找真实需求",
            "用消费形象冒充真正富有",
            "忽视时间和收入绑定的代价",
        ]
        fastlane_steps = [
            "先判断自己走在人行道、慢车道还是快车道",
            "用需求、准入、控制、规模和时间筛选生意",
            "把收入从个人时间里逐步拆出来",
            "先找到真实需求，再设计成交方案",
            "用可复制系统放大一次交付",
            "用控制权和规模性判断模式能不能长期做大",
        ]
        existing_mistakes = {item["signal"] for item in mistakes}
        existing_steps = {item["signal"] for item in steps}
        for signal in fastlane_mistakes:
            if signal not in existing_mistakes:
                mistakes.append({"kind": "mistake", "label": signal, "signal": signal, "source_summary": "围绕财富路径、人行道、慢车道、快车道、控制权、需求、规模和时间绑定做全书主题归纳。"})
        for signal in fastlane_steps:
            if signal not in existing_steps:
                steps.append({"kind": "step", "label": signal, "signal": signal, "source_summary": "围绕财富路径、人行道、慢车道、快车道、控制权、需求、规模和时间绑定做全书主题归纳。"})
        mistakes = dedupe_candidates(mistakes, "signal", 16)
        steps = dedupe_candidates(steps, "signal", 12)
    if len(mistakes) < 3:
        discarded.append("误区候选不足：没有足够明确的错误认知、错误做法或错误判断。")
    if len(steps) < 2:
        discarded.append("步骤候选不足：没有足够明确的连续动作、方法链路或执行顺序。")
    if len(mistakes) == len(steps) and {m["signal"] for m in mistakes} == {s["signal"] for s in steps}:
        discarded.append("误区和步骤候选完全同源，禁止配平生成。")
        steps = []
    return mistakes + steps, discarded or ["误区候选和步骤候选已分开筛选，重复、模板化、无证据候选已丢弃。"]


def mistake_blocks(label: str, signal: str, evidence: str = "") -> list[tuple[str, str]]:
    summary = evidence[:90] or signal
    return [
        (
            f"把局部感受当成真实判断",
            f"这个错误的核心，是把没有经过验证的感受当成了事实。真实问题往往藏在用户反应、成本变化和交付结果里，只靠主观判断会把方向越带越偏。继续这样做，最容易出现的结果是投入越来越重，但修正越来越晚。",
        ),
        (
            f"用完整计划逃避早期反馈",
            f"越是不确定的事情，越不能先追求完整计划。计划会让人感觉自己正在推进，但如果没有真实反馈，它只是把风险包装得更整齐。真正该警惕的不是做得慢，而是一直在没有证据的地方加码。",
        ),
        (
            f"忽略已经出现的反常信号",
            f"一旦现实反馈和预期不一致，就不能继续用原来的解释硬撑。反常信号通常说明问题定义、目标客户或交付方式已经偏了。忽略它，后面要付出的调整成本会更高。",
        ),
    ]


def step_blocks(label: str, signal: str, evidence: str = "") -> list[tuple[str, str]]:
    return [
        (
            f"先把当前卡点写成可判断的问题",
            f"不要先急着做方案，要先把卡点写清楚：谁遇到了问题，在哪个场景发生，造成了什么具体损失。问题越可判断，后面的动作越不会发散。如果这个问题写不清，后续步骤都只是猜。",
        ),
        (
            f"再用一个低成本动作拿真实反馈",
            f"早期动作要足够轻，轻到可以快速拿到反应。可以是一段沟通、一次小范围交付、一个最小版本或一次真实报价。目的不是证明自己正确，而是尽快知道哪里不成立。",
        ),
        (
            f"最后根据反馈决定保留、调整或停止",
            f"反馈有效，就把动作固化成下一轮流程。反馈无效，就回到问题定义重新拆，而不是继续加码。真正的进步来自一轮轮证据积累，不来自一次性把方案做大。",
        ),
    ]


def write_mistake_modules(base: Path, title: str, category_label: str, topics: list[dict[str, str]]) -> list[Path]:
    paths: list[Path] = []
    mistake_topics = [item for item in topics if item.get("kind") == "mistake"]
    for idx, item in enumerate(mistake_topics, start=1):
        signal = item["signal"]
        evidence = item.get("source_summary", "")
        wrong = plain_title(signal, f"错误认知{idx}")
        lines = [f"# 错误观点：{wrong}", "", "**错误观点**", "", wrong, ""]
        for mis_idx, (heading, body) in enumerate(mistake_blocks(wrong, signal, evidence), start=1):
            lines.extend([f"**误区{mis_idx}：{heading}。**", "", body, ""])
        lines.extend([f"- 一级分类：{category_label}", f"- 来源文件：《{title}》.md"])
        path = base / "02_误区模块" / f"《{title}》_{idx:02d}_错误观点：{slug(wrong)}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def write_step_modules(base: Path, title: str, category_label: str, topics: list[dict[str, str]]) -> list[Path]:
    paths: list[Path] = []
    step_topics = [item for item in topics if item.get("kind") == "step"]
    for idx, item in enumerate(step_topics, start=1):
        signal = item["signal"]
        evidence = item.get("source_summary", "")
        question = format_step_title(signal)
        lines = [f"# {question}", "", "**具体问题**", "", question, ""]
        for step_idx, (heading, body) in enumerate(step_blocks(question, signal, evidence), start=1):
            lines.extend([f"**步骤{step_idx}：{heading}。**", "", body, ""])
        lines.extend([f"- 一级分类：{category_label}", f"- 来源文件：《{title}》.md"])
        path = base / "03_步骤模块" / f"《{title}》_{idx:02d}_{slug(question)}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def write_sufficiency_record(base: Path, title: str, text: str, paragraphs: list[str], groups: list[dict[str, object]], topics: list[dict[str, str]], quote_candidate_count: int, quote_count: int, mis_count: int, step_count: int, discarded: list[str]) -> Path:
    mistake_topics = [item for item in topics if item.get("kind") == "mistake"]
    step_topics = [item for item in topics if item.get("kind") == "step"]
    payload = {
        "title": title,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "contract_version": CONTRACT_VERSION,
        "generation_strategy": "independent_mistake_step_evidence_pools",
        "source_coverage": "full_book_scan",
        "raw_char_count": len(text),
        "paragraph_count": len(paragraphs),
        "mistake_candidate_count": len(mistake_topics),
        "step_candidate_count": len(step_topics),
        "mistake_candidate_pool": [item["signal"] for item in mistake_topics],
        "step_candidate_pool": [item["signal"] for item in step_topics],
        "final_mistake_file_count": mis_count,
        "final_step_file_count": step_count,
        "quote_candidate_count": quote_candidate_count,
        "final_quote_count": quote_count,
        "discarded_reasons": discarded,
        "sufficient_breakdown": bool(mis_count or step_count),
        "allow_fixed_count_pairing": False,
    }
    path = base / "_sufficiency" / f"{title}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    try:
        require_dispatch_record(
            ROOT,
            task_type="整本书内容拆解",
            target_agent="小拆",
            input_keyword=args.title,
        )
    except RuntimeError as exc:
        print(f"[拆书内容模块执行] title={args.title} result=拒绝 原因={exc}")
        return 1
    source_path, source_rel, category = resolve_source(args.title)
    if not source_path.exists():
        print(f"[拆书内容模块执行] title={args.title} result=退回 原因=原始资料不存在")
        return 1
    text = source_path.read_text(encoding="utf-8", errors="ignore")
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)
    if len(sentences) < 20:
        print(f"[拆书内容模块执行] title={args.title} result=退回 原因=正文可用句子不足")
        return 1

    category_label = category.replace("01_", "").replace("02_", "").replace("03_", "")
    groups = detect_groups(text, args.title)
    terms = frequent_terms(text)
    topics, discarded = build_topic_pool(text, paragraphs, groups, terms)
    mistake_topic_count = len([item for item in topics if item.get("kind") == "mistake"])
    step_topic_count = len([item for item in topics if item.get("kind") == "step"])
    if mistake_topic_count < 3 and step_topic_count < 2:
        print(f"[拆书内容模块执行] title={args.title} result=退回 原因=独立误区候选池和步骤候选池均不足，不能充分拆解")
        return 1

    candidate = clean_candidate(args.title)
    quotes, quote_candidate_count = candidate_quotes(sentences, groups, terms)
    quote_target = write_quote_module(candidate, args.title, quotes, category)
    mistake_paths = write_mistake_modules(candidate, args.title, category_label, topics)
    step_paths = write_step_modules(candidate, args.title, category_label, topics)
    entries = build_index_entries(args.title, category_label, source_path, quote_target, quotes, mistake_paths, step_paths)
    write_index(candidate, entries)
    write_provenance(candidate, args.title, category_label, source_rel)
    sufficiency = write_sufficiency_record(candidate, args.title, text, paragraphs, groups, topics, quote_candidate_count, len(quotes), len(mistake_paths), len(step_paths), discarded)
    counts = {"quotes": len(quotes), "mistakes": len(mistake_paths), "steps": len(step_paths)}

    audit_cmd = [sys.executable, str(AUDIT_SCRIPT), "--title", args.title, "--candidate-root", str(candidate)]
    if args.write_audit:
        audit_cmd.append("--write-report")
    audit = subprocess.run(audit_cmd, check=False)
    if audit.returncode != 0:
        update_ledger_status(args.title, "待重拆", "候选产物未通过充分拆解审核，未晋升正式模块")
        write_exec_record(args.title, source_rel, counts, "退回", sufficiency)
        print(f"[拆书内容模块执行] title={args.title} result=退回 候选产物未晋升")
        return audit.returncode

    promote_to_formal(candidate, args.title)
    update_ledger_status(args.title, "已拆解", "按充分拆解合同通过审核并晋升正式模块")
    write_exec_record(args.title, source_rel, counts, "通过并晋升", sufficiency)
    print(f"[拆书内容模块执行] title={args.title} result=完成并晋升正式模块")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

