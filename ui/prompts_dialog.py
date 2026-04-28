"""
ui/prompts_dialog.py — 查看/编辑两个 Prompt 的弹窗
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QTextEdit, QPushButton, QLabel, QSizePolicy,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from config import load_config, save_config, get_default_prompt1, get_default_prompt2


class PromptsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑 Prompt")
        self.resize(800, 600)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "Prompt1：Stage1 过滤用（判断哪些截图是B站视频页/评论页）\n"
            "Prompt2：Stage2 提取用（从截图中提取14个字段）"
        )
        hint.setStyleSheet("color: #888;")
        layout.addWidget(hint)

        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        # Prompt 1
        p1_widget = QWidget()
        p1_layout = QVBoxLayout(p1_widget)
        self.prompt1_edit = QTextEdit()
        self.prompt1_edit.setFont(QFont("Menlo", 12))
        p1_layout.addWidget(self.prompt1_edit)
        reset1_btn = QPushButton("恢复默认")
        reset1_btn.setFixedWidth(90)
        reset1_btn.clicked.connect(lambda: self.prompt1_edit.setPlainText(get_default_prompt1()))
        p1_layout.addWidget(reset1_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(p1_widget, "Prompt 1（过滤）")

        # Prompt 2
        p2_widget = QWidget()
        p2_layout = QVBoxLayout(p2_widget)
        self.prompt2_edit = QTextEdit()
        self.prompt2_edit.setFont(QFont("Menlo", 12))
        p2_layout.addWidget(self.prompt2_edit)
        reset2_btn = QPushButton("恢复默认")
        reset2_btn.setFixedWidth(90)
        reset2_btn.clicked.connect(lambda: self.prompt2_edit.setPlainText(get_default_prompt2()))
        p2_layout.addWidget(reset2_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(p2_widget, "Prompt 2（提取）")

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _load(self):
        cfg = load_config()
        self.prompt1_edit.setPlainText(cfg.get("prompt1", get_default_prompt1()))
        self.prompt2_edit.setPlainText(cfg.get("prompt2", get_default_prompt2()))

    def _save_and_close(self):
        cfg = load_config()
        cfg["prompt1"] = self.prompt1_edit.toPlainText().strip()
        cfg["prompt2"] = self.prompt2_edit.toPlainText().strip()
        save_config(cfg)
        self.accept()

    def get_prompts(self) -> tuple[str, str]:
        return (
            self.prompt1_edit.toPlainText().strip(),
            self.prompt2_edit.toPlainText().strip(),
        )
