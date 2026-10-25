"""用 Streamlit 自带 AppTest 验证两种搜索模式。

运行：
    python -m unittest -v test_cet_search.py
"""

import os
import unittest

from streamlit.testing.v1 import AppTest


# 测试不读取真实 Supabase secrets，使用隔离的本地模式。
os.environ["WORD_BOOK_ALLOW_LOCAL_MODE"] = "1"

CET_MODE = "四六级词汇优先"
ALL_MODE = "全词库搜索"


class CetSearchTest(unittest.TestCase):
    def query(self, word: str, mode: str) -> AppTest:
        """启动无浏览器的页面实例，并模拟输入、选择和点击。"""

        app = AppTest.from_file("app.py").run(timeout=20)
        app.selectbox[0].set_value(mode)
        app.text_input[0].set_value(word)
        app.button[0].click().run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        return app

    def test_cet_word_is_highlighted(self):
        app = self.query("zebra", CET_MODE)

        messages = [message.value for message in app.success]
        self.assertTrue(any("四六级词汇" in message for message in messages))
        self.assertIn("zebra", [header.value for header in app.subheader])

    def test_non_cet_word_falls_back_to_full_dictionary(self):
        app = self.query("apple", CET_MODE)

        messages = [message.value for message in app.warning]
        self.assertTrue(
            any("不属于四六级范围" in message for message in messages)
        )
        self.assertIn("apple", [header.value for header in app.subheader])

    def test_full_dictionary_mode_has_no_cet_range_warning(self):
        app = self.query("apple", ALL_MODE)

        messages = [message.value for message in app.warning]
        self.assertFalse(
            any("不属于四六级范围" in message for message in messages)
        )
        self.assertIn("apple", [header.value for header in app.subheader])


if __name__ == "__main__":
    unittest.main()
