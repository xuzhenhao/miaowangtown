#!/usr/bin/env python3
"""
Build the 3-panel direct close-up comparison `route_a_v4_comparison.png`:
  - Left Panel: Target Red-Box Reference Cat (Close-up 4x)
  - Middle Panel: Rejected Route A v3 (showing the 4 ghost paws, top vertical barcode, 3 legs, and painted orange dots)
  - Right Panel: Fixed Route A v4 (zero ghost paws, zero barcode, 4 clean legs, ringed tail, natural AI fur & Miemie markings)
"""
from pathlib import Path
import sys
from PIL import Image, ImageDraw

V1_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
V3_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v3_crisp")
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v4_clean")

sys.path.insert(0, str(V1_DIR))
from composite_comparison import load_font


def main():
    ref_full = Image.open(V1_DIR / "target_redbox_ref.png").convert("RGB")
    v3_full = Image.open(V3_DIR / "route_a_v3_in_town.png").convert("RGB")
    v4_full = Image.open(OUT_DIR / "route_a_v4_in_town.png").convert("RGB")

    # Exact same crop box (700, 440, 980, 672) -> 280x232 upscaled 3x (840x696) for each panel
    crop_box = (700, 440, 980, 672)
    pw, ph = 560, 464
    c_ref = ref_full.crop(crop_box).resize((pw, ph), Image.Resampling.NEAREST)
    c_v3 = v3_full.crop(crop_box).resize((pw, ph), Image.Resampling.NEAREST)
    c_v4 = v4_full.crop(crop_box).resize((pw, ph), Image.Resampling.NEAREST)

    pad = 20
    header_h = 86
    title_h = 52
    footer_h = 110
    board_w = pw * 3 + pad * 4
    board_h = header_h + title_h + ph + footer_h + pad * 3

    board = Image.new("RGB", (board_w, board_h), (22, 20, 18))
    draw = ImageDraw.Draw(board)

    font_h1 = load_font(28)
    font_h2 = load_font(20)
    font_sub = load_font(16)

    draw.text(
        (pad, 16),
        "喵汪小镇 · 路线 A v4 彻底修复特写直比（Target 红框原图 vs 被打回的 v3 问题图 vs 全新修复 v4）",
        fill=(245, 236, 220),
        font=font_h1,
    )
    draw.text(
        (pad, 52),
        "修复重点：① 彻底清除石板地4只原猫残爪鬼影与顶部台阶竖条拉伸  ② 移除一切Python硬画橙色圆点与14色迷彩量化  ③ 补齐4条腿与虎斑环尾",
        fill=(175, 230, 170),
        font=font_sub,
    )

    panels = [
        (0, "1. Target 红框目标猫（同视野特写基准）", (235, 115, 100), c_ref, [
            "• 理想基准：2×2 画布像素块，大绿眼高光通透",
            "• 自然柔和的虎斑毛流过渡与干净 1px 深褐描边",
            "• 四足白袜清晰站立于石板地，无杂乱伪影",
        ]),
        (1, "2. 刚被打回的 Route A v3（问题暴露特写）", (235, 165, 95), c_v3, [
            "✗ 脚下石板地残留 4 只原猫半透明白爪鬼影 + 顶部竖条拉伸",
            "✗ Python 脚本硬画的左脸颊/左腕亮橘色圆斑与生硬深棕八字胡",
            "✗ 14色强制量化导致迷彩碎斑、右后腿缺失(仅3腿)、尾巴死黑",
        ]),
        (2, "3. 全新修复 Route A v4（纯净 AI 原生像素 + 干净背景）", (120, 235, 140), c_v4, [
            "✓ 石板地与门廊台阶 100% 干净（零残爪鬼影、零竖条拉伸）",
            "✓ 零脚本涂鸦色块/零迷彩量化，保留 AI 原生细腻毛流与阴阳嘴套",
            "✓ 四条腿与四只白袜完整分明，尾巴环纹清晰，2×2 像素块锐利干净",
        ]),
    ]

    for idx, title, col_rgb, pim, bullets in panels:
        px = pad + idx * (pw + pad)
        py = header_h + pad
        draw.rectangle((px, py, px + pw, py + title_h), fill=(38, 34, 30), outline=col_rgb, width=2)
        draw.text((px + 12, py + 14), title, fill=col_rgb, font=font_h2)
        board.paste(pim, (px, py + title_h))
        draw.rectangle((px, py + title_h, px + pw, py + title_h + ph), outline=col_rgb, width=2)

        fy = py + title_h + ph + 8
        draw.rectangle((px, fy, px + pw, fy + footer_h - 8), fill=(32, 29, 26), outline=(80, 72, 64), width=1)
        for bi, btxt in enumerate(bullets):
            draw.text((px + 10, fy + 10 + bi * 28), btxt, fill=(230, 224, 212), font=font_sub)

    out_path = OUT_DIR / "route_a_v4_comparison.png"
    board.save(out_path, quality=95)
    print(f"[v4_cmp] Saved {out_path} ({board.size})")


if __name__ == "__main__":
    main()
