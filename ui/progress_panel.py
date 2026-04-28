"""
ui/progress_panel.py — 阶段标签 + 进度条 + 日志
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QTextEdit,
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt


class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        # 阶段标签 + 进度条
        bar_row = QHBoxLayout()
        self.stage_label = QLabel("就绪")
        self.stage_label.setFont(QFont("", 12, QFont.Weight.Bold))
        self.stage_label.setMinimumWidth(180)
        bar_row.addWidget(self.stage_label)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        bar_row.addWidget(self.progress, stretch=1)

        self.count_label = QLabel("")
        self.count_label.setMinimumWidth(80)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bar_row.addWidget(self.count_label)

        layout.addLayout(bar_row)

        # 日志区
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setFont(QFont("Menlo", 11))
        self.log_edit.setStyleSheet("background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.log_edit, stretch=1)

    def set_stage(self, text: str):
        self.stage_label.setText(text)

    def set_range(self, total: int):
        self.progress.setMaximum(total)
        self.progress.setValue(0)
        self.count_label.setText(f"0/{total}")

    def set_value(self, val: int):
        total = self.progress.maximum()
        self.progress.setValue(val)
        self.count_label.setText(f"{val}/{total}")

    def reset(self):
        self.progress.setValue(0)
        self.progress.setMaximum(1)
        self.count_label.setText("")
        self.stage_label.setText("就绪")
        self.log_edit.clear()

    def log(self, text: str, color: str = "#d4d4d4"):
        html = f'<span style="color:{color};">{text}</span>'
        self.log_edit.append(html)
        # 自动滚动到底部
        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def log_info(self, text: str):
        self.log(text, "#d4d4d4")

    def log_ok(self, text: str):
        self.log(text, "#4ec9b0")

    def log_warn(self, text: str):
        self.log(text, "#dcdcaa")

    def log_error(self, text: str):
        self.log(text, "#f44747")
