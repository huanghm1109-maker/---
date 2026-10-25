"""验证不同登录邮箱之间的生词隔离。"""

import tempfile
import unittest
from pathlib import Path

from user_wordbook import UserWordBookStore


class UserWordBookStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_file = (
            Path(self.temporary_directory.name) / "user_wordbooks.sqlite3"
        )
        self.store = UserWordBookStore(sqlite_path=database_file)
        self.store.add_user("student-a", "hash-a")
        self.store.add_user("student-b", "hash-b")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_users_only_see_their_own_words(self):
        self.store.add_word("student-a", "apple")
        self.store.add_word("student-b", "zebra")

        self.assertEqual(
            self.store.list_words("student-a"),
            ["apple"],
        )
        self.assertEqual(
            self.store.list_words("student-b"),
            ["zebra"],
        )

    def test_username_and_word_comparisons_are_case_insensitive(self):
        self.assertTrue(
            self.store.add_word("Student-A", "Apple")
        )
        self.assertFalse(
            self.store.add_word("student-a", "apple")
        )
        self.assertTrue(
            self.store.contains(
                "STUDENT-A",
                "APPLE",
            )
        )

    def test_remove_only_affects_the_selected_user(self):
        self.store.add_word("student-a", "apple")
        self.store.add_word("student-b", "apple")

        self.assertTrue(
            self.store.remove_word("student-a", "APPLE")
        )

        self.assertEqual(
            self.store.list_words("student-a"),
            [],
        )
        self.assertEqual(
            self.store.list_words("student-b"),
            ["apple"],
        )

    def test_accounts_are_not_duplicated(self):
        self.assertFalse(self.store.add_user("Student-A", "another-hash"))
        users = self.store.list_users()
        self.assertEqual(
            [(user["username"], user["password_hash"]) for user in users],
            [("student-a", "hash-a"), ("student-b", "hash-b")],
        )


if __name__ == "__main__":
    unittest.main()
