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
import streamlit_authenticator as stauth

from auth_service import (
    PASSWORD_RULE_MESSAGE,
    USERNAME_PATTERN_MESSAGE,
    build_credentials,
    hash_password,
    normalize_username,
    registration_code_matches,
    validate_password,
    validate_username,
)
from meaning_parser import parse_meanings
from offline_dictionary import (
    DictionaryEntry,
    DictionaryUnavailableError,
    InvalidWordError,
    OfflineDictionary,
)
from user_wordbook import UserWordBookError, UserWordBookStore


# 使用 Path 拼接路径，比直接写字符串更不容易出错。
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = Path(
    os.environ.get("WORD_BOOK_FILE", BASE_DIR / "words.json")
).expanduser().resolve()
SEARCH_MODE_CET = "四六级词汇优先"
SEARCH_MODE_ALL = "全词库搜索"
LOCAL_USER = "本地模式"


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


def is_local_request() -> bool:
    """只有本机开发环境允许不登录使用原有的 words.json。"""

    if os.environ.get("WORD_BOOK_ALLOW_LOCAL_MODE") == "1":
        return True

    host = st.context.headers.get("Host", "")
    hostname = host.split(":", 1)[0].strip("[]").casefold()
    return not hostname or hostname in {"localhost", "127.0.0.1", "::1"}


def get_database_url() -> str:
    try:
        return str(st.secrets["database"]["url"]).strip()
    except (FileNotFoundError, KeyError):
        return ""


def get_authenticator_settings() -> dict:
    """读取 Cookie 和可选注册邀请码配置。"""

    try:
        settings = st.secrets["authenticator"]
    except (FileNotFoundError, KeyError):
        return {}
    return {
        "cookie_name": str(settings.get("cookie_name", "")).strip(),
        "cookie_key": str(settings.get("cookie_key", "")).strip(),
        "cookie_expiry_days": float(
            settings.get("cookie_expiry_days", 7)
        ),
        "registration_code": str(
            settings.get("registration_code", "")
        ),
    }


def render_registration_form(
    store: UserWordBookStore,
    registration_code: str,
) -> None:
    """注册账号，密码只保存 bcrypt 哈希。"""

    with st.form("registration_form", clear_on_submit=True):
        username = st.text_input(
            "用户名",
            placeholder="3-20 位字母、数字、_ 或 -",
            max_chars=20,
        )
        password = st.text_input("密码", type="password")
        password_repeat = st.text_input("再次输入密码", type="password")
        entered_code = ""
        if registration_code:
            entered_code = st.text_input(
                "班级邀请码",
                type="password",
                help="向管理员获取邀请码。",
            )
        submitted = st.form_submit_button("注册", type="primary")

    if not submitted:
        st.caption(PASSWORD_RULE_MESSAGE)
        return

    normalized = normalize_username(username)
    if not validate_username(normalized):
        st.error(USERNAME_PATTERN_MESSAGE)
        return
    if password != password_repeat:
        st.error("两次输入的密码不一致。")
        return
    if not validate_password(password):
        st.error(PASSWORD_RULE_MESSAGE)
        return
    if not registration_code_matches(entered_code, registration_code):
        st.error("班级邀请码不正确。")
        return

    try:
        created = store.add_user(normalized, hash_password(password))
    except UserWordBookError as error:
        st.error(str(error))
        return

    if created:
        st.success("注册成功，请切换到“登录”页签。")
    else:
        st.error("该用户名已经被注册。")


