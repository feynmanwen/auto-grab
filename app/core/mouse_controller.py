"""
Mouse Controller module using PyAutoGUI
"""
import time
from typing import Tuple, Optional
import pyautogui

# 啟用安全機制：當滑鼠游標移至螢幕角落 (0, 0) 時自動觸發例外中止
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05  # 每次動作間極小緩衝


class MouseController:
    def __init__(self):
        pass

    @staticmethod
    def get_current_position() -> Tuple[int, int]:
        return pyautogui.position()

    @staticmethod
    def click_target(
        x: int,
        y: int,
        action: str = "single_click",  # "single_click" 或 "double_click"
        restore_cursor: bool = False,
        move_duration: float = 0.1
    ) -> bool:
        """
        將滑鼠移至指定座標 (x, y) 並執行單擊或雙擊。
        
        :param x: 螢幕物理 X 座標
        :param y: 螢幕物理 Y 座標
        :param action: "single_click" 或 "double_click"
        :param restore_cursor: 是否在點擊後復原滑鼠至原本位置
        :param move_duration: 移動耗時 (秒)，0 代表瞬間跳躍
        :return: 是否點擊成功
        """
        try:
            original_pos = pyautogui.position() if restore_cursor else None

            # 移動滑鼠至目標位置
            if move_duration > 0:
                pyautogui.moveTo(x, y, duration=move_duration)
            else:
                pyautogui.moveTo(x, y)

            # 執行點擊
            if action == "double_click":
                # 雙擊左鍵，間隔 0.15 秒
                pyautogui.doubleClick(x, y, interval=0.15, button="left")
            else:
                # 單擊左鍵
                pyautogui.click(x, y, button="left")

            # 若需要復原游標位置
            if restore_cursor and original_pos:
                time.sleep(0.05)
                pyautogui.moveTo(original_pos[0], original_pos[1], duration=0.05)

            return True
        except pyautogui.FailSafeException:
            print("PyAutoGUI FailSafe triggered by user!")
            raise
        except Exception as e:
            print(f"Error performing mouse click: {e}")
            return False
