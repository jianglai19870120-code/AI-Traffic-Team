from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(os.environ.get("AI_TRAFFIC_FACTORY_ROOT") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT / "tools"))

from brand_footer import append_brand_footer

BOOK_EXTENSIONS = {".md", ".txt", ".pdf", ".epub"}
TEXT_EXTENSIONS = {".md", ".txt"}
OCR_MIN_TEXT = 120
LEDGER_HEADER = """# 原始资料输入清单

说明：

- 这是新根层统一原始资料入口
- 这里只登记资料本身，不绑定选题，不判断链路
- 这张表只回答 3 件事：你输入了什么资料、资料来自谁、它是否已拆解

| 序号 | 资料标题 | 作者/来源主体 | 资料类型 | 原始资料文件路径 | 当前状态 | 备注 |
|---|---|---|---|---|---|---|"""


@dataclass
class Result:
    source: Path
    status: str
    title: str
    author: str
    target: Path | None
    note: str


@dataclass
class LedgerEntry:
    category: str
    title: str
    author: str
    source_path: str
    status: str
    remark: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="标准化原始资料为正式 md")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--scope", choices=["main"], default="main")
    parser.add_argument("--category", default="", help="只处理指定分类目录，如 01_科学创业")
    parser.add_argument("--apply", action="store_true", help="实际写入和改名；默认仅预演")
    parser.add_argument("--limit", type=int, default=0, help="限制处理文件数，0 表示不限制")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    main_root = root / "02_资产中心" / "01_原始知识库" / "01_好书原始资料"
    ledger_path = root / "02_资产中心" / "01_原始知识库" / "00_原始资料输入清单.md"

    source_roots: list[Path] = []
    if args.scope == "main" and main_root.exists():
        source_roots.append(main_root)

    results: list[Result] = []
    count = 0
    for source_root in source_roots:
        for file_path in iter_source_files(source_root):
            if args.category and file_path.parent.name != args.category:
                continue
            count += 1
            if args.limit and count > args.limit:
                break
            results.append(process_one(file_path, source_root, ledger_path, apply=args.apply))
        if args.limit and count > args.limit:
            break

    print_report(results, apply=args.apply)
    if args.apply:
        rebuild_ledger(root, main_root, ledger_path)
        refresh_dashboard(root)
    return 0


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in BOOK_EXTENSIONS:
            continue
        yield path


def process_one(file_path: Path, source_root: Path, ledger_path: Path, apply: bool) -> Result:
    category_dir = file_path.parent
    title, author = parse_title_author(file_path.stem)
    if not author:
        author = "未知作者"
    clean_title = clean_title_text(title)
    clean_author = clean_author_text(author)
    target_name = f"《{clean_title}》.md"
    target_path = category_dir / target_name

    if file_path.suffix.lower() == ".epub":
        return Result(file_path, "skip", clean_title, clean_author, None, "当前环境未接入 epub 提取库")

    if file_path.suffix.lower() == ".md" and file_path.name == target_name:
        return Result(file_path, "ok", clean_title, clean_author, file_path, "已是正式 md")

    if target_path.exists():
        if apply and file_path.suffix.lower() == ".md" and file_path != target_path and file_path.exists():
            file_path.unlink()
            return Result(file_path, "ok", clean_title, clean_author, target_path, "已删除旧命名 md，保留正式 md")
        return Result(file_path, "skip", clean_title, clean_author, target_path, "已存在正式 md，旧原文件留待审核后清理")

    content, note = extract_markdown_content(file_path)
    if not content.strip():
        return Result(file_path, "fail", clean_title, clean_author, None, f"正文为空：{note}")

    if apply:
        target_path.write_text(content, encoding="utf-8")
        if file_path != target_path and file_path.exists():
            # 标准化入库阶段先只删除旧 md 重命名场景；非 md 原文件等待小审通过后再删
            if file_path.suffix.lower() == ".md":
                file_path.unlink()

    return Result(file_path, "ok", clean_title, clean_author, target_path, note)


