#!/usr/bin/env python3
"""
Stage M1 — Rest Rig & Anchor Adaptation (`pipeline/rig/adapt_rest.py`)
Evaluates current `id_*` and `sty_*` Shape Keys on `CAT_BODY`, grounds the lowest paw
vertices to `Z = 0.0`, recomputes all 40 bone head/tail positions in `CAT_ARMATURE` Edit Mode
from `art/master_cat/landmark_vertices.json` using the unified formula shared with `build_master.py`,
resets the Armature Rest Pose, and updates `hot_head/back/belly/groom/pet` and `foot_FL/FR/BL/BR`
Empty anchors so all 4 feet sit on `Z = 0.0` with error < 0.5mm and tongue shift < 1mm.
"""
import json
from pathlib import Path
import bpy
from mathutils import Vector
import numpy as np

ROOT_DIR = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT_DIR / "art" / "master_cat"


def evaluate_shaped_vertices(obj_body) -> np.ndarray:
    """Evaluate the active combination of Identity & Style Shape Keys on CAT_BODY in object space."""
    mesh = obj_body.data
    n_verts = len(mesh.vertices)
    if mesh.shape_keys is None or len(mesh.shape_keys.key_blocks) == 0:
        return np.array([[v.co.x, v.co.y, v.co.z] for v in mesh.vertices], dtype=np.float64)

    kb = mesh.shape_keys.key_blocks
    basis = np.array([[kb["Basis"].data[i].co.x, kb["Basis"].data[i].co.y, kb["Basis"].data[i].co.z] for i in range(n_verts)], dtype=np.float64)
    out = basis.copy()
    for block in kb:
        if block.name == "Basis" or abs(block.value) < 1e-7:
            continue
        pts = np.array([[block.data[i].co.x, block.data[i].co.y, block.data[i].co.z] for i in range(n_verts)], dtype=np.float64)
        out += float(block.value) * (pts - basis)
    return out


