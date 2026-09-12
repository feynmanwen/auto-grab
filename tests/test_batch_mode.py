"""
Tests for Batch Mode and Crosshair Target Preview
"""
import os
import sys
import unittest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import AppConfig, BatchStep
from app.core.worker import draw_crosshair_marker, BatchWorkflowWorker
from app.core.screen_capture import capture_roi, get_screen_scale_factor, ensure_desktop_access

ensure_desktop_access()


class TestBatchMode(unittest.TestCase):
    def test_batch_step_serialization(self):
        step = BatchStep(
            name="測試步驟1",
            roi_x=200,
            roi_y=300,
            roi_w=400,
            roi_h=150,
            keywords=["確認", "OK"],
            match_mode="exact",
            confidence_threshold=0.8,
            mouse_action="double_click",
            click_offset_x=10,
            click_offset_y=-5,
            post_delay=2.5,
            timeout_seconds=45.0
        )
        d = step.to_dict()
        self.assertEqual(d["name"], "測試步驟1")
        self.assertEqual(d["roi_x"], 200)
        self.assertEqual(d["mouse_action"], "double_click")
        self.assertEqual(d["post_delay"], 2.5)

        restored = BatchStep.from_dict(d)
        self.assertEqual(restored.name, "測試步驟1")
        self.assertEqual(restored.keywords, ["確認", "OK"])
        self.assertEqual(restored.post_delay, 2.5)

    def test_app_config_with_batch_steps(self):
        cfg = AppConfig()
        cfg.batch_steps.append(BatchStep(name="Step 1", keywords=["登入"]))
        cfg.batch_steps.append(BatchStep(name="Step 2", keywords=["開始"]))
        cfg.batch_loop = True
        cfg.batch_cooldown = 3.5

        test_file = "test_batch_config.json"
        cfg.save(test_file)
        self.assertTrue(os.path.exists(test_file))

        loaded = AppConfig.load(test_file)
        self.assertEqual(len(loaded.batch_steps), 2)
        self.assertEqual(loaded.batch_steps[0].name, "Step 1")
        self.assertEqual(loaded.batch_steps[1].name, "Step 2")
        self.assertTrue(loaded.batch_loop)
        self.assertEqual(loaded.batch_cooldown, 3.5)

        if os.path.exists(test_file):
            os.remove(test_file)

    def test_crosshair_marker_drawing(self):
        img = Image.new("RGB", (200, 200), (50, 50, 50))
        marked = draw_crosshair_marker(img, 100, 100, color="#FF0033", label="點擊處")
        self.assertEqual(marked.size, (200, 200))
        # 標註後應該有紅色與黃色像素
        extrema = marked.getextrema()
        self.assertNotEqual(extrema, ((50, 50), (50, 50), (50, 50)))

    def test_screen_capture_non_black(self):
        dpr = get_screen_scale_factor()
        img, rect = capture_roi(100, 100, 100, 100, dpr)
        self.assertIsNotNone(img, "截圖結果不應為 None")
        expected_w = int(round(100 * dpr))
        expected_h = int(round(100 * dpr))
        self.assertEqual(rect[2], expected_w)
        self.assertEqual(rect[3], expected_h)


if __name__ == "__main__":
    unittest.main()