def parse_title_author(stem: str) -> tuple[str, str]:
    stem = stem.strip()
    m = re.match(r"^《(?P<title>.+?)》$", stem)
    if m:
        return m.group("title").strip(), ""
    m = re.match(r"^《(?P<title>.+?)》(?P<author>.+)$", stem)
    if m:
        return m.group("title").strip(), m.group("author").strip()

    parts = re.split(r"[-_—｜|]+", stem)
    if len(parts) >= 2:
        return parts[0].strip(), parts[-1].strip()
    return stem, ""


def clean_title_text(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^《(.+?)》$", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[（(][^)）]{0,60}(完整版|全彩|扫描版|珍藏版|修订版|升级版|pdf|PDF|epub|mobi|azw3)[^)]*[)）]$", "", text)
    text = re.sub(r"(完整版|全彩版|扫描版|修订版|升级版|电子书|pdf|PDF|epub|mobi|azw3)$", "", text)
    text = re.sub(r"[【\[].*?(公众号|下载|资源|扫描|整理).*?[】\]]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -_—｜|")
    return text or "未命名资料"


def clean_author_text(value: str) -> str:
    text = value.strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"^(作者[:：]?)", "", text)
    return text or "未知作者"


def extract_markdown_content(file_path: Path) -> tuple[str, str]:
    suffix = file_path.suffix.lower()
    if suffix == ".md":
        return file_path.read_text(encoding="utf-8", errors="ignore"), "md 原文保留"
    if suffix == ".txt":
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return f"# {file_path.stem}\n\n{text.strip()}\n", "txt 转 md"
    if suffix == ".pdf":
        return extract_pdf(file_path)
    return "", "不支持的格式"


def extract_pdf(file_path: Path) -> tuple[str, str]:
    import fitz

    doc = fitz.open(file_path)
    pages: list[str] = []
    used_ocr = False
    ocr = None

    for idx, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if len(text) < OCR_MIN_TEXT:
            if ocr is None:
                try:
                    from rapidocr_onnxruntime import RapidOCR  # type: ignore
                    ocr = RapidOCR()
                except Exception:
                    ocr = False
            if ocr:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                result, _ = ocr(pix.tobytes("png"), use_det=True, use_cls=True, use_rec=True)
                if result:
                    text = "\n".join(item[1] for item in result).strip()
                    used_ocr = True
        if text:
            pages.append(f"## 第{idx}页\n\n{text}")

    doc.close()
    joined = "\n\n".join(pages).strip()
    note = "pdf 直提文本"
    if used_ocr:
        note = "pdf 经 OCR 转 md"
    return f"# {file_path.stem}\n\n{joined}\n" if joined else "", note


def rebuild_ledger(root: Path, main_root: Path, ledger_path: Path) -> None:
    existing_rows = read_existing_ledger_rows(ledger_path)
    done_titles = load_done_titles(root)
    entries = collect_effective_entries(main_root, existing_rows, done_titles)
    lines = [LEDGER_HEADER]
    for index, entry in enumerate(entries, start=1):
        lines.append(
            f"| {index} | {entry.title} | {entry.author} | 书籍 | `{entry.source_path}` | {entry.status} | {entry.remark} |"
        )
    ledger_path.write_text(append_brand_footer("\n".join(lines).rstrip() + "\n"), encoding="utf-8")


def read_existing_ledger_rows(ledger_path: Path) -> list[dict[str, str]]:
    if not ledger_path.exists():
        return []
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    for line in ledger_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) == {"-"}:
            continue
        if cells[0] == "序号":
            headers = cells
            continue
        if headers and len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def load_done_titles(root: Path) -> set[str]:
    provenance_dir = root / "01_Agent系统" / "04_小拆-内容拆解Agent" / "99_执行记录" / "正式产物来源"
    done: set[str] = set()
    if not provenance_dir.exists():
        return done
    for path in provenance_dir.glob("*.json"):
        if path.stem.endswith("_充分拆解记录"):
            continue
        done.add(normalize_title_key(path.stem))
    return done


