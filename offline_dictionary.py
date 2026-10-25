import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DICTIONARY_FILE = Path(__file__).resolve().parent / "data" / "ecdict.sqlite3"
ENGLISH_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
CET_TAGS = ("cet4", "cet6")


class DictionaryUnavailableError(RuntimeError):
    pass


class InvalidWordError(ValueError):
    pass


@dataclass(frozen=True)
class DictionaryEntry:
    word: str
    phonetic: str
    translation: str
    definition: str
    tag: str

    @property
    def cet_levels(self):
        """返回该词拥有的 CET 标签，例如 ("CET4", "CET6")。"""

        tags = {
            token
            for token in re.split(r"[\s,;]+", self.tag.casefold().strip())
            if token
        }
        return tuple(tag.upper() for tag in CET_TAGS if tag in tags)

    @property
    def is_cet(self):
        """该词是否至少属于 CET4 或 CET6。"""

        return bool(self.cet_levels)


class OfflineDictionary:
    def __init__(self, database_path=DICTIONARY_FILE):
        self.database_path = Path(database_path)
        self.connection = None

    def connect(self):
        if self.connection is not None:
            return
        if not self.database_path.is_file():
            raise DictionaryUnavailableError(
                f"找不到离线词典：{self.database_path}"
            )

        uri = f"{self.database_path.resolve().as_posix()}?mode=ro"
        try:
            self.connection = sqlite3.connect(
                f"file:{uri}", uri=True, check_same_thread=False
            )
            self.connection.execute("PRAGMA query_only = ON")
        except sqlite3.Error as error:
            raise DictionaryUnavailableError(f"无法打开离线词典：{error}") from error

    def lookup(self, word):
        self.connect()
        normalized = word.casefold()
        try:
            row = self.connection.execute(
                """
                SELECT word, phonetic, translation, definition, tag
                FROM entries
                WHERE normalized = ?
                """,
                (normalized,),
            ).fetchone()
        except sqlite3.Error as error:
            raise DictionaryUnavailableError(f"读取离线词典失败：{error}") from error

        return DictionaryEntry(*row) if row else None

    def validate_word(self, raw_text):
        if not raw_text:
            raise InvalidWordError("请先输入一个英文单词。")
        if any(character.isspace() for character in raw_text):
            raise InvalidWordError("一次只能输入一个英文单词，不能包含空格。")
        if self.contains_chinese(raw_text):
            raise InvalidWordError("生词必须是英文单词，不能输入中文。")
        if len(raw_text) > 64:
            raise InvalidWordError("单词过长，请检查是否输入错误。")
        if not ENGLISH_WORD_PATTERN.fullmatch(raw_text):
            raise InvalidWordError("只能输入英文字母，以及单词内部的连字符或撇号。")

        entry = self.lookup(raw_text)
        if entry is None:
            raise InvalidWordError(
                f"离线词典中找不到“{raw_text}”，请检查拼写；随机字母不能添加。"
            )
        return entry

    @staticmethod
    def contains_chinese(text):
        return any(
            "\u3400" <= character <= "\u4dbf"
            or "\u4e00" <= character <= "\u9fff"
            or "\uf900" <= character <= "\ufaff"
            for character in text
        )

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
