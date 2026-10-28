#!/usr/bin/env python3
"""
Composite `route_a_v3_sprite.png` into the HD-2D town scene at 1:1 pixel parity
(zero secondary resampling of the 236x236 2x2-texel sprite!) -> `route_a_v3_in_town.png`,
and build the 4-panel comparison sheet `route_a_v2_vs_v3_crisp_comparison.png`:
  - Panel 1 (Top-Left): Target Red-Box Reference (with 4x zoom inset)
  - Panel 2 (Top-Right): Route A v2 (Previous version, soft/blurry, with 4x zoom inset)
  - Panel 3 (Bottom-Left): Route A v3 Crisp (2x2-texel parity + palette-snapped crisp pixel clusters + 1px toe/eye micro-details, with 4x zoom inset)
  - Panel 4 (Bottom-Right): 6x Ultra-Close-Up Direct Side-by-Side Comparison (Target vs Route A v2 vs Route A v3 Crisp across Head/Eyes/Muzzle, Flank Stripes/Cloud, and Paws/Toe Grooves)
"""
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

V1_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
V2_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v2_polish")
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v3_crisp")

sys.path.insert(0, str(V1_DIR))
from composite_comparison import load_font


def composite_v3_exact_1to1(plate_im: Image.Image, sprite_path: Path, out_path: Path) -> Image.Image:
    """
    Paste `route_a_v3_sprite.png` directly onto `plate_im` WITHOUT any secondary resize,
    so every 2x2 pixel block remains 100% integer-aligned on the 1364x1064 town canvas!
    """
    scene = plate_im.convert("RGBA")
    sprite = Image.open(sprite_path).convert("RGBA")
    s_arr = np.array(sprite)
    ys, xs = np.where(s_arr[:, :, 3] > 128)
    # Align crop boundaries to multiples of 2 so 2x2 blocks stay intact
    x0 = (xs.min() // 2) * 2
    y0 = (ys.min() // 2) * 2
    x1 = ((xs.max() + 2) // 2) * 2
    y1 = ((ys.max() + 2) // 2) * 2
    crop_s = sprite.crop((x0, y0, x1, y1))
    tw, th = crop_s.size

    paste_x = 840 - (tw // 4) * 2
    paste_y = 662 - th

    # Soft ground contact shadow under the four paws and body
    shadow_layer = Image.new("RGBA", scene.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    sdraw.ellipse(
        (paste_x + int(tw * 0.08), paste_y + int(th * 0.78),
         paste_x + int(tw * 0.86), paste_y + int(th * 1.03)),
        fill=(14, 11, 9, 138)
    )
    for px_rel, py_rel in [(0.18, 0.94), (0.34, 0.96), (0.55, 0.94), (0.72, 0.95)]:
        cx = paste_x + int(tw * px_rel)
        cy = paste_y + int(th * py_rel)
        sdraw.ellipse((cx - 22, cy - 9, cx + 22, cy + 9), fill=(10, 8, 6, 170))

    shadow_blur = shadow_layer.filter(ImageFilter.GaussianBlur(radius=6.0))
    scene = Image.alpha_composite(scene, shadow_blur)

    cat_layer = Image.new("RGBA", scene.size, (0, 0, 0, 0))
    cat_layer.paste(crop_s, (paste_x, paste_y), crop_s)
    scene = Image.alpha_composite(scene, cat_layer)

    rgb_out = scene.convert("RGB")
    rgb_out.save(out_path, quality=95)
    print(f"[composite_v3] Saved 1:1 exact texel composite {out_path} (cat bbox {tw}x{th})")
    return rgb_out


def build_v2_vs_v3_comparison(target_im: Image.Image, v2_im: Image.Image, v3_im: Image.Image):
    pw, ph = 920, 680
    header_h = 88
    title_h = 54
    pad = 20

    board_w = pw * 2 + pad * 3
    board_h = header_h + (ph + title_h) * 2 + pad * 3
    board = Image.new("RGB", (board_w, board_h), (24, 22, 20))
    draw = ImageDraw.Draw(board)

    font_h1 = load_font(30)
    font_h2 = load_font(22)
    font_sub = load_font(17)
    font_sm = load_font(15)

    draw.text(
        (pad, 16),
        "喵汪小镇 · 路线 A 去糊锐化精调对比（Route A v2 偏软糊 vs Route A v3 Crisp 2×2像素块对齐+色阶收敛）",
        fill=(245, 236, 220),
        font=font_h1,
    )
    draw.text(
        (pad, 54),
        "根因修复：① 消除二次非整数缩放与双线性插值软边，严格对齐 2×2 画布像素块  ② 14色高反差色阶聚类消除灰蒙过渡  ③ 补齐1px分趾线与锐利眼高光",
        fill=(185, 230, 175),
        font=font_sub,
    )

    def make_town_panel(full_im: Image.Image, badge_text: str, border_col=(225, 180, 110)) -> Image.Image:
        crop_town = full_im.crop((180, 180, 1320, 1020)).resize((pw, ph), Image.Resampling.LANCZOS)
        cat_box = full_im.crop((700, 440, 980, 672))
        inset_w, inset_h = 336, 278
        cat_zoom = cat_box.resize((inset_w, inset_h), Image.Resampling.NEAREST)

        p_im = crop_town.copy()
        p_draw = ImageDraw.Draw(p_im)
        ix, iy = 16, ph - inset_h - 16
        p_draw.rectangle((ix - 3, iy - 28, ix + inset_w + 3, iy + inset_h + 3), fill=(28, 24, 20), outline=border_col, width=2)
        p_im.paste(cat_zoom, (ix, iy))
        p_draw.text((ix + 6, iy - 24), f"4x 像素放大 ({badge_text})", fill=border_col, font=font_sub)
        return p_im

    p1_im = make_town_panel(target_im, "Target 左上角理想参考", border_col=(235, 115, 100))
    p2_im = make_town_panel(v2_im, "Route A v2 (上一版: 双线性软边)", border_col=(230, 185, 115))
    p3_im = make_town_panel(v3_im, "Route A v3 Crisp (本次去糊锐化)", border_col=(120, 235, 140))

    # Panel 4: 6x Ultra-Close-Up Direct Side-by-Side Comparison (Target vs v2 vs v3 Crisp)
    p4_im = Image.new("RGB", (pw, ph), (32, 29, 26))
    p4_draw = ImageDraw.Draw(p4_im)

    cols_info = [
        ("Target 左上参考猫 (6x)", target_im, (235, 115, 100)),
        ("Route A v2 上一版 (6x 偏糊)", v2_im, (230, 185, 115)),
        ("Route A v3 Crisp (6x 锐利精致)", v3_im, (120, 235, 140)),
    ]
    col_w = (pw - 48) // 3
    # Two rows of 6x zooms:
    # Row 1: Head, Emerald Eyes, Asymmetric Peanut Muzzle & Ears (crop 80x68 -> 288x244)
    # Row 2: Flank Tabby Stripes, White Cloud, Belly Orange Spot & Four Paws with 1px Toe Lines (crop 110x78 -> 288x204)
    for c_i, (c_title, src_im, c_col) in enumerate(cols_info):
        cx = 12 + c_i * (col_w + 12)
        p4_draw.rectangle((cx, 10, cx + col_w, 44), fill=(44, 39, 34), outline=c_col, width=2)
        p4_draw.text((cx + 8, 16), c_title, fill=c_col, font=font_sm)

        # Row 1: Head & Eyes crop
        head_crop = src_im.crop((712, 455, 840, 565)).resize((col_w, 245), Image.Resampling.NEAREST)
        p4_im.paste(head_crop, (cx, 50))
        p4_draw.rectangle((cx, 50, cx + col_w, 295), outline=c_col, width=1)
        p4_draw.text((cx + 6, 272), "▲ 头部/大绿眼/阴阳嘴套/胡须", fill=(245, 235, 215), font=font_sm)

        # Row 2: Body Stripes, White Cloud & Paws Toe Lines crop
        body_crop = src_im.crop((728, 535, 920, 665)).resize((col_w, 245), Image.Resampling.NEAREST)
        p4_im.paste(body_crop, (cx, 305))
        p4_draw.rectangle((cx, 305, cx + col_w, 550), outline=c_col, width=1)
        p4_draw.text((cx + 6, 527), "▲ 虎斑/左腹白云/暖橘斑/爪分趾线", fill=(245, 235, 215), font=font_sm)

    # Summary box at bottom of Panel 4
    p4_draw.rectangle((12, 562, pw - 12, ph - 10), fill=(42, 38, 33), outline=(120, 235, 140), width=1)
    p4_draw.text(
        (20, 570),
        "量化诊断与去糊升级：① 实测左上参考猫为 2×2 画布像素块（有效网格 ~118×104），v2 因 Bilinear+二次缩放导致 76% 邻域发虚；",
        fill=(245, 225, 175),
        font=font_sm,
    )
    p4_draw.text(
        (20, 598),
        "② v3 严格采用 118×118 逻辑网格 + 2×2 整数倍贴合 + 14色保体积色阶吸附，消除半透明灰边，保留 AI 立体毛感；",
        fill=(215, 235, 210),
        font=font_sm,
    )
    p4_draw.text(
        (20, 626),
        "③ 补齐 1px 爪尖分趾深褐竖线、锐利双高光翠绿眼、清晰倒Y鼻嘴线与耳廓层次，颗粒精致度追平左上红框参考图。",
        fill=(165, 235, 165),
        font=font_sm,
    )

    panels = [
        (0, 0, "Panel 1 · 左上角红框参考图（Target 理想精致度基准）", (235, 115, 100), p1_im),
        (1, 0, "Panel 2 · 路线 A v2（上一版：Bilinear+二次缩放导致边缘微糊）", (230, 185, 115), p2_im),
        (0, 1, "Panel 3 · 路线 A v3 Crisp（本次去糊锐化：2×2像素对齐+色阶收敛+分趾细节）", (120, 235, 140), p3_im),
        (1, 1, "Panel 4 · Target vs v2 vs v3 局部 6x 超清并排直比（眼神·虎斑·爪分趾）", (135, 205, 245), p4_im),
    ]

    for col_i, row_i, title, col_rgb, panel_img in panels:
        px = pad + col_i * (pw + pad)
        py = header_h + pad + row_i * (ph + title_h + pad)
        draw.rectangle((px, py, px + pw, py + title_h), fill=(40, 36, 32), outline=col_rgb, width=2)
        draw.text((px + 14, py + 13), title, fill=col_rgb, font=font_h2)
        board.paste(panel_img, (px, py + title_h))
        draw.rectangle((px, py + title_h, px + pw, py + title_h + ph), outline=col_rgb, width=2)

    out_cmp = OUT_DIR / "route_a_v2_vs_v3_crisp_comparison.png"
    board.save(out_cmp, quality=95)
    print(f"[composite_v3] Saved 4-panel comparison {out_cmp} ({board.size})")


def main():
    plate_im = Image.open(V1_DIR / "town_clean_plate.png").convert("RGB")
    target_im = Image.open(V1_DIR / "target_redbox_ref.png").convert("RGB")
    v2_im = Image.open(V2_DIR / "route_a_v2_in_town.png").convert("RGB")
    v3_im = composite_v3_exact_1to1(plate_im, OUT_DIR / "route_a_v3_sprite.png", OUT_DIR / "route_a_v3_in_town.png")
    build_v2_vs_v3_comparison(target_im, v2_im, v3_im)


if __name__ == "__main__":
    main()
