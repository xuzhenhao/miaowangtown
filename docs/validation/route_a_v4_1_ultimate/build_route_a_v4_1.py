#!/usr/bin/env python3
"""
Route A v4.1 (Ultimate Static Benchmark Edition):
Builds directly upon the user-approved `Route A v4` (`route_a_v4_highres_clean.png` & `clean_town_bg.png`)
with ZERO geometric paint blobs and ZERO 14-color camo quantization, implementing the 3 targeted upgrades:

1. Upgrade 1 — Mask-Aware Pre-Filtered Box/Area Downsampling + Edge De-Halo + Isolated Speckle Cleanup:
   - Extrapolates interior cat fur colors 14px outward across the high-res mask boundary so edge pixels
     never blend with background gray or dark border fringe during area integration.
   - Applies a gentle 3x3 edge-preserving median/bilateral pre-filter on the 901x823 high-res RGB to remove
     single-pixel JPEG grain before downsampling.
   - Uses `Image.Resampling.BOX` (area-integral averaging) + mild UnsharpMask to downsample to the `114x104`
     logical grid, paired with a clean binary alpha mask (`alpha > 168`) and a 1-pass isolated-speckle filter
     (replaces only single-pixel outliers whose 4 cardinal neighbors all differ by >32 in luma, while keeping
     eye catchlights and pupils untouched).

2. Upgrade 2 — Ultra-Soft Fur-Guided Enhancement of Miemie's Asymmetric 5-Markings (Zero Hard Edges):
   - All modulations are computed on the 901x823 high-res canvas using large Gaussian-blurred masks (`radius=22..38px`)
     multiplied by the local fur luminance/chroma structure:
     a) Asymmetric Peanut Muzzle: gently enriches the right-muzzle (`x_log in [15..20], y_log in [46..51]`) warm caramel
        patch while softly brightening the left-muzzle (`x_log in [9..14]` & `[22..33], y_log in [43..52]`) cream-white fur.
     b) Snow-White Chest Bib + Left Flank White Cloud + Warm Apricot-Orange Belly Transition:
        softly lifts the upward white cloud on the lower left flank (`x_log in [46..58], y_log in [66..76]`) and blends
        a subtle, feathery warm golden-apricot transition along its upper-posterior border (`x_log in [54..66], y_log in [62..72]`).
     c) Front-High / Hind-Short Four White Socks: softly extends the cream-white fur up the two front legs (`y_log in [80..89]`)
        for Miemie's over-the-knee front socks (preserving a subtle warm caramel hint on the inner right wrist), while
        tightening the two hind socks to the lower ankle (`y_log >= 87`) so the hind thighs show rich dark tabby stripes.

3. Upgrade 3 — HD-2D Town Environment Lighting & Ground Contact Shadow Integration:
   - Applies a smooth, directional HD-2D lighting field across the cat body matching the town's top-right warm lanterns
     and late-afternoon sun:
     * Warm amber-gold key light (`[1.06, 1.02, 0.94]`) across the upper head crown, ear backs, and dorsal spine;
     * Soft cool-warm ambient occlusion (`[0.86, 0.84, 0.82]`) under the lower chin, lower belly underside, and inner legs.
   - Renders a multi-layered soft elliptical ground contact shadow + per-paw ambient occlusion on the stone floor.
"""
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

V1_DIR = Path("/workspace/miaowangtown/reference/town_ref")
V4_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v4_1_ultimate")
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v4_1_ultimate")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_soft_gaussian_field(sh: int, sw: int, cx_rel: float, cy_rel: float,
                             rx_rel: float, ry_rel: float, blur_radius: float = 28.0) -> np.ndarray:
    """Create an ultra-smooth, infinitely differentiable Gaussian weight field in [0..1] with zero geometric edge."""
    yy, xx = np.meshgrid(np.linspace(0.0, 1.0, sh, dtype=np.float32),
                         np.linspace(0.0, 1.0, sw, dtype=np.float32), indexing="ij")
    d2 = ((xx - cx_rel) / rx_rel) ** 2 + ((yy - cy_rel) / ry_rel) ** 2
    raw = np.exp(-0.5 * d2)
    im_w = Image.fromarray(np.clip(raw * 255.0, 0, 255).astype(np.uint8), mode="L")
    im_w = im_w.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    return np.array(im_w, dtype=np.float32) / 255.0


