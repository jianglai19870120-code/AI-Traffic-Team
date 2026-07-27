from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from brand_footer import append_brand_footer

BOOK_EXTENSIONS = {".md", ".txt", ".pdf", ".epub"}
TEXT_EXTENSIONS = {".md", ".txt"}
OCR_MIN_TEXT = 120


@dataclass
class Result:
    source: Path
    status: str
    title: str
    author: str
    target: Path | None
    note: str


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
        ensure_ledger_entry(
            ledger_path=ledger_path,
            category_dir=category_dir,
            target_name=target_name,
            title=clean_title,
            author=clean_author,
            apply=apply,
            remark="已是正式 md，完成清单校验",
        )
        return Result(file_path, "ok", clean_title, clean_author, file_path, "已是正式 md")

    content, note = extract_markdown_content(file_path)
    if not content.strip():
        return Result(file_path, "fail", clean_title, clean_author, None, f"正文为空：{note}")

    if apply:
        target_path.write_text(content, encoding="utf-8")
        if file_path != target_path and file_path.exists():
            # 标准化入库阶段先只删除旧 md 重命名场景；非 md 原文件等待小审通过后再删
            if file_path.suffix.lower() == ".md":
                file_path.unlink()
        ensure_ledger_entry(
            ledger_path=ledger_path,
            category_dir=category_dir,
            target_name=target_name,
            title=clean_title,
            author=clean_author,
            apply=True,
            remark=note,
        )
    else:
        ensure_ledger_entry(
            ledger_path=ledger_path,
            category_dir=category_dir,
            target_name=target_name,
            title=clean_title,
            author=clean_author,
            apply=False,
            remark=note,
        )

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
                result, _ = ocr(pix.samples, use_det=True, use_cls=True, use_rec=True)
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


def ensure_ledger_entry(
    ledger_path: Path,
    category_dir: Path,
    target_name: str,
    title: str,
    author: str,
    apply: bool,
    remark: str,
) -> None:
    relative = f"01_原始知识库/01_好书原始资料/{category_dir.name}/" + target_name
    row = f"| AUTO | {title} | {author} | 书籍 | `{relative}` | 未拆解 | {remark} |"
    if not apply:
        return

    content = ledger_path.read_text(encoding="utf-8", errors="ignore")
    if f"`{relative}`" in content:
        return

    marker = "|---|---|---|---|---|---|---|"
    if marker not in content:
        return
    content = content.replace(marker, marker + "\n" + row, 1)
    ledger_path.write_text(append_brand_footer(content), encoding="utf-8")


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
