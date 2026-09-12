"""
Batch Step Configuration Dialog
"""
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPushButton,
    QGroupBox, QMessageBox
)

from app.config import BatchStep
from app.ui.roi_selector import ROISelectorOverlay


class BatchStepDialog(QDialog):
    def __init__(self, step: Optional[BatchStep] = None, step_index: int = 1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定批次步驟" if step else "新增批次步驟")
        self.resize(520, 560)

        self.step = step or BatchStep(
            name=f"步驟 {step_index}",
            roi_x=100,
            roi_y=100,
            roi_w=300,
            roi_h=150,
            keywords=["確定"],
            mouse_action="single_click",
            post_delay=1.0,
            timeout_seconds=30.0
        )

        self._init_ui()
        self._load_from_step()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. 步驟基本資訊
        info_group = QGroupBox("📌 步驟基本資訊")
        info_layout = QGridLayout(info_group)
        info_layout.addWidget(QLabel("步驟名稱:"), 0, 0)
        self.edit_name = QLineEdit()
        info_layout.addWidget(self.edit_name, 0, 1)
        layout.addWidget(info_group)

        # 2. ROI 範圍設定
        roi_group = QGroupBox("📍 專屬螢幕區域 (ROI)")
        roi_layout = QVBoxLayout(roi_group)
        self.btn_select_roi = QPushButton("📐 立即框選螢幕區域 (隱藏本視窗供您拖曳)")
        self.btn_select_roi.setStyleSheet("font-weight: bold; padding: 8px; background-color: #0d6efd; color: white; border-radius: 4px;")
        self.btn_select_roi.clicked.connect(self._start_roi_selection)
        roi_layout.addWidget(self.btn_select_roi)

        coord_grid = QGridLayout()
        coord_grid.addWidget(QLabel("X:"), 0, 0)
        self.spin_x = QSpinBox()
        self.spin_x.setRange(-9999, 99999)
        coord_grid.addWidget(self.spin_x, 0, 1)

        coord_grid.addWidget(QLabel("Y:"), 0, 2)
        self.spin_y = QSpinBox()
        self.spin_y.setRange(-9999, 99999)
        coord_grid.addWidget(self.spin_y, 0, 3)

        coord_grid.addWidget(QLabel("寬 (W):"), 1, 0)
        self.spin_w = QSpinBox()
        self.spin_w.setRange(10, 99999)
        coord_grid.addWidget(self.spin_w, 1, 1)

        coord_grid.addWidget(QLabel("高 (H):"), 1, 2)
        self.spin_h = QSpinBox()
        self.spin_h.setRange(10, 99999)
        coord_grid.addWidget(self.spin_h, 1, 3)
        roi_layout.addLayout(coord_grid)
        layout.addWidget(roi_group)

        # 3. OCR 目標辨識
        ocr_group = QGroupBox("🔍 文字目標辨識")
        ocr_layout = QGridLayout(ocr_group)
        ocr_layout.addWidget(QLabel("目標關鍵字:"), 0, 0)
        self.edit_keywords = QLineEdit()
        self.edit_keywords.setPlaceholderText("多關鍵字以逗號分隔，例如: 確定, 送出")
        ocr_layout.addWidget(self.edit_keywords, 0, 1)

        ocr_layout.addWidget(QLabel("匹配模式:"), 1, 0)
        self.combo_match = QComboBox()
        self.combo_match.addItems(["包含關鍵字 (模糊比對)", "完全一致 (精確比對)"])
        ocr_layout.addWidget(self.combo_match, 1, 1)

        ocr_layout.addWidget(QLabel("信心度門檻:"), 2, 0)
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.1, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(0.60)
        ocr_layout.addWidget(self.spin_conf, 2, 1)
        layout.addWidget(ocr_group)

        # 4. 滑鼠動作與排程時間
        action_group = QGroupBox("🖱️ 動作與流程時間控制")
        action_layout = QGridLayout(action_group)
        action_layout.addWidget(QLabel("滑鼠動作:"), 0, 0)
        self.combo_action = QComboBox()
        self.combo_action.addItems(["左鍵單擊 (Single Click)", "左鍵雙擊 (Double Click)"])
        action_layout.addWidget(self.combo_action, 0, 1)

        offset_box = QHBoxLayout()
        self.spin_off_x = QSpinBox()
        self.spin_off_x.setRange(-500, 500)
        self.spin_off_y = QSpinBox()
        self.spin_off_y.setRange(-500, 500)
        offset_box.addWidget(QLabel("X:"))
        offset_box.addWidget(self.spin_off_x)
        offset_box.addWidget(QLabel("Y:"))
        offset_box.addWidget(self.spin_off_y)
        action_layout.addWidget(QLabel("點擊座標微調:"), 1, 0)
        action_layout.addLayout(offset_box, 1, 1)

        action_layout.addWidget(QLabel("點擊後等待延遲 (秒):"), 2, 0)
        self.spin_post_delay = QDoubleSpinBox()
        self.spin_post_delay.setRange(0.0, 300.0)
        self.spin_post_delay.setSingleStep(0.5)
        self.spin_post_delay.setValue(1.0)
        action_layout.addWidget(self.spin_post_delay, 2, 1)

        action_layout.addWidget(QLabel("等待超時上限 (秒):"), 3, 0)
        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(0.0, 3600.0)
        self.spin_timeout.setSingleStep(5.0)
        self.spin_timeout.setValue(30.0)
        self.spin_timeout.setSpecialValueText("無限制 (0)")
        action_layout.addWidget(self.spin_timeout, 3, 1)
        layout.addWidget(action_group)

        # 按鈕列
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("確認儲存")
        self.btn_save.setStyleSheet("padding: 6px 16px; font-weight: bold; background-color: #198754; color: white; border-radius: 4px;")
        self.btn_save.clicked.connect(self._save_and_accept)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def _load_from_step(self):
        self.edit_name.setText(self.step.name)
        self.spin_x.setValue(self.step.roi_x)
        self.spin_y.setValue(self.step.roi_y)
        self.spin_w.setValue(self.step.roi_w)
        self.spin_h.setValue(self.step.roi_h)
        self.edit_keywords.setText(", ".join(self.step.keywords))
        self.combo_match.setCurrentIndex(0 if self.step.match_mode == "contains" else 1)
        self.spin_conf.setValue(self.step.confidence_threshold)
        self.combo_action.setCurrentIndex(0 if self.step.mouse_action == "single_click" else 1)
        self.spin_off_x.setValue(self.step.click_offset_x)
        self.spin_off_y.setValue(self.step.click_offset_y)
        self.spin_post_delay.setValue(self.step.post_delay)
        self.spin_timeout.setValue(self.step.timeout_seconds)

    def _start_roi_selection(self):
        """
        透過將視窗透明度暫時設為 0.0，使背景畫面完整露出，
        並以模態方式啟動全螢幕框選對話框，不受父層模態阻擋。
        """
        self.setWindowOpacity(0.0)
        overlay = ROISelectorOverlay(self)
        if overlay.exec() == QDialog.DialogCode.Accepted:
            x, y, w, h = overlay.get_roi()
            self.spin_x.setValue(x)
            self.spin_y.setValue(y)
            self.spin_w.setValue(w)
            self.spin_h.setValue(h)
        self.setWindowOpacity(1.0)
        self.raise_()
        self.activateWindow()

    def _save_and_accept(self):
        raw_kw = self.edit_keywords.text()
        kws = [k.strip() for k in raw_kw.replace("，", ",").split(",") if k.strip()]
        if not kws:
            QMessageBox.warning(self, "資料不完整", "請至少填寫一個目標關鍵字！")
            return
        if self.spin_w.value() <= 0 or self.spin_h.value() <= 0:
            QMessageBox.warning(self, "資料不完整", "ROI 寬度與高度必須大於 0！")
            return

        self.step.name = self.edit_name.text().strip() or "未命名步驟"
        self.step.roi_x = self.spin_x.value()
        self.step.roi_y = self.spin_y.value()
        self.step.roi_w = self.spin_w.value()
        self.step.roi_h = self.spin_h.value()
        self.step.keywords = kws
        self.step.match_mode = "contains" if self.combo_match.currentIndex() == 0 else "exact"
        self.step.confidence_threshold = self.spin_conf.value()
        self.step.mouse_action = "single_click" if self.combo_action.currentIndex() == 0 else "double_click"
        self.step.click_offset_x = self.spin_off_x.value()
        self.step.click_offset_y = self.spin_off_y.value()
        self.step.post_delay = self.spin_post_delay.value()
        self.step.timeout_seconds = self.spin_timeout.value()

        self.accept()

    def get_step(self) -> BatchStep:
        return self.step
