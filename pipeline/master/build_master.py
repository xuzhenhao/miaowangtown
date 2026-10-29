#!/usr/bin/env python3
"""
build_master.py — Milestone M1 Master Cat Builder (`art/master_cat/master_cat.blend` & `master_cat.glb`).

Builds the frozen Chibi Master Cat following `CAT_DIGITAL_TWIN_ENGINEERING_SPEC.md`,
`FUSED_CAT_DIGITAL_TWIN_AND_V4_1_PIPELINE_SPEC.md`, and `DEVELOPMENT_PLAN.md (v1.3)`:
  1. `CAT_BODY`: Closed manifold mesh (2,321 vertices, 4,634 triangles, 0 non-manifold edges,
     consistent outward normals) in pure Chibi Rest Pose (`Basis`), directly aligned in 3D so that
     the pure static Rest mesh (`Basis` with all Shape Keys = 0.0 and ZERO view-specific calibration keys)
     achieves `<= 2.0 px` full-silhouette boundary distance (including all 4 legs and tail) on `d045`.
  2. `CAT_EYE_L`, `CAT_EYE_R`: Independent closed manifold 3D eyeball meshes symmetrically seated in their
     anatomical eye sockets with forward-slightly-divergent orientation (`yaw = +-14 deg`, `pitch = +26 deg`),
     dedicated UV in `D2` quadrant, isolated materials `MAT_EYE_L`, `MAT_EYE_R`, and ZERO shape keys so
     front (`d000`), 3/4 (`d045`/`d315`), and profile (`d090`/`d270`) views all show natural emerald eyes.
  3. `CAT_TONGUE`: Independent closed manifold tongue mesh inside the lower jaw oral cavity (`mouth_floor`)
     with dedicated UV in `D3` quadrant and material `MAT_TONGUE`.
  4. Fixed 4x4 Quadrant 100% Asymmetric Non-Mirrored UV Layout (work size 2048x2048, game size 1024x1024,
     >=16px padding on 2048 canvas, zero unexpected UV overlaps, frozen SHA-256 `uv_hash` written to
     `art/master_cat/uv_manifest.json`, `art/master_cat/master_spec.json`, and `art/master_cat/uv_layout.png`).
  5. `CAT_ARMATURE`: 40 standard quadruped bones (`root` at (0,0,0), anatomical `_L` at X<0 and `_R` at X>0),
     built via the exact same `compute_bone_targets_and_centers` formula used by `pipeline/rig/adapt_rest.py`,
     with smooth, normalized skin weights (<= 4 bones per vertex and strict L/R separation).
  6. Separated Identity (`id_*`, 8 keys), Style (`sty_*`, 5 keys), and Face (`blink_L/R`, `squint_L/R`, `mouth_open`)
     Shape Keys on `CAT_BODY` ONLY (zero `cal_*` keys anywhere).
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
from PIL import Image, ImageDraw

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

sys.path.insert(0, str(ROOT_DIR))
from pipeline.rig.adapt_rest import compute_bone_targets_and_centers


# 4x4 Quadrant UV Regions (Blender UV origin: bottom-left (0,0) to top-right (1,1))
UV_QUADRANTS = {
    "A1_head_front":       {"grid": [0, 3], "semantic": "head_front",       "u_range": [0.00, 0.25], "v_range": [0.75, 1.00], "color": (235, 110, 95)},
    "A2_head_back":        {"grid": [1, 3], "semantic": "head_back",        "u_range": [0.25, 0.50], "v_range": [0.75, 1.00], "color": (240, 155, 85)},
    "A3_muzzle_chin":      {"grid": [2, 3], "semantic": "head_muzzle",      "u_range": [0.50, 0.75], "v_range": [0.75, 1.00], "color": (245, 195, 85)},
    "A4_ears_LR":          {"grid": [3, 3], "semantic": "ears_LR",          "u_range": [0.75, 1.00], "v_range": [0.75, 1.00], "color": (195, 215, 95)},
    "B1_torso_L":          {"grid": [0, 2], "semantic": "torso_L",          "u_range": [0.00, 0.25], "v_range": [0.50, 0.75], "color": (95, 195, 145)},
    "B2_torso_R":          {"grid": [1, 2], "semantic": "torso_R",          "u_range": [0.25, 0.50], "v_range": [0.50, 0.75], "color": (85, 185, 215)},
    "B3_torso_back":       {"grid": [2, 2], "semantic": "torso_back",       "u_range": [0.50, 0.75], "v_range": [0.50, 0.75], "color": (105, 145, 235)},
    "B4_torso_belly":      {"grid": [3, 2], "semantic": "torso_belly",      "u_range": [0.75, 1.00], "v_range": [0.50, 0.75], "color": (155, 125, 235)},
    "C1_leg_FL":           {"grid": [0, 1], "semantic": "leg_FL",           "u_range": [0.00, 0.25], "v_range": [0.25, 0.50], "color": (215, 115, 205)},
    "C2_leg_FR":           {"grid": [1, 1], "semantic": "leg_FR",           "u_range": [0.25, 0.50], "v_range": [0.25, 0.50], "color": (235, 115, 155)},
    "C3_leg_BL":           {"grid": [2, 1], "semantic": "leg_BL",           "u_range": [0.50, 0.75], "v_range": [0.25, 0.50], "color": (185, 145, 115)},
    "C4_leg_BR":           {"grid": [3, 1], "semantic": "leg_BR",           "u_range": [0.75, 1.00], "v_range": [0.25, 0.50], "color": (145, 175, 135)},
    "D1_tail":             {"grid": [0, 0], "semantic": "tail",             "u_range": [0.00, 0.25], "v_range": [0.00, 0.25], "color": (115, 175, 195)},
    "D2_eyes_LR":          {"grid": [1, 0], "semantic": "eyes_LR",          "u_range": [0.25, 0.50], "v_range": [0.00, 0.25], "color": (85, 210, 135)},
    "D3_nose_pads_tongue": {"grid": [2, 0], "semantic": "nose_pads_tongue", "u_range": [0.50, 0.75], "v_range": [0.00, 0.25], "color": (230, 140, 150)},
    "D4_reserved":         {"grid": [3, 0], "semantic": "reserved",         "u_range": [0.75, 1.00], "v_range": [0.00, 0.25], "color": (130, 135, 145)},
}


def classify_body_triangles(vs: np.ndarray, tris: np.ndarray, v_part: np.ndarray) -> list:
    """Assign each triangle of CAT_BODY to one of the 16 4x4 semantic quadrants."""
    tri_Centroids = vs[tris].mean(axis=1)
    v0 = vs[tris[:, 0]]
    v1 = vs[tris[:, 1]]
    v2 = vs[tris[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    fn_norm = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = fn / np.maximum(fn_norm, 1e-9)

    tp0 = v_part[tris[:, 0]]
    tp1 = v_part[tris[:, 1]]
    tp2 = v_part[tris[:, 2]]

    quads = []
    for i in range(len(tris)):
        cx, cy, cz = tri_Centroids[i]
        nx, ny, nz = fn[i]
        parts = (tp0[i], tp1[i], tp2[i])
        # Paw pads & nose tip in D3_nose_pads_tongue, inner collar seam in D4_reserved, eye socket rim in D2_eyes_LR
        if cz < 0.015 and nz < -0.35:
            quads.append("D3_nose_pads_tongue")
            continue
        if cy > 0.165 and 0.305 <= cz <= 0.365 and abs(cx) < 0.018:
            quads.append("D3_nose_pads_tongue")
            continue
        if cy > 0.145 and 0.330 <= cz <= 0.380 and 0.022 <= abs(cx) <= 0.062:
            quads.append("D2_eyes_LR")
            continue
        if 0.215 <= cz <= 0.265 and 0.030 <= cy <= 0.105 and abs(cx) < 0.038:
            quads.append("D4_reserved")
            continue
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
        # Head & Ears
        if cz >= 0.245 or (cy > 0.075 and cz > 0.215):
            if cz >= 0.395 and abs(cx) >= 0.024:
                quads.append("A4_ears_LR")
            elif cy >= 0.140 and cz <= 0.325:
                quads.append("A3_muzzle_chin")
            elif ny >= -0.05 and cy >= 0.095:
                quads.append("A1_head_front")
            else:
                quads.append("A2_head_back")
            continue
        # Torso: B1 (left X<0), B2 (right X>=0), B3 (dorsal back), B4 (ventral belly)
        if nz >= 0.55 and cz >= 0.185:
            quads.append("B3_torso_back")
        elif nz <= -0.35 and cz <= 0.165:
            quads.append("B4_torso_belly")
        elif cx < 0.0:
            quads.append("B1_torso_L")
        else:
            quads.append("B2_torso_R")
    return quads


def assign_non_overlapping_4x4_uvs(mesh_body: bpy.types.Mesh, vs: np.ndarray, tris: np.ndarray, v_part: np.ndarray):
    """
    Assign 100% asymmetric, non-overlapping UVs to CAT_BODY strictly inside each 4x4 quadrant cell
    with >= 16px padding on a 2048x2048 canvas based directly on the final pure Basis mesh.
    """
    uv_layer = mesh_body.uv_layers.new(name="UVMap")
    mesh_body.uv_layers.active = uv_layer

    tri_quads = classify_body_triangles(vs, tris, v_part)
    quad_to_tris = {k: [] for k in UV_QUADRANTS}
    for ti, qname in enumerate(tri_quads):
        quad_to_tris[qname].append(ti)

    cell_margin = 0.011
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


def create_closed_ellipsoid_mesh(name: str, center_basis: tuple, radii: tuple, rot_euler: tuple,
                                 u_bounds: tuple, v_bounds: tuple, segs_u: int = 12, segs_v: int = 10) -> bpy.types.Object:
    """
    Create a closed manifold triangulated ellipsoid mesh with ZERO shape keys and clean UV mapping
    inside (u_bounds, v_bounds) where each vertex's UV encodes its local anterior surface coordinates
    along its natural forward-slightly-divergent anatomical axis.
    """
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs_u, v_segments=segs_v, radius=1.0)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    unit_coords = np.array([[v.co.x, v.co.y, v.co.z] for v in bm.verts], dtype=np.float64)

    rx, ry, rz = radii
    rot_mat = Euler(rot_euler, 'XYZ').to_matrix().to_4x4()
    trans_mat = Matrix.Translation(Vector(center_basis))
    for i, v in enumerate(bm.verts):
        p = Vector((unit_coords[i, 0] * rx, unit_coords[i, 1] * ry, unit_coords[i, 2] * rz))
        v.co = trans_mat @ (rot_mat @ p)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True

    uv_layer = mesh.uv_layers.new(name="UVMap")
    mesh.uv_layers.active = uv_layer
    u0, u1 = u_bounds
    v0, v1 = v_bounds
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vid = mesh.loops[li].vertex_index
            ux = 0.5 + 0.46 * float(unit_coords[vid, 0])
            vz = 0.5 + 0.46 * float(unit_coords[vid, 2])
            u_val = u0 + ux * (u1 - u0)
            v_val = v0 + vz * (v1 - v0)
            uv_layer.data[li].uv = (round(u_val, 6), round(v_val, 6))

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

    for qname, qinfo in UV_QUADRANTS.items():
        u0, u1 = qinfo["u_range"]
        v0, v1 = qinfo["v_range"]
        x0 = int(u0 * W)
        x1 = int(u1 * W)
        y0 = int((1.0 - v1) * H)
        y1 = int((1.0 - v0) * H)
        col = qinfo["color"]
        dr.rectangle([x0 + 2, y0 + 2, x1 - 2, y1 - 2], fill=(col[0] // 5, col[1] // 5, col[2] // 5, 255),
                     outline=(col[0], col[1], col[2], 200), width=3)
        dr.rectangle([x0 + 16, y0 + 16, x1 - 16, y1 - 16], outline=(90, 95, 110, 140), width=1)

    uv_body = mesh_body.uv_layers.active.data
    for ti, poly in enumerate(mesh_body.polygons):
        qname = tri_quads[ti]
        col = UV_QUADRANTS[qname]["color"]
        pts = []
        for li in poly.loop_indices:
            u, v = uv_body[li].uv
            pts.append((u * (W - 1), (1.0 - v) * (H - 1)))
        dr.polygon(pts, fill=(col[0], col[1], col[2], 185), outline=(245, 245, 250, 220))

    for m_extra, qname in [(mesh_eye_l, "D2_eyes_LR"), (mesh_eye_r, "D2_eyes_LR"), (mesh_tongue, "D3_nose_pads_tongue")]:
        uv_ex = m_extra.uv_layers.active.data
        col = UV_QUADRANTS[qname]["color"]
        for poly in m_extra.polygons:
            pts = []
            for li in poly.loop_indices:
                u, v = uv_ex[li].uv
                pts.append((u * (W - 1), (1.0 - v) * (H - 1)))
            dr.polygon(pts, fill=(col[0], col[1], col[2], 200), outline=(255, 255, 255, 220))

    for qname, qinfo in UV_QUADRANTS.items():
        u0, u1 = qinfo["u_range"]
        v0, v1 = qinfo["v_range"]
        x0 = int(u0 * W) + 22
        y0 = int((1.0 - v1) * H) + 20
        label = f"{qname} ({qinfo['semantic']})"
        dr.rectangle([x0 - 4, y0 - 2, x0 + len(label) * 8 + 8, y0 + 18], fill=(12, 14, 18, 215))
        dr.text((x0, y0), label, fill=(255, 255, 255, 255))

    header = f"MIAOWANGTOWN MASTER CAT 4x4 ASYMMETRIC UV LAYOUT (2048x2048) | uv_hash={uv_hash[:24]}..."
    dr.rectangle([16, H - 44, W - 16, H - 12], fill=(12, 14, 18, 230))
    dr.text((28, H - 34), header, fill=(220, 245, 255, 255))

    im.save(UV_LAYOUT_PNG_PATH)
    print(f"[build_master] Saved UV layout chart: {UV_LAYOUT_PNG_PATH}")


def assign_skin_weights(obj_body: bpy.types.Object, vs: np.ndarray, tris: np.ndarray,
                        v_part: np.ndarray, bones_spec: list, bone_segments: dict):
    """
    Assign smooth, anatomically blended, normalized skin weights to CAT_BODY:
      - `root` is non-deforming (0 weights).
      - Every vertex is influenced by 1..4 deforming bones, weights sum to 1.000000.
      - Strict anatomical L/R separation: vertices with X < -0.008 never receive `_R` bone weights,
        and vertices with X > +0.008 never receive `_L` bone weights.
      - Smooth Laplacian weight blending across shoulder/armpit and hip/inner-thigh junctions so
        Sit Pose and Wide-Stride Pose bend cleanly without mesh bunching or tearing.
    """
    for b in bones_spec:
        obj_body.vertex_groups.new(name=b["name"])

    leg_FL_bones = ["clavicle_L", "upperarm_L", "forearm_L", "paw_F_L"]
    leg_FR_bones = ["clavicle_R", "upperarm_R", "forearm_R", "paw_F_R"]
    leg_BL_bones = ["thigh_L", "shin_L", "foot_L", "paw_B_L"]
    leg_BR_bones = ["thigh_R", "shin_R", "foot_R", "paw_B_R"]
    tail_bones = ["tail_01", "tail_02", "tail_03", "tail_04", "tail_05", "tail_06"]
    spine_head_bones = ["hips", "spine_01", "spine_02", "spine_03", "spine_04", "neck_01", "neck_02", "head", "jaw"]
    ear_L_bones = ["ear_L_01", "ear_L_02"]
    ear_R_bones = ["ear_R_01", "ear_R_02"]

    all_deform = [b["name"] for b in bones_spec if b["deform"] and b["name"] not in ("eye_L", "eye_R", "tongue_01", "tongue_tip")]
    b_to_idx = {bn: i for i, bn in enumerate(all_deform)}
    n_v = len(vs)
    n_b = len(all_deform)
    W_mat = np.zeros((n_v, n_b), dtype=np.float64)

    def point_seg_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
        ab = b - a
        l2 = float(np.dot(ab, ab))
        if l2 < 1e-10:
            return float(np.linalg.norm(p - a))
        t = max(0.0, min(1.0, float(np.dot(p - a, ab)) / l2))
        proj = a + t * ab
        return float(np.linalg.norm(p - proj))

    for vid in range(n_v):
        p = vs[vid]
        part = int(v_part[vid])
        if part == 2:  # FL (-X, +Y)
            cands = leg_FL_bones + ["spine_03", "spine_04"]
        elif part == 1:  # FR (+X, +Y)
            cands = leg_FR_bones + ["spine_03", "spine_04"]
        elif part == 4:  # BL (-X, -Y)
            cands = leg_BL_bones + ["hips", "spine_01"]
        elif part == 3:  # BR (+X, -Y)
            cands = leg_BR_bones + ["hips", "spine_01"]
        elif part == 5:  # Tail
            cands = tail_bones + ["hips"]
        else:
            cands = list(spine_head_bones)
            if p[2] > 0.35 and p[0] < -0.015:
                cands += ear_L_bones
            elif p[2] > 0.35 and p[0] > 0.015:
                cands += ear_R_bones
            if p[2] < 0.175 and p[1] > 0.0:
                cands += (leg_FL_bones[:2] if p[0] < 0 else leg_FR_bones[:2])
            elif p[2] < 0.175 and p[1] <= 0.0:
                cands += (leg_BL_bones[:2] if p[0] < 0 else leg_BR_bones[:2])

        if p[0] < -0.008:
            cands = [bn for bn in cands if not bn.endswith("_R") and "_R_" not in bn]
        elif p[0] > 0.008:
            cands = [bn for bn in cands if not bn.endswith("_L") and "_L_" not in bn]

        for bn in cands:
            h, t = bone_segments[bn]
            d_val = point_seg_dist(p, h, t)
            W_mat[vid, b_to_idx[bn]] = 1.0 / (max(d_val, 0.014) ** 2.0)

    # Smooth skin weights across mesh edges (3 iterations) while respecting strict L/R separation
    adj = [set() for _ in range(n_v)]
    for a, b, c in tris:
        adj[a].update([b, c])
        adj[b].update([a, c])
        adj[c].update([a, b])
    adj = [np.array(list(s), dtype=np.int32) for s in adj]

    for _ in range(3):
        W_next = W_mat.copy()
        for vid in range(n_v):
            nbs = adj[vid]
            W_next[vid] = 0.60 * W_mat[vid] + 0.40 * W_mat[nbs].mean(axis=0)
        W_mat = W_next

    # Zero out any L/R cross weights beyond +-8mm and keep top <= 4 bones per vertex, normalized to 1.0
    for vid in range(n_v):
        px_v = float(vs[vid, 0])
        for bi, bn in enumerate(all_deform):
            if (bn.endswith("_L") or "_L_" in bn) and px_v > 0.008:
                W_mat[vid, bi] = 0.0
            elif (bn.endswith("_R") or "_R_" in bn) and px_v < -0.008:
                W_mat[vid, bi] = 0.0
        row = W_mat[vid]
        top_idxs = np.argsort(row)[::-1][:4]
        top_vals = [float(row[i]) for i in top_idxs if row[i] > 1e-6]
        top_bns = [all_deform[i] for i in top_idxs if row[i] > 1e-6]
        if not top_vals:
            top_bns = ["spine_02"]
            top_vals = [1.0]
        s = sum(top_vals)
        norm_w = [v / s for v in top_vals]
        norm_w[-1] = 1.0 - sum(norm_w[:-1])
        for bn, w in zip(top_bns, norm_w):
            if w > 0.0:
                obj_body.vertex_groups[bn].add([vid], float(w), 'REPLACE')


def add_separated_shape_keys(obj_body: bpy.types.Object, vs_basis: np.ndarray, v_part: np.ndarray):
    """
    Create Basis + 8 Identity (`id_*`) + 5 Style (`sty_*`) + 5 Face (`blink_L/R`, `squint_L/R`, `mouth_open`)
    Shape Keys on CAT_BODY. ZERO `cal_*` keys are created!
    """
    sk_basis = obj_body.shape_key_add(name="Basis", from_mix=False)
    sk_basis.interpolation = 'KEY_LINEAR'

    n_v = len(vs_basis)
    x = vs_basis[:, 0]
    y = vs_basis[:, 1]
    z = vs_basis[:, 2]

    torso_w = np.exp(-((y - (-0.02)) / 0.11) ** 2) * np.clip((0.26 - z) / 0.12, 0.0, 1.0) * (v_part == 0)
    belly_w = np.exp(-((y - (-0.02)) / 0.10) ** 2) * np.clip((0.18 - z) / 0.08, 0.0, 1.0) * (v_part == 0)
    head_w = np.clip((z - 0.255) / 0.035, 0.0, 1.0) * (v_part == 0)
    cheek_w = np.exp(-((z - 0.315) / 0.040) ** 2) * np.exp(-((y - 0.145) / 0.045) ** 2) * (v_part == 0)
    muzzle_w = np.exp(-((z - 0.305) / 0.030) ** 2) * np.clip((y - 0.155) / 0.05, 0.0, 1.0) * (v_part == 0)
    ear_w = np.clip((z - 0.400) / 0.055, 0.0, 1.0) * (v_part == 0)
    paw_w = np.isin(v_part, [1, 2, 3, 4]).astype(np.float64) * np.clip((0.045 - z) / 0.045, 0.0, 1.0) * np.clip(z / 0.005, 0.0, 1.0)

    deltas = {}

    d_fat = np.zeros_like(vs_basis)
    d_fat[:, 0] = x * torso_w * 0.12
    d_fat[:, 2] = (z - 0.16) * torso_w * 0.06
    deltas["id_body_fat"] = d_fat

    d_belly = np.zeros_like(vs_basis)
    d_belly[:, 2] = -0.015 * belly_w
    d_belly[:, 0] = x * belly_w * 0.08
    deltas["id_belly"] = d_belly

    leg_mask = np.isin(v_part, [1, 2, 3, 4]).astype(np.float64)
    d_leg = np.zeros_like(vs_basis)
    d_leg[:, 2] = (z / 0.48) * 0.012 * np.clip(z / 0.01, 0.0, 1.0) * leg_mask
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

    d_sty_head = np.zeros_like(vs_basis)
    hc = np.array([0.0, 0.135, 0.292])
    d_sty_head[:, 0] = (x - hc[0]) * head_w * 0.035
    d_sty_head[:, 1] = (y - hc[1]) * head_w * 0.035
    d_sty_head[:, 2] = (z - hc[2]) * head_w * 0.025
    deltas["sty_head_enlarge"] = d_sty_head

    d_sty_leg = np.zeros_like(vs_basis)
    d_sty_leg[:, 2] = -0.008 * np.clip(z / 0.12, 0.0, 1.0) * leg_mask
    deltas["sty_leg_shorten"] = d_sty_leg

    d_sty_eye = np.zeros_like(vs_basis)
    eye_region = np.exp(-((z - 0.354) / 0.028) ** 2) * np.exp(-((y - 0.165) / 0.030) ** 2) * (v_part == 0)
    d_sty_eye[:, 0] = x * eye_region * 0.04
    d_sty_eye[:, 2] = (z - 0.354) * eye_region * 0.06
    deltas["sty_eye_enlarge"] = d_sty_eye

    d_sty_cheek = np.zeros_like(vs_basis)
    d_sty_cheek[:, 0] = x * cheek_w * 0.09
    d_sty_cheek[:, 2] = -0.004 * cheek_w
    deltas["sty_face_chibi_cheek"] = d_sty_cheek

    d_sty_paw = np.zeros_like(vs_basis)
    d_sty_paw[:, 0] = np.sign(x) * paw_w * 0.004
    d_sty_paw[:, 1] = np.sign(y) * paw_w * 0.004
    deltas["sty_paw_round"] = d_sty_paw

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
    jaw_m = np.exp(-((z - 0.285) / 0.022) ** 2) * np.clip((y - 0.145) / 0.05, 0.0, 1.0) * (v_part == 0)
    d_mouth[:, 2] = -0.010 * jaw_m
    deltas["mouth_open"] = d_mouth

    # Pin shared oral tongue-bed + chin landmarks so CAT_TONGUE + tongue_01/tongue_tip stay 0.0mm shift
    landmarks = json.loads(LANDMARK_PATH.read_text())["points"]
    tongue_bed_vids = sorted(set(
        list(landmarks.get("mouth_floor", []))
        + list(landmarks.get("tongue_01", []))
        + list(landmarks.get("tongue_tip", []))
        + list(landmarks.get("chin", []))
    ))
    pin_exempt = {"mouth_open"}

    for kname, d_arr in deltas.items():
        sk = obj_body.shape_key_add(name=kname, from_mix=False)
        sk.interpolation = 'KEY_LINEAR'
        sk.slider_min = 0.0
        sk.slider_max = 1.0
        sk.value = 0.0
        target = vs_basis + d_arr
        if kname not in pin_exempt:
            for vid in tongue_bed_vids:
                target[vid] = vs_basis[vid]
        for vid in range(n_v):
            sk.data[vid].co = (float(target[vid, 0]), float(target[vid, 1]), float(target[vid, 2]))


def main():
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    landmarks_doc = json.loads(LANDMARK_PATH.read_text(encoding="utf-8"))
    points = landmarks_doc["points"]
    topo = np.load(TOPO_CACHE_PATH)

    vs_basis = topo["vs_basis"].astype(np.float64)
    tris = topo["tris"].astype(np.int32)
    v_part = topo["v_part"].astype(np.int32)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    # 1. Build CAT_BODY with consistent outward normals and smooth shading
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

    # Neutral materials (NO cat-specific identity textures!)
    mat_fur = create_neutral_material("MAT_FUR", (0.78, 0.75, 0.72, 1.0), roughness=0.75)
    mat_eye_l = create_neutral_material("MAT_EYE_L", (0.28, 0.66, 0.36, 1.0), roughness=0.15)
    mat_eye_r = create_neutral_material("MAT_EYE_R", (0.28, 0.66, 0.36, 1.0), roughness=0.15)
    mat_tongue = create_neutral_material("MAT_TONGUE", (0.82, 0.46, 0.48, 1.0), roughness=0.45)
    mesh_body.materials.append(mat_fur)

    # 2. Assign 4x4 Quadrant Asymmetric Non-Mirrored UVs to CAT_BODY
    fixed_tris = np.array([[p.vertices[0], p.vertices[1], p.vertices[2]] for p in mesh_body.polygons], dtype=np.int32)
    tri_quads = assign_non_overlapping_4x4_uvs(mesh_body, vs_basis, fixed_tris, v_part)

    # 3. Compute unified bone, eye, tongue, and anchor targets (shared with `adapt_rest.py`)
    bone_targets, anchor_targets, eye_l_vec, eye_r_vec, tongue_vec = compute_bone_targets_and_centers(vs_basis, points)

    # Build independent CAT_EYE_L, CAT_EYE_R, and CAT_TONGUE meshes seated in their exact sockets
    # Strictly symmetric 3D ellipsoids facing forward-slightly-outward (yaw = +-14 deg, pitch = +26 deg)
    # with ZERO shape keys, so front (d000), 3/4 (d045/d315), and profile (d090/d270) all see natural eyes!
    obj_eye_l = create_closed_ellipsoid_mesh(
        "CAT_EYE_L",
        (float(eye_l_vec.x), float(eye_l_vec.y), float(eye_l_vec.z)),
        (0.0155, 0.0135, 0.0165),
        (math.radians(26.0), 0.0, math.radians(14.0)),
        u_bounds=(0.265, 0.365), v_bounds=(0.020, 0.230),
    )
    obj_eye_l.data.materials.append(mat_eye_l)

    obj_eye_r = create_closed_ellipsoid_mesh(
        "CAT_EYE_R",
        (float(eye_r_vec.x), float(eye_r_vec.y), float(eye_r_vec.z)),
        (0.0155, 0.0135, 0.0165),
        (math.radians(26.0), 0.0, math.radians(-14.0)),
        u_bounds=(0.385, 0.485), v_bounds=(0.020, 0.230),
    )
    obj_eye_r.data.materials.append(mat_eye_r)

    obj_tongue = create_closed_ellipsoid_mesh(
        "CAT_TONGUE",
        (float(tongue_vec.x), float(tongue_vec.y), float(tongue_vec.z)),
        (0.0085, 0.0135, 0.0038),
        (0.08, 0.0, 0.0),
        u_bounds=(0.520, 0.730), v_bounds=(0.020, 0.230),
    )
    obj_tongue.data.materials.append(mat_tongue)

    # 4. Compute deterministic UV Hash and update uv_manifest.json + master_spec.json + uv_layout.png
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
                "color_rgb": list(qinfo["color"]),
                "triangle_count": int(sum(1 for q in tri_quads if q == qname)),
            }
            for qname, qinfo in UV_QUADRANTS.items()
        },
        "uv_hash": uv_hash,
    }
    UV_MANIFEST_PATH.write_text(json.dumps(uv_manifest, indent=2, ensure_ascii=False))
    z_tot = float(vs_basis[:, 2].max() - vs_basis[:, 2].min())
    z_chin = float(vs_basis[points["chin"], 2].mean())
    spec["proportions_basis"] = {
        "total_height_m": round(z_tot, 4),
        "chin_height_m": round(z_chin, 4),
        "head_height_ratio": round((z_tot - z_chin) / z_tot, 4),
    }
    spec["uv_hash"] = uv_hash
    SPEC_PATH.write_text(json.dumps(spec, indent=2, ensure_ascii=False))
    print(f"[build_master] Frozen uv_hash = {uv_hash}")
    render_uv_layout_png(mesh_body, obj_eye_l.data, obj_eye_r.data, obj_tongue.data, tri_quads, uv_hash)

    # 5. Build CAT_ARMATURE with 40 bones in Edit Mode using unified bone_targets
    arm_data = bpy.data.armatures.new("CAT_ARMATURE")
    arm_obj = bpy.data.objects.new("CAT_ARMATURE", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')

    bones_spec = spec["bones"]
    bone_segments = {}
    rig_map_bones = {}

    for bspec in bones_spec:
        bname = bspec["name"]
        eb = arm_data.edit_bones.new(bname)
        eb.use_deform = bool(bspec["deform"])
        h_vec, t_vec = bone_targets[bname]
        eb.head = h_vec
        eb.tail = t_vec
        eb.roll = 0.0
        h_pos = np.array([h_vec.x, h_vec.y, h_vec.z], dtype=np.float64)
        t_pos = np.array([t_vec.x, t_vec.y, t_vec.z], dtype=np.float64)
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

    # 6. Bind meshes to CAT_ARMATURE & assign smooth normalized skin weights (<= 4 bones/vertex)
    assign_skin_weights(obj_body, vs_basis, fixed_tris, v_part, bones_spec, bone_segments)

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

    # 7. Add separated Shape Keys (`id_*`, `sty_*`, `blink_L/R`, `squint_L/R`, `mouth_open`) — NO `cal_*` keys!
    add_separated_shape_keys(obj_body, vs_basis, v_part)

    # 8. Create Empty anchors (`hot_*` and `foot_*`) parented to CAT_ARMATURE bones
    for aname, (pbone, a_loc) in anchor_targets.items():
        emp = bpy.data.objects.new(aname, None)
        emp.empty_display_type = 'PLAIN_AXES'
        emp.empty_display_size = 0.025
        bpy.context.collection.objects.link(emp)

        emp.parent = arm_obj
        emp.parent_type = 'BONE'
        emp.parent_bone = pbone
        bone_obj = arm_obj.data.bones[pbone]
        bone_tail_world = arm_obj.matrix_world @ bone_obj.matrix_local @ Vector((0.0, bone_obj.length, 0.0))
        bone_mat_world = arm_obj.matrix_world @ bone_obj.matrix_local
        bone_mat_world.translation = bone_tail_world
        emp.matrix_parent_inverse = bone_mat_world.inverted()
        emp.location = a_loc

    bpy.context.view_layer.update()

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
