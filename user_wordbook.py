"""按登录用户名隔离账号和生词的数据访问层。"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class UserWordBookError(RuntimeError):
    """多用户生词存储不可用。"""


class UserWordBookStore:
    """使用 PostgreSQL 或本地 SQLite 保存账号和每位用户的生词。"""

    def __init__(self, database_url=None, sqlite_path=None):
        self.database_url = database_url
        self.sqlite_path = (
            Path(sqlite_path) if sqlite_path is not None else None
        )
        self.is_postgres = bool(database_url)
        self.create_schema()

    def _connect(self):
        if self.is_postgres:
            try:
                import psycopg
            except ImportError as error:
                raise UserWordBookError(
                    "缺少 psycopg，请重新安装 requirements.txt"
                ) from error
            return psycopg.connect(self.database_url)

        if self.sqlite_path is None:
            raise UserWordBookError("没有配置用户生词数据库")
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.sqlite_path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self):
        """提交成功事务或回滚失败事务，并始终关闭连接。"""

        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _placeholder(self):
        return "%s" if self.is_postgres else "?"

    def create_schema(self):
        """创建账号表和用户生词表。"""

        created_at_type = "TIMESTAMPTZ" if self.is_postgres else "TEXT"
        users_sql = f"""
            CREATE TABLE IF NOT EXISTS app_users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at {created_at_type} NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """
        words_sql = f"""
            CREATE TABLE IF NOT EXISTS wordbook_entries (
                username TEXT NOT NULL,
                word TEXT NOT NULL,
                normalized TEXT NOT NULL,
                created_at {created_at_type} NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (username, normalized),
                FOREIGN KEY (username) REFERENCES app_users(username)
                    ON DELETE CASCADE
            )
        """
        try:
            with self._connection() as connection:
                connection.execute(users_sql)
                connection.execute(words_sql)
        except Exception as error:
            raise UserWordBookError(
                f"无法初始化用户生词数据库：{error}"
            ) from error

    @staticmethod
    def normalize_username(username):
        normalized = username.strip().casefold()
        if not normalized:
            raise UserWordBookError("用户名不能为空")
        return normalized

    def list_users(self):
        """读取登录所需的用户名和密码哈希。"""

        sql = """
            SELECT username, password_hash
            FROM app_users
            ORDER BY lower(username)
        """
        try:
            with self._connection() as connection:
                rows = connection.execute(sql).fetchall()
        except Exception as error:
            raise UserWordBookError(f"无法读取用户账号：{error}") from error
        return [
            {"username": row[0], "password_hash": row[1]}
            for row in rows
        ]

    def add_user(self, username, password_hash):
        """创建账号；已存在时返回 False。"""

        normalized = self.normalize_username(username)
        placeholder = self._placeholder()
        sql = f"""
            INSERT INTO app_users (username, password_hash)
            VALUES ({placeholder}, {placeholder})
            ON CONFLICT (username) DO NOTHING
        """
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    sql, (normalized, password_hash)
                )
                return cursor.rowcount > 0
        except Exception as error:
            raise UserWordBookError(f"无法创建账号：{error}") from error

    def list_words(self, username):
        """返回一个用户自己的生词，不包含其他用户的数据。"""

        normalized_username = self.normalize_username(username)
        placeholder = self._placeholder()
        sql = f"""
            SELECT word
            FROM wordbook_entries
            WHERE username = {placeholder}
            ORDER BY lower(word)
        """
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    sql, (normalized_username,)
                ).fetchall()
        except Exception as error:
            raise UserWordBookError(f"无法读取个人生词：{error}") from error
        return [row[0] for row in rows]

    def add_word(self, username, word):
        """只给当前用户添加单词；重复添加返回 False。"""

        normalized_username = self.normalize_username(username)
        placeholder = self._placeholder()
        sql = f"""
            INSERT INTO wordbook_entries (username, word, normalized)
            VALUES ({placeholder}, {placeholder}, {placeholder})
            ON CONFLICT (username, normalized) DO NOTHING
        """
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    sql, (normalized_username, word, word.casefold())
                )
                return cursor.rowcount > 0
        except Exception as error:
            raise UserWordBookError(f"无法保存个人生词：{error}") from error

    def remove_word(self, username, word):
        """只删除当前用户自己的单词。"""

        normalized_username = self.normalize_username(username)
        placeholder = self._placeholder()
        sql = f"""
            DELETE FROM wordbook_entries
            WHERE username = {placeholder} AND normalized = {placeholder}
        """
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    sql, (normalized_username, word.casefold())
                )
                return cursor.rowcount > 0
        except Exception as error:
            raise UserWordBookError(f"无法删除个人生词：{error}") from error

    def contains(self, username, word):
        normalized_username = self.normalize_username(username)
        placeholder = self._placeholder()
        sql = f"""
            SELECT 1
            FROM wordbook_entries
            WHERE username = {placeholder} AND normalized = {placeholder}
            LIMIT 1
        """
        try:
            with self._connection() as connection:
                return connection.execute(
                    sql, (normalized_username, word.casefold())
                ).fetchone() is not None
        except Exception as error:
            raise UserWordBookError(f"无法检查个人生词：{error}") from error
