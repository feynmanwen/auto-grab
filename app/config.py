import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


@dataclass
class BatchStep:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "步驟"
    roi_x: int = 100
    roi_y: int = 100
    roi_w: int = 200
    roi_h: int = 80
    keywords: List[str] = field(default_factory=lambda: ["確定"])
    match_mode: str = "contains"  # "contains" 或 "exact"
    confidence_threshold: float = 0.6
    mouse_action: str = "single_click"  # "single_click" 或 "double_click"
    click_offset_x: int = 0
    click_offset_y: int = 0
    post_delay: float = 1.0        # 成功點擊後等待秒數再執行下一步
    timeout_seconds: float = 30.0  # 超時上限(秒)，0 為無上限

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchStep":
        valid_keys = set(cls.__annotations__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class AppConfig:
    # --- 單一模式 ROI 設定 ---
    roi_x: int = 0
    roi_y: int = 0
    roi_w: int = 600
    roi_h: int = 400
    roi_configured: bool = False

    # OCR 關鍵字與匹配
    keywords: List[str] = field(default_factory=lambda: ["確定"])
    match_mode: str = "contains"  # "contains" 或 "exact"
    confidence_threshold: float = 0.6

    # 滑鼠行為
    mouse_action: str = "single_click"  # "single_click" 或 "double_click"
    click_offset_x: int = 0
    click_offset_y: int = 0
    restore_cursor: bool = False  # 點擊後是否復位滑鼠
    move_duration: float = 0.1    # 滑鼠平滑移動秒數 (0 代表瞬間)

    # 執行模式 (單一)
    loop_mode: bool = True        # 預設為循環監控
    cooldown_seconds: float = 3.0 # 命中點擊後的冷卻時間(秒)
    scan_interval: float = 1.0    # 每次掃描間隔(秒)

    # --- 批次模式 (Batch Mode) 設定 ---
    batch_steps: List[BatchStep] = field(default_factory=list)
    batch_loop: bool = False      # 整批完成後是否循環重跑
    batch_cooldown: float = 2.0   # 整批循環重跑間隔(秒)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["batch_steps"] = [s.to_dict() if isinstance(s, BatchStep) else s for s in self.batch_steps]
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        valid_keys = set(cls.__annotations__.keys())
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        if "batch_steps" in filtered_data:
            steps_data = filtered_data["batch_steps"]
            filtered_data["batch_steps"] = [
                BatchStep.from_dict(s) if isinstance(s, dict) else s for s in steps_data
            ]
        return cls(**filtered_data)

    def save(self, filepath: str = CONFIG_FILE_PATH) -> None:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save config: {e}")

    @classmethod
    def load(cls, filepath: str = CONFIG_FILE_PATH) -> "AppConfig":
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls.from_dict(data)
            except Exception as e:
                print(f"Failed to load config, using defaults: {e}")
        return cls()
