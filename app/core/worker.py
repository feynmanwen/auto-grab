"""
Background Worker Threads for Screen OCR AutoClicker:
1. AutoClickWorker: 單一區域循環/單次監控
2. BatchWorkflowWorker: 多步驟循序批次執行
"""
import time
from typing import Optional, List
from PIL import Image, ImageDraw
from PySide6.QtCore import QThread, Signal

from app.config import AppConfig, BatchStep
from app.core.screen_capture import capture_roi, ensure_desktop_access
from app.core.ocr_engine import OCREngine, OCRMatchResult
from app.core.mouse_controller import MouseController
import pyautogui


def draw_crosshair_marker(
    img: Image.Image,
    cx: int,
    cy: int,
    radius: int = 12,
    color: str = "#FF0033",
    label: Optional[str] = None
) -> Image.Image:
    """
    在 PIL 影像上繪製高對比度十字瞄準準心與點擊提示標籤。
    採用雙層顏色（外黑內亮），確保在深色與淺色背景上皆清晰可見。
    """
    out_img = img.copy()
    draw = ImageDraw.Draw(out_img)

    # 1. 雙層圓圈 (黑底 + 亮色)
    for r, col, width in [(radius + 1, "#000000", 3), (radius, color, 2)]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=width)

    # 2. 十字線 (向外延伸)
    line_len = radius + 8
    # 黑色陰影外框
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        draw.line([cx - line_len + dx, cy + dy, cx + line_len + dx, cy + dy], fill="#000000", width=3)
        draw.line([cx + dx, cy - line_len + dy, cx + dx, cy + line_len + dy], fill="#000000", width=3)
    # 亮色主要十字線
    draw.line([cx - line_len, cy, cx + line_len, cy], fill=color, width=2)
    draw.line([cx, cy - line_len, cx, cy + line_len], fill=color, width=2)

    # 3. 中心中心實心小圓點
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill="#FFFF00", outline="#000000")

    # 4. 附帶文字標籤 (例如 "點擊位置")
    if label:
        tx = cx + radius + 6
        ty = cy - 8
        draw.text((tx + 1, ty + 1), label, fill="#000000")
        draw.text((tx, ty), label, fill="#FFFF00")

    return out_img


