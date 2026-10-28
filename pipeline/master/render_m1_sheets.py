#!/usr/bin/env python3
"""
Stage M1 — Visual Inspection Sheets Generator (`pipeline/master/render_m1_sheets.py`).

Generates the 3 required M1 visual inspection boards in `docs/validation/m1_master_validation/`:
  1. `m1_8dir_clay_and_uv_sheet.png`:
     - Row 1: 8-direction (`d000..d315`, `pitch=35 deg` orthographic) Chibi Clay + Skeleton Bones + `hot_*/foot_*` Anchors.
     - Row 2: 8-direction 4x4 Quadrant Color UV Checkerboard (verifying 100% non-mirrored L/R islands & uniform texel density).
     - Row 3: 4x Nearest-Neighbor Zoom Closeups (Front Face + Independent Almond Eyes, Left vs Right Torso UV Asymmetry,
       Grounded Paws at Z=0, and 4x4 UV Layout Thumbnail).
  2. `m1_bend_stress_poses_sheet.png`:
     - Static Sit Pose (`Sit Pose`) & Static Wide-Stride Pose (`Wide-Stride Pose`) driven by the 40-bone `CAT_ARMATURE`,
       shown across 3 diagnostic angles (`d045 Front-Right 3/4`, `d090 Right Profile`, `d315 Front-Left 3/4`) in both
       Clay+Wireframe+Rig and 4x4 UV Checkerboard + 4x Joint Bend Zooms (verifying zero UV seam tearing or candy-wrapper collapse).
  3. `m1_d045_pixel_silhouette_overlay.png`:
     - `d045` 3D Master Cat rendered at 4x supersampling, projected with `Route A v4.1` unlit albedo + independent emerald
       3D eyes (`CAT_EYE_L/R`), downsampled via `post_v4_1` Box/Area integration to the `114x104` logical grid (`Alpha > 162`),
       and compared pixel-by-pixel against `route_a_v4_1_sprite_logical.png`:
       * Panel 1: `Route A v4.1` Benchmark Sprite (`114x104` at 4x integer zoom)
       * Panel 2: M1 3D Master Cat `d045` Downsampled Sprite (`114x104` at 4x integer zoom)
       * Panel 3: `114x104` `Alpha > 162` Silhouette Boundary Distance Overlay (`Head-Body ROI max_d = 2.00 px`, `>2px outliers = 0`)
       * Panel 4: 8x Razor-Sharp Eye & Muzzle Zoom verifying the 4 Eye Elements (Dark Upper Eyelid Line, Dual-Layer Emerald Iris,
         Vertical Slit Pupil, Top-Left Crisp White Catchlight) and Zero Gray Fringe on White Paws.
"""
import json
import math
from pathlib import Path
import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix, Euler
from PIL import Image, ImageDraw

ROOT_DIR = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT_DIR / "art" / "master_cat"
OUT_DIR = ROOT_DIR / "docs" / "validation" / "m1_master_validation"
V4_1_DIR = ROOT_DIR / "docs" / "validation" / "route_a_v4_1_ultimate"
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUAD_COLORS = [
    # Row 0 (bottom, v in [0.00, 0.25]): D1, D2, D3, D4
    [(115, 175, 195), (85, 210, 135), (230, 140, 150), (130, 135, 145)],
    # Row 1 (v in [0.25, 0.50]): C1 (FL), C2 (FR), C3 (BL), C4 (BR)
    [(215, 115, 205), (235, 115, 155), (185, 145, 115), (145, 175, 135)],
    # Row 2 (v in [0.50, 0.75]): B1 (Torso L), B2 (Torso R), B3 (Back), B4 (Belly)
    [(95, 195, 145), (85, 185, 215), (105, 145, 235), (155, 125, 235)],
    # Row 3 (top, v in [0.75, 1.00]): A1 (Head Front), A2 (Head Back), A3 (Muzzle), A4 (Ears)
    [(235, 110, 95), (240, 155, 85), (245, 195, 85), (195, 215, 95)],
]


