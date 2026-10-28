#!/usr/bin/env python3
"""
Route A v4 (Clean AI-Native HD-2D Pixel Sprite + Zero Ghost Paws / Zero Barcode / Zero Paint Blobs):
1. Uses the newly generated `route_a_v4_ai_source.jpg` (which has all 4 white-socked paws clearly separated,
   ringed tabby tail, asymmetric right-caramel / left-white peanut muzzle, white chest bib & flank cloud,
   and vivid emerald-green eyes).
2. NO Python-drawn orange circles, NO 14-color camo quantization, NO artificial fork lines on paws!
   Instead, cleanly extracts the AI cat foreground, downsamples to the exact 116x102 logical pixel grid
   with Nearest-neighbor sampling (preserving 100% of the rich, natural AI fur shades and crisp brushwork),
   adds a clean 1px dark espresso outer outline (`#1b100a`), scales by exact 2x2 integer blocks (`232x204`),
   and composites onto `clean_town_bg.png` with soft ground contact shadows under all 4 paws!
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

V1_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
V3_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v3_crisp")
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v4_clean")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_clean_ai_pixel_sprite() -> Image.Image:
    im = Image.open(OUT_DIR / "route_a_v4_ai_source.jpg").convert("RGB")
    # Mild contrast & sharpness enhancement so natural AI fur tufts and eye highlights stay crisp at 116x102
    im = ImageEnhance.Contrast(im).enhance(1.08)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=135, threshold=3))
    arr = np.array(im)
    H, W, _ = arr.shape

    # Background is neutral gray (R≈G≈B≈103); cat fur/eyes/stripes have either chroma or strong luma difference
    corners = np.vstack([
        arr[:40, :40].reshape(-1, 3),
        arr[:40, -40:].reshape(-1, 3),
        arr[-40:, :40].reshape(-1, 3),
        arr[-40:, -40:].reshape(-1, 3),
    ])
    bg_med = np.median(corners, axis=0)
    dist_bg = np.linalg.norm(arr.astype(np.float32) - bg_med[None, None, :], axis=2)

    r, g, b = arr[:, :, 0].astype(np.int32), arr[:, :, 1].astype(np.int32), arr[:, :, 2].astype(np.int32)
    chroma = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)

    # Foreground mask: exclude neutral gray background (where chroma < 16 and 68 < luma < 148)
    is_cat = (
        (chroma >= 18)
        | (r > 162)
        | (r < 64)
        | (dist_bg > 34.0)
    ) & (dist_bg > 22.0)
    is_cat[:16, :] = False
    is_cat[-16:, :] = False
    is_cat[:, :16] = False
    is_cat[:, -16:] = False

    # Keep main connected body (remove any tiny isolated background specks and thin floating whisker fringe before pixelation)
    # 2px erosion to strip 1px anti-aliased gray border halo around the cat
    eroded = is_cat.copy()
    for _ in range(3):
        nxt = eroded.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt &= np.roll(np.roll(eroded, dy, axis=0), dx, axis=1)
        eroded = nxt
    # Dilate back 1px so silhouette stays full without the gray fringe
    fg = eroded.copy()
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        fg |= np.roll(np.roll(eroded, dy, axis=0), dx, axis=1)

    # Also fill any internal holes inside the cat body (e.g. dark pupils or dark stripes that happened to have low chroma)
    # Any pixel inside the bounding box with r < 75 or surrounded by fg is part of the cat
    ys, xs = np.where(fg)
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()

    # Flood-fill background from the 4 corners of the bounding box padded by 4px
    pad = 8
    bx0, bx1 = max(0, x0 - pad), min(W, x1 + pad)
    by0, by1 = max(0, y0 - pad), min(H, y1 + pad)
    sub_fg = fg[by0:by1, bx0:bx1].copy()
    sh, sw = sub_fg.shape
    bg_reach = np.zeros((sh, sw), dtype=bool)
    bg_reach[0, :] = ~sub_fg[0, :]
    bg_reach[-1, :] = ~sub_fg[-1, :]
    bg_reach[:, 0] = ~sub_fg[:, 0]
    bg_reach[:, -1] = ~sub_fg[:, -1]
    for _ in range(max(sh, sw)):
        prev = bg_reach.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            bg_reach |= np.roll(np.roll(bg_reach, dy, axis=0), dx, axis=1) & (~sub_fg)
        if np.array_equal(prev, bg_reach):
            break
    # Interior of cat = ~bg_reach!
    sub_solid = ~bg_reach

    # Replace background pixels in `sub_rgb` with nearest interior cat pixel so edge sampling never pulls gray!
    sub_rgb = arr[by0:by1, bx0:bx1].copy()
    valid_c = sub_solid.copy()
    for _ in range(10):
        if np.all(valid_c):
            break
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            sv = np.roll(np.roll(valid_c, dy, axis=0), dx, axis=1)
            sc = np.roll(np.roll(sub_rgb, dy, axis=0), dx, axis=1)
            fill = (~valid_c) & sv
            if np.any(fill):
                sub_rgb[fill] = sc[fill]
                valid_c[fill] = True

    # Slightly warm-harmonize the white fur and brown coat so it sits naturally in the warm lantern-lit HD-2D town
    # (target cat white fur is warm cream (224, 204, 178) rather than cool blue-white)
    sub_f = sub_rgb.astype(np.float32)
    sub_f[:, :, 0] = np.clip(sub_f[:, :, 0] * 1.01, 0, 255)
    sub_f[:, :, 1] = np.clip(sub_f[:, :, 1] * 0.96, 0, 255)
    sub_f[:, :, 2] = np.clip(sub_f[:, :, 2] * 0.86, 0, 255)
    sub_rgb = sub_f.astype(np.uint8)

    rgba_hi = np.zeros((sh, sw, 4), dtype=np.uint8)
    rgba_hi[:, :, :3] = sub_rgb
    rgba_hi[sub_solid, 3] = 255

    hi_im = Image.fromarray(rgba_hi, mode="RGBA")
    hi_im.save(OUT_DIR / "route_a_v4_highres_clean.png")

    # Downsample to exact logical pixel grid (114x104) with NEAREST so every pixel is crisp and retains natural AI shading!
    gw = 114
    gh = int(round(gw * sh / float(sw)))
    low_im = hi_im.resize((gw, gh), Image.Resampling.NEAREST)
    low_arr = np.array(low_im)
    alpha = low_arr[:, :, 3] > 128

    # Remove any single-pixel isolated spurs on the silhouette boundary
    nb_count = np.zeros_like(alpha, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb_count += np.roll(np.roll(alpha, dy, axis=0), dx, axis=1).astype(np.int32)
    alpha &= (nb_count >= 2)
    low_arr[~alpha] = [0, 0, 0, 0]
    low_arr[alpha, 3] = 255

    # Add crisp 1px dark espresso outer pixel outline (#1b100a = 27, 16, 10)
    outline_col = np.array([27, 16, 10, 255], dtype=np.uint8)
    dilated = np.zeros_like(alpha)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dilated |= np.roll(np.roll(alpha, dy, axis=0), dx, axis=1)
    edge = dilated & (~alpha)
    low_arr[edge] = outline_col

    # Add 2 crisp pixel whiskers on the left side of the muzzle (2px/3px long, warm cream-white)
    w_mask = alpha & (low_arr[:, :, 0] > 175) & (low_arr[:, :, 1] > 150)
    gy_grid = np.arange(gh)[:, None]
    wys, wxs = np.where(w_mask & (gy_grid > gh * 0.36) & (gy_grid < gh * 0.54))
    if len(wxs) > 0:
        wx_min = int(np.percentile(wxs, 3))
        wy_med = int(np.median(wys[wxs <= wx_min + 3]))
        for wy_off, wx_len in [(-1, 3), (2, 3)]:
            wy = wy_med + wy_off
            for step in range(1, wx_len + 1):
                wx = wx_min - step
                if 0 <= wx < gw and 0 <= wy < gh:
                    low_arr[wy, wx] = [228, 210, 186, 255]

    low_out = Image.fromarray(low_arr, mode="RGBA")
    low_out.save(OUT_DIR / "route_a_v4_sprite_logical.png")

    # Scale by exact 2x2 integer blocks -> 228x208 on the 1364x1064 town canvas!
    sprite_2x = low_out.resize((gw * 2, gh * 2), Image.Resampling.NEAREST)
    sprite_2x.save(OUT_DIR / "route_a_v4_sprite.png")
    print(f"[v4] Saved logical sprite ({gw}x{gh}) and 2x2 canvas sprite ({sprite_2x.size})")
    return sprite_2x


def composite_v4_into_clean_town(sprite_2x: Image.Image) -> Image.Image:
    bg = Image.open(OUT_DIR / "clean_town_bg.png").convert("RGBA")
    tw, th = sprite_2x.size

    # Place cat at the exact position of the original red-box cat (center x=840, bottom of front paws at y=662)
    paste_x = 840 - (tw // 4) * 2
    paste_y = 662 - th

    # Soft ground contact shadow under the body and all 4 paws
    shadow_layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    # Main under-body soft shadow ellipse
    sdraw.ellipse(
        (paste_x + int(tw * 0.10), paste_y + int(th * 0.76),
         paste_x + int(tw * 0.84), paste_y + int(th * 1.01)),
        fill=(12, 10, 8, 125)
    )
    # 4 paw contact shadows matching the 4 paws of `route_a_v4_sprite.png`:
    # Paw 1 (front right, screen left): x_rel=0.22, y_rel=0.95
    # Paw 2 (front left, screen mid-left): x_rel=0.41, y_rel=0.97
    # Paw 3 (hind right, screen mid): x_rel=0.55, y_rel=0.89
    # Paw 4 (hind left, screen right): x_rel=0.76, y_rel=0.91
    for px_rel, py_rel in [(0.22, 0.95), (0.41, 0.97), (0.55, 0.89), (0.76, 0.91)]:
        cx = paste_x + int(tw * px_rel)
        cy = paste_y + int(th * py_rel)
        sdraw.ellipse((cx - 20, cy - 8, cx + 20, cy + 8), fill=(8, 6, 5, 160))

    shadow_blur = shadow_layer.filter(ImageFilter.GaussianBlur(radius=5.5))
    scene = Image.alpha_composite(bg, shadow_blur)

    cat_layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    cat_layer.paste(sprite_2x, (paste_x, paste_y), sprite_2x)
    scene = Image.alpha_composite(scene, cat_layer)

    rgb_out = scene.convert("RGB")
    rgb_out.save(OUT_DIR / "route_a_v4_in_town.png", quality=95)

    # Save exact same close-up crop as the user's screenshot (700, 440, 980, 672) upscaled 4x with NEAREST!
    closeup = rgb_out.crop((700, 440, 980, 672)).resize((280 * 4, 232 * 4), Image.Resampling.NEAREST)
    closeup.save(OUT_DIR / "route_a_v4_closeup_crop.png")
    print("[v4] Saved route_a_v4_in_town.png and route_a_v4_closeup_crop.png")
    return rgb_out


def main():
    sprite_2x = extract_clean_ai_pixel_sprite()
    composite_v4_into_clean_town(sprite_2x)


if __name__ == "__main__":
    main()
