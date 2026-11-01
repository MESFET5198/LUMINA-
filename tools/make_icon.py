#!/usr/bin/env python3
"""Generate ``assets/icon.png``: 256×256 静态 PNG，无 EXIF/ICC/文本块。

注册表要求图标是静态 PNG、≤2 MiB、≤1024×1024、无元数据，这里直接生成以
保证每次构建字节稳定（同样的 Pillow 版本下）。
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SIZE = 256


def main() -> int:
    img = Image.new("RGB", (SIZE, SIZE), (24, 25, 28))
    draw = ImageDraw.Draw(img)

    # 背景：从深到浅的径向渐变，模拟“高度图”的明暗关系
    for r in range(SIZE // 2, 0, -1):
        t = r / (SIZE / 2)
        shade = int(24 + (58 - 24) * (1 - t))
        draw.ellipse(
            [SIZE // 2 - r, SIZE // 2 - r, SIZE // 2 + r, SIZE // 2 + r],
            fill=(shade, shade, shade + 3),
        )

    # 浮雕环：一圈圈等高线，越靠中心越亮（= 越高）
    steps = 7
    for i in range(steps, 0, -1):
        radius = int(SIZE * 0.42 * i / steps)
        lum = int(90 + 150 * (1 - i / steps))
        color = (lum, int(lum * 0.92), int(lum * 0.72))
        draw.ellipse(
            [SIZE // 2 - radius, SIZE // 2 - radius, SIZE // 2 + radius, SIZE // 2 + radius],
            outline=color,
            width=max(2, SIZE // 64),
        )

    # 中心高光 + 一道“山脊”折线，读作地形
    draw.ellipse([SIZE // 2 - 16, SIZE // 2 - 16, SIZE // 2 + 16, SIZE // 2 + 16], fill=(246, 232, 198))
    ridge = []
    for x in range(28, SIZE - 28, 4):
        y = SIZE // 2 + int(46 * math.sin((x - SIZE / 2) / 26.0) * math.exp(-abs(x - SIZE / 2) / 220.0))
        ridge.append((x, y))
    draw.line(ridge, fill=(78, 161, 255), width=3, joint="curve")

    out = ROOT / "assets" / "icon.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    # pnginfo 不传 → 不写任何文本块；Pillow 也不会自动写 EXIF/ICC
    img.save(out, format="PNG", optimize=True)
    print(f"[ok] {out} · {out.stat().st_size} 字节 · {SIZE}x{SIZE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
