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


def ensure_desktop_access():
    """
    確保目前執行緒連結至 Windows 使用中的互動式桌面 (Input Desktop)，
    使 GDI / BitBlt 具備擷取真實螢幕的存取權限。
    """
    try:
        user32 = ctypes.windll.user32
        hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception:
        pass


# 模組載入時嘗試連結目前執行緒至互動桌面
ensure_desktop_access()


def get_screen_scale_factor() -> float:
    """
    獲取系統主螢幕的 DPI 縮放比例 (例如 1.0, 1.25, 1.5, 2.0)。
    """
    if QGuiApplication is not None:
        app = QApplication.instance()
        if app is None:
            ensure_desktop_access()
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

    # 確保當前執行緒具有桌面存取權限
    ensure_desktop_access()

    bbox = (phys_x, phys_y, phys_x + phys_w, phys_y + phys_h)

    # 1. 優先方案：使用 PIL.ImageGrab
    try:
        img = ImageGrab.grab(bbox=bbox)
        if img:
            return img, (phys_x, phys_y, phys_w, phys_h)
    except Exception:
        pass

    # 2. 次選方案：跨多螢幕 PIL.ImageGrab
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
