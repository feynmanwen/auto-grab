"""
Script to automatically generate the full-HD demo video (demo.mp4)
and optimized animated GIF (demo.gif) for auto-grab.
"""
import os
import sys
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 30

FONT_PATH_BOLD = "C:/Windows/Fonts/msjhbd.ttc"
FONT_PATH_REG = "C:/Windows/Fonts/msjh.ttc"
FONT_PATH_EN_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_PATH_EN = "C:/Windows/Fonts/segoeui.ttf"

def get_font(size: int, bold: bool = False, en_only: bool = False) -> ImageFont.FreeTypeFont:
    if en_only:
        p = FONT_PATH_EN_BOLD if bold else FONT_PATH_EN
    else:
        p = FONT_PATH_BOLD if bold else FONT_PATH_REG
    if not os.path.exists(p):
        p = "C:/Windows/Fonts/arial.ttf"
    return ImageFont.truetype(p, size)

def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - math.pow(-2 * t + 2, 3) / 2

def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - math.pow(1 - t, 3)

def create_background() -> Image.Image:
    """建立科技暗色系背景附帶微細網格"""
    bg = Image.new("RGB", (WIDTH, HEIGHT), color="#0c111a")
    draw = ImageDraw.Draw(bg)
    # 頂部微妙漸層
    for y in range(0, 200):
        alpha = int(25 * (1 - y / 200))
        draw.line([(0, y), (WIDTH, y)], fill=(16, 24, 40))
    # 科技微細網格線
    grid_size = 48
    for x in range(0, WIDTH, grid_size):
        draw.line([(x, 0), (x, HEIGHT)], fill=(18, 26, 42), width=1)
    for y in range(0, HEIGHT, grid_size):
        draw.line([(0, y), (WIDTH, y)], fill=(18, 26, 42), width=1)
    return bg

def draw_header_banner(img: Image.Image, step_num: str, title: str, subtitle: str):
    """繪製頂部指示標題列"""
    draw = ImageDraw.Draw(img)
    # 陰影底板
    draw.rounded_rectangle([40, 24, WIDTH - 40, 100], radius=14, fill="#111928", outline="#1f2a3d", width=2)
    # 步驟徽章
    draw.rounded_rectangle([58, 38, 200, 86], radius=8, fill="#059669", outline="#10b981", width=1)
    f_badge = get_font(18, bold=True)
    draw.text((72, 48), step_num, fill="#ffffff", font=f_badge)
    # 主標題
    f_title = get_font(24, bold=True)
    draw.text((220, 38), title, fill="#ffffff", font=f_title)
    # 副標題
    f_sub = get_font(16, bold=False)
    draw.text((224, 70), subtitle, fill="#94a3b8", font=f_sub)

    # 右側品牌小徽章
    draw.rounded_rectangle([WIDTH - 250, 42, WIDTH - 58, 82], radius=8, fill="#1e293b", outline="#334155", width=1)
    f_brand = get_font(15, bold=True, en_only=True)
    draw.text((WIDTH - 232, 52), "auto-grab v1.2", fill="#38bdf8", font=f_brand)

def draw_cursor(img: Image.Image, x: int, y: int, click_progress: float = 0.0):
    """繪製 Windows 游標箭頭與點擊波紋"""
    draw = ImageDraw.Draw(img)
    x = int(round(x))
    y = int(round(y))

    # 點擊波紋 (Expanding Ripple)
    if click_progress > 0:
        r = int(click_progress * 38)
        alpha = int(255 * (1.0 - click_progress))
        color = f"#{38:02x}{189:02x}{248:02x}"
        draw.ellipse([x - r, y - r, x + r, y + r], outline=color, width=3)
        r2 = int(click_progress * 22)
        draw.ellipse([x - r2, y - r2, x + r2, y + r2], outline="#10b981", width=2)

    # 游標箭頭多邊形 (相對於 (x, y))
    pts = [
        (x, y),
        (x, y + 22),
        (x + 5, y + 17),
        (x + 10, y + 26),
        (x + 14, y + 24),
        (x + 9, y + 15),
        (x + 16, y + 15)
    ]
    # 黑色陰影外輪廓
    shadow_pts = [(p[0] + 2, p[1] + 2) for p in pts]
    draw.polygon(shadow_pts, fill="#000000")
    # 白色游標主體
    draw.polygon(pts, fill="#ffffff", outline="#000000")

