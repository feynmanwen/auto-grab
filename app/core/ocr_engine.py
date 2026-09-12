"""
OCR Engine Module using RapidOCR
"""
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional, Any
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR


@dataclass
class OCRMatchResult:
    matched_text: str
    target_keyword: str
    confidence: float
    box: List[List[float]]              # 區域內文字外框 4 點座標 [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    local_center: Tuple[int, int]       # ROI 影像內的中心座標 (px, py)
    screen_target: Tuple[int, int]      # 螢幕實體座標 (可直接傳給滑鼠點擊)


class OCREngine:
    def __init__(self):
        # 初始化 RapidOCR 實例 (支援中英混排與繁簡體)
        self.engine = RapidOCR()

    def recognize(self, image: Image.Image) -> List[dict]:
        """
        對傳入的 PIL Image 進行文字辨識。
        返回辨識清單: [{"box": [...], "text": str, "score": float}]
        """
        if image is None:
            return []

        # 轉換為 numpy array (RGB)
        img_np = np.array(image.convert("RGB"))
        ocr_res, elapse = self.engine(img_np)
        
        results = []
        if ocr_res:
            for item in ocr_res:
                box, text, score = item
                results.append({
                    "box": box,
                    "text": str(text).strip(),
                    "score": float(score)
                })
        return results

    def find_target_keyword(
        self,
        image: Image.Image,
        keywords: List[str],
        match_mode: str = "contains",
        confidence_threshold: float = 0.6,
        roi_phys_origin: Tuple[int, int] = (0, 0),
        offset: Tuple[int, int] = (0, 0)
    ) -> Optional[OCRMatchResult]:
        """
        在圖像中辨識文字並尋找是否命中關鍵字清單。
        
        :param image: 擷取的 ROI 圖像 (PIL Image)
        :param keywords: 尋找的關鍵字清單 (例如 ["確定", "OK"])
        :param match_mode: 匹配模式 ("contains" 或 "exact")
        :param confidence_threshold: 信心度門檻值 (0.0 ~ 1.0)
        :param roi_phys_origin: ROI 在螢幕上的物理左上角座標 (phys_x, phys_y)
        :param offset: 自訂點擊偏移量 (offset_x, offset_y)
        :return: 若命中則回傳 OCRMatchResult，否則回傳 None
        """
        detections = self.recognize(image)
        if not detections:
            return None

        clean_keywords = [kw.strip() for kw in keywords if kw.strip()]
        if not clean_keywords:
            return None

        best_match: Optional[OCRMatchResult] = None
        highest_score = -1.0

        for item in detections:
            text = item["text"]
            score = item["score"]

            if score < confidence_threshold:
                continue

            matched_kw = None
            for kw in clean_keywords:
                if match_mode == "exact":
                    if text == kw:
                        matched_kw = kw
                        break
                else:  # "contains" 包含匹配
                    if kw in text:
                        matched_kw = kw
                        break

            if matched_kw:
                # 計算外框 4 點的幾何中心點
                box = item["box"]
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                local_cx = int(round(sum(xs) / len(xs)))
                local_cy = int(round(sum(ys) / len(ys)))

                # 螢幕物理座標 = ROI 左上角 + 本地中心點 + 偏移量
                screen_x = roi_phys_origin[0] + local_cx + offset[0]
                screen_y = roi_phys_origin[1] + local_cy + offset[1]

                if score > highest_score:
                    highest_score = score
                    best_match = OCRMatchResult(
                        matched_text=text,
                        target_keyword=matched_kw,
                        confidence=score,
                        box=box,
                        local_center=(local_cx, local_cy),
                        screen_target=(screen_x, screen_y)
                    )

        return best_match
