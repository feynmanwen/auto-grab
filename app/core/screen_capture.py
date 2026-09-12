"""
Screen capture utility module supporting High-DPI, multi-monitor, and DWM composition.
"""
import ctypes
from typing import Tuple, Optional
from PIL import Image, ImageGrab

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QGuiApplication, QImage
except ImportError:
    QApplication = None
    QGuiApplication = None
    QImage = None


def get_screen_scale_factor() -> float:
    """
    獲取系統主螢幕的 DPI 縮放比例 (例如 1.0, 1.25, 1.5, 2.0)。
    """
    if QGuiApplication is not None:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        screen = QGuiApplication.primaryScreen()
        if screen:
            return float(screen.devicePixelRatio())
    return 1.0


def capture_roi(
    roi_x: int,
    roi_y: int,
    roi_w: int,
    roi_h: int,
    dpr: float = 1.0
) -> Tuple[Optional[Image.Image], Tuple[int, int, int, int]]:
    """
    根據邏輯座標與 DPI 縮放比精確擷取螢幕 ROI 區域。
    
    :param roi_x: 邏輯 X 座標
    :param roi_y: 邏輯 Y 座標
    :param roi_w: 邏輯寬度
    :param roi_h: 邏輯高度
    :param dpr: 螢幕設備像素比 (Device Pixel Ratio)
    :return: (PIL Image 物件, 物理座標 (phys_x, phys_y, phys_w, phys_h))
    """
    if roi_w <= 0 or roi_h <= 0:
        return None, (0, 0, 0, 0)

    phys_x = int(round(roi_x * dpr))
    phys_y = int(round(roi_y * dpr))
    phys_w = int(round(roi_w * dpr))
    phys_h = int(round(roi_h * dpr))

    # 1. 優先使用 Qt 原生 QScreen.grabWindow (高 DPI 零失真、避開 BitBlt 權限阻擋)
    if QGuiApplication is not None:
        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0, roi_x, roi_y, roi_w, roi_h)
                if not pixmap.isNull():
                    qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
                    width = qimg.width()
                    height = qimg.height()
                    ptr = qimg.bits()
                    img = Image.frombuffer("RGB", (width, height), ptr, "raw", "RGB", 0, 1)
                    return img, (phys_x, phys_y, width, height)
        except Exception:
            pass

    # 2. 次選方案：使用 PIL.ImageGrab
    bbox = (phys_x, phys_y, phys_x + phys_w, phys_y + phys_h)
    try:
        img = ImageGrab.grab(bbox=bbox)
        if img:
            return img, (phys_x, phys_y, phys_w, phys_h)
    except Exception:
        try:
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
            if img:
                return img, (phys_x, phys_y, phys_w, phys_h)
        except Exception:
            pass

    # 3. 備援方案：使用 mss 擷取
    try:
        import mss
        with mss.mss() as sct:
            monitor = {"top": phys_y, "left": phys_x, "width": phys_w, "height": phys_h}
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img, (phys_x, phys_y, phys_w, phys_h)
    except Exception:
        pass

    return None, (phys_x, phys_y, phys_w, phys_h)
