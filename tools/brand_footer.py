from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "00_系统说明" / "品牌尾注规范.md"
FALLBACK_BLOCK = "\n".join(
    [
        "---",
        "• 带你用AI，把你的能力变成你的生意",
        "• 有使用问题，或加入我的会员答疑群！",
        "• 姜来已来2046，联系微信： lact175",
        "---",
    ]
)


def load_brand_footer_block() -> str:
    if SPEC_PATH.exists():
        text = SPEC_PATH.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"```md\s*(?P<block>---.*?---)\s*```", text, flags=re.S)
        if match:
            return match.group("block").strip()
    return FALLBACK_BLOCK


BRAND_FOOTER_BLOCK = load_brand_footer_block()


def strip_brand_footer(text: str) -> str:
    patterns = [
        r"\n*---\s*\n品牌尾注：.*?$",
        r"\n*品牌尾注：\s*\n[-•]\s*带你用AI，把你的能力变成你的生意。?\s*\n[-•]\s*(?:AI流量团队作者：姜来已来2046|AI流量工厂作者：姜来已来2046)\s*\n[-•]\s*有任何使用问题，可以联系我！微信：\s*lact175\s*\n*$",
        r"\n*---\s*\n[-•]\s*带你用AI，把你的能力变成你的生意。?\s*\n[-•]\s*(?:AI流量团队作者：姜来已来2046|AI流量工厂作者：姜来已来2046)\s*\n[-•]\s*有任何使用问题，可以联系我！微信：\s*lact175\s*\n*$",
        r"\n*---\s*\n•\s*带你用AI，把你的能力变成你的生意\s*\n•\s*有使用问题，或加入我的会员答疑群！\s*\n•\s*姜来已来2046，联系微信：\s*lact175\s*\n---\s*\n*$",
    ]
    cleaned = text.rstrip()
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.S)
    return cleaned.rstrip()


def append_brand_footer(text: str) -> str:
    cleaned = strip_brand_footer(text)
    if not cleaned:
        return BRAND_FOOTER_BLOCK + "\n"
    return cleaned + "\n\n" + BRAND_FOOTER_BLOCK + "\n"
