"""
Main Window for Screen OCR AutoClicker supporting Single and Batch Modes.
"""
import os
import time
from typing import Optional, List
from PIL import Image, ImageQt
from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer
from PySide6.QtGui import QPixmap, QImage, QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QRadioButton, QButtonGroup, QTextEdit, QGroupBox,
    QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView
)

from app.config import AppConfig, BatchStep
from app.core.screen_capture import capture_roi, get_screen_scale_factor
from app.core.worker import AutoClickWorker, BatchWorkflowWorker, draw_crosshair_marker
from app.ui.roi_selector import ROISelectorOverlay
from app.ui.batch_step_dialog import BatchStepDialog
import keyboard


class HotkeySignaler(QObject):
    hotkey_pressed = Signal()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自動文字偵測點選工具 (Screen OCR AutoClicker) - [單一 / 批次雙模式]")
        self.resize(1050, 750)

        # 載入設定
        self.config = AppConfig.load()
        self.dpr = get_screen_scale_factor()

        # 熱鍵訊號轉發器
        self.hotkey_signaler = HotkeySignaler()
        self.hotkey_signaler.hotkey_pressed.connect(self._on_hotkey_toggle)

        # 背景執行緒實例
        self.single_worker: Optional[AutoClickWorker] = None
        self.batch_worker: Optional[BatchWorkflowWorker] = None

        # 延遲更新預覽的計時器 (避免拉動數值滑桿頻繁截圖)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(60)
        self.preview_timer.timeout.connect(self._do_refresh_single_preview)

        # 初始化介面
        self._init_ui()
        self._load_config_to_ui()
        self._setup_global_hotkey()

        # 啟動時立即擷取並預覽一次
        QTimer.singleShot(150, self._refresh_roi_preview)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # === 左側控制面板 (採用 QTabWidget 分頁) ===
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("QTabBar::tab { font-weight: bold; padding: 8px 16px; }")

        # 分頁 1: 單一區域模式
        single_tab = QWidget()
        self._setup_single_tab(single_tab)
        self.tab_widget.addTab(single_tab, "📍 單一區域模式")

        # 分頁 2: 批次工作流模式
        batch_tab = QWidget()
        self._setup_batch_tab(batch_tab)
        self.tab_widget.addTab(batch_tab, "⚡ 批次多步驟模式")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # === 右側面板：預覽畫面與即時日誌 ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 預覽圖群組
        preview_group = QGroupBox("🖼️ 即時畫面預覽 (瞄準準心標註點擊目標)")
        preview_layout = QVBoxLayout(preview_group)
        self.lbl_preview_info = QLabel("區域: 未知 | 點擊座標: 未知")
        self.lbl_preview_info.setStyleSheet("font-size: 11px; color: #555; font-weight: bold;")
        preview_layout.addWidget(self.lbl_preview_info)

        self.lbl_preview = QLabel("尚未擷取預覽")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setMinimumSize(400, 260)
        self.lbl_preview.setStyleSheet("background-color: #1e1e1e; color: #888888; border: 1px solid #333; border-radius: 4px;")
        preview_layout.addWidget(self.lbl_preview)
        right_layout.addWidget(preview_group)

        # 日誌群組
        log_group = QGroupBox("📋 執行日誌紀錄")
        log_layout = QVBoxLayout(log_group)
        
        log_top_layout = QHBoxLayout()
        self.lbl_status = QLabel("狀態: 待命中 (按 F8 或點擊開始)")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #0d6efd;")
        self.btn_clear_log = QPushButton("清空日誌")
        self.btn_clear_log.clicked.connect(lambda: self.log_view.clear())
        log_top_layout.addWidget(self.lbl_status)
        log_top_layout.addStretch()
        log_top_layout.addWidget(self.btn_clear_log)
        log_layout.addLayout(log_top_layout)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #f8f9fa; font-family: Consolas, monospace; font-size: 11px;")
        log_layout.addWidget(self.log_view)

        right_layout.addWidget(log_group)

        # 左右分配比例 48 : 52
        main_layout.addWidget(self.tab_widget, stretch=5)
        main_layout.addWidget(right_panel, stretch=5)

    # -------------------------------------------------------------
    # 單一模式介面建置
    # -------------------------------------------------------------
    def _setup_single_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 1. ROI 區域設定
        roi_group = QGroupBox("📍 螢幕感興趣區域 (ROI)")
        roi_layout = QVBoxLayout(roi_group)

        btn_roi_layout = QHBoxLayout()
        self.btn_select_roi = QPushButton("📐 框選螢幕區域 (選取)")
        self.btn_select_roi.setStyleSheet("font-weight: bold; padding: 6px 12px; background-color: #0d6efd; color: white; border-radius: 4px;")
        self.btn_select_roi.clicked.connect(self._start_roi_selection)
        self.btn_preview_roi = QPushButton("📷 立即重整預覽")
        self.btn_preview_roi.clicked.connect(self._refresh_roi_preview)
        btn_roi_layout.addWidget(self.btn_select_roi)
        btn_roi_layout.addWidget(self.btn_preview_roi)
        roi_layout.addLayout(btn_roi_layout)

        coord_grid = QGridLayout()
        coord_grid.addWidget(QLabel("X:"), 0, 0)
        self.spin_roi_x = QSpinBox()
        self.spin_roi_x.setRange(-9999, 99999)
        coord_grid.addWidget(self.spin_roi_x, 0, 1)

        coord_grid.addWidget(QLabel("Y:"), 0, 2)
        self.spin_roi_y = QSpinBox()
        self.spin_roi_y.setRange(-9999, 99999)
        coord_grid.addWidget(self.spin_roi_y, 0, 3)

        coord_grid.addWidget(QLabel("寬度 (W):"), 1, 0)
        self.spin_roi_w = QSpinBox()
        self.spin_roi_w.setRange(10, 99999)
        coord_grid.addWidget(self.spin_roi_w, 1, 1)

        coord_grid.addWidget(QLabel("高度 (H):"), 1, 2)
        self.spin_roi_h = QSpinBox()
        self.spin_roi_h.setRange(10, 99999)
        coord_grid.addWidget(self.spin_roi_h, 1, 3)

        # 數值調整時即時觸發更新與重繪準心
        self.spin_roi_x.valueChanged.connect(self._on_single_param_changed)
        self.spin_roi_y.valueChanged.connect(self._on_single_param_changed)
        self.spin_roi_w.valueChanged.connect(self._on_single_param_changed)
        self.spin_roi_h.valueChanged.connect(self._on_single_param_changed)

        roi_layout.addLayout(coord_grid)
        layout.addWidget(roi_group)

        # 2. 文字目標設定
        ocr_group = QGroupBox("🔍 OCR 文字目標辨識")
        ocr_layout = QGridLayout(ocr_group)
        ocr_layout.addWidget(QLabel("目標關鍵字:"), 0, 0)
        self.edit_keywords = QLineEdit()
        self.edit_keywords.setPlaceholderText("多組字詞請用逗號分隔，例如: 確定, 送出, OK")
        ocr_layout.addWidget(self.edit_keywords, 0, 1)

        ocr_layout.addWidget(QLabel("匹配模式:"), 1, 0)
        self.combo_match_mode = QComboBox()
        self.combo_match_mode.addItems(["包含關鍵字 (模糊匹配)", "完全一致 (精確匹配)"])
        ocr_layout.addWidget(self.combo_match_mode, 1, 1)

        ocr_layout.addWidget(QLabel("信心度門檻:"), 2, 0)
        self.spin_confidence = QDoubleSpinBox()
        self.spin_confidence.setRange(0.1, 1.0)
        self.spin_confidence.setSingleStep(0.05)
        self.spin_confidence.setValue(0.60)
        ocr_layout.addWidget(self.spin_confidence, 2, 1)
        layout.addWidget(ocr_group)

        # 3. 滑鼠動作設定
        mouse_group = QGroupBox("🖱️ 滑鼠行為與執行策略")
        mouse_layout = QGridLayout(mouse_group)

        mouse_layout.addWidget(QLabel("點擊動作:"), 0, 0)
        self.combo_mouse_action = QComboBox()
        self.combo_mouse_action.addItems(["左鍵單擊 (Single Click)", "左鍵雙擊 (Double Click)"])
        mouse_layout.addWidget(self.combo_mouse_action, 0, 1)

        mouse_layout.addWidget(QLabel("執行模式:"), 1, 0)
        mode_layout = QHBoxLayout()
        self.radio_loop = QRadioButton("循環監控 (命中後冷卻繼續)")
        self.radio_single = QRadioButton("單次點擊 (命中後停止)")
        self.radio_group = QButtonGroup(self)
        self.radio_group.addButton(self.radio_loop)
        self.radio_group.addButton(self.radio_single)
        mode_layout.addWidget(self.radio_loop)
        mode_layout.addWidget(self.radio_single)
        mouse_layout.addLayout(mode_layout, 1, 1)

        mouse_layout.addWidget(QLabel("冷卻時間 (秒):"), 2, 0)
        self.spin_cooldown = QDoubleSpinBox()
        self.spin_cooldown.setRange(0.2, 300.0)
        self.spin_cooldown.setSingleStep(0.5)
        self.spin_cooldown.setValue(3.0)
        mouse_layout.addWidget(self.spin_cooldown, 2, 1)

        mouse_layout.addWidget(QLabel("掃描輪詢間隔 (秒):"), 3, 0)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 60.0)
        self.spin_interval.setSingleStep(0.2)
        self.spin_interval.setValue(1.0)
        mouse_layout.addWidget(self.spin_interval, 3, 1)

        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("X 偏移:"))
        self.spin_offset_x = QSpinBox()
        self.spin_offset_x.setRange(-500, 500)
        offset_layout.addWidget(self.spin_offset_x)
        offset_layout.addWidget(QLabel("Y 偏移:"))
        self.spin_offset_y = QSpinBox()
        self.spin_offset_y.setRange(-500, 500)
        offset_layout.addWidget(self.spin_offset_y)

        # 偏移調整時立即重繪準心！
        self.spin_offset_x.valueChanged.connect(self._on_single_param_changed)
        self.spin_offset_y.valueChanged.connect(self._on_single_param_changed)

        mouse_layout.addWidget(QLabel("點擊座標微調:"), 4, 0)
        mouse_layout.addLayout(offset_layout, 4, 1)

        self.check_restore_cursor = QCheckBox("點擊後將游標復原至原位")
        mouse_layout.addWidget(self.check_restore_cursor, 5, 0, 1, 2)
        layout.addWidget(mouse_group)

        # 4. 控制按鈕
        control_group = QGroupBox("⚡ 執行控制")
        ctrl_layout = QVBoxLayout(control_group)

        self.btn_single_toggle = QPushButton("▶ 開始單一監控 (快捷鍵: F8)")
        self.btn_single_toggle.setStyleSheet(
            "font-size: 15px; font-weight: bold; padding: 10px; "
            "background-color: #198754; color: white; border-radius: 6px;"
        )
        self.btn_single_toggle.clicked.connect(self._toggle_single_monitoring)
        ctrl_layout.addWidget(self.btn_single_toggle)

        tip_label = QLabel("提示：隨時按下 <b>F8</b> 或將滑鼠甩至螢幕左上角均可緊急中斷！")
        tip_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        ctrl_layout.addWidget(tip_label)

        layout.addWidget(control_group)
        layout.addStretch()

    # -------------------------------------------------------------
    # 批次模式介面建置
    # -------------------------------------------------------------
    def _setup_batch_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 步驟列表工具列
        tb_layout = QHBoxLayout()
        self.btn_add_step = QPushButton("➕ 新增步驟")
        self.btn_add_step.setStyleSheet("font-weight: bold; background-color: #0d6efd; color: white;")
        self.btn_add_step.clicked.connect(self._on_add_batch_step)

        self.btn_edit_step = QPushButton("✏️ 編輯")
        self.btn_edit_step.clicked.connect(self._on_edit_batch_step)

        self.btn_reselect_roi = QPushButton("📐 重新框選 ROI")
        self.btn_reselect_roi.clicked.connect(self._on_reselect_batch_roi)

        self.btn_del_step = QPushButton("🗑️ 刪除")
        self.btn_del_step.setStyleSheet("color: #dc3545;")
        self.btn_del_step.clicked.connect(self._on_delete_batch_step)

        self.btn_move_up = QPushButton("⬆️ 上移")
        self.btn_move_up.clicked.connect(self._on_move_step_up)

        self.btn_move_down = QPushButton("⬇️ 下移")
        self.btn_move_down.clicked.connect(self._on_move_step_down)

        tb_layout.addWidget(self.btn_add_step)
        tb_layout.addWidget(self.btn_edit_step)
        tb_layout.addWidget(self.btn_reselect_roi)
        tb_layout.addWidget(self.btn_del_step)
        tb_layout.addWidget(self.btn_move_up)
        tb_layout.addWidget(self.btn_move_down)
        layout.addLayout(tb_layout)

        # 批次步驟表格清單
        self.table_steps = QTableWidget()
        self.table_steps.setColumnCount(7)
        self.table_steps.setHorizontalHeaderLabels([
            "序號", "步驟名稱", "ROI 座標 (X, Y, W, H)", "目標文字", "滑鼠動作", "後續延遲", "超時"
        ])
        self.table_steps.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_steps.horizontalHeader().setStretchLastSection(True)
        self.table_steps.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_steps.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_steps.itemSelectionChanged.connect(self._on_step_row_selected)
        self.table_steps.doubleClicked.connect(self._on_edit_batch_step)
        layout.addWidget(self.table_steps)

        # 批次循環設定
        batch_opt_group = QGroupBox("⚙️ 批次執行策略")
        bopt_layout = QHBoxLayout(batch_opt_group)
        self.check_batch_loop = QCheckBox("整批完成後持續循環重跑")
        self.check_batch_loop.stateChanged.connect(self._save_ui_to_config)
        bopt_layout.addWidget(self.check_batch_loop)

        bopt_layout.addWidget(QLabel("整批循環冷卻 (秒):"))
        self.spin_batch_cd = QDoubleSpinBox()
        self.spin_batch_cd.setRange(0.5, 300.0)
        self.spin_batch_cd.setValue(2.0)
        self.spin_batch_cd.valueChanged.connect(self._save_ui_to_config)
        bopt_layout.addWidget(self.spin_batch_cd)
        layout.addWidget(batch_opt_group)

        # 批次執行控制按鈕
        self.btn_batch_toggle = QPushButton("▶ 開始執行批次工作流 (快捷鍵: F8)")
        self.btn_batch_toggle.setStyleSheet(
            "font-size: 15px; font-weight: bold; padding: 10px; "
            "background-color: #198754; color: white; border-radius: 6px;"
        )
        self.btn_batch_toggle.clicked.connect(self._toggle_batch_monitoring)
        layout.addWidget(self.btn_batch_toggle)

    # -------------------------------------------------------------
    # 快捷鍵與分頁事件
    # -------------------------------------------------------------
    def _setup_global_hotkey(self):
        try:
            keyboard.add_hotkey("f8", lambda: self.hotkey_signaler.hotkey_pressed.emit())
        except Exception as e:
            self._append_log(f"⚠️ 全域快捷鍵 F8 註冊失敗: {e}", "warning")

    @Slot()
    def _on_hotkey_toggle(self):
        """根據當前分頁或執行狀態切換開始/停止"""
        if self.single_worker and self.single_worker.isRunning():
            self._stop_single_monitoring()
        elif self.batch_worker and self.batch_worker.isRunning():
            self._stop_batch_monitoring()
        else:
            if self.tab_widget.currentIndex() == 0:
                self._start_single_monitoring()
            else:
                self._start_batch_monitoring()

    def _on_tab_changed(self, index: int):
        if index == 0:
            self._refresh_roi_preview()
        else:
            self._on_step_row_selected()

    # -------------------------------------------------------------
    # 單一模式邏輯與即時準心預覽
    # -------------------------------------------------------------
    def _on_single_param_changed(self):
        """當調整 X, Y, W, H 或點擊偏移時，觸發延遲刷新，避免頻繁呼叫"""
        self._save_ui_to_config()
        self.preview_timer.start()

    def _do_refresh_single_preview(self):
        self._refresh_roi_preview()

    def _refresh_roi_preview(self):
        """擷取單一模式目前 ROI 畫面並在上面即時繪製瞄準準心"""
        self._save_ui_to_config()
        img, phys_rect = capture_roi(
            self.config.roi_x,
            self.config.roi_y,
            self.config.roi_w,
            self.config.roi_h,
            self.dpr
        )
        if img:
            # 計算中心點加偏移量 (物理像素)
            cw = img.width // 2 + int(round(self.config.click_offset_x * self.dpr))
            ch = img.height // 2 + int(round(self.config.click_offset_y * self.dpr))
            marked_img = draw_crosshair_marker(img, cw, ch, color="#00E5FF", label="點擊目標位置")
            self._display_preview_image(marked_img)

            phys_cx = phys_rect[0] + cw
            phys_cy = phys_rect[1] + ch
            self.lbl_preview_info.setText(
                f"📍 ROI: ({self.config.roi_x}, {self.config.roi_y}, {self.config.roi_w}x{self.config.roi_h}) | "
                f"🎯 點擊螢幕座標: ({phys_cx}, {phys_cy})"
            )
        else:
            self.lbl_preview.setText("無法擷取此範圍 (尺寸無效或超出邊界)")
            self.lbl_preview_info.setText("擷取失敗")

    def _display_preview_image(self, pil_image: Image.Image):
        """將 PIL Image 等比縮放並清晰顯示在 lbl_preview"""
        try:
            qim = ImageQt.ImageQt(pil_image)
            pixmap = QPixmap.fromImage(qim)
            scaled = pixmap.scaled(
                self.lbl_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_preview.setPixmap(scaled)
        except Exception as e:
            print(f"Error displaying preview: {e}")

    def _start_roi_selection(self):
        self.setWindowOpacity(0.0)
        overlay = ROISelectorOverlay(self)
        if overlay.exec() == QDialog.DialogCode.Accepted:
            x, y, w, h = overlay.get_roi()
            self.spin_roi_x.setValue(x)
            self.spin_roi_y.setValue(y)
            self.spin_roi_w.setValue(w)
            self.spin_roi_h.setValue(h)
            self._save_ui_to_config()
            self._append_log(f"📍 已更新 ROI 區域: (X={x}, Y={y}, W={w}, H={h})", "success")
            self._refresh_roi_preview()
        else:
            self._append_log("取消框選 ROI 區域", "info")
        self.setWindowOpacity(1.0)
        self.raise_()
        self.activateWindow()

    def _toggle_single_monitoring(self):
        if self.single_worker and self.single_worker.isRunning():
            self._stop_single_monitoring()
        else:
            self._start_single_monitoring()

    def _start_single_monitoring(self):
        self._save_ui_to_config()
        if not self.config.keywords:
            QMessageBox.warning(self, "未設定關鍵字", "請先輸入至少一個目標文字關鍵字！")
            return
        if self.config.roi_w <= 0 or self.config.roi_h <= 0:
            QMessageBox.warning(self, "ROI 無效", "請先框選或輸入有效的 ROI 寬度與高度！")
            return

        self.btn_single_toggle.setText("⏹ 停止監控 (快捷鍵: F8)")
        self.btn_single_toggle.setStyleSheet(
            "font-size: 15px; font-weight: bold; padding: 10px; "
            "background-color: #dc3545; color: white; border-radius: 6px;"
        )
        self.btn_select_roi.setEnabled(False)

        self.single_worker = AutoClickWorker(self.config, self.dpr, parent=self)
        self.single_worker.log_signal.connect(self._append_log)
        self.single_worker.status_signal.connect(self._update_status)
        self.single_worker.preview_signal.connect(self._display_preview_image)
        self.single_worker.stopped_signal.connect(self._on_single_worker_stopped)
        self.single_worker.start()

    def _stop_single_monitoring(self):
        if self.single_worker:
            self.lbl_status.setText("狀態: 正在停止...")
            self.single_worker.stop()

    @Slot()
    def _on_single_worker_stopped(self):
        self.btn_single_toggle.setText("▶ 開始單一監控 (快捷鍵: F8)")
        self.btn_single_toggle.setStyleSheet(
            "font-size: 15px; font-weight: bold; padding: 10px; "
            "background-color: #198754; color: white; border-radius: 6px;"
        )
        self.btn_select_roi.setEnabled(True)
        self.lbl_status.setText("狀態: 已停止")
        self._append_log("⏹ 單一監控已停止", "info")

    # -------------------------------------------------------------
    # 批次模式邏輯與表格操作
    # -------------------------------------------------------------
    def _update_batch_table(self):
        """重新整理批次表格顯示"""
        self.table_steps.setRowCount(len(self.config.batch_steps))
        for row, step in enumerate(self.config.batch_steps):
            item_seq = QTableWidgetItem(str(row + 1))
            item_seq.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_name = QTableWidgetItem(step.name)
            item_roi = QTableWidgetItem(f"({step.roi_x}, {step.roi_y}, {step.roi_w}x{step.roi_h})")
            item_kw = QTableWidgetItem(", ".join(step.keywords))
            
            act_str = "左鍵雙擊" if step.mouse_action == "double_click" else "左鍵單擊"
            item_act = QTableWidgetItem(act_str)
            item_delay = QTableWidgetItem(f"{step.post_delay}s")
            item_delay.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_to = QTableWidgetItem(f"{step.timeout_seconds}s" if step.timeout_seconds > 0 else "無")
            item_to.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_steps.setItem(row, 0, item_seq)
            self.table_steps.setItem(row, 1, item_name)
            self.table_steps.setItem(row, 2, item_roi)
            self.table_steps.setItem(row, 3, item_kw)
            self.table_steps.setItem(row, 4, item_act)
            self.table_steps.setItem(row, 5, item_delay)
            self.table_steps.setItem(row, 6, item_to)

    def _on_step_row_selected(self):
        """當使用者選取某個步驟列時，在右側即時預覽該步驟的 ROI 與準心"""
        row = self.table_steps.currentRow()
        if 0 <= row < len(self.config.batch_steps):
            step = self.config.batch_steps[row]
            img, phys_rect = capture_roi(step.roi_x, step.roi_y, step.roi_w, step.roi_h, self.dpr)
            if img:
                cw = img.width // 2 + int(round(step.click_offset_x * self.dpr))
                ch = img.height // 2 + int(round(step.click_offset_y * self.dpr))
                marked_img = draw_crosshair_marker(img, cw, ch, color="#FF0055", label=f"步驟 {row + 1} 準心")
                self._display_preview_image(marked_img)
                self.lbl_preview_info.setText(
                    f"👉 選取步驟 {row + 1}「{step.name}」 | ROI: ({step.roi_x}, {step.roi_y}, {step.roi_w}x{step.roi_h})"
                )

    def _on_add_batch_step(self):
        dialog = BatchStepDialog(step_index=len(self.config.batch_steps) + 1, parent=self)
        if dialog.exec():
            step = dialog.get_step()
            self.config.batch_steps.append(step)
            self.config.save()
            self._update_batch_table()
            self.table_steps.selectRow(len(self.config.batch_steps) - 1)
            self._append_log(f"➕ 已新增批次步驟: {step.name}", "success")

    def _on_edit_batch_step(self):
        row = self.table_steps.currentRow()
        if not (0 <= row < len(self.config.batch_steps)):
            QMessageBox.information(self, "提示", "請先點選欲編輯的步驟！")
            return
        step = self.config.batch_steps[row]
        dialog = BatchStepDialog(step=step, parent=self)
        if dialog.exec():
            self.config.save()
            self._update_batch_table()
            self.table_steps.selectRow(row)
            self._append_log(f"✏️ 已更新批次步驟: {step.name}", "info")

    def _on_reselect_batch_roi(self):
        row = self.table_steps.currentRow()
        if not (0 <= row < len(self.config.batch_steps)):
            QMessageBox.information(self, "提示", "請先點選欲重新框選的步驟！")
            return
        step = self.config.batch_steps[row]
        self.setWindowOpacity(0.0)
        overlay = ROISelectorOverlay(self)
        if overlay.exec() == QDialog.DialogCode.Accepted:
            x, y, w, h = overlay.get_roi()
            step.roi_x, step.roi_y, step.roi_w, step.roi_h = x, y, w, h
            self.config.save()
            self._update_batch_table()
            self.table_steps.selectRow(row)
            self._append_log(f"📐 步驟 {row + 1}「{step.name}」ROI 更新為 ({x}, {y}, {w}x{h})", "success")
        else:
            self._append_log("取消重新框選批次 ROI", "info")
        self.setWindowOpacity(1.0)
        self.raise_()
        self.activateWindow()

    def _on_delete_batch_step(self):
        row = self.table_steps.currentRow()
        if not (0 <= row < len(self.config.batch_steps)):
            return
        step = self.config.batch_steps[row]
        reply = QMessageBox.question(self, "確認刪除", f"確定要刪除步驟「{step.name}」嗎？")
        if reply == QMessageBox.StandardButton.Yes:
            del self.config.batch_steps[row]
            self.config.save()
            self._update_batch_table()
            self._append_log(f"🗑️ 已刪除步驟: {step.name}", "info")

    def _on_move_step_up(self):
        row = self.table_steps.currentRow()
        if row > 0:
            steps = self.config.batch_steps
            steps[row - 1], steps[row] = steps[row], steps[row - 1]
            self.config.save()
            self._update_batch_table()
            self.table_steps.selectRow(row - 1)

    def _on_move_step_down(self):
        row = self.table_steps.currentRow()
        if 0 <= row < len(self.config.batch_steps) - 1:
            steps = self.config.batch_steps
            steps[row + 1], steps[row] = steps[row], steps[row + 1]
            self.config.save()
            self._update_batch_table()
            self.table_steps.selectRow(row + 1)

    def _toggle_batch_monitoring(self):
        if self.batch_worker and self.batch_worker.isRunning():
            self._stop_batch_monitoring()
        else:
            self._start_batch_monitoring()

    def _start_batch_monitoring(self):
        if not self.config.batch_steps:
            QMessageBox.warning(self, "步驟清單為空", "請先至少新增一個批次步驟！")
            return

        self.btn_batch_toggle.setText("⏹ 停止批次 (快捷鍵: F8)")
        self.btn_batch_toggle.setStyleSheet(
            "font-size: 15px; font-weight: bold; padding: 10px; "
            "background-color: #dc3545; color: white; border-radius: 6px;"
        )

        self.batch_worker = BatchWorkflowWorker(
            steps=self.config.batch_steps,
            loop_batch=self.check_batch_loop.isChecked(),
            batch_cooldown=self.spin_batch_cd.value(),
            dpr=self.dpr,
            parent=self
        )
        self.batch_worker.log_signal.connect(self._append_log)
        self.batch_worker.status_signal.connect(self._update_status)
        self.batch_worker.preview_signal.connect(self._display_preview_image)
        self.batch_worker.step_started_signal.connect(self._on_batch_step_highlight)
        self.batch_worker.stopped_signal.connect(self._on_batch_worker_stopped)
        self.batch_worker.start()

    def _stop_batch_monitoring(self):
        if self.batch_worker:
            self.lbl_status.setText("狀態: 批次正在終止...")
            self.batch_worker.stop()

    @Slot(int)
    def _on_batch_step_highlight(self, step_idx: int):
        """執行時高亮當前步驟列"""
        if 0 <= step_idx < self.table_steps.rowCount():
            self.table_steps.selectRow(step_idx)

    @Slot()
    def _on_batch_worker_stopped(self):
        self.btn_batch_toggle.setText("▶ 開始執行批次工作流 (快捷鍵: F8)")
        self.btn_batch_toggle.setStyleSheet(
            "font-size: 15px; font-weight: bold; padding: 10px; "
            "background-color: #198754; color: white; border-radius: 6px;"
        )
        self.lbl_status.setText("狀態: 批次已停止")
        self._append_log("⏹ 批次流程已停止", "info")

    # -------------------------------------------------------------
    # 資料載入與儲存
    # -------------------------------------------------------------
    def _load_config_to_ui(self):
        # 單一模式
        self.spin_roi_x.setValue(self.config.roi_x)
        self.spin_roi_y.setValue(self.config.roi_y)
        self.spin_roi_w.setValue(self.config.roi_w)
        self.spin_roi_h.setValue(self.config.roi_h)

        self.edit_keywords.setText(", ".join(self.config.keywords))
        self.combo_match_mode.setCurrentIndex(0 if self.config.match_mode == "contains" else 1)
        self.spin_confidence.setValue(self.config.confidence_threshold)

        self.combo_mouse_action.setCurrentIndex(0 if self.config.mouse_action == "single_click" else 1)
        if self.config.loop_mode:
            self.radio_loop.setChecked(True)
        else:
            self.radio_single.setChecked(True)

        self.spin_cooldown.setValue(self.config.cooldown_seconds)
        self.spin_interval.setValue(self.config.scan_interval)
        self.spin_offset_x.setValue(self.config.click_offset_x)
        self.spin_offset_y.setValue(self.config.click_offset_y)
        self.check_restore_cursor.setChecked(self.config.restore_cursor)

        # 批次模式
        self.check_batch_loop.setChecked(self.config.batch_loop)
        self.spin_batch_cd.setValue(self.config.batch_cooldown)
        self._update_batch_table()

    def _save_ui_to_config(self):
        self.config.roi_x = self.spin_roi_x.value()
        self.config.roi_y = self.spin_roi_y.value()
        self.config.roi_w = self.spin_roi_w.value()
        self.config.roi_h = self.spin_roi_h.value()
        self.config.roi_configured = True

        raw_keywords = self.edit_keywords.text()
        self.config.keywords = [k.strip() for k in raw_keywords.replace("，", ",").split(",") if k.strip()]
        self.config.match_mode = "contains" if self.combo_match_mode.currentIndex() == 0 else "exact"
        self.config.confidence_threshold = self.spin_confidence.value()

        self.config.mouse_action = "single_click" if self.combo_mouse_action.currentIndex() == 0 else "double_click"
        self.config.loop_mode = self.radio_loop.isChecked()
        self.config.cooldown_seconds = self.spin_cooldown.value()
        self.config.scan_interval = self.spin_interval.value()
        self.config.click_offset_x = self.spin_offset_x.value()
        self.config.click_offset_y = self.spin_offset_y.value()
        self.config.restore_cursor = self.check_restore_cursor.isChecked()

        self.config.batch_loop = self.check_batch_loop.isChecked()
        self.config.batch_cooldown = self.spin_batch_cd.value()

        self.config.save()

    @Slot(str, str)
    def _append_log(self, text: str, level: str = "info"):
        t = time.strftime("%H:%M:%S")
        color_map = {
            "info": "#212529",
            "success": "#198754",
            "warning": "#fd7e14",
            "error": "#dc3545"
        }
        color = color_map.get(level, "#212529")
        html = f"<div style='color:{color};'>[{t}] {text}</div>"
        self.log_view.append(html)
        self.log_view.moveCursor(self.log_view.textCursor().MoveOperation.End)

    @Slot(str)
    def _update_status(self, status: str):
        self.lbl_status.setText(f"狀態: {status}")

    def closeEvent(self, event):
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if self.single_worker and self.single_worker.isRunning():
            self.single_worker.stop()
            self.single_worker.wait(500)
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.stop()
            self.batch_worker.wait(500)
        self._save_ui_to_config()
        super().closeEvent(event)
