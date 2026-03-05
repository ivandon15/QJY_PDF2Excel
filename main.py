import sys
import os
from dotenv import load_dotenv
load_dotenv()

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("警告: 未设置 ANTHROPIC_API_KEY 环境变量，提取功能将不可用")
    app = QApplication(sys.argv)
    app.setApplicationName("PDF2Excel")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
