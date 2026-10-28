#!/usr/bin/env python3
"""
Route A v2: Frequency-Preserving Polish of Route A (AI View Generation + 3D Camera Projection UV Bake).
100% preserves the soft painterly fur texture, volume shading, and natural tabby flow of Route A (`route_a_ai_view.jpg`),
while applying soft, feathered, high-frequency-preserving color/luma modulations in UV / 3D surface space to
precisely match Miemie's 5 signature markings and crisp emerald-green eyes:

  1. Marking 1 (Asymmetric Peanut Muzzle — Right caramel, Left white):
     - Right muzzle (`-X` in head space, screen-left of nose): warm caramel-peanut tint (`#c9854c`) modulated by AI fur luma.
     - Left muzzle (`+X` in head space, screen-right cheek): clean cream-white fur lift (`#f0e2ce`) modulated by AI fur luma.
  2. Marking 2 (Snow-white Chest Bib + Left Flank White Cloud):
     - Smoothly extends the chest bib into a soft-edged white cloud patch rising up the left flank (`+X` mid-belly/flank),
       preserving every underlying AI fur brushstroke and shadow gradient.
  3. Marking 3 (Belly Edge Warm Orange-Apricot Transition Spot):
     - Soft warm apricot-orange fur tint (`#dc8e4e`) along the upper-posterior border of the left flank white cloud
       and lower belly transition, matching `miemie_ref_08_left_side_orange_belly.jpg`.
  4. Marking 4 (Four White Socks — High Front Socks + Right Wrist Caramel Spot, Short Hind Socks + Striped Thighs):
     - Raises the front leg white socks above the knee (`y < 0.235`) with a subtle warm caramel spot on the inner right wrist;
       keeps hind socks short at the ankle (`y < 0.145`) with rich dark tabby stripes on the hind thighs.
  5. Marking 5 (Vivid Emerald-Green Almond Eyes + Terracotta-Pink Nose):
     - Enhances iris saturation & clarity (deep emerald upper iris -> luminous jade-green lower crescent),
       deepens the vertical slit pupil & upper dark brown lash line, and places crisp white catchlights
       (top-left primary + bottom-right secondary) and a warm terracotta-pink nose (`#d46552`).
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
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v2_polish")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / max(1e-6, edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def soft_ellipsoid(px: np.ndarray, py: np.ndarray, pz: np.ndarray,
                   cx: float, cy: float, cz: float,
                   rx: float, ry: float, rz: float,
                   feather: float = 0.35, fur_n: np.ndarray = 0.0) -> np.ndarray:
    """Returns a soft [0..1] weight mask inside an ellipsoid with organic fur-tuft feathering."""
    d = np.sqrt(((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 + ((pz - cz) / rz) ** 2) + fur_n
    return 1.0 - smoothstep(1.0 - feather, 1.0 + feather * 0.5, d)


def transfer_fur_tint(base_rgb: np.ndarray, target_color: list[float], weight: np.ndarray,
                      luma_preserve: float = 0.75, contrast_scale: float = 1.0) -> np.ndarray:
    """
    Frequency-preserving color/luma transfer:
    Re-tints `base_rgb` toward `target_color` while preserving the local AI fur luminance variations
    (brushstrokes, hair strands, and soft 3D volume shading).
    """
    tgt = np.array(target_color, dtype=np.float32)
    luma = 0.299 * base_rgb[..., 0] + 0.587 * base_rgb[..., 1] + 0.114 * base_rgb[..., 2]
    # Normalize local luma around mean fur luma (~155) so dark fur crevices stay darker and highlights stay brighter
    rel_luma = np.clip((luma / 158.0 - 1.0) * contrast_scale + 1.0, 0.58, 1.28)[..., None]
    modulated_tgt = np.clip(tgt[None, None, :] * (luma_preserve * rel_luma + (1.0 - luma_preserve)), 0.0, 255.0)
    w = weight[..., None]
    return base_rgb * (1.0 - w) + modulated_tgt * w


def bake_route_a_v2_atlas(valid, part_map, pos_map, norm_map) -> Image.Image:
    # 1. Start from the exact Route A v1 camera-projected AI view texture
    ai_im = Image.open(V1_DIR / "route_a_ai_view.jpg").convert("RGB")
    ai_arr = np.array(ai_im)
    ah, aw, _ = ai_arr.shape

    corners = np.vstack([
        ai_arr[:30, :30].reshape(-1, 3),
        ai_arr[:30, -30:].reshape(-1, 3),
        ai_arr[-30:, :30].reshape(-1, 3),
        ai_arr[-30:, -30:].reshape(-1, 3),
    ])
    bg_med = np.median(corners, axis=0)
    dist_bg = np.linalg.norm(ai_arr.astype(np.float32) - bg_med[None, None, :], axis=2)

    r, g, b = ai_arr[:, :, 0].astype(np.int32), ai_arr[:, :, 1].astype(np.int32), ai_arr[:, :, 2].astype(np.int32)
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

    # =========================================================================
    # 2. Frequency-Preserving Polish of Miemie's 5 Signature Markings in 3D/UV Space
    # =========================================================================
    px_3d = pos_map[..., 0]
    py_3d = pos_map[..., 1]
    pz_3d = pos_map[..., 2]
    p_head = inv_rotate_head_np(pos_map)
    hx = p_head[..., 0]
    hy = p_head[..., 1]
    hz = p_head[..., 2]

    # High-frequency multi-scale fur strand modulation so all soft masks have feathery hair-tuft edges
    fur_n = (
        0.065 * np.sin(px_3d * 72.0 + pz_3d * 54.0)
        + 0.045 * np.cos(py_3d * 88.0 - pz_3d * 62.0)
        + 0.030 * np.sin(hx * 110.0 + hy * 95.0)
    )

    is_body = (part_map == 3)
    is_neck = (part_map == 2)
    is_head = (part_map == 0)
    is_muzzle = (part_map == 1)
    is_fLegL = (part_map == 4)
    is_fLegR = (part_map == 5)
    is_hLegL = (part_map == 6)
    is_hLegR = (part_map == 7)

    # --- Marking 1: Asymmetric Peanut Muzzle ("右满暖棕、左浅奶油白") ---
    # First ensure the left muzzle & lower cheek (+X, screen right of nose) is clean, bright cream-white fur
    w_left_muzzle_white = soft_ellipsoid(
        hx, hy, hz,
        cx=0.065, cy=0.645, cz=0.55,
        rx=0.095, ry=0.068, rz=0.12,
        feather=0.42, fur_n=fur_n
    ) * ((is_head | is_muzzle) & (hx > -0.005)).astype(np.float32)
    atlas = transfer_fur_tint(atlas, [238.0, 222.0, 200.0], w_left_muzzle_white * 0.82, luma_preserve=0.55, contrast_scale=0.6)

    # Now sculpt Miemie's signature right-muzzle (`-X`, screen left of nose/mouth) warm caramel-peanut patch!
    w_right_muzzle_caramel = soft_ellipsoid(
        hx, hy, hz,
        cx=-0.052, cy=0.658, cz=0.57,
        rx=0.068, ry=0.052, rz=0.11,
        feather=0.38, fur_n=fur_n
    ) * ((is_head | is_muzzle) & (hx < 0.008)).astype(np.float32)
    atlas = transfer_fur_tint(atlas, [182.0, 112.0, 56.0], w_right_muzzle_caramel * 0.88, luma_preserve=0.68, contrast_scale=0.8)

    # Subtle darker whisker-pad accent dots inside the right caramel patch
    w_right_whisker_core = soft_ellipsoid(
        hx, hy, hz,
        cx=-0.058, cy=0.652, cz=0.58,
        rx=0.032, ry=0.024, rz=0.08,
        feather=0.40, fur_n=fur_n * 0.5
    ) * ((is_head | is_muzzle) & (hx < -0.015)).astype(np.float32)
    atlas = transfer_fur_tint(atlas, [132.0, 76.0, 34.0], w_right_whisker_core * 0.65, luma_preserve=0.75)

    # --- Marking 2: Snow-White Chest Bib + Left Flank White Cloud ("雪白围脖 + 左肋腹白云斑") ---
    # Enhance the snow-white chest bib so it connects cleanly down to the belly
    w_chest_bib = soft_ellipsoid(
        px_3d, py_3d, pz_3d,
        cx=0.02, cy=0.44, cz=0.28,
        rx=0.15, ry=0.16, rz=0.16,
        feather=0.45, fur_n=fur_n
    ) * (is_body | is_neck).astype(np.float32)
    atlas = transfer_fur_tint(atlas, [235.0, 218.0, 196.0], w_chest_bib * 0.70, luma_preserve=0.65, contrast_scale=0.65)

    # Left flank (+X, facing camera!) upward white cloud patch breaking up the lower rib stripes
    w_flank_cloud = soft_ellipsoid(
        px_3d, py_3d, pz_3d,
        cx=0.155, cy=0.335, cz=0.035,
        rx=0.12, ry=0.098, rz=0.145,
        feather=0.42, fur_n=fur_n * 1.2
    ) * (is_body & (px_3d > 0.03)).astype(np.float32)
    atlas = transfer_fur_tint(atlas, [232.0, 214.0, 190.0], w_flank_cloud * 0.86, luma_preserve=0.55, contrast_scale=0.55)

    # --- Marking 3: Belly Edge Warm Orange-Apricot Transition Spot ("腹缘小暖橘过渡斑") ---
    # Placed right at the posterior/upper border of the left flank white cloud & lower belly edge
    w_belly_orange = soft_ellipsoid(
        px_3d, py_3d, pz_3d,
        cx=0.150, cy=0.335, cz=-0.085,
        rx=0.085, ry=0.068, rz=0.088,
        feather=0.45, fur_n=fur_n
    ) * (is_body & (px_3d > 0.03)).astype(np.float32)
    atlas = transfer_fur_tint(atlas, [216.0, 134.0, 64.0], w_belly_orange * 0.88, luma_preserve=0.62, contrast_scale=0.75)

    # --- Marking 4: High Front White Socks (+ Right Wrist Caramel Spot) & Short Hind Ankle Socks + Hind Thigh Stripes ---
    # Front legs: over-the-knee white socks up to y = 0.235
    w_front_socks = (1.0 - smoothstep(0.19, 0.255, py_3d + fur_n * 0.25)) * (is_fLegL | is_fLegR).astype(np.float32)
    atlas = transfer_fur_tint(atlas, [232.0, 215.0, 192.0], w_front_socks * 0.82, luma_preserve=0.60, contrast_scale=0.60)

    # Miemie's right front wrist inner caramel spot
    w_wrist_spot = soft_ellipsoid(
        px_3d, py_3d, pz_3d,
        cx=-0.065, cy=0.175, cz=0.41,
        rx=0.048, ry=0.042, rz=0.055,
        feather=0.40, fur_n=fur_n * 0.5
    ) * is_fLegR.astype(np.float32)
    atlas = transfer_fur_tint(atlas, [184.0, 116.0, 62.0], w_wrist_spot * 0.80, luma_preserve=0.68)

    # Hind legs: short ankle white socks (y < 0.135); above y=0.155 ensure warm brown tabby thigh ("花裤衩")
    w_hind_socks = (1.0 - smoothstep(0.105, 0.150, py_3d + fur_n * 0.20)) * (is_hLegL | is_hLegR).astype(np.float32)
    atlas = transfer_fur_tint(atlas, [230.0, 212.0, 188.0], w_hind_socks * 0.82, luma_preserve=0.60, contrast_scale=0.60)

    # Reinforce hind thigh tabby stripes ("花裤衩") above the short hind sock so any excessive white on upper hind leg becomes rich tabby
    w_hind_thigh = smoothstep(0.145, 0.195, py_3d + fur_n * 0.2) * (is_hLegL | is_hLegR).astype(np.float32)
    thigh_stripe_wave = 0.5 + 0.5 * np.sin((py_3d + fur_n * 0.25) * 10.5 * math.pi * 2.0)
    w_thigh_base = w_hind_thigh * (1.0 - smoothstep(0.55, 0.78, thigh_stripe_wave))
    w_thigh_dark = w_hind_thigh * smoothstep(0.55, 0.78, thigh_stripe_wave)
    atlas = transfer_fur_tint(atlas, [150.0, 98.0, 54.0], w_thigh_base * 0.65, luma_preserve=0.72)
    atlas = transfer_fur_tint(atlas, [56.0, 33.0, 17.0], w_thigh_dark * 0.78, luma_preserve=0.68)

    # Subtle reinforcement of dorsal/rib mackerel tabby contrast so stripes read crisply after pixelation
    rib_coord = pz_3d - (0.52 - py_3d) * 0.22 + fur_n * 0.25
    rib_wave = np.sin(rib_coord * 6.4 * math.pi * 2.0)
    w_rib_stripe = (
        smoothstep(0.35, 0.70, rib_wave)
        * (is_body & (py_3d > 0.34) & (pz_3d < 0.20)).astype(np.float32)
        * (1.0 - w_flank_cloud)
        * (1.0 - w_belly_orange * 0.7)
    )
    atlas = transfer_fur_tint(atlas, [54.0, 32.0, 16.0], w_rib_stripe * 0.45, luma_preserve=0.78)

    atlas_u8 = np.clip(atlas, 0, 255).astype(np.uint8)
    im = Image.fromarray(atlas_u8, mode="RGB")
    im.save(OUT_DIR / "route_a_v2_atlas_1024.png")
    return im


def polish_highres_eyes_and_nose(highres_path: Path):
    """
    In the 512x512 rendered view (`route_a_v2_highres_render.png`), refine the emerald-green eyes
    and terracotta-pink nose with soft-feathered multi-layer glazing so that when downsampled to
    92x92 pixel art, the eyes have unmistakable emerald depth, vertical slit pupils, dark upper lash lines,
    and crisp white catchlights — while blending seamlessly into the surrounding AI fur!
    """
    im = Image.open(highres_path).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

    # Detect existing green iris pixels from the AI projection for both eyes:
    # Far/right eye (screen left): x in [66..95], y in [200..238]
    # Near/left eye (screen right): x in [125..166], y in [210..252]
    yy, xx = np.meshgrid(np.arange(512, dtype=np.float32), np.arange(512, dtype=np.float32), indexing="ij")

    eye_specs = [
        # (cx, cy, rx, ry, pupil_rx, pupil_ry, hl1_dx, hl1_dy, hl1_r, hl2_dx, hl2_dy, hl2_r)
        (80.2, 220.5, 10.5, 14.5, 3.6, 10.5, -3.2, -4.8, 3.4, 3.2, 5.2, 1.8),   # Far eye (screen left)
        (145.8, 231.8, 16.2, 16.5, 5.2, 12.2, -5.0, -5.2, 4.4, 5.2, 5.8, 2.3),  # Near eye (screen right)
    ]

    for cx, cy, rx, ry, prx, pry, h1x, h1y, h1r, h2x, h2y, h2r in eye_specs:
        dx = (xx - cx) / rx
        dy = (yy - cy) / ry
        d = np.sqrt(dx * dx + dy * dy)

        # 1. Dark espresso-brown upper eyelid lash arch (`#1e110a`)
        lash_d = np.sqrt(dx * dx + ((yy - (cy - 1.5)) / (ry * 1.06)) ** 2)
        w_lash = (1.0 - smoothstep(0.88, 1.16, lash_d)) * smoothstep(0.76, 0.94, d) * (dy < 0.35).astype(np.float32)
        for c_i, val in enumerate([28.0, 16.0, 10.0]):
            arr[:, :, c_i] = arr[:, :, c_i] * (1.0 - w_lash * 0.85) + val * (w_lash * 0.85)

        # 2. Vivid Emerald Iris Gradient (deep forest emerald top -> bright luminous jade-emerald lower crescent)
        w_iris = 1.0 - smoothstep(0.78, 0.98, d)
        grad_t = np.clip((dy + 0.7) / 1.4, 0.0, 1.0)
        # Upper iris: (46, 118, 52), Lower bright crescent: (126, 218, 104)
        iris_r = 46.0 * (1.0 - grad_t) + 126.0 * grad_t
        iris_g = 118.0 * (1.0 - grad_t) + 218.0 * grad_t
        iris_b = 52.0 * (1.0 - grad_t) + 104.0 * grad_t
        arr[:, :, 0] = arr[:, :, 0] * (1.0 - w_iris * 0.78) + iris_r * (w_iris * 0.78)
        arr[:, :, 1] = arr[:, :, 1] * (1.0 - w_iris * 0.78) + iris_g * (w_iris * 0.78)
        arr[:, :, 2] = arr[:, :, 2] * (1.0 - w_iris * 0.78) + iris_b * (w_iris * 0.78)

        # 3. Crisp Vertical Slit Pupil (`#121a10`)
        pd = np.sqrt(((xx - cx) / prx) ** 2 + ((yy - cy) / pry) ** 2)
        w_pupil = 1.0 - smoothstep(0.72, 1.02, pd)
        for c_i, val in enumerate([16.0, 24.0, 14.0]):
            arr[:, :, c_i] = arr[:, :, c_i] * (1.0 - w_pupil * 0.92) + val * (w_pupil * 0.92)

        # 4. Crisp Pure-White Top-Left Catchlight + Subtle Bottom-Right Secondary Glint
        hd1 = np.sqrt((xx - (cx + h1x)) ** 2 + (yy - (cy + h1y)) ** 2) / h1r
        w_hl1 = 1.0 - smoothstep(0.65, 1.05, hd1)
        hd2 = np.sqrt((xx - (cx + h2x)) ** 2 + (yy - (cy + h2y)) ** 2) / h2r
        w_hl2 = (1.0 - smoothstep(0.60, 1.05, hd2)) * 0.85
        w_hl = np.maximum(w_hl1, w_hl2)
        for c_i, val in enumerate([255.0, 254.0, 250.0]):
            arr[:, :, c_i] = arr[:, :, c_i] * (1.0 - w_hl) + val * w_hl

    # 5. Terracotta-Pink Nose Leather (`#d46856`) with soft nostril/philtrum definition at (93, 249)
    nx_c, ny_c = 93.5, 249.0
    nd = np.sqrt(((xx - nx_c) / 8.5) ** 2 + ((yy - ny_c) / 5.2) ** 2)
    w_nose = (1.0 - smoothstep(0.65, 1.08, nd)) * (a > 128).astype(np.float32)
    for c_i, val in enumerate([214.0, 104.0, 86.0]):
        arr[:, :, c_i] = arr[:, :, c_i] * (1.0 - w_nose * 0.82) + val * (w_nose * 0.82)

    out_im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")
    out_im.save(highres_path)


def pixelate_and_outline_v2(highres_path: Path, out_sprite_path: Path, grid_size: int = 92):
    """
    Downsample the polished 3D render to a 92x92 HD-2D pixel grid using hybrid Box-filtered color
    (for silky-smooth fur transitions) + crisp Nearest-neighbor eye catchlights, surrounded by a
    clean 1px dark brown-black pixel outline (`#1b100a`) and 2px pixel white whiskers.
    """
    im = Image.open(highres_path).convert("RGBA")
    arr = np.array(im)
    ys, xs = np.where(arr[:, :, 3] > 32)
    pad_hi = 26
    x0 = max(0, xs.min() - pad_hi)
    x1 = min(im.width, xs.max() + pad_hi)
    y0 = max(0, ys.min() - pad_hi)
    y1 = min(im.height, ys.max() + pad_hi)
    side = max(x1 - x0, y1 - y0)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, (side // 2 - cx, side // 2 - cy))

    # Hybrid resample: BILINEAR/BOX for rich painterly fur volume + NEAREST for crisp eye highlights/pupils
    low_box = np.array(sq.resize((grid_size, grid_size), Image.Resampling.BILINEAR))
    low_near = np.array(sq.resize((grid_size, grid_size), Image.Resampling.NEAREST))

    alpha = low_near[:, :, 3] > 115
    low_arr = low_box.copy()
    # Keep eye region & nose super crisp using `low_near`
    is_eye_or_hl = (
        ((low_near[:, :, 1].astype(int) - low_near[:, :, 0].astype(int)) > 12)
        | (low_near[:, :, 0] > 235)
        | ((low_near[:, :, 0] < 38) & (low_near[:, :, 1] < 38))
    )
    low_arr[is_eye_or_hl] = low_near[is_eye_or_hl]

    low_arr[~alpha] = [0, 0, 0, 0]
    low_arr[alpha, 3] = 255

    # 1px outer pixel outline (#1b100a = 27, 16, 10)
    outline_col = np.array([27, 16, 10, 255], dtype=np.uint8)
    dilated = np.zeros_like(alpha)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dilated |= np.roll(np.roll(alpha, dy, axis=0), dx, axis=1)
    edge = dilated & (~alpha)
    low_arr[edge] = outline_col

    # Add 2 crisp pixel whiskers on the left side of muzzle
    w_mask = alpha & (low_arr[:, :, 0] > 165) & (low_arr[:, :, 1] > 105)
    wys, wxs = np.where(w_mask & (np.arange(grid_size)[:, None] > grid_size * 0.42) & (np.arange(grid_size)[:, None] < grid_size * 0.58))
    if len(wxs) > 0:
        wx_min = int(np.percentile(wxs, 4))
        wy_med = int(np.median(wys[wxs <= wx_min + 3]))
        for wy_off, wx_len in [(-1, 3), (2, 3)]:
            wy = wy_med + wy_off
            for step in range(1, wx_len + 1):
                wx = wx_min - step
                if 0 <= wx < grid_size and 0 <= wy < grid_size:
                    low_arr[wy, wx] = [236, 222, 204, 255]

    low_im = Image.fromarray(low_arr, mode="RGBA")
    low_im.save(OUT_DIR / "route_a_v2_sprite_lowres.png")
    up_im = low_im.resize((grid_size * 3, grid_size * 3), Image.Resampling.NEAREST)
    up_im.save(out_sprite_path)
    print(f"[route_a_v2] Saved pixel sprite {out_sprite_path} ({up_im.size})")


def main():
    obj, valid, part_map, pos_map, norm_map = build_rest_map_from_glb()
    bake_route_a_v2_atlas(valid, part_map, pos_map, norm_map)
    highres_path = OUT_DIR / "route_a_v2_highres_render.png"
    render_chibi_with_atlas(obj, OUT_DIR / "route_a_v2_atlas_1024.png", highres_path)
    polish_highres_eyes_and_nose(highres_path)
    pixelate_and_outline_v2(highres_path, OUT_DIR / "route_a_v2_sprite.png", grid_size=92)


if __name__ == "__main__":
    main()
