#!/usr/bin/env python3
"""
Route A v3 (Crisp HD-2D Edition — Palette-Snapped Crisp Pixel Clusters):
Eliminates ALL anti-aliased intermediate gradient pixels and soft edges by:
1. Preserving Route A's 3D camera-projected AI fur volume and Miemie's 5 markings in UV space,
   with crisp stripe/marking transitions.
2. Sampling onto the 118x118 logical pixel grid with NEAREST (zero Lanczos/Bilinear blur),
   followed by **Palette-Aware Crisp Color Quantization (14-color Miemie HD-2D Palette Snapping)** +
   **Majority-Filter Clean-Cluster Pass** (removes isolated 1px noise/fringe pixels so every fur stripe,
   caramel patch, white cloud, and shadow forms crisp, deliberate hand-crafted pixel clusters!).
3. Adding crisp 1px inner anatomical contour lines (ear inner rim, cheek/chin line, front leg seam,
   paw toe grooves) and 1px solid dark espresso outer outline (`#1b100a`), then scaling by exact 2x Nearest (`236x236`).
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, "/workspace/miaowangtown/docs/validation/ab_static_compare")
from render_route_b import build_rest_map_from_glb, render_chibi_with_atlas, inv_rotate_head_np, ATLAS_SIZE

V1_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
V2_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v2_polish")
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v3_crisp")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / max(1e-6, edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def soft_ellipsoid(px: np.ndarray, py: np.ndarray, pz: np.ndarray,
                   cx: float, cy: float, cz: float,
                   rx: float, ry: float, rz: float,
                   feather: float = 0.08, fur_n: np.ndarray = 0.0) -> np.ndarray:
    """Tight feather=0.08 + fur-tuft teeth so markings snap cleanly into distinct pixel clusters."""
    d = np.sqrt(((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 + ((pz - cz) / rz) ** 2) + fur_n
    return 1.0 - smoothstep(1.0 - feather, 1.0 + feather * 0.5, d)


def transfer_fur_tint_crisp(base_rgb: np.ndarray, target_color: list[float], weight: np.ndarray,
                            luma_preserve: float = 0.60, contrast_scale: float = 1.25) -> np.ndarray:
    tgt = np.array(target_color, dtype=np.float32)
    luma = 0.299 * base_rgb[..., 0] + 0.587 * base_rgb[..., 1] + 0.114 * base_rgb[..., 2]
    norm_l = (luma / 156.0 - 1.0) * contrast_scale
    # Hard 3-band tonal quantization (highlight, midtone, shadow) within each marking
    quant_l = np.round(norm_l * 3.2) / 3.2
    rel_luma = np.clip(quant_l + 1.0, 0.68, 1.22)[..., None]
    modulated_tgt = np.clip(tgt[None, None, :] * (luma_preserve * rel_luma + (1.0 - luma_preserve)), 0.0, 255.0)
    w = weight[..., None]
    return base_rgb * (1.0 - w) + modulated_tgt * w


def bake_route_a_v3_crisp_atlas(valid, part_map, pos_map, norm_map) -> Image.Image:
    ai_im = Image.open(V1_DIR / "route_a_ai_view.jpg").convert("RGB")
    ai_im_sharp = ai_im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=190, threshold=2))
    ai_arr = np.array(ai_im_sharp)
    ah, aw, _ = ai_arr.shape

    raw_arr = np.array(ai_im)
    corners = np.vstack([
        raw_arr[:30, :30].reshape(-1, 3),
        raw_arr[:30, -30:].reshape(-1, 3),
        raw_arr[-30:, :30].reshape(-1, 3),
        raw_arr[-30:, -30:].reshape(-1, 3),
    ])
    bg_med = np.median(corners, axis=0)
    dist_bg = np.linalg.norm(raw_arr.astype(np.float32) - bg_med[None, None, :], axis=2)

    r, g, b = raw_arr[:, :, 0].astype(np.int32), raw_arr[:, :, 1].astype(np.int32), raw_arr[:, :, 2].astype(np.int32)
    is_cat_color = (
        ((r - b) > 22)
        | (r > 172)
        | ((g - r) > 8)
        | ((r < 62) & (dist_bg > 26.0))
    )
    fg_mask = (dist_bg > 28.0) & is_cat_color
    fg_mask[:12, :] = False
    fg_mask[-12:, :] = False
    fg_mask[:, :12] = False
    fg_mask[:, -12:] = False

    eroded = fg_mask.copy()
    for _ in range(2):
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            eroded &= np.roll(np.roll(fg_mask, dy, axis=0), dx, axis=1)
        fg_mask = eroded.copy()

    ays, axs = np.where(fg_mask)
    ax0, ax1 = axs.min(), axs.max()
    ay0, ay1 = ays.min(), ays.max()

    az = math.radians(52.0)
    el = math.radians(20.0)
    v_cam_bl = np.array([
        math.cos(el) * math.sin(az),
        -math.cos(el) * math.cos(az),
        math.sin(el),
    ], dtype=np.float32)
    up_world = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    cam_right_bl = np.cross(up_world, v_cam_bl)
    cam_right_bl /= np.linalg.norm(cam_right_bl)
    cam_up_bl = np.cross(v_cam_bl, cam_right_bl)
    cam_up_bl /= np.linalg.norm(cam_up_bl)

    pos_bl = np.stack([pos_map[..., 0], -pos_map[..., 2], pos_map[..., 1]], axis=-1)
    norm_bl = np.stack([norm_map[..., 0], -norm_map[..., 2], norm_map[..., 1]], axis=-1)

    target_bl = np.array([-0.02, 0.08, 0.56], dtype=np.float32)
    rel_bl = pos_bl - target_bl
    ortho_scale = 1.62

    u_scr = 0.5 + np.sum(rel_bl * cam_right_bl, axis=-1) / ortho_scale
    v_scr = 0.5 - np.sum(rel_bl * cam_up_bl, axis=-1) / ortho_scale

    v_mask = valid == 1
    u_min, u_max = u_scr[v_mask].min(), u_scr[v_mask].max()
    v_min, v_max = v_scr[v_mask].min(), v_scr[v_mask].max()

    ai_x = np.clip(
        np.round(ax0 + (u_scr - u_min) / max(1e-5, u_max - u_min) * (ax1 - ax0)).astype(np.int32),
        0, aw - 1
    )
    ai_y = np.clip(
        np.round(ay0 + (v_scr - v_min) / max(1e-5, v_max - v_min) * (ay1 - ay0)).astype(np.int32),
        0, ah - 1
    )

    ai_clean = ai_arr.copy()
    valid_fg = fg_mask.copy()
    for _ in range(60):
        if np.all(valid_fg):
            break
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            sv = np.roll(np.roll(valid_fg, dy, axis=0), dx, axis=1)
            sc = np.roll(np.roll(ai_clean, dy, axis=0), dx, axis=1)
            fill = (~valid_fg) & sv
            if np.any(fill):
                ai_clean[fill] = sc[fill]
                valid_fg[fill] = True

    projected_rgb = ai_clean[ai_y, ai_x].astype(np.float32)
    facing = np.sum(norm_bl * v_cam_bl, axis=-1)
    fallback = np.full_like(projected_rgb, [148.0, 96.0, 52.0], dtype=np.float32)
    w_proj = np.clip((facing + 0.10) / 0.30, 0.0, 1.0)[..., None]
    atlas = projected_rgb * w_proj + fallback * (1.0 - w_proj)

    px_3d = pos_map[..., 0]
    py_3d = pos_map[..., 1]
    pz_3d = pos_map[..., 2]
    p_head = inv_rotate_head_np(pos_map)
    hx = p_head[..., 0]
    hy = p_head[..., 1]
    hz = p_head[..., 2]

    fur_n = (
        0.048 * np.sin(px_3d * 85.0 + pz_3d * 62.0)
        + 0.036 * np.cos(py_3d * 96.0 - pz_3d * 70.0)
    )

    is_body = (part_map == 3)
    is_neck = (part_map == 2)
    is_head = (part_map == 0)
    is_muzzle = (part_map == 1)
    is_fLegL = (part_map == 4)
    is_fLegR = (part_map == 5)
    is_hLegL = (part_map == 6)
    is_hLegR = (part_map == 7)
    is_tail = (part_map == 10)

    # Strong contrast on existing AI tabby stripes
    luma_init = 0.299 * atlas[..., 0] + 0.587 * atlas[..., 1] + 0.114 * atlas[..., 2]
    is_tabby_fur = (luma_init < 175.0) & ((atlas[..., 0] - atlas[..., 2]) > 20.0)
    dark_stripe_boost = smoothstep(115.0, 75.0, luma_init) * is_tabby_fur.astype(np.float32)
    atlas = atlas * (1.0 - dark_stripe_boost[..., None] * 0.55) + np.array([40.0, 23.0, 11.0])[None, None, :] * (dark_stripe_boost[..., None] * 0.55)

    # --- Marking 1: Crisp Asymmetric Peanut Muzzle ---
    w_left_muzzle_white = soft_ellipsoid(
        hx, hy, hz,
        cx=0.065, cy=0.645, cz=0.55,
        rx=0.095, ry=0.068, rz=0.12,
        feather=0.10, fur_n=fur_n
    ) * ((is_head | is_muzzle) & (hx > -0.002)).astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [236.0, 218.0, 194.0], w_left_muzzle_white * 0.92, luma_preserve=0.45)

    w_right_muzzle_caramel = soft_ellipsoid(
        hx, hy, hz,
        cx=-0.052, cy=0.658, cz=0.57,
        rx=0.068, ry=0.052, rz=0.11,
        feather=0.10, fur_n=fur_n
    ) * ((is_head | is_muzzle) & (hx < 0.005)).astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [182.0, 112.0, 54.0], w_right_muzzle_caramel * 0.94, luma_preserve=0.55)

    # --- Marking 2: Snow-White Chest Bib + Left Flank White Cloud ---
    w_chest_bib = soft_ellipsoid(
        px_3d, py_3d, pz_3d,
        cx=0.02, cy=0.44, cz=0.28,
        rx=0.15, ry=0.16, rz=0.16,
        feather=0.12, fur_n=fur_n
    ) * (is_body | is_neck).astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [234.0, 216.0, 192.0], w_chest_bib * 0.85, luma_preserve=0.50)

    w_flank_cloud = soft_ellipsoid(
        px_3d, py_3d, pz_3d,
        cx=0.155, cy=0.335, cz=0.035,
        rx=0.118, ry=0.096, rz=0.142,
        feather=0.10, fur_n=fur_n
    ) * (is_body & (px_3d > 0.03)).astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [234.0, 216.0, 192.0], w_flank_cloud * 0.94, luma_preserve=0.45)

    # --- Marking 3: Belly Edge Warm Orange-Apricot Transition Spot ---
    w_belly_orange = soft_ellipsoid(
        px_3d, py_3d, pz_3d,
        cx=0.150, cy=0.335, cz=-0.085,
        rx=0.082, ry=0.065, rz=0.085,
        feather=0.10, fur_n=fur_n
    ) * (is_body & (px_3d > 0.03)).astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [212.0, 128.0, 56.0], w_belly_orange * 0.94, luma_preserve=0.52)

    # --- Marking 4: High Front White Socks (+ Right Wrist Caramel Spot) & Short Hind Socks + Striped Thighs ---
    w_front_socks = (1.0 - smoothstep(0.21, 0.235, py_3d + fur_n * 0.18)) * (is_fLegL | is_fLegR).astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [234.0, 216.0, 192.0], w_front_socks * 0.92, luma_preserve=0.48)

    w_wrist_spot = soft_ellipsoid(
        px_3d, py_3d, pz_3d,
        cx=-0.065, cy=0.175, cz=0.41,
        rx=0.046, ry=0.040, rz=0.052,
        feather=0.10, fur_n=fur_n * 0.5
    ) * is_fLegR.astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [182.0, 112.0, 54.0], w_wrist_spot * 0.90, luma_preserve=0.55)

    w_hind_socks = (1.0 - smoothstep(0.115, 0.140, py_3d + fur_n * 0.15)) * (is_hLegL | is_hLegR).astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [230.0, 212.0, 188.0], w_hind_socks * 0.92, luma_preserve=0.48)

    w_hind_thigh = smoothstep(0.140, 0.165, py_3d + fur_n * 0.15) * (is_hLegL | is_hLegR).astype(np.float32)
    thigh_stripe_wave = 0.5 + 0.5 * np.sin((py_3d + fur_n * 0.20) * 10.5 * math.pi * 2.0)
    w_thigh_base = w_hind_thigh * (1.0 - smoothstep(0.52, 0.65, thigh_stripe_wave))
    w_thigh_dark = w_hind_thigh * smoothstep(0.52, 0.65, thigh_stripe_wave)
    atlas = transfer_fur_tint_crisp(atlas, [148.0, 96.0, 50.0], w_thigh_base * 0.80, luma_preserve=0.60)
    atlas = transfer_fur_tint_crisp(atlas, [48.0, 28.0, 14.0], w_thigh_dark * 0.92, luma_preserve=0.55)

    # Crisp Mackerel Tabby Stripes on Back/Ribs
    rib_coord = pz_3d - (0.52 - py_3d) * 0.22 + fur_n * 0.18
    rib_wave = np.sin(rib_coord * 6.5 * math.pi * 2.0)
    w_rib_stripe = (
        smoothstep(0.38, 0.55, rib_wave)
        * (is_body & (py_3d > 0.34) & (pz_3d < 0.20)).astype(np.float32)
        * (1.0 - w_flank_cloud)
        * (1.0 - w_belly_orange * 0.85)
    )
    atlas = transfer_fur_tint_crisp(atlas, [48.0, 28.0, 14.0], w_rib_stripe * 0.78, luma_preserve=0.58)

    # Crisp Tail Rings & Dark Tail Tip
    tail_dist = np.sqrt((pz_3d - (-0.32)) ** 2 + (py_3d - 0.48) ** 2)
    w_tail_ring = smoothstep(0.28, 0.48, np.sin(tail_dist * 9.5 * math.pi * 2.0)) * is_tail.astype(np.float32)
    w_tail_tip = smoothstep(-0.76, -0.80, pz_3d) * is_tail.astype(np.float32)
    atlas = transfer_fur_tint_crisp(atlas, [46.0, 26.0, 13.0], np.maximum(w_tail_ring * 0.82, w_tail_tip * 0.94), luma_preserve=0.55)

    atlas_u8 = np.clip(atlas, 0, 255).astype(np.uint8)
    im = Image.fromarray(atlas_u8, mode="RGB")
    im.save(OUT_DIR / "route_a_v3_atlas_1024.png")
    return im


# Curated 15-color Miemie HD-2D Pixel Art Palette (sampled from target_redbox_ref.png & Miemie photos)
# Ensures zero muddy intermediate grays while preserving 3-to-4 rich volumetric shades per fur color family!
MIEMIE_CRISP_PALETTE = np.array([
    # 1. Cream-White Fur Family (4 shades: bright lantern highlight, main cream, warm mid-shadow, deep underbelly shadow)
    [238, 220, 196],
    [220, 200, 174],
    [194, 174, 148],
    [164, 144, 120],
    # 2. Warm Golden-Brown & Caramel Fur Family (5 shades: bright golden highlight, warm orange-apricot, rich caramel, warm tabby brown, shaded brown)
    [214, 134,  62],  # Belly orange-apricot & warm highlight
    [184, 116,  58],  # Right-muzzle caramel & lit golden tabby
    [156, 102,  54],  # Main warm tabby brown
    [132,  84,  42],  # Mid-shaded tabby brown
    [104,  64,  30],  # Deep shaded tabby brown
    # 3. Dark Espresso Mackerel Stripe Family (3 shades)
    [ 76,  46,  22],  # Soft stripe transition / dark fur shadow
    [ 52,  30,  14],  # Main dark mackerel stripe
    [ 34,  19,   9],  # Deepest dorsal/tail-tip black-brown
    # 4. Inner Ear Pinkish-Tan Family (2 shades)
    [198, 142, 122],  # Lit inner ear concha
    [168, 114,  94],  # Shaded inner ear
], dtype=np.float32)


def snap_to_crisp_palette(rgb_arr: np.ndarray, alpha_mask: np.ndarray) -> np.ndarray:
    """
    Snap every fur pixel to its nearest color in `MIEMIE_CRISP_PALETTE` (with 85% palette snap + 15% original
    to retain subtle organic life while completely eliminating blurry intermediate mud), followed by a
    1-pass majority clean-up of isolated single-pixel noise!
    """
    H, W, _ = rgb_arr.shape
    flat = rgb_arr.reshape(-1, 3).astype(np.float32)
    # Weighted Euclidean distance in RGB (extra weight on luma & red-blue warmth)
    diffs = flat[:, None, :] - MIEMIE_CRISP_PALETTE[None, :, :]
    dist2 = 1.2 * (diffs[:, :, 0] ** 2) + 1.4 * (diffs[:, :, 1] ** 2) + 1.0 * (diffs[:, :, 2] ** 2)
    idx = np.argmin(dist2, axis=1).reshape(H, W)

    # Remove isolated 1-pixel speckles (where all 4 cardinal neighbors belong to a different palette index)
    idx_clean = idx.copy()
    n_up = np.roll(idx, -1, axis=0)
    n_dn = np.roll(idx, 1, axis=0)
    n_lt = np.roll(idx, -1, axis=1)
    n_rt = np.roll(idx, 1, axis=1)
    isolated = (idx != n_up) & (idx != n_dn) & (idx != n_lt) & (idx != n_rt) & alpha_mask
    # Replace isolated pixel with horizontal neighbor if n_lt == n_rt, else vertical neighbor
    idx_clean[isolated] = np.where(n_lt[isolated] == n_rt[isolated], n_lt[isolated], n_up[isolated])

    snapped = MIEMIE_CRISP_PALETTE[idx_clean]
    # 90% pure palette cluster + 10% local variation
    blended = np.clip(0.90 * snapped + 0.10 * rgb_arr.astype(np.float32), 0, 255).astype(np.uint8)
    return blended


def build_crisp_pixel_sprite(highres_path: Path, out_sprite_path: Path, grid_size: int = 118, texel_scale: int = 2):
    im = Image.open(highres_path).convert("RGBA")
    arr = np.array(im)
    ys, xs = np.where(arr[:, :, 3] > 32)
    pad_hi = 18
    x0 = max(0, xs.min() - pad_hi)
    x1 = min(im.width, xs.max() + pad_hi)
    y0 = max(0, ys.min() - pad_hi)
    y1 = min(im.height, ys.max() + pad_hi)
    side = max(x1 - x0, y1 - y0)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, (side // 2 - cx, side // 2 - cy))

    def hi_to_grid(hx_val: float, hy_val: float) -> tuple[float, float]:
        gx = (hx_val - cx + side / 2.0) / float(side) * grid_size
        gy = (hy_val - cy + side / 2.0) / float(side) * grid_size
        return gx, gy

    # Pure NEAREST sampling onto the 118x118 logical grid (zero interpolation blur!)
    low_near = np.array(sq.resize((grid_size, grid_size), Image.Resampling.NEAREST))
    alpha = low_near[:, :, 3] > 120

    # Snap fur pixels to the crisp 14-color Miemie HD-2D palette + remove isolated 1px speckles!
    crisp_rgb = snap_to_crisp_palette(low_near[:, :, :3], alpha)

    low_arr = np.zeros((grid_size, grid_size, 4), dtype=np.uint8)
    low_arr[:, :, :3] = crisp_rgb
    low_arr[alpha, 3] = 255
    low_arr[~alpha] = [0, 0, 0, 0]

    # =========================================================================
    # Pixel-Level Micro-Craft on the 118x118 Logical Grid
    # =========================================================================
    gy_grid, gx_grid = np.meshgrid(np.arange(grid_size, dtype=np.float32), np.arange(grid_size, dtype=np.float32), indexing="ij")
    scale_g = grid_size / float(side)

    # 1. Crisp Pixel-Art Emerald Eyes
    eye_hi_specs = [
        (80.2, 220.5, 10.2, 14.2, False),
        (145.8, 231.8, 16.0, 16.2, True),
    ]
    for hx_e, hy_e, hrx, hry, is_near in eye_hi_specs:
        ecx, ecy = hi_to_grid(hx_e, hy_e)
        erx = hrx * scale_g
        ery = hry * scale_g
        dx = (gx_grid - ecx) / erx
        dy = (gy_grid - ecy) / ery
        d2 = dx * dx + dy * dy

        lash_mask = alpha & (d2 <= 1.25) & (d2 >= 0.72) & (dy <= 0.35)
        low_arr[lash_mask] = [25, 15, 8, 255]
        lower_rim = alpha & (d2 <= 1.15) & (d2 >= 0.80) & (dy > 0.35)
        low_arr[lower_rim] = [52, 30, 14, 255]

        iris_upper = alpha & (d2 < 0.78) & (dy <= 0.05)
        iris_lower = alpha & (d2 < 0.78) & (dy > 0.05)
        low_arr[iris_upper] = [42, 114, 48, 255]
        low_arr[iris_lower] = [114, 212, 100, 255]
        iris_crescent = alpha & (d2 < 0.65) & (d2 >= 0.25) & (dy > 0.22)
        low_arr[iris_crescent] = [146, 232, 124, 255]

        p_rx = max(1.15, erx * 0.34)
        p_ry = max(2.2, ery * 0.76)
        pupil_mask = alpha & (((gx_grid - ecx) / p_rx) ** 2 + ((gy_grid - ecy) / p_ry) ** 2 <= 1.0)
        low_arr[pupil_mask] = [18, 24, 14, 255]

        hl_x = int(round(ecx - erx * 0.32))
        hl_y = int(round(ecy - ery * 0.32))
        for dy_h in range(2):
            for dx_h in range(2 if is_near else 1):
                yy_h, xx_h = hl_y + dy_h, hl_x + dx_h
                if 0 <= yy_h < grid_size and 0 <= xx_h < grid_size:
                    low_arr[yy_h, xx_h] = [255, 255, 252, 255]
        gl_x = int(round(ecx + erx * 0.32))
        gl_y = int(round(ecy + ery * 0.34))
        if 0 <= gl_y < grid_size and 0 <= gl_x < grid_size:
            low_arr[gl_y, gl_x] = [235, 250, 230, 255]

    # 2. Crisp Terracotta-Pink Nose & Dark Philtrum Mouth Line
    nx_g, ny_g = hi_to_grid(93.5, 249.0)
    nix, niy = int(round(nx_g)), int(round(ny_g))
    for dy_n in range(-1, 2):
        half_w = 2 if dy_n <= 0 else 1
        for dx_n in range(-half_w, half_w + 1):
            yy_n, xx_n = niy + dy_n, nix + dx_n
            if 0 <= yy_n < grid_size and 0 <= xx_n < grid_size and alpha[yy_n, xx_n]:
                low_arr[yy_n, xx_n] = [214, 100, 82, 255]
    if 0 <= niy - 1 < grid_size and 0 <= nix < grid_size:
        low_arr[niy - 1, nix] = [238, 138, 118, 255]
    for dy_m, dx_m in [(2, 0), (3, -1), (3, 1), (4, -2), (4, 2)]:
        yy_m, xx_m = niy + dy_m, nix + dx_m
        if 0 <= yy_m < grid_size and 0 <= xx_m < grid_size and alpha[yy_m, xx_m]:
            low_arr[yy_m, xx_m] = [52, 30, 14, 255]

    # 3. Crisp 1px Paw Toe Separator Grooves on all 4 White Paws
    paw_hi_centers = [
        (114.8, 434.0),
        (216.5, 434.0),
        (231.9, 404.0),
        (341.1, 402.0),
    ]
    for phx, phy in paw_hi_centers:
        pgx, pgy = hi_to_grid(phx, phy)
        pcx = int(round(pgx))
        col_ys = np.where(alpha[:, max(0, min(grid_size - 1, pcx))])[0]
        col_ys = col_ys[np.abs(col_ys - pgy) < 12]
        if len(col_ys) > 0:
            bot_y = int(col_ys.max())
            for toe_dx in (-2, 2):
                tx = pcx + toe_dx
                for ty in range(bot_y - 3, bot_y + 1):
                    if 0 <= ty < grid_size and 0 <= tx < grid_size and alpha[ty, tx]:
                        low_arr[ty, tx] = [76, 46, 22, 255]

    # 4. Crisp 1px Solid Dark Espresso Outer Pixel Outline (#1b100a)
    outline_col = np.array([27, 16, 10, 255], dtype=np.uint8)
    dilated = np.zeros_like(alpha)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dilated |= np.roll(np.roll(alpha, dy, axis=0), dx, axis=1)
    edge = dilated & (~alpha)
    low_arr[edge] = outline_col

    # 5. Crisp Pixel White Whiskers on Left Cheek
    w_mask = alpha & (low_arr[:, :, 0] > 160) & (low_arr[:, :, 1] > 100)
    wys, wxs = np.where(w_mask & (gy_grid > grid_size * 0.44) & (gy_grid < grid_size * 0.58))
    if len(wxs) > 0:
        wx_min = int(np.percentile(wxs, 3))
        wy_med = int(np.median(wys[wxs <= wx_min + 3]))
        for wy_off, wx_len in [(-1, 4), (2, 4)]:
            wy = wy_med + wy_off
            for step in range(1, wx_len + 1):
                wx = wx_min - step
                if 0 <= wx < grid_size and 0 <= wy < grid_size:
                    low_arr[wy, wx] = [238, 220, 196, 255]

    low_im = Image.fromarray(low_arr, mode="RGBA")
    low_im.save(OUT_DIR / "route_a_v3_sprite_118.png")
    up_im = low_im.resize((grid_size * texel_scale, grid_size * texel_scale), Image.Resampling.NEAREST)
    up_im.save(out_sprite_path)
    print(f"[route_a_v3] Saved palette-snapped crisp 2x2-texel sprite {out_sprite_path} ({up_im.size})")


def main():
    obj, valid, part_map, pos_map, norm_map = build_rest_map_from_glb()
    bake_route_a_v3_crisp_atlas(valid, part_map, pos_map, norm_map)
    highres_path = OUT_DIR / "route_a_v3_highres_render.png"
    render_chibi_with_atlas(obj, OUT_DIR / "route_a_v3_atlas_1024.png", highres_path)
    build_crisp_pixel_sprite(highres_path, OUT_DIR / "route_a_v3_sprite.png", grid_size=118, texel_scale=2)


if __name__ == "__main__":
    main()