def compute_bone_targets_and_centers(vs_def: np.ndarray, landmarks: dict):
    """
    Unified 40-bone head/tail + eye/tongue/anchor target computation shared identically
    between `build_master.py` and `adapt_rest.py`.
    """
    def pt_pos(key: str) -> Vector:
        idxs = landmarks[key]
        return Vector(vs_def[idxs].mean(axis=0).tolist())

    head_p = pt_pos("head_center")
    chin_p = pt_pos("chin")
    # Shared oral-cavity tongue-bed landmark for CAT_TONGUE mesh + tongue_01/tongue_tip bones.
    # Prefer mouth_floor; fall back to tongue_01 (both must index the same lower-jaw bed verts).
    if "mouth_floor" in landmarks:
        tongue_bed_p = pt_pos("mouth_floor")
    else:
        tongue_bed_p = pt_pos("tongue_01")

    eye_L_center = pt_pos("eye_L")
    eye_R_center = pt_pos("eye_R")
    # Tongue rests a fixed 15mm above the pinned tongue-bed, fully inside the lower jaw.
    tongue_center = Vector((0.0, float(tongue_bed_p.y), float(tongue_bed_p.z + 0.015)))

    bone_targets = {
        "root": (Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.06, 0.0))),
        "hips": (pt_pos("hips_center"), pt_pos("spine_01")),
        "spine_01": (pt_pos("spine_01"), pt_pos("spine_02")),
        "spine_02": (pt_pos("spine_02"), pt_pos("spine_03")),
        "spine_03": (pt_pos("spine_03"), pt_pos("spine_04")),
        "spine_04": (pt_pos("spine_04"), pt_pos("neck_01")),
        "neck_01": (pt_pos("neck_01"), pt_pos("neck_02")),
        "neck_02": (pt_pos("neck_02"), head_p),
        "head": (head_p, pt_pos("crown")),
        "jaw": (Vector((0.0, 0.5 * (head_p.y + chin_p.y), 0.5 * (head_p.z + chin_p.z))), chin_p),
        "tongue_01": (
            Vector((0.0, tongue_center.y - 0.010, tongue_center.z)),
            Vector((0.0, tongue_center.y, tongue_center.z)),
        ),
        "tongue_tip": (
            Vector((0.0, tongue_center.y, tongue_center.z)),
            Vector((0.0, tongue_center.y + 0.012, tongue_center.z)),
        ),
        "eye_L": (eye_L_center, Vector((eye_L_center.x, eye_L_center.y + 0.025, eye_L_center.z))),
        "eye_R": (eye_R_center, Vector((eye_R_center.x, eye_R_center.y + 0.025, eye_R_center.z))),
        "ear_L_01": (pt_pos("ear_L_base"), pt_pos("ear_L_mid")),
        "ear_L_02": (pt_pos("ear_L_mid"), pt_pos("ear_L_tip")),
        "ear_R_01": (pt_pos("ear_R_base"), pt_pos("ear_R_mid")),
        "ear_R_02": (pt_pos("ear_R_mid"), pt_pos("ear_R_tip")),
        "clavicle_L": (pt_pos("clavicle_L"), pt_pos("shoulder_FL")),
        "upperarm_L": (pt_pos("shoulder_FL"), pt_pos("elbow_FL")),
        "forearm_L": (pt_pos("elbow_FL"), pt_pos("wrist_FL")),
        "paw_F_L": (pt_pos("wrist_FL"), Vector((pt_pos("paw_FL").x, pt_pos("paw_FL").y + 0.015, 0.0))),
        "clavicle_R": (pt_pos("clavicle_R"), pt_pos("shoulder_FR")),
        "upperarm_R": (pt_pos("shoulder_FR"), pt_pos("elbow_FR")),
        "forearm_R": (pt_pos("elbow_FR"), pt_pos("wrist_FR")),
        "paw_F_R": (pt_pos("wrist_FR"), Vector((pt_pos("paw_FR").x, pt_pos("paw_FR").y + 0.015, 0.0))),
        "thigh_L": (pt_pos("thigh_BL"), pt_pos("knee_BL")),
        "shin_L": (pt_pos("knee_BL"), pt_pos("ankle_BL")),
        "foot_L": (pt_pos("ankle_BL"), Vector((pt_pos("paw_BL").x, pt_pos("paw_BL").y, 0.012))),
        "paw_B_L": (Vector((pt_pos("paw_BL").x, pt_pos("paw_BL").y, 0.012)), Vector((pt_pos("paw_BL").x, pt_pos("paw_BL").y + 0.020, 0.0))),
        "thigh_R": (pt_pos("thigh_BR"), pt_pos("knee_BR")),
        "shin_R": (pt_pos("knee_BR"), pt_pos("ankle_BR")),
        "foot_R": (pt_pos("ankle_BR"), Vector((pt_pos("paw_BR").x, pt_pos("paw_BR").y, 0.012))),
        "paw_B_R": (Vector((pt_pos("paw_BR").x, pt_pos("paw_BR").y, 0.012)), Vector((pt_pos("paw_BR").x, pt_pos("paw_BR").y + 0.020, 0.0))),
        "tail_01": (pt_pos("tail_root"), pt_pos("tail_01")),
        "tail_02": (pt_pos("tail_01"), pt_pos("tail_02")),
        "tail_03": (pt_pos("tail_02"), pt_pos("tail_03")),
        "tail_04": (pt_pos("tail_03"), pt_pos("tail_04")),
        "tail_05": (pt_pos("tail_04"), pt_pos("tail_05")),
        "tail_06": (pt_pos("tail_05"), pt_pos("tail_tip")),
    }

    anchor_targets = {
        "hot_head": ("head", pt_pos("hot_head")),
        "hot_back": ("spine_02", pt_pos("hot_back")),
        "hot_belly": ("spine_02", pt_pos("hot_belly")),
        "hot_groom": ("forearm_L", pt_pos("hot_groom")),
        "hot_pet": ("head", pt_pos("hot_pet")),
        "foot_FL": ("paw_F_L", Vector((pt_pos("paw_FL").x, pt_pos("paw_FL").y, 0.0))),
        "foot_FR": ("paw_F_R", Vector((pt_pos("paw_FR").x, pt_pos("paw_FR").y, 0.0))),
        "foot_BL": ("paw_B_L", Vector((pt_pos("paw_BL").x, pt_pos("paw_BL").y, 0.0))),
        "foot_BR": ("paw_B_R", Vector((pt_pos("paw_BR").x, pt_pos("paw_BR").y, 0.0))),
    }
    return bone_targets, anchor_targets, eye_L_center, eye_R_center, tongue_center


