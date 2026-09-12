"""
Screen OCR AutoClicker Entry Point
"""
import sys
import os

# 確保當前目錄在 Python sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.screen_capture import ensure_desktop_access

# 在建立任何 GUI 視窗前，連結至 Windows 互動式桌面
ensure_desktop_access()

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow


def main():
    # 支援 Windows 高解析度螢幕 (High-DPI) 精確縮放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 設置應用程式通用字型
    font = app.font()
    font.setFamily("Microsoft JhengHei, Segoe UI, sans-serif")
    font.setPointSize(9)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
