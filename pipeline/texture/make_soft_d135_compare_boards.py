#!/usr/bin/env python3
"""Build Layer A black-bg honest compare boards for soft-d135 ROI experiment."""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_roi"


def to_black(rgba_or_rgb: Image.Image) -> Image.Image:
    im = rgba_or_rgb.convert("RGBA")
    bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
    return Image.alpha_composite(bg, im).convert("RGB")


def side_by_side(before: Path, after: Path, title: str, out: Path):
    b = to_black(Image.open(before))
    a = to_black(Image.open(after))
    # normalize size
    h = max(b.height, a.height)
    w = b.width + a.width + 30
    canvas = Image.new("RGB", (w, h + 40), (0, 0, 0))
    canvas.paste(b, (10, 30))
    canvas.paste(a, (b.width + 20, 30))
    dr = ImageDraw.Draw(canvas)
    dr.text((10, 8), f"{title} | LEFT=baseline RIGHT=soft", fill=(220, 220, 230))
    canvas.save(out)


def main():
    base = OUT / "baseline"
    for tag in ("x035", "x015"):
        dest = OUT / tag
        if not (dest / "m2_2_d090_layer_a_4x_crop.png").is_file():
            print("skip missing", tag)
            continue
        side_by_side(
            base / "m2_2_d090_layer_a_4x_crop.png",
            dest / "m2_2_d090_layer_a_4x_crop.png",
            f"d090 LayerA 4x black ({tag})",
            dest / "compare_d090_4x_black.png",
        )
        side_by_side(
            base / "m2_2_d045_layer_a_4x_crop.png",
            dest / "m2_2_d045_layer_a_4x_crop.png",
            f"d045 LayerA 4x black ({tag})",
            dest / "compare_d045_4x_black.png",
        )
        # combined sheet
        c90 = Image.open(dest / "compare_d090_4x_black.png")
        c45 = Image.open(dest / "compare_d045_4x_black.png")
        sheet = Image.new("RGB", (max(c90.width, c45.width), c90.height + c45.height + 10), (0, 0, 0))
        sheet.paste(c90, (0, 0))
        sheet.paste(c45, (0, c90.height + 10))
        sheet.save(dest / "compare_layer_a_d090_d045_4x_black.png")
        print("wrote boards", tag)


if __name__ == "__main__":
    main()
