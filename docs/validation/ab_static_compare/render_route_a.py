#!/usr/bin/env python3
"""
Route A: AI View-Controlled Generation + 3D Camera Projection UV Baking + Offscreen Pixelation & Outline.
Includes chroma/luma background exclusion so the AI image's gray background and painted whiskers
never leak gray scanline artifacts onto the 3D UV atlas.
"""
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image

import sys
sys.path.insert(0, "/workspace/miaowangtown/docs/validation/ab_static_compare")
from render_route_b import build_rest_map_from_glb, render_chibi_with_atlas, pixelate_and_outline, ATLAS_SIZE

OUT_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")


def bake_route_a_camera_projection(valid, part_map, pos_map, norm_map) -> Image.Image:
    ai_im = Image.open(OUT_DIR / "route_a_ai_view.jpg").convert("RGB")
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

    # Also exclude low-saturation neutral gray background / whisker-fringe pixels:
    # Cat fur is either warm brown/caramel (R - B > 22), cream white (R > 175), green eye (G - R > 10), or dark stripe (R < 65)
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

    # Erode 2px then dilate to strip any thin floating whiskers in background
    eroded = fg_mask.copy()
    for _ in range(2):
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            eroded &= np.roll(np.roll(fg_mask, dy, axis=0), dx, axis=1)
        fg_mask = eroded.copy()

    ays, axs = np.where(fg_mask)
    ax0, ax1 = axs.min(), axs.max()
    ay0, ay1 = ays.min(), ays.max()
    print(f"[route_a] Clean AI cat foreground bbox in {aw}x{ah}: x=[{ax0},{ax1}], y=[{ay0},{ay1}]")

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

    projected_rgb = ai_clean[ai_y, ai_x]

    facing = np.sum(norm_bl * v_cam_bl, axis=-1)
    fallback = np.full_like(projected_rgb, [152, 98, 52], dtype=np.uint8)
    w_proj = np.clip((facing + 0.10) / 0.30, 0.0, 1.0)[..., None]
    atlas_rgb = np.clip(projected_rgb.astype(np.float32) * w_proj + fallback.astype(np.float32) * (1.0 - w_proj), 0, 255).astype(np.uint8)

    im = Image.fromarray(atlas_rgb, mode="RGB")
    im.save(OUT_DIR / "route_a_atlas_1024.png")
    return im


def main():
    obj, valid, part_map, pos_map, norm_map = build_rest_map_from_glb()
    bake_route_a_camera_projection(valid, part_map, pos_map, norm_map)
    render_chibi_with_atlas(obj, OUT_DIR / "route_a_atlas_1024.png", OUT_DIR / "route_a_highres_render.png")
    pixelate_and_outline(OUT_DIR / "route_a_highres_render.png", OUT_DIR / "route_a_sprite.png", grid_size=84)


if __name__ == "__main__":
    main()
