"""
Unit and Integration Tests for Screen OCR AutoClicker
"""
import os
import sys
import unittest
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 將專案根目錄加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import AppConfig
from app.core.ocr_engine import OCREngine
from app.core.screen_capture import get_screen_scale_factor, capture_roi, ensure_desktop_access
from app.core.mouse_controller import MouseController

ensure_desktop_access()


class TestScreenOCRAutoClicker(unittest.TestCase):
    def test_config_save_load(self):
        """測試設定檔儲存與載入"""
        test_cfg_path = os.path.join(os.path.dirname(__file__), "test_config.json")
        cfg = AppConfig(
            roi_x=120,
            roi_y=240,
            roi_w=500,
            roi_h=300,
            keywords=["提交", "確定"],
            match_mode="contains",
            confidence_threshold=0.75,
            mouse_action="double_click",
            loop_mode=True,
            cooldown_seconds=4.5
        )
        cfg.save(test_cfg_path)
        self.assertTrue(os.path.exists(test_cfg_path))

        loaded = AppConfig.load(test_cfg_path)
        self.assertEqual(loaded.roi_x, 120)
        self.assertEqual(loaded.roi_y, 240)
        self.assertEqual(loaded.keywords, ["提交", "確定"])
        self.assertEqual(loaded.mouse_action, "double_click")
        self.assertEqual(loaded.cooldown_seconds, 4.5)

        if os.path.exists(test_cfg_path):
            os.remove(test_cfg_path)

    def test_ocr_engine_detection(self):
        """測試 RapidOCR 在合成圖片上的文字辨識與座標計算"""
        img = Image.new("RGB", (600, 300), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # 嘗試載入微軟正黑體或 Arial
        font = None
        for font_path in ["C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/arial.ttf"]:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, 36)
                    break
                except Exception:
                    pass

        # 在 (200, 120) 位置繪製「確定付款」
        draw.text((200, 120), "確定付款", font=font, fill=(0, 0, 0))

        engine = OCREngine()
        result = engine.find_target_keyword(
            image=img,
            keywords=["確定"],
            match_mode="contains",
            confidence_threshold=0.5,
            roi_phys_origin=(100, 100),
            offset=(0, 0)
        )

        self.assertIsNotNone(result, "OCR 應成功辨識出目標文字")
        self.assertIn("確定", result.matched_text)
        # 本地中心點應在繪製文字的大致範圍內 (X: 200~350, Y: 120~180)
        cx, cy = result.local_center
        self.assertTrue(180 <= cx <= 380, f"Local X center {cx} out of expected bounds")
        self.assertTrue(110 <= cy <= 190, f"Local Y center {cy} out of expected bounds")

        # 螢幕物理座標應包含 roi_phys_origin (100, 100)
        sx, sy = result.screen_target
        self.assertEqual(sx, 100 + cx)
        self.assertEqual(sy, 100 + cy)

    def test_screen_scale_factor(self):
        """測試 DPI 縮放比例取得"""
        dpr = get_screen_scale_factor()
        self.assertGreaterEqual(dpr, 1.0)

    def test_screen_capture(self):
        """測試螢幕小範圍截圖"""
        dpr = get_screen_scale_factor()
        img, phys_rect = capture_roi(10, 10, 100, 100, dpr=dpr)
        self.assertIsNotNone(img)
        expected_w = int(round(100 * dpr))
        expected_h = int(round(100 * dpr))
        self.assertEqual(phys_rect[2], expected_w)
        self.assertEqual(phys_rect[3], expected_h)


if __name__ == "__main__":
    unittest.main()
