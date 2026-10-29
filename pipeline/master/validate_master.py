#!/usr/bin/env python3
"""
Stage M1 — 13-Item Industrial Master Cat Automated Gate (`pipeline/master/validate_master.py`)
Validates `art/master_cat/master_cat.blend` against all 12 structural criteria in `DEVELOPMENT_PLAN.md` v1.3
(both before and after applying `id_*` + `sty_*` Shape Keys + `adapt_rest.py`, including tongue shift < 1mm,
and verifying zero `cal_*` or unauthorized shape keys exist on any mesh)
PLUS Check 13: Real `d045` `114x104` Full Silhouette Bidirectional Distance (`<= 2.0 px` including all 4 legs
and tail, zero `> 2.0 px` outliers) and Real Measured 4-Element Emerald Eye Pixel Counts rendered directly
from the pure Rest (`Basis`, all shape key values == 0.0) `CAT_BODY` + `CAT_EYE_L` + `CAT_EYE_R` 3D meshes
in `master_cat.blend` without any calibration shape keys, script vertex relocation, or benchmark pixel copy-paste.
Writes `docs/validation/m1_master_validation/validation_report.json`.
"""
import hashlib
import json
import math
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Vector
import numpy as np
from PIL import Image, ImageDraw

ROOT_DIR = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT_DIR / "art" / "master_cat"
V4_1_DIR = ROOT_DIR / "docs" / "validation" / "route_a_v4_1_ultimate"
OUT_DIR = ROOT_DIR / "docs" / "validation" / "m1_master_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT_DIR))

from pipeline.rig.adapt_rest import adapt_rest_rig


def compute_uv_hash(mesh) -> str:
    uv = mesh.uv_layers.active.data
    rows = [
        [loop.vertex_index, round(uv[loop.index].uv.x, 6), round(uv[loop.index].uv.y, 6)]
        for loop in mesh.loops
    ]
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def get_camera_basis(yaw_deg: float = -45.0, pitch_deg: float = 35.0):
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
        s = np.zeros_like(mask)
        if dy == -1:
            s[:-1, :] = mask[1:, :]
        elif dy == 1:
            s[1:, :] = mask[:-1, :]
        elif dx == -1:
            s[:, :-1] = mask[:, 1:]
        elif dx == 1:
            s[:, 1:] = mask[:, :-1]
        er &= s
    return mask & (~er)


