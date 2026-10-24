import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QLabel,
    QMenu,
)
from PyQt6.QtCore import Qt

DATA_FILE = "words.json"


class WordBookWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.words = self.load_words()
        self.init_ui()
        self.refresh_list()

    def init_ui(self):
        # 注意：这里把无边框和透明背景的代码删了，现在是正常的系统窗口
        self.setWindowTitle("生词本")  # 窗口标题
        self.resize(320, 420)

        # 主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)

        # 标题标签
        title_label = QLabel("📖 我的生词本")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # 输入区
        input_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入生词，按回车添加...")
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

        # 生词列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                font-size: 14px;
            }
            QListWidget::item { padding: 4px; }
        """)

        # 开启右键菜单删除功能
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.list_widget)
        self.setLayout(layout)

        def add_word(self):
            word = self.input_field.text().strip()
            if not word or word in self.words:
                self.input_field.clear()
                return
            self.words.append(word)
            self.words = sorted(self.words, key=str.lower)
            self.save_words()
            self.refresh_list()
            self.input_field.clear()

        # 右键删除功能
        def show_context_menu(self, pos):
            item = self.list_widget.itemAt(pos)
            if item:
                menu = QMenu()
                delete_action = menu.addAction("🗑️ 删除该单词")
                action = menu.exec(self.list_widget.mapToGlobal(pos))
                if action == delete_action:
                    word = item.text()
                    self.words.remove(word)
                    self.save_words()
                    self.refresh_list()

        # 按 ESC 键直接关闭窗口
        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_Escape:
                self.close()

        def load_words(self):
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    return []
            return []

        def save_words(self):
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.words, f, ensure_ascii=False, indent=2)

        def refresh_list(self):
            self.list_widget.clear()
            for w in self.words:
                self.list_widget.addItem(w)

            # 👇👇👇 在这里加入搜索框 👇👇👇
            self.search_field = QLineEdit()
            self.search_field.setPlaceholderText("🔍 搜索单词...")
            self.search_field.setStyleSheet(
                "padding: 6px; border: 1px solid #bbb; border-radius: 4px;"
            )
            # 关键：只要搜索框里的字变了，就去刷新列表
            self.search_field.textChanged.connect(self.refresh_list)
            layout.addWidget(self.search_field)
            # 👆👆👆 ------------------ 👆👆👆
            layout.addWidget(self.list_widget)  # 原有的代码

            # 👇👇👇 在这里加入删除按钮区 👇👇👇
            bottom_row = QHBoxLayout()
            delete_btn = QPushButton("🗑️ 删除选中")
            delete_btn.clicked.connect(self.delete_selected_word)  # 点击触发删除方法
            delete_btn.setStyleSheet("""
            QPushButton { background: #ff6b6b; color: white; border-radius: 4px; padding: 6px 14px; }
            QPushButton:hover { background: #e65c5c; }
            """)
            bottom_row.addStretch()  # 让按钮靠右边
            bottom_row.addWidget(delete_btn)
            layout.addLayout(bottom_row)
            # 👆👆👆 ------------------ 👆👆👆


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = WordBookWidget()
    widget.show()
    sys.exit(app.exec())
