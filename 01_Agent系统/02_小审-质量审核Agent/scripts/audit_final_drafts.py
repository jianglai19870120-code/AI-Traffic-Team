from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PRIVATE_AUDIT_DIR = ROOT / "_private" / "agent_records" / "02_小审-质量审核Agent" / "审核记录"
DRAFT_ROOT = ROOT / "_private" / "assets" / "07_润色成稿库" / "01_干货型成稿"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="小审成稿放行审核")
    parser.add_argument("--file", required=True, help="待审核成稿 Markdown 文件绝对路径")
    parser.add_argument("--write-report", action="store_true", help="写入正式审核记录")
    return parser.parse_args()


def split_body(text: str) -> str:
    content_lines: list[str] = []
    meta_seen = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            meta_seen = 1
            continue
        if meta_seen and stripped.startswith("文案结构："):
            meta_seen = 2
            continue
        if meta_seen >= 2 and stripped.startswith("开头卡片编号："):
            meta_seen = 3
            continue
        if meta_seen >= 3:
            content_lines.append(line)
    return "\n".join(content_lines).strip()


def audit_file(path: Path) -> dict[str, list[str]]:
    issues = {
        "文案阶段": [],
        "文件合同": [],
        "结构保留": [],
        "口播可用性": [],
    }
    if not path.exists():
        issues["文案阶段"].append("文件不存在")
        return issues
    if path.suffix.lower() != ".md":
        issues["文案阶段"].append("不是 Markdown 文件")
        return issues
    if DRAFT_ROOT not in path.parents:
        issues["文案阶段"].append("文件不在 07_润色成稿库/01_干货型成稿 目录")

    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    first_heading = next((line.strip() for line in lines if line.strip()), "")
    expected_h1 = f"# {path.stem}"
    if first_heading != expected_h1:
        issues["文件合同"].append("H1 标题与文件名主体不一致")
    if "文案结构：干货型" not in text:
        issues["文件合同"].append("缺少固定字段“文案结构：干货型”")
    if not re.search(r"开头卡片编号：BK\d{3}", text):
        issues["文件合同"].append("缺少合法的开头卡片编号")
    if "|" in text:
        issues["文件合同"].append("成稿中不应再保留表格")
    bad_terms = ["三套干货逻辑方案", "方案 1", "方案1", "文案润色", "选用模块", "对应来源", "匹配结果", "逐句复刻对应关系"]
    hits = [term for term in bad_terms if term in text]
    if hits:
        issues["文件合同"].append("残留中间层字段：" + "、".join(hits))

    body = split_body(text)
    if not body:
        issues["结构保留"].append("缺少正文")
        return issues
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if len(paragraphs) < 3:
        issues["结构保留"].append("正文段落过少，像半成品")
    if not any(token in body for token in ("误区", "很多人", "你以为", "不是", "真正")):
        issues["结构保留"].append("看不出误区段")
    if sum(body.count(token) for token in ("第一", "先", "第二", "再", "第三", "最后")) < 4:
        issues["结构保留"].append("看不出两组步骤的推进结构")
    if not any(token in body for token in ("接下来", "说到这里", "再往下", "但问题是", "真正到了这一步", "这时候", "接着", "然后第二步")):
        issues["结构保留"].append("过渡承接感偏弱，疑似没有保留中间桥接")
    if not any(token in body for token in ("所以", "最后", "说到底", "归根到底")):
        issues["结构保留"].append("看不出金句收口段")

    if any(token in body for token in ("待补", "待确认", "后面再写", "TODO", "这里可以")):
        issues["口播可用性"].append("正文仍有中间态痕迹")
    if "```" in body:
        issues["口播可用性"].append("成稿中不应出现代码块")
    if len(re.findall(r"[。！？!?]", body)) < 8:
        issues["口播可用性"].append("口播句数过少，像压缩提纲")
    return issues


def write_report(path: Path, issues: dict[str, list[str]], passed: bool) -> Path:
    PRIVATE_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report = PRIVATE_AUDIT_DIR / f"{stamp}_成稿放行审核_{path.stem}.md"
    lines = [
        "# 小审审核记录",
        "",
        f"- 审核时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 审核对象：{path.name}",
        "- 审核类型：成稿放行审核",
        f"- 审核结论：{'通过' if passed else '退回'}",
        "- 对应标准：成稿放行审核标准.md",
        "",
        "## 发现",
        "",
    ]
    if passed:
        lines.append("- 成稿合同成立，结构未被打乱，允许作为正式成稿进入下游使用。")
    else:
        for section, section_issues in issues.items():
            if not section_issues:
                continue
            lines.extend([f"### {section}", ""])
            lines.extend(f"- {issue}" for issue in section_issues)
            lines.append("")
        lines.extend(["## 退回建议", "", "- 退回小写修正成稿润色或结构承接。", "- 修正前不允许作为正式成稿进入下一步。", ""])
    lines.extend(["---", "", "品牌尾注：", "", "- 带你用AI，把你的能力变成你的生意。", "- AI流量工厂作者：姜来已来2046", "- 有任何使用问题，可以联系我！微信： lact175", ""])
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def refresh_dashboard() -> None:
    script = ROOT / "tools" / "build_xiaojiang_dashboard.py"
    if script.exists():
        subprocess.run([sys.executable, str(script)], check=False)


def main() -> int:
    args = parse_args()
    path = Path(args.file)
    issues = audit_file(path)
    passed = all(not section_issues for section_issues in issues.values())
    print(f"[成稿放行审核] file={path} result={'通过' if passed else '退回'}")
    for section, section_issues in issues.items():
        for issue in section_issues:
            print(f"{section}\t{issue}")
    if args.write_report:
        report = write_report(path, issues, passed)
        print(f"report\t{report}")
        refresh_dashboard()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