def load_ui_frames() -> dict:
    """載入先前擷取的真實 UI 截圖並做等比縮放"""
    frames = {}
    base_dir = "scratch/ui_frames"
    names = {
        "initial": "01_initial.png",
        "configured": "02_configured.png",
        "active": "03_hit_success.png",
        "batch": "04_batch_tab.png",
        "dialog": "05_batch_dialog.png"
    }
    # 主視窗預設目標顯示寬度 1400 (在 1920 畫布上居中)
    target_w = 1420
    for key, fname in names.items():
        p = os.path.join(base_dir, fname)
        if os.path.exists(p):
            im = Image.open(p).convert("RGBA")
            ratio = target_w / im.width
            target_h = int(im.height * ratio)
            frames[key] = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
        else:
            print(f"Warning: {p} not found!")
    return frames

def render_window_with_shadow(canvas: Image.Image, win_img: Image.Image, x: int, y: int):
    """將視窗加上精美懸浮陰影繪製至畫布"""
    w, h = win_img.size
    # 柔和深色陰影
    shadow = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle([15, 15, w + 25, h + 25], radius=14, fill=(0, 0, 0, 160))
    canvas.paste(shadow, (x - 20, y - 15), shadow)
    # 主視窗
    canvas.paste(win_img, (x, y), win_img)