def evaluate_d045_silhouette_and_eyes() -> dict:
    """
    Evaluate `CAT_BODY`, `CAT_EYE_L`, `CAT_EYE_R` directly from `master_cat.blend` in 100% pure Rest (`Basis`)
    state (asserting all shape key values == 0.0 and zero `cal_*` keys exist anywhere), render at 4x supersampling
    (456x416), downsample via `post_v4_1` Box/Area integration to `114x104` (`Alpha > 162`), and measure:
      - `full_silhouette_max_distance_px` (including all 4 legs and tail)
      - `head_body_max_distance_px`
      - `full_silhouette_outliers_gt_2px`
      - `mask_iou`
      - Real pixel counts of the 4 eye elements inside `CAT_EYE_L` and `CAT_EYE_R` on the `114x104` grid.
    """
    non_zero_shape_keys = []
    cal_shape_keys = []
    for name in ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]:
        obj = bpy.data.objects[name]
        if obj.data.shape_keys:
            for kb in obj.data.shape_keys.key_blocks:
                if kb.name.startswith("cal_"):
                    cal_shape_keys.append(f"{name}:{kb.name}")
                if kb.name != "Basis" and abs(kb.value) > 1e-7:
                    non_zero_shape_keys.append(f"{name}:{kb.name}={kb.value}")

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    e_u, e_v, e_w = get_camera_basis(-45.0, 35.0)
    s_log = 0.0040
    orig_log = (52.7, 94.0)
    gw, gh = 114, 104
    ss = 4
    hi_w, hi_h = gw * ss, gh * ss

    # 1. Rasterize evaluated CAT_BODY 4x supersampled silhouette mask (100% pure Basis mesh)
    ev_body = bpy.data.objects["CAT_BODY"].evaluated_get(depsgraph)
    m_body = ev_body.to_mesh()
    m_body.calc_loop_triangles()
    vs_b = np.array([list(ev_body.matrix_world @ v.co) for v in m_body.vertices], dtype=np.float64)
    tris_b = np.array([[lt.vertices[0], lt.vertices[1], lt.vertices[2]] for lt in m_body.loop_triangles], dtype=np.int32)
    ev_body.to_mesh_clear()

    px_b = orig_log[0] + (vs_b @ e_u) / s_log
    py_b = orig_log[1] - (vs_b @ e_v) / s_log
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
    alpha_m1_inner = low_a_val > 162
    nb_m = np.zeros_like(alpha_m1_inner, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb_m += np.roll(np.roll(alpha_m1_inner, dy, axis=0), dx, axis=1).astype(np.int32)
    alpha_m1_inner &= (nb_m >= 2)
    dil_m = np.zeros_like(alpha_m1_inner)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dil_m |= np.roll(np.roll(alpha_m1_inner, dy, axis=0), dx, axis=1)
    mask_m1_outlined = alpha_m1_inner | dil_m

    # Reference Route A v4.1 masks (`Alpha > 162`)
    ref_hi = np.array(Image.open(V4_1_DIR / "route_a_v4_highres_clean.png").convert("RGBA"))
    ref_log = np.array(Image.open(V4_1_DIR / "route_a_v4_1_sprite_logical.png").convert("RGBA"))
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
    mask_ref_logical = ref_log[:, :, 3] > 162

    # Measure full-silhouette bidirectional boundary distance (including all 4 legs and tail!)
    b_ref = get_4conn_boundary(mask_ref_logical)
    b_mod = get_4conn_boundary(mask_m1_outlined)
    yr, xr = np.where(b_ref)
    ym, xm = np.where(b_mod)
    d2_full = (yr[:, None] - ym[None, :]) ** 2 + (xr[:, None] - xm[None, :]) ** 2
    dr_min = np.sqrt(d2_full.min(axis=1))
    dm_min = np.sqrt(d2_full.min(axis=0))
    all_full_d = np.concatenate([dr_min, dm_min])

    full_max_d = float(all_full_d.max())
    full_p95_d = float(np.percentile(all_full_d, 95))
    full_mean_d = float(all_full_d.mean())
    full_outliers = int((all_full_d > 2.001).sum())

    # Also measure inner pre-outline full-silhouette max distance
    b_ref_in = get_4conn_boundary(alpha_ref_inner)
    b_mod_in = get_4conn_boundary(alpha_m1_inner)
    yri, xri = np.where(b_ref_in)
    ymi, xmi = np.where(b_mod_in)
    d2_in = (yri[:, None] - ymi[None, :]) ** 2 + (xri[:, None] - xmi[None, :]) ** 2
    inner_full_max_d = float(max(np.sqrt(d2_in.min(axis=1)).max(), np.sqrt(d2_in.min(axis=0)).max()))

    # Measure Head-Body region max distance
    hb_r = (xr <= 80) & (yr <= 72)
    hb_m = (xm <= 80) & (ym <= 72)
    hb_max_d = float(max(dr_min[hb_r].max(), dm_min[hb_m].max()))
    iou = float((mask_ref_logical & mask_m1_outlined).sum() / max(1, (mask_ref_logical | mask_m1_outlined).sum()))

    # 2. Rasterize evaluated CAT_EYE_L and CAT_EYE_R using their own D2 UVs and parametric 4-element emerald shader
    eye_mask_hi = np.zeros((hi_h, hi_w), dtype=bool)
    rgb_eye_hi = np.zeros((hi_h, hi_w, 3), dtype=np.uint8)
    zbuf_eye = np.full((hi_h, hi_w), -1e9, dtype=np.float64)

    for name, u_b in [("CAT_EYE_L", (0.265, 0.365)), ("CAT_EYE_R", (0.385, 0.485))]:
        ev = bpy.data.objects[name].evaluated_get(depsgraph)
        m = ev.to_mesh()
        m.calc_loop_triangles()
        vs = np.array([list(ev.matrix_world @ v.co) for v in m.vertices], dtype=np.float64)
        uv_layer = m.uv_layers.active.data
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
            denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(denom) < 1e-8:
                continue
            yy, xx = np.meshgrid(np.arange(ymin, ymax + 1) + 0.5, np.arange(xmin, xmax + 1) + 0.5, indexing="ij")
            w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
            w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
            w2 = 1.0 - w0 - w1
            z_pix = w0 * z0 + w1 * z1 + w2 * z2
            sub_z = zbuf_eye[ymin : ymax + 1, xmin : xmax + 1]
            vis = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4) & (z_pix >= sub_z)
            if not np.any(vis):
                continue
            sub_z[vis] = z_pix[vis]
            l0, l1, l2 = lt.loops
            u0_t, v0_t = uv_layer[l0].uv
            u1_t, v1_t = uv_layer[l1].uv
            u2_t, v2_t = uv_layer[l2].uv
            u_p = w0[vis] * u0_t + w1[vis] * u1_t + w2[vis] * u2_t
            v_p = w0[vis] * v0_t + w1[vis] * v1_t + w2[vis] * v2_t
            ux = (u_p - u_b[0]) / (u_b[1] - u_b[0])
            vz = (v_p - 0.020) / (0.230 - 0.020)
            ex = (ux - 0.5) / 0.42
            ez = (vz - 0.5) / 0.42
            c_pix = np.full((len(ex), 3), [43, 122, 61], dtype=np.uint8)
            is_bright = ez < 0.05
            c_pix[is_bright] = [104, 200, 100]
            is_pupil = (np.abs(ex) < 0.25) & (ez > -0.62) & (ez < 0.52)
            c_pix[is_pupil] = [18, 28, 22]
            is_hl = ((ex - 0.30) ** 2 + (ez - 0.26) ** 2) < 0.11
            c_pix[is_hl] = [252, 248, 240]
            is_lid = ez > 0.55
            c_pix[is_lid] = [27, 16, 10]
            rgb_eye_hi[ymin : ymax + 1, xmin : xmax + 1][vis] = c_pix
            eye_mask_hi[ymin : ymax + 1, xmin : xmax + 1][vis] = True
        ev.to_mesh_clear()

    low_near = np.array(Image.fromarray(rgb_eye_hi, mode="RGB").resize((gw, gh), Image.Resampling.NEAREST))
    eye_mask_low = np.array(Image.fromarray((eye_mask_hi.astype(np.uint8) * 255), mode="L").resize((gw, gh), Image.Resampling.BOX)) > 96
    r, g, b = low_near[:, :, 0].astype(int), low_near[:, :, 1].astype(int), low_near[:, :, 2].astype(int)

    eyelid_dark_px = int((eye_mask_low & (r == 27) & (g == 16) & (b == 10)).sum())
    outer_emerald_px = int((eye_mask_low & (r == 43) & (g == 122) & (b == 61)).sum())
    inner_bright_emerald_px = int((eye_mask_low & (r == 104) & (g == 200) & (b == 100)).sum())
    vertical_pupil_px = int((eye_mask_low & (r == 18) & (g == 28) & (b == 22)).sum())
    white_catchlight_px = int((eye_mask_low & (r > 230) & (g > 230) & (b > 220)).sum())

    eye_4_elements_readable = bool(
        eyelid_dark_px >= 6
        and outer_emerald_px >= 8
        and inner_bright_emerald_px >= 6
        and vertical_pupil_px >= 4
        and white_catchlight_px >= 2
    )

    gate_pass = (
        len(cal_shape_keys) == 0
        and len(non_zero_shape_keys) == 0
        and full_max_d <= 2.0
        and inner_full_max_d <= 2.0
        and hb_max_d <= 2.0
        and full_outliers == 0
        and iou >= 0.93
        and eye_4_elements_readable
    )
    return {
        "pass": gate_pass,
        "pure_basis_rest_mesh_evaluated": (len(cal_shape_keys) == 0 and len(non_zero_shape_keys) == 0),
        "cal_shape_keys_found": cal_shape_keys,
        "non_zero_shape_keys_during_eval": non_zero_shape_keys,
        "logical_grid": [gw, gh],
        "alpha_threshold": 162,
        "full_silhouette_max_distance_px": round(full_max_d, 4),
        "inner_full_silhouette_max_distance_px": round(inner_full_max_d, 4),
        "full_silhouette_p95_distance_px": round(full_p95_d, 4),
        "full_silhouette_mean_distance_px": round(full_mean_d, 4),
        "full_silhouette_outliers_gt_2px": full_outliers,
        "head_body_max_distance_px": round(hb_max_d, 4),
        "mask_iou": round(iou, 4),
        "eyelid_dark_px_count": eyelid_dark_px,
        "outer_emerald_px_count": outer_emerald_px,
        "inner_bright_emerald_px_count": inner_bright_emerald_px,
        "vertical_pupil_px_count": vertical_pupil_px,
        "white_catchlight_px_count": white_catchlight_px,
        "eye_4_elements_readable": eye_4_elements_readable,
    }


