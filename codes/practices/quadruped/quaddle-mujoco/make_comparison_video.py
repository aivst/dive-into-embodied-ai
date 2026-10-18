"""Show the preserved old recording and coordinated gait at equal playback speed."""
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent


def main():
    out = ROOT / "outputs"
    old = imageio.get_reader(out / "quaddle-previous.mp4")
    new = imageio.get_reader(out / "quaddle-coordinated.mp4")
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
    small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 17)
    with imageio.get_writer(out / "gait-before-after.mp4", fps=25, codec="libx264", quality=8) as writer:
        for i, (a, b) in enumerate(zip(old, new)):
            frame = Image.new("RGB", (1280, 560), (14,21,33))
            draw = ImageDraw.Draw(frame)
            draw.text((20,10), "BEFORE  |  2.97 Hz", font=font, fill=(240,190,120))
            draw.text((660,10), "AFTER  |  1.94 Hz", font=font, fill=(120,225,205))
            draw.text((20,45), "Front / rear amplitude: 10 / 48 deg", font=small, fill=(190,200,215))
            draw.text((660,45), "Front / rear amplitude: 23 / 28 deg", font=small, fill=(190,200,215))
            frame.paste(Image.fromarray(a).resize((640,480)), (0,80))
            frame.paste(Image.fromarray(b).resize((640,480)), (640,80))
            writer.append_data(np.asarray(frame))
            if i == 175:
                frame.save(out / "gait-before-after.webp", quality=85)
    old.close()
    new.close()
    print(out / "gait-before-after.mp4")


if __name__ == "__main__":
    main()