def generate_video():
    print("=" * 60)
    print("  Starting auto-grab Demo Video Generation (1080p)...")
    print("=" * 60)

    os.makedirs("docs", exist_ok=True)
    ui_frames = load_ui_frames()
    bg_template = create_background()

    out_mp4 = "docs/demo.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_mp4, fourcc, FPS, (WIDTH, HEIGHT))

    gif_frames = []

    total_frames = 840  # 28 秒
    win_x = (WIDTH - ui_frames["initial"].width) // 2
    win_y = 135

    print(f"Total video frames to render: {total_frames} ({total_frames / FPS:.1f}s)")

    for f_idx in range(total_frames):
        canvas = bg_template.copy()
        draw = ImageDraw.Draw(canvas)

        # -----------------------------------------------------------------
        # SCENE 1: 開場標題 (Frames 0 ~ 90, 0 ~ 3.0s)
        # -----------------------------------------------------------------
        if f_idx < 90:
            p = f_idx / 90.0
            # 漸入透明度
            alpha = int(255 * min(1.0, p * 2.5))
            
            # 中央發光卡片
            card_w, card_h = 1100, 520
            cx = (WIDTH - card_w) // 2
            cy = (HEIGHT - card_h) // 2
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=24, fill="#0f172a", outline="#10b981", width=3)
            
            # 瞄準準心大圖示
            icon_cx, icon_cy = WIDTH // 2, cy + 110
            draw.ellipse([icon_cx - 45, icon_cy - 45, icon_cx + 45, icon_cy + 45], outline="#10b981", width=4)
            draw.ellipse([icon_cx - 24, icon_cy - 24, icon_cx + 24, icon_cy + 24], outline="#38bdf8", width=3)
            draw.line([(icon_cx - 65, icon_cy), (icon_cx + 65, icon_cy)], fill="#10b981", width=3)
            draw.line([(icon_cx, icon_cy - 65), (icon_cx, icon_cy + 65)], fill="#10b981", width=3)
            draw.ellipse([icon_cx - 6, icon_cy - 6, icon_cx + 6, icon_cy + 6], fill="#f59e0b")

            # 主標題
            f_huge = get_font(52, bold=True, en_only=True)
            t1 = "auto-grab"
            draw.text((WIDTH // 2 - 145, cy + 185), t1, fill="#ffffff", font=f_huge)

            # 副標題
            f_sub = get_font(26, bold=True)
            t2 = "Screen OCR AutoClicker · 智慧文字辨識自動點選工具"
            draw.text((WIDTH // 2 - 325, cy + 265), t2, fill="#38bdf8", font=f_sub)

            # 說明文字
            f_desc = get_font(20, bold=False)
            t3 = "專為 Windows PC 設計 | 自由框選 · 離線 RapidOCR · 單一監控 · 批次工作流"
            draw.text((WIDTH // 2 - 365, cy + 325), t3, fill="#94a3b8", font=f_desc)

            # 特色標籤群
            tags = ["📍 自由螢幕 ROI 框選", "⚡ 批次多步驟自動化", "🎯 毫米級瞄準準心", "🛡️ F8 全域安全中斷"]
            tag_x = cx + 60
            f_tag = get_font(16, bold=True)
            for tag in tags:
                draw.rounded_rectangle([tag_x, cy + 410, tag_x + 225, cy + 460], radius=10, fill="#1e293b", outline="#334155", width=1)
                draw.text((tag_x + 20, cy + 424), tag, fill="#34d399", font=f_tag)
                tag_x += 245

        # -----------------------------------------------------------------
        # SCENE 2: 步驟 1 - 自由框選 ROI 區域 (Frames 90 ~ 290, 3.0 ~ 9.6s)
        # -----------------------------------------------------------------
        elif f_idx < 290:
            rel = f_idx - 90
            draw_header_banner(canvas, "步驟 1 / 4", "自由框選螢幕感興趣區域 (ROI Selection)", "點擊「重新框選 ROI」，在螢幕上按住滑鼠左鍵自由拉框鎖定目標")
            
            if rel < 60:
                # 初始未設定主視窗，游標移向「重新框選 ROI」按鈕
                render_window_with_shadow(canvas, ui_frames["initial"], win_x, win_y)
                # 游標軌跡
                t = ease_in_out(rel / 50.0)
                cur_x = win_x + 100 + t * 240
                cur_y = win_y + 120 + t * 45
                click_p = max(0.0, (rel - 50) / 10.0) if rel >= 50 else 0.0
                draw_cursor(canvas, cur_x, cur_y, click_p)

            elif rel < 200:
                # 進入「全螢幕半透明遮罩」模擬真實框選行為！
                # 模擬背景有一款應用程式視窗，內有按鈕「Submit / 確定送出」
                # 繪製模擬的目標視窗
                app_x, app_y, app_w, app_h = 450, 240, 1020, 650
                draw.rounded_rectangle([app_x, app_y, app_x + app_w, app_y + app_h], radius=16, fill="#1e293b", outline="#334155", width=2)
                # 標題列
                draw.rounded_rectangle([app_x, app_y, app_x + app_w, app_y + 45], radius=16, fill="#0f172a")
                draw.text((app_x + 24, app_y + 12), "業務審核管理系統 - 客戶訂單資料表", fill="#94a3b8", font=get_font(16, bold=True))
                # 模擬內容表單
                draw.text((app_x + 60, app_y + 100), "客戶姓名: 陳大明   |   合約編號: CT-20260912-88", fill="#cbd5e1", font=get_font(18))
                draw.text((app_x + 60, app_y + 150), "審核狀態: 待確認   |   金額總計: NT$ 128,000", fill="#cbd5e1", font=get_font(18))
                
                # 目標按鈕「立即送出審核 (Submit)」
                btn_bx, btn_by, btn_bw, btn_bh = 760, 520, 360, 90
                draw.rounded_rectangle([btn_bx, btn_by, btn_bx + btn_bw, btn_by + btn_bh], radius=12, fill="#059669", outline="#34d399", width=2)
                f_btn = get_font(24, bold=True)
                draw.text((btn_bx + 55, btn_by + 28), "立即送出審核 (Submit)", fill="#ffffff", font=f_btn)

                # 全螢幕深色半透明遮罩
                mask = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 125))
                mdraw = ImageDraw.Draw(mask)
                # 頂部提示條
                mdraw.rectangle([0, 0, WIDTH, 50], fill=(0, 0, 0, 200))
                f_tip = get_font(18, bold=True)
                mdraw.text((WIDTH // 2 - 250, 12), "【按住滑鼠左鍵並拖曳】框選區域  |  【ESC 鍵】取消框選", fill="#ffffff", font=f_tip)

                # 拖曳選取框動畫
                drag_rel = rel - 60
                drag_t = ease_in_out(min(1.0, drag_rel / 75.0))
                sel_x1 = btn_bx - 20
                sel_y1 = btn_by - 15
                sel_x2 = sel_x1 + int((btn_bw + 40) * drag_t)
                sel_y2 = sel_y1 + int((btn_bh + 30) * drag_t)

                # 挖空選取區讓底圖透出
                mdraw.rectangle([sel_x1, sel_y1, sel_x2, sel_y2], fill=(0, 0, 0, 0))
                # 疊合遮罩
                canvas.paste(mask, (0, 0), mask)

                # 繪製青綠色高亮外框與尺寸標籤
                draw.rectangle([sel_x1, sel_y1, sel_x2, sel_y2], outline="#00e5ff", width=3)
                if drag_t > 0.3:
                    dim_w = sel_x2 - sel_x1
                    dim_h = sel_y2 - sel_y1
                    draw.text((sel_x1 + 6, sel_y2 + 8), f"{dim_w} x {dim_h} px", fill="#00e5ff", font=get_font(15, bold=True))

                cur_x = sel_x2
                cur_y = sel_y2
                draw_cursor(canvas, cur_x, cur_y)

            else:
                # 框選完成，主視窗復原且座標已自動帶入！右側顯示帶有準心的按鈕預覽
                render_window_with_shadow(canvas, ui_frames["configured"], win_x, win_y)
                # 游標移至預覽區觀察
                cur_x = win_x + 950
                cur_y = win_y + 320
                draw_cursor(canvas, cur_x, cur_y)

        # -----------------------------------------------------------------
        # SCENE 3: 步驟 2 - 輸入關鍵字與啟動監控 (Frames 290 ~ 470, 9.6 ~ 15.6s)
        # -----------------------------------------------------------------
        elif f_idx < 470:
            rel = f_idx - 290
            draw_header_banner(canvas, "步驟 2 / 4", "設定目標文字與點擊策略 (Keywords & Settings)", "輸入目標關鍵字，支援繁簡中英文包含或精確比對，右側即時瞄準預覽")
            
            render_window_with_shadow(canvas, ui_frames["configured"], win_x, win_y)

            if rel < 90:
                # 游標移至關鍵字輸入框並模擬焦點
                t = ease_in_out(rel / 80.0)
                cur_x = win_x + 180 + t * 80
                cur_y = win_y + 245
                draw_cursor(canvas, cur_x, cur_y)
            else:
                # 游標移至「啟動文字偵測監控」按鈕並點擊！
                t = ease_in_out((rel - 90) / 70.0)
                btn_start_x = win_x + 220
                btn_start_y = win_y + 640
                cur_x = (win_x + 260) * (1 - t) + btn_start_x * t
                cur_y = (win_y + 245) * (1 - t) + btn_start_y * t
                click_p = max(0.0, (rel - 160) / 10.0) if rel >= 160 else 0.0
                draw_cursor(canvas, cur_x, cur_y, click_p)

        # -----------------------------------------------------------------
        # SCENE 4: 步驟 3 - RapidOCR 命中與精確自動點選 (Frames 470 ~ 650, 15.6 ~ 21.6s)
        # -----------------------------------------------------------------
        elif f_idx < 650:
            rel = f_idx - 470
            draw_header_banner(canvas, "步驟 3 / 4", "RapidOCR 即時秒級辨識與精準自動點選 (Auto Click)", "目標文字出現瞬間，引擎以 26ms 高速定位座標並自動平滑移至中心點擊")

            # 顯示監控中與命中日誌狀態的主視窗
            render_window_with_shadow(canvas, ui_frames["active"], win_x, win_y)

            # 在右側或浮動區展示「真實螢幕上的目標被偵測鎖定與滑鼠飛入點擊」
            demo_box_x = win_x + 920
            demo_box_y = win_y + 210
            
            if rel >= 30:
                # 繪製 OCR 命中鎖定標籤
                draw.rounded_rectangle([demo_box_x - 10, demo_box_y - 40, demo_box_x + 240, demo_box_y - 5], radius=6, fill="#dc2626")
                draw.text((demo_box_x, demo_box_y - 32), "🎯 命中: Submit (0.98 | 26ms)", fill="#ffffff", font=get_font(14, bold=True))

                # 滑鼠游標從主視窗左側平滑移動到點擊準心處
                move_t = ease_out(min(1.0, (rel - 40) / 45.0)) if rel >= 40 else 0.0
                cur_x = (win_x + 300) * (1 - move_t) + (demo_box_x + 90) * move_t
                cur_y = (win_y + 600) * (1 - move_t) + (demo_box_y + 50) * move_t

                # 點擊波紋
                click_p = max(0.0, (rel - 85) / 12.0) if 85 <= rel <= 97 else 0.0
                draw_cursor(canvas, cur_x, cur_y, click_p)

                # 點擊成功徽章
                if rel >= 90:
                    draw.rounded_rectangle([win_x + 700, win_y + 620, win_x + 980, win_y + 675], radius=10, fill="#059669", outline="#34d399", width=2)
                    draw.text((win_x + 720, win_y + 636), "✅ 自動點擊成功 (冷卻 3.0s)", fill="#ffffff", font=get_font(18, bold=True))
            else:
                draw_cursor(canvas, win_x + 300, win_y + 600)

        # -----------------------------------------------------------------
        # SCENE 5: 步驟 4 - 批次多步驟自動化工作流 (Frames 650 ~ 750, 21.6 ~ 25.0s)
        # -----------------------------------------------------------------
        elif f_idx < 750:
            rel = f_idx - 650
            draw_header_banner(canvas, "步驟 4 / 4", "批次多步驟自動化工作流 (Batch Workflow)", "依序自動執行：步驟 1 登入 -> 步驟 2 同意條款 -> 步驟 3 送出完成")

            # 顯示批次分頁主視窗
            render_window_with_shadow(canvas, ui_frames["batch"], win_x, win_y)

            # 浮動顯示批次新增對話框動畫
            if rel < 50:
                dlg_img = ui_frames["dialog"]
                dx = win_x + 280
                dy = win_y + 60
                canvas.paste(dlg_img, (dx, dy))
                draw.rectangle([dx, dy, dx + dlg_img.width, dy + dlg_img.height], outline="#38bdf8", width=2)
                # 游標移至確認儲存
                draw_cursor(canvas, dx + 420, dy + 520)
            else:
                # 步驟逐步推進高亮
                step_idx = min(3, (rel - 50) // 25 + 1)
                bar_x = win_x + 300
                bar_y = win_y + 640
                draw.rounded_rectangle([bar_x, bar_y, bar_x + 600, bar_y + 40], radius=10, fill="#1e293b", outline="#334155")
                fill_w = int(600 * (step_idx / 3.0))
                draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + 40], radius=10, fill="#10b981")
                draw.text((bar_x + 200, bar_y + 8), f"批次步驟推進中 ({step_idx}/3 完成)", fill="#ffffff", font=get_font(16, bold=True))
                draw_cursor(canvas, win_x + 500, win_y + 350)

        # -----------------------------------------------------------------
        # SCENE 6: 系統級安全機制與結尾 (Frames 750 ~ 840, 25.0 ~ 28.0s)
        # -----------------------------------------------------------------
        else:
            rel = f_idx - 750
            # 結尾資訊卡片
            card_w, card_h = 1200, 560
            cx = (WIDTH - card_w) // 2
            cy = (HEIGHT - card_h) // 2
            draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=24, fill="#0f172a", outline="#38bdf8", width=3)

            f_t = get_font(36, bold=True)
            draw.text((WIDTH // 2 - 280, cy + 50), "🛡️ 系統級雙重安全防護機制", fill="#ffffff", font=f_t)

            # 防護 1: F8 全域熱鍵
            f_box_w = 480
            draw.rounded_rectangle([cx + 70, cy + 130, cx + 70 + f_box_w, cy + 300], radius=16, fill="#1e293b", outline="#ef4444", width=2)
            # 鍵盤按鍵圖樣
            draw.rounded_rectangle([cx + 100, cy + 160, cx + 190, cy + 240], radius=10, fill="#374151", outline="#9ca3af", width=2)
            draw.text((cx + 122, cy + 182), "F8", fill="#ffffff", font=get_font(28, bold=True, en_only=True))
            draw.text((cx + 215, cy + 165), "全域緊急停止鍵", fill="#ef4444", font=get_font(22, bold=True))
            draw.text((cx + 215, cy + 205), "任何時候按下 F8，即刻中止點選！", fill="#cbd5e1", font=get_font(16))

            # 防護 2: 角落防呆
            draw.rounded_rectangle([cx + 630, cy + 130, cx + 630 + f_box_w, cy + 300], radius=16, fill="#1e293b", outline="#f59e0b", width=2)
            draw.text((cx + 670, cy + 165), "邊界角落防護 (Fail-Safe)", fill="#f59e0b", font=get_font(22, bold=True))
            draw.text((cx + 670, cy + 205), "將滑鼠游標猛甩至螢幕左上角 (0, 0)", fill="#cbd5e1", font=get_font(16))
            draw.text((cx + 670, cy + 235), "即可立即觸發 PyAutoGUI 安全中斷", fill="#94a3b8", font=get_font(15))

            # 下方 GitHub 連結與網站資訊
            draw.rounded_rectangle([cx + 70, cy + 340, cx + card_w - 70, cy + 490], radius=16, fill="#111827", outline="#10b981", width=2)
            draw.text((cx + 100, cy + 365), "🚀 立即體驗與下載：", fill="#ffffff", font=get_font(22, bold=True))
            draw.text((cx + 100, cy + 405), "GitHub 倉庫: https://github.com/feynmanwen/auto-grab", fill="#38bdf8", font=get_font(18, bold=True, en_only=True))
            draw.text((cx + 100, cy + 440), "線上看板: https://feynmanwen.github.io/auto-grab/", fill="#34d399", font=get_font(18, bold=True, en_only=True))

        # 轉成 OpenCV BGR 格式寫入影片
        frame_bgr = cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)
        writer.write(frame_bgr)

        # 同步收集 GIF 取樣幀 (每 3 幀取 1 幀，縮放為 800x450 以兼顧畫質與體積)
        if f_idx % 3 == 0:
            small_im = canvas.resize((800, 450), Image.Resampling.BILINEAR)
            gif_frames.append(small_im)

        if (f_idx + 1) % 150 == 0 or f_idx == total_frames - 1:
            print(f"Rendered {f_idx + 1} / {total_frames} frames ({((f_idx + 1) / total_frames) * 100:.1f}%)")

    writer.release()
    print(f"\n✅ MP4 Video saved to {out_mp4} (Size: {os.path.getsize(out_mp4):,} bytes)")

    # 匯出 GIF
    out_gif = "docs/demo.gif"
    print(f"Exporting animated GIF ({len(gif_frames)} frames)...")
    gif_frames[0].save(
        out_gif,
        save_all=True,
        append_images=gif_frames[1:],
        duration=100,  # 10 fps playback
        loop=0,
        optimize=True
    )
    print(f"✅ Animated GIF saved to {out_gif} (Size: {os.path.getsize(out_gif):,} bytes)")
    print("=" * 60)

if __name__ == "__main__":
    generate_video()
