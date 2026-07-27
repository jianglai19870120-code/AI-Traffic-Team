from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from brand_footer import append_brand_footer


ROOT = Path(__file__).resolve().parents[3]
PRIVATE_AUDIT_DIR = ROOT / "01_Agent系统" / "02_小审-质量审核Agent" / "99_审核记录"
BODY_ROOT = ROOT / "02_资产中心" / "06_生成正文库" / "01_干货型文案"
EXPECTED_HEADER = ["序号", "逻辑关系", "选用模块", "对应来源"]
EXPECTED_FLOW = ["误区1", "误区2", "过渡句", "步骤1", "步骤2", "步骤3", "过渡句", "步骤1", "步骤2", "步骤3", "金句收口"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="小审机器文案放行审核")
    parser.add_argument("--file", required=True, help="待审核正文方案 Markdown 文件绝对路径")
    parser.add_argument("--write-report", action="store_true", help="写入正式审核记录")
    return parser.parse_args()


def parse_table(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            rows.append([part.strip() for part in stripped.strip("|").split("|")])
    return rows


def old_terms(text: str) -> list[str]:
    bad_terms = ["三套干货逻辑方案", "方案 1", "方案1", "方案 2", "方案2", "方案 3", "方案3", "文案润色", "爆款开头复刻"]
    return [term for term in bad_terms if term in text]


def audit_file(path: Path) -> dict[str, list[str]]:
    issues = {
        "文案阶段": [],
        "文件合同": [],
        "11行结构": [],
        "模块可用性": [],
    }
    if not path.exists():
        issues["文案阶段"].append("文件不存在")
        return issues
    if path.suffix.lower() != ".md":
        issues["文案阶段"].append("不是 Markdown 文件")
        return issues
    if BODY_ROOT not in path.parents:
        issues["文案阶段"].append("文件不在 06_生成正文库/01_干货型文案 目录")

    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    first_heading = next((line.strip() for line in lines if line.strip()), "")
    expected_h1 = f"# {path.stem}"
    if first_heading != expected_h1:
        issues["文件合同"].append("H1 标题与文件名主体不一致")
    if "文案结构：干货型" not in text:
        issues["文件合同"].append("缺少固定字段“文案结构：干货型”")
    if "主线" not in text:
        issues["文件合同"].append("缺少主线")
    hits = old_terms(text)
    if hits:
        issues["文件合同"].append("残留旧字段：" + "、".join(hits))

    table_rows = parse_table(text)
    if len(table_rows) < 13:
        issues["11行结构"].append("表格行数不足，无法形成固定 11 行结构")
        return issues

    header = table_rows[0]
    body_rows = table_rows[2:]
    if header != EXPECTED_HEADER:
        issues["11行结构"].append("表头不是固定四列表：序号 / 逻辑关系 / 选用模块 / 对应来源")
    if len(body_rows) != 11:
        issues["11行结构"].append(f"正文表格不是固定 11 行，当前 {len(body_rows)} 行")
        return issues

    for idx, row in enumerate(body_rows, start=1):
        if len(row) != 4:
            issues["11行结构"].append(f"第 {idx} 行列数不是 4")
            continue
        _, logic, module, source = row
        expected_logic = EXPECTED_FLOW[idx - 1]
        if logic != expected_logic:
            issues["11行结构"].append(f"第 {idx} 行逻辑关系应为“{expected_logic}”，当前为“{logic}”")
        if logic == "过渡句":
            if not module:
                issues["11行结构"].append(f"第 {idx} 行过渡句为空")
            if source:
                issues["11行结构"].append(f"第 {idx} 行过渡句来源应留空")
        else:
            if not module:
                issues["模块可用性"].append(f"第 {idx} 行缺少选用模块")
            if not source:
                issues["模块可用性"].append(f"第 {idx} 行缺少对应来源")
        if any(token in module for token in ("待补", "待找", "待确认", "后面再写", "TODO")):
            issues["模块可用性"].append(f"第 {idx} 行仍是中间态")

    if text.count("步骤1") < 2 or text.count("步骤2") < 2 or text.count("步骤3") < 2:
        issues["11行结构"].append("两组步骤没有完整展开成 2 组 3 步结构")
    return issues


def write_report(path: Path, issues: dict[str, list[str]], passed: bool) -> Path:
    PRIVATE_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report = PRIVATE_AUDIT_DIR / f"{stamp}_机器文案放行审核_{path.stem}.md"
    lines = [
        "# 小审审核记录",
        "",
        f"- 审核时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 审核对象：{path.name}",
        "- 审核类型：机器文案放行审核",
        f"- 审核结论：{'通过' if passed else '退回'}",
        "- 对应标准：机器文案放行审核标准.md",
        "",
        "## 发现",
        "",
    ]
    if passed:
        lines.append("- 文件合同和 11 行结构均成立，允许进入成稿阶段。")
    else:
        for section, section_issues in issues.items():
            if not section_issues:
                continue
            lines.extend([f"### {section}", ""])
            lines.extend(f"- {issue}" for issue in section_issues)
            lines.append("")
        lines.extend(["## 退回建议", "", "- 退回小写修正正文方案结构或模块引用。", "- 修正前不允许进入 07_润色成稿库。", ""])
    report.write_text(append_brand_footer("\n".join(lines)), encoding="utf-8")
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
    print(f"[机器文案放行审核] file={path} result={'通过' if passed else '退回'}")
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
