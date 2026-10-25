"""离线生词本网页版。

运行方式：
    streamlit run app.py

程序结构：
1. 数据层：读取、保存生词；通过 ECDICT 查询释义。
2. 界面层：接收搜索词，点击查询按钮，展示查询结果。

Streamlit 的特点是“脚本从上到下执行”。页面上的按钮被点击后，
整个脚本会重新运行一次，所以这里用 st.session_state 保存上一次查询。
"""

import json
from pathlib import Path

import streamlit as st

from offline_dictionary import (
    DictionaryEntry,
    DictionaryUnavailableError,
    InvalidWordError,
    OfflineDictionary,
)


# 使用 Path 拼接路径，比直接写字符串更不容易出错。
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "words.json"


@st.cache_resource
def get_dictionary() -> OfflineDictionary:
    """创建一个可复用的离线词典对象。

    @st.cache_resource 会让多个页面访问共用同一个对象，
    避免每次都重新连接 SQLite 数据库。
    """

    return OfflineDictionary(BASE_DIR / "data" / "ecdict.sqlite3")


def load_words() -> list[str]:
    """从 words.json 读取生词，并清理空值和重复项。

    处理前后的例子：
        原数据：[" cat ", "Dog", "cat", 123]
        返回值：["cat", "Dog"]

    casefold() 是适合英文大小写比较的方法，所以 "Cat" 和 "cat"
    会被视为同一个单词。
    """

    if not DATA_FILE.exists():
        return []

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("words.json 的内容必须是列表")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        # 数据损坏时只显示提示，不冒险覆盖用户原文件。
        st.error(f"无法读取生词本：{error}")
        return []

    words: list[str] = []
    seen: set[str] = set()

    # enumerate 常用于需要“值 + 位置/编号”的场景；这里只遍历值。
    for value in data:
        if not isinstance(value, str):
            continue

        word = value.strip()
        key = word.casefold()
        if word and key not in seen:
            words.append(word)
            seen.add(key)

    return words


def save_words(words: list[str]) -> None:
    """按字母顺序保存生词。

    先写临时文件，再替换正式文件。这样即使保存中途失败，
    原来的 words.json 也不容易被写坏。
    """

    words.sort(key=str.casefold)
    temporary_file = DATA_FILE.with_name(f"{DATA_FILE.name}.tmp")
    temporary_file.write_text(
        json.dumps(words, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(DATA_FILE)


def add_to_wordbook(entry: DictionaryEntry) -> bool:
    """把查询结果加入生词本；已存在时返回 False。"""

    words = load_words()
    if any(word.casefold() == entry.word.casefold() for word in words):
        return False

    words.append(entry.word)
    save_words(words)
    return True


def remove_from_wordbook(entry: DictionaryEntry) -> bool:
    """从生词本删除一个单词，并保留文件中已有的拼写形式。"""

    words = load_words()
    remaining_words = [
        word for word in words if word.casefold() != entry.word.casefold()
    ]
    if len(remaining_words) == len(words):
        return False

    save_words(remaining_words)
    return True


def find_saved_word(entry: DictionaryEntry, words: list[str]) -> str | None:
    """返回生词本中与该词对应的原始写法。

    例如查询 "CAT" 时，生词本里的 "Cat" 仍然可以匹配。
    """

    for word in words:
        if word.casefold() == entry.word.casefold():
            return word
    return None


def show_result(entry: DictionaryEntry) -> None:
    """把 DictionaryEntry 对象转换成页面上的结果区域。"""

    st.subheader(entry.word)
    if entry.phonetic:
        st.caption(f"/{entry.phonetic}/")

    st.markdown("**中文释义**")
    translation = entry.translation or "词典中没有中文释义。"
    # ECDICT 中的换行有时保存成字面量 "\\n"，这里转换成真正的换行。
    st.write(translation.replace("\\n", "\n"))

    if entry.definition:
        with st.expander("查看英文释义"):
            st.write(entry.definition.replace("\\n", "\n"))

    saved_word = find_saved_word(entry, load_words())
    if saved_word:
        st.success(f"“{saved_word}”已经在生词本中。")
        if st.button("从生词本移除", type="secondary"):
            if remove_from_wordbook(entry):
                st.rerun()
    else:
        if st.button("加入生词本", type="primary"):
            if add_to_wordbook(entry):
                st.success(f"已将“{entry.word}”加入生词本。")
            else:
                st.info("这个单词已经在生词本中。")


def main() -> None:
    """页面入口：安排输入框、按钮和结果区域。"""

    st.set_page_config(page_title="离线生词本", page_icon="📖", layout="centered")
    st.title("📖 离线生词本")
    st.caption("输入一个英文单词，从本地 ECDICT 词典中查询释义。")

    # 使用表单可以把输入和按钮组合起来，点击“查询”时才提交一次。
    with st.form("search_form", clear_on_submit=False):
        query = st.text_input(
            "搜索单词",
            placeholder="例如：apple",
            max_chars=64,
        )
        submitted = st.form_submit_button("查询", type="primary")

    if submitted:
        # 表单提交后，把搜索词保存下来；单击“收藏”等按钮时仍能显示结果。
        st.session_state.last_query = query.strip()

    st.divider()
    st.subheader("查询结果")

    last_query = st.session_state.get("last_query", "")
    if not last_query:
        st.info("请在上方输入英文单词，然后点击“查询”。")
        return

    try:
        # validate_word 同时完成格式检查与词典查询。
        entry = get_dictionary().validate_word(last_query)
    except InvalidWordError as error:
        st.warning(str(error))
        return
    except DictionaryUnavailableError as error:
        st.error(str(error))
        return

    show_result(entry)

    words = load_words()
    with st.expander(f"我的生词本（{len(words)} 个）"):
        if words:
            st.write("、".join(words))
        else:
            st.caption("生词本还是空的。查询单词后，可以点击“加入生词本”。")


# 直接执行 app.py 时进入 main；被其他文件导入时不会自动运行页面。
if __name__ == "__main__":
    main()
