"""用户名注册、密码哈希和 authenticator 凭据转换。"""

import hmac

from streamlit_authenticator import Hasher, Validator


USERNAME_PATTERN_MESSAGE = "用户名只能包含英文字母、数字、下划线或连字符，长度 3-20 位。"
PASSWORD_RULE_MESSAGE = (
    "密码需为 8-20 位，并同时包含大写字母、小写字母、数字和特殊字符。"
)


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def validate_username(username: str) -> bool:
    normalized = normalize_username(username)
    return (
        3 <= len(normalized) <= 20
        and all(
            character.isascii()
            and (character.isalnum() or character in {"_", "-"})
            for character in normalized
        )
    )


def validate_password(password: str) -> bool:
    return Validator().validate_password(password)


def hash_password(password: str) -> str:
    return Hasher.hash(password)


def password_matches(password: str, password_hash: str) -> bool:
    try:
        return Hasher.check_pw(password, password_hash)
    except (TypeError, ValueError):
        return False


def registration_code_matches(entered_code: str, expected_code: str) -> bool:
    """没有配置邀请码时允许注册；配置后必须完全匹配。"""

    if not expected_code:
        return True
    return hmac.compare_digest(entered_code.strip(), expected_code)


def build_credentials(users: list[dict]) -> dict:
    """把数据库账号转换成 streamlit-authenticator 需要的结构。"""

    return {
        "usernames": {
            user["username"]: {
                "name": user["username"],
                "password": user["password_hash"],
            }
            for user in users
        }
    }