def authenticate_user():
    """显示用户注册/登录页；成功时返回用户名和 authenticator。"""

    database_url = get_database_url()
    if not database_url:
        if is_local_request():
            return None, None
        st.error("云端尚未配置 Supabase 数据库。")
        st.stop()

    settings = get_authenticator_settings()
    if not settings.get("cookie_name") or not settings.get("cookie_key"):
        st.error("尚未配置登录 Cookie，请检查 .streamlit/secrets.toml。")
        st.stop()

    try:
        store = get_user_wordbook_store()
        users = store.list_users()
    except UserWordBookError as error:
        st.error(str(error))
        st.stop()

    authenticator = stauth.Authenticate(
        build_credentials(users),
        settings["cookie_name"],
        settings["cookie_key"],
        settings["cookie_expiry_days"],
        auto_hash=False,
    )

    st.title("📖 生词本")
    st.caption("请使用自己的用户名登录，生词会分别保存。")

    try:
        # 先检查 Cookie；已登录时不再绘制登录/注册页签。
        authenticator.login(location="unrendered")
    except stauth.LoginError as error:
        st.error(str(error))

    if st.session_state.get("authentication_status"):
        username = normalize_username(st.session_state["username"])
        return username, authenticator

    login_tab, register_tab = st.tabs(["登录", "注册新账号"])
    with login_tab:
        try:
            authenticator.login(
                location="main",
                fields={
                    "Form name": "登录",
                    "Username": "用户名",
                    "Password": "密码",
                    "Login": "登录",
                },
                key="wordbook_login",
                max_login_attempts=5,
                clear_on_submit=False,
            )
        except stauth.LoginError as error:
            st.error(str(error))

        if st.session_state.get("authentication_status"):
            st.rerun()
        if st.session_state.get("authentication_status") is False:
            st.error("用户名或密码错误。")
        else:
            st.info("请输入用户名和密码。")

    with register_tab:
        render_registration_form(
            store,
            settings.get("registration_code", ""),
        )

    st.stop()


@st.cache_resource
def get_user_wordbook_store() -> UserWordBookStore:
    """生产环境使用 Supabase；本地测试可回退到 SQLite。"""

    database_url = get_database_url()

    sqlite_path = Path(
        os.environ.get(
            "WORD_BOOK_USER_DB",
            BASE_DIR / "data" / "user_wordbooks.sqlite3",
        )
    ).expanduser().resolve()
    return UserWordBookStore(
        database_url=database_url or None,
        sqlite_path=sqlite_path,
    )


def load_words(username: str | None = None) -> list[str]:
    """读取当前用户的生词；本地模式仍使用 words.json。

    处理前后的例子：
        原数据：[" cat ", "Dog", "cat", 123]
        返回值：["cat", "Dog"]

    casefold() 是适合英文大小写比较的方法，所以 "Cat" 和 "cat"
    会被视为同一个单词。
    """

    if username is not None:
        return get_user_wordbook_store().list_words(username)
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


def add_to_wordbook(
    entry: DictionaryEntry,
    username: str | None = None,
) -> bool:
    """把查询结果加入生词本；已存在时返回 False。"""

    if username is not None:
        return get_user_wordbook_store().add_word(username, entry.word)

    words = load_words()
    if any(word.casefold() == entry.word.casefold() for word in words):
        return False

    words.append(entry.word)
    save_words(words)
    return True


def remove_word_from_wordbook(
    word: str,
    username: str | None = None,
) -> bool:
    """从生词本删除一个单词，并保留文件中已有的拼写形式。"""

    if username is not None:
        return get_user_wordbook_store().remove_word(username, word)

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


def remove_from_wordbook(
    entry: DictionaryEntry,
    username: str | None = None,
) -> bool:
    """删除对象写法，方便查询结果区域复用底层删词函数。"""

    return remove_word_from_wordbook(entry.word, username)


def find_saved_word(entry: DictionaryEntry, words: list[str]) -> str | None:
    """返回生词本中与该词对应的原始写法。

    例如查询 "CAT" 时，生词本里的 "Cat" 仍然可以匹配。
    """

    for word in words:
        if word.casefold() == entry.word.casefold():
            return word
    return None


