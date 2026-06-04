"""AI CFD Assistant — 近地翼片 2D-CFD 仿真 入口."""

import sys
import os

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from src.main_window import MainWindow
from src.theme import QSS


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("近地翼片 2D-CFD 仿真")
    app.setOrganizationName("CFD-Lab")
    app.setStyleSheet("")

    # Check API key
    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        # Try to read from local .env file
        config_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DEEPSEEK_API_KEY=") or line.startswith("OPENAI_API_KEY="):
                        os.environ["DEEPSEEK_API_KEY"] = line.split("=", 1)[1].strip('"').strip("'")
                        break

    window = MainWindow()
    window.show()

    # Show API key warning if not set
    if not os.environ.get("DEEPSEEK_API_KEY"):
        QMessageBox.warning(
            window, "API Key 未配置",
            "未检测到 DEEPSEEK_API_KEY 环境变量。\n\n"
            "请在项目目录下创建 .env 文件并添加:\n"
            "DEEPSEEK_API_KEY=your_key_here\n\n"
            "或设置系统环境变量 DEEPSEEK_API_KEY\n\n"
            "AI 对话功能需要 API Key 才能使用。\n"
            "可视化面板不受影响。"
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