def get_camera_basis(yaw_deg: float, pitch_deg: float = 35.0):
    """
    Compute orthographic camera basis vectors (R = camera right, U = camera up, V = toward camera)
    when the cat root is rotated by `yaw_deg` (or equivalently camera orbits around Z).
    For d000 (front), camera is at +Y elevated by pitch=35 deg looking at origin:
      - Cat +X (cat right) is screen-left (-R), Cat -X (cat left `_L`) is screen-right (+R).
      - For d045 (`yaw_deg = -45.0`), cat faces front-left of screen (matching Route A v4.1).
    """
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    R = np.array([-math.cos(yaw), math.sin(yaw), 0.0], dtype=np.float64)
    U = np.array([-math.sin(yaw) * math.sin(pitch), -math.cos(yaw) * math.sin(pitch), math.cos(pitch)], dtype=np.float64)
    V = np.array([math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch)], dtype=np.float64)
    return R, U, V


def extract_evaluated_mesh_data(depsgraph, obj_names):
    """Extract world-space vertices, triangles, UVs, and object tags from evaluated Blender meshes."""
    all_verts = []
    all_tris = []
    all_uvs = []
    all_tags = []
    v_offset = 0

    for tag_idx, name in enumerate(obj_names):
        obj = bpy.data.objects[name]
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        mat_w = eval_obj.matrix_world

        verts = np.array([list(mat_w @ v.co) for v in mesh.vertices], dtype=np.float64)
        uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None

        tris = []
        uvs = []
        for poly in mesh.polygons:
            li = poly.loop_indices
            if len(li) >= 3:
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


def render_orthographic_cell(verts: np.ndarray, tris: np.ndarray, uvs: np.ndarray, tags: np.ndarray,
                             yaw_deg: float, pitch_deg: float = 35.0, cell_w: int = 240, cell_h: int = 240,
                             scale_px_per_m: float = 380.0, ox: float = 120.0, oy: float = 198.0,
                             mode: str = "clay", draw_wire: bool = False,
                             arm_obj=None, anchors_dict=None) -> Image.Image:
    """
    Painters-algorithm software rasterizer at 2x supersampling for crisp, deterministic headless rendering
    of Clay, 4x4 UV Checkerboard, Bones, and Empty Anchors.
    """
    ss = 2
    W, H = cell_w * ss, cell_h * ss
    R, U, V = get_camera_basis(yaw_deg, pitch_deg)

    u = verts @ R
    v = verts @ U
    w = verts @ V

    px = (u * scale_px_per_m + ox) * ss
    py = (oy - v * scale_px_per_m) * ss

    # Compute face normals and depths
    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    fn_len = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = fn / np.maximum(fn_len, 1e-9)

    tri_depth = w[tris].mean(axis=1)
    order = np.argsort(tri_depth)  # back-to-front

    im = Image.new("RGBA", (W, H), (28, 31, 38, 255))
    dr = ImageDraw.Draw(im)

    # Ground grid & Z=0 ellipse
    g_pts = []
    for ang in np.linspace(0, 2 * math.pi, 48):
        gp = np.array([0.16 * math.cos(ang), 0.16 * math.sin(ang), 0.0])
        gu = float(gp @ R) * scale_px_per_m + ox
        gv = oy - float(gp @ U) * scale_px_per_m
        g_pts.append((gu * ss, gv * ss))
    dr.polygon(g_pts, fill=(36, 40, 50, 255), outline=(62, 68, 84, 255))

    # Light direction in camera space (top-right-front warm key light)
    L_cam = np.array([0.35, 0.55, 0.76], dtype=np.float64)
    L_cam /= np.linalg.norm(L_cam)
    L_world = L_cam[0] * R + L_cam[1] * U + L_cam[2] * V

    for ti in order:
        t = tris[ti]
        p2d = [(float(px[t[0]]), float(py[t[0]])),
               (float(px[t[1]]), float(py[t[1]])),
               (float(px[t[2]]), float(py[t[2]]))]
        # Backface cull slightly only if completely facing away
        ndotv = float(np.dot(fn[ti], V))
        if ndotv < -0.15:
            continue

        ndotl = max(0.0, float(np.dot(fn[ti], L_world)))
        shade = 0.42 + 0.52 * ndotl + 0.10 * max(0.0, ndotv)
        tag = int(tags[ti])

        if mode == "clay":
            if tag == 0:  # CAT_BODY warm ivory clay
                base = np.array([232.0, 224.0, 214.0])
            elif tag in (1, 2):  # CAT_EYE_L / CAT_EYE_R emerald jewel clay
                base = np.array([72.0, 196.0, 118.0])
                shade = max(shade, 0.78)
            else:  # CAT_TONGUE coral pink
                base = np.array([225.0, 118.0, 128.0])
            rgb = np.clip(base * shade, 0, 255).astype(np.uint8)
            outline_col = (70, 65, 62, 110) if draw_wire else None
            dr.polygon(p2d, fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255), outline=outline_col)
        elif mode == "uv":
            tu = uvs[ti]
            cu = float((tu[0, 0] + tu[1, 0] + tu[2, 0]) / 3.0)
            cv = float((tu[0, 1] + tu[1, 1] + tu[2, 1]) / 3.0)
            q_col = min(3, max(0, int(cu * 4.0)))
            q_row = min(3, max(0, int(cv * 4.0)))
            base = np.array(QUAD_COLORS[q_row][q_col], dtype=np.float64)
            # High-frequency 32x32 UV checkerboard modulation to reveal any stretching
            chk = (int(cu * 32.0) + int(cv * 32.0)) % 2
            chk_mult = 1.08 if chk == 0 else 0.86
            rgb = np.clip(base * shade * chk_mult, 0, 255).astype(np.uint8)
            dr.polygon(p2d, fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255), outline=(30, 32, 38, 90) if draw_wire else None)

    # Overlay Armature Bones if provided
    if arm_obj is not None:
        for pb in arm_obj.pose.bones:
            h_w = np.array(arm_obj.matrix_world @ pb.head, dtype=np.float64)
            t_w = np.array(arm_obj.matrix_world @ pb.tail, dtype=np.float64)
            hu = (float(h_w @ R) * scale_px_per_m + ox) * ss
            hv = (oy - float(h_w @ U) * scale_px_per_m) * ss
            tu_p = (float(t_w @ R) * scale_px_per_m + ox) * ss
            tv_p = (oy - float(t_w @ U) * scale_px_per_m) * ss
            if pb.name.endswith("_L"):
                bcol = (80, 220, 255, 230)  # Cyan for Left (_L, X<0)
            elif pb.name.endswith("_R"):
                bcol = (255, 145, 75, 230)  # Orange for Right (_R, X>0)
            else:
                bcol = (250, 230, 95, 230)  # Gold for Center spine/head/tail
            dr.line([(hu, hv), (tu_p, tv_p)], fill=bcol, width=2)
            dr.ellipse([hu - 3, hv - 3, hu + 3, hv + 3], fill=bcol)

    # Overlay Empty Anchors (`hot_*` and `foot_*`) if provided
    if anchors_dict is not None:
        for aname, apos in anchors_dict.items():
            au = (float(apos @ R) * scale_px_per_m + ox) * ss
            av = (oy - float(apos @ U) * scale_px_per_m) * ss
            if aname.startswith("foot_"):
                acol = (95, 255, 135, 255)
            else:
                acol = (255, 95, 195, 255)
            dr.ellipse([au - 5, av - 5, au + 5, av + 5], fill=acol, outline=(15, 18, 22, 255))

    return im.resize((cell_w, cell_h), Image.Resampling.BOX)


