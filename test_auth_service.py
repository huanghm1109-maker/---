"""用户名、密码和注册邀请码规则测试。"""

import unittest

from auth_service import (
    build_credentials,
    hash_password,
    normalize_username,
    password_matches,
    registration_code_matches,
    validate_password,
    validate_username,
)


class AuthServiceTest(unittest.TestCase):
    def test_username_is_normalized(self):
        self.assertEqual(normalize_username("  Student-A  "), "student-a")
        self.assertTrue(validate_username("student-a"))
        self.assertFalse(validate_username("学生"))
        self.assertFalse(validate_username("a"))

    def test_password_hash_does_not_store_plain_text(self):
        password_hash = hash_password("Strong1!")

        self.assertNotEqual(password_hash, "Strong1!")
        self.assertTrue(password_matches("Strong1!", password_hash))
        self.assertFalse(password_matches("Wrong1!", password_hash))

    def test_password_rules_and_registration_code(self):
        self.assertTrue(validate_password("Strong1!"))
        self.assertFalse(validate_password("weak"))
        self.assertTrue(registration_code_matches("class-123", "class-123"))
        self.assertFalse(registration_code_matches("wrong", "class-123"))
        self.assertTrue(registration_code_matches("", ""))

    def test_credentials_contain_hashes(self):
        credentials = build_credentials(
            [{"username": "student-a", "password_hash": "hash-a"}]
        )

        self.assertEqual(
            credentials["usernames"]["student-a"]["password"],
            "hash-a",
        )


if __name__ == "__main__":
    unittest.main()
