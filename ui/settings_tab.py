import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from config import load_config, save_config


class SettingsTab(QWidget):
    settings_saved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- API 设置 ---
        api_label = QLabel("API 设置")
        api_label.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(api_label)

        form = QFormLayout()
        form.setSpacing(8)

        # API Key
        key_row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("sk-ant-...")
        self.toggle_btn = QPushButton("显示")
        self.toggle_btn.setFixedWidth(48)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self.key_input)
        key_row.addWidget(self.toggle_btn)
        form.addRow("API Key:", key_row)

        # Base URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://api.anthropic.com（留空使用默认）")
        form.addRow("Base URL:", self.url_input)

        layout.addLayout(form)

        # Test button + status
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setFixedWidth(90)
        self.test_btn.clicked.connect(self._test_connection)
        self.test_status = QLabel("")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status)
        test_row.addStretch()
        layout.addLayout(test_row)

        layout.addSpacing(8)

        # --- Prompt ---
        prompt_label = QLabel("提取 Prompt")
        prompt_label.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(prompt_label)

        hint = QLabel("告诉模型你想提取哪些信息、从哪类页面提取。返回 JSON 中需包含 \"match\": true/false 作为是否纳入结果的标志。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setFont(QFont("Menlo", 12))
        self.prompt_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.prompt_edit)

        # Save button
        save_btn = QPushButton("保存设置")
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def _toggle_key_visibility(self, checked):
        self.key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.toggle_btn.setText("隐藏" if checked else "显示")

    def _load(self):
        cfg = load_config()
        self.key_input.setText(cfg.get("api_key", ""))
        self.url_input.setText(cfg.get("base_url", ""))
        self.prompt_edit.setPlainText(cfg.get("prompt", ""))

    def _save(self):
        import os
        cfg = {
            "api_key": self.key_input.text().strip(),
            "base_url": self.url_input.text().strip(),
            "prompt": self.prompt_edit.toPlainText().strip(),
        }
        save_config(cfg)
        # Apply to environment immediately
        if cfg["api_key"]:
            os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]
        if cfg["base_url"]:
            os.environ["ANTHROPIC_BASE_URL"] = cfg["base_url"]
        elif "ANTHROPIC_BASE_URL" in os.environ:
            del os.environ["ANTHROPIC_BASE_URL"]
        self.test_status.setText("✅ 已保存")
        self.settings_saved.emit()

    def _test_connection(self):
        self.test_btn.setEnabled(False)
        self.test_status.setText("测试中...")

        api_key = self.key_input.text().strip()
        base_url = self.url_input.text().strip()

        def run():
            try:
                from anthropic import Anthropic
                kwargs = {"api_key": api_key} if api_key else {}
                if base_url:
                    kwargs["base_url"] = base_url
                client = Anthropic(**kwargs)
                client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=8,
                    messages=[{"role": "user", "content": "hi"}]
                )
                result = "✅ 连接成功"
            except Exception as e:
                result = f"❌ 失败: {str(e)[:60]}"
            from PyQt6.QtCore import QMetaObject, Qt
            from PyQt6.QtCore import Q_ARG
            self._test_result = result
            QMetaObject.invokeMethod(self, "_on_test_done", Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=run, daemon=True).start()

    def _on_test_done(self):
        self.test_status.setText(getattr(self, "_test_result", ""))
        self.test_btn.setEnabled(True)

    def get_prompt(self) -> str:
        return self.prompt_edit.toPlainText().strip()