def collect_effective_entries(
    main_root: Path,
    existing_rows: list[dict[str, str]],
    done_titles: set[str],
) -> list[LedgerEntry]:
    row_groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in existing_rows:
        if row.get("资料类型", "").strip() != "书籍":
            continue
        raw_path = row.get("原始资料文件路径", "").strip().strip("`")
        category = extract_category_from_relative(raw_path)
        title = normalize_title_key(row.get("资料标题", "").strip())
        if not category or not title:
            continue
        row_groups.setdefault((category, title), []).append(row)

    candidates: dict[tuple[str, str], tuple[int, Path, str, str]] = {}
    for file_path in iter_source_files(main_root):
        category = file_path.parent.name
        title, author = parse_title_author(file_path.stem)
        clean_title = clean_title_text(title)
        clean_author = clean_author_text(author or "未知作者")
        priority = candidate_priority(file_path)
        key = (category, normalize_title_key(clean_title))
        current = candidates.get(key)
        candidate = (priority, file_path, clean_title, clean_author)
        if current is None or candidate < current:
            candidates[key] = candidate

    entries: list[LedgerEntry] = []
    asset_root = main_root.parents[1]
    for (category, title_key), (_, file_path, clean_title, clean_author) in sorted(
        candidates.items(), key=lambda item: (item[0][0], item[1][2])
    ):
        group = row_groups.get((category, title_key), [])
        source_path = file_path.relative_to(asset_root).as_posix()
        author = choose_author(clean_author, source_path, group)
        status = choose_status(title_key, file_path, group, done_titles)
        remark = choose_remark(file_path, source_path, group)
        entries.append(
            LedgerEntry(
                category=category,
                title=clean_title,
                author=author,
                source_path=source_path,
                status=status,
                remark=remark,
            )
        )
    return entries


def candidate_priority(file_path: Path) -> int:
    if file_path.suffix.lower() == ".md" and re.fullmatch(r"《[^》]+》\.md", file_path.name):
        return 0
    if file_path.suffix.lower() == ".md":
        return 1
    if file_path.suffix.lower() == ".txt":
        return 2
    if file_path.suffix.lower() == ".pdf":
        return 3
    return 4


def extract_category_from_relative(relative: str) -> str:
    marker = "01_好书原始资料/"
    if marker not in relative:
        return ""
    tail = relative.split(marker, 1)[1]
    parts = [part for part in tail.split("/") if part]
    if len(parts) < 2:
        return ""
    return parts[0]


def choose_author(default_author: str, source_path: str, rows: list[dict[str, str]]) -> str:
    for row in rows:
        if row.get("原始资料文件路径", "").strip().strip("`") == source_path:
            value = clean_author_text(row.get("作者/来源主体", "").strip() or default_author)
            if value != "未知作者":
                return value
    for row in rows:
        value = clean_author_text(row.get("作者/来源主体", "").strip() or default_author)
        if value != "未知作者":
            return value
    return default_author


def choose_status(title_key: str, file_path: Path, rows: list[dict[str, str]], done_titles: set[str]) -> str:
    if title_key in done_titles:
        return "已拆解"
    status_order = ("待重拆", "未拆解", "已拆解")
    for target_status in status_order:
        for row in rows:
            if row.get("当前状态", "").strip() == target_status:
                return target_status
    if file_path.suffix.lower() == ".md" and re.fullmatch(r"《[^》]+》\.md", file_path.name):
        return "未拆解"
    return "未拆解"


