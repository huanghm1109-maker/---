import json
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from offline_dictionary import (
    DictionaryUnavailableError,
    InvalidWordError,
    OfflineDictionary,
)

DATA_FILE = Path(__file__).resolve().with_name("words.json")


class WordBookWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.load_error = None
        self.words = self.load_words()
        self.translation_word = ""
        self.dictionary = OfflineDictionary()

        self.init_ui()
        self.refresh_list()

        if self.load_error:
            QTimer.singleShot(0, self.show_load_error)

    def init_ui(self):
        self.setWindowTitle("生词本")
        self.resize(420, 560)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)

        title_label = QLabel("📖 我的生词本")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("搜索"))
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("输入单词或字母，实时筛选...")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self.refresh_list)
        search_row.addWidget(self.search_field)
        layout.addLayout(search_row)

        input_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入英文单词，按回车添加...")
        self.input_field.setMaxLength(100)
        self.input_field.returnPressed.connect(self.add_word)

        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_word)
        add_btn.setStyleSheet("""
            QPushButton { background: #4a9eff; color: white; border-radius: 4px; padding: 6px 14px; }
            QPushButton:hover { background: #3a8eef; }
        """)

        input_row.addWidget(self.input_field)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                font-size: 14px;
            }
            QListWidget::item { padding: 6px; }
        """)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.itemDoubleClicked.connect(
            lambda item: self.translate_word(item.data(Qt.ItemDataRole.UserRole))
        )
        self.list_widget.currentItemChanged.connect(self.update_selection_hint)
        layout.addWidget(self.list_widget, 1)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.count_label)

        action_row = QHBoxLayout()
        action_row.addStretch()

        self.translate_btn = QPushButton("查词典")
        self.translate_btn.clicked.connect(self.translate_selected)

        delete_btn = QPushButton("删除选中")
        delete_btn.setStyleSheet("""
            QPushButton { color: #b42318; }
            QPushButton:hover { color: #7a1b12; }
        """)
        delete_btn.clicked.connect(self.delete_selected)

        action_row.addWidget(self.translate_btn)
        action_row.addWidget(delete_btn)
        layout.addLayout(action_row)

        self.translation_label = QLabel(
            "选中生词后点击“查词典”，从本地 ECDICT 离线词典读取释义。"
        )
        self.translation_label.setWordWrap(True)
        self.translation_label.setMinimumHeight(64)
        self.translation_label.setTextFormat(Qt.TextFormat.PlainText)
        self.translation_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.translation_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.translation_label.setStyleSheet(
            "background: #f5f7fa; border: 1px solid #dde3ea; "
            "border-radius: 4px; padding: 8px; color: #333;"
        )
        layout.addWidget(self.translation_label)

        delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.list_widget)
        delete_shortcut.activated.connect(self.delete_selected)

        self.setLayout(layout)

    def current_word(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def add_word(self):
        word = self.input_field.text()
        try:
            self.dictionary.validate_word(word)
        except InvalidWordError as error:
            self.show_input_error(str(error))
            return
        except DictionaryUnavailableError as error:
            self.show_dictionary_error(str(error))
            return

        if any(existing.casefold() == word.casefold() for existing in self.words):
            self.translation_label.setText(f"“{word}”已经在生词本中了。")
            self.input_field.selectAll()
            return

        self.words.append(word)
        self.words.sort(key=str.casefold)
        if not self.save_words():
            self.words.remove(word)
            return

        self.input_field.clear()
        self.search_field.clear()
        self.refresh_list(selected_word=word)

    def show_input_error(self, message):
        self.translation_label.setText(message)
        self.input_field.setFocus()
        self.input_field.selectAll()
        QMessageBox.warning(self, "输入错误", message)

    def refresh_list(self, *_args, selected_word=None):
        keep_word = selected_word if selected_word is not None else self.current_word()
        search_text = self.search_field.text().strip().casefold()
        displayed_words = [
            word for word in self.words if search_text in word.casefold()
        ]

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        selected_item = None
        for word in displayed_words:
            self.list_widget.addItem(word)
            item = self.list_widget.item(self.list_widget.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, word)
            if word == keep_word:
                selected_item = item

        if selected_item:
            self.list_widget.setCurrentItem(selected_item)
        self.list_widget.blockSignals(False)

        if search_text:
            self.count_label.setText(
                f"找到 {len(displayed_words)} 个，共 {len(self.words)} 个生词"
            )
        else:
            self.count_label.setText(f"共 {len(self.words)} 个生词")

    def update_selection_hint(self, current, _previous):
        if not current:
            return
        word = current.data(Qt.ItemDataRole.UserRole)
        if word != self.translation_word:
            self.translation_label.setText(f"已选择“{word}”，点击“查词典”查看释义。")

    def translate_selected(self):
        word = self.current_word()
        if not word:
            self.translation_label.setText("请先在列表中选择一个生词。")
            return
        self.translate_word(word)

    def translate_word(self, word):
        if not word:
            return

        self.translation_word = word
        try:
            entry = self.dictionary.lookup(word)
        except DictionaryUnavailableError as error:
            self.show_dictionary_error(str(error))
            return
        if entry is None:
            self.show_dictionary_error(f"离线词典中找不到“{word}”，请检查拼写。")
            return

        translation = entry.translation or entry.definition or "词典中没有释义。"
        translation = translation.replace("\\n", "\n")
        phonetic = f"/{entry.phonetic}/" if entry.phonetic else ""
        lines = [f"“{entry.word}”"]
        if phonetic:
            lines.append(phonetic)
        lines.append(translation)
        self.show_translation(word, "\n".join(lines))

    def show_translation(self, word, translation):
        if word != self.translation_word:
            return
        self.translation_label.setText(translation)

    def show_dictionary_error(self, message):
        self.translation_label.setText(message)

    def delete_selected(self):
        word = self.current_word()
        if not word:
            self.translation_label.setText("请先在列表中选择要删除的生词。")
            return
        self.delete_word(word)

    def delete_word(self, word, ask_for_confirmation=True):
        if ask_for_confirmation:
            answer = QMessageBox.question(
                self,
                "删除生词",
                f"确定要删除“{word}”吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if word not in self.words:
            return
        self.words.remove(word)
        if not self.save_words():
            self.words.append(word)
            self.words.sort(key=str.casefold)
            return

        if word == self.translation_word:
            self.translation_word = ""
            self.translation_label.setText(f"已删除“{word}”。")
        self.refresh_list()

    def show_context_menu(self, position):
        item = self.list_widget.itemAt(position)
        if not item:
            return

        self.list_widget.setCurrentItem(item)
        word = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu()
        translate_action = menu.addAction("📚 查询词典")
        delete_action = menu.addAction("🗑️ 删除该单词")
        action = menu.exec(self.list_widget.mapToGlobal(position))

        if action == translate_action:
            self.translate_word(word)
        elif action == delete_action:
            self.delete_word(word)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.dictionary.close()
        super().closeEvent(event)

    def load_words(self):
        if not DATA_FILE.exists():
            return []

        try:
            with DATA_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, list):
                raise ValueError("生词文件内容必须是列表")
        except (OSError, ValueError) as error:
            self.load_error = f"无法读取 {DATA_FILE}：{error}"
            return []

        words = []
        seen = set()
        for value in data:
            if not isinstance(value, str):
                continue
            word = value.strip()
            key = word.casefold()
            if word and key not in seen:
                words.append(word)
                seen.add(key)
        return words

    def save_words(self):
        temporary_file = DATA_FILE.with_name(f"{DATA_FILE.name}.tmp")
        try:
            with temporary_file.open("w", encoding="utf-8") as file:
                json.dump(self.words, file, ensure_ascii=False, indent=2)
                file.write("\n")
            temporary_file.replace(DATA_FILE)
            return True
        except OSError as error:
            QMessageBox.critical(self, "保存失败", f"无法保存生词：{error}")
            return False

    def show_load_error(self):
        QMessageBox.warning(
            self,
            "读取失败",
            f"{self.load_error}\n\n原文件没有被修改。",
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = WordBookWidget()
    widget.show()
    sys.exit(app.exec())