def run_validation() -> dict:
    blend_path = MASTER_DIR / "master_cat.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    master_spec = json.loads((MASTER_DIR / "master_spec.json").read_text())
    uv_manifest = json.loads((MASTER_DIR / "uv_manifest.json").read_text())
    landmarks_doc = json.loads((MASTER_DIR / "landmark_vertices.json").read_text())
    landmarks = landmarks_doc["points"]

    checks = {}

    # =========================================================================
    # Check 1: Manifoldness (0 non-manifold edges, 0 holes, 0 zero-area faces)
    # =========================================================================
    req_meshes = ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]
    mesh_stats = {}
    c1_pass = True
    for m_name in req_meshes:
        if m_name not in bpy.data.objects or bpy.data.objects[m_name].type != "MESH":
            c1_pass = False
            mesh_stats[m_name] = {"exists": False}
            continue
        obj = bpy.data.objects[m_name]
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        non_man_edges = [e.index for e in bm.edges if not e.is_manifold]
        boundary_edges = [e.index for e in bm.edges if e.is_boundary]
        zero_faces = [f.index for f in bm.faces if f.calc_area() <= 1e-10]
        mesh_stats[m_name] = {
            "exists": True,
            "vertices": len(obj.data.vertices),
            "triangles": len(bm.faces),
            "non_manifold_edges": len(non_man_edges),
            "boundary_edges": len(boundary_edges),
            "zero_area_faces": len(zero_faces),
        }
        if len(non_man_edges) > 0 or len(boundary_edges) > 0 or len(zero_faces) > 0:
            c1_pass = False
        bm.free()
    body_tris = mesh_stats.get("CAT_BODY", {}).get("triangles", 0)
    if not (3500 <= body_tris <= 6000):
        c1_pass = False
    checks["01_manifold_and_watertight"] = {
        "pass": c1_pass,
        "meshes": mesh_stats,
    }

    # =========================================================================
    # Check 2: Consistent Outward Normals (Signed Volume > 0 & 0 flipped faces)
    # =========================================================================
    normal_stats = {}
    c2_pass = True
    for m_name in req_meshes:
        obj = bpy.data.objects[m_name]
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        signed_vol = 0.0
        for f in bm.faces:
            v0, v1, v2 = f.verts[0].co, f.verts[1].co, f.verts[2].co
            signed_vol += float(v0.dot(v1.cross(v2))) / 6.0
        orig_normals = [Vector(f.normal) for f in bm.faces]
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        flipped = sum(1 for n_old, f in zip(orig_normals, bm.faces) if n_old.dot(f.normal) < 0.0)
        normal_stats[m_name] = {
            "signed_volume_m3": round(signed_vol, 7),
            "flipped_faces": flipped,
        }
        if signed_vol <= 0.0 or flipped > 0:
            c2_pass = False
        bm.free()
    checks["02_outward_normals"] = {
        "pass": c2_pass,
        "details": normal_stats,
    }

    # =========================================================================
    # Check 3: Normalized Vertex Weights & <= 4 Influencing Bones per Vertex
    # =========================================================================
    weight_stats = {}
    c3_pass = True
    for m_name in req_meshes:
        obj = bpy.data.objects[m_name]
        max_inf = 0
        unweighted = 0
        unnormalized = 0
        lr_cross_errors = 0
        vg_names = {g.index: g.name for g in obj.vertex_groups}
        for v in obj.data.vertices:
            groups = [g for g in v.groups if g.weight > 1e-6]
            if len(groups) == 0:
                unweighted += 1
            if len(groups) > max_inf:
                max_inf = len(groups)
            w_sum = sum(g.weight for g in groups)
            if abs(w_sum - 1.0) > 1e-3:
                unnormalized += 1
            for g in groups:
                b_name = vg_names.get(g.group, "")
                if (b_name.endswith("_L") or "_L_" in b_name) and v.co.x > 0.008:
                    lr_cross_errors += 1
                elif (b_name.endswith("_R") or "_R_" in b_name) and v.co.x < -0.008:
                    lr_cross_errors += 1
        weight_stats[m_name] = {
            "max_influences_per_vertex": max_inf,
            "unweighted_vertices": unweighted,
            "unnormalized_vertices": unnormalized,
            "lr_cross_skin_errors": lr_cross_errors,
        }
        if max_inf > 4 or unweighted > 0 or unnormalized > 0 or lr_cross_errors > 0:
            c3_pass = False
    checks["03_vertex_weights_normalized_and_le4"] = {
        "pass": c3_pass,
        "details": weight_stats,
    }

    # =========================================================================
    # Check 4: Shape Keys (`id_*`, `sty_*`, `face`) Stability, Range [0, 1],
    #          No NaN, and ZERO `cal_*` or unauthorized keys on any mesh!
    # =========================================================================
    obj_body = bpy.data.objects["CAT_BODY"]
    sk_blocks = obj_body.data.shape_keys.key_blocks if obj_body.data.shape_keys else {}
    req_id_keys = master_spec["shape_keys"]["identity"]
    req_sty_keys = master_spec["shape_keys"]["style"]
    req_face_keys = master_spec["shape_keys"]["face"]
    all_req_keys = req_id_keys + req_sty_keys + req_face_keys
    allowed_body_keys = set(["Basis"] + all_req_keys)

    unauthorized_keys = []
    for m_name in req_meshes:
        m_obj = bpy.data.objects[m_name]
        if m_obj.data.shape_keys:
            for kb in m_obj.data.shape_keys.key_blocks:
                if m_name == "CAT_BODY":
                    if kb.name not in allowed_body_keys or kb.name.startswith("cal_"):
                        unauthorized_keys.append(f"{m_name}:{kb.name}")
                else:
                    unauthorized_keys.append(f"{m_name}:{kb.name}")

    missing_keys = [k for k in all_req_keys if k not in sk_blocks]
    nan_keys = []
    range_errors = []
    zero_delta_keys = []
    basis_pts = np.array([[v.co.x, v.co.y, v.co.z] for v in sk_blocks["Basis"].data], dtype=np.float64)
    for k in all_req_keys:
        if k not in sk_blocks:
            continue
        blk = sk_blocks[k]
        if abs(blk.slider_min - 0.0) > 1e-5 or abs(blk.slider_max - 1.0) > 1e-5:
            range_errors.append(k)
        pts = np.array([[v.co.x, v.co.y, v.co.z] for v in blk.data], dtype=np.float64)
        if not np.all(np.isfinite(pts)):
            nan_keys.append(k)
        max_delta = float(np.linalg.norm(pts - basis_pts, axis=1).max())
        if max_delta < 1e-4:
            zero_delta_keys.append(k)

    c4_pass = (
        len(unauthorized_keys) == 0
        and len(missing_keys) == 0
        and len(nan_keys) == 0
        and len(range_errors) == 0
        and len(zero_delta_keys) == 0
    )
    checks["04_shape_keys_valid_and_separated"] = {
        "pass": c4_pass,
        "identity_keys_count": len(req_id_keys),
        "style_keys_count": len(req_sty_keys),
        "face_keys_count": len(req_face_keys),
        "unauthorized_or_cal_keys": unauthorized_keys,
        "missing_keys": missing_keys,
        "nan_keys": nan_keys,
        "range_errors": range_errors,
        "zero_delta_keys": zero_delta_keys,
    }

    # =========================================================================
    # Check 5: UV in [0, 1], 16 Non-Overlapping Quadrants, 100% Non-Mirrored L/R
    # =========================================================================
    uv_data = obj_body.data.uv_layers.active.data
    us = np.array([d.uv.x for d in uv_data], dtype=np.float64)
    vs = np.array([d.uv.y for d in uv_data], dtype=np.float64)
    in_bounds = bool(np.all((us >= 0.0) & (us <= 1.0) & (vs >= 0.0) & (vs <= 1.0)))

    poly_quads = []
    deg_uv_tris = 0
    for poly in obj_body.data.polygons:
        l0, l1, l2 = poly.loop_indices[0], poly.loop_indices[1], poly.loop_indices[2]
        u0, v0 = uv_data[l0].uv.x, uv_data[l0].uv.y
        u1, v1 = uv_data[l1].uv.x, uv_data[l1].uv.y
        u2, v2 = uv_data[l2].uv.x, uv_data[l2].uv.y
        area2 = abs((u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0))
        if area2 <= 1e-10:
            deg_uv_tris += 1
        cu = (u0 + u1 + u2) / 3.0
        cv = (v0 + v1 + v2) / 3.0
        col = min(3, max(0, int(cu * 4.0)))
        row_bl = min(3, max(0, int(cv * 4.0)))
        poly_quads.append((col, row_bl))

    unique_quads = set(poly_quads)
    lr_pairs_disjoint = (
        (0, 2) in unique_quads and (1, 2) in unique_quads
        and (0, 1) in unique_quads and (1, 1) in unique_quads
        and (2, 1) in unique_quads and (3, 1) in unique_quads
        and (3, 3) in unique_quads and (1, 0) in unique_quads
    )
    c5_pass = in_bounds and len(unique_quads) == 16 and deg_uv_tris == 0 and lr_pairs_disjoint
    checks["05_uv_bounds_and_non_mirrored_4x4"] = {
        "pass": c5_pass,
        "uv_min": [round(float(us.min()), 6), round(float(vs.min()), 6)],
        "uv_max": [round(float(us.max()), 6), round(float(vs.max()), 6)],
        "occupied_quadrants": len(unique_quads),
        "degenerate_uv_triangles": deg_uv_tris,
        "lr_islands_independent": lr_pairs_disjoint,
    }

    # =========================================================================
    # Check 6: Deterministic `uv_hash` Matches `uv_manifest.json` & `master_spec.json`
    # =========================================================================
    measured_hash = compute_uv_hash(obj_body.data)
    manifest_hash = uv_manifest.get("uv_hash", "")
    spec_hash = master_spec.get("uv_hash", "")
    c6_pass = (measured_hash == manifest_hash) and (measured_hash == spec_hash) and measured_hash.startswith("sha256:")
    checks["06_uv_hash_matches_manifest"] = {
        "pass": c6_pass,
        "measured_uv_hash": measured_hash,
        "manifest_uv_hash": manifest_hash,
    }

    # =========================================================================
    # Check 7: 40 Bones Naming & Hierarchy Matches `master_spec.json`
    # =========================================================================
    obj_arm = bpy.data.objects["CAT_ARMATURE"]
    spec_bones = master_spec.get("bones_40") or master_spec.get("bones")
    arm_bones = obj_arm.data.bones
    hierarchy_mismatches = []
    for b_info in spec_bones:
        b_name = b_info["name"]
        p_expected = b_info["parent"]
        if b_name not in arm_bones:
            hierarchy_mismatches.append(f"Missing bone: {b_name}")
            continue
        b_actual = arm_bones[b_name]
        p_actual = b_actual.parent.name if b_actual.parent else None
        if p_actual != p_expected:
            hierarchy_mismatches.append(f"{b_name}: parent {p_actual} != {p_expected}")
    c7_pass = (len(arm_bones) == 40) and (len(spec_bones) == 40) and (len(hierarchy_mismatches) == 0)
    checks["07_40_bones_hierarchy"] = {
        "pass": c7_pass,
        "bone_count": len(arm_bones),
        "mismatches": hierarchy_mismatches,
    }

    # =========================================================================
    # Check 8: Anatomical Left (`_L` at X < 0) and Right (`_R` at X > 0) Not Swapped
    # =========================================================================
    lr_bone_errors = []
    for bone in arm_bones:
        hx = float(bone.head_local.x)
        tx = float(bone.tail_local.x)
        if bone.name.endswith("_L"):
            if not (hx < -1e-4 and tx < -1e-4):
                lr_bone_errors.append(f"{bone.name}: head_x={hx:.4f}, tail_x={tx:.4f} (expected < 0)")
        elif bone.name.endswith("_R"):
            if not (hx > 1e-4 and tx > 1e-4):
                lr_bone_errors.append(f"{bone.name}: head_x={hx:.4f}, tail_x={tx:.4f} (expected > 0)")
    root_at_origin = float(arm_bones["root"].head_local.length) < 1e-5
    c8_pass = (len(lr_bone_errors) == 0) and root_at_origin
    checks["08_anatomical_lr_bones_and_root_origin"] = {
        "pass": c8_pass,
        "root_at_origin": root_at_origin,
        "lr_bone_errors": lr_bone_errors,
    }

    # =========================================================================
    # Check 9: `landmark_vertices.json` Indices Valid & Symmetric Under Deformation
    # =========================================================================
    n_verts = len(obj_body.data.vertices)
    invalid_indices = []
    for k, idxs in landmarks.items():
        if not isinstance(idxs, list) or len(idxs) == 0:
            invalid_indices.append(k)
            continue
        for idx in idxs:
            if not (0 <= int(idx) < n_verts):
                invalid_indices.append(f"{k}:{idx}")

    sym_pairs = [
        ("eye_L", "eye_R"),
        ("ear_L_base", "ear_R_base"),
        ("ear_L_mid", "ear_R_mid"),
        ("ear_L_tip", "ear_R_tip"),
        ("clavicle_L", "clavicle_R"),
        ("shoulder_FL", "shoulder_FR"),
        ("elbow_FL", "elbow_FR"),
        ("wrist_FL", "wrist_FR"),
        ("paw_FL", "paw_FR"),
        ("thigh_BL", "thigh_BR"),
        ("knee_BL", "knee_BR"),
        ("ankle_BL", "ankle_BR"),
        ("paw_BL", "paw_BR"),
    ]
    max_sym_err_m = 0.0
    for kL, kR in sym_pairs:
        pL = basis_pts[landmarks[kL]].mean(axis=0)
        pR = basis_pts[landmarks[kR]].mean(axis=0)
        err = float(np.linalg.norm([pL[0] + pR[0], pL[1] - pR[1], pL[2] - pR[2]]))
        max_sym_err_m = max(max_sym_err_m, err)

    c9_pass = (len(invalid_indices) == 0) and (max_sym_err_m < 1e-4)
    checks["09_landmark_vertices_valid_and_symmetric"] = {
        "pass": c9_pass,
        "landmark_groups_count": len(landmarks),
        "invalid_indices": invalid_indices,
        "max_lr_symmetry_error_m": round(max_sym_err_m, 7),
    }

    # =========================================================================
    # Check 10: `hot_*` & `foot_*` Empty Anchors Exist and Parented to Armature Bones
    # =========================================================================
    req_anchors = ["hot_head", "hot_back", "hot_belly", "hot_groom", "hot_pet", "foot_FL", "foot_FR", "foot_BL", "foot_BR"]
    missing_anchors = []
    anchor_binding_errors = []
    foot_rest_z_mm = {}
    for a_name in req_anchors:
        if a_name not in bpy.data.objects:
            missing_anchors.append(a_name)
            continue
        emp = bpy.data.objects[a_name]
        if emp.type != "EMPTY" or emp.parent != obj_arm or emp.parent_type != "BONE" or emp.parent_bone not in arm_bones:
            anchor_binding_errors.append(a_name)
        if a_name.startswith("foot_"):
            foot_rest_z_mm[a_name] = round(abs(float(emp.matrix_world.translation.z)) * 1000.0, 5)

    c10_pass = (len(missing_anchors) == 0) and (len(anchor_binding_errors) == 0) and (max(foot_rest_z_mm.values(), default=999.0) < 0.5)
    checks["10_hot_and_foot_anchors_bound"] = {
        "pass": c10_pass,
        "missing_anchors": missing_anchors,
        "binding_errors": anchor_binding_errors,
        "rest_foot_z_error_mm": foot_rest_z_mm,
    }

    # =========================================================================
    # Check 11: `adapt_rest.py` Consistency —
    #   Rest AND deformed tongue_01 shift both < 1.0mm (hard gate),
    #   4 feet grounded at Z=0 (< 0.5mm), deformed head ratio in [40%, 43%]
    # =========================================================================
    rest_adapt_report = adapt_rest_rig(landmarks_path=MASTER_DIR / "landmark_vertices.json")
    rest_tongue_shift_mm = rest_adapt_report["tongue_01_shift_mm"]

    test_shape = {
        "id_body_fat": 0.45,
        "id_belly": 0.35,
        "id_leg_len": 0.30,
        "id_face_round": 0.65,
        "id_muzzle_len": 0.40,
        "sty_head_enlarge": 0.35,
        "sty_leg_shorten": 0.30,
        "sty_eye_enlarge": 0.45,
        "sty_face_chibi_cheek": 0.40,
        "sty_paw_round": 0.30,
    }
    for k, val in test_shape.items():
        obj_body.data.shape_keys.key_blocks[k].value = val

    adapt_report = adapt_rest_rig(
        landmarks_path=MASTER_DIR / "landmark_vertices.json",
        report_path=OUT_DIR / "rig_adapt_report.json",
    )
    max_foot_err_after_mm = adapt_report["max_foot_z_error_mm"]
    head_ratio_after = adapt_report["deformed_proportions"]["head_height_ratio"]
    deformed_tongue_shift_mm = adapt_report["tongue_01_shift_mm"]
    c11_pass = (
        (rest_tongue_shift_mm < 1.0)
        and (deformed_tongue_shift_mm < 1.0)
        and (max_foot_err_after_mm < 0.5)
        and (0.40 <= head_ratio_after <= 0.43)
    )
    checks["11_adapt_rest_after_shapekeys_ground_and_ratio"] = {
        "pass": c11_pass,
        "rest_tongue_01_shift_mm": rest_tongue_shift_mm,
        "deformed_tongue_01_shift_mm": deformed_tongue_shift_mm,
        "max_foot_z_error_mm": max_foot_err_after_mm,
        "foot_z_errors_mm": adapt_report["foot_z_errors_mm"],
        "deformed_head_height_ratio": head_ratio_after,
        "tongue_shift_hard_limit_mm": 1.0,
    }

    # =========================================================================
    # Check 12: Source Master Contains Zero Cat-Specific Identity Textures or Dirty Images
    # =========================================================================
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    dirty_images = [img.name for img in bpy.data.images if img.name not in ("Render Result", "Viewer Node")]
    dirty_actions = [act.name for act in bpy.data.actions]
    c12_pass = (len(dirty_images) == 0) and (len(dirty_actions) == 0)
    checks["12_clean_master_no_identity_textures"] = {
        "pass": c12_pass,
        "embedded_images": dirty_images,
        "embedded_actions": dirty_actions,
    }

    # =========================================================================
    # Check 13: Real `d045` `114x104` Full Silhouette Distance (`<= 2.0 px` including
    #           all 4 legs and tail) & Real Measured 4-Element Emerald Eye Readability
    #           on 100% Pure Static Rest Mesh (`Basis`, all ShapeKey values == 0.0)
    # =========================================================================
    d045_gate = evaluate_d045_silhouette_and_eyes()
    checks["13_d045_full_silhouette_and_eye_4_elements"] = d045_gate

    all_passed = all(c["pass"] for c in checks.values())
    passed_count = sum(1 for c in checks.values() if c["pass"])
    summary = {
        "milestone": "M1",
        "overall_status": "PASS" if all_passed else "FAIL",
        "passed_checks": f"{passed_count}/{len(checks)}",
        "uv_hash": measured_hash,
        "pure_basis_rest_mesh_evaluated": d045_gate["pure_basis_rest_mesh_evaluated"],
        "full_silhouette_max_distance_px": d045_gate["full_silhouette_max_distance_px"],
        "head_body_max_distance_px": d045_gate["head_body_max_distance_px"],
        "mask_iou": d045_gate["mask_iou"],
        "eye_4_elements_readable": d045_gate["eye_4_elements_readable"],
        "checks": checks,
    }
    report_file = OUT_DIR / "validation_report.json"
    report_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[validate_master] {summary['overall_status']} ({summary['passed_checks']}) -> {report_file}")
    if not all_passed:
        for k, v in checks.items():
            if not v["pass"]:
                print(f"  FAILED: {k} -> {v}")
        sys.exit(1)
    return summary


if __name__ == "__main__":
    run_validation()
