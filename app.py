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
import os
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
DATA_FILE = Path(
    os.environ.get("WORD_BOOK_FILE", BASE_DIR / "words.json")
).expanduser().resolve()
SEARCH_MODE_CET = "四六级词汇优先"
SEARCH_MODE_ALL = "全词库搜索"


@st.cache_resource
def get_dictionary() -> OfflineDictionary:
    """创建一个可复用的离线词典对象。

    @st.cache_resource 会让多个页面访问共用同一个对象，
    避免每次都重新连接 SQLite 数据库。
    """

    return OfflineDictionary(BASE_DIR / "data" / "ecdict.sqlite3")


@st.cache_data(ttl="1h", max_entries=2000)
def lookup_word(word: str) -> DictionaryEntry | None:
    """查询并缓存生词本中的一个词。

    生词本每次重绘都需要显示 CET 标记，因此标签查询会重复发生。
    cache_data 按单词缓存结果，并限制最多保存 2000 项，避免缓存无限增长。
    """

    return get_dictionary().lookup(word)


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


def remove_word_from_wordbook(word: str) -> bool:
    """从生词本删除一个单词，并保留文件中已有的拼写形式。"""

    words = load_words()
    remaining_words = [
        saved_word
        for saved_word in words
        if saved_word.casefold() != word.casefold()
    ]
    if len(remaining_words) == len(words):
        return False

    save_words(remaining_words)
    return True


def remove_from_wordbook(entry: DictionaryEntry) -> bool:
    """删除对象写法，方便查询结果区域复用底层删词函数。"""

    return remove_word_from_wordbook(entry.word)


def find_saved_word(entry: DictionaryEntry, words: list[str]) -> str | None:
    """返回生词本中与该词对应的原始写法。

    例如查询 "CAT" 时，生词本里的 "Cat" 仍然可以匹配。
    """

    for word in words:
        if word.casefold() == entry.word.casefold():
            return word
    return None


def wordbook_label(word: str, entry: DictionaryEntry | None) -> str:
    """生成“单词 + CET 等级徽标”的折叠标题。"""

    label = f"**{word}**"
    if entry is None or not entry.is_cet:
        return label

    badge_colors = {"CET4": "green", "CET6": "violet"}
    badges = [
        f":{badge_colors[level]}-badge[{level}]"
        for level in entry.cet_levels
    ]
    return f"{label} {' '.join(badges)}"


def render_wordbook_entry(word: str) -> None:
    """绘制一行生词；只有展开时才加载并显示释义。"""

    try:
        entry = lookup_word(word)
    except DictionaryUnavailableError as error:
        entry = None
        lookup_error = str(error)
    else:
        lookup_error = ""

    expander = st.expander(
        wordbook_label(word, entry),
        key=f"wordbook_expander_{word.casefold()}",
        on_change="rerun",
        icon=":material/book_2:",
    )

    # .open 需要 on_change="rerun" 才有值；折叠时跳过释义渲染。
    if not expander.open:
        return

    with expander:
        if lookup_error:
            st.error(lookup_error)
        elif entry is None:
            st.warning("离线词典中没有找到这个生词。")
        else:
            if entry.phonetic:
                st.caption(f"音标：/{entry.phonetic}/")

            st.markdown("**中文释义**")
            translation = entry.translation or "词典中没有中文释义。"
            st.text(translation.replace("\\n", "\n"))

            if entry.definition:
                st.markdown("**英文释义**")
                st.text(entry.definition.replace("\\n", "\n"))

        if st.button(
            "删除这个单词",
            key=f"delete_word_{word.casefold()}",
            icon=":material/delete:",
            type="secondary",
        ):
            if remove_word_from_wordbook(word):
                st.toast(f"已删除“{word}”")
            st.rerun()


@st.fragment
def render_wordbook() -> None:
    """搜索并展示生词本；搜索只重跑这个独立区域。"""

    st.header("我的生词本")
    words = sorted(load_words(), key=str.casefold)

    search_text = st.text_input(
        "在生词本中搜索",
        type="search",
        placeholder="输入单词或字母",
        key="wordbook_search",
        live="300ms",
    )
    normalized_search = (search_text or "").strip().casefold()
    displayed_words = [
        word for word in words if normalized_search in word.casefold()
    ]

    if normalized_search:
        st.caption(f"找到 {len(displayed_words)} 个，共 {len(words)} 个生词")
    else:
        st.caption(f"共 {len(words)} 个生词，点击单词可展开或收起释义")

    if not words:
        st.info("生词本还是空的。查询单词后，可以点击“加入生词本”。")
        return
    if not displayed_words:
        st.info("生词本中没有匹配的单词。")
        return

    for word in displayed_words:
        render_wordbook_entry(word)


def show_result(entry: DictionaryEntry, search_mode: str) -> None:
    """把 DictionaryEntry 对象转换成页面上的结果区域。"""

    if entry.is_cet:
        cet_levels = " / ".join(entry.cet_levels)
        st.success(f"🎯 四六级词汇：{cet_levels}")
    elif search_mode == SEARCH_MODE_CET:
        st.warning(
            "该词不属于四六级范围，已为你展示全库释义。"
        )

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
        search_mode = st.selectbox(
            "搜索范围",
            options=[SEARCH_MODE_CET, SEARCH_MODE_ALL],
            index=0,
            help="优先模式会标注四六级词汇；非四六级词仍会回退到全词库显示。",
        )
        query = st.text_input(
            "搜索单词",
            placeholder="例如：apple",
            max_chars=64,
        )
        submitted = st.form_submit_button("查询", type="primary")

    if submitted:
        # 表单提交后，把搜索词保存下来；单击“收藏”等按钮时仍能显示结果。
        st.session_state.last_query = query.strip()
        st.session_state.last_mode = search_mode

    st.divider()
    st.subheader("查询结果")

    last_query = st.session_state.get("last_query", "")
    last_mode = st.session_state.get("last_mode", SEARCH_MODE_CET)
    if not last_query:
        st.info("请在上方输入英文单词，然后点击“查询”。")
    else:
        st.caption(f"当前搜索范围：{last_mode}")
        try:
            # validate_word 同时完成格式检查与词典查询。
            entry = get_dictionary().validate_word(last_query)
        except InvalidWordError as error:
            st.warning(str(error))
        except DictionaryUnavailableError as error:
            st.error(str(error))
        else:
            show_result(entry, last_mode)

    st.divider()
    render_wordbook()


# 直接执行 app.py 时进入 main；被其他文件导入时不会自动运行页面。
if __name__ == "__main__":
    main()