class AutoClickWorker(QThread):
    """單一區域監控執行緒"""
    log_signal = Signal(str, str)         # (訊息, 級別: info/success/warning/error)
    status_signal = Signal(str)          # 狀態列訊息
    matched_signal = Signal(object)      # OCRMatchResult 物件
    preview_signal = Signal(object)      # PIL Image
    stopped_signal = Signal()            # 執行緒結束

    def __init__(self, config: AppConfig, dpr: float = 1.0, parent=None):
        super().__init__(parent)
        self.config = config
        self.dpr = dpr
        self._is_running = False
        self.ocr_engine = OCREngine()
        self.mouse_controller = MouseController()

    def stop(self):
        self._is_running = False

    def run(self):
        self._is_running = True
        ensure_desktop_access()
        self.log_signal.emit("🚀 開始單一區域文字偵測點選監控...", "info")
        self.status_signal.emit("監控中...")

        try:
            while self._is_running:
                img, phys_rect = capture_roi(
                    self.config.roi_x,
                    self.config.roi_y,
                    self.config.roi_w,
                    self.config.roi_h,
                    self.dpr
                )

                if img is None:
                    self.log_signal.emit("⚠️ 無法擷取螢幕畫面，請確認 ROI 範圍設定", "warning")
                    self._sleep_interruptible(self.config.scan_interval)
                    continue

                phys_origin = (phys_rect[0], phys_rect[1])
                offset = (
                    int(round(self.config.click_offset_x * self.dpr)),
                    int(round(self.config.click_offset_y * self.dpr))
                )

                start_time = time.time()
                match_result: Optional[OCRMatchResult] = self.ocr_engine.find_target_keyword(
                    image=img,
                    keywords=self.config.keywords,
                    match_mode=self.config.match_mode,
                    confidence_threshold=self.config.confidence_threshold,
                    roi_phys_origin=phys_origin,
                    offset=offset
                )
                cost_ms = int((time.time() - start_time) * 1000)

                if match_result:
                    # 繪製命中多邊形紅框與準心
                    preview_img = img.copy()
                    draw = ImageDraw.Draw(preview_img)
                    pts = [(p[0], p[1]) for p in match_result.box]
                    pts.append(pts[0])
                    draw.line(pts, fill="#FF0000", width=3)

                    # 標註準心中心點
                    cx, cy = match_result.local_center
                    offset_cx = cx + int(round(self.config.click_offset_x * self.dpr))
                    offset_cy = cy + int(round(self.config.click_offset_y * self.dpr))
                    preview_img = draw_crosshair_marker(
                        preview_img, offset_cx, offset_cy,
                        color="#00FFCC", label=f"命中: {match_result.matched_text}"
                    )
                    self.preview_signal.emit(preview_img)

                    action_name = "雙擊" if self.config.mouse_action == "double_click" else "單擊"
                    log_msg = (
                        f"🎯 命中目標 [{match_result.target_keyword}] (文字: '{match_result.matched_text}', "
                        f"信心度: {match_result.confidence:.2f}, 耗時: {cost_ms}ms)"
                    )
                    self.log_signal.emit(log_msg, "success")
                    self.matched_signal.emit(match_result)

                    target_x, target_y = match_result.screen_target
                    self.log_signal.emit(
                        f"🖱️ 滑鼠移至螢幕座標 ({target_x}, {target_y}) 執行左鍵{action_name}",
                        "info"
                    )

                    click_success = self.mouse_controller.click_target(
                        x=target_x,
                        y=target_y,
                        action=self.config.mouse_action,
                        restore_cursor=self.config.restore_cursor,
                        move_duration=self.config.move_duration
                    )

                    if not click_success:
                        self.log_signal.emit("❌ 滑鼠點擊操作失敗", "error")

                    if not self.config.loop_mode:
                        self.log_signal.emit("✅ 單次點擊模式已完成，自動停止監控", "info")
                        self.status_signal.emit("已完成 (已停止)")
                        break
                    else:
                        cd = self.config.cooldown_seconds
                        self.log_signal.emit(f"⏳ 進入冷卻時間 ({cd} 秒)...", "info")
                        
                        cd_start = time.time()
                        while self._is_running and (time.time() - cd_start < cd):
                            remain = max(0.0, cd - (time.time() - cd_start))
                            self.status_signal.emit(f"冷卻中 (剩餘 {remain:.1f} 秒)...")
                            time.sleep(0.1)

                        if self._is_running:
                            self.status_signal.emit("監控中...")
                else:
                    # 未命中：在中心加上微調偏移準心顯示
                    cw = img.width // 2 + int(round(self.config.click_offset_x * self.dpr))
                    ch = img.height // 2 + int(round(self.config.click_offset_y * self.dpr))
                    prev_marked = draw_crosshair_marker(img, cw, ch, color="#FFAA00", label="預設點擊點")
                    self.preview_signal.emit(prev_marked)
                    self.status_signal.emit(f"監控中 (掃描 {cost_ms}ms，未發現目標)...")
                    self._sleep_interruptible(self.config.scan_interval)

        except pyautogui.FailSafeException:
            self.log_signal.emit("🛑 偵測到使用者將滑鼠移至角落，已觸發緊急停止！", "error")
            self.status_signal.emit("已觸發安全停止")
        except Exception as e:
            self.log_signal.emit(f"❌ 監控執行緒異常: {str(e)}", "error")
            self.status_signal.emit("發生異常停止")
        finally:
            self._is_running = False
            self.stopped_signal.emit()

    def _sleep_interruptible(self, duration: float):
        steps = int(duration / 0.1)
        for _ in range(steps):
            if not self._is_running:
                break
            time.sleep(0.1)
        remaining = duration - (steps * 0.1)
        if self._is_running and remaining > 0:
            time.sleep(remaining)