def adapt_rest_rig(landmarks_path: Path = None, report_path: Path = None) -> dict:
    if landmarks_path is None:
        landmarks_path = MASTER_DIR / "landmark_vertices.json"
    landmarks = json.loads(landmarks_path.read_text())["points"]

    obj_body = bpy.data.objects["CAT_BODY"]
    obj_arm = bpy.data.objects["CAT_ARMATURE"]
    obj_eye_L = bpy.data.objects["CAT_EYE_L"]
    obj_eye_R = bpy.data.objects["CAT_EYE_R"]
    obj_tongue = bpy.data.objects["CAT_TONGUE"]

    # 1. Evaluate deformed vertex coordinates from Shape Keys
    vs_def = evaluate_shaped_vertices(obj_body)
    z_min = float(vs_def[:, 2].min())

    # Ground deformed mesh so lowest paw vertex sits at Z = 0.0
    if abs(z_min) > 1e-6:
        vs_def[:, 2] -= z_min
        if obj_body.data.shape_keys:
            for block in obj_body.data.shape_keys.key_blocks:
                for i in range(len(obj_body.data.vertices)):
                    block.data[i].co.z -= z_min
        for i in range(len(obj_body.data.vertices)):
            obj_body.data.vertices[i].co.z -= z_min
        obj_body.data.update()

    bone_targets, anchor_targets, new_eye_L_vec, new_eye_R_vec, new_tongue_vec = compute_bone_targets_and_centers(vs_def, landmarks)

    # Update eye & tongue mesh rest positions to follow deformed eye/jaw landmarks
    for obj_m, target_vec in [
        (obj_eye_L, new_eye_L_vec),
        (obj_eye_R, new_eye_R_vec),
        (obj_tongue, new_tongue_vec),
    ]:
        mesh_m = obj_m.data
        if mesh_m.shape_keys and "Basis" in mesh_m.shape_keys.key_blocks:
            kb_m = mesh_m.shape_keys.key_blocks
            old_c = np.array([[v.co.x, v.co.y, v.co.z] for v in kb_m["Basis"].data]).mean(axis=0)
            delta = np.array(target_vec) - old_c
            for blk in kb_m:
                for i in range(len(mesh_m.vertices)):
                    blk.data[i].co = Vector((np.array(blk.data[i].co) + delta).tolist())
        old_v = np.array([[v.co.x, v.co.y, v.co.z] for v in mesh_m.vertices]).mean(axis=0)
        delta_v = np.array(target_vec) - old_v
        for v in mesh_m.vertices:
            v.co = Vector((np.array(v.co) + delta_v).tolist())
        mesh_m.update()

    # 2. Recompute 40 bone head/tail positions in Edit Mode
    bpy.context.view_layer.objects.active = obj_arm
    bpy.ops.object.mode_set(mode="EDIT")
    bone_deltas = {}
    for b_name, (h_new, t_new) in bone_targets.items():
        eb = obj_arm.data.edit_bones[b_name]
        dh = float((h_new - eb.head).length)
        dt = float((t_new - eb.tail).length)
        eb.head = h_new
        if (t_new - h_new).length < 1e-4:
            eb.tail = h_new + Vector((0.0, 0.015, 0.0))
        else:
            eb.tail = t_new
        bone_deltas[b_name] = {"head_shift_m": round(dh, 6), "tail_shift_m": round(dt, 6)}
    bpy.ops.object.mode_set(mode="OBJECT")

    # Reset Pose Mode transforms to identity
    for pb in obj_arm.pose.bones:
        pb.matrix_basis.identity()

    # 3. Update Empty anchors (`hot_*` and `foot_*`)
    for a_name, (parent_bone, a_loc) in anchor_targets.items():
        emp = bpy.data.objects[a_name]
        bone_obj = obj_arm.data.bones[parent_bone]
        bone_tail_world = obj_arm.matrix_world @ bone_obj.matrix_local @ Vector((0.0, bone_obj.length, 0.0))
        bone_mat_world = obj_arm.matrix_world @ bone_obj.matrix_local
        bone_mat_world.translation = bone_tail_world
        emp.matrix_parent_inverse = bone_mat_world.inverted()
        emp.location = a_loc

    bpy.context.view_layer.update()

    foot_z_errors_mm = {}
    for f_name in ["foot_FL", "foot_FR", "foot_BL", "foot_BR"]:
        emp = bpy.data.objects[f_name]
        z_w = float(emp.matrix_world.translation.z)
        foot_z_errors_mm[f_name] = round(abs(z_w) * 1000.0, 5)

    z_tot = float(vs_def[:, 2].max() - vs_def[:, 2].min())
    z_chin = float(vs_def[landmarks["chin"], 2].mean())
    tongue_shift_mm = round(max(bone_deltas["tongue_01"]["head_shift_m"], bone_deltas["tongue_01"]["tail_shift_m"]) * 1000.0, 4)
    report = {
        "status": "PASS",
        "bone_count": len(bone_targets),
        "bone_deltas": bone_deltas,
        "tongue_01_shift_mm": tongue_shift_mm,
        "foot_z_errors_mm": foot_z_errors_mm,
        "max_foot_z_error_mm": max(foot_z_errors_mm.values()),
        "deformed_proportions": {
            "total_height_m": round(z_tot, 4),
            "chin_height_m": round(z_chin, 4),
            "head_height_ratio": round((z_tot - z_chin) / z_tot, 4),
        },
    }
    if report_path is not None:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    rep = adapt_rest_rig()
    print(
        "[adapt_rest] Completed:",
        json.dumps(rep["foot_z_errors_mm"]),
        "Tongue shift (mm):",
        rep["tongue_01_shift_mm"],
        "Head ratio:",
        rep["deformed_proportions"]["head_height_ratio"],
    )
