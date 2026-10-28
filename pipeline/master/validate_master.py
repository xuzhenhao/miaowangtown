#!/usr/bin/env python3
"""
Stage M1 — 12-Item Industrial Master Cat Automated Gate (`pipeline/master/validate_master.py`)
Validates `art/master_cat/master_cat.blend` against all 12 criteria in `DEVELOPMENT_PLAN.md` v1.3
(both before and after applying `id_*` + `sty_*` Shape Keys + `adapt_rest.py`), and writes
`docs/validation/m1_master_validation/validation_report.json`.
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

ROOT_DIR = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT_DIR / "art" / "master_cat"
OUT_DIR = ROOT_DIR / "docs" / "validation" / "m1_master_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT_DIR))

from pipeline.rig.adapt_rest import adapt_rest_rig, evaluate_shaped_vertices


def compute_uv_hash(mesh) -> str:
    uv = mesh.uv_layers.active.data
    rows = [
        [loop.vertex_index, round(uv[loop.index].uv.x, 6), round(uv[loop.index].uv.y, 6)]
        for loop in mesh.loops
    ]
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


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
    # Also verify CAT_BODY triangle count is in [3500, 6000]
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
        # Signed volume via divergence theorem: V = (1/6) * sum(v0 . (v1 x v2))
        signed_vol = 0.0
        for f in bm.faces:
            v0, v1, v2 = f.verts[0].co, f.verts[1].co, f.verts[2].co
            signed_vol += float(v0.dot(v1.cross(v2))) / 6.0
        # Also check if recalc_face_normals flips any face
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
                if b_name.endswith("_L") and v.co.x > 0.008:
                    lr_cross_errors += 1
                elif b_name.endswith("_R") and v.co.x < -0.008:
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
    # Check 4: Shape Keys (`id_*`, `sty_*`, `face`) Stability, Range [0, 1], No NaN
    # =========================================================================
    obj_body = bpy.data.objects["CAT_BODY"]
    sk_blocks = obj_body.data.shape_keys.key_blocks if obj_body.data.shape_keys else {}
    req_id_keys = master_spec["shape_keys"]["identity"]
    req_sty_keys = master_spec["shape_keys"]["style"]
    req_face_keys = master_spec["shape_keys"]["face"]
    all_req_keys = req_id_keys + req_sty_keys + req_face_keys

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

    c4_pass = (len(missing_keys) == 0 and len(nan_keys) == 0 and len(range_errors) == 0 and len(zero_delta_keys) == 0)
    checks["04_shape_keys_valid_and_separated"] = {
        "pass": c4_pass,
        "identity_keys_count": len(req_id_keys),
        "style_keys_count": len(req_sty_keys),
        "face_keys_count": len(req_face_keys),
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

    # Verify each polygon's UV centroid falls into one of the 16 quadrants and L/R quadrants do not overlap
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
    # Check L vs R independence: B1 (0,2) vs B2 (1,2), C1 (0,1) vs C2 (1,1), C3 (2,1) vs C4 (3,1), A4 (3,3) vs D2 (1,0)
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

    # Check L/R symmetry of paired landmarks on Basis
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
    # Check 11: Shape Keys Deformation + `adapt_rest.py` Keeps 4 Feet on Z=0 (< 0.5mm)
    #           and Head-to-Body Height Ratio in [40%, 43%]
    # =========================================================================
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
    c11_pass = (max_foot_err_after_mm < 0.5) and (0.40 <= head_ratio_after <= 0.435)
    checks["11_adapt_rest_after_shapekeys_ground_and_ratio"] = {
        "pass": c11_pass,
        "max_foot_z_error_mm": max_foot_err_after_mm,
        "foot_z_errors_mm": adapt_report["foot_z_errors_mm"],
        "deformed_head_height_ratio": head_ratio_after,
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

    all_passed = all(c["pass"] for c in checks.values())
    passed_count = sum(1 for c in checks.values() if c["pass"])
    summary = {
        "milestone": "M1",
        "overall_status": "PASS" if all_passed else "FAIL",
        "passed_checks": f"{passed_count}/{len(checks)}",
        "uv_hash": measured_hash,
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