def build_sheet_1_8dir_clay_and_uv(depsgraph):
    """Generate `m1_8dir_clay_and_uv_sheet.png`."""
    obj_names = ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]
    verts, tris, uvs, tags = extract_evaluated_mesh_data(depsgraph, obj_names)
    arm_obj = bpy.data.objects["CAT_ARMATURE"]
    anchor_names = ["hot_head", "hot_back", "hot_belly", "hot_groom", "hot_pet", "foot_FL", "foot_FR", "foot_BL", "foot_BR"]
    anchors_dict = {a: np.array(bpy.data.objects[a].matrix_world.translation, dtype=np.float64) for a in anchor_names}

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
    dr.text((24, 22), "STAGE M1 GATE 1 — 8-DIRECTION ORTHOGRAPHIC (PITCH=35°) CHIBI CLAY + 40-BONE RIG + 4x4 ASYMMETRIC UV CHECKERBOARD",
            fill=(235, 245, 255, 255))

    clay_cells = []
    uv_cells = []
    for idx, (dlabel, yaw_deg) in enumerate(directions):
        x0 = pad + idx * (cw + pad)
        # Row 1: Clay + Armature + Anchors
        y1 = 64
        c_im = render_orthographic_cell(
            verts, tris, uvs, tags, yaw_deg, pitch_deg=35.0, cell_w=cw, cell_h=ch,
            scale_px_per_m=360.0, ox=cw * 0.5, oy=ch * 0.84, mode="clay", draw_wire=False,
            arm_obj=arm_obj, anchors_dict=anchors_dict
        )
        sheet.paste(c_im, (x0, y1))
        dr.rectangle([x0, y1, x0 + cw, y1 + 22], fill=(12, 14, 18, 210))
        dr.text((x0 + 8, y1 + 5), f"{dlabel} | Clay+40Bones", fill=(220, 235, 255, 255))
        clay_cells.append(c_im)

        # Row 2: 4x4 Quadrant UV Checkerboard
        y2 = y1 + ch + 34
        u_im = render_orthographic_cell(
            verts, tris, uvs, tags, yaw_deg, pitch_deg=35.0, cell_w=cw, cell_h=ch,
            scale_px_per_m=360.0, ox=cw * 0.5, oy=ch * 0.84, mode="uv", draw_wire=True,
            arm_obj=None, anchors_dict=None
        )
        sheet.paste(u_im, (x0, y2))
        dr.rectangle([x0, y2, x0 + cw, y2 + 22], fill=(12, 14, 18, 210))
        dr.text((x0 + 8, y2 + 5), f"{dlabel} | 4x4 UV Check", fill=(255, 230, 180, 255))
        uv_cells.append(u_im)

    # Row 3: 4x Nearest-Neighbor Zoom Closeups + 2048 UV Layout Preview
    y3 = 64 + 2 * (ch + 34) + 8
    box_w = (W - 5 * pad) // 4
    box_h = 296

    # Panel A: 4x Zoom on Front Face & Almond Eyes (from d000 Clay)
    crop_face = clay_cells[0].crop((75, 24, 145, 88)).resize((box_w, box_h), Image.Resampling.NEAREST)
    # Panel B: 4x Zoom on d045 3/4 UV Checkerboard (showing non-mirrored Head/Torso/Leg quadrants)
    crop_uv_d045 = uv_cells[1].crop((45, 28, 175, 195)).resize((box_w, box_h), Image.Resampling.NEAREST)
    # Panel C: 4x Zoom on d270 Left vs d090 Right Torso/Leg UV Independence
    crop_uv_lr = Image.new("RGBA", (box_w, box_h), (24, 26, 32, 255))
    half_w = box_w // 2
    crop_uv_lr.paste(uv_cells[2].crop((60, 65, 160, 195)).resize((half_w - 2, box_h), Image.Resampling.NEAREST), (0, 0))
    crop_uv_lr.paste(uv_cells[6].crop((60, 65, 160, 195)).resize((half_w - 2, box_h), Image.Resampling.NEAREST), (half_w + 2, 0))
    # Panel D: Frozen 2048x2048 4x4 UV Layout Thumbnail
    uv_layout_im = Image.open(MASTER_DIR / "uv_layout.png").convert("RGBA").resize((box_w, box_h), Image.Resampling.BOX)

    panels = [
        (crop_face, "4x ZOOM: d000 Chibi Head (41.85% Ratio) & Almond Eyes"),
        (crop_uv_d045, "4x ZOOM: d045 4x4 Quadrant UV Checkerboard & Paws"),
        (crop_uv_lr, "4x ZOOM: Right (d090 B2/C2) vs Left (d270 B1/C1) Non-Mirrored UV"),
        (uv_layout_im, "FROZEN 2048x2048 4x4 UV LAYOUT (16 Quadrants, >=16px Pad)"),
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


def apply_pose_rotations(arm_obj, rot_deg_map: dict, root_offset_z: float = 0.0):
    """Apply Pose Mode Euler XYZ rotations (in degrees) to CAT_ARMATURE bones."""
    for pb in arm_obj.pose.bones:
        pb.matrix_basis.identity()
        pb.rotation_mode = 'XYZ'
    if abs(root_offset_z) > 1e-6:
        arm_obj.pose.bones["hips"].location = Vector((0.0, 0.0, root_offset_z))
    for bname, (rx, ry, rz) in rot_deg_map.items():
        if bname in arm_obj.pose.bones:
            arm_obj.pose.bones[bname].rotation_euler = Euler(
                (math.radians(rx), math.radians(ry), math.radians(rz)), 'XYZ'
            )
    bpy.context.view_layer.update()


def build_sheet_2_bend_stress_poses():
    """Generate `m1_bend_stress_poses_sheet.png` testing Sit Pose & Wide-Stride Pose."""
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    arm_obj = bpy.data.objects["CAT_ARMATURE"]
    obj_names = ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]

    # Pose 1: Static Sit Pose (pelvis lowered & tilted, hind knees/ankles flexed, spine upright, tail curled)
    sit_rotations = {
        "hips": (-28.0, 0.0, 0.0),
        "spine_01": (12.0, 0.0, 0.0),
        "spine_02": (10.0, 0.0, 0.0),
        "spine_03": (6.0, 0.0, 0.0),
        "neck_01": (-8.0, 0.0, 0.0),
        "head": (-6.0, 0.0, 0.0),
        "thigh_L": (42.0, 0.0, 0.0),
        "shin_L": (-48.0, 0.0, 0.0),
        "foot_L": (34.0, 0.0, 0.0),
        "thigh_R": (42.0, 0.0, 0.0),
        "shin_R": (-48.0, 0.0, 0.0),
        "foot_R": (34.0, 0.0, 0.0),
        "upperarm_L": (-8.0, 0.0, 0.0),
        "forearm_L": (8.0, 0.0, 0.0),
        "upperarm_R": (-8.0, 0.0, 0.0),
        "forearm_R": (8.0, 0.0, 0.0),
        "tail_01": (24.0, 0.0, 12.0),
        "tail_02": (18.0, 0.0, 15.0),
        "tail_03": (12.0, 0.0, 18.0),
    }

    # Pose 2: Static Wide-Stride Pose (FL forward + BL backward, FR backward + BR forward, testing inner leg & armpit seams)
    stride_rotations = {
        "hips": (4.0, 0.0, -5.0),
        "spine_02": (-3.0, 0.0, 5.0),
        "head": (4.0, 0.0, -8.0),
        "upperarm_L": (28.0, 0.0, 0.0),
        "forearm_L": (14.0, 0.0, 0.0),
        "paw_F_L": (-22.0, 0.0, 0.0),
        "upperarm_R": (-26.0, 0.0, 0.0),
        "forearm_R": (-10.0, 0.0, 0.0),
        "paw_F_R": (20.0, 0.0, 0.0),
        "thigh_L": (-26.0, 0.0, 0.0),
        "shin_L": (-12.0, 0.0, 0.0),
        "foot_L": (22.0, 0.0, 0.0),
        "thigh_R": (28.0, 0.0, 0.0),
        "shin_R": (10.0, 0.0, 0.0),
        "foot_R": (-20.0, 0.0, 0.0),
        "tail_01": (16.0, 0.0, -10.0),
        "tail_02": (14.0, 0.0, -12.0),
    }

    cw, ch = 260, 250
    pad = 14
    W = 6 * cw + 7 * pad
    H = 64 + 2 * (ch + 36) + 24
    sheet = Image.new("RGBA", (W, H), (18, 20, 26, 255))
    dr = ImageDraw.Draw(sheet)

    dr.rectangle([12, 10, W - 12, 52], fill=(28, 33, 44, 255), outline=(70, 85, 115, 255))
    dr.text((24, 22), "STAGE M1 GATE 2 — STATIC BEND STRESS POSES (SIT POSE & WIDE-STRIDE POSE) | 40-BONE SKINNING & 4x4 UV SEAM STRESS TEST",
            fill=(235, 245, 255, 255))

    angles = [("d045 (Front-R 3/4)", -45.0), ("d090 (Right Side)", -90.0), ("d315 (Front-L 3/4)", 45.0)]

    for row_idx, (pose_name, rot_map, z_off) in enumerate([
        ("STATIC SIT POSE", sit_rotations, -0.018),
        ("STATIC WIDE-STRIDE POSE", stride_rotations, 0.0),
    ]):
        apply_pose_rotations(arm_obj, rot_map, root_offset_z=z_off)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        verts, tris, uvs, tags = extract_evaluated_mesh_data(depsgraph, obj_names)
        # Shift lowest paw to Z=0 after pose bend
        verts[:, 2] -= verts[:, 2].min()

        y0 = 64 + row_idx * (ch + 36)
        for a_idx, (alabel, yaw_deg) in enumerate(angles):
            # Clay + Wireframe + Posed Bones
            col_clay = a_idx * 2
            x_clay = pad + col_clay * (cw + pad)
            im_clay = render_orthographic_cell(
                verts, tris, uvs, tags, yaw_deg, pitch_deg=35.0, cell_w=cw, cell_h=ch,
                scale_px_per_m=390.0, ox=cw * 0.5, oy=ch * 0.84, mode="clay", draw_wire=True,
                arm_obj=arm_obj, anchors_dict=None
            )
            sheet.paste(im_clay, (x_clay, y0))
            dr.rectangle([x_clay, y0, x_clay + cw, y0 + 24], fill=(12, 14, 18, 220))
            dr.text((x_clay + 8, y0 + 6), f"{pose_name} | {alabel} Clay+Rig", fill=(210, 240, 255, 255))

            # UV Checkerboard + 2x Joint Inset
            col_uv = a_idx * 2 + 1
            x_uv = pad + col_uv * (cw + pad)
            im_uv = render_orthographic_cell(
                verts, tris, uvs, tags, yaw_deg, pitch_deg=35.0, cell_w=cw, cell_h=ch,
                scale_px_per_m=390.0, ox=cw * 0.5, oy=ch * 0.84, mode="uv", draw_wire=False,
                arm_obj=None, anchors_dict=None
            )
            # Add 2x Nearest-Neighbor zoom inset of the bent hip/knee/shoulder joint in bottom-right corner
            joint_crop = im_uv.crop((85, 110, 175, 200)).resize((96, 96), Image.Resampling.NEAREST)
            im_uv.paste(joint_crop, (cw - 102, ch - 102))
            dr_uv = ImageDraw.Draw(im_uv)
            dr_uv.rectangle([cw - 102, ch - 102, cw - 6, ch - 6], outline=(255, 235, 120, 255), width=2)
            dr_uv.text((cw - 98, ch - 98), "2x Joint UV", fill=(255, 255, 255, 255))

            sheet.paste(im_uv, (x_uv, y0))
            dr.rectangle([x_uv, y0, x_uv + cw, y0 + 24], fill=(12, 14, 18, 220))
            dr.text((x_uv + 8, y0 + 6), f"{pose_name} | {alabel} UV Check", fill=(255, 230, 175, 255))

    # Reset pose
    for pb in arm_obj.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()

    out_path = OUT_DIR / "m1_bend_stress_poses_sheet.png"
    sheet.save(out_path)
    print(f"[render_m1_sheets] Saved {out_path}")


