"""
ui/settings_panel.py — API 配置面板

单套 api_key + base_url，自动检测 provider（OpenAI/Anthropic），
检测成功后填充两个模型下拉框（Stage1 过滤模型 / Stage2 提取模型）。
"""
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from config import load_config, save_config


class SettingsPanel(QWidget):
    settings_saved = pyqtSignal()
    _detect_done = pyqtSignal(object, str)  # (models_list | None, status_text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._detect_done.connect(self._on_detect_done)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题
        title = QLabel("API 配置")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)

        # API Key
        key_row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("sk-... 或 sk-ant-...")
        self.toggle_btn = QPushButton("显示")
        self.toggle_btn.setFixedWidth(48)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.toggled.connect(self._toggle_key)
        key_row.addWidget(self.key_input)
        key_row.addWidget(self.toggle_btn)
        form.addRow("API Key:", key_row)

        # Base URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://api.anthropic.com  或  https://api.openai.com/v1  或任意兼容地址"
        )
        form.addRow("Base URL:", self.url_input)

        layout.addLayout(form)

        # 检测按钮 + 状态
        detect_row = QHBoxLayout()
        self.detect_btn = QPushButton("检测可用模型")
        self.detect_btn.clicked.connect(self._do_detect)
        self.provider_label = QLabel("")
        self.provider_label.setStyleSheet("color: #888;")
        detect_row.addWidget(self.detect_btn)
        detect_row.addWidget(self.provider_label)
        detect_row.addStretch()
        layout.addLayout(detect_row)

        layout.addSpacing(8)

        # 模型选择
        model_title = QLabel("模型选择")
        model_title.setFont(QFont("", 13, QFont.Weight.Bold))
        layout.addWidget(model_title)

        hint = QLabel(
            "Stage1（过滤）可选便宜快速的模型；Stage2（提取）建议选最准确的模型。\n"
            "两个可以相同，也可以不同。请先点击「检测可用模型」填充列表。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        layout.addWidget(hint)

        model_form = QFormLayout()
        model_form.setSpacing(8)

        self.model1_combo = QComboBox()
        self.model1_combo.setEditable(True)
        self.model1_combo.setMinimumWidth(300)
        model_form.addRow("Stage1 过滤模型:", self.model1_combo)

        self.model2_combo = QComboBox()
        self.model2_combo.setEditable(True)
        self.model2_combo.setMinimumWidth(300)
        model_form.addRow("Stage2 提取模型:", self.model2_combo)

        layout.addLayout(model_form)

        layout.addStretch()

        # 保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def _toggle_key(self, checked: bool):
        self.key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.toggle_btn.setText("隐藏" if checked else "显示")

    def _load(self):
        cfg = load_config()
        self.key_input.setText(cfg.get("api_key", ""))
        self.url_input.setText(cfg.get("base_url", ""))
        m1 = cfg.get("model_stage1", "")
        m2 = cfg.get("model_stage2", "")
        if m1:
            self.model1_combo.addItem(m1)
            self.model1_combo.setCurrentText(m1)
        if m2 and m2 != m1:
            self.model2_combo.addItem(m2)
        if m2:
            self.model2_combo.setCurrentText(m2)
        provider = cfg.get("detected_provider", "")
        if provider:
            self.provider_label.setText(f"✅ {provider}-compatible")

    def _do_detect(self):
        api_key = self.key_input.text().strip()
        base_url = self.url_input.text().strip()
        if not api_key or not base_url:
            self.provider_label.setText("❌ 请先填写 API Key 和 Base URL")
            return

        self.detect_btn.setEnabled(False)
        self.provider_label.setText("检测中...")

        from core.llm_client import clear_provider_cache
        clear_provider_cache()

        def run():
            try:
                from core.llm_client import auto_detect_provider, fetch_models
                provider = auto_detect_provider(api_key, base_url)
                models = fetch_models(api_key, base_url)
                self._detect_done.emit(models, f"✅ {provider}-compatible，共 {len(models)} 个模型")
            except Exception as e:
                self._detect_done.emit(None, f"❌ {str(e)[:80]}")

        threading.Thread(target=run, daemon=True).start()

    @pyqtSlot(object, str)
    def _on_detect_done(self, models, status_text):
        self.detect_btn.setEnabled(True)
        self.provider_label.setText(status_text)
        if models is not None:
            cur1 = self.model1_combo.currentText()
            cur2 = self.model2_combo.currentText()
            self.model1_combo.clear()
            self.model2_combo.clear()
            if models:
                for m in models:
                    self.model1_combo.addItem(m)
                    self.model2_combo.addItem(m)
                if cur1 in models:
                    self.model1_combo.setCurrentText(cur1)
                if cur2 in models:
                    self.model2_combo.setCurrentText(cur2)
            else:
                # /models 不支持，保留用户已输入的文字，提示手动输入
                self.model1_combo.setCurrentText(cur1)
                self.model2_combo.setCurrentText(cur2)
                self.provider_label.setText(
                    status_text + "  ⚠️ /models 接口不可用，请手动输入模型名称"
                )

    def _save(self):
        cfg = load_config()
        cfg["api_key"] = self.key_input.text().strip()
        cfg["base_url"] = self.url_input.text().strip()
        cfg["model_stage1"] = self.model1_combo.currentText().strip()
        cfg["model_stage2"] = self.model2_combo.currentText().strip()
        # 缓存 provider 标签（仅供显示，不影响运行时检测）
        txt = self.provider_label.text()
        if "openai" in txt:
            cfg["detected_provider"] = "openai"
        elif "anthropic" in txt:
            cfg["detected_provider"] = "anthropic"
        save_config(cfg)
        import os
        if cfg["api_key"]:
            os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]
        self.provider_label.setText(self.provider_label.text() + "  ✅ 已保存")
        self.settings_saved.emit()

    def get_config(self) -> dict:
        """返回当前界面上填写的配置（未保存的也包括）。"""
        return {
            "api_key": self.key_input.text().strip(),
            "base_url": self.url_input.text().strip(),
            "model_stage1": self.model1_combo.currentText().strip(),
            "model_stage2": self.model2_combo.currentText().strip(),
        }
