#!/usr/bin/env python3
"""
Composite `route_a_v2_sprite.png` into the HD-2D town scene (`route_a_v2_in_town.png`)
and build the 4-panel comparison sheet `route_a_v1_vs_v2_comparison.png`:
  - Panel 1 (Top-Left): Target Red-Box Reference (with 4x zoom inset)
  - Panel 2 (Top-Right): Route A v1 — Previous baseline (with 4x zoom inset)
  - Panel 3 (Bottom-Left): Route A v2 — Frequency-Preserving 5-Markings & Emerald Eyes Polish (with 4x zoom inset & ①~⑤ callouts)
  - Panel 4 (Bottom-Right): Miemie Real Photos 5-Markings 1-to-1 Reference Close-ups
"""
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

V1_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v2_polish")

sys.path.insert(0, str(V1_DIR))
from composite_comparison import composite_cat_into_town, load_font


def make_annotated_v2_inset(v2_full: Image.Image, inset_w: int, inset_h: int, font_badge) -> Image.Image:
    cat_box = v2_full.crop((695, 435, 985, 675))
    cat_zoom = cat_box.resize((inset_w, inset_h), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(cat_zoom)

    # Add clean callout badges ①~⑤ pointing to the 5 polished features on the 4x zoom inset
    # Coordinates in cat_zoom (310x256):
    # Cat occupies roughly x in [32..275], y in [22..236]
    callouts = [
        # (badge_x, badge_y, target_x, target_y, label, color)
        (18, 128, 66, 126, "①右嘴套斑", (255, 200, 120)),
        (16, 74,  78, 92,  "⑤翠绿亮眼", (130, 245, 150)),
        (158, 168, 156, 134, "②左腹白云", (240, 240, 255)),
        (228, 158, 184, 138, "③暖橘斑",   (255, 175, 105)),
        (82, 224, 102, 198, "④前高后低袜", (220, 235, 255)),
    ]
    for bx, by, tx, ty, text, col in callouts:
        draw.line((bx + 28, by + 10, tx, ty), fill=col, width=2)
        draw.ellipse((tx - 3, ty - 3, tx + 3, ty + 3), fill=col, outline=(20, 16, 12))
        # Small dark pill behind text
        tw = len(text) * 13 + 8
        draw.rectangle((bx, by, bx + tw, by + 20), fill=(22, 18, 15), outline=col, width=1)
        draw.text((bx + 4, by + 1), text, fill=col, font=font_badge)

    return cat_zoom


def build_v1_v2_comparison(target_im: Image.Image, v1_im: Image.Image, v2_im: Image.Image):
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
    font_badge = load_font(13)

    draw.text(
        (pad, 16),
        "喵汪小镇 · 路线 A 静态单帧精调对比（Route A v1 原始投影 vs Route A v2 五印记与翠绿大眼精调）",
        fill=(245, 236, 220),
        font=font_h1,
    )
    draw.text(
        (pad, 54),
        "核心原则：100% 保留路线 A 的 AI 真猫毛发层次与柔和体积光影，通过保频色彩/明度调制精准落位咩咩五印记与通透翡翠绿眼",
        fill=(185, 225, 175),
        font=font_sub,
    )

    def make_town_panel(full_im: Image.Image, badge_text: str, annotate_v2: bool = False) -> Image.Image:
        crop_town = full_im.crop((180, 180, 1320, 1020)).resize((pw, ph), Image.Resampling.LANCZOS)
        inset_w, inset_h = 330, 268
        if annotate_v2:
            cat_zoom = make_annotated_v2_inset(full_im, inset_w, inset_h, font_badge)
        else:
            cat_box = full_im.crop((695, 435, 985, 675))
            cat_zoom = cat_box.resize((inset_w, inset_h), Image.Resampling.NEAREST)

        p_im = crop_town.copy()
        p_draw = ImageDraw.Draw(p_im)
        ix, iy = 16, ph - inset_h - 16
        border_col = (130, 230, 140) if annotate_v2 else (225, 180, 110)
        p_draw.rectangle((ix - 3, iy - 28, ix + inset_w + 3, iy + inset_h + 3), fill=(28, 24, 20), outline=border_col, width=2)
        p_im.paste(cat_zoom, (ix, iy))
        p_draw.text((ix + 6, iy - 24), f"4x 像素细节 ({badge_text})", fill=border_col, font=font_sub)
        return p_im

    p1_im = make_town_panel(target_im, "Target 红框理想参考", annotate_v2=False)
    p2_im = make_town_panel(v1_im, "Route A v1 精调前", annotate_v2=False)
    p3_im = make_town_panel(v2_im, "Route A v2 五印记+眼神精调", annotate_v2=True)

    # Panel 4: Miemie Real Photos 5-Markings 1-to-1 Feature Close-ups
    p4_im = Image.new("RGB", (pw, ph), (34, 31, 28))
    p4_draw = ImageDraw.Draw(p4_im)
    photo_dir = Path("/workspace/miaowangtown/reference/miemie_photos")
    photo_specs = [
        ("miemie_ref_01_front45_loaf.jpg", "①⑤ 正侧特写：右嘴套暖焦糖斑 + 翠绿亮眼 + 砖红粉鼻"),
        ("miemie_ref_07_front_couch.jpg", "①② 正面特写：右满左白阴阳花生嘴套 + 雪白大胸围脖"),
        ("miemie_ref_02_left_flank_white_patch.jpg", "②⑤ 左肋特写：左肋腹向上漫延白云斑 + 背部深褐虎斑"),
        ("miemie_ref_08_left_side_orange_belly.jpg", "③④ 腹侧与四肢：左腹白毛边暖橘斑 + 前长后短四蹄白袜"),
    ]
    sub_w, sub_h = (pw - 36) // 2, (ph - 125) // 2
    for idx, (fname, cap) in enumerate(photo_specs):
        r_i, c_i = divmod(idx, 2)
        sx = 12 + c_i * (sub_w + 12)
        sy = 10 + r_i * (sub_h + 10)
        pim = Image.open(photo_dir / fname).convert("RGB")
        th_img = sub_h - 28
        target_asp = sub_w / float(th_img)
        cur_asp = pim.width / float(pim.height)
        if cur_asp > target_asp:
            new_w = int(pim.height * target_asp)
            x_off = (pim.width - new_w) // 2
            pim = pim.crop((x_off, 0, x_off + new_w, pim.height))
        else:
            new_h = int(pim.width / target_asp)
            y_off = (pim.height - new_h) // 2
            pim = pim.crop((0, y_off, pim.width, y_off + new_h))
        pim = pim.resize((sub_w, th_img), Image.Resampling.LANCZOS)
        p4_im.paste(pim, (sx, sy))
        p4_draw.rectangle((sx, sy + th_img, sx + sub_w, sy + sub_h), fill=(48, 43, 38))
        p4_draw.text((sx + 6, sy + th_img + 4), cap, fill=(235, 225, 210), font=font_sub)

    p4_draw.rectangle((12, ph - 86, pw - 12, ph - 10), fill=(44, 39, 34), outline=(130, 210, 130), width=1)
    p4_draw.text(
        (20, ph - 78),
        "Route A v2 精调升级点（全部采用保频毛发色彩/明度调制，零生硬色块）：",
        fill=(245, 220, 170),
        font=font_sub,
    )
    p4_draw.text(
        (20, ph - 52),
        "① 右嘴套暖焦糖斑+左白脸颊  ② 胸围脖连左肋腹白云斑  ③ 腹缘暖橘过渡斑",
        fill=(220, 235, 215),
        font=font_sub,
    )
    p4_draw.text(
        (20, ph - 28),
        "④ 前腿过膝白袜(含右腕斑)+后腿短袜配花裤衩  ⑤ 通透翡翠绿渐变虹膜+竖瞳+双高光+粉鼻",
        fill=(175, 235, 175),
        font=font_sub,
    )

    panels = [
        (0, 0, "Panel 1 · 用户红框参考图（Target 理想 HD-2D 观感）", (235, 110, 95), p1_im),
        (1, 0, "Panel 2 · 路线 A v1（上一版：AI 毛感自然，但缺五印记细节）", (135, 195, 240), p2_im),
        (0, 1, "Panel 3 · 路线 A v2（本次精调：保留柔和毛感 + 补齐五印记与翠绿亮眼）", (120, 230, 135), p3_im),
        (1, 1, "Panel 4 · 咩咩真照五印记一一对应特写（①~⑤ 验收对照）", (235, 200, 130), p4_im),
    ]

    for col_i, row_i, title, col_rgb, panel_img in panels:
        px = pad + col_i * (pw + pad)
        py = header_h + pad + row_i * (ph + title_h + pad)
        draw.rectangle((px, py, px + pw, py + title_h), fill=(40, 36, 32), outline=col_rgb, width=2)
        draw.text((px + 14, py + 13), title, fill=col_rgb, font=font_h2)
        board.paste(panel_img, (px, py + title_h))
        draw.rectangle((px, py + title_h, px + pw, py + title_h + ph), outline=col_rgb, width=2)

    out_cmp = OUT_DIR / "route_a_v1_vs_v2_comparison.png"
    board.save(out_cmp, quality=95)
    print(f"[composite_v2] Saved {out_cmp} ({board.size})")


def main():
    plate_im = Image.open(V1_DIR / "town_clean_plate.png").convert("RGB")
    target_im = Image.open(V1_DIR / "target_redbox_ref.png").convert("RGB")
    v1_im = Image.open(V1_DIR / "route_a_in_town.png").convert("RGB")
    v2_im = composite_cat_into_town(plate_im, OUT_DIR / "route_a_v2_sprite.png", OUT_DIR / "route_a_v2_in_town.png")
    build_v1_v2_comparison(target_im, v1_im, v2_im)


if __name__ == "__main__":
    main()
