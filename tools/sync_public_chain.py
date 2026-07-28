from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from brand_footer import append_brand_footer


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "01_Agent系统" / "01_小姜-CEO助理Agent" / "99_本地运行记录"
SUMMARY_JSON = SUMMARY_DIR / "最近公开同步结果.json"
SUMMARY_MD = SUMMARY_DIR / "最近公开同步结果.md"

HIDDEN_DIRS = [
    "02_资产中心/01_原始知识库/99_我的工作纪实",
    "02_资产中心/02_内容模块库/99_工作纪实模块",
    "01_Agent系统/01_小姜-CEO助理Agent/99_本地运行记录",
    "01_Agent系统/02_小审-质量审核Agent/99_审核记录",
    "01_Agent系统/03_小息-信息采集Agent/99_执行记录",
    "01_Agent系统/04_小拆-内容拆解Agent/99_执行记录",
    "03_工作流中心/01_短视频主工作流/99_运行记录",
]

EXCLUDED_PUBLIC_PATHS = [
    "02_资产中心/01_原始知识库/01_好书原始资料",
]

PUBLIC_CHAIN = [
    "00_系统说明",
    "01_Agent系统",
    "02_资产中心/01_原始知识库",
    "02_资产中心/02_内容模块库",
    "02_资产中心/03_对标账号库",
    "02_资产中心/04_爆款选题库",
    "02_资产中心/05_爆款开头库",
    "02_资产中心/06_生成正文库",
    "02_资产中心/07_润色成稿库",
    "02_资产中心/08_视觉配图库",
    "03_工作流中心",
    "10_Skills武器库",
    "tools",
]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_if_changed(path: Path, content: str) -> bool:
    ensure_parent(path)
    previous = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else None
    if previous == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def existing_hidden_dirs() -> list[str]:
    found: list[str] = []
    for rel in HIDDEN_DIRS:
        if (ROOT / rel).exists():
            found.append(rel)
    return found


def build_summary() -> dict:
    return {
        "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "正式系统与衍生资产公开 + 原始书源和本地业务目录排除",
        "public_chain": PUBLIC_CHAIN,
        "hidden_dirs": existing_hidden_dirs(),
        "excluded_public_paths": EXCLUDED_PUBLIC_PATHS,
        "notes": [
            "02_资产中心 已切为正式资产主链。",
            "公开发布同步正式系统、可公开业务资产和书籍衍生模块。",
            "完整书籍原文不进入 GitHub，公开清单使用空白模板。",
            "工作纪实、工作纪实模块、Agent 运行记录与工作流运行记录只作为本地隐藏目录存在。",
            "本脚本不再维护模板替代层，只负责记录当前公开同步口径。",
        ],
    }


def build_summary_md(summary: dict) -> str:
    lines = [
        "# 最近公开同步结果",
        "",
        f"- 同步时间：{summary['synced_at']}",
        f"- 同步模式：{summary['mode']}",
        "",
        "## 当前公开主链",
        "",
    ]
    for item in summary["public_chain"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## 本地隐藏目录",
        "",
    ]
    if summary["hidden_dirs"]:
        for item in summary["hidden_dirs"]:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前未发现本地隐藏目录。")

    lines += [
        "",
        "## 公开包额外排除",
        "",
    ]
    for item in summary["excluded_public_paths"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## 说明",
        "",
    ]
    for note in summary["notes"]:
        lines.append(f"- {note}")

    return append_brand_footer("\n".join(lines))


def sync_public_chain() -> dict:
    summary = build_summary()
    changed_json = write_if_changed(SUMMARY_JSON, json.dumps(summary, ensure_ascii=False, indent=2))
    changed_md = write_if_changed(SUMMARY_MD, build_summary_md(summary))
    summary["updated"] = changed_json or changed_md
    return summary


def main() -> None:
    summary = sync_public_chain()
    print(str(SUMMARY_JSON))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
