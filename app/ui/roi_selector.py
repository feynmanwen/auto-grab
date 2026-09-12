"""
Full screen semi-transparent ROI selector overlay implemented as QDialog.
Using QDialog ensures compatibility with modal parent dialogs (nested exec)
without blocking mouse events.
"""
from typing import Tuple
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication
from PySide6.QtWidgets import QDialog


class ROISelectorOverlay(QDialog):
    roi_selected = Signal(int, int, int, int)  # (x, y, w, h)
    canceled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 設定為無邊框、置頂視窗
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(1.0)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.start_pos: QPoint = QPoint()
        self.current_pos: QPoint = QPoint()
        self.is_drawing: bool = False
        self.selected_roi: Tuple[int, int, int, int] = (0, 0, 0, 0)

        # 涵蓋所有螢幕的整體虛擬桌面
        self._setup_geometry()

    def _setup_geometry(self):
        total_rect = QRect()
        for screen in QGuiApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        self.setGeometry(total_rect)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.pos()
            self.current_pos = event.pos()
            self.is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            rect = QRect(self.start_pos, self.current_pos).normalized()
            # 轉換為全螢幕絕對座標
            global_top_left = self.mapToGlobal(rect.topLeft())
            x = global_top_left.x()
            y = global_top_left.y()
            w = rect.width()
            h = rect.height()

            if w >= 5 and h >= 5:
                self.selected_roi = (x, y, w, h)
                self.roi_selected.emit(x, y, w, h)
                self.accept()
            else:
                self.canceled.emit()
                self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.canceled.emit()
            self.reject()
        else:
            super().keyPressEvent(event)

    def get_roi(self) -> Tuple[int, int, int, int]:
        return self.selected_roi

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. 繪製全螢幕半透明深色遮罩
        mask_color = QColor(0, 0, 0, 110)
        painter.fillRect(self.rect(), mask_color)

        # 2. 若正在拖曳框選，將選取區域挖空並畫上高亮邊框
        if self.is_drawing or not self.start_pos.isNull():
            selected_rect = QRect(self.start_pos, self.current_pos).normalized()

            # 將選取區挖空變清晰
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selected_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            # 繪製青綠色高亮外框
            border_pen = QPen(QColor(0, 220, 255), 2, Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.drawRect(selected_rect)

            # 顯示尺寸提示文字 (W x H)
            dim_text = f"{selected_rect.width()} x {selected_rect.height()}"
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(selected_rect.left() + 6, selected_rect.bottom() + 18, dim_text)

        # 3. 頂部提示操作指示
        tip_text = "【按住滑鼠左鍵並拖曳】框選區域 | 【ESC 鍵】取消框選"
        painter.setFont(QFont("Microsoft JhengHei", 12, QFont.Weight.Bold))
        # 繪製陰影底條
        painter.fillRect(0, 0, self.width(), 45, QColor(0, 0, 0, 180))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(0, 0, self.width(), 45, Qt.AlignmentFlag.AlignCenter, tip_text)
