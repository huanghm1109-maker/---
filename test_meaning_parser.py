"""普通释义与专业领域释义拆分测试。"""

import unittest

from meaning_parser import DomainMeaning, parse_meanings


class MeaningParserTest(unittest.TestCase):
    def test_splits_ordinary_and_domain_meanings(self):
        sections = parse_meanings("n. 苹果, 家伙\\n[医] 苹果")

        self.assertEqual(sections.general, ("n. 苹果, 家伙",))
        self.assertEqual(
            sections.specialized,
            (DomainMeaning(domain="医", text="苹果"),),
        )

    def test_supports_chinese_brackets_and_mixed_lines(self):
        sections = parse_meanings(
            "n. 电脑, 电子计算机\n【计】 计算机\n[网络] 网络"
        )

        self.assertEqual(sections.general, ("n. 电脑, 电子计算机",))
        self.assertEqual(
            [meaning.domain for meaning in sections.specialized],
            ["计", "网络"],
        )

    def test_handles_actual_and_literal_newlines(self):
        sections = parse_meanings("n. 银行\n[医] 库\r\n[法] 银行")

        self.assertEqual(sections.general, ("n. 银行",))
        self.assertEqual(
            [meaning.text for meaning in sections.specialized],
            ["库", "银行"],
        )


if __name__ == "__main__":
    unittest.main()
