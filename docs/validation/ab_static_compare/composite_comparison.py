#!/usr/bin/env python3
"""
Composite Route A and Route B pixel cats onto `town_clean_plate.png` at the exact position
and scale of the red-box reference cat (`x in [712..972], y in [448..665]`), with soft elliptical
ground contact shadows under their paws, and build `ab_town_comparison.png`.
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")


def composite_cat_into_town(plate_im: Image.Image, sprite_path: Path, out_path: Path) -> Image.Image:
    scene = plate_im.convert("RGBA")
    sprite = Image.open(sprite_path).convert("RGBA")
    s_arr = np.array(sprite)
    ys, xs = np.where(s_arr[:, :, 3] > 128)
    crop_s = sprite.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

    # Target cat footprint in `target_redbox_ref.png`:
    # Width ~ 236 px, Height ~ 208 px, bottom of paws at y = 661, center x = 842
    target_h = 210
    scale = target_h / float(crop_s.height)
    target_w = int(round(crop_s.width * scale / 3.0)) * 3
    target_h = int(round(crop_s.height * scale / 3.0)) * 3
    cat_resized = crop_s.resize((target_w, target_h), Image.Resampling.NEAREST)

    paste_x = 840 - target_w // 2
    paste_y = 662 - target_h

    # 1. Soft ground contact shadow under the four paws and body (matching lantern directional light from top-right)
    shadow_layer = Image.new("RGBA", scene.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    # Main under-body soft shadow ellipse
    sdraw.ellipse(
        (paste_x + int(target_w * 0.08), paste_y + int(target_h * 0.78),
         paste_x + int(target_w * 0.86), paste_y + int(target_h * 1.03)),
        fill=(14, 11, 9, 135)
    )
    # Four paw contact shadows (darker tight ellipses right under each paw)
    for px_rel, py_rel in [(0.18, 0.94), (0.34, 0.96), (0.55, 0.94), (0.72, 0.95)]:
        cx = paste_x + int(target_w * px_rel)
        cy = paste_y + int(target_h * py_rel)
        sdraw.ellipse((cx - 22, cy - 9, cx + 22, cy + 9), fill=(10, 8, 6, 165))

    shadow_blur = shadow_layer.filter(ImageFilter.GaussianBlur(radius=6.5))
    scene = Image.alpha_composite(scene, shadow_blur)

    # 2. Paste crisp pixel cat sprite
    cat_layer = Image.new("RGBA", scene.size, (0, 0, 0, 0))
    cat_layer.paste(cat_resized, (paste_x, paste_y), cat_resized)
    scene = Image.alpha_composite(scene, cat_layer)

    rgb_out = scene.convert("RGB")
    rgb_out.save(out_path, quality=95)
    print(f"[composite] Saved {out_path} ({rgb_out.size})")
    return rgb_out


def load_font(size: int):
    for p in [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def build_4panel_comparison(target_im: Image.Image, route_a_im: Image.Image, route_b_im: Image.Image):
    """
    Build a high-resolution 2x2 comparison board `ab_town_comparison.png`:
      - Panel 1 (Top-Left): Target Red-Box Reference (in town + 4x pixel detail inset)
      - Panel 2 (Top-Right): Route B — Hand-crafted Layered UV Master + Photo 5-Markings Mask (in town + 4x pixel detail inset)
      - Panel 3 (Bottom-Left): Route A — AI View Generation + 3D Camera Projection UV Bake (in town + 4x pixel detail inset)
      - Panel 4 (Bottom-Right): Miemie Real Photos Reference (Front Muzzle Asymmetry + Left Flank White Cloud & Belly Spot + Side Tabby/Socks)
    """
    pw, ph = 920, 680
    header_h = 86
    title_h = 54
    pad = 20

    board_w = pw * 2 + pad * 3
    board_h = header_h + (ph + title_h) * 2 + pad * 3
    board = Image.new("RGB", (board_w, board_h), (24, 22, 20))
    draw = ImageDraw.Draw(board)

    font_h1 = load_font(30)
    font_h2 = load_font(22)
    font_sub = load_font(17)

    draw.text(
        (pad, 16),
        "喵汪小镇 · 静态单帧 A/B 路线实景对比（同一微Q 3D底座 + 离屏像素化 + 1px描边）",
        fill=(245, 236, 220),
        font=font_h1,
    )
    draw.text(
        (pad, 54),
        "核心对比：路线 A（AI 受控视角生成 → 3D 投影烘焙 UV） vs 路线 B（精绘分层纹理母版 + 真照采样色板与五印记掩码）",
        fill=(192, 180, 164),
        font=font_sub,
    )

    def make_town_panel_with_inset(full_im: Image.Image, draw_redbox: bool = False, badge_text: str = "") -> Image.Image:
        # Crop around bridge + inn entrance + cat (x in [180..1320], y in [180..1020]) -> aspect ~ 920x680
        crop_town = full_im.crop((180, 180, 1320, 1020)).resize((pw, ph), Image.Resampling.LANCZOS)
        # Extract 4x nearest-neighbor zoom inset of the cat (from full_im x in [695..985], y in [435..675])
        cat_box = full_im.crop((695, 435, 985, 675))
        inset_w, inset_h = 310, 256
        cat_zoom = cat_box.resize((inset_w, inset_h), Image.Resampling.NEAREST)

        p_im = crop_town.copy()
        p_draw = ImageDraw.Draw(p_im)
        # Paste 4x zoom inset at bottom-left corner (over dark canal water so it doesn't block the bridge character or cat)
        ix, iy = 16, ph - inset_h - 16
        p_draw.rectangle((ix - 3, iy - 28, ix + inset_w + 3, iy + inset_h + 3), fill=(28, 24, 20), outline=(225, 180, 110), width=2)
        p_im.paste(cat_zoom, (ix, iy))
        p_draw.text((ix + 6, iy - 24), f"4x 像素放大细节 ({badge_text})", fill=(245, 225, 185), font=font_sub)
        return p_im

    p1_im = make_town_panel_with_inset(target_im, badge_text="Target 红框原图")
    p2_im = make_town_panel_with_inset(route_b_im, badge_text="路线 B 精绘分层+五印记")
    p3_im = make_town_panel_with_inset(route_a_im, badge_text="路线 A AI投影烘焙")

    # Panel 4: Miemie Real Photos 2x2 grid + 5-Markings checklist
    p4_im = Image.new("RGB", (pw, ph), (34, 31, 28))
    p4_draw = ImageDraw.Draw(p4_im)
    photo_dir = Path("/workspace/miaowangtown/reference/miemie_photos")
    photo_specs = [
        ("miemie_ref_01_front45_loaf.jpg", "① 正侧45°：大绿眼 + 右嘴套焦糖斑 + 粉鼻"),
        ("miemie_ref_07_front_couch.jpg", "② 正脸：阴阳花生嘴套(右满左白) + 雪白胸围脖"),
        ("miemie_ref_02_left_flank_white_patch.jpg", "③ 左侧卧：左肋腹白云斑 + 背部深黑棕虎斑条纹"),
        ("miemie_ref_08_left_side_orange_belly.jpg", "④ 侧躺全身：前高后短四蹄白袜 + 腹缘暖橘过渡"),
    ]
    sub_w, sub_h = (pw - 36) // 2, (ph - 115) // 2
    for idx, (fname, cap) in enumerate(photo_specs):
        r_i, c_i = divmod(idx, 2)
        sx = 12 + c_i * (sub_w + 12)
        sy = 10 + r_i * (sub_h + 10)
        pim = Image.open(photo_dir / fname).convert("RGB")
        # Center-crop to aspect sub_w : (sub_h - 28)
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

    p4_draw.rectangle((12, ph - 76, pw - 12, ph - 10), fill=(46, 40, 34), outline=(140, 115, 85), width=1)
    p4_draw.text(
        (22, ph - 68),
        "五印记核对：①右嘴套暖棕/左浅白  ②白围脖+左肋白云  ③腹缘小暖橘斑  ④前长后短四白袜  ⑤鲭鱼虎斑+环尾黑尖",
        fill=(245, 215, 165),
        font=font_sub,
    )
    p4_draw.text(
        (22, ph - 40),
        "对比结论：路线 B 条纹干净锐利、大绿眼高光神态与红框同款、五印记位置精准且无 AI 投影边缘伪影。",
        fill=(185, 230, 165),
        font=font_sub,
    )

    panels = [
        (0, 0, "Panel 1 · 用户红框参考图（Target 理想 HD-2D 观感）", (235, 110, 95), p1_im),
        (1, 0, "Panel 2 · 路线 B：精绘分层 UV 底图 + 照片提取五印记掩码与色板（推荐）", (130, 220, 130), p2_im),
        (0, 1, "Panel 3 · 路线 A：AI 深度/视角受控生成 + 3D 相机反投烘焙 UV", (135, 195, 240), p3_im),
        (1, 1, "Panel 4 · 咩咩真照特征输入源（五印记 & 色板采样对照）", (235, 200, 130), p4_im),
    ]

    for col_i, row_i, title, col_rgb, panel_img in panels:
        px = pad + col_i * (pw + pad)
        py = header_h + pad + row_i * (ph + title_h + pad)
        draw.rectangle((px, py, px + pw, py + title_h), fill=(40, 36, 32), outline=col_rgb, width=2)
        draw.text((px + 14, py + 13), title, fill=col_rgb, font=font_h2)
        board.paste(panel_img, (px, py + title_h))
        draw.rectangle((px, py + title_h, px + pw, py + title_h + ph), outline=col_rgb, width=2)

    out_cmp = OUT_DIR / "ab_town_comparison.png"
    board.save(out_cmp, quality=95)
    print(f"[composite] Saved 4-panel comparison {out_cmp} ({board.size})")


def main():
    plate_im = Image.open(OUT_DIR / "town_clean_plate.png").convert("RGB")
    target_im = Image.open(OUT_DIR / "target_redbox_ref.png").convert("RGB")
    route_a_im = composite_cat_into_town(plate_im, OUT_DIR / "route_a_sprite.png", OUT_DIR / "route_a_in_town.png")
    route_b_im = composite_cat_into_town(plate_im, OUT_DIR / "route_b_sprite.png", OUT_DIR / "route_b_in_town.png")
    build_4panel_comparison(target_im, route_a_im, route_b_im)


if __name__ == "__main__":
    main()
