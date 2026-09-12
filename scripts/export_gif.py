"""
Extract keyframes from docs/demo.mp4 and generate an optimized docs/demo.gif.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import cv2
from PIL import Image

def main():
    mp4_path = "docs/demo.mp4"
    gif_path = "docs/demo.gif"
    
    if not os.path.exists(mp4_path):
        print(f"Error: {mp4_path} does not exist!")
        return

    print("Extracting frames from demo.mp4 to generate demo.gif...")
    cap = cv2.VideoCapture(mp4_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # 每 4 幀取 1 幀 (約 7.5 FPS), 寬度縮至 800x450
    step = 4
    frames = []
    idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(rgb).resize((800, 450), Image.Resampling.LANCZOS)
            # 使用自適應調色盤減少體積
            im_pal = im.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
            frames.append(im_pal)
        idx += 1

    cap.release()
    print(f"Collected {len(frames)} frames. Writing {gif_path}...")
    
    if frames:
        # 7.5 fps -> duration 133ms
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=133,
            loop=0,
            optimize=True
        )
        print(f"Successfully generated {gif_path} (Size: {os.path.getsize(gif_path):,} bytes)")

if __name__ == "__main__":
    main()
