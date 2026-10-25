"""生词本列表、CET 标记、搜索、展开和删除的自动化测试。"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class WordbookUiTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temporary_directory.name) / "words.json"
        self.previous_data_file = os.environ.get("WORD_BOOK_FILE")
        os.environ["WORD_BOOK_FILE"] = str(self.data_file)

    def tearDown(self):
        if self.previous_data_file is None:
            os.environ.pop("WORD_BOOK_FILE", None)
        else:
            os.environ["WORD_BOOK_FILE"] = self.previous_data_file
        self.temporary_directory.cleanup()

    def run_app(self, words: list[str]) -> AppTest:
        self.data_file.write_text(
            json.dumps(words, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        app = AppTest.from_file("app.py").run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        return app

    def test_each_word_is_one_row_with_distinct_cet_badges(self):
        app = self.run_app(["apple", "zebra"])
        labels = {
            expander.key: expander.label for expander in app.expander
        }

        self.assertEqual(len(labels), 2)
        self.assertNotIn("CET4", labels["wordbook_expander_apple"])
        self.assertIn("CET4", labels["wordbook_expander_zebra"])
        self.assertIn("CET6", labels["wordbook_expander_zebra"])
        self.assertEqual(len(app.text), 0)

    def test_wordbook_search_filters_rows(self):
        app = self.run_app(["apple", "zebra"])

        app.text_input(key="wordbook_search").set_value("ze").run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        keys = [expander.key for expander in app.expander]
        self.assertEqual(keys, ["wordbook_expander_zebra"])

    def test_opening_word_shows_translation_and_delete_button(self):
        app = self.run_app(["apple", "zebra"])
        app.session_state["wordbook_expander_apple"] = True
        app.run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(
            any("苹果" in markdown.value for markdown in app.markdown)
        )
        self.assertTrue(any(button.key == "delete_word_apple" for button in app.button))

    def test_domain_meaning_is_hidden_until_toggle_is_enabled(self):
        app = self.run_app(["computer"])
        app.session_state["wordbook_expander_computer"] = True
        app.run(timeout=20)

        visible_text = "\n".join(markdown.value for markdown in app.markdown)
        self.assertIn("电脑", visible_text)
        self.assertNotIn("[计] 计算机", visible_text)

        app.toggle(key="show_special_wordbook_computer").set_value(True).run(
            timeout=20
        )

        expanded_text = "\n".join(markdown.value for markdown in app.markdown)
        self.assertIn("**[计]**", expanded_text)
        self.assertIn("计算机", expanded_text)
        self.assertEqual(len(app.exception), 0)

    def test_cet_common_meaning_is_marked_before_domain_meaning(self):
        app = self.run_app(["zebra"])
        app.session_state["wordbook_expander_zebra"] = True
        app.run(timeout=20)

        markdown_values = [markdown.value for markdown in app.markdown]
        cet_heading_index = next(
            index
            for index, value in enumerate(markdown_values)
            if "四六级重点词释义" in value
        )
        self.assertIn("CET4", markdown_values[cet_heading_index])
        self.assertIn("CET6", markdown_values[cet_heading_index])

    def test_delete_button_removes_only_selected_word(self):
        app = self.run_app(["apple", "zebra"])
        app.session_state["wordbook_expander_apple"] = True
        app.run(timeout=20)

        app.button(key="delete_word_apple").click().run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        saved_words = json.loads(self.data_file.read_text(encoding="utf-8"))
        self.assertEqual(saved_words, ["zebra"])


if __name__ == "__main__":
    unittest.main()
