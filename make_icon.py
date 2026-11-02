# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico（无外部依赖，纯 PIL 画一个'汽'字方块）。"""
from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("需要 Pillow：pip install pillow")


def make_icon(out: Path, size: int = 256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 圆角渐变底
    for y in range(size):
        t = y / size
        r = int(0x3E + (0x1A - 0x3E) * t)
        g = int(0xA6 + (0x7C - 0xA6) * t)
        b = int(0xFF + (0xE0 - 0xFF) * t)
        d.line([(0, y), (size, y)], fill=(r, g, b, 255))
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
    img.putalpha(mask)

    # 中间 '汽' 字
    text = "汽"
    font = None
    for fp in ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if Path(fp).is_file():
            try:
                font = ImageFont.truetype(fp, int(size * 0.6))
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
    d2 = ImageDraw.Draw(img)
    bbox = d2.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d2.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text,
            font=font, fill=(255, 255, 255, 255))

    img.save(out, format="ICO",
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("生成图标:", out)


if __name__ == "__main__":
    assets = Path(__file__).resolve().parent / "assets"
    assets.mkdir(exist_ok=True)
    make_icon(assets / "icon.ico")