class BatchWorkflowWorker(QThread):
    """批次模式 (Batch Workflow) 循序多步驟執行緒"""
    log_signal = Signal(str, str)              # (訊息, 級別)
    status_signal = Signal(str)               # 狀態訊息
    step_started_signal = Signal(int)         # (步驟索引 0-based)
    step_completed_signal = Signal(int)       # (步驟索引 0-based)
    preview_signal = Signal(object)           # PIL Image
    stopped_signal = Signal()                 # 執行緒結束

    def __init__(self, steps: List[BatchStep], loop_batch: bool = False, batch_cooldown: float = 2.0, dpr: float = 1.0, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.loop_batch = loop_batch
        self.batch_cooldown = batch_cooldown
        self.dpr = dpr
        self._is_running = False
        self.ocr_engine = OCREngine()
        self.mouse_controller = MouseController()

    def stop(self):
        self._is_running = False

    def run(self):
        self._is_running = True
        ensure_desktop_access()
        total_steps = len(self.steps)
        if total_batch := total_steps:
            self.log_signal.emit(f"⚡ 開始執行批次工作流 (共 {total_batch} 個步驟)...", "info")
        else:
            self.log_signal.emit("⚠️ 批次步驟清單為空，請先加入步驟！", "warning")
            self.stopped_signal.emit()
            return

        batch_count = 1
        try:
            while self._is_running:
                if self.loop_batch and batch_count > 1:
                    self.log_signal.emit(f"🔁 進入批次循環第 {batch_count} 輪執行...", "info")

                for idx, step in enumerate(self.steps):
                    if not self._is_running:
                        break

                    self.step_started_signal.emit(idx)
                    step_num = idx + 1
                    self.log_signal.emit(
                        f"👉 [步驟 {step_num}/{total_steps}] 啟動監控: 「{step.name}」 "
                        f"(尋找: {', '.join(step.keywords)}, 動作: {'雙擊' if step.mouse_action == 'double_click' else '單擊'})",
                        "info"
                    )
                    self.status_signal.emit(f"步驟 {step_num}/{total_steps}「{step.name}」等待中...")

                    step_start_time = time.time()
                    step_matched = False

                    # 單一步驟等待文字出現的循環
                    while self._is_running and not step_matched:
                        # 檢查超時
                        elapsed = time.time() - step_start_time
                        if step.timeout_seconds > 0 and elapsed > step.timeout_seconds:
                            self.log_signal.emit(
                                f"❌ 步驟 {step_num} 等待超時 ({step.timeout_seconds}秒未出現目標文字)，中止批次流程！",
                                "error"
                            )
                            self.status_signal.emit(f"步驟 {step_num} 超時中止")
                            self._is_running = False
                            break

                        # 擷取該步驟的專屬 ROI
                        img, phys_rect = capture_roi(
                            step.roi_x, step.roi_y, step.roi_w, step.roi_h, self.dpr
                        )

                        if img is None:
                            time.sleep(0.3)
                            continue

                        phys_origin = (phys_rect[0], phys_rect[1])
                        offset = (
                            int(round(step.click_offset_x * self.dpr)),
                            int(round(step.click_offset_y * self.dpr))
                        )

                        match_result = self.ocr_engine.find_target_keyword(
                            image=img,
                            keywords=step.keywords,
                            match_mode=step.match_mode,
                            confidence_threshold=step.confidence_threshold,
                            roi_phys_origin=phys_origin,
                            offset=offset
                        )

                        if match_result:
                            step_matched = True
                            # 繪製命中高亮圖與準心
                            preview_img = img.copy()
                            draw = ImageDraw.Draw(preview_img)
                            pts = [(p[0], p[1]) for p in match_result.box]
                            pts.append(pts[0])
                            draw.line(pts, fill="#FF0000", width=3)

                            cx, cy = match_result.local_center
                            offset_cx = cx + int(round(step.click_offset_x * self.dpr))
                            offset_cy = cy + int(round(step.click_offset_y * self.dpr))
                            preview_img = draw_crosshair_marker(
                                preview_img, offset_cx, offset_cy,
                                color="#00FFCC", label=f"命中: {match_result.matched_text}"
                            )
                            self.preview_signal.emit(preview_img)

                            # 執行滑鼠動作
                            tx, ty = match_result.screen_target
                            action_str = "雙擊" if step.mouse_action == "double_click" else "單擊"
                            self.log_signal.emit(
                                f"🎯 步驟 {step_num} 命中 '{match_result.matched_text}'！移至 ({tx}, {ty}) 執行{action_str}",
                                "success"
                            )

                            self.mouse_controller.click_target(
                                x=tx, y=ty, action=step.mouse_action, restore_cursor=False
                            )
                            self.step_completed_signal.emit(idx)

                            # 點擊後延遲 post_delay
                            if step.post_delay > 0:
                                self.log_signal.emit(f"⏳ 步驟 {step_num} 完成，延遲等待 {step.post_delay} 秒後進行下一步...", "info")
                                cd_start = time.time()
                                while self._is_running and (time.time() - cd_start < step.post_delay):
                                    rem = max(0.0, step.post_delay - (time.time() - cd_start))
                                    self.status_signal.emit(f"步驟 {step_num} 完成，等待下一步 (剩餘 {rem:.1f} 秒)...")
                                    time.sleep(0.1)
                        else:
                            # 未命中：即時預覽未命中畫面及準心
                            cw = img.width // 2 + int(round(step.click_offset_x * self.dpr))
                            ch = img.height // 2 + int(round(step.click_offset_y * self.dpr))
                            prev_marked = draw_crosshair_marker(img, cw, ch, color="#FFAA00", label="目標準心")
                            self.preview_signal.emit(prev_marked)
                            time.sleep(0.3)

                    if not step_matched:
                        # 該步驟未完成且已跳出 (超時或中斷)
                        break

                if not self._is_running:
                    break

                # 整批步驟全數完成
                self.log_signal.emit(f"🎉 批次流程 (第 {batch_count} 輪) 所有步驟已全數順利完成！", "success")
                if self.loop_batch:
                    batch_count += 1
                    self.log_signal.emit(f"⏳ 整批冷卻等待 {self.batch_cooldown} 秒後重新從步驟 1 循環...", "info")
                    cd_start = time.time()
                    while self._is_running and (time.time() - cd_start < self.batch_cooldown):
                        rem = max(0.0, self.batch_cooldown - (time.time() - cd_start))
                        self.status_signal.emit(f"整批循環冷卻中 (剩餘 {rem:.1f} 秒)...")
                        time.sleep(0.1)
                else:
                    self.status_signal.emit("批次流程全數完成")
                    break

        except pyautogui.FailSafeException:
            self.log_signal.emit("🛑 偵測到使用者將滑鼠移至角落，批次已緊急終止！", "error")
            self.status_signal.emit("已觸發安全停止")
        except Exception as e:
            self.log_signal.emit(f"❌ 批次執行異常: {str(e)}", "error")
            self.status_signal.emit("批次異常中斷")
        finally:
            self._is_running = False
            self.stopped_signal.emit()
