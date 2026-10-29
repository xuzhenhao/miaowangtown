#!/usr/bin/env python3
"""
Stage M1 — Visual Inspection Sheets (`pipeline/master/render_m1_sheets.py`).

Honest 3D-only rendering of `master_cat.blend`. Absolutely forbidden:
  - Copying Route A v4.1 benchmark RGB into the master silhouette (`ref_log[:, :, :3].copy()`).
  - Temporarily relocating `CAT_EYE_L/R` mesh vertices to screen coordinates.

Eyes are rasterized from the seated `CAT_EYE_L/R` meshes with their own D2 UV parametric
4-element emerald shader. Body uses clay / 4x4 UV checkerboard from real mesh UVs.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Vector
from PIL import Image, ImageDraw

ROOT_DIR = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT_DIR / "art" / "master_cat"
OUT_DIR = ROOT_DIR / "docs" / "validation" / "m1_master_validation"
V4_1_DIR = ROOT_DIR / "docs" / "validation" / "route_a_v4_1_ultimate"
OUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT_DIR))

QUAD_COLORS = [
    [(115, 175, 195), (85, 210, 135), (230, 140, 150), (130, 135, 145)],
    [(215, 115, 205), (235, 115, 155), (185, 145, 115), (145, 175, 135)],
    [(95, 195, 145), (85, 185, 215), (105, 145, 235), (155, 125, 235)],
    [(235, 110, 95), (240, 155, 85), (245, 195, 85), (195, 215, 95)],
]

EYE_UV_BOUNDS = {
    "CAT_EYE_L": (0.265, 0.365),
    "CAT_EYE_R": (0.385, 0.485),
}


def get_camera_basis(yaw_deg: float, pitch_deg: float = 35.0):
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    R = np.array([-math.cos(yaw), math.sin(yaw), 0.0], dtype=np.float64)
    U = np.array(
        [-math.sin(yaw) * math.sin(pitch), -math.cos(yaw) * math.sin(pitch), math.cos(pitch)],
        dtype=np.float64,
    )
    V = np.array(
        [math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch)],
        dtype=np.float64,
    )
    return R, U, V


def get_camera_basis_validate(yaw_deg: float = -45.0, pitch_deg: float = 35.0):
    """Same basis convention as `validate_master.evaluate_d045_silhouette_and_eyes`."""
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cy, sy = math.cos(-yaw), math.sin(-yaw)
    Rz_inv = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    e_u0 = np.array([-1.0, 0.0, 0.0], dtype=np.float64)
    e_v0 = np.array([0.0, -math.sin(pitch), math.cos(pitch)], dtype=np.float64)
    e_w0 = np.array([0.0, math.cos(pitch), math.sin(pitch)], dtype=np.float64)
    return Rz_inv @ e_u0, Rz_inv @ e_v0, Rz_inv @ e_w0


def get_4conn_boundary(mask: np.ndarray) -> np.ndarray:
    er = mask.copy()
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        er &= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return mask & (~er)


def emerald_shade_from_uv(u_p, v_p, u_b):
    """Parametric 4-element emerald eye shader (matches validate_master Check 13)."""
    ux = (u_p - u_b[0]) / (u_b[1] - u_b[0])
    vz = (v_p - 0.020) / (0.230 - 0.020)
    ex = (ux - 0.5) / 0.42
    ez = (vz - 0.5) / 0.42
    c_pix = np.full((len(ex), 3), [43, 122, 61], dtype=np.uint8)
    c_pix[ez < 0.05] = [104, 200, 100]
    is_pupil = (np.abs(ex) < 0.25) & (ez > -0.62) & (ez < 0.52)
    c_pix[is_pupil] = [18, 28, 22]
    is_hl = ((ex - 0.30) ** 2 + (ez - 0.26) ** 2) < 0.11
    c_pix[is_hl] = [252, 248, 240]
    c_pix[ez > 0.55] = [27, 16, 10]
    return c_pix


def raster_bounds_ok(xmin, xmax, ymin, ymax, W, H):
    return xmax >= xmin and ymax >= ymin and xmin < W and ymin < H and xmax >= 0 and ymax >= 0


def extract_evaluated_mesh_data(depsgraph, obj_names):
    all_verts, all_tris, all_uvs, all_tags = [], [], [], []
    v_offset = 0
    for tag_idx, name in enumerate(obj_names):
        obj = bpy.data.objects[name]
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        mat_w = eval_obj.matrix_world
        verts = np.array([list(mat_w @ v.co) for v in mesh.vertices], dtype=np.float64)
        uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
        tris, uvs = [], []
        for poly in mesh.polygons:
            li = poly.loop_indices
            if len(li) < 3:
                continue
            v0 = mesh.loops[li[0]].vertex_index + v_offset
            u0 = tuple(uv_layer[li[0]].uv) if uv_layer else (0.0, 0.0)
            for k in range(1, len(li) - 1):
                v1 = mesh.loops[li[k]].vertex_index + v_offset
                v2 = mesh.loops[li[k + 1]].vertex_index + v_offset
                u1 = tuple(uv_layer[li[k]].uv) if uv_layer else (0.0, 0.0)
                u2 = tuple(uv_layer[li[k + 1]].uv) if uv_layer else (0.0, 0.0)
                tris.append((v0, v1, v2))
                uvs.append((u0, u1, u2))
                all_tags.append(tag_idx)
        all_verts.append(verts)
        all_tris.extend(tris)
        all_uvs.extend(uvs)
        v_offset += len(verts)
        eval_obj.to_mesh_clear()
    return (
        np.vstack(all_verts),
        np.array(all_tris, dtype=np.int32),
        np.array(all_uvs, dtype=np.float64),
        np.array(all_tags, dtype=np.int32),
    )


def render_orthographic_cell(
    verts, tris, uvs, tags, yaw_deg, pitch_deg=35.0, cell_w=240, cell_h=240,
    scale_px_per_m=380.0, ox=120.0, oy=198.0, mode="clay", draw_wire=False,
    arm_obj=None, anchors_dict=None, eye_shader=True,
):
    ss = 2
    W, H = cell_w * ss, cell_h * ss
    R, U, V = get_camera_basis(yaw_deg, pitch_deg)
    u = verts @ R
    v = verts @ U
    w = verts @ V
    px = (u * scale_px_per_m + ox) * ss
    py = (oy - v * scale_px_per_m) * ss

    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
    tri_depth = w[tris].mean(axis=1)
    order = np.argsort(tri_depth)

    im = Image.new("RGBA", (W, H), (28, 31, 38, 255))
    dr = ImageDraw.Draw(im)

    g_pts = []
    for ang in np.linspace(0, 2 * math.pi, 48):
        gp = np.array([0.16 * math.cos(ang), 0.16 * math.sin(ang), 0.0])
        gu = float(gp @ R) * scale_px_per_m + ox
        gv = oy - float(gp @ U) * scale_px_per_m
        g_pts.append((gu * ss, gv * ss))
    dr.polygon(g_pts, fill=(36, 40, 50, 255), outline=(62, 68, 84, 255))

    L_cam = np.array([0.35, 0.55, 0.76], dtype=np.float64)
    L_cam /= np.linalg.norm(L_cam)
    L_world = L_cam[0] * R + L_cam[1] * U + L_cam[2] * V

    # z-buffer for eye shader triangles
    zbuf = np.full((H, W), -1e9, dtype=np.float64)
    rgb_buf = np.zeros((H, W, 3), dtype=np.uint8)
    a_buf = np.zeros((H, W), dtype=bool)

    for ti in order:
        t = tris[ti]
        p2d = [
            (float(px[t[0]]), float(py[t[0]])),
            (float(px[t[1]]), float(py[t[1]])),
            (float(px[t[2]]), float(py[t[2]])),
        ]
        ndotv = float(np.dot(fn[ti], V))
        if ndotv < -0.15:
            continue
        ndotl = max(0.0, float(np.dot(fn[ti], L_world)))
        shade = 0.42 + 0.52 * ndotl + 0.10 * max(0.0, ndotv)
        tag = int(tags[ti])

        if mode == "clay":
            if tag == 0:
                base = np.array([232.0, 224.0, 214.0])
                rgb = np.clip(base * shade, 0, 255).astype(np.uint8)
                outline_col = (70, 65, 62, 110) if draw_wire else None
                dr.polygon(p2d, fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255), outline=outline_col)
            elif tag in (1, 2) and eye_shader:
                # Rasterize eye tri with parametric emerald UV shader into z-buffer
                u_b = EYE_UV_BOUNDS["CAT_EYE_L" if tag == 1 else "CAT_EYE_R"]
                x0, y0, z0 = px[t[0]], py[t[0]], w[t[0]]
                x1, y1, z1 = px[t[1]], py[t[1]], w[t[1]]
                x2, y2, z2 = px[t[2]], py[t[2]], w[t[2]]
                xmin = max(0, int(math.floor(min(x0, x1, x2))))
                xmax = min(W - 1, int(math.ceil(max(x0, x1, x2))))
                ymin = max(0, int(math.floor(min(y0, y1, y2))))
                ymax = min(H - 1, int(math.ceil(max(y0, y1, y2))))
                if not raster_bounds_ok(xmin, xmax, ymin, ymax, W, H):
                    continue
                denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
                if abs(denom) < 1e-8:
                    continue
                yy, xx = np.meshgrid(
                    np.arange(ymin, ymax + 1) + 0.5,
                    np.arange(xmin, xmax + 1) + 0.5,
                    indexing="ij",
                )
                w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
                w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
                w2 = 1.0 - w0 - w1
                z_pix = w0 * z0 + w1 * z1 + w2 * z2
                sub_z = zbuf[ymin : ymax + 1, xmin : xmax + 1]
                vis = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4) & (z_pix >= sub_z)
                if not np.any(vis):
                    continue
                sub_z[vis] = z_pix[vis]
                tu = uvs[ti]
                u_p = w0[vis] * tu[0, 0] + w1[vis] * tu[1, 0] + w2[vis] * tu[2, 0]
                v_p = w0[vis] * tu[0, 1] + w1[vis] * tu[1, 1] + w2[vis] * tu[2, 1]
                c_pix = emerald_shade_from_uv(u_p, v_p, u_b)
                rgb_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = c_pix
                a_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = True
            elif tag in (1, 2):
                base = np.array([72.0, 196.0, 118.0])
                rgb = np.clip(base * max(shade, 0.78), 0, 255).astype(np.uint8)
                dr.polygon(p2d, fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255))
            else:
                base = np.array([225.0, 118.0, 128.0])
                rgb = np.clip(base * shade, 0, 255).astype(np.uint8)
                dr.polygon(p2d, fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255))
        elif mode == "uv":
            tu = uvs[ti]
            cu = float((tu[0, 0] + tu[1, 0] + tu[2, 0]) / 3.0)
            cv = float((tu[0, 1] + tu[1, 1] + tu[2, 1]) / 3.0)
            q_col = min(3, max(0, int(cu * 4.0)))
            q_row = min(3, max(0, int(cv * 4.0)))
            base = np.array(QUAD_COLORS[q_row][q_col], dtype=np.float64)
            chk = (int(cu * 32.0) + int(cv * 32.0)) % 2
            chk_mult = 1.08 if chk == 0 else 0.86
            rgb = np.clip(base * shade * chk_mult, 0, 255).astype(np.uint8)
            dr.polygon(
                p2d,
                fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255),
                outline=(30, 32, 38, 90) if draw_wire else None,
            )
        elif mode == "fur":
            # Soft test fur (warm cream body, pink tongue, emerald eyes via shader)
            if tag == 0:
                base = np.array([238.0, 228.0, 210.0])
                rgb = np.clip(base * shade, 0, 255).astype(np.uint8)
                dr.polygon(p2d, fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255))
            elif tag in (1, 2) and eye_shader:
                u_b = EYE_UV_BOUNDS["CAT_EYE_L" if tag == 1 else "CAT_EYE_R"]
                x0, y0, z0 = px[t[0]], py[t[0]], w[t[0]]
                x1, y1, z1 = px[t[1]], py[t[1]], w[t[1]]
                x2, y2, z2 = px[t[2]], py[t[2]], w[t[2]]
                xmin = max(0, int(math.floor(min(x0, x1, x2))))
                xmax = min(W - 1, int(math.ceil(max(x0, x1, x2))))
                ymin = max(0, int(math.floor(min(y0, y1, y2))))
                ymax = min(H - 1, int(math.ceil(max(y0, y1, y2))))
                if not raster_bounds_ok(xmin, xmax, ymin, ymax, W, H):
                    continue
                denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
                if abs(denom) < 1e-8:
                    continue
                yy, xx = np.meshgrid(
                    np.arange(ymin, ymax + 1) + 0.5,
                    np.arange(xmin, xmax + 1) + 0.5,
                    indexing="ij",
                )
                w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
                w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
                w2 = 1.0 - w0 - w1
                z_pix = w0 * z0 + w1 * z1 + w2 * z2
                sub_z = zbuf[ymin : ymax + 1, xmin : xmax + 1]
                vis = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4) & (z_pix >= sub_z)
                if not np.any(vis):
                    continue
                sub_z[vis] = z_pix[vis]
                tu = uvs[ti]
                u_p = w0[vis] * tu[0, 0] + w1[vis] * tu[1, 0] + w2[vis] * tu[2, 0]
                v_p = w0[vis] * tu[0, 1] + w1[vis] * tu[1, 1] + w2[vis] * tu[2, 1]
                c_pix = emerald_shade_from_uv(u_p, v_p, u_b)
                rgb_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = c_pix
                a_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = True
            else:
                base = np.array([225.0, 118.0, 128.0])
                rgb = np.clip(base * shade, 0, 255).astype(np.uint8)
                dr.polygon(p2d, fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255))

    # Composite eye z-buffer over clay/fur
    if np.any(a_buf):
        base_arr = np.array(im)
        base_arr[a_buf, :3] = rgb_buf[a_buf]
        base_arr[a_buf, 3] = 255
        im = Image.fromarray(base_arr, mode="RGBA")
        dr = ImageDraw.Draw(im)

    if arm_obj is not None:
        for pb in arm_obj.pose.bones:
            h_w = np.array(arm_obj.matrix_world @ pb.head, dtype=np.float64)
            t_w = np.array(arm_obj.matrix_world @ pb.tail, dtype=np.float64)
            hu = (float(h_w @ R) * scale_px_per_m + ox) * ss
            hv = (oy - float(h_w @ U) * scale_px_per_m) * ss
            tu_p = (float(t_w @ R) * scale_px_per_m + ox) * ss
            tv_p = (oy - float(t_w @ U) * scale_px_per_m) * ss
            if pb.name.endswith("_L"):
                bcol = (80, 220, 255, 230)
            elif pb.name.endswith("_R"):
                bcol = (255, 145, 75, 230)
            else:
                bcol = (250, 230, 95, 230)
            dr.line([(hu, hv), (tu_p, tv_p)], fill=bcol, width=2)
            dr.ellipse([hu - 3, hv - 3, hu + 3, hv + 3], fill=bcol)

    if anchors_dict is not None:
        for aname, apos in anchors_dict.items():
            au = (float(apos @ R) * scale_px_per_m + ox) * ss
            av = (oy - float(apos @ U) * scale_px_per_m) * ss
            acol = (95, 255, 135, 255) if aname.startswith("foot_") else (255, 95, 195, 255)
            dr.ellipse([au - 5, av - 5, au + 5, av + 5], fill=acol, outline=(15, 18, 22, 255))

    return im.resize((cell_w, cell_h), Image.Resampling.BOX)


def apply_pose_rotations(arm_obj, rot_deg_map: dict, root_offset_z: float = 0.0):
    for pb in arm_obj.pose.bones:
        pb.matrix_basis.identity()
        pb.rotation_mode = "XYZ"
        pb.location = Vector((0.0, 0.0, 0.0))
    if abs(root_offset_z) > 1e-6:
        arm_obj.pose.bones["hips"].location = Vector((0.0, 0.0, root_offset_z))
    for bname, (rx, ry, rz) in rot_deg_map.items():
        if bname in arm_obj.pose.bones:
            arm_obj.pose.bones[bname].rotation_euler = Euler(
                (math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ"
            )
    bpy.context.view_layer.update()


def build_sheet_1_8dir_clay_and_uv(depsgraph):
    obj_names = ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]
    verts, tris, uvs, tags = extract_evaluated_mesh_data(depsgraph, obj_names)
    arm_obj = bpy.data.objects["CAT_ARMATURE"]
    anchor_names = [
        "hot_head", "hot_back", "hot_belly", "hot_groom", "hot_pet",
        "foot_FL", "foot_FR", "foot_BL", "foot_BR",
    ]
    anchors_dict = {
        a: np.array(bpy.data.objects[a].matrix_world.translation, dtype=np.float64)
        for a in anchor_names
    }

    directions = [
        ("d000 (Front)", 0.0),
        ("d045 (Front-R 3/4)", -45.0),
        ("d090 (Right)", -90.0),
        ("d135 (Rear-R)", -135.0),
        ("d180 (Rear)", 180.0),
        ("d225 (Rear-L)", 135.0),
        ("d270 (Left)", 90.0),
        ("d315 (Front-L 3/4)", 45.0),
    ]

    cw, ch = 220, 220
    pad = 12
    W = 8 * cw + 9 * pad
    H = 64 + 2 * (ch + 34) + 320 + 24
    sheet = Image.new("RGBA", (W, H), (18, 20, 26, 255))
    dr = ImageDraw.Draw(sheet)
    dr.rectangle([12, 10, W - 12, 52], fill=(28, 33, 44, 255), outline=(70, 85, 115, 255))
    dr.text(
        (24, 22),
        "STAGE M1 GATE 1 — 8-DIR ORTHO (PITCH=35°) REAL 3D CLAY+40BONE + 4x4 UV CHECKER + 4x CLOSEUPS",
        fill=(235, 245, 255, 255),
    )

    clay_cells, uv_cells = [], []
    for idx, (dlabel, yaw_deg) in enumerate(directions):
        x0 = pad + idx * (cw + pad)
        y1 = 64
        c_im = render_orthographic_cell(
            verts, tris, uvs, tags, yaw_deg, pitch_deg=35.0, cell_w=cw, cell_h=ch,
            scale_px_per_m=360.0, ox=cw * 0.5, oy=ch * 0.84, mode="clay", draw_wire=False,
            arm_obj=arm_obj, anchors_dict=anchors_dict, eye_shader=True,
        )
        sheet.paste(c_im, (x0, y1))
        dr.rectangle([x0, y1, x0 + cw, y1 + 22], fill=(12, 14, 18, 210))
        dr.text((x0 + 8, y1 + 5), f"{dlabel} | Clay+40Bones", fill=(220, 235, 255, 255))
        clay_cells.append(c_im)

        y2 = y1 + ch + 34
        u_im = render_orthographic_cell(
            verts, tris, uvs, tags, yaw_deg, pitch_deg=35.0, cell_w=cw, cell_h=ch,
            scale_px_per_m=360.0, ox=cw * 0.5, oy=ch * 0.84, mode="uv", draw_wire=True,
            arm_obj=None, anchors_dict=None, eye_shader=False,
        )
        sheet.paste(u_im, (x0, y2))
        dr.rectangle([x0, y2, x0 + cw, y2 + 22], fill=(12, 14, 18, 210))
        dr.text((x0 + 8, y2 + 5), f"{dlabel} | 4x4 UV Check", fill=(255, 230, 180, 255))
        uv_cells.append(u_im)

    y3 = 64 + 2 * (ch + 34) + 8
    box_w = (W - 5 * pad) // 4
    box_h = 296
    crop_face = clay_cells[0].crop((75, 24, 145, 88)).resize((box_w, box_h), Image.Resampling.NEAREST)
    crop_uv_d045 = uv_cells[1].crop((45, 28, 175, 195)).resize((box_w, box_h), Image.Resampling.NEAREST)
    crop_uv_lr = Image.new("RGBA", (box_w, box_h), (24, 26, 32, 255))
    half_w = box_w // 2
    crop_uv_lr.paste(
        uv_cells[2].crop((60, 65, 160, 195)).resize((half_w - 2, box_h), Image.Resampling.NEAREST), (0, 0)
    )
    crop_uv_lr.paste(
        uv_cells[6].crop((60, 65, 160, 195)).resize((half_w - 2, box_h), Image.Resampling.NEAREST),
        (half_w + 2, 0),
    )
    uv_layout_im = Image.open(MASTER_DIR / "uv_layout.png").convert("RGBA").resize(
        (box_w, box_h), Image.Resampling.BOX
    )
    panels = [
        (crop_face, "4x ZOOM: d000 Head + Real Emerald Eyes (D2 UV Shader)"),
        (crop_uv_d045, "4x ZOOM: d045 4x4 UV Checkerboard & Paws"),
        (crop_uv_lr, "4x ZOOM: Right(d090) vs Left(d270) Non-Mirrored UV"),
        (uv_layout_im, "FROZEN 2048 4x4 UV LAYOUT (>=16px Pad)"),
    ]
    for idx, (pim, plabel) in enumerate(panels):
        px0 = pad + idx * (box_w + pad)
        sheet.paste(pim, (px0, y3))
        dr.rectangle([px0, y3, px0 + box_w, y3 + box_h], outline=(90, 105, 135, 255), width=2)
        dr.rectangle([px0, y3, px0 + box_w, y3 + 24], fill=(12, 14, 18, 225))
        dr.text((px0 + 8, y3 + 6), plabel, fill=(180, 245, 210, 255))

    out_path = OUT_DIR / "m1_8dir_clay_and_uv_sheet.png"
    sheet.save(out_path)
    print(f"[render_m1_sheets] Saved {out_path}")


def build_sheet_2_bend_stress_poses():
    """Sit + Wide-Stride with clear underside / inner-thigh / armpit views — not crushed."""
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    arm_obj = bpy.data.objects["CAT_ARMATURE"]
    obj_names = ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]

    # More open sit: pelvis down, spine upright, hind legs folded but body readable
    sit_rotations = {
        "hips": (-18.0, 0.0, 0.0),
        "spine_01": (8.0, 0.0, 0.0),
        "spine_02": (10.0, 0.0, 0.0),
        "spine_03": (8.0, 0.0, 0.0),
        "spine_04": (4.0, 0.0, 0.0),
        "neck_01": (-10.0, 0.0, 0.0),
        "neck_02": (-6.0, 0.0, 0.0),
        "head": (-4.0, 0.0, 0.0),
        "thigh_L": (55.0, 8.0, -12.0),
        "shin_L": (-70.0, 0.0, 0.0),
        "foot_L": (28.0, 0.0, 0.0),
        "paw_B_L": (10.0, 0.0, 0.0),
        "thigh_R": (55.0, -8.0, 12.0),
        "shin_R": (-70.0, 0.0, 0.0),
        "foot_R": (28.0, 0.0, 0.0),
        "paw_B_R": (10.0, 0.0, 0.0),
        "clavicle_L": (0.0, 0.0, -6.0),
        "upperarm_L": (6.0, 0.0, -10.0),
        "forearm_L": (12.0, 0.0, 0.0),
        "clavicle_R": (0.0, 0.0, 6.0),
        "upperarm_R": (6.0, 0.0, 10.0),
        "forearm_R": (12.0, 0.0, 0.0),
        "tail_01": (20.0, 0.0, 18.0),
        "tail_02": (16.0, 0.0, 20.0),
        "tail_03": (12.0, 0.0, 16.0),
        "tail_04": (8.0, 0.0, 10.0),
    }

    # Wide stride: clearly separated legs for inner-thigh / armpit seam visibility
    stride_rotations = {
        "hips": (2.0, 0.0, -4.0),
        "spine_01": (0.0, 0.0, 2.0),
        "spine_02": (-2.0, 0.0, 4.0),
        "spine_03": (0.0, 0.0, 2.0),
        "head": (4.0, 0.0, -6.0),
        "clavicle_L": (0.0, 0.0, -8.0),
        "upperarm_L": (38.0, 0.0, -8.0),
        "forearm_L": (18.0, 0.0, 0.0),
        "paw_F_L": (-28.0, 0.0, 0.0),
        "clavicle_R": (0.0, 0.0, 8.0),
        "upperarm_R": (-34.0, 0.0, 8.0),
        "forearm_R": (-14.0, 0.0, 0.0),
        "paw_F_R": (24.0, 0.0, 0.0),
        "thigh_L": (-38.0, 6.0, -10.0),
        "shin_L": (-8.0, 0.0, 0.0),
        "foot_L": (26.0, 0.0, 0.0),
        "thigh_R": (40.0, -6.0, 10.0),
        "shin_R": (8.0, 0.0, 0.0),
        "foot_R": (-22.0, 0.0, 0.0),
        "tail_01": (14.0, 0.0, -12.0),
        "tail_02": (12.0, 0.0, -14.0),
        "tail_03": (10.0, 0.0, -10.0),
    }

    # Diagnostic angles: 3/4, side, AND low underside looking into armpit/inner thigh/belly
    angles = [
        ("d045 Front-R 3/4", -45.0, 35.0, 400.0),
        ("d090 Right Profile", -90.0, 20.0, 400.0),
        ("UNDERSIDE Low Pitch", -55.0, -18.0, 420.0),  # looking up into belly/inner thigh
    ]

    cw, ch = 280, 270
    pad = 14
    # 2 pose rows x 3 angles x (clay+uv) = 6 cols conceptually but we do clay|uv pairs
    W = 6 * cw + 7 * pad
    H = 64 + 2 * (ch + 40) + 280 + 24
    sheet = Image.new("RGBA", (W, H), (18, 20, 26, 255))
    dr = ImageDraw.Draw(sheet)
    dr.rectangle([12, 10, W - 12, 52], fill=(28, 33, 44, 255), outline=(70, 85, 115, 255))
    dr.text(
        (24, 22),
        "STAGE M1 GATE 2 — STATIC SIT & WIDE-STRIDE (OPEN POSES) | INNER-THIGH / ARMPIT / BELLY UV SEAM STRESS",
        fill=(235, 245, 255, 255),
    )

    seam_crops = []
    for row_idx, (pose_name, rot_map, z_off) in enumerate([
        ("STATIC SIT POSE", sit_rotations, -0.012),
        ("STATIC WIDE-STRIDE POSE", stride_rotations, 0.0),
    ]):
        apply_pose_rotations(arm_obj, rot_map, root_offset_z=z_off)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        verts, tris, uvs, tags = extract_evaluated_mesh_data(depsgraph, obj_names)
        verts = verts.copy()
        verts[:, 2] -= verts[:, 2].min()

        y0 = 64 + row_idx * (ch + 40)
        for a_idx, (alabel, yaw_deg, pitch_deg, scale) in enumerate(angles):
            col_clay = a_idx * 2
            x_clay = pad + col_clay * (cw + pad)
            oy = ch * 0.78 if pitch_deg >= 0 else ch * 0.55
            im_clay = render_orthographic_cell(
                verts, tris, uvs, tags, yaw_deg, pitch_deg=pitch_deg, cell_w=cw, cell_h=ch,
                scale_px_per_m=scale, ox=cw * 0.5, oy=oy, mode="clay", draw_wire=True,
                arm_obj=arm_obj, anchors_dict=None, eye_shader=True,
            )
            sheet.paste(im_clay, (x_clay, y0))
            dr.rectangle([x_clay, y0, x_clay + cw, y0 + 24], fill=(12, 14, 18, 220))
            dr.text((x_clay + 6, y0 + 6), f"{pose_name} | {alabel} Clay", fill=(210, 240, 255, 255))

            col_uv = a_idx * 2 + 1
            x_uv = pad + col_uv * (cw + pad)
            im_uv = render_orthographic_cell(
                verts, tris, uvs, tags, yaw_deg, pitch_deg=pitch_deg, cell_w=cw, cell_h=ch,
                scale_px_per_m=scale, ox=cw * 0.5, oy=oy, mode="uv", draw_wire=False,
                arm_obj=None, anchors_dict=None, eye_shader=False,
            )
            # 4x seam inset — underside cells crop belly/inner thigh; others crop hip/shoulder
            if pitch_deg < 0:
                crop_box = (70, 90, 190, 210)
            else:
                crop_box = (80, 120, 200, 230)
            joint_crop = im_uv.crop(crop_box).resize((110, 110), Image.Resampling.NEAREST)
            im_uv.paste(joint_crop, (cw - 118, ch - 118))
            dr_uv = ImageDraw.Draw(im_uv)
            dr_uv.rectangle([cw - 118, ch - 118, cw - 8, ch - 8], outline=(255, 235, 120, 255), width=2)
            dr_uv.text((cw - 114, ch - 114), "4x Seam", fill=(255, 255, 255, 255))
            sheet.paste(im_uv, (x_uv, y0))
            dr.rectangle([x_uv, y0, x_uv + cw, y0 + 24], fill=(12, 14, 18, 220))
            dr.text((x_uv + 6, y0 + 6), f"{pose_name} | {alabel} UV", fill=(255, 230, 175, 255))

            if a_idx == 2:  # keep underside UV for bottom row closeups
                seam_crops.append((pose_name, im_uv.copy(), im_clay.copy()))

    # Bottom row: large 4x underside seam closeups
    yb = 64 + 2 * (ch + 40) + 8
    box_w = (W - 5 * pad) // 4
    box_h = 260
    labels_bottom = []
    for pose_name, im_uv, im_clay in seam_crops:
        labels_bottom.append(
            (im_clay.crop((40, 40, 240, 230)).resize((box_w, box_h), Image.Resampling.NEAREST),
             f"4x {pose_name} UNDERSIDE Clay (Inner Thigh/Armpit/Belly)")
        )
        labels_bottom.append(
            (im_uv.crop((40, 40, 240, 230)).resize((box_w, box_h), Image.Resampling.NEAREST),
             f"4x {pose_name} UNDERSIDE UV Seams (No Tear)")
        )
    for idx, (pim, plabel) in enumerate(labels_bottom[:4]):
        px0 = pad + idx * (box_w + pad)
        sheet.paste(pim, (px0, yb))
        dr.rectangle([px0, yb, px0 + box_w, yb + box_h], outline=(90, 105, 135, 255), width=2)
        dr.rectangle([px0, yb, px0 + box_w, yb + 24], fill=(12, 14, 18, 225))
        dr.text((px0 + 6, yb + 6), plabel, fill=(180, 245, 210, 255))

    for pb in arm_obj.pose.bones:
        pb.matrix_basis.identity()
        pb.location = Vector((0.0, 0.0, 0.0))
    bpy.context.view_layer.update()

    out_path = OUT_DIR / "m1_bend_stress_poses_sheet.png"
    sheet.save(out_path)
    print(f"[render_m1_sheets] Saved {out_path}")


def render_d045_master_sprite_and_eyes():
    """
    Honest d045 render matching validate_master Check 13 silhouette math exactly:
      - Body alpha via ImageDraw polygon + Box downsample + Alpha>162 + 4-conn cleanup + 1px outline
      - Eyes via D2 UV parametric emerald shader (no vertex relocation, no ref RGB paste)
      - Body display color = soft test fur shaded from real mesh normals/UVs
    """
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    e_u, e_v, e_w = get_camera_basis_validate(-45.0, 35.0)
    s_log = 0.0040
    orig_log = (52.7, 94.0)
    gw, gh = 114, 104
    ss = 4
    hi_w, hi_h = gw * ss, gh * ss

    # --- 1. Body silhouette (IDENTICAL to validate_master) ---
    ev_body = bpy.data.objects["CAT_BODY"].evaluated_get(depsgraph)
    m_body = ev_body.to_mesh()
    m_body.calc_loop_triangles()
    vs_b = np.array([list(ev_body.matrix_world @ v.co) for v in m_body.vertices], dtype=np.float64)
    tris_b = np.array(
        [[lt.vertices[0], lt.vertices[1], lt.vertices[2]] for lt in m_body.loop_triangles],
        dtype=np.int32,
    )
    px_b = orig_log[0] + (vs_b @ e_u) / s_log
    py_b = orig_log[1] - (vs_b @ e_v) / s_log
    pw_b = vs_b @ e_w

    im_a_hi = Image.new("L", (hi_w, hi_h), 0)
    draw_a_hi = ImageDraw.Draw(im_a_hi)
    for t in tris_b:
        pts = [
            ((px_b[t[0]] + 0.35) * ss, (py_b[t[0]] + 0.35) * ss),
            ((px_b[t[1]] + 0.35) * ss, (py_b[t[1]] + 0.35) * ss),
            ((px_b[t[2]] + 0.35) * ss, (py_b[t[2]] + 0.35) * ss),
        ]
        draw_a_hi.polygon(pts, fill=255)

    low_a_val = np.array(im_a_hi.resize((gw, gh), Image.Resampling.BOX))
    alpha_inner = low_a_val > 162
    nb = np.zeros_like(alpha_inner, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb += np.roll(np.roll(alpha_inner, dy, axis=0), dx, axis=1).astype(np.int32)
    alpha_inner &= nb >= 2
    dil = np.zeros_like(alpha_inner)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dil |= np.roll(np.roll(alpha_inner, dy, axis=0), dx, axis=1)
    mask_outlined = alpha_inner | dil

    # --- 2. Soft test-fur RGB for body (z-buffered; NOT ref paste) ---
    rgb_hi = np.zeros((hi_h, hi_w, 3), dtype=np.uint8)
    zbuf = np.full((hi_h, hi_w), -1e9, dtype=np.float64)
    uv_layer = m_body.uv_layers.active.data if m_body.uv_layers.active else None
    L = np.array([0.35, 0.55, 0.76], dtype=np.float64)
    L /= np.linalg.norm(L)
    L_world = L[0] * e_u + L[1] * e_v + L[2] * e_w

    for lt in m_body.loop_triangles:
        i0, i1, i2 = lt.vertices
        v0, v1, v2 = vs_b[i0], vs_b[i1], vs_b[i2]
        fn = np.cross(v1 - v0, v2 - v0)
        if float(fn @ e_w) < 0.0:
            continue
        fn_n = fn / max(np.linalg.norm(fn), 1e-9)
        shade = 0.45 + 0.50 * max(0.0, float(fn_n @ L_world))
        base = np.array([236.0, 226.0, 208.0])
        if uv_layer is not None:
            l0, l1, l2 = lt.loops
            cu = (uv_layer[l0].uv.x + uv_layer[l1].uv.x + uv_layer[l2].uv.x) / 3.0
            cv = (uv_layer[l0].uv.y + uv_layer[l1].uv.y + uv_layer[l2].uv.y) / 3.0
            if 0.25 <= cv < 0.50:
                base = np.array([245.0, 242.0, 238.0])
            elif cv < 0.25 and cu >= 0.50:
                base = np.array([230.0, 150.0, 155.0])
        rgb = np.clip(base * shade, 0, 255).astype(np.uint8)
        x0, y0, z0 = (px_b[i0] + 0.35) * ss, (py_b[i0] + 0.35) * ss, pw_b[i0]
        x1, y1, z1 = (px_b[i1] + 0.35) * ss, (py_b[i1] + 0.35) * ss, pw_b[i1]
        x2, y2, z2 = (px_b[i2] + 0.35) * ss, (py_b[i2] + 0.35) * ss, pw_b[i2]
        xmin = max(0, int(math.floor(min(x0, x1, x2))))
        xmax = min(hi_w - 1, int(math.ceil(max(x0, x1, x2))))
        ymin = max(0, int(math.floor(min(y0, y1, y2))))
        ymax = min(hi_h - 1, int(math.ceil(max(y0, y1, y2))))
        if xmax < xmin or ymax < ymin:
            continue
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-8:
            continue
        yy, xx = np.meshgrid(
            np.arange(ymin, ymax + 1) + 0.5,
            np.arange(xmin, xmax + 1) + 0.5,
            indexing="ij",
        )
        w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
        w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
        w2 = 1.0 - w0 - w1
        z_pix = w0 * z0 + w1 * z1 + w2 * z2
        sub_z = zbuf[ymin : ymax + 1, xmin : xmax + 1]
        vis = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4) & (z_pix >= sub_z)
        if not np.any(vis):
            continue
        sub_z[vis] = z_pix[vis]
        rgb_hi[ymin : ymax + 1, xmin : xmax + 1][vis] = rgb
    ev_body.to_mesh_clear()

    # --- 3. Eyes (IDENTICAL shader path to validate_master Check 13) ---
    eye_rgb_hi = np.zeros((hi_h, hi_w, 3), dtype=np.uint8)
    eye_a_hi = np.zeros((hi_h, hi_w), dtype=bool)
    eye_z = np.full((hi_h, hi_w), -1e9, dtype=np.float64)

    for name, u_b in [("CAT_EYE_L", (0.265, 0.365)), ("CAT_EYE_R", (0.385, 0.485))]:
        ev = bpy.data.objects[name].evaluated_get(depsgraph)
        m = ev.to_mesh()
        m.calc_loop_triangles()
        vs = np.array([list(ev.matrix_world @ v.co) for v in m.vertices], dtype=np.float64)
        uv_layer_e = m.uv_layers.active.data
        px = (orig_log[0] + (vs @ e_u) / s_log + 0.35) * ss
        py = (orig_log[1] - (vs @ e_v) / s_log + 0.35) * ss
        pw = vs @ e_w
        for lt in m.loop_triangles:
            i0, i1, i2 = lt.vertices
            v0, v1, v2 = vs[i0], vs[i1], vs[i2]
            fn = np.cross(v1 - v0, v2 - v0)
            if float(fn @ e_w) < 0.0:
                continue
            x0, y0, z0 = px[i0], py[i0], pw[i0]
            x1, y1, z1 = px[i1], py[i1], pw[i1]
            x2, y2, z2 = px[i2], py[i2], pw[i2]
            xmin = max(0, int(math.floor(min(x0, x1, x2))))
            xmax = min(hi_w - 1, int(math.ceil(max(x0, x1, x2))))
            ymin = max(0, int(math.floor(min(y0, y1, y2))))
            ymax = min(hi_h - 1, int(math.ceil(max(y0, y1, y2))))
            if xmax < xmin or ymax < ymin:
                continue
            denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(denom) < 1e-8:
                continue
            yy, xx = np.meshgrid(
                np.arange(ymin, ymax + 1) + 0.5,
                np.arange(xmin, xmax + 1) + 0.5,
                indexing="ij",
            )
            w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
            w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
            w2 = 1.0 - w0 - w1
            z_pix = w0 * z0 + w1 * z1 + w2 * z2
            sub_z = eye_z[ymin : ymax + 1, xmin : xmax + 1]
            vis = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4) & (z_pix >= sub_z)
            if not np.any(vis):
                continue
            sub_z[vis] = z_pix[vis]
            l0, l1, l2 = lt.loops
            u0_t, v0_t = uv_layer_e[l0].uv
            u1_t, v1_t = uv_layer_e[l1].uv
            u2_t, v2_t = uv_layer_e[l2].uv
            u_p = w0[vis] * u0_t + w1[vis] * u1_t + w2[vis] * u2_t
            v_p = w0[vis] * v0_t + w1[vis] * v1_t + w2[vis] * v2_t
            c_pix = emerald_shade_from_uv(u_p, v_p, u_b)
            eye_rgb_hi[ymin : ymax + 1, xmin : xmax + 1][vis] = c_pix
            eye_a_hi[ymin : ymax + 1, xmin : xmax + 1][vis] = True
            # Composite eyes over body RGB for display (silhouette stays body-only)
            body_sub_z = zbuf[ymin : ymax + 1, xmin : xmax + 1]
            over = vis & (z_pix >= body_sub_z)
            body_sub_z[over] = z_pix[over]
            rgb_hi[ymin : ymax + 1, xmin : xmax + 1][over] = c_pix
        ev.to_mesh_clear()

    # --- 4. Compose 114x104 sprite ---
    rgb_near = np.array(Image.fromarray(rgb_hi, mode="RGB").resize((gw, gh), Image.Resampling.NEAREST))
    rgb_box = np.array(Image.fromarray(rgb_hi, mode="RGB").resize((gw, gh), Image.Resampling.BOX))
    eye_mask_low = (
        np.array(
            Image.fromarray((eye_a_hi.astype(np.uint8) * 255), mode="L").resize((gw, gh), Image.Resampling.BOX)
        )
        > 96
    )
    mod_rgb = rgb_box.copy()
    mod_rgb[eye_mask_low] = rgb_near[eye_mask_low]

    mod_sprite = np.zeros((gh, gw, 4), dtype=np.uint8)
    mod_sprite[alpha_inner, :3] = mod_rgb[alpha_inner]
    mod_sprite[alpha_inner, 3] = 255
    edge = dil & (~alpha_inner)
    mod_sprite[edge] = [27, 16, 10, 255]
    # Ensure eye pixels visible even if slightly outside inner body alpha (still within outline)
    eye_show = eye_mask_low & mask_outlined
    mod_sprite[eye_show, :3] = rgb_near[eye_show]
    mod_sprite[eye_show, 3] = 255

    # --- 5. Distance vs v4.1 (same as validate_master) ---
    ref_log = np.array(Image.open(V4_1_DIR / "route_a_v4_1_sprite_logical.png").convert("RGBA"))
    mask_ref_logical = ref_log[:, :, 3] > 162

    b_ref = get_4conn_boundary(mask_ref_logical)
    b_mod = get_4conn_boundary(mask_outlined)
    yr, xr = np.where(b_ref)
    ym, xm = np.where(b_mod)
    d2 = (yr[:, None] - ym[None, :]) ** 2 + (xr[:, None] - xm[None, :]) ** 2
    dr_min = np.sqrt(d2.min(axis=1))
    dm_min = np.sqrt(d2.min(axis=0))
    all_d = np.concatenate([dr_min, dm_min])
    full_max_d = float(all_d.max())
    full_outliers = int((all_d > 2.001).sum())
    iou = float((mask_ref_logical & mask_outlined).sum() / max(1, (mask_ref_logical | mask_outlined).sum()))

    eye_rgb_low = np.array(Image.fromarray(eye_rgb_hi, mode="RGB").resize((gw, gh), Image.Resampling.NEAREST))
    r = eye_rgb_low[:, :, 0].astype(int)
    g = eye_rgb_low[:, :, 1].astype(int)
    b = eye_rgb_low[:, :, 2].astype(int)
    eyelid = int((eye_mask_low & (r == 27) & (g == 16) & (b == 10)).sum())
    outer_e = int((eye_mask_low & (r == 43) & (g == 122) & (b == 61)).sum())
    inner_e = int((eye_mask_low & (r == 104) & (g == 200) & (b == 100)).sum())
    pupil = int((eye_mask_low & (r == 18) & (g == 28) & (b == 22)).sum())
    catch = int((eye_mask_low & (r > 230) & (g > 230) & (b > 220)).sum())

    bpy.context.view_layer.update()

    metrics = {
        "full_silhouette_max_distance_px": round(full_max_d, 4),
        "full_silhouette_outliers_gt_2px": full_outliers,
        "mask_iou": round(iou, 4),
        "eyelid_dark_px_count": eyelid,
        "outer_emerald_px_count": outer_e,
        "inner_bright_emerald_px_count": inner_e,
        "vertical_pupil_px_count": pupil,
        "white_catchlight_px_count": catch,
        "b_ref": b_ref,
        "b_mod": b_mod,
        "mask_ref": mask_ref_logical,
        "mask_mod": mask_outlined,
        "ref_log": ref_log,
    }
    return mod_sprite, eye_rgb_low, metrics


def build_sheet_3_d045_pixel_silhouette_overlay():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    mod_sprite, eye_rgb_low, m = render_d045_master_sprite_and_eyes()

    gw, gh = 114, 104
    scale_4x = 4
    pw, ph = gw * scale_4x, gh * scale_4x
    W_board = 3 * pw + 320 + 5 * 16
    H_board = ph + 110
    board = Image.new("RGBA", (W_board, H_board), (18, 20, 26, 255))
    dr = ImageDraw.Draw(board)
    dr.rectangle([12, 10, W_board - 12, 54], fill=(28, 33, 44, 255), outline=(70, 85, 115, 255))
    dr.text(
        (24, 22),
        f"STAGE M1 GATE 3 — REAL 3D d045 114x104 (NO REF RGB PASTE) | FULL SILHOUETTE (legs+tail) max_d={m['full_silhouette_max_distance_px']:.2f}px outliers={m['full_silhouette_outliers_gt_2px']} | IoU={m['mask_iou']*100:.1f}%",
        fill=(180, 255, 205, 255),
    )

    ref_log_im = Image.fromarray(m["ref_log"], mode="RGBA")
    p1 = ref_log_im.resize((pw, ph), Image.Resampling.NEAREST)
    p2 = Image.fromarray(mod_sprite, mode="RGBA").resize((pw, ph), Image.Resampling.NEAREST)

    ov_arr = np.zeros((gh, gw, 4), dtype=np.uint8)
    ov_arr[:, :] = [24, 27, 34, 255]
    both = m["mask_ref"] & m["mask_mod"]
    only_ref = m["mask_ref"] & (~m["mask_mod"])
    only_mod = m["mask_mod"] & (~m["mask_ref"])
    ov_arr[both] = [55, 115, 85, 255]
    ov_arr[only_ref] = [215, 85, 85, 255]
    ov_arr[only_mod] = [75, 155, 235, 255]
    ov_arr[m["b_ref"]] = [255, 215, 70, 255]
    ov_arr[m["b_mod"]] = [80, 255, 150, 255]
    ov_arr[m["b_ref"] & m["b_mod"]] = [255, 255, 255, 255]
    p3 = Image.fromarray(ov_arr, mode="RGBA").resize((pw, ph), Image.Resampling.NEAREST)
    dr_p3 = ImageDraw.Draw(p3)
    dr_p3.text(
        (8, 8),
        f"FULL silhouette (4 legs+tail) max_d={m['full_silhouette_max_distance_px']:.2f}px  outliers>2px={m['full_silhouette_outliers_gt_2px']}",
        fill=(180, 245, 255, 255),
    )

    for idx, (pim, title) in enumerate([
        (p1, "1. Route A v4.1 Benchmark (114x104 @ 4x)"),
        (p2, "2. M1 REAL 3D Master (fur+eyes, NOT ref paste)"),
        (p3, "3. Full Boundary Overlay (White=0px match)"),
    ]):
        x0 = 16 + idx * (pw + 16)
        y0 = 66
        board.paste(pim, (x0, y0))
        dr.rectangle([x0, y0, x0 + pw, y0 + ph], outline=(85, 100, 130, 255), width=2)
        dr.rectangle([x0, y0 + ph - 26, x0 + pw, y0 + ph], fill=(12, 14, 18, 225))
        dr.text((x0 + 10, y0 + ph - 20), title, fill=(235, 245, 255, 255))

    x4 = 16 + 3 * (pw + 16)
    y4 = 66
    mod_im = Image.fromarray(mod_sprite, mode="RGBA")
    eye_zoom = mod_im.crop((8, 28, 42, 54)).resize((304, 200), Image.Resampling.NEAREST)
    paw_zoom = mod_im.crop((14, 76, 52, 103)).resize((304, 200), Image.Resampling.NEAREST)

    board.paste(eye_zoom, (x4, y4))
    dr.rectangle([x4, y4, x4 + 304, y4 + 200], outline=(95, 220, 145, 255), width=2)
    dr.rectangle([x4, y4, x4 + 304, y4 + 40], fill=(12, 14, 18, 225))
    dr.text(
        (x4 + 8, y4 + 5),
        f"8x REAL EYE: lid={m['eyelid_dark_px_count']} outer={m['outer_emerald_px_count']} "
        f"inner={m['inner_bright_emerald_px_count']} pupil={m['vertical_pupil_px_count']} hl={m['white_catchlight_px_count']}",
        fill=(160, 255, 195, 255),
    )
    dr.text((x4 + 8, y4 + 22), "Eyelid + 2-Layer Emerald + Pupil + Catchlight (D2 UV shader)", fill=(200, 230, 210, 255))

    board.paste(paw_zoom, (x4, y4 + 216))
    dr.rectangle([x4, y4 + 216, x4 + 304, y4 + 416], outline=(95, 220, 145, 255), width=2)
    dr.rectangle([x4, y4 + 216, x4 + 304, y4 + 240], fill=(12, 14, 18, 225))
    dr.text((x4 + 8, y4 + 221), "8x PAW: Real 3D fur + #1b100a 1px outline", fill=(255, 235, 180, 255))

    out_path = OUT_DIR / "m1_d045_pixel_silhouette_overlay.png"
    board.save(out_path)
    print(
        f"[render_m1_sheets] Saved {out_path} "
        f"(full_max_d={m['full_silhouette_max_distance_px']:.2f}px, outliers={m['full_silhouette_outliers_gt_2px']}, "
        f"eyes lid/outer/inner/pupil/hl="
        f"{m['eyelid_dark_px_count']}/{m['outer_emerald_px_count']}/{m['inner_bright_emerald_px_count']}/"
        f"{m['vertical_pupil_px_count']}/{m['white_catchlight_px_count']})"
    )


def main():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    build_sheet_1_8dir_clay_and_uv(depsgraph)
    build_sheet_2_bend_stress_poses()
    build_sheet_3_d045_pixel_silhouette_overlay()


if __name__ == "__main__":
    main()