def cet_badge_markdown(entry: DictionaryEntry | None) -> str:
    """生成可插入 Markdown 正文的 CET4/CET6 徽标。"""

    if entry is None or not entry.is_cet:
        return ""

    badge_colors = {"CET4": "green", "CET6": "violet"}
    return " ".join(
        f":{badge_colors[level]}-badge[{level}]"
        for level in entry.cet_levels
    )


def wordbook_label(word: str, entry: DictionaryEntry | None) -> str:
    """生成“单词 + CET 等级徽标”的折叠标题。"""

    label = f"**{word}**"
    badges = cet_badge_markdown(entry)
    if not badges:
        return label
    return f"{label} {badges}"


def render_meanings(entry: DictionaryEntry, key_prefix: str) -> None:
    """先显示普通/CET 重点释义，再把专业释义放入可选开关。"""

    sections = parse_meanings(entry.translation)
    cet_badges = cet_badge_markdown(entry)
    heading = "四六级重点词释义" if cet_badges else "常用释义"

    st.markdown(f"**{heading}** {cet_badges}")
    if cet_badges:
        st.caption("ECDICT 标签属于词条级；这里优先展示非专业领域释义。")

    if sections.general:
        for meaning in sections.general:
            st.markdown(f"- {meaning}")
    else:
        st.caption("该词没有单独的普通释义。")

    if sections.specialized:
        show_specialized = st.toggle(
            f"显示专业领域释义（{len(sections.specialized)} 条）",
            key=f"show_special_{key_prefix}_{entry.word.casefold()}",
        )
        if show_specialized:
            for meaning in sections.specialized:
                st.markdown(f"- **[{meaning.domain}]** {meaning.text}")


def render_wordbook_entry(word: str, username: str | None) -> None:
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

            render_meanings(entry, key_prefix="wordbook")

            if entry.definition:
                st.markdown("**英文释义**")
                st.text(entry.definition.replace("\\n", "\n"))

        if st.button(
            "删除这个单词",
            key=f"delete_word_{word.casefold()}",
            icon=":material/delete:",
            type="secondary",
        ):
            if remove_word_from_wordbook(word, username):
                st.toast(f"已删除“{word}”")
            st.rerun()


@st.fragment
def render_wordbook(username: str | None) -> None:
    """搜索并展示生词本；搜索只重跑这个独立区域。"""

    st.header("我的生词本")
    words = sorted(load_words(username), key=str.casefold)

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
        render_wordbook_entry(word, username)


def show_result(
    entry: DictionaryEntry,
    search_mode: str,
    username: str | None,
) -> None:
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

    render_meanings(entry, key_prefix="query")

    if entry.definition:
        with st.expander("查看英文释义"):
            st.write(entry.definition.replace("\\n", "\n"))

    saved_word = find_saved_word(entry, load_words(username))
    if saved_word:
        st.success(f"“{saved_word}”已经在生词本中。")
        if st.button("从生词本移除", type="secondary"):
            if remove_from_wordbook(entry, username):
                st.rerun()
    else:
        if st.button("加入生词本", type="primary"):
            if add_to_wordbook(entry, username):
                st.success(f"已将“{entry.word}”加入生词本。")
            else:
                st.info("这个单词已经在生词本中。")


def main() -> None:
    """页面入口：安排输入框、按钮和结果区域。"""

    st.set_page_config(page_title="离线生词本", page_icon="📖", layout="centered")
    username, authenticator = authenticate_user()

    st.title("📖 离线生词本")
    st.caption("输入一个英文单词，从本地 ECDICT 词典中查询释义。")

    with st.sidebar:
        if username is None:
            st.warning("当前是本机模式，登录配置完成后将启用独立生词本。")
        else:
            st.caption(f"已登录：{username}")
            authenticator.logout(
                "退出登录",
                location="sidebar",
            )

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
            try:
                show_result(entry, last_mode, username)
            except UserWordBookError as error:
                st.error(str(error))

    st.divider()
    render_wordbook(username)


# 直接执行 app.py 时进入 main；被其他文件导入时不会自动运行页面。
if __name__ == "__main__":
    main()