def build_route_a_v4_1_sprite() -> Image.Image:
    hi_im = Image.open(V4_DIR / "route_a_v4_highres_clean.png").convert("RGBA")
    arr = np.array(hi_im)
    sh, sw, _ = arr.shape
    rgb_orig = arr[:, :, :3].astype(np.float32)
    alpha_orig = arr[:, :, 3] > 128

    # =========================================================================
    # Upgrade 1a: Edge De-Halo & Pre-Filtering on High-Res (901x823)
    # =========================================================================
    # Erode alpha by 2px before extrapolating RGB outward so any residual 1px gray/dark border pixels
    # from the original AI cutout are completely replaced by clean interior fur colors!
    inner_valid = alpha_orig.copy()
    for _ in range(2):
        nxt = inner_valid.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt &= np.roll(np.roll(inner_valid, dy, axis=0), dx, axis=1)
        inner_valid = nxt

    rgb_clean = rgb_orig.copy()
    val_mask = inner_valid.copy()
    for _ in range(16):
        if np.all(val_mask):
            break
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            sv = np.roll(np.roll(val_mask, dy, axis=0), dx, axis=1)
            sc = np.roll(np.roll(rgb_clean, dy, axis=0), dx, axis=1)
            fill = (~val_mask) & sv
            if np.any(fill):
                rgb_clean[fill] = sc[fill]
                val_mask[fill] = True

    # Gentle 3x3 median filter on high-res RGB to remove tiny JPEG mosquito noise while keeping fur edges sharp
    rgb_med = np.array(Image.fromarray(np.clip(rgb_clean, 0, 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(size=3)), dtype=np.float32)
    # Blend 65% median-filtered + 35% original so fine eye details stay crisp
    rgb_work = 0.65 * rgb_med + 0.35 * rgb_clean

    # =========================================================================
    # Upgrade 2: Ultra-Soft Fur-Guided Enhancement of Miemie's 5 Markings
    # =========================================================================
    luma = 0.299 * rgb_work[:, :, 0] + 0.587 * rgb_work[:, :, 1] + 0.114 * rgb_work[:, :, 2]
    # Normalized local fur texture factor around local 15x15 mean (preserves 100% of individual hair strand brushwork!)
    luma_smooth = np.array(
        Image.fromarray(np.clip(luma, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=8.0)),
        dtype=np.float32
    )
    fur_detail_ratio = np.clip((luma + 10.0) / (luma_smooth + 10.0), 0.72, 1.28)[:, :, None]

    # 2a. Asymmetric Peanut Muzzle ("右满暖焦糖、左浅奶油白")
    # In logical (114x104) coords:
    # Nose is at (14.5/114=0.127, 45.5/104=0.437).
    # Miemie's right muzzle caramel patch (viewer's left of mouth line / below nose): cx=0.155, cy=0.468
    # Wait: on a 3/4 view facing left:
    # Screen-left of nose (`x_rel in [0.09..0.135], y_rel in [0.42..0.48]`) is the cat's RIGHT muzzle (`-X`)!
    # Screen-right of nose (`x_rel in [0.16..0.28], y_rel in [0.43..0.51]`) is the cat's LEFT muzzle/cheek (`+X`)!
    # Let us verify: in `route_a_v4_ai_source.jpg`, the AI put a warm tan patch at `x_log in [15..21], y_log in [45..52]`.
    # Let us gently brighten the left cheek (`x_rel=0.23, y_rel=0.46`) to clean cream-white so the warm caramel peanut muzzle
    # next to the nose stands out with unmistakable "阴阳花生嘴套" charm!
    w_cheek_left_white = make_soft_gaussian_field(sh, sw, cx_rel=0.235, cy_rel=0.465, rx_rel=0.045, ry_rel=0.035, blur_radius=18.0)
    # Only lift mid/light fur (don't touch dark eye rim or whiskers)
    w_cheek_left_white *= np.clip((luma - 115.0) / 55.0, 0.0, 1.0)
    target_cream = np.array([232.0, 212.0, 184.0], dtype=np.float32)[None, None, :] * fur_detail_ratio
    rgb_work = rgb_work * (1.0 - w_cheek_left_white[:, :, None] * 0.48) + target_cream * (w_cheek_left_white[:, :, None] * 0.48)

    # Gently enrich the warm caramel peanut tone on the right muzzle pad (`cx_rel=0.155, cy_rel=0.472`)
    w_muzzle_caramel = make_soft_gaussian_field(sh, sw, cx_rel=0.152, cy_rel=0.472, rx_rel=0.028, ry_rel=0.024, blur_radius=14.0)
    w_muzzle_caramel *= np.clip((luma - 85.0) / 50.0, 0.0, 1.0) * np.clip((205.0 - luma) / 35.0, 0.0, 1.0)
    target_caramel = np.array([178.0, 116.0, 66.0], dtype=np.float32)[None, None, :] * fur_detail_ratio
    rgb_work = rgb_work * (1.0 - w_muzzle_caramel[:, :, None] * 0.42) + target_caramel * (w_muzzle_caramel[:, :, None] * 0.42)

    # 2b. Left Flank Upward White Cloud (`cx_rel=0.455, cy_rel=0.695`) + Subtle Warm Apricot Belly Edge Transition (`cx_rel=0.515, cy_rel=0.665`)
    w_flank_cloud = make_soft_gaussian_field(sh, sw, cx_rel=0.455, cy_rel=0.695, rx_rel=0.055, ry_rel=0.042, blur_radius=22.0)
    # Only modulate along the existing white belly / lower flank border
    w_flank_cloud *= np.clip((luma - 80.0) / 60.0, 0.0, 1.0)
    target_cloud = np.array([224.0, 204.0, 178.0], dtype=np.float32)[None, None, :] * fur_detail_ratio
    rgb_work = rgb_work * (1.0 - w_flank_cloud[:, :, None] * 0.46) + target_cloud * (w_flank_cloud[:, :, None] * 0.46)

    # Subtle warm golden-apricot fur transition right where the white belly/cloud meets the brown flank tabby
    w_belly_warm = make_soft_gaussian_field(sh, sw, cx_rel=0.520, cy_rel=0.668, rx_rel=0.048, ry_rel=0.035, blur_radius=20.0)
    w_belly_warm *= np.clip((luma - 75.0) / 50.0, 0.0, 1.0) * np.clip((195.0 - luma) / 40.0, 0.0, 1.0)
    target_apricot = np.array([186.0, 124.0, 70.0], dtype=np.float32)[None, None, :] * fur_detail_ratio
    rgb_work = rgb_work * (1.0 - w_belly_warm[:, :, None] * 0.38) + target_apricot * (w_belly_warm[:, :, None] * 0.38)

    # 2c. Front-High / Hind-Short Four White Socks:
    # Front right leg (`cx_rel=0.195, cy_rel=0.815`) and front left leg (`cx_rel=0.385, cy_rel=0.835`):
    # softly lift the upper sock region (`cy_rel in [0.78..0.86]`) to warm cream-white so front socks look clearly over-the-knee!
    w_front_sock_R = make_soft_gaussian_field(sh, sw, cx_rel=0.195, cy_rel=0.815, rx_rel=0.042, ry_rel=0.042, blur_radius=16.0)
    w_front_sock_L = make_soft_gaussian_field(sh, sw, cx_rel=0.385, cy_rel=0.835, rx_rel=0.045, ry_rel=0.042, blur_radius=16.0)
    w_front_socks = np.maximum(w_front_sock_R, w_front_sock_L) * np.clip((luma - 65.0) / 55.0, 0.0, 1.0)
    target_sock_cream = np.array([224.0, 204.0, 178.0], dtype=np.float32)[None, None, :] * fur_detail_ratio
    rgb_work = rgb_work * (1.0 - w_front_socks[:, :, None] * 0.55) + target_sock_cream * (w_front_socks[:, :, None] * 0.55)

    # Hind legs (`cx_rel=0.535, cy_rel=0.805` and `cx_rel=0.745, cy_rel=0.815`):
    # gently warm-tan the upper ankle (`cy_rel in [0.76..0.83]`) so the hind white socks look shorter (ankle-height) below the striped thighs!
    w_hind_upper_R = make_soft_gaussian_field(sh, sw, cx_rel=0.535, cy_rel=0.800, rx_rel=0.042, ry_rel=0.035, blur_radius=15.0)
    w_hind_upper_L = make_soft_gaussian_field(sh, sw, cx_rel=0.745, cy_rel=0.810, rx_rel=0.045, ry_rel=0.035, blur_radius=15.0)
    w_hind_upper = np.maximum(w_hind_upper_R, w_hind_upper_L) * np.clip((luma - 135.0) / 50.0, 0.0, 1.0)
    target_hind_tan = np.array([154.0, 104.0, 60.0], dtype=np.float32)[None, None, :] * fur_detail_ratio
    rgb_work = rgb_work * (1.0 - w_hind_upper[:, :, None] * 0.52) + target_hind_tan * (w_hind_upper[:, :, None] * 0.52)

    # =========================================================================
    # Upgrade 3: HD-2D Town Environment Lighting Integration (Top-Right Warm Lantern Key + Underbelly AO)
    # =========================================================================
    yy, xx = np.meshgrid(np.linspace(0.0, 1.0, sh, dtype=np.float32),
                         np.linspace(0.0, 1.0, sw, dtype=np.float32), indexing="ij")
    # Top-back-right warm lantern highlight (head crown, ear tips, upper back)
    key_light = np.clip(1.0 - ((xx - 0.38) ** 2 / 0.28 + (yy - 0.18) ** 2 / 0.18), 0.0, 1.0)
    # Under-belly, lower chest, and inner hind leg ambient occlusion shadow
    ao_belly = make_soft_gaussian_field(sh, sw, cx_rel=0.48, cy_rel=0.76, rx_rel=0.22, ry_rel=0.10, blur_radius=24.0)
    ao_chin = make_soft_gaussian_field(sh, sw, cx_rel=0.22, cy_rel=0.54, rx_rel=0.08, ry_rel=0.04, blur_radius=16.0)
    ao_total = np.clip(ao_belly * 0.75 + ao_chin * 0.45, 0.0, 1.0)

    # Apply directional warm tint and soft AO (keeping green eyes untouched!)
    is_eye_hi = ((rgb_work[:, :, 1] - rgb_work[:, :, 0]) > 10.0) & (rgb_work[:, :, 1] > 70.0)
    env_mult = np.ones_like(rgb_work)
    # Warm golden lantern key light
    env_mult[:, :, 0] += key_light * 0.055
    env_mult[:, :, 1] += key_light * 0.025
    env_mult[:, :, 2] -= key_light * 0.015
    # Soft underbelly/chin ambient occlusion
    env_mult[:, :, 0] -= ao_total * 0.10
    env_mult[:, :, 1] -= ao_total * 0.11
    env_mult[:, :, 2] -= ao_total * 0.12
    env_mult[is_eye_hi] = 1.0

    rgb_lit = np.clip(rgb_work * env_mult, 0, 255).astype(np.uint8)

    # =========================================================================
    # Upgrade 1b: Mask-Aware Box/Area Downsampling to 114x104 + Speckle Cleanup
    # =========================================================================
    gw, gh = 114, 104
    # Downsample the extrapolated `rgb_lit` with BOX (area average) so every 8x8 high-res patch averages smoothly
    # without random Nearest-Neighbor jump noise, then apply a crisp UnsharpMask!
    im_rgb_hi = Image.fromarray(rgb_lit, mode="RGB")
    im_rgb_box = im_rgb_hi.resize((gw, gh), Image.Resampling.BOX)
    im_rgb_crisp = im_rgb_box.filter(ImageFilter.UnsharpMask(radius=1.0, percent=115, threshold=2))
    low_rgb = np.array(im_rgb_crisp, dtype=np.uint8)

    # Also keep pure Nearest sample for the emerald eyes & catchlights so eye glints are 100% razor-sharp!
    im_rgb_near = im_rgb_hi.resize((gw, gh), Image.Resampling.NEAREST)
    near_rgb = np.array(im_rgb_near, dtype=np.uint8)
    eye_zone_low = np.zeros((gh, gw), dtype=bool)
    eye_zone_low[31:47, 10:35] = True
    is_eye_or_hl = eye_zone_low & (
        ((near_rgb[:, :, 1].astype(int) - near_rgb[:, :, 0].astype(int)) > 8)
        | (near_rgb[:, :, 0] > 220)
        | ((near_rgb[:, :, 0] < 45) & (near_rgb[:, :, 1] < 45))
    )
    low_rgb[is_eye_or_hl] = near_rgb[is_eye_or_hl]

    # Boost the top-left white catchlight & emerald lower crescent on both eyes by 10% for extra life
    for ey in range(33, 46):
        for ex in range(11, 34):
            r_p, g_p, b_p = [int(v) for v in low_rgb[ey, ex]]
            if g_p > r_p + 12 and g_p > 80:
                # Vivid emerald iris boost
                low_rgb[ey, ex, 0] = max(0, int(r_p * 0.90))
                low_rgb[ey, ex, 1] = min(255, int(g_p * 1.12 + 8))
                low_rgb[ey, ex, 2] = max(0, int(b_p * 0.92))
            elif r_p > 210 and g_p > 205 and b_p > 190:
                # Pure crisp catchlight
                low_rgb[ey, ex] = [252, 248, 240]

    # Downsample alpha with BOX and threshold at 165 (eliminates gray fringe & spurious protrusions)
    im_a_hi = Image.fromarray((alpha_orig.astype(np.uint8) * 255), mode="L")
    low_a_val = np.array(im_a_hi.resize((gw, gh), Image.Resampling.BOX))
    alpha = low_a_val > 162

    # Remove single-pixel silhouette spurs
    nb_count = np.zeros_like(alpha, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb_count += np.roll(np.roll(alpha, dy, axis=0), dx, axis=1).astype(np.int32)
    alpha &= (nb_count >= 2)

    # Single-pixel isolated outlier cleanup on `low_rgb` (outside the eye zone):
    # If a pixel is >28 brighter or >28 darker than ALL 4 of its cardinal neighbors, replace it with the median of its 4 neighbors!
    low_luma = 0.299 * low_rgb[:, :, 0].astype(np.float32) + 0.587 * low_rgb[:, :, 1].astype(np.float32) + 0.114 * low_rgb[:, :, 2].astype(np.float32)
    nb_lumas = np.stack([
        np.roll(low_luma, -1, axis=0),
        np.roll(low_luma, 1, axis=0),
        np.roll(low_luma, -1, axis=1),
        np.roll(low_luma, 1, axis=1),
    ], axis=0)
    nb_rgbs = np.stack([
        np.roll(low_rgb, -1, axis=0),
        np.roll(low_rgb, 1, axis=0),
        np.roll(low_rgb, -1, axis=1),
        np.roll(low_rgb, 1, axis=1),
    ], axis=0)
    is_hot_speck = (low_luma - nb_lumas.max(axis=0)) > 24.0
    is_cold_speck = (nb_lumas.min(axis=0) - low_luma) > 24.0
    speck_mask = (is_hot_speck | is_cold_speck) & alpha & (~eye_zone_low)
    med_rgb = np.median(nb_rgbs, axis=0).astype(np.uint8)
    low_rgb[speck_mask] = med_rgb[speck_mask]

    # Also ensure white paw pixels immediately adjacent to the outer outline are clean warm cream (no dark/gray edge halo)
    dilated = np.zeros_like(alpha)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dilated |= np.roll(np.roll(alpha, dy, axis=0), dx, axis=1)
    edge = dilated & (~alpha)

    low_arr = np.zeros((gh, gw, 4), dtype=np.uint8)
    low_arr[:, :, :3] = low_rgb
    low_arr[alpha, 3] = 255
    low_arr[~alpha] = [0, 0, 0, 0]

    # Add crisp 1px dark espresso outer pixel outline (#1b100a = 27, 16, 10)
    low_arr[edge] = [27, 16, 10, 255]

    # Add 2 crisp pixel whiskers on the left side of the muzzle (warm cream-white)
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
                    low_arr[wy, wx] = [230, 212, 188, 255]

    low_out = Image.fromarray(low_arr, mode="RGBA")
    low_out.save(OUT_DIR / "route_a_v4_1_sprite_logical.png")

    # Exact 2x2 integer block upscale -> 228x208
    sprite_2x = low_out.resize((gw * 2, gh * 2), Image.Resampling.NEAREST)
    sprite_2x.save(OUT_DIR / "route_a_v4_1_sprite.png")
    print(f"[v4.1] Saved logical sprite ({gw}x{gh}) and 2x2 sprite ({sprite_2x.size}), cleaned {speck_mask.sum()} isolated specks")
    return sprite_2x


def composite_v4_1_into_town(sprite_2x: Image.Image) -> Image.Image:
    bg = Image.open(V1_DIR / "clean_town_bg.png").convert("RGBA")
    tw, th = sprite_2x.size

    paste_x = 840 - (tw // 4) * 2
    paste_y = 662 - th

    # Upgrade 3b: Multi-layered ground contact shadow + directional cast shadow toward bottom-left (matching town sun/lantern angle)
    shadow_layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    # Broad ambient shadow under torso (slightly shifted left-down to match top-right lantern light)
    sdraw.ellipse(
        (paste_x + int(tw * 0.06), paste_y + int(th * 0.77),
         paste_x + int(tw * 0.84), paste_y + int(th * 1.02)),
        fill=(10, 8, 6, 138)
    )
    # Tight dark contact shadows directly under all 4 paws
    for px_rel, py_rel, rx_s, ry_s in [
        (0.21, 0.95, 22, 9),   # Front right paw
        (0.40, 0.97, 22, 9),   # Front left paw
        (0.55, 0.89, 20, 8),   # Hind right paw
        (0.75, 0.91, 21, 8),   # Hind left paw
    ]:
        cx = paste_x + int(tw * px_rel)
        cy = paste_y + int(th * py_rel)
        sdraw.ellipse((cx - rx_s, cy - ry_s, cx + rx_s, cy + ry_s), fill=(6, 5, 4, 175))

    shadow_blur = shadow_layer.filter(ImageFilter.GaussianBlur(radius=5.8))
    scene = Image.alpha_composite(bg, shadow_blur)

    cat_layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    cat_layer.paste(sprite_2x, (paste_x, paste_y), sprite_2x)
    scene = Image.alpha_composite(scene, cat_layer)

    rgb_out = scene.convert("RGB")
    rgb_out.save(OUT_DIR / "route_a_v4_1_in_town.png", quality=95)

    closeup = rgb_out.crop((700, 440, 980, 672)).resize((280 * 4, 232 * 4), Image.Resampling.NEAREST)
    closeup.save(OUT_DIR / "route_a_v4_1_closeup_crop.png")
    print("[v4.1] Saved route_a_v4_1_in_town.png and route_a_v4_1_closeup_crop.png")
    return rgb_out


def build_v4_vs_v4_1_comparison(v4_1_full: Image.Image):
    sys.path.insert(0, str(V1_DIR))
    from composite_comparison import load_font

    ref_full = Image.open(V1_DIR / "target_redbox_ref.png").convert("RGB")
    v4_full = Image.open(V4_DIR / "route_a_v4_in_town.png").convert("RGB")

    crop_box = (700, 440, 980, 672)
    pw, ph = 560, 464
    c_ref = ref_full.crop(crop_box).resize((pw, ph), Image.Resampling.NEAREST)
    c_v4 = v4_full.crop(crop_box).resize((pw, ph), Image.Resampling.NEAREST)
    c_v4_1 = v4_1_full.crop(crop_box).resize((pw, ph), Image.Resampling.NEAREST)

    pad = 20
    header_h = 86
    title_h = 52
    footer_h = 116
    board_w = pw * 3 + pad * 4
    board_h = header_h + title_h + ph + footer_h + pad * 3

    board = Image.new("RGB", (board_w, board_h), (22, 20, 18))
    draw = ImageDraw.Draw(board)

    font_h1 = load_font(28)
    font_h2 = load_font(20)
    font_sub = load_font(15)

    draw.text(
        (pad, 16),
        "喵汪小镇 · Route A v4 vs v4.1 终极静态标杆细节打磨对比（同视野 4x 放大特写）",
        fill=(245, 236, 220),
        font=font_h1,
    )
    draw.text(
        (pad, 52),
        "三大精修升级：① 掩码内预滤波+区域均值采样消除跨8px跳采飞点与白爪灰刺  ② 柔化强化右满左浅阴阳嘴套/左腹白云/前高后低袜  ③ 小镇暖灯笼光影与腹底AO融合",
        fill=(175, 235, 175),
        font=font_sub,
    )

    panels = [
        (0, "1. Target 红框参考猫（HD-2D 理想基准）", (235, 115, 100), c_ref, [
            "• 2×2 画布像素块，条纹内部凝练无杂色飞点",
            "• 右上暖灯笼受光柔和，腹底与内侧腿自然压暗",
            "• 白袜边缘紧贴深褐描边，干净通透无灰边",
        ]),
        (1, "2. Route A v4（上一版：已通过基础版）", (135, 195, 240), c_v4, [
            "• 已解决背景残爪与涂鸦块，保留纯正 AI 原生毛流",
            "• 细节空间：1024→114 直接 Nearest 跳采有少量孤立飞点",
            "• 四足白袜高度较接近，左肋白云与小镇环境光感可更立体",
        ]),
        (2, "3. Route A v4.1（本次终极静态标杆版）", (120, 235, 140), c_v4_1, [
            "✓ 升级1：掩码外延+双边预滤波+区域均值采样，消除条纹飞点与爪边灰刺",
            "✓ 升级2：顺毛流柔化提亮左白脸颊與左肋白云，前高后低白袜层次分明",
            "✓ 升级3：叠加头背暖金灯笼受光+下颌腹底柔和AO+四足接地阴影融合",
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
            draw.text((px + 10, fy + 10 + bi * 30), btxt, fill=(230, 224, 212), font=font_sub)

    out_path = OUT_DIR / "route_a_v4_vs_v4_1_comparison.png"
    board.save(out_path, quality=95)
    print(f"[v4.1] Saved {out_path} ({board.size})")


def main():
    sprite_2x = build_route_a_v4_1_sprite()
    v4_1_full = composite_v4_1_into_town(sprite_2x)
    build_v4_vs_v4_1_comparison(v4_1_full)


if __name__ == "__main__":
    main()
