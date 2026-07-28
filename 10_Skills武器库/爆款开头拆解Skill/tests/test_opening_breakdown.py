from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_baokuan_opening_breakdown.py"
SPEC = importlib.util.spec_from_file_location("opening_breakdown", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OpeningBreakdownTests(unittest.TestCase):
    def functions_for(self, script: str) -> tuple[list[str], list[str]]:
        sentences = MODULE.extract_function_sentences(script, limit=5)
        functions = [
            MODULE.detect_core_function(sentence, idx, len(sentences))
            for idx, sentence in enumerate(sentences, start=1)
        ]
        return sentences, functions

    def test_bk001_keeps_existing_granularity(self) -> None:
        script = (
            "这个世界是可以作弊的，而且正大光明的作弊。"
            "这条视频的内容会很长，到底有多长我也不知道，也没打草稿啊。"
            "聊到哪儿算哪儿啊。"
            "但肯定会非常长。"
            "数据呢，我无所谓啊，因为我随时可能会把它删了啊。"
        )
        sentences, functions = self.functions_for(script)
        self.assertEqual(len(sentences), 5)
        self.assertEqual(
            functions,
            ["反常识判断", "降低防备", "降低防备", "内容预告", "降低防备"],
        )

    def test_bk002_semantic_chain(self) -> None:
        script = (
            "今年是我不上班儿的第7年，为了实现这个事儿呢，我前后总共是裸辞了3次。"
            "但是在整个经历里面，我觉得最值得说的一个点其实是4个字，叫做不要创业。"
            "我说这个话从我嘴里说出来会比较奇怪，因为你去看我账号主页的视频，我可能一半以上都在讲创业相关的方法论。"
            "但是我连续经历三次的情况，就是在我辞职离开公司的那一刻，我所面临的情况和我后面所经历的创业的情况，它是完全相反的，这是两套完全不同的游戏规则。"
            "我第一次辞职是我大学本科毕业的第一年，那时候我22岁，那我当时想从职场脱离出来的这个情况，就跟所有想要经历这个状态的人一样，对吧？"
        )
        sentences, functions = self.functions_for(script)
        self.assertEqual(len(sentences), 5)
        self.assertEqual(
            functions,
            ["经历背书", "反常识判断", "身份冲突", "规则反转", "故事引入"],
        )

    def test_bk003_repairs_asr_and_splits_by_function(self) -> None:
        script = (
            "如何在24小时以内找到自己的生意并开始盈有上次发这个卡是2024年啊，"
            "发完之后让我的小红书两天半涨了1万粉丝，因为虽然听起来很像标题打了。"
            "但你看完之后发现这真的是一个可以实现的事情，一个合适的参考对标是真的可以让你在几个小时以内就建立起自己的生意的。"
            "今天给大家公开一个这个我的表格工作法，可以让你只用这么一个Excel表格就找到适合自己去模仿局这边的生意。"
        )
        sentences, functions = self.functions_for(script)
        self.assertEqual(len(sentences), 5)
        self.assertEqual(
            functions,
            ["结果承诺", "案例证明", "质疑回应", "可行性证明", "方法预告"],
        )
        self.assertTrue(all(MODULE.han_len(sentence) <= MODULE.SOFT_SENTENCE_LIMIT for sentence in sentences))

    def test_unknown_function_is_not_content_preview(self) -> None:
        self.assertEqual(MODULE.detect_core_function("这件事让我想了很久。", 2, 5), MODULE.UNKNOWN_FUNCTION)

    def test_overlong_sentence_is_rejected(self) -> None:
        sentence = "这是一个需要重新切分的复杂判断" * 12 + "。"
        issues = MODULE.validate_breakdown_components(
            [sentence] * 5,
            ["结果承诺"] * 5,
            ["明确结果＋目标对象＋结果承诺"] * 5,
            ["给出明确结果"] * 5,
            ["你可以获得【明确结果】。"] * 5,
            {"适合的新正文": "正文具有明确结果承诺"},
        )
        self.assertTrue(any("切分失败" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
