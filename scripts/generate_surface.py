#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "printables" / "two-zone-surface.png"
WIDTH, HEIGHT = 3508, 2480  # A4 landscape at 300 DPI


def font(size: int):
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#f5f2ea")
    draw = ImageDraw.Draw(image)
    margin = 180
    gap = 100
    top = 420
    bottom = HEIGHT - 210
    middle = WIDTH // 2
    zones = [
        ((margin, top, middle - gap // 2, bottom), "ONE", "#0797a7"),
        ((middle + gap // 2, top, WIDTH - margin, bottom), "TWO", "#dc3b32"),
    ]

    draw.text((margin, 90), "SURFACE OS", fill="#11181d", font=font(150))
    draw.text(
        (margin, 275),
        "Place one hand or object in a zone. Press CONFIRM to activate.",
        fill="#4d5a61",
        font=font(48),
    )

    for bounds, label, color in zones:
        draw.rounded_rectangle(bounds, radius=70, outline=color, width=22)
        label_font = font(210)
        box = draw.textbbox((0, 0), label, font=label_font)
        text_width = box[2] - box[0]
        text_height = box[3] - box[1]
        x0, y0, x1, y1 = bounds
        draw.text(
            ((x0 + x1 - text_width) / 2, (y0 + y1 - text_height) / 2 - 45),
            label,
            fill=color,
            font=label_font,
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, dpi=(300, 300))
    print(OUTPUT)


if __name__ == "__main__":
    main()