def choose_remark(file_path: Path, source_path: str, rows: list[dict[str, str]]) -> str:
    current_remarks: list[str] = []
    all_remarks: list[str] = []
    for row in rows:
        row_path = row.get("原始资料文件路径", "").strip().strip("`")
        remark = row.get("备注", "").strip()
        if row_path == source_path and remark:
            current_remarks.append(remark)
    for row in rows:
        remark = row.get("备注", "").strip()
        if remark:
            all_remarks.append(remark)

    remarks = current_remarks + [item for item in all_remarks if item not in current_remarks]
    if not remarks:
        if file_path.suffix.lower() == ".md" and re.fullmatch(r"《[^》]+》\.md", file_path.name):
            return "已是正式 md，完成清单重建"
        if file_path.suffix.lower() == ".txt":
            return "txt 原始文件待标准化入库"
        if file_path.suffix.lower() == ".pdf":
            return "pdf 原始文件待标准化入库"
        if file_path.suffix.lower() == ".epub":
            return "epub 原始文件待标准化入库"
        return "待补充来源备注"
    deduped: list[str] = []
    seen: set[str] = set()
    for remark in remarks:
        normalized = re.sub(r"\s+", " ", remark).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    compressed = compress_remarks(file_path, deduped)
    return "；".join(compressed) if compressed else "待补充来源备注"


def normalize_title_key(value: str) -> str:
    return clean_title_text(value.strip().strip("《》"))


def compress_remarks(file_path: Path, remarks: list[str]) -> list[str]:
    source_note = summarize_source_note(file_path, remarks)
    progress_note = summarize_progress_note(remarks)

    compressed: list[str] = []
    for item in (source_note, progress_note):
        if item and item not in compressed:
            compressed.append(item)
    if compressed:
        return compressed
    return remarks[:1]


def summarize_source_note(file_path: Path, remarks: list[str]) -> str:
    source_patterns = [
        "由小息通过 pymupdf4llm + RapidOCR 从扫描型 PDF 分段 OCR 转 md 正式入库",
        "由小息从外部 PDF 转 md 正式入库",
        "2026-07-28 从原始 PDF 重新补回正式 md",
        "2026-07-28 统一源文件命名为《未来的工作》.md",
        "md 原文保留",
        "txt 转 md",
        "pdf 经 OCR 转 md",
        "pdf 直提文本",
        "已是正式 md，完成清单校验",
        "已是正式 md，完成清单重建",
        "已迁入正式原始知识库",
    ]
    for pattern in source_patterns:
        if pattern in remarks:
            return pattern
    if file_path.suffix.lower() == ".md" and re.fullmatch(r"《[^》]+》\.md", file_path.name):
        return "已是正式 md，完成清单重建"
    if file_path.suffix.lower() == ".txt":
        return "txt 原始文件待标准化入库"
    if file_path.suffix.lower() == ".pdf":
        return "pdf 原始文件待标准化入库"
    if file_path.suffix.lower() == ".epub":
        return "epub 原始文件待标准化入库"
    return ""


def summarize_progress_note(remarks: list[str]) -> str:
    if any("按充分拆解合同通过审核并晋升正式模块" in remark for remark in remarks):
        return "已通过充分拆解审核并晋升正式模块"
    if any("候选产物未通过充分拆解审核，未晋升正式模块" in remark for remark in remarks):
        return "候选产物曾退回，尚未晋升正式模块"
    if any("因模板化误区步骤配平被撤回" in remark for remark in remarks):
        return "曾因模板化配平退回"
    return ""


def print_report(results: list[Result], apply: bool) -> None:
    mode = "正式写入" if apply else "预演"
    print(f"[原始资料标准化入库] {mode}")
    ok = 0
    fail = 0
    skip = 0
    for item in results:
        if item.status == "ok":
            ok += 1
        elif item.status == "fail":
            fail += 1
        else:
            skip += 1
        target = item.target if item.target else "-"
        print(f"{item.status}\t{item.source}\t=>\t{target}\t{item.note}")
    print(f"统计: ok={ok}, fail={fail}, skip={skip}")


def refresh_dashboard(root: Path) -> None:
    script = root / "tools" / "build_xiaojiang_dashboard.py"
    if not script.exists():
        return
    subprocess.run([sys.executable, str(script)], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
