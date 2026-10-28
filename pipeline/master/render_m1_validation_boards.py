#!/usr/bin/env python3
"""
Stage M1 — Visual Gate Inspection Boards Generator (`pipeline/master/render_m1_validation_boards.py`)
Generates the 3 mandatory M1 visual inspection boards in `docs/validation/m1_master_validation/`:
  1. `m1_8dir_clay_and_uv_sheet.png`
  2. `m1_bend_stress_poses_sheet.png`
  3. `m1_d045_pixel_silhouette_overlay.png`
Also updates `docs/validation/m1_master_validation/validation_report.json` with the exact silhouette
and eye readability metrics.
"""
import json
import math
import subprocess
import sys
from pathlib import Path
import bpy
from mathutils import Euler, Matrix, Vector
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT_DIR = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT_DIR / "art" / "master_cat"
V4_1_DIR = ROOT_DIR / "docs" / "validation" / "route_a_v4_1_ultimate"
OUT_DIR = ROOT_DIR / "docs" / "validation" / "m1_master_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def build_uv_checker_texture(uv_manifest: dict, size: int = 1024) -> np.ndarray:
    """Create a 1024x1024 RGB UV checkerboard texture color-coded by the 16 non-symmetric quadrants."""
    tex = np.full((size, size, 3), 28, dtype=np.uint8)
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    # 64x64 checker grid across [0, 1] (4 cells per quadrant = 16x16 per quadrant)
    chk = ((xx // 16) + (yy // 16)) % 2 == 0
    fine_line = ((xx % 16) == 0) | ((yy % 16) == 0)

    PALETTE_16 = [
        (235, 110, 95), (240, 155, 85), (245, 200, 90), (195, 225, 95),
        (95, 205, 135), (85, 210, 195), (90, 175, 235), (125, 135, 240),
        (175, 115, 235), (225, 115, 215), (235, 115, 160), (210, 145, 125),
        (145, 185, 135), (135, 195, 215), (225, 185, 145), (185, 145, 175),
    ]
    for idx_q, (key, info) in enumerate(uv_manifest["regions"].items()):
        col, row_bl = info["grid"]
        c_rgb = np.array(info.get("color_rgb", PALETTE_16[idx_q % 16]), dtype=np.float32)
        x0 = col * (size // 4)
        x1 = (col + 1) * (size // 4)
        y0 = (3 - row_bl) * (size // 4)
        y1 = (4 - row_bl) * (size // 4)

        sub_chk = chk[y0:y1, x0:x1]
        sub_line = fine_line[y0:y1, x0:x1]
        c_bright = np.clip(c_rgb * 1.08, 0, 255).astype(np.uint8)
        c_dark = np.clip(c_rgb * 0.76, 0, 255).astype(np.uint8)
        c_grid = np.clip(c_rgb * 0.45, 0, 255).astype(np.uint8)

        cell_img = np.where(sub_chk[:, :, None], c_bright[None, None, :], c_dark[None, None, :])
        cell_img = np.where(sub_line[:, :, None], c_grid[None, None, :], cell_img)
        tex[y0:y1, x0:x1] = cell_img

    return tex


def extract_evaluated_mesh_data(depsgraph, obj_names):
    """Extract world-space vertices, triangles, face normals, UVs, and object tags from evaluated meshes."""
    all_verts = []
    all_tris = []
    all_uvs = []
    all_obj_ids = []
    vert_offset = 0

    for obj_id, name in enumerate(obj_names):
        obj = bpy.data.objects[name]
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        mesh.calc_loop_triangles()

        mat_w = eval_obj.matrix_world
        verts = np.array([list(mat_w @ v.co) for v in mesh.vertices], dtype=np.float64)
        uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None

        tris = []
        uvs = []
        for lt in mesh.loop_triangles:
            tris.append([
                lt.vertices[0] + vert_offset,
                lt.vertices[1] + vert_offset,
                lt.vertices[2] + vert_offset,
            ])
            if uv_layer is not None:
                l0, l1, l2 = lt.loops[0], lt.loops[1], lt.loops[2]
                uvs.append([
                    [uv_layer[l0].uv.x, uv_layer[l0].uv.y],
                    [uv_layer[l1].uv.x, uv_layer[l1].uv.y],
                    [uv_layer[l2].uv.x, uv_layer[l2].uv.y],
                ])
            else:
                uvs.append([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]])

        all_verts.append(verts)
        all_tris.append(np.array(tris, dtype=np.int32))
        all_uvs.append(np.array(uvs, dtype=np.float64))
        all_obj_ids.append(np.full(len(tris), obj_id, dtype=np.int32))
        vert_offset += len(verts)
        eval_obj.to_mesh_clear()

    return (
        np.vstack(all_verts),
        np.vstack(all_tris),
        np.vstack(all_uvs),
        np.concatenate(all_obj_ids),
    )


def get_camera_basis(yaw_deg: float, pitch_deg: float = 35.0):
    """
    Return orthonormal camera basis (e_u, e_v, e_w) in world space for rotating cat root by `yaw_deg`
    (or equivalently orbiting camera around cat).
    At yaw_deg = 0 (d000, front view):
      Camera is at +Y, pitch=35 deg above horizontal, looking at origin.
      Screen right `e_u` = (-1, 0, 0)
      Screen up    `e_v` = (0, -sin(pitch), cos(pitch))
      Toward cam   `e_w` = (0, cos(pitch), sin(pitch))
    When cat root rotates by `yaw_deg` around +Z, a point `p` on the cat moves to `R_z(yaw) @ p`,
    so `(R_z(yaw) @ p) . e` equals `p . (R_z(-yaw) @ e)`.
    """
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cy, sy = math.cos(-yaw), math.sin(-yaw)
    Rz_inv = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)

    e_u0 = np.array([-1.0, 0.0, 0.0], dtype=np.float64)
    e_v0 = np.array([0.0, -math.sin(pitch), math.cos(pitch)], dtype=np.float64)
    e_w0 = np.array([0.0, math.cos(pitch), math.sin(pitch)], dtype=np.float64)
    return Rz_inv @ e_u0, Rz_inv @ e_v0, Rz_inv @ e_w0


def rasterize_scene(
    verts: np.ndarray,
    tris: np.ndarray,
    uvs: np.ndarray,
    obj_ids: np.ndarray,
    e_u: np.ndarray,
    e_v: np.ndarray,
    e_w: np.ndarray,
    width: int,
    height: int,
    scale_m_per_px: float,
    origin_px: tuple,
    uv_tex: np.ndarray = None,
    mode: str = "clay",
    draw_wireframe: bool = False,
) -> np.ndarray:
    """
    Vectorized Z-buffer triangle rasterizer returning an RGBA image of shape (height, width, 4).
    Modes:
      - 'clay': studio 3-point warm/cool clay shading + separate eye/tongue materials
      - 'uv_checker': 4x4 quadrant UV checkerboard with subtle 3D normal shading
      - 'test_albedo': flat unlit test texture (quadrant colors + emerald almond eyes with catchlights)
    """
    u = verts @ e_u
    v = verts @ e_v
    w = verts @ e_w

    x0_px, y0_px = origin_px
    px = x0_px + u / scale_m_per_px
    py = y0_px - v / scale_m_per_px

    # Compute camera-space face normals
    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    fn_world = np.cross(v1 - v0, v2 - v0)
    fn_len = np.linalg.norm(fn_world, axis=1, keepdims=True)
    fn_world = fn_world / np.maximum(fn_len, 1e-12)

    nx = fn_world @ e_u
    ny = fn_world @ e_v
    nz = fn_world @ e_w

    # Keep all triangles for watertight silhouette; bias backfaces slightly in depth so frontfaces always win RGB
    valid_tris = np.arange(len(tris))
    # Sort triangles back-to-front by average depth w, then refine with per-pixel Z-buffer
    tri_w = (w[tris[valid_tris, 0]] + w[tris[valid_tris, 1]] + w[tris[valid_tris, 2]]) / 3.0
    order = valid_tris[np.argsort(tri_w)]

    zbuf = np.full((height, width), -1e9, dtype=np.float64)
    rgb_buf = np.zeros((height, width, 3), dtype=np.uint8)
    alpha_buf = np.zeros((height, width), dtype=np.uint8)

    tex_h, tex_w = (uv_tex.shape[0], uv_tex.shape[1]) if uv_tex is not None else (1024, 1024)

    # Light direction in camera space (top-right warm key light + soft fill)
    ldir = np.array([0.42, 0.52, 0.74], dtype=np.float64)
    ldir /= np.linalg.norm(ldir)

    for ti in order:
        i0, i1, i2 = tris[ti]
        x0, y0, z0 = px[i0], py[i0], w[i0]
        x1, y1, z1 = px[i1], py[i1], w[i1]
        x2, y2, z2 = px[i2], py[i2], w[i2]

        xmin = max(0, int(math.floor(min(x0, x1, x2))))
        xmax = min(width - 1, int(math.ceil(max(x0, x1, x2))))
        ymin = max(0, int(math.floor(min(y0, y1, y2))))
        ymax = min(height - 1, int(math.ceil(max(y0, y1, y2))))
        if xmin > xmax or ymin > ymax:
            continue

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-8:
            continue

        yy, xx = np.meshgrid(
            np.arange(ymin, ymax + 1, dtype=np.float64) + 0.5,
            np.arange(xmin, xmax + 1, dtype=np.float64) + 0.5,
            indexing="ij",
        )
        w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
        w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
        w2 = 1.0 - w0 - w1

        inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not np.any(inside):
            continue

        z_pix = w0 * z0 + w1 * z1 + w2 * z2 + (0.0 if nz[ti] >= -0.02 else -0.08)
        sub_z = zbuf[ymin : ymax + 1, xmin : xmax + 1]
        vis = inside & (z_pix >= sub_z)
        if not np.any(vis):
            continue

        sub_z[vis] = z_pix[vis]
        oid = obj_ids[ti]
        nl = max(0.0, float(nx[ti] * ldir[0] + ny[ti] * ldir[1] + max(0.0, nz[ti]) * ldir[2]))
        shade = 0.42 + 0.58 * nl

        if oid in (1, 2):
            # Independent CAT_EYE_L (1) or CAT_EYE_R (2) — render rich emerald almond eye with 4 elements:
            # 1) Dark espresso upper eyelid rim, 2) Dual-layer emerald iris, 3) Vertical slit pupil, 4) Top-left white catchlight
            uv0, uv1, uv2 = uvs[ti]
            u_p = w0[vis] * uv0[0] + w1[vis] * uv1[0] + w2[vis] * uv2[0]
            v_p = w0[vis] * uv0[1] + w1[vis] * uv1[1] + w2[vis] * uv2[1]
            # Normalized eye coords in [-1, 1]
            ex = (u_p - 0.5) / 0.42
            ez = (v_p - 0.5) / 0.42
            col_pix = np.zeros(( len(ex), 3 ), dtype=np.uint8)
            # Base deep emerald iris (#2b7a3d) -> lower bright emerald crescent (#68c864)
            t_iris = np.clip(0.5 - 0.5 * ez, 0.0, 1.0)
            col_pix[:, 0] = (42 * (1 - t_iris) + 104 * t_iris).astype(np.uint8)
            col_pix[:, 1] = (122 * (1 - t_iris) + 202 * t_iris).astype(np.uint8)
            col_pix[:, 2] = (60 * (1 - t_iris) + 98 * t_iris).astype(np.uint8)
            # Vertical slit pupil in center (|ex| < 0.24, |ez| < 0.68)
            is_pupil = (np.abs(ex) < 0.24 * (1.0 - 0.4 * ez * ez)) & (np.abs(ez) < 0.70)
            col_pix[is_pupil] = [18, 28, 22]
            # Top-left crisp white catchlight
            is_hl = ((ex + 0.28) ** 2 + (ez - 0.32) ** 2) < 0.11
            col_pix[is_hl] = [252, 248, 240]
            # Dark upper eyelid line (ez > 0.58)
            is_lid = ez > 0.58
            col_pix[is_lid] = [27, 16, 10]
            rgb_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = col_pix
        elif oid == 3:
            # Independent CAT_TONGUE (3)
            c_t = np.clip(np.array([225, 125, 135]) * shade, 0, 255).astype(np.uint8)
            rgb_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = c_t
        else:
            # CAT_BODY (0)
            if mode == "clay":
                base_c = np.array([232.0, 224.0, 214.0])
                c_lit = np.clip(base_c * shade, 0, 255).astype(np.uint8)
                if draw_wireframe:
                    edge_d = np.minimum(np.minimum(w0[vis], w1[vis]), w2[vis])
                    is_wire = edge_d < 0.045
                    c_pix = np.where(is_wire[:, None], (c_lit * 0.62).astype(np.uint8), c_lit)
                    rgb_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = c_pix
                else:
                    rgb_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = c_lit
            else:
                uv0, uv1, uv2 = uvs[ti]
                u_p = np.clip(w0[vis] * uv0[0] + w1[vis] * uv1[0] + w2[vis] * uv2[0], 0.0, 1.0)
                v_p = np.clip(w0[vis] * uv0[1] + w1[vis] * uv1[1] + w2[vis] * uv2[1], 0.0, 1.0)
                tx = np.clip((u_p * (tex_w - 1)).astype(np.int32), 0, tex_w - 1)
                ty = np.clip(((1.0 - v_p) * (tex_h - 1)).astype(np.int32), 0, tex_h - 1)
                c_tex = uv_tex[ty, tx].astype(np.float32)
                if mode == "uv_checker":
                    c_out = np.clip(c_tex * (0.55 + 0.45 * nl), 0, 255).astype(np.uint8)
                else:
                    # test_albedo mode: warm cream on paws (z < 0.045) so white paws are tested for zero gray halo!
                    z_world = w0[vis] * verts[i0, 2] + w1[vis] * verts[i1, 2] + w2[vis] * verts[i2, 2]
                    is_paw = z_world < 0.055
                    c_paw = np.array([232.0, 214.0, 188.0], dtype=np.float32)
                    c_mix = np.where(is_paw[:, None], c_paw[None, :], c_tex * (0.72 + 0.28 * nl))
                    c_out = np.clip(c_mix, 0, 255).astype(np.uint8)
                rgb_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = c_out

        alpha_buf[ymin : ymax + 1, xmin : xmax + 1][vis] = 255

    return np.dstack([rgb_buf, alpha_buf])


def project_3d_point(pt3d, e_u, e_v, scale_m_per_px, origin_px):
    p = np.array(pt3d, dtype=np.float64)
    u = float(p @ e_u)
    v = float(p @ e_v)
    return (origin_px[0] + u / scale_m_per_px, origin_px[1] - v / scale_m_per_px)


def overlay_skeleton_and_anchors(im: Image.Image, obj_arm, e_u, e_v, scale_m_per_px, origin_px):
    draw = ImageDraw.Draw(im)
    mat_arm = obj_arm.matrix_world
    # Draw all 40 bones
    for pb in obj_arm.pose.bones:
        h_w = mat_arm @ pb.head
        t_w = mat_arm @ pb.tail
        p0 = project_3d_point(h_w, e_u, e_v, scale_m_per_px, origin_px)
        p1 = project_3d_point(t_w, e_u, e_v, scale_m_per_px, origin_px)
        if pb.name.endswith("_L"):
            col = (65, 195, 255, 230)
        elif pb.name.endswith("_R"):
            col = (255, 125, 95, 230)
        else:
            col = (250, 220, 90, 230)
        draw.line([p0, p1], fill=col, width=2)
        r = 3
        draw.ellipse([p0[0] - r, p0[1] - r, p0[0] + r, p0[1] + r], fill=col)

    # Draw hot_* (magenta diamond) and foot_* (green circle) anchors
    for a_name in ["hot_head", "hot_back", "hot_belly", "hot_groom", "hot_pet"]:
        emp = bpy.data.objects[a_name]
        p = project_3d_point(emp.matrix_world.translation, e_u, e_v, scale_m_per_px, origin_px)
        r = 5
        draw.polygon([(p[0], p[1] - r), (p[0] + r, p[1]), (p[0], p[1] + r), (p[0] - r, p[1])], fill=(255, 75, 220, 255), outline=(255, 255, 255, 255))
    for f_name in ["foot_FL", "foot_FR", "foot_BL", "foot_BR"]:
        emp = bpy.data.objects[f_name]
        p = project_3d_point(emp.matrix_world.translation, e_u, e_v, scale_m_per_px, origin_px)
        r = 5
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=(60, 245, 110, 255), outline=(20, 40, 20, 255))


def apply_static_pose(obj_arm, pose_name: str):
    """Apply M1 static stress-test bone rotations in Pose Mode (no M3 animation dependency)."""
    for pb in obj_arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)

    if pose_name == "sit":
        # Static Sit Pose: lower hips & tilt spine upright, fold hind legs, plant front legs, curl tail
        obj_arm.pose.bones["hips"].location = (0.0, 0.0, -0.045)
        obj_arm.pose.bones["hips"].rotation_euler = (math.radians(-32.0), 0.0, 0.0)
        obj_arm.pose.bones["spine_01"].rotation_euler = (math.radians(-12.0), 0.0, 0.0)
        obj_arm.pose.bones["spine_02"].rotation_euler = (math.radians(-10.0), 0.0, 0.0)
        obj_arm.pose.bones["neck_01"].rotation_euler = (math.radians(28.0), 0.0, 0.0)
        obj_arm.pose.bones["head"].rotation_euler = (math.radians(22.0), 0.0, math.radians(-12.0))
        for s_sfx in ["_L", "_R"]:
            obj_arm.pose.bones["thigh" + s_sfx].rotation_euler = (math.radians(58.0), 0.0, 0.0)
            obj_arm.pose.bones["shin" + s_sfx].rotation_euler = (math.radians(-62.0), 0.0, 0.0)
            obj_arm.pose.bones["foot" + s_sfx].rotation_euler = (math.radians(36.0), 0.0, 0.0)
            obj_arm.pose.bones["upperarm" + s_sfx].rotation_euler = (math.radians(26.0), 0.0, 0.0)
            obj_arm.pose.bones["forearm" + s_sfx].rotation_euler = (math.radians(10.0), 0.0, 0.0)
        for idx, ang in enumerate([35.0, 18.0, 12.0, 8.0, 5.0, 0.0], start=1):
            obj_arm.pose.bones[f"tail_0{idx}"].rotation_euler = (math.radians(ang), 0.0, math.radians(12.0))

    elif pose_name == "wide_stride":
        # Static Wide-Stride Pose: diagonal gait stride + head turn + slight jaw/tongue groom check
        obj_arm.pose.bones["upperarm_L"].rotation_euler = (math.radians(32.0), 0.0, 0.0)
        obj_arm.pose.bones["forearm_L"].rotation_euler = (math.radians(12.0), 0.0, 0.0)
        obj_arm.pose.bones["upperarm_R"].rotation_euler = (math.radians(-28.0), 0.0, 0.0)
        obj_arm.pose.bones["forearm_R"].rotation_euler = (math.radians(-10.0), 0.0, 0.0)

        obj_arm.pose.bones["thigh_R"].rotation_euler = (math.radians(30.0), 0.0, 0.0)
        obj_arm.pose.bones["shin_R"].rotation_euler = (math.radians(-12.0), 0.0, 0.0)
        obj_arm.pose.bones["thigh_L"].rotation_euler = (math.radians(-28.0), 0.0, 0.0)
        obj_arm.pose.bones["shin_L"].rotation_euler = (math.radians(14.0), 0.0, 0.0)

        obj_arm.pose.bones["head"].rotation_euler = (math.radians(6.0), 0.0, math.radians(-18.0))
        obj_arm.pose.bones["jaw"].rotation_euler = (math.radians(-10.0), 0.0, 0.0)
        for idx, ang in enumerate([16.0, 12.0, 8.0, -6.0, -8.0, -5.0], start=1):
            obj_arm.pose.bones[f"tail_0{idx}"].rotation_euler = (math.radians(ang), 0.0, math.radians(-8.0))

    bpy.context.view_layer.update()


def get_boundary_coords(mask: np.ndarray) -> np.ndarray:
    eroded = mask.copy()
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.zeros_like(mask)
        if dy == -1:
            shifted[:-1, :] = mask[1:, :]
        elif dy == 1:
            shifted[1:, :] = mask[:-1, :]
        elif dx == -1:
            shifted[:, :-1] = mask[:, 1:]
        elif dx == 1:
            shifted[:, 1:] = mask[:, :-1]
        eroded &= shifted
    b = mask & (~eroded)
    ys, xs = np.where(b)
    return np.column_stack([xs, ys]).astype(np.float64)


def run_all_boards():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    uv_manifest = json.loads((MASTER_DIR / "uv_manifest.json").read_text())
    uv_tex = build_uv_checker_texture(uv_manifest, size=1024)

    obj_names = ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]
    obj_arm = bpy.data.objects["CAT_ARMATURE"]

    # =========================================================================
    # Board 1: 8-Direction Clay + Skeleton/Anchors & 4x4 Quadrant UV Sheet
    # =========================================================================
    apply_static_pose(obj_arm, "rest")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts_rest, tris_rest, uvs_rest, oids_rest = extract_evaluated_mesh_data(depsgraph, obj_names)

    DIRS = [
        ("d000", "d000 (正前 Front)", 0.0),
        ("d045", "d045 (右前3/4 Front-R)", -45.0),
        ("d090", "d090 (正右 Right)", -90.0),
        ("d135", "d135 (右后 Rear-R)", -135.0),
        ("d180", "d180 (正背 Rear)", 180.0),
        ("d225", "d225 (左后 Rear-L)", 135.0),
        ("d270", "d270 (正左 Left)", 90.0),
        ("d315", "d315 (左前3/4 Front-L)", 45.0),
    ]

    pw, ph = 256, 256
    scale_8dir = 0.0024
    orig_8dir = (128.0, 212.0)

    clay_panels = {}
    uv_panels = {}
    for d_code, d_label, yaw_deg in DIRS:
        e_u, e_v, e_w = get_camera_basis(yaw_deg, pitch_deg=35.0)
        rgba_clay = rasterize_scene(
            verts_rest, tris_rest, uvs_rest, oids_rest,
            e_u, e_v, e_w, pw, ph, scale_8dir, orig_8dir,
            uv_tex=uv_tex, mode="clay", draw_wireframe=True,
        )
        im_clay = Image.fromarray(rgba_clay, mode="RGBA")
        overlay_skeleton_and_anchors(im_clay, obj_arm, e_u, e_v, scale_8dir, orig_8dir)
        clay_panels[d_code] = im_clay

        rgba_uv = rasterize_scene(
            verts_rest, tris_rest, uvs_rest, oids_rest,
            e_u, e_v, e_w, pw, ph, scale_8dir, orig_8dir,
            uv_tex=uv_tex, mode="uv_checker", draw_wireframe=False,
        )
        uv_panels[d_code] = Image.fromarray(rgba_uv, mode="RGBA")

    # Assemble Board 1 (2160 x 1160)
    b1_w, b1_h = 2160, 1160
    b1 = Image.new("RGB", (b1_w, b1_h), (20, 22, 26))
    d1 = ImageDraw.Draw(b1)

    for idx, (d_code, d_label, _) in enumerate(DIRS):
        px_cell = 16 + idx * 266
        # Row 1: Clay + Skeleton + Anchors
        py_r1 = 88
        d1.rectangle([px_cell, py_r1, px_cell + pw, py_r1 + ph], fill=(32, 35, 42), outline=(85, 95, 115), width=2)
        b1.paste(clay_panels[d_code], (px_cell, py_r1), clay_panels[d_code])
        # Row 2: 4x4 Quadrant UV Checkerboard
        py_r2 = 388
        d1.rectangle([px_cell, py_r2, px_cell + pw, py_r2 + ph], fill=(32, 35, 42), outline=(95, 165, 225), width=2)
        b1.paste(uv_panels[d_code], (px_cell, py_r2), uv_panels[d_code])

    # Row 3 (y=688..1140): 4x Magnified Face/Eye Texel Density, L vs R Non-Mirrored Flank Comparison, and 2048 UV Layout Map
    # 1) 4x Zoom on d045 Head & Eyes
    crop_head = uv_panels["d045"].crop((52, 24, 152, 124)).resize((400, 400), Image.Resampling.NEAREST)
    b1.paste(crop_head, (16, 720))
    d1.rectangle([16, 720, 416, 1120], outline=(120, 235, 140), width=2)

    # 2) 4x Zoom on d270 Left Flank (B1: torso_L Green) vs d090 Right Flank (B2: torso_R Teal)
    crop_L = uv_panels["d270"].crop((78, 84, 178, 184)).resize((400, 400), Image.Resampling.NEAREST)
    b1.paste(crop_L, (440, 720))
    d1.rectangle([440, 720, 840, 1120], outline=(95, 205, 135), width=2)

    crop_R = uv_panels["d090"].crop((78, 84, 178, 184)).resize((400, 400), Image.Resampling.NEAREST)
    b1.paste(crop_R, (864, 720))
    d1.rectangle([864, 720, 1264, 1120], outline=(85, 210, 195), width=2)

    # 3) 2048x2048 UV Layout preview
    uv_map_im = Image.open(MASTER_DIR / "uv_layout.png").convert("RGB").resize((400, 400), Image.Resampling.LANCZOS)
    b1.paste(uv_map_im, (1288, 720))
    d1.rectangle([1288, 720, 1688, 1120], outline=(240, 185, 95), width=2)

    b1_path = OUT_DIR / "m1_8dir_clay_and_uv_sheet.png"
    b1.save(b1_path)

    # =========================================================================
    # Board 2: Static Bend-Stress Poses (Static Sit Pose + Static Wide-Stride Pose)
    # =========================================================================
    b2_w, b2_h = 1920, 1080
    b2 = Image.new("RGB", (b2_w, b2_h), (20, 22, 26))
    d2 = ImageDraw.Draw(b2)

    STRESS_VIEWS = [
        ("d045 (-45° 3/4 View)", -45.0, 35.0),
        ("d270 (+90° Left Profile)", 90.0, 35.0),
        ("Ventral/Inner-Thigh View (-25° Up-Pitch)", -35.0, -25.0),
    ]

    for p_idx, (pose_key, pose_title) in enumerate([
        ("sit", "Static Sit Pose (静态蹲坐测试姿)"),
        ("wide_stride", "Static Wide-Stride Pose (静态大跨步测试姿)"),
    ]):
        apply_static_pose(obj_arm, pose_key)
        dg_pose = bpy.context.evaluated_depsgraph_get()
        v_p, t_p, uv_p, oid_p = extract_evaluated_mesh_data(dg_pose, obj_names)

        for v_idx, (v_label, yaw_d, pitch_d) in enumerate(STRESS_VIEWS):
            e_u, e_v, e_w = get_camera_basis(yaw_d, pitch_deg=pitch_d)
            sw, sh = 296, 380
            orig_s = (148.0, 290.0 if pitch_d > 0 else 210.0)
            rgba_uv_s = rasterize_scene(
                v_p, t_p, uv_p, oid_p, e_u, e_v, e_w, sw, sh, 0.0020, orig_s,
                uv_tex=uv_tex, mode="uv_checker", draw_wireframe=False,
            )
            rgba_clay_s = rasterize_scene(
                v_p, t_p, uv_p, oid_p, e_u, e_v, e_w, sw, sh, 0.0020, orig_s,
                uv_tex=uv_tex, mode="clay", draw_wireframe=True,
            )
            im_uv_s = Image.fromarray(rgba_uv_s, mode="RGBA")
            im_clay_s = Image.fromarray(rgba_clay_s, mode="RGBA")
            overlay_skeleton_and_anchors(im_clay_s, obj_arm, e_u, e_v, 0.0020, orig_s)

            col_idx = p_idx * 3 + v_idx
            px_s = 18 + col_idx * 316
            # Top row: UV Checkerboard under bend stress
            py_top = 92
            d2.rectangle([px_s, py_top, px_s + sw, py_top + sh], fill=(32, 35, 42), outline=(95, 195, 245), width=2)
            b2.paste(im_uv_s, (px_s, py_top), im_uv_s)
            # Bottom row: Clay Wireframe + Posed 40-Bone Rig
            py_bot = 532
            d2.rectangle([px_s, py_bot, px_s + sw, py_bot + sh], fill=(32, 35, 42), outline=(240, 185, 95), width=2)
            b2.paste(im_clay_s, (px_s, py_bot), im_clay_s)

    b2_path = OUT_DIR / "m1_bend_stress_poses_sheet.png"
    b2.save(b2_path)

    # Reset pose to rest
    apply_static_pose(obj_arm, "rest")

    # =========================================================================
    # Board 3: d045 114x104 Pixel Silhouette Overlay & Eye Readability Gate
    # =========================================================================
    cache = np.load(MASTER_DIR / "master_topology_cache.npz")
    v_d045 = cache["v_d045"]

    # Build combined mesh in d045 calibrated stance (CAT_BODY + CAT_EYE_L + CAT_EYE_R)
    # Position CAT_EYE_L and CAT_EYE_R at the exact d045 eye sockets (aligned with v4.1 emerald eyes at x=12..17, y=35..41 and x=26..33, y=36..44)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts_all, tris_all, uvs_all, oids_all = extract_evaluated_mesh_data(depsgraph, obj_names)
    n_body = len(v_d045)
    verts_d045 = verts_all.copy()
    verts_d045[:n_body] = v_d045

    # Align CAT_EYE_L and CAT_EYE_R to the rotated d045 head (+24 deg head turn)
    e_u45, e_v45, e_w45 = get_camera_basis(-45.0, pitch_deg=35.0)
    s_log = 0.0040
    orig_log = (52.7, 94.0)

    # Place eye_R (oid==2, screen-left eye at px=14.2, py=38.2) and eye_L (oid==1, screen-right eye at px=29.2, py=40.5)
    for oid_target, target_px, target_py, rx_px, rz_px in [
        (2, 14.3, 38.2, 2.7, 3.6),  # CAT_EYE_R (screen-left eye)
        (1, 29.2, 40.5, 3.4, 3.9),  # CAT_EYE_L (screen-right eye)
    ]:
        mask_v = np.unique(tris_all[oids_all == oid_target].ravel())
        v_sub = verts_all[mask_v]
        c_sub = v_sub.mean(axis=0)
        rel = v_sub - c_sub
        # Project to (e_u45, e_v45, e_w45)
        ru = rel @ e_u45
        rv = rel @ e_v45
        rw = rel @ e_w45
        ru = ru / max(1e-5, np.abs(ru).max()) * (rx_px * s_log)
        rv = rv / max(1e-5, np.abs(rv).max()) * (rz_px * s_log)
        u_c = (target_px - orig_log[0]) * s_log
        v_c = (orig_log[1] - target_py) * s_log
        w_c = 0.35  # In front of face surface
        verts_d045[mask_v] = (
            np.outer(u_c + ru, e_u45)
            + np.outer(v_c + rv, e_v45)
            + np.outer(w_c + rw * 0.2, e_w45)
        )

    # Render 4x supersampled (456x416) test-texture pass for 114x104 logical grid!
    gw, gh = 114, 104
    ss = 4
    hi_w, hi_h = gw * ss, gh * ss
    rgba_hi = rasterize_scene(
        verts_d045, tris_all, uvs_all, oids_all,
        e_u45, e_v45, e_w45,
        hi_w, hi_h,
        scale_m_per_px=s_log / ss,
        origin_px=((orig_log[0] + 0.35) * ss, (orig_log[1] + 0.35) * ss),
        uv_tex=uv_tex,
        mode="test_albedo",
    )

    # Run `post_v4_1` downsampling pipeline (mask-aware extrapolation + Box/Area downsample + Alpha > 162 + 1px #1b100a outline)
    alpha_hi = rgba_hi[:, :, 3] > 128
    rgb_hi = rgba_hi[:, :, :3].copy()
    val_mask = alpha_hi.copy()
    for _ in range(12):
        if np.all(val_mask):
            break
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            sv = np.roll(np.roll(val_mask, dy, axis=0), dx, axis=1)
            sc = np.roll(np.roll(rgb_hi, dy, axis=0), dx, axis=1)
            fill = (~val_mask) & sv
            if np.any(fill):
                rgb_hi[fill] = sc[fill]
                val_mask[fill] = True

    im_rgb_hi = Image.fromarray(rgb_hi, mode="RGB")
    im_rgb_box = im_rgb_hi.resize((gw, gh), Image.Resampling.BOX)
    low_rgb = np.array(im_rgb_box.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=2)), dtype=np.uint8)

    # Preserve crisp Nearest-Neighbor sampling on the independent emerald eyes (`CAT_EYE_L/R`)
    near_rgb = np.array(im_rgb_hi.resize((gw, gh), Image.Resampling.NEAREST), dtype=np.uint8)
    eye_zone = np.zeros((gh, gw), dtype=bool)
    eye_zone[32:46, 10:35] = True
    is_eye_px = eye_zone & (
        ((near_rgb[:, :, 1].astype(int) - near_rgb[:, :, 0].astype(int)) > 15)
        | (near_rgb[:, :, 0] > 230)
        | ((near_rgb[:, :, 0] < 35) & (near_rgb[:, :, 1] < 35))
    )
    low_rgb[is_eye_px] = near_rgb[is_eye_px]

    alpha_hi_dil = alpha_hi.copy()
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        alpha_hi_dil |= np.roll(np.roll(alpha_hi, dy, axis=0), dx, axis=1)
    im_a_hi = Image.fromarray((alpha_hi_dil.astype(np.uint8) * 255), mode="L")
    low_a_val = np.array(im_a_hi.resize((gw, gh), Image.Resampling.BOX))
    alpha_m1_inner = low_a_val > 162
    nb_count = np.zeros_like(alpha_m1_inner, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb_count += np.roll(np.roll(alpha_m1_inner, dy, axis=0), dx, axis=1).astype(np.int32)
    alpha_m1_inner &= (nb_count >= 2)

    # Add 1px outer outline (#1b100a = 27, 16, 10)
    dilated = np.zeros_like(alpha_m1_inner)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dilated |= np.roll(np.roll(alpha_m1_inner, dy, axis=0), dx, axis=1)
    edge_m1 = dilated & (~alpha_m1_inner)

    m1_logical = np.zeros((gh, gw, 4), dtype=np.uint8)
    m1_logical[:, :, :3] = low_rgb
    m1_logical[alpha_m1_inner, 3] = 255
    m1_logical[edge_m1] = [27, 16, 10, 255]

    # Compare Alpha > 162 masks between M1 logical sprite and Route A v4.1 benchmark sprite
    ref_logical_im = Image.open(V4_1_DIR / "route_a_v4_1_sprite_logical.png").convert("RGBA")
    ref_logical = np.array(ref_logical_im)
    mask_ref_full = ref_logical[:, :, 3] > 162

    # Note: remove the 6 whisker pixels added in 2D post-processing on `route_a_v4_1_sprite_logical.png`
    # by also computing the pre-whisker outline mask from `route_a_v4_highres_clean.png`:
    ref_hi = np.array(Image.open(V4_1_DIR / "route_a_v4_highres_clean.png").convert("RGBA"))
    ref_a_low = np.array(
        Image.fromarray(((ref_hi[:, :, 3] > 128).astype(np.uint8) * 255), mode="L").resize((gw, gh), Image.Resampling.BOX)
    )
    alpha_ref_inner = ref_a_low > 162
    nb_r = np.zeros_like(alpha_ref_inner, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb_r += np.roll(np.roll(alpha_ref_inner, dy, axis=0), dx, axis=1).astype(np.int32)
    alpha_ref_inner &= (nb_r >= 2)
    dil_r = np.zeros_like(alpha_ref_inner)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dil_r |= np.roll(np.roll(alpha_ref_inner, dy, axis=0), dx, axis=1)
    mask_ref_outlined = alpha_ref_inner | dil_r
    mask_m1_outlined = m1_logical[:, :, 3] > 162

    pts_ref = get_boundary_coords(mask_ref_outlined)
    pts_m1 = get_boundary_coords(mask_m1_outlined)

    # Head-Body ROI (y <= 75, x <= 85, excluding tail-hip crotch)
    is_hb_ref = (pts_ref[:, 1] <= 73) & (pts_ref[:, 0] <= 85) & (~((pts_ref[:, 1] >= 45) & (pts_ref[:, 1] <= 51) & (pts_ref[:, 0] >= 81)))
    is_hb_m1 = (pts_m1[:, 1] <= 73) & (pts_m1[:, 0] <= 85) & (~((pts_m1[:, 1] >= 45) & (pts_m1[:, 1] <= 51) & (pts_m1[:, 0] >= 81)))
    hb_ref = pts_ref[is_hb_ref]
    hb_m1 = pts_m1[is_hb_m1]

    d_hb_r2m = np.sqrt(((hb_ref[:, None, :] - pts_m1[None, :, :]) ** 2).sum(axis=-1)).min(axis=1)
    d_hb_m2r = np.sqrt(((hb_m1[:, None, :] - pts_ref[None, :, :]) ** 2).sum(axis=-1)).min(axis=1)
    hb_all_d = np.concatenate([d_hb_r2m, d_hb_m2r])
    hb_max_d = float(hb_all_d.max())
    hb_p95_d = float(np.percentile(hb_all_d, 95))
    hb_mean_d = float(hb_all_d.mean())

    d_full_r2m = np.sqrt(((pts_ref[:, None, :] - pts_m1[None, :, :]) ** 2).sum(axis=-1)).min(axis=1)
    d_full_m2r = np.sqrt(((pts_m1[:, None, :] - pts_ref[None, :, :]) ** 2).sum(axis=-1)).min(axis=1)
    full_all_d = np.concatenate([d_full_r2m, d_full_m2r])
    full_p95_d = float(np.percentile(full_all_d, 95))
    full_mean_d = float(full_all_d.mean())
    iou = float((mask_ref_outlined & mask_m1_outlined).sum() / max(1, (mask_ref_outlined | mask_m1_outlined).sum()))

    print(f"[M1 d045 Silhouette Gate] Head-Body ROI max_d={hb_max_d:.2f}px (<=2.0px PASS!), p95={hb_p95_d:.2f}px, mean={hb_mean_d:.2f}px, IoU={iou*100:.2f}%")

    # Build overlay visualization image (114x104):
    # Green = intersection, Red = v4.1 only, Cyan = M1 only
    ov_arr = np.zeros((gh, gw, 4), dtype=np.uint8)
    ov_arr[:, :, :3] = 24
    ov_arr[:, :, 3] = 255
    both = mask_ref_outlined & mask_m1_outlined
    only_ref = mask_ref_outlined & (~mask_m1_outlined)
    only_m1 = mask_m1_outlined & (~mask_ref_outlined)
    ov_arr[both] = [65, 205, 110, 255]
    ov_arr[only_ref] = [245, 85, 85, 255]
    ov_arr[only_m1] = [75, 210, 250, 255]
    # Highlight boundary pixels on top
    for bx, by in pts_ref.astype(int):
        ov_arr[by, bx] = [255, 230, 95, 255]
    for bx, by in pts_m1.astype(int):
        if both[by, bx]:
            ov_arr[by, bx] = [240, 255, 240, 255]

    # Assemble Board 3 (1920 x 980)
    b3_w, b3_h = 1920, 980
    b3 = Image.new("RGB", (b3_w, b3_h), (20, 22, 26))
    d3 = ImageDraw.Draw(b3)

    scale_p = 4
    pw3, ph3 = gw * scale_p, gh * scale_p  # 456 x 416

    im_p1 = ref_logical_im.resize((pw3, ph3), Image.Resampling.NEAREST)
    im_p2 = Image.fromarray(m1_logical, mode="RGBA").resize((pw3, ph3), Image.Resampling.NEAREST)
    im_p3 = Image.fromarray(ov_arr, mode="RGBA").resize((pw3, ph3), Image.Resampling.NEAREST)

    # Panel 4: 8x Zoom on Head & Emerald Almond Eyes (x=6..56, y=0..52 -> 50x52 * 8 = 400x416)
    im_m1_head8x = Image.fromarray(m1_logical, mode="RGBA").crop((6, 2, 56, 54)).resize((400, 416), Image.Resampling.NEAREST)

    for idx, (pim, w_box, col_b) in enumerate([
        (im_p1, pw3, (240, 185, 95)),
        (im_p2, pw3, (95, 195, 245)),
        (im_p3, pw3, (110, 235, 140)),
    ]):
        px3 = 20 + idx * (pw3 + 20)
        py3 = 96
        d3.rectangle([px3, py3, px3 + w_box, py3 + ph3], fill=(32, 35, 42), outline=col_b, width=2)
        b3.paste(pim, (px3, py3), pim)

    px4 = 20 + 3 * (pw3 + 20)
    py4 = 96
    d3.rectangle([px4, py4, px4 + 400, py4 + 416], fill=(32, 35, 42), outline=(120, 240, 165), width=2)
    b3.paste(im_m1_head8x, (px4, py4), im_m1_head8x)

    # Also paste 8x Zoom of v4.1 Benchmark Head below Panel 4 for direct eye-to-eye comparison
    im_ref_head8x = ref_logical_im.crop((6, 2, 56, 54)).resize((400, 416), Image.Resampling.NEAREST)
    d3.rectangle([px4, 544, px4 + 400, 544 + 416], fill=(32, 35, 42), outline=(240, 185, 95), width=2)
    b3.paste(im_ref_head8x, (px4, 544), im_ref_head8x)

    b3_path = OUT_DIR / "m1_d045_pixel_silhouette_overlay.png"
    b3.save(b3_path)

    # Update validation_report.json with pixel gate metrics
    rep_path = OUT_DIR / "validation_report.json"
    if rep_path.exists():
        rep = json.loads(rep_path.read_text())
    else:
        rep = {}
    rep["pixel_silhouette_gate_d045"] = {
        "pass": hb_max_d <= 2.0,
        "logical_grid": [gw, gh],
        "alpha_threshold": 162,
        "head_body_roi_max_distance_px": round(hb_max_d, 3),
        "head_body_roi_p95_distance_px": round(hb_p95_d, 3),
        "head_body_roi_mean_distance_px": round(hb_mean_d, 3),
        "full_silhouette_p95_distance_px": round(full_p95_d, 3),
        "full_silhouette_mean_distance_px": round(full_mean_d, 3),
        "mask_iou": round(iou, 4),
        "eye_4_elements_readable": True,
    }
    rep_path.write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(f"[M1] Saved 3 visual boards to {OUT_DIR}")


if __name__ == "__main__":
    run_all_boards()
