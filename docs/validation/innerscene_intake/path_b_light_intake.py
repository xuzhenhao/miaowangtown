#!/usr/bin/env python3
"""
Innerscene Standing Cat Path B: lightweight intake
- skip Voxel Remesh / anatomy sculpt
- keep original UV + baseColor
- normalize to Three.js convention (height≈1.25, feet y=0)
- fit 26 bones to actual mesh cross-sections (NOT raw template span)
- auto + heuristic skin weights
- export to docs/validation/grab3d_intake/out_b/
Does NOT copy to assets/ or public/base.
"""
import json
import math
import os
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

# Import helpers from build_base
sys.path.insert(0, "/workspace/miaowangtown/prototype/tools/blender")
import build_base as bb

SRC = "/workspace/miaowangtown/reference/open_cat_bases/innerscene_standing_cat/cat_clean.glb"
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/innerscene_intake/out_b")
META_PATH = Path("/workspace/miaowangtown/docs/validation/innerscene_intake/path_b_meta.json")


def normalize_keep_materials(obj: bpy.types.Object):
    """Same scale/placement as build_base.normalize_imported_mesh but KEEP materials/UV."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    verts = [v.co.copy() for v in obj.data.vertices]
    min_v = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    max_v = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    size = max_v - min_v
    scale = 1.25 / max(size.z, 1e-4)
    center_x = 0.5 * (min_v.x + max_v.x)
    center_y = 0.5 * (min_v.y + max_v.y)
    for v in obj.data.vertices:
        v.co.x = (v.co.x - center_x) * scale
        v.co.y = (v.co.y - center_y) * scale
        v.co.z = (v.co.z - min_v.z) * scale
    obj.data.update()


def mesh_three_verts(obj):
    return [bb.b2t(v.co.copy()) for v in obj.data.vertices]


def bbox_three(verts):
    xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
        "span": [max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)],
    }


def ground_paws(verts, eps=0.025):
    """Find approximate paw contact centroids in Three space (y up, +z forward)."""
    low = [v for v in verts if v.y <= eps]
    # quadrants by x and z
    paws = {}
    for name, xsign, zsign in (
        ("fpawL", 1, 1), ("fpawR", -1, 1), ("hpawL", 1, -1), ("hpawR", -1, -1)
    ):
        pts = [v for v in low if (v.x * xsign > 0.02) and (v.z * zsign > 0.02)]
        if not pts:
            # relax
            pts = [v for v in low if (v.x * xsign >= 0) and (v.z * zsign >= 0)]
        if pts:
            c = sum(pts, Vector((0, 0, 0))) / len(pts)
            paws[name] = {"pos": [c.x, c.y, c.z], "n": len(pts)}
        else:
            paws[name] = None
    return paws, len(low)


def estimate_body_landmarks(verts):
    """Estimate spine/chest/hips/head/ears from mesh density extrema."""
    bb_ = bbox_three(verts)
    zmin, zmax = bb_["min"][2], bb_["max"][2]
    ymin, ymax = bb_["min"][1], bb_["max"][1]
    # body core: |x| small
    core = [v for v in verts if abs(v.x) < 0.08]
    # height profile along z
    def band_y(z0, z1, x_max=0.12):
        pts = [v for v in verts if z0 <= v.z <= z1 and abs(v.x) <= x_max]
        if not pts:
            return None
        return sum(p.y for p in pts) / len(pts)

    # head = highest forward verts
    head_cands = [v for v in verts if v.z > zmax * 0.55 and v.y > ymax * 0.55]
    if not head_cands:
        head_cands = [v for v in verts if v.y > ymax * 0.7]
    head = sum(head_cands, Vector((0, 0, 0))) / max(1, len(head_cands))

    # ears = top-most left/right
    top = sorted(verts, key=lambda v: v.y, reverse=True)[: max(20, len(verts)//50)]
    earL = [v for v in top if v.x > 0.04]
    earR = [v for v in top if v.x < -0.04]
    earL_p = sum(earL, Vector((0, 0, 0))) / max(1, len(earL)) if earL else Vector((0.12, ymax * 0.95, head.z))
    earR_p = sum(earR, Vector((0, 0, 0))) / max(1, len(earR)) if earR else Vector((-0.12, ymax * 0.95, head.z))

    # hips near rear body center height
    hips_z = zmin * 0.35 + (zmax * 0.05)  # toward rear but not tail tip
    # better: find rear body mass (not thin tail)
    body = [v for v in verts if abs(v.x) < 0.18 and v.y > 0.25]
    # tail candidates: far back thin
    # chest: forward body
    chest_pts = [v for v in body if v.z > 0.15]
    hips_pts = [v for v in body if v.z < -0.05]
    chest_c = sum(chest_pts, Vector((0, 0, 0))) / max(1, len(chest_pts)) if chest_pts else Vector((0, 0.55, 0.25))
    hips_c = sum(hips_pts, Vector((0, 0, 0))) / max(1, len(hips_pts)) if hips_pts else Vector((0, 0.52, -0.2))
    spine_c = Vector((0.0, 0.5 * (chest_c.y + hips_c.y), 0.5 * (chest_c.z + hips_c.z)))

    # neck between chest and head
    neck = Vector((0.0, 0.55 * head.y + 0.45 * chest_c.y, 0.55 * head.z + 0.45 * chest_c.z))

    # tail tip = min z among elevated verts
    tail_pts = [v for v in verts if v.z < zmin * 0.5 + zmax * 0.5 and v.z < -0.15]
    if not tail_pts:
        tail_pts = [v for v in verts if v.z < bb_["min"][2] + 0.15]
    tail_tip = min(tail_pts, key=lambda v: v.z) if tail_pts else Vector((0, 0.6, zmin))

    return {
        "bbox": bb_,
        "head": head,
        "earL": earL_p,
        "earR": earR_p,
        "chest": chest_c,
        "hips": hips_c,
        "spine": spine_c,
        "neck": neck,
        "tail_tip": tail_tip,
    }


def fit_bone_defs(landmarks, paws):
    """Build 26 bone defs fitted to mesh landmarks (Three coords)."""
    hips = landmarks["hips"]
    chest = landmarks["chest"]
    spine = landmarks["spine"]
    neck = landmarks["neck"]
    head = landmarks["head"]
    earL = landmarks["earL"]
    earR = landmarks["earR"]
    tip = landmarks["tail_tip"]

    # paw targets
    def paw_or(name, fallback):
        p = paws.get(name)
        if p and p.get("pos"):
            return Vector(p["pos"])
        return fallback

    fpawL = paw_or("fpawL", Vector((0.14, 0.05, chest.z + 0.05)))
    fpawR = paw_or("fpawR", Vector((-0.14, 0.05, chest.z + 0.05)))
    hpawL = paw_or("hpawL", Vector((0.15, 0.05, hips.z - 0.05)))
    hpawR = paw_or("hpawR", Vector((-0.15, 0.05, hips.z - 0.05)))

    # raise paw bones slightly above ground (wrist/hock)
    def lift(p, y=0.10):
        return Vector((p.x, max(y, p.y + 0.06), p.z))

    fpawL, fpawR = lift(fpawL, 0.09), lift(fpawR, 0.09)
    hpawL, hpawR = lift(hpawL, 0.14), lift(hpawR, 0.14)

    # shoulders above paws toward chest
    shoulderL = Vector((0.55 * abs(fpawL.x) + 0.45 * 0.12, chest.y * 0.85, 0.7 * chest.z + 0.3 * fpawL.z))
    shoulderR = Vector((-shoulderL.x, shoulderL.y, shoulderL.z))
    elbowL = Vector((0.7 * fpawL.x + 0.3 * shoulderL.x, 0.45 * shoulderL.y + 0.55 * fpawL.y, 0.55 * fpawL.z + 0.45 * shoulderL.z))
    elbowR = Vector((-elbowL.x, elbowL.y, elbowL.z))

    hipL = Vector((0.55 * abs(hpawL.x) + 0.45 * 0.12, hips.y * 0.9, hips.z))
    hipR = Vector((-hipL.x, hipL.y, hipL.z))
    kneeL = Vector((0.7 * hpawL.x + 0.3 * hipL.x, 0.5 * hipL.y + 0.5 * hpawL.y, 0.4 * hpawL.z + 0.6 * hipL.z + 0.04))
    kneeR = Vector((-kneeL.x, kneeL.y, kneeL.z))
    # hock a bit behind knee
    hpawL = Vector((hpawL.x, hpawL.y, min(hpawL.z, kneeL.z - 0.06)))
    hpawR = Vector((hpawR.x, hpawR.y, min(hpawR.z, kneeR.z - 0.06)))

    # tail curve from hips to tip
    tail_root = Vector((0.0, hips.y * 0.95, hips.z - 0.06))
    tail_pts = []
    for i in range(7):
        t = i / 6.0
        # slight arch
        y = bb.lerp(tail_root.y, tip.y, t) + 0.06 * math.sin(math.pi * t)
        z = bb.lerp(tail_root.z, tip.z, t)
        tail_pts.append(Vector((0.0, y, z)))

    defs = [
        ("root", None, Vector((0.0, 0.0, 0.0))),
        ("hips", "root", Vector((0.0, hips.y, hips.z))),
        ("spine", "hips", Vector((0.0, spine.y, spine.z))),
        ("chest", "spine", Vector((0.0, chest.y, chest.z))),
        ("neck", "chest", Vector((0.0, neck.y, neck.z))),
        ("head", "neck", Vector((0.0, head.y, head.z))),
        ("earL", "head", Vector((earL.x, earL.y, earL.z))),
        ("earR", "head", Vector((earR.x, earR.y, earR.z))),
        ("shoulderL", "chest", shoulderL),
        ("elbowL", "shoulderL", elbowL),
        ("fpawL", "elbowL", fpawL),
        ("shoulderR", "chest", shoulderR),
        ("elbowR", "shoulderR", elbowR),
        ("fpawR", "elbowR", fpawR),
        ("hipL", "hips", hipL),
        ("kneeL", "hipL", kneeL),
        ("hpawL", "kneeL", hpawL),
        ("hipR", "hips", hipR),
        ("kneeR", "hipR", kneeR),
        ("hpawR", "kneeR", hpawR),
    ]
    # tail0..tail5 along curve
    for i in range(6):
        t = (i + 0.5) / 6.0
        idx = t * (len(tail_pts) - 1)
        i0 = int(idx); i1 = min(len(tail_pts) - 1, i0 + 1)
        u = idx - i0
        p = tail_pts[i0].lerp(tail_pts[i1], u)
        parent = "hips" if i == 0 else f"tail{i-1}"
        defs.append((f"tail{i}", parent, p))
    return defs, tail_pts


def tag_parts_keep_uv(obj, landmarks, paws):
    """Assign _PART without rebuilding UV atlas — keep original UVs."""
    me = obj.data
    if "_PART" in me.attributes:
        me.attributes.remove(me.attributes["_PART"])
    part_attr = me.attributes.new(name="_PART", type="FLOAT", domain="POINT")
    hips_z = landmarks["hips"].z
    chest_z = landmarks["chest"].z
    head_y = landmarks["head"].y
    for vi, v in enumerate(me.vertices):
        p = bb.b2t(v.co)
        pid = 3  # body
        if p.y > head_y - 0.12 and p.z > chest_z * 0.3:
            if abs(p.x) > 0.06 and p.y > head_y - 0.02:
                pid = 8 if p.x >= 0 else 9  # ear
            elif p.z > landmarks["head"].z - 0.02 and p.y < head_y - 0.05:
                pid = 1  # muzzle-ish
            else:
                pid = 0  # head
        elif p.z < hips_z - 0.08 and abs(p.x) < 0.12:
            pid = 10  # tail
        elif p.y < 0.52:
            if p.z >= 0.02:
                pid = 4 if p.x >= 0 else 5  # fLeg
            else:
                pid = 6 if p.x >= 0 else 7  # hLeg
        elif p.y > 0.65 and p.z > chest_z * 0.5:
            pid = 2  # neck
        part_attr.data[vi].value = float(pid)
    # normals
    me.calc_normals_split() if hasattr(me, "calc_normals_split") else None
    normals = [bb.b2t(v.normal.copy()) for v in me.vertices]
    return obj, normals


def build_armature_fitted(obj, bone_defs):
    arm_data = bpy.data.armatures.new("cat_armature_data")
    arm_obj = bpy.data.objects.new("cat_armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = {}
    bones_json = {}
    for name, parent, pos_three in bone_defs:
        eb = arm_data.edit_bones.new(name)
        head_bl = bb.t2b(pos_three)
        eb.head = head_bl
        eb.tail = head_bl + Vector((0.0, 0.0, 0.05))
        eb.roll = 0.0
        if parent and parent in edit_bones:
            eb.parent = edit_bones[parent]
        edit_bones[name] = eb
        bones_json[name] = {
            "parent": parent,
            "pos": [round(pos_three.x, 5), round(pos_three.y, 5), round(pos_three.z, 5)],
        }
    bpy.ops.object.mode_set(mode="OBJECT")

    # Parent + armature mod
    obj.parent = arm_obj
    arm_mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    arm_mod.object = arm_obj

    # Automatic weights via parenting with deform
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        auto_ok = True
    except Exception as e:
        auto_ok = False
        print("[path_b] ARMATURE_AUTO failed:", e)
        # fallback: ensure vertex groups exist empty then heuristic
        for name, _, _ in bone_defs:
            if name not in obj.vertex_groups:
                obj.vertex_groups.new(name=name)

    # Ensure armature modifier exists after parent_set
    has_arm = any(m.type == "ARMATURE" for m in obj.modifiers)
    if not has_arm:
        arm_mod = obj.modifiers.new(name="Armature", type="ARMATURE")
        arm_mod.object = arm_obj

    # If auto weights missing groups, fill with scaled heuristic using fitted bone positions
    needed = [n for n, _, _ in bone_defs]
    missing = [n for n in needed if n not in obj.vertex_groups]
    if missing or not auto_ok:
        print("[path_b] filling heuristic weights; missing", missing)
        # map fitted positions into a simple nearest-bone weight
        bone_pos = {n: p for n, _, p in bone_defs}
        for n in needed:
            if n not in obj.vertex_groups:
                obj.vertex_groups.new(name=n)
        for vi, v in enumerate(obj.data.vertices):
            p = bb.b2t(v.co)
            # nearest 2 bones
            dists = []
            for n, bp in bone_pos.items():
                if n == "root":
                    continue
                d = (p - bp).length
                dists.append((d, n))
            dists.sort()
            d0, n0 = dists[0]
            d1, n1 = dists[1] if len(dists) > 1 else (d0 + 1e-3, n0)
            w0 = 1.0 / max(d0, 1e-4)
            w1 = 1.0 / max(d1, 1e-4)
            s = w0 + w1
            obj.vertex_groups[n0].add([vi], w0 / s, "REPLACE")
            if n1 != n0:
                obj.vertex_groups[n1].add([vi], w1 / s, "REPLACE")

    return arm_obj, bones_json, auto_ok


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bb.clear_scene()
    bpy.ops.import_scene.gltf(filepath=SRC)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = "cat_base"

    # Keep materials; normalize
    normalize_keep_materials(obj)
    has_uv = bool(obj.data.uv_layers)
    n_mats = len(obj.material_slots)
    print(f"[path_b] after normalize: verts={len(obj.data.vertices)} uv={has_uv} mats={n_mats}")

    verts = mesh_three_verts(obj)
    landmarks = estimate_body_landmarks(verts)
    paws, n_low = ground_paws(verts)
    print("[path_b] bbox", landmarks["bbox"])
    print("[path_b] paws", json.dumps(paws, indent=2))
    print("[path_b] ground_low", n_low)

    bone_defs, tail_pts = fit_bone_defs(landmarks, paws)
    # Force L/R symmetry for standing Rest (mirror +X onto -X by averaging magnitudes)
    def symmetrize_defs(defs):
        by = {n: (par, pos) for n, par, pos in defs}
        pairs = [
            ("earL", "earR"), ("shoulderL", "shoulderR"), ("elbowL", "elbowR"),
            ("fpawL", "fpawR"), ("hipL", "hipR"), ("kneeL", "kneeR"), ("hpawL", "hpawR"),
        ]
        for a, b in pairs:
            if a not in by or b not in by:
                continue
            pa, pb = by[a][1], by[b][1]
            ax = 0.5 * (abs(pa.x) + abs(pb.x))
            ay = 0.5 * (pa.y + pb.y)
            az = 0.5 * (pa.z + pb.z)
            by[a] = (by[a][0], Vector((ax, ay, az)))
            by[b] = (by[b][0], Vector((-ax, ay, az)))
        # midline bones: force x=0
        for mid in ("root", "hips", "spine", "chest", "neck", "head") + tuple(f"tail{i}" for i in range(6)):
            if mid in by:
                par, pos = by[mid]
                by[mid] = (par, Vector((0.0, pos.y, pos.z)))
        return [(n, by[n][0], by[n][1]) for n, _, _ in defs]
    bone_defs = symmetrize_defs(bone_defs)
    # Also symmetrize paw report for meta
    for L, R in (("fpawL", "fpawR"), ("hpawL", "hpawR")):
        if paws.get(L) and paws.get(R) and paws[L].get("pos") and paws[R].get("pos"):
            pl, pr = paws[L]["pos"], paws[R]["pos"]
            ax = 0.5 * (abs(pl[0]) + abs(pr[0]))
            ay = 0.5 * (pl[1] + pr[1])
            az = 0.5 * (pl[2] + pr[2])
            paws[L]["pos"] = [ax, ay, az]
            paws[R]["pos"] = [-ax, ay, az]
            paws[L]["symmetrized"] = True
            paws[R]["symmetrized"] = True
    obj, normals = tag_parts_keep_uv(obj, landmarks, paws)
    arm_obj, bones_json, auto_ok = build_armature_fitted(obj, bone_defs)

    # Shape keys using build_base (may be mis-scaled but OK for validation)
    try:
        bb.add_shape_keys(obj)
        sk_ok = True
    except Exception as e:
        print("[path_b] shapekeys failed", e)
        sk_ok = False

    anchors = bb.compute_face_anchors(obj, arm_obj, normals)
    arm_obj["faceAnchors"] = json.dumps(anchors)

    meta_payload = {
        "bones": bones_json,
        "anchors": anchors,
        "parts": [
            {"id": pid, "name": bb.PART_NAMES[pid], "rect": list(bb.PART_RECTS[pid])}
            for pid in range(len(bb.PART_NAMES))
        ],
        "intake": "innerscene_path_b_light_no_remesh_fit_bones_sym",
        "auto_weights": auto_ok,
        "shape_keys": sk_ok,
        "uv_preserved": has_uv,
        "materials": n_mats,
        "landmarks": {
            k: ([round(v.x, 4), round(v.y, 4), round(v.z, 4)] if hasattr(v, "x") else v)
            for k, v in landmarks.items() if k != "bbox"
        },
        "bbox": landmarks["bbox"],
        "paws": paws,
        "ground_low_count": n_low,
    }
    bones_path = OUT_DIR / "bones.json"
    with open(bones_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, ensure_ascii=False, indent=2)

    # Export — preserve materials
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    arm_obj.select_set(True)
    for o in bpy.context.scene.objects:
        if o.name.startswith("anchor_"):
            o.select_set(True)
    glb_path = OUT_DIR / "cat_base.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_attributes=True,
        export_morph=True,
        export_morph_normal=False,
        export_skins=True,
        export_all_influences=False,
        export_animations=False,
        export_extras=True,
    )

    # NOTE: intentionally do NOT copy to assets/
    meta = {
        "src": SRC,
        "out_glb": str(glb_path),
        "verts": len(obj.data.vertices),
        "tris": len(obj.data.polygons),
        "uv_preserved": has_uv,
        "materials": n_mats,
        "auto_weights": auto_ok,
        "shape_keys": sk_ok,
        "bbox": landmarks["bbox"],
        "paws": paws,
        "bone_count": len(bones_json),
        "assets_copied": False,
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("[path_b] DONE", json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
