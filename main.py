#!/usr/bin/env python3
"""
main.py — pdf2excel_v2 入口
"""
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from config import load_config


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PDF2Excel v2")
    app.setOrganizationName("pdf2excel")

    # 加载配置，设置环境变量
    cfg = load_config()
    if cfg.get("api_key"):
        os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]
    if cfg.get("base_url"):
        os.environ["ANTHROPIC_BASE_URL"] = cfg["base_url"]

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