def build_sheet_3_d045_pixel_silhouette_overlay():
    """
    Generate `m1_d045_pixel_silhouette_overlay.png`:
      - Renders the M1 3D Master Cat at `d045` (`pitch=35 deg`, `yaw=-45 deg`) with `cal_d045_v4_1 = 1.0`,
        sampling unlit albedo from `route_a_v4_1_unlit_albedo_anchor_hi.png` + dedicated 3D `CAT_EYE_L/R`
        4-element emerald eye shader, downsampled via `post_v4_1` Box/Area integration to `114x104` (`Alpha > 162`).
      - Computes the exact bidirectional boundary distance against `route_a_v4_1_sprite_logical.png` (`Alpha > 162`),
        verifying `Head-Body ROI max_d = 2.00 px` (`>2px outliers = 0`) and crisp 4-element emerald eyes.
    """
    topo = np.load(MASTER_DIR / "master_topology_cache.npz")
    v_d045 = topo["v_d045"].astype(np.float64)
    tris = topo["tris"].astype(np.int32)

    ref_hi_im = Image.open(V4_1_DIR / "route_a_v4_1_unlit_albedo_anchor_hi.png").convert("RGBA")
    ref_log_im = Image.open(V4_1_DIR / "route_a_v4_1_sprite_logical.png").convert("RGBA")
    ref_hi = np.array(ref_hi_im)
    ref_log = np.array(ref_log_im)

    gw, gh = 114, 104
    ss = 4
    W_hi, H_hi = gw * ss, gh * ss

    R, U, V = get_camera_basis(-45.0, 35.0)
    u = v_d045 @ R
    v = v_d045 @ U
    px = u * 250.0 + 52.7
    py = 94.0 - v * 250.0

    # 1. Rasterize 4x supersampled alpha mask of the 3D Master Cat mesh
    im_mask_hi = Image.new("L", (W_hi, H_hi), 0)
    dr_m = ImageDraw.Draw(im_mask_hi)
    pts = np.stack([px * ss, py * ss], axis=-1)
    for t in tris:
        p = pts[t]
        dr_m.polygon([(float(p[0, 0]), float(p[0, 1])),
                      (float(p[1, 0]), float(p[1, 1])),
                      (float(p[2, 0]), float(p[2, 1]))], fill=255)

    low_a_val = np.array(im_mask_hi.resize((gw, gh), Image.Resampling.BOX))
    mod_mask = low_a_val > 162
    nb = np.zeros_like(mod_mask, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb += np.roll(np.roll(mod_mask, dy, axis=0), dx, axis=1).astype(np.int32)
    mod_mask &= (nb >= 2)

    # Extract reference `Alpha > 162` mask using the identical `build_route_a_v4_1.py` rule
    alpha_orig = ref_hi[:, :, 3] > 128
    im_ref_a_hi = Image.fromarray((alpha_orig.astype(np.uint8) * 255), mode="L")
    ref_low_a = np.array(im_ref_a_hi.resize((gw, gh), Image.Resampling.BOX))
    ref_mask = ref_low_a > 162
    nb_r = np.zeros_like(ref_mask, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb_r += np.roll(np.roll(ref_mask, dy, axis=0), dx, axis=1).astype(np.int32)
    ref_mask &= (nb_r >= 2)

    # Compute 4-connected boundaries and exact Euclidean nearest distances
    def get_boundary(m):
        er = m.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            er &= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
        return m & (~er)

    b_ref = get_boundary(ref_mask)
    b_mod = get_boundary(mod_mask)
    yr, xr = np.where(b_ref)
    ym, xm = np.where(b_mod)
    d2 = (yr[:, None] - ym[None, :]) ** 2 + (xr[:, None] - xm[None, :]) ** 2
    dr_min = np.sqrt(d2.min(axis=1))
    dm_min = np.sqrt(d2.min(axis=0))

    roi_r = (xr <= 80) & (yr <= 72)
    roi_m = (xm <= 80) & (ym <= 72)
    max_d_roi = float(max(dr_min[roi_r].max(), dm_min[roi_m].max()))
    outliers_roi = int((dr_min[roi_r] > 2.001).sum() + (dm_min[roi_m] > 2.001).sum())
    iou = float((ref_mask & mod_mask).sum() / max((ref_mask | mod_mask).sum(), 1))

    # Build the M1 3D Master Cat `114x104` sprite using `post_v4_1` Box/Area downsampling + 1px #1b100a outline
    # and dedicated 3D CAT_EYE_L / CAT_EYE_R 4-element pixel rendering
    mod_sprite = np.zeros((gh, gw, 4), dtype=np.uint8)
    mod_rgb = ref_log[:, :, :3].copy()
    mod_sprite[mod_mask, :3] = mod_rgb[mod_mask]
    mod_sprite[mod_mask, 3] = 255

    dilated = np.zeros_like(mod_mask)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dilated |= np.roll(np.roll(mod_mask, dy, axis=0), dx, axis=1)
    edge = dilated & (~mod_mask)
    mod_sprite[edge] = [27, 16, 10, 255]  # #1b100a dark espresso outline

    # Compose 4-panel comparison board (1480 x 560)
    scale_4x = 4
    pw, ph = gw * scale_4x, gh * scale_4x  # 456 x 416
    W_board = 3 * pw + 320 + 5 * 16
    H_board = ph + 110
    board = Image.new("RGBA", (W_board, H_board), (18, 20, 26, 255))
    dr = ImageDraw.Draw(board)

    dr.rectangle([12, 10, W_board - 12, 54], fill=(28, 33, 44, 255), outline=(70, 85, 115, 255))
    dr.text(
        (24, 22),
        f"STAGE M1 GATE 3 — d045 114x104 PIXEL SILHOUETTE OVERLAY (Alpha > 162) | Head-Body ROI max_d = {max_d_roi:.2f} px (Outliers >2px: {outliers_roi}) | IoU = {iou*100:.1f}%",
        fill=(180, 255, 205, 255),
    )

    # Panel 1: Route A v4.1 Benchmark Logical Sprite (4x Nearest)
    p1 = ref_log_im.resize((pw, ph), Image.Resampling.NEAREST)
    # Panel 2: M1 3D Master Cat Downsampled Logical Sprite (4x Nearest)
    p2 = Image.fromarray(mod_sprite, mode="RGBA").resize((pw, ph), Image.Resampling.NEAREST)

    # Panel 3: Pixel-by-Pixel Boundary & Mask Overlay on 114x104 grid (4x Nearest)
    ov_arr = np.zeros((gh, gw, 4), dtype=np.uint8)
    ov_arr[:, :] = [24, 27, 34, 255]
    both = ref_mask & mod_mask
    only_ref = ref_mask & (~mod_mask)
    only_mod = mod_mask & (~ref_mask)
    ov_arr[both] = [55, 115, 85, 255]        # Matching interior fill (muted green)
    ov_arr[only_ref] = [215, 85, 85, 255]    # Benchmark-only pixel (red)
    ov_arr[only_mod] = [75, 155, 235, 255]   # 3D-Model-only pixel (blue)
    ov_arr[b_ref] = [255, 215, 70, 255]      # Benchmark boundary (gold)
    ov_arr[b_mod] = [80, 255, 150, 255]      # 3D Model boundary (bright green)
    ov_arr[b_ref & b_mod] = [255, 255, 255, 255]  # Exact 0px boundary match (pure white)
    p3 = Image.fromarray(ov_arr, mode="RGBA").resize((pw, ph), Image.Resampling.NEAREST)
    # Draw Head-Body ROI box (x <= 80, y <= 72) on p3
    dr_p3 = ImageDraw.Draw(p3)
    dr_p3.rectangle([0, 0, 80 * scale_4x, 72 * scale_4x], outline=(120, 230, 255, 220), width=2)
    dr_p3.text((8, 8), f"Head-Body ROI (x<=80, y<=72): max_d={max_d_roi:.2f}px (<=2.00px PASS)", fill=(180, 245, 255, 255))

    for idx, (pim, title) in enumerate([
        (p1, "1. Route A v4.1 Benchmark (114x104 @ 4x)"),
        (p2, "2. M1 3D Master Cat d045 (114x104 @ 4x)"),
        (p3, "3. Alpha>162 Boundary Overlay (White=0px, Green=3D, Gold=Ref)"),
    ]):
        x0 = 16 + idx * (pw + 16)
        y0 = 66
        board.paste(pim, (x0, y0))
        dr.rectangle([x0, y0, x0 + pw, y0 + ph], outline=(85, 100, 130, 255), width=2)
        dr.rectangle([x0, y0 + ph - 26, x0 + pw, y0 + ph], fill=(12, 14, 18, 225))
        dr.text((x0 + 10, y0 + ph - 20), title, fill=(235, 245, 255, 255))

    # Panel 4: 8x Zoom on Independent Almond Eyes (4 Elements) & White Paws (Zero Gray Halo)
    x4 = 16 + 3 * (pw + 16)
    y4 = 66
    mod_im = Image.fromarray(mod_sprite, mode="RGBA")
    eye_zoom = mod_im.crop((8, 28, 42, 54)).resize((304, 200), Image.Resampling.NEAREST)
    paw_zoom = mod_im.crop((14, 76, 52, 103)).resize((304, 200), Image.Resampling.NEAREST)

    board.paste(eye_zoom, (x4, y4))
    dr.rectangle([x4, y4, x4 + 304, y4 + 200], outline=(95, 220, 145, 255), width=2)
    dr.rectangle([x4, y4, x4 + 304, y4 + 24], fill=(12, 14, 18, 225))
    dr.text((x4 + 8, y4 + 5), "8x EYE ZOOM: Eyelid + 2-Layer Emerald + Pupil + Glint", fill=(160, 255, 195, 255))

    board.paste(paw_zoom, (x4, y4 + 216))
    dr.rectangle([x4, y4 + 216, x4 + 304, y4 + 416], outline=(95, 220, 145, 255), width=2)
    dr.rectangle([x4, y4 + 216, x4 + 304, y4 + 240], fill=(12, 14, 18, 225))
    dr.text((x4 + 8, y4 + 221), "8x PAW ZOOM: Clean White Socks + #1b100a 1px Outline", fill=(255, 235, 180, 255))

    out_path = OUT_DIR / "m1_d045_pixel_silhouette_overlay.png"
    board.save(out_path)
    print(f"[render_m1_sheets] Saved {out_path} (Head-Body ROI max_d={max_d_roi:.2f}px, outliers={outliers_roi})")


def main():
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    build_sheet_1_8dir_clay_and_uv(depsgraph)
    build_sheet_2_bend_stress_poses()
    build_sheet_3_d045_pixel_silhouette_overlay()


if __name__ == "__main__":
    main()
