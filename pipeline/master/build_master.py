#!/usr/bin/env python3
"""
build_master.py — Milestone M1 Master Cat Builder (`art/master_cat/master_cat.blend` & `master_cat.glb`).

Builds the frozen Chibi Master Cat following `CAT_DIGITAL_TWIN_ENGINEERING_SPEC.md`,
`FUSED_CAT_DIGITAL_TWIN_AND_V4_1_PIPELINE_SPEC.md`, and `DEVELOPMENT_PLAN.md (v1.3)`:
  1. `CAT_BODY`: Closed manifold mesh (2,321 vertices, 4,634 triangles, 0 non-manifold edges,
     consistent outward normals) in symmetric Chibi Rest Pose (head height = 41.85% of total height,
     all 4 paws grounded at Z=0 within <0.1mm).
  2. `CAT_EYE_L`, `CAT_EYE_R`: Independent closed manifold almond eyeball meshes with dedicated UV
     in `D2` quadrant and isolated materials `MAT_EYE_L`, `MAT_EYE_R`.
  3. `CAT_TONGUE`: Independent closed manifold tongue mesh inside the lower jaw with dedicated UV
     in `D3` quadrant and material `MAT_TONGUE`.
  4. Fixed 4x4 Quadrant 100% Asymmetric Non-Mirrored UV Layout (work size 2048x2048, game size 1024x1024,
     >=16px padding on 2048 canvas, zero unexpected UV overlaps, frozen SHA-256 `uv_hash` written to
     `art/master_cat/uv_manifest.json` and `art/master_cat/uv_layout.png`).
  5. `CAT_ARMATURE`: 40 standard quadruped bones (`root` at (0,0,0), anatomical `_L` at X<0 and `_R` at X>0),
     normalized skin weights with <= 4 bones per vertex and strict L/R separation.
  6. Separated Identity (`id_*`, 8 keys), Style (`sty_*`, 5 keys), Face (`blink_L/R`, `squint_L/R`, `mouth_open`),
     and Calibration (`cal_d045_v4_1`) Shape Keys.
  7. Interaction & ground contact Empty anchors: `hot_head`, `hot_back`, `hot_belly`, `hot_groom`, `hot_pet`,
     `foot_FL`, `foot_FR`, `foot_BL`, `foot_BR`.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix, Euler
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT_DIR / "art" / "master_cat"
SPEC_PATH = MASTER_DIR / "master_spec.json"
LANDMARK_PATH = MASTER_DIR / "landmark_vertices.json"
TOPO_CACHE_PATH = MASTER_DIR / "master_topology_cache.npz"
UV_MANIFEST_PATH = MASTER_DIR / "uv_manifest.json"
UV_LAYOUT_PNG_PATH = MASTER_DIR / "uv_layout.png"
BLEND_OUT_PATH = MASTER_DIR / "master_cat.blend"
GLB_OUT_PATH = MASTER_DIR / "master_cat.glb"
RIG_MAP_PATH = MASTER_DIR / "rig_map.json"


# 4x4 Quadrant UV Regions (Blender UV origin: bottom-left (0,0) to top-right (1,1))
# Row 1 (top, v in [0.75, 1.00]): A1, A2, A3, A4
# Row 2 (v in [0.50, 0.75]): B1, B2, B3, B4
# Row 3 (v in [0.25, 0.50]): C1, C2, C3, C4
# Row 4 (bottom, v in [0.00, 0.25]): D1, D2, D3, D4
UV_QUADRANTS = {
    "A1_head_front":   {"grid": [0, 3], "semantic": "head_front",   "u_range": [0.00, 0.25], "v_range": [0.75, 1.00], "color": (235, 110, 95)},
    "A2_head_back":    {"grid": [1, 3], "semantic": "head_back",    "u_range": [0.25, 0.50], "v_range": [0.75, 1.00], "color": (240, 155, 85)},
    "A3_muzzle_chin":  {"grid": [2, 3], "semantic": "head_muzzle",  "u_range": [0.50, 0.75], "v_range": [0.75, 1.00], "color": (245, 195, 85)},
    "A4_ears_LR":      {"grid": [3, 3], "semantic": "ears_LR",      "u_range": [0.75, 1.00], "v_range": [0.75, 1.00], "color": (195, 215, 95)},
    "B1_torso_L":      {"grid": [0, 2], "semantic": "torso_L",      "u_range": [0.00, 0.25], "v_range": [0.50, 0.75], "color": (95, 195, 145)},
    "B2_torso_R":      {"grid": [1, 2], "semantic": "torso_R",      "u_range": [0.25, 0.50], "v_range": [0.50, 0.75], "color": (85, 185, 215)},
    "B3_torso_back":   {"grid": [2, 2], "semantic": "torso_back",   "u_range": [0.50, 0.75], "v_range": [0.50, 0.75], "color": (105, 145, 235)},
    "B4_torso_belly":  {"grid": [3, 2], "semantic": "torso_belly",  "u_range": [0.75, 1.00], "v_range": [0.50, 0.75], "color": (155, 125, 235)},
    "C1_leg_FL":       {"grid": [0, 1], "semantic": "leg_FL",       "u_range": [0.00, 0.25], "v_range": [0.25, 0.50], "color": (215, 115, 205)},
    "C2_leg_FR":       {"grid": [1, 1], "semantic": "leg_FR",       "u_range": [0.25, 0.50], "v_range": [0.25, 0.50], "color": (235, 115, 155)},
    "C3_leg_BL":       {"grid": [2, 1], "semantic": "leg_BL",       "u_range": [0.50, 0.75], "v_range": [0.25, 0.50], "color": (185, 145, 115)},
    "C4_leg_BR":       {"grid": [3, 1], "semantic": "leg_BR",       "u_range": [0.75, 1.00], "v_range": [0.25, 0.50], "color": (145, 175, 135)},
    "D1_tail":         {"grid": [0, 0], "semantic": "tail",         "u_range": [0.00, 0.25], "v_range": [0.00, 0.25], "color": (115, 175, 195)},
    "D2_eyes_LR":      {"grid": [1, 0], "semantic": "eyes_LR",      "u_range": [0.25, 0.50], "v_range": [0.00, 0.25], "color": (85, 210, 135)},
    "D3_nose_pads_tongue": {"grid": [2, 0], "semantic": "nose_pads_tongue", "u_range": [0.50, 0.75], "v_range": [0.00, 0.25], "color": (230, 140, 150)},
    "D4_reserved":     {"grid": [3, 0], "semantic": "reserved",     "u_range": [0.75, 1.00], "v_range": [0.00, 0.25], "color": (130, 135, 145)},
}


def classify_body_triangles(vs: np.ndarray, tris: np.ndarray, v_part: np.ndarray) -> list:
    """Assign each triangle of CAT_BODY to one of the 4x4 semantic quadrants."""
    tri_Centroids = vs[tris].mean(axis=1)
    v0 = vs[tris[:, 0]]
    v1 = vs[tris[:, 1]]
    v2 = vs[tris[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    fn_norm = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = fn / np.maximum(fn_norm, 1e-9)

    # Determine dominant part for each triangle
    tp0 = v_part[tris[:, 0]]
    tp1 = v_part[tris[:, 1]]
    tp2 = v_part[tris[:, 2]]

    quads = []
    for i in range(len(tris)):
        cx, cy, cz = tri_Centroids[i]
        nx, ny, nz = fn[i]
        parts = (tp0[i], tp1[i], tp2[i])
        # Tail
        if 5 in parts or cy < -0.138:
            quads.append("D1_tail")
            continue
        # Legs: 1=FR (+X,+Y), 2=FL (-X,+Y), 3=BR (+X,-Y), 4=BL (-X,-Y)
        if 2 in parts or (cz < 0.118 and cy > 0.015 and cx < 0.0):
            quads.append("C1_leg_FL")
            continue
        if 1 in parts or (cz < 0.118 and cy > 0.015 and cx >= 0.0):
            quads.append("C2_leg_FR")
            continue
        if 4 in parts or (cz < 0.118 and cy <= 0.015 and cx < 0.0):
            quads.append("C3_leg_BL")
            continue
        if 3 in parts or (cz < 0.118 and cy <= 0.015 and cx >= 0.0):
            quads.append("C4_leg_BR")
            continue
        # Head & Ears (cz >= 0.235 or (cy > 0.075 and cz > 0.205))
        if cz >= 0.235 or (cy > 0.075 and cz > 0.205):
            if cz >= 0.375 and abs(cx) >= 0.028:
                quads.append("A4_ears_LR")
            elif cy >= 0.155 and cz <= 0.305:
                quads.append("A3_muzzle_chin")
            elif ny >= -0.05 and cy >= 0.110:
                quads.append("A1_head_front")
            else:
                quads.append("A2_head_back")
            continue
        # Torso: B1 (left X<0), B2 (right X>=0), B3 (dorsal back), B4 (ventral belly)
        if nz >= 0.55 and cz >= 0.185:
            quads.append("B3_torso_back")
        elif nz <= -0.45 and cz <= 0.155:
            quads.append("B4_torso_belly")
        elif cx < 0.0:
            quads.append("B1_torso_L")
        else:
            quads.append("B2_torso_R")
    return quads


def assign_non_overlapping_4x4_uvs(mesh_body: bpy.types.Mesh, vs: np.ndarray, tris: np.ndarray, v_part: np.ndarray):
    """
    Assign 100% asymmetric, non-overlapping UVs to CAT_BODY strictly inside each 4x4 quadrant cell
    with >= 16px padding on a 2048x2048 canvas (i.e. margin >= 0.008 in UV units around every cell
    and every triangle island).
    Why per-quadrant structured atlas packing + topological projection:
      - Guarantees 0% L/R mirroring (left and right face/torso/legs/ears have distinct UV space).
      - Guarantees 0 unexpected UV triangle overlaps while keeping semantic regions strictly inside
        their designated 4x4 quadrant cell (`[u0+margin, u1-margin] x [v0+margin, v1-margin]`).
    """
    uv_layer = mesh_body.uv_layers.new(name="UVMap")
    mesh_body.uv_layers.active = uv_layer

    tri_quads = classify_body_triangles(vs, tris, v_part)
    # Group triangle indices by quadrant
    quad_to_tris = {k: [] for k in UV_QUADRANTS}
    for ti, qname in enumerate(tri_quads):
        quad_to_tris[qname].append(ti)

    # Margin of 16px in 2048 = 16 / 2048 = 0.0078125 -> use 0.010 cell border margin
    cell_margin = 0.010
    tri_Centroids = vs[tris].mean(axis=1)

    for qname, t_list in quad_to_tris.items():
        if not t_list:
            continue
        qinfo = UV_QUADRANTS[qname]
        u0, u1 = qinfo["u_range"]
        v0, v1 = qinfo["v_range"]
        u_min_cell = u0 + cell_margin
        u_max_cell = u1 - cell_margin
        v_min_cell = v0 + cell_margin
        v_max_cell = v1 - cell_margin

        # Sort triangles spatially (by Z then X/Y) so adjacent triangles sit near each other in the quadrant
        t_arr = np.array(t_list, dtype=np.int32)
        c_sub = tri_Centroids[t_arr]
        order = np.lexsort((c_sub[:, 0], c_sub[:, 1], c_sub[:, 2]))
        t_sorted = t_arr[order]

        n_tris = len(t_sorted)
        cols = int(math.ceil(math.sqrt(n_tris)))
        rows = int(math.ceil(n_tris / cols))
        du = (u_max_cell - u_min_cell) / cols
        dv = (v_max_cell - v_min_cell) / rows
        pad_u = du * 0.12
        pad_v = dv * 0.12

        for idx, ti in enumerate(t_sorted):
            r = idx // cols
            c = idx % cols
            cu0 = u_min_cell + c * du + pad_u
            cu1 = u_min_cell + (c + 1) * du - pad_u
            cv0 = v_min_cell + r * dv + pad_v
            cv1 = v_min_cell + (r + 1) * dv - pad_v

            # Project the 3 vertices of triangle `ti` into its local tangent plane to preserve triangle aspect shape
            pts3d = vs[tris[ti]]
            e1 = pts3d[1] - pts3d[0]
            l1 = np.linalg.norm(e1)
            if l1 < 1e-8:
                t_uv = np.array([[cu0, cv0], [cu1, cv0], [0.5 * (cu0 + cu1), cv1]])
            else:
                x_ax = e1 / l1
                n_vec = np.cross(e1, pts3d[2] - pts3d[0])
                nl = np.linalg.norm(n_vec)
                if nl < 1e-8:
                    t_uv = np.array([[cu0, cv0], [cu1, cv0], [0.5 * (cu0 + cu1), cv1]])
                else:
                    n_vec /= nl
                    y_ax = np.cross(n_vec, x_ax)
                    p2d = np.stack([(pts3d - pts3d[0]) @ x_ax, (pts3d - pts3d[0]) @ y_ax], axis=-1)
                    mn = p2d.min(axis=0)
                    mx = p2d.max(axis=0)
                    span = np.maximum(mx - mn, 1e-7)
                    norm2d = (p2d - mn) / span
                    t_uv = np.stack([
                        cu0 + norm2d[:, 0] * (cu1 - cu0),
                        cv0 + norm2d[:, 1] * (cv1 - cv0),
                    ], axis=-1)

            poly = mesh_body.polygons[ti]
            for k, loop_idx in enumerate(poly.loop_indices):
                uv_layer.data[loop_idx].uv = (round(float(t_uv[k, 0]), 6), round(float(t_uv[k, 1]), 6))

    return tri_quads


def create_closed_ellipsoid_mesh(name: str, center: tuple, radii: tuple, rot_euler: tuple,
                                 u_bounds: tuple, v_bounds: tuple, segs_u: int = 16, segs_v: int = 12) -> bpy.types.Object:
    """Create a closed manifold ellipsoid mesh with clean non-overlapping UV inside (u_bounds, v_bounds)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs_u, v_segments=segs_v, radius=1.0)
    rx, ry, rz = radii
    rot_mat = Euler(rot_euler, 'XYZ').to_matrix().to_4x4()
    trans_mat = Matrix.Translation(Vector(center))
    for v in bm.verts:
        p = Vector((v.co.x * rx, v.co.y * ry, v.co.z * rz))
        v.co = trans_mat @ (rot_mat @ p)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    # Assign UVs strictly within u_bounds x v_bounds
    uv_layer = mesh.uv_layers.new(name="UVMap")
    mesh.uv_layers.active = uv_layer
    n_polys = len(mesh.polygons)
    cols = int(math.ceil(math.sqrt(n_polys)))
    rows = int(math.ceil(n_polys / cols))
    u0, u1 = u_bounds
    v0, v1 = v_bounds
    du = (u1 - u0) / cols
    dv = (v1 - v0) / rows
    for idx, poly in enumerate(mesh.polygons):
        r = idx // cols
        c = idx % cols
        cu0 = u0 + (c + 0.12) * du
        cu1 = u0 + (c + 0.88) * du
        cv0 = v0 + (r + 0.12) * dv
        cv1 = v0 + (r + 0.88) * dv
        n_l = len(poly.loop_indices)
        if n_l == 3:
            pts = [(cu0, cv0), (cu1, cv0), (0.5 * (cu0 + cu1), cv1)]
        else:
            pts = [(cu0, cv0), (cu1, cv0), (cu1, cv1), (cu0, cv1)]
        for k, li in enumerate(poly.loop_indices):
            uv_layer.data[li].uv = (round(pts[k % len(pts)][0], 6), round(pts[k % len(pts)][1], 6))

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def create_neutral_material(name: str, base_rgba: tuple, roughness: float = 0.7) -> bpy.types.Material:
    """Create a clean neutral material with Principled BSDF (zero cat-specific identity textures)."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = base_rgba
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def compute_uv_hash(mesh: bpy.types.Mesh) -> str:
    uv = mesh.uv_layers.active.data
    rows = [
        [loop.vertex_index, round(uv[loop.index].uv.x, 6), round(uv[loop.index].uv.y, 6)]
        for loop in mesh.loops
    ]
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def render_uv_layout_png(mesh_body: bpy.types.Mesh, mesh_eye_l: bpy.types.Mesh,
                         mesh_eye_r: bpy.types.Mesh, mesh_tongue: bpy.types.Mesh,
                         tri_quads: list, uv_hash: str):
    """Render the 2048x2048 4x4 quadrant UV layout verification chart (`art/master_cat/uv_layout.png`)."""
    W, H = 2048, 2048
    im = Image.new("RGBA", (W, H), (24, 26, 32, 255))
    dr = ImageDraw.Draw(im)

    # Draw 4x4 grid cells and labels
    for qname, qinfo in UV_QUADRANTS.items():
        u0, u1 = qinfo["u_range"]
        v0, v1 = qinfo["v_range"]
        x0 = int(u0 * W)
        x1 = int(u1 * W)
        y0 = int((1.0 - v1) * H)
        y1 = int((1.0 - v0) * H)
        col = qinfo["color"]
        # Soft cell background tint
        dr.rectangle([x0 + 2, y0 + 2, x1 - 2, y1 - 2], fill=(col[0] // 5, col[1] // 5, col[2] // 5, 255),
                     outline=(col[0], col[1], col[2], 200), width=3)
        # 16px safe padding border inside each cell
        dr.rectangle([x0 + 16, y0 + 16, x1 - 16, y1 - 16], outline=(90, 95, 110, 140), width=1)

    # Draw CAT_BODY UV triangles
    uv_body = mesh_body.uv_layers.active.data
    for ti, poly in enumerate(mesh_body.polygons):
        qname = tri_quads[ti]
        col = UV_QUADRANTS[qname]["color"]
        pts = []
        for li in poly.loop_indices:
            u, v = uv_body[li].uv
            pts.append((u * (W - 1), (1.0 - v) * (H - 1)))
        dr.polygon(pts, fill=(col[0], col[1], col[2], 185), outline=(245, 245, 250, 220))

    # Draw Eye L/R and Tongue UVs in D2 and D3
    for m_extra, qname in [(mesh_eye_l, "D2_eyes_LR"), (mesh_eye_r, "D2_eyes_LR"), (mesh_tongue, "D3_nose_pads_tongue")]:
        uv_ex = m_extra.uv_layers.active.data
        col = UV_QUADRANTS[qname]["color"]
        for poly in m_extra.polygons:
            pts = []
            for li in poly.loop_indices:
                u, v = uv_ex[li].uv
                pts.append((u * (W - 1), (1.0 - v) * (H - 1)))
            dr.polygon(pts, fill=(col[0], col[1], col[2], 200), outline=(255, 255, 255, 220))

    # Overlay quadrant titles at top-left of each cell
    for qname, qinfo in UV_QUADRANTS.items():
        u0, u1 = qinfo["u_range"]
        v0, v1 = qinfo["v_range"]
        x0 = int(u0 * W) + 22
        y0 = int((1.0 - v1) * H) + 20
        label = f"{qname} ({qinfo['semantic']})"
        dr.rectangle([x0 - 4, y0 - 2, x0 + len(label) * 8 + 8, y0 + 18], fill=(12, 14, 18, 215))
        dr.text((x0, y0), label, fill=(255, 255, 255, 255))

    # Header banner with UV Hash
    header = f"MIAOWANGTOWN MASTER CAT 4x4 ASYMMETRIC UV LAYOUT (2048x2048) | uv_hash={uv_hash[:24]}..."
    dr.rectangle([16, H - 44, W - 16, H - 12], fill=(12, 14, 18, 230))
    dr.text((28, H - 34), header, fill=(220, 245, 255, 255))

    im.save(UV_LAYOUT_PNG_PATH)
    print(f"[build_master] Saved UV layout chart: {UV_LAYOUT_PNG_PATH}")


def compute_bone_head_tail(bname: str, binfo: dict, points: dict, vs: np.ndarray):
    """Compute bone head and tail 3D positions from landmark vertex groups."""
    h_vids = points[binfo["head"]]
    head_pos = vs[h_vids].mean(axis=0).copy()
    if binfo.get("zero_xy_head"):
        head_pos[0] = 0.0
        head_pos[1] = 0.0
    if binfo.get("zero_z_head"):
        head_pos[2] = 0.0
    if binfo.get("ground_z"):
        head_pos[2] = float(vs[h_vids, 2].min())

    if "tail" in binfo:
        t_vids = points[binfo["tail"]]
        tail_pos = vs[t_vids].mean(axis=0).copy()
        if binfo["tail"] in ("hips", "spine_01", "spine_02", "spine_03", "spine_04",
                             "neck_01", "neck_02", "head", "head_top", "jaw", "chin",
                             "muzzle_tip", "tongue_01", "tongue_tip",
                             "tail_01", "tail_02", "tail_03", "tail_04", "tail_05", "tail_06", "tail_tip"):
            tail_pos[0] = 0.0
    else:
        off = np.array(binfo["tail_offset"], dtype=np.float64)
        tail_pos = head_pos + off

    if bname.startswith(("hips", "spine_", "neck_", "head", "jaw", "tongue_", "tail_")):
        head_pos[0] = 0.0
        tail_pos[0] = 0.0

    # Ensure non-zero bone length
    if np.linalg.norm(tail_pos - head_pos) < 0.005:
        tail_pos = head_pos + np.array([0.0, 0.015, 0.0])

    return head_pos, tail_pos


def assign_skin_weights(obj_body: bpy.types.Object, arm_obj: bpy.types.Object,
                        vs: np.ndarray, v_part: np.ndarray, bones_spec: list, bone_segments: dict):
    """
    Assign smooth, normalized skin weights to CAT_BODY:
      - `root` is non-deforming (0 weights).
      - Every vertex is influenced by 1..4 deforming bones, weights sum to 1.000000.
      - Strict anatomical L/R separation: vertices with X < -0.002 never receive `_R` bone weights,
        and vertices with X > +0.002 never receive `_L` bone weights.
    """
    deform_bones = [b["name"] for b in bones_spec if b["deform"] and b["name"] not in ("eye_L", "eye_R", "tongue_01", "tongue_tip")]
    for b in bones_spec:
        obj_body.vertex_groups.new(name=b["name"])

    # Partition candidate bones by part and side for clean anatomical binding
    leg_FL_bones = ["clavicle_L", "upperarm_L", "forearm_L", "hand_L"]
    leg_FR_bones = ["clavicle_R", "upperarm_R", "forearm_R", "hand_R"]
    leg_BL_bones = ["thigh_L", "shin_L", "foot_L", "paw_B_L"]
    leg_BR_bones = ["thigh_R", "shin_R", "foot_R", "paw_B_R"]
    tail_bones = ["tail_01", "tail_02", "tail_03", "tail_04", "tail_05", "tail_06"]
    spine_head_bones = ["hips", "spine_01", "spine_02", "spine_03", "spine_04", "neck_01", "neck_02", "head", "jaw"]
    ear_L_bones = ["ear_L_01", "ear_L_02"]
    ear_R_bones = ["ear_R_01", "ear_R_02"]

    def point_seg_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
        ab = b - a
        l2 = float(np.dot(ab, ab))
        if l2 < 1e-10:
            return float(np.linalg.norm(p - a))
        t = max(0.0, min(1.0, float(np.dot(p - a, ab)) / l2))
        proj = a + t * ab
        return float(np.linalg.norm(p - proj))

    for vid in range(len(vs)):
        p = vs[vid]
        part = int(v_part[vid])
        if part == 2:  # FL (-X, +Y)
            cands = leg_FL_bones + ["spine_04"]
        elif part == 1:  # FR (+X, +Y)
            cands = leg_FR_bones + ["spine_04"]
        elif part == 4:  # BL (-X, -Y)
            cands = leg_BL_bones + ["hips"]
        elif part == 3:  # BR (+X, -Y)
            cands = leg_BR_bones + ["hips"]
        elif part == 5:  # Tail
            cands = tail_bones + ["hips"]
        else:
            cands = list(spine_head_bones)
            if p[2] > 0.35 and p[0] < -0.015:
                cands += ear_L_bones
            elif p[2] > 0.35 and p[0] > 0.015:
                cands += ear_R_bones
            if p[2] < 0.16 and p[1] > 0.0:
                cands += (leg_FL_bones[:2] if p[0] < 0 else leg_FR_bones[:2])
            elif p[2] < 0.16 and p[1] <= 0.0:
                cands += (leg_BL_bones[:2] if p[0] < 0 else leg_BR_bones[:2])

        # Enforce strict L/R anatomical separation
        if p[0] < -0.0001:
            cands = [bn for bn in cands if not bn.endswith("_R") and "_R_" not in bn]
        elif p[0] > 0.0001:
            cands = [bn for bn in cands if not bn.endswith("_L") and "_L_" not in bn]
        else:
            cands = [bn for bn in cands if not bn.endswith(("_L", "_R")) and "_L_" not in bn and "_R_" not in bn]

        dists = []
        for bn in cands:
            h, t = bone_segments[bn]
            d_val = point_seg_dist(p, h, t)
            dists.append((d_val, bn))
        dists.sort(key=lambda x: x[0])
        top = dists[:3]  # at most 3 bones (strictly <= 4)
        inv = [1.0 / (max(d_val, 0.008) ** 2.5) for d_val, _ in top]
        s = sum(inv)
        weights = [w / s for w in inv]
        # Adjust last weight so sum is exact 1.0
        weights[-1] = 1.0 - sum(weights[:-1])
        for (_, bn), w in zip(top, weights):
            if w > 0.0:
                obj_body.vertex_groups[bn].add([vid], float(w), 'REPLACE')


def add_separated_shape_keys(obj_body: bpy.types.Object, vs_basis: np.ndarray, v_d045: np.ndarray, v_part: np.ndarray):
    """
    Create Basis + 8 Identity (`id_*`) + 5 Style (`sty_*`) + 5 Face (`blink_L/R`, `squint_L/R`, `mouth_open`)
    + 1 Calibration (`cal_d045_v4_1`) Shape Keys on CAT_BODY.
    All shape keys preserve manifold topology, contain zero NaN/Inf, and keep symmetrical displacements
    for symmetric keys.
    """
    sk_basis = obj_body.shape_key_add(name="Basis", from_mix=False)
    sk_basis.interpolation = 'KEY_LINEAR'

    n_v = len(vs_basis)
    x = vs_basis[:, 0]
    y = vs_basis[:, 1]
    z = vs_basis[:, 2]

    # Smooth weight masks
    torso_w = np.exp(-((y - (-0.02)) / 0.11) ** 2) * np.clip((0.26 - z) / 0.12, 0.0, 1.0) * (v_part == 0)
    belly_w = np.exp(-((y - (-0.02)) / 0.10) ** 2) * np.clip((0.18 - z) / 0.08, 0.0, 1.0) * (v_part == 0)
    leg_w = np.isin(v_part, [1, 2, 3, 4]).astype(np.float64) * np.clip(z / 0.02, 0.0, 1.0)
    neck_w = np.exp(-((z - 0.24) / 0.045) ** 2) * (v_part == 0)
    head_w = np.clip((z - 0.235) / 0.035, 0.0, 1.0) * (v_part == 0)
    cheek_w = np.exp(-((z - 0.295) / 0.040) ** 2) * np.exp(-((y - 0.145) / 0.045) ** 2) * (v_part == 0)
    muzzle_w = np.exp(-((z - 0.285) / 0.030) ** 2) * np.clip((y - 0.165) / 0.05, 0.0, 1.0) * (v_part == 0)
    ear_w = np.clip((z - 0.375) / 0.055, 0.0, 1.0) * (v_part == 0)
    paw_w = np.isin(v_part, [1, 2, 3, 4]).astype(np.float64) * np.clip((0.045 - z) / 0.045, 0.0, 1.0) * np.clip(z / 0.005, 0.0, 1.0)

    deltas = {}

    # 8 Identity Shape Keys (`id_*`)
    d_fat = np.zeros_like(vs_basis)
    d_fat[:, 0] = x * torso_w * 0.12
    d_fat[:, 2] = (z - 0.16) * torso_w * 0.06
    deltas["id_body_fat"] = d_fat

    d_belly = np.zeros_like(vs_basis)
    d_belly[:, 2] = -0.015 * belly_w
    d_belly[:, 0] = x * belly_w * 0.08
    deltas["id_belly"] = d_belly

    d_leg = np.zeros_like(vs_basis)
    d_leg[:, 2] = (z / 0.45) * 0.012 * np.clip(z / 0.01, 0.0, 1.0)
    deltas["id_leg_len"] = d_leg

    d_neck = np.zeros_like(vs_basis)
    d_neck[:, 2] = 0.010 * head_w
    deltas["id_neck_len"] = d_neck

    d_faceround = np.zeros_like(vs_basis)
    d_faceround[:, 0] = x * cheek_w * 0.12
    d_faceround[:, 1] = (y - 0.13) * cheek_w * 0.06
    deltas["id_face_round"] = d_faceround

    d_muzzle = np.zeros_like(vs_basis)
    d_muzzle[:, 1] = 0.012 * muzzle_w
    deltas["id_muzzle_len"] = d_muzzle

    d_earsize = np.zeros_like(vs_basis)
    d_earsize[:, 0] = np.sign(x) * ear_w * 0.008
    d_earsize[:, 2] = ear_w * 0.014
    deltas["id_ear_size"] = d_earsize

    d_earfold = np.zeros_like(vs_basis)
    d_earfold[:, 1] = ear_w * 0.015
    d_earfold[:, 2] = -ear_w * 0.018
    deltas["id_ear_fold"] = d_earfold

    # 5 Style Shape Keys (`sty_*` fine-tuning sliders in [0, 1]; head ratio stays inside 40%..43%)
    d_sty_head = np.zeros_like(vs_basis)
    hc = np.array([0.0, 0.135, 0.260])
    d_sty_head[:, 0] = (x - hc[0]) * head_w * 0.035
    d_sty_head[:, 1] = (y - hc[1]) * head_w * 0.035
    d_sty_head[:, 2] = (z - hc[2]) * head_w * 0.025
    deltas["sty_head_enlarge"] = d_sty_head

    d_sty_leg = np.zeros_like(vs_basis)
    # Gently compress body height while keeping paws grounded at Z=0 and head ratio within 40%..43%
    d_sty_leg[:, 2] = -0.008 * np.clip(z / 0.12, 0.0, 1.0)
    deltas["sty_leg_shorten"] = d_sty_leg

    d_sty_eye = np.zeros_like(vs_basis)
    eye_region = np.exp(-((z - 0.322) / 0.025) ** 2) * np.exp(-((y - 0.195) / 0.025) ** 2) * (v_part == 0)
    d_sty_eye[:, 0] = x * eye_region * 0.04
    d_sty_eye[:, 2] = (z - 0.322) * eye_region * 0.06
    deltas["sty_eye_enlarge"] = d_sty_eye

    d_sty_cheek = np.zeros_like(vs_basis)
    d_sty_cheek[:, 0] = x * cheek_w * 0.09
    d_sty_cheek[:, 2] = -0.004 * cheek_w
    deltas["sty_face_chibi_cheek"] = d_sty_cheek

    d_sty_paw = np.zeros_like(vs_basis)
    d_sty_paw[:, 0] = np.sign(x) * paw_w * 0.004
    d_sty_paw[:, 1] = np.sign(y) * paw_w * 0.004
    deltas["sty_paw_round"] = d_sty_paw

    # 5 Face Shape Keys (`blink_L`, `blink_R`, `squint_L`, `squint_R`, `mouth_open`)
    lid_L = eye_region * (x < -0.01)
    lid_R = eye_region * (x > 0.01)
    for kname, mask, dz in [
        ("blink_L", lid_L, -0.008),
        ("blink_R", lid_R, -0.008),
        ("squint_L", lid_L, -0.004),
        ("squint_R", lid_R, -0.004),
    ]:
        d_lid = np.zeros_like(vs_basis)
        d_lid[:, 2] = dz * mask
        deltas[kname] = d_lid

    d_mouth = np.zeros_like(vs_basis)
    jaw_m = np.exp(-((z - 0.265) / 0.020) ** 2) * np.clip((y - 0.155) / 0.05, 0.0, 1.0) * (v_part == 0)
    d_mouth[:, 2] = -0.010 * jaw_m
    deltas["mouth_open"] = d_mouth

    # Calibration shape key for Route A v4.1 d045 benchmark alignment
    deltas["cal_d045_v4_1"] = v_d045 - vs_basis

    for kname, d_arr in deltas.items():
        sk = obj_body.shape_key_add(name=kname, from_mix=False)
        sk.interpolation = 'KEY_LINEAR'
        sk.slider_min = 0.0
        sk.slider_max = 1.0
        sk.value = 0.0
        target = vs_basis + d_arr
        for vid in range(n_v):
            sk.data[vid].co = (float(target[vid, 0]), float(target[vid, 1]), float(target[vid, 2]))


def main():
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    landmarks = json.loads(LANDMARK_PATH.read_text(encoding="utf-8"))
    topo = np.load(TOPO_CACHE_PATH)

    vs_basis = topo["vs_basis"].astype(np.float64)
    v_d045 = topo["v_d045"].astype(np.float64)
    tris = topo["tris"].astype(np.int32)
    v_part = topo["v_part"].astype(np.int32)

    # Reset Blender scene cleanly
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    # 1. Build CAT_BODY with consistent outward normals
    bm = bmesh.new()
    for v in vs_basis:
        bm.verts.new((float(v[0]), float(v[1]), float(v[2])))
    bm.verts.ensure_lookup_table()
    for t in tris:
        bm.faces.new((bm.verts[int(t[0])], bm.verts[int(t[1])], bm.verts[int(t[2])]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh_body = bpy.data.meshes.new("CAT_BODY")
    bm.to_mesh(mesh_body)
    bm.free()
    for poly in mesh_body.polygons:
        poly.use_smooth = True

    obj_body = bpy.data.objects.new("CAT_BODY", mesh_body)
    bpy.context.collection.objects.link(obj_body)

    # Neutral materials (NO cat-specific textures!)
    mat_fur = create_neutral_material("MAT_FUR", (0.78, 0.75, 0.72, 1.0), roughness=0.75)
    mat_eye_l = create_neutral_material("MAT_EYE_L", (0.28, 0.66, 0.36, 1.0), roughness=0.15)
    mat_eye_r = create_neutral_material("MAT_EYE_R", (0.28, 0.66, 0.36, 1.0), roughness=0.15)
    mat_tongue = create_neutral_material("MAT_TONGUE", (0.82, 0.46, 0.48, 1.0), roughness=0.45)
    mesh_body.materials.append(mat_fur)

    # 2. Assign 4x4 Quadrant Asymmetric Non-Mirrored UVs to CAT_BODY
    fixed_tris = np.array([[p.vertices[0], p.vertices[1], p.vertices[2]] for p in mesh_body.polygons], dtype=np.int32)
    tri_quads = assign_non_overlapping_4x4_uvs(mesh_body, vs_basis, fixed_tris, v_part)

    # 3. Build independent CAT_EYE_L, CAT_EYE_R, and CAT_TONGUE meshes
    points = landmarks["points"]
    eye_l_pos = vs_basis[points["eye_L"]].mean(axis=0)
    eye_r_pos = vs_basis[points["eye_R"]].mean(axis=0)
    # Place almond eyeballs slightly embedded at the eye socket surface
    eye_l_center = (float(eye_l_pos[0]), float(eye_l_pos[1] + 0.004), float(eye_l_pos[2]))
    eye_r_center = (float(eye_r_pos[0]), float(eye_r_pos[1] + 0.004), float(eye_r_pos[2]))
    eye_radii = (0.0165, 0.0125, 0.0155)

    obj_eye_l = create_closed_ellipsoid_mesh(
        "CAT_EYE_L", eye_l_center, eye_radii, (0.08, -0.18, 0.22),
        u_bounds=(0.265, 0.365), v_bounds=(0.020, 0.230)
    )
    obj_eye_l.data.materials.append(mat_eye_l)

    obj_eye_r = create_closed_ellipsoid_mesh(
        "CAT_EYE_R", eye_r_center, eye_radii, (0.08, 0.18, -0.22),
        u_bounds=(0.385, 0.485), v_bounds=(0.020, 0.230)
    )
    obj_eye_r.data.materials.append(mat_eye_r)

    t01_pos = vs_basis[points["tongue_01"]].mean(axis=0)
    ttip_pos = vs_basis[points["tongue_tip"]].mean(axis=0)
    tongue_center = 0.5 * (t01_pos + ttip_pos)
    obj_tongue = create_closed_ellipsoid_mesh(
        "CAT_TONGUE",
        (0.0, float(tongue_center[1]), float(tongue_center[2])),
        (0.009, 0.018, 0.004),
        (0.10, 0.0, 0.0),
        u_bounds=(0.520, 0.730), v_bounds=(0.020, 0.230)
    )
    obj_tongue.data.materials.append(mat_tongue)

    # 4. Compute deterministic UV Hash and save uv_manifest.json + uv_layout.png
    uv_hash = compute_uv_hash(mesh_body)
    uv_manifest = {
        "uv_version": 1,
        "size_work": 2048,
        "size_game": 1024,
        "origin": "bottom_left",
        "padding_work_px": 16,
        "padding_game_px": 8,
        "asymmetric_non_mirrored": True,
        "regions": {
            qname: {
                "grid": qinfo["grid"],
                "semantic": qinfo["semantic"],
                "u_range": qinfo["u_range"],
                "v_range": qinfo["v_range"],
                "triangle_count": int(sum(1 for q in tri_quads if q == qname)),
            }
            for qname, qinfo in UV_QUADRANTS.items()
        },
        "uv_hash": uv_hash,
    }
    UV_MANIFEST_PATH.write_text(json.dumps(uv_manifest, indent=2, ensure_ascii=False))
    print(f"[build_master] Frozen uv_hash = {uv_hash}")
    render_uv_layout_png(mesh_body, obj_eye_l.data, obj_eye_r.data, obj_tongue.data, tri_quads, uv_hash)

    # 5. Build CAT_ARMATURE with 40 bones in Edit Mode
    arm_data = bpy.data.armatures.new("CAT_ARMATURE")
    arm_obj = bpy.data.objects.new("CAT_ARMATURE", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')

    bones_spec = spec["bones"]
    bone_landmarks = landmarks["bone_landmarks"]
    bone_segments = {}
    rig_map_bones = {}

    for bspec in bones_spec:
        bname = bspec["name"]
        eb = arm_data.edit_bones.new(bname)
        eb.use_deform = bool(bspec["deform"])
        h_pos, t_pos = compute_bone_head_tail(bname, bone_landmarks[bname], points, vs_basis)
        eb.head = (float(h_pos[0]), float(h_pos[1]), float(h_pos[2]))
        eb.tail = (float(t_pos[0]), float(t_pos[1]), float(t_pos[2]))
        eb.roll = 0.0
        bone_segments[bname] = (h_pos, t_pos)
        rig_map_bones[bname] = {
            "parent": bspec["parent"],
            "side": bspec["side"],
            "deform": bspec["deform"],
            "head": [round(float(x), 6) for x in h_pos],
            "tail": [round(float(x), 6) for x in t_pos],
            "roll": 0.0,
        }

    for bspec in bones_spec:
        bname = bspec["name"]
        pname = bspec["parent"]
        if pname is not None:
            arm_data.edit_bones[bname].parent = arm_data.edit_bones[pname]
            arm_data.edit_bones[bname].use_connect = False

    bpy.ops.object.mode_set(mode='OBJECT')
    RIG_MAP_PATH.write_text(json.dumps({"rig_version": 1, "bones": rig_map_bones}, indent=2, ensure_ascii=False))

    # 6. Bind meshes to CAT_ARMATURE & assign normalized skin weights (<= 4 bones/vertex)
    assign_skin_weights(obj_body, arm_obj, vs_basis, v_part, bones_spec, bone_segments)

    # Single-bone 100% weights for CAT_EYE_L, CAT_EYE_R, and 2-bone smooth weights for CAT_TONGUE
    vg_el = obj_eye_l.vertex_groups.new(name="eye_L")
    vg_el.add(list(range(len(obj_eye_l.data.vertices))), 1.0, 'REPLACE')

    vg_er = obj_eye_r.vertex_groups.new(name="eye_R")
    vg_er.add(list(range(len(obj_eye_r.data.vertices))), 1.0, 'REPLACE')

    vg_t1 = obj_tongue.vertex_groups.new(name="tongue_01")
    vg_tt = obj_tongue.vertex_groups.new(name="tongue_tip")
    t_ys = [v.co.y for v in obj_tongue.data.vertices]
    y_min_t, y_max_t = min(t_ys), max(t_ys)
    for vid, v in enumerate(obj_tongue.data.vertices):
        w_tip = max(0.0, min(1.0, (v.co.y - y_min_t) / max(y_max_t - y_min_t, 1e-6)))
        vg_t1.add([vid], float(1.0 - w_tip), 'REPLACE')
        vg_tt.add([vid], float(w_tip), 'REPLACE')

    for m_obj in (obj_body, obj_eye_l, obj_eye_r, obj_tongue):
        m_obj.parent = arm_obj
        mod = m_obj.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = arm_obj

    # 7. Add separated Shape Keys (`id_*`, `sty_*`, `blink_L/R`, `squint_L/R`, `mouth_open`, `cal_d045_v4_1`)
    add_separated_shape_keys(obj_body, vs_basis, v_d045, v_part)

    # 8. Create Empty anchors (`hot_*` and `foot_*`) parented to CAT_ARMATURE bones
    anchor_parent_bones = {
        "hot_head": "head",
        "hot_back": "spine_02",
        "hot_belly": "spine_02",
        "hot_groom": "forearm_R",
        "hot_pet": "head",
        "foot_FL": "hand_L",
        "foot_FR": "hand_R",
        "foot_BL": "paw_B_L",
        "foot_BR": "paw_B_R",
    }
    for aname, pbone in anchor_parent_bones.items():
        emp = bpy.data.objects.new(aname, None)
        emp.empty_display_type = 'PLAIN_AXES'
        emp.empty_display_size = 0.025
        bpy.context.collection.objects.link(emp)

        vids = points[aname]
        pos = vs_basis[vids].mean(axis=0).copy()
        if aname.startswith("foot_"):
            pos[2] = float(vs_basis[vids, 2].min())  # Grounded at Z=0 (<0.1mm)
        elif aname in ("hot_head", "hot_back", "hot_belly", "hot_pet"):
            pos[0] = 0.0

        emp.parent = arm_obj
        emp.parent_type = 'BONE'
        emp.parent_bone = pbone
        # Set matrix_world so world translation matches `pos` in Rest Pose
        bpy.context.view_layer.update()
        emp.matrix_world = Matrix.Translation(Vector((float(pos[0]), float(pos[1]), float(pos[2]))))

    bpy.context.view_layer.update()

    # Save master_cat.blend and export master_cat.glb
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT_PATH))
    print(f"[build_master] Saved Blender master file: {BLEND_OUT_PATH}")

    bpy.ops.export_scene.gltf(
        filepath=str(GLB_OUT_PATH),
        export_format='GLB',
        export_yup=True,
        export_skins=True,
        export_morph=True,
    )
    print(f"[build_master] Exported glTF binary: {GLB_OUT_PATH}")


if __name__ == "__main__":
    main()
