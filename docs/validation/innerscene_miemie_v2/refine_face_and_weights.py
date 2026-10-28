#!/usr/bin/env python3
"""
Innerscene miemie v2: resample faceAnchors from actual head/muzzle mesh,
clean upper-leg shear + belly midline limb leakage. Isolation only.
"""
from __future__ import annotations

import json
import math
import struct
import sys
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, "/workspace/miaowangtown/prototype/tools/blender")
import build_base as bb

ROOT = Path("/workspace/miaowangtown")
OUT = ROOT / "docs/validation/innerscene_miemie_v2"
SRC_GLB = OUT / "cat_base_src.glb"
SRC_BONES = OUT / "bones_src.json"
OUT_GLB = OUT / "cat_base.glb"
OUT_BONES = OUT / "bones.json"
AUDIT_BEFORE = OUT / "skin_audit_before.json"
AUDIT_AFTER = OUT / "skin_audit_after.json"
ANCHORS_META = OUT / "face_anchors_meta.json"


def clear():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.armatures):
        for ob in list(coll):
            coll.remove(ob, do_unlink=True) if hasattr(coll, "remove") else None
    # safer clear
    bpy.ops.wm.read_factory_settings(use_empty=True)


def audit_weights(mesh_obj) -> dict:
    mesh = mesh_obj.data
    vg_index = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
    weights = []
    for v in mesh.vertices:
        wmap = {}
        for g in v.groups:
            wmap[vg_index[g.group]] = g.weight
        weights.append(wmap)

    buckets = defaultdict(list)
    for i, v in enumerate(mesh.vertices):
        p = bb.b2t(v.co)
        key = (round(p.x, 4), round(p.y, 4), round(p.z, 4))
        buckets[key].append(i)

    seam_mismatch = 0
    for key, idxs in buckets.items():
        if len(idxs) < 2:
            continue
        base = weights[idxs[0]]
        for j in idxs[1:]:
            w2 = weights[j]
            keys = set(base) | set(w2)
            diff = sum(abs(base.get(k, 0) - w2.get(k, 0)) for k in keys)
            if diff > 1e-3:
                seam_mismatch += 1
                break

    shear = 0
    for i, v in enumerate(mesh.vertices):
        p = bb.b2t(v.co)
        w = weights[i]
        if p.y > 0.32 and abs(p.z - 0.30) < 0.20 and abs(p.x) > 0.08:
            fpaw = w.get("fpawL", 0) + w.get("fpawR", 0)
            if fpaw > 0.15:
                shear += 1
        if p.y > 0.35 and p.z < -0.05 and abs(p.x) > 0.08:
            hpaw = w.get("hpawL", 0) + w.get("hpawR", 0)
            if hpaw > 0.15:
                shear += 1

    belly_leak = 0
    for i, v in enumerate(mesh.vertices):
        p = bb.b2t(v.co)
        if abs(p.x) <= 0.05 and 0.22 < p.y < 0.38 and abs(p.z) < 0.22:
            limb = sum(
                w
                for k, w in weights[i].items()
                if any(s in k for s in ("shoulder", "elbow", "fpaw", "hip", "knee", "hpaw"))
            )
            if limb > 0.08:
                belly_leak += 1

    return {
        "verts": len(mesh.vertices),
        "tris": len(mesh.polygons),
        "unique_positions": len(buckets),
        "uv_seam_weight_mismatches": seam_mismatch,
        "upper_leg_shear": shear,
        "belly_midline_leakage": belly_leak,
        "vertex_groups": [vg.name for vg in mesh_obj.vertex_groups],
    }


def get_weight_map(obj) -> list[dict[str, float]]:
    vg_index = {vg.index: vg.name for vg in obj.vertex_groups}
    out = []
    for v in obj.data.vertices:
        wmap = {vg_index[g.group]: g.weight for g in v.groups}
        out.append(wmap)
    return out


def set_weight_map(obj, weights: list[dict[str, float]]):
    # clear all groups
    for vg in obj.vertex_groups:
        vg.add(list(range(len(obj.data.vertices))), 0.0, "REPLACE")
    # write
    name_to_vg = {vg.name: vg for vg in obj.vertex_groups}
    for vi, wmap in enumerate(weights):
        # normalize
        s = sum(max(0.0, w) for w in wmap.values())
        if s <= 1e-8:
            # fallback spine
            if "spine" in name_to_vg:
                name_to_vg["spine"].add([vi], 1.0, "REPLACE")
            continue
        for name, w in wmap.items():
            if name not in name_to_vg or w <= 0:
                continue
            name_to_vg[name].add([vi], w / s, "REPLACE")


def clean_weights(obj) -> dict:
    """Reduce shear (paw influence on upper legs) and belly midline limb leak."""
    weights = get_weight_map(obj)
    before = audit_weights(obj)
    shear_fixed = 0
    belly_fixed = 0

    LIMB_TOKENS = ("shoulder", "elbow", "fpaw", "hip", "knee", "hpaw")
    BODY_PREFER = ("spine", "hips", "chest", "root")

    for i, v in enumerate(obj.data.vertices):
        p = bb.b2t(v.co)
        w = dict(weights[i])

        # --- upper front leg shear: paw weight too high on thigh ---
        if p.y > 0.32 and abs(p.z - 0.30) < 0.20 and abs(p.x) > 0.08:
            side = "L" if p.x >= 0 else "R"
            fpaw_k = f"fpaw{side}"
            fpaw = w.get(fpaw_k, 0.0)
            if fpaw > 0.15:
                # move paw weight into elbow/shoulder
                give = fpaw
                w[fpaw_k] = 0.0
                elbow_k = f"elbow{side}"
                sh_k = f"shoulder{side}"
                w[elbow_k] = w.get(elbow_k, 0.0) + give * 0.55
                w[sh_k] = w.get(sh_k, 0.0) + give * 0.45
                shear_fixed += 1

        # --- upper hind leg shear ---
        if p.y > 0.35 and p.z < -0.05 and abs(p.x) > 0.08:
            side = "L" if p.x >= 0 else "R"
            hpaw_k = f"hpaw{side}"
            hpaw = w.get(hpaw_k, 0.0)
            if hpaw > 0.15:
                give = hpaw
                w[hpaw_k] = 0.0
                knee_k = f"knee{side}"
                hip_k = f"hip{side}"
                w[knee_k] = w.get(knee_k, 0.0) + give * 0.55
                w[hip_k] = w.get(hip_k, 0.0) + give * 0.45
                shear_fixed += 1

        # --- belly midline limb leak ---
        if abs(p.x) <= 0.05 and 0.22 < p.y < 0.38 and abs(p.z) < 0.22:
            limb = {k: wv for k, wv in w.items() if any(t in k for t in LIMB_TOKENS)}
            limb_sum = sum(limb.values())
            if limb_sum > 0.08:
                for k in limb:
                    w[k] = 0.0
                # distribute to body chain
                body_present = [k for k in BODY_PREFER if k in w or True]
                # prefer existing body weights; else equal
                body_w = {k: w.get(k, 0.0) for k in BODY_PREFER}
                body_s = sum(body_w.values())
                if body_s < 1e-6:
                    for k in ("spine", "hips", "chest"):
                        w[k] = w.get(k, 0.0) + limb_sum / 3.0
                else:
                    for k, bw in body_w.items():
                        w[k] = w.get(k, 0.0) + limb_sum * (bw / body_s)
                belly_fixed += 1

        # soft clamp: paw bones should not affect high-y verts
        if p.y > 0.28:
            for side in ("L", "R"):
                for paw in (f"fpaw{side}", f"hpaw{side}"):
                    if w.get(paw, 0) > 0.05 and (
                        (paw.startswith("fpaw") and p.y > 0.30)
                        or (paw.startswith("hpaw") and p.y > 0.32)
                    ):
                        extra = w[paw]
                        w[paw] = 0.0
                        mid = f"elbow{side}" if paw.startswith("fpaw") else f"knee{side}"
                        w[mid] = w.get(mid, 0.0) + extra

        weights[i] = w

    # sync UV-seam duplicates to identical weights (average)
    buckets = defaultdict(list)
    for i, v in enumerate(obj.data.vertices):
        p = bb.b2t(v.co)
        key = (round(p.x, 4), round(p.y, 4), round(p.z, 4))
        buckets[key].append(i)
    seam_synced = 0
    for idxs in buckets.values():
        if len(idxs) < 2:
            continue
        # average
        keys = set()
        for i in idxs:
            keys |= set(weights[i])
        avg = {}
        for k in keys:
            avg[k] = sum(weights[i].get(k, 0.0) for i in idxs) / len(idxs)
        for i in idxs:
            weights[i] = dict(avg)
        seam_synced += 1

    set_weight_map(obj, weights)
    after = audit_weights(obj)
    return {
        "shear_fixed_ops": shear_fixed,
        "belly_fixed_ops": belly_fixed,
        "seam_buckets_synced": seam_synced,
        "before": before,
        "after": after,
    }


def resample_face_anchors(obj, arm_obj) -> tuple[dict, dict]:
    """Adaptive anchors from head/muzzle _PART surface (Three-space)."""
    me = obj.data
    part_attr = me.attributes.get("_PART")
    if part_attr is None:
        raise RuntimeError("missing _PART")

    verts_t = [bb.b2t(v.co.copy()) for v in me.vertices]
    norms_t = [bb.b2t(v.normal.copy()).normalized() for v in me.vertices]

    head = [(i, verts_t[i], norms_t[i]) for i in range(len(verts_t)) if int(round(part_attr.data[i].value)) == 0]
    muzzle = [(i, verts_t[i], norms_t[i]) for i in range(len(verts_t)) if int(round(part_attr.data[i].value)) == 1]
    if len(head) < 20:
        raise RuntimeError(f"too few head verts: {len(head)}")
    if len(muzzle) < 10:
        # fall back: use front-lower head as muzzle
        hy = [p.y for _, p, _ in head]
        hz = [p.z for _, p, _ in head]
        y_cut = min(hy) + 0.35 * (max(hy) - min(hy))
        z_cut = min(hz) + 0.55 * (max(hz) - min(hz))
        muzzle = [(i, p, n) for i, p, n in head if p.y <= y_cut and p.z >= z_cut]

    hy = [p.y for _, p, _ in head]
    hx = [p.x for _, p, _ in head]
    hz = [p.z for _, p, _ in head]
    head_ymin, head_ymax = min(hy), max(hy)
    head_zmax = max(hz)
    half_w = 0.5 * (max(hx) - min(hx))

    # Eyes: mid-upper front of head, L/R of midline, facing forward
    eye_y = head_ymin + 0.60 * (head_ymax - head_ymin)
    eye_x_abs = max(0.055, min(0.12, 0.35 * half_w))

    def pick_eye(sign: float):
        scored = []
        for i, p, n in head:
            if p.x * sign < 0.025:
                continue
            if n.z < 0.12:
                continue
            score = (
                -3.0 * abs(p.y - eye_y)
                - 2.0 * abs(abs(p.x) - eye_x_abs)
                + 4.0 * (p.z / max(head_zmax, 1e-3))
                + 1.5 * n.z
                - 0.4 * abs(n.y)
            )
            scored.append((score, i, p, n))
        if not scored:
            # fallback nearest
            target = Vector((sign * eye_x_abs, eye_y, head_zmax))
            best = min(head, key=lambda t: (t[1] - target).length_squared)
            return best[0], best[1], best[2]
        scored.sort(reverse=True)
        _, i, p, n = scored[0]
        return i, p, n

    iL, pL, nL = pick_eye(1.0)
    iR, pR, nR = pick_eye(-1.0)
    # symmetrize Y/Z and |X|
    eye_y_s = 0.5 * (pL.y + pR.y)
    eye_z_s = 0.5 * (pL.z + pR.z)
    eye_x_s = 0.5 * (abs(pL.x) + abs(pR.x))
    # lift slightly along normal so decals sit on surface
    def lift(p, n, amt=0.004):
        return p + n.normalized() * amt

    # re-pick vertex nearest to symmetrized target
    def nearest_on_parts(target, parts_list, allowed_n_z=None):
        best_i, best_d, best_p, best_n = 0, 1e9, target, Vector((0, 0, 1))
        for i, p, n in parts_list:
            if allowed_n_z is not None and n.z < allowed_n_z:
                continue
            d = (p - target).length_squared
            if d < best_d:
                best_i, best_d, best_p, best_n = i, d, p, n
        return best_i, best_p, best_n

    tL = Vector((eye_x_s, eye_y_s, eye_z_s))
    tR = Vector((-eye_x_s, eye_y_s, eye_z_s))
    iL, pL, nL = nearest_on_parts(tL, head, 0.05)
    iR, pR, nR = nearest_on_parts(tR, head, 0.05)
    # use symmetrized ideal positions with surface Z from nearest verts
    posL = Vector((eye_x_s, eye_y_s, 0.5 * (pL.z + pR.z)))
    posR = Vector((-eye_x_s, eye_y_s, 0.5 * (pL.z + pR.z)))
    # ideal forward-ish normals
    nL_ideal = Vector((0.28, 0.04, 0.96)).normalized()
    nR_ideal = Vector((-0.28, 0.04, 0.96)).normalized()
    # blend with actual
    nL_use = (0.55 * nL_ideal + 0.45 * nL.normalized()).normalized()
    nR_use = (0.55 * nR_ideal + 0.45 * nR.normalized()).normalized()
    posL = lift(posL, nL_use, 0.005)
    posR = lift(posR, nR_use, 0.005)

    # Mouth: front center of muzzle
    my = [p.y for _, p, _ in muzzle]
    mz = [p.z for _, p, _ in muzzle]
    mouth_y = min(my) + 0.42 * (max(my) - min(my))
    mouth_z = max(mz)
    tM = Vector((0.0, mouth_y, mouth_z))
    iM, pM, nM = nearest_on_parts(tM, muzzle, None)
    nM_ideal = Vector((0.0, 0.02, 0.9998)).normalized()
    nM_use = (0.6 * nM_ideal + 0.4 * nM.normalized()).normalized()
    posM = lift(Vector((0.0, pM.y, max(pM.z, mouth_z * 0.98))), nM_use, 0.005)

    # Whiskers: sides of muzzle
    whisker_y = min(my) + 0.38 * (max(my) - min(my))
    whisker_x = max(0.08, min(0.16, 0.55 * half_w))

    def pick_whisker(sign):
        t = Vector((sign * whisker_x, whisker_y, max(mz) - 0.01))
        i, p, n = nearest_on_parts(t, muzzle if muzzle else head, None)
        ideal = Vector((sign * 0.64, -0.04, 0.767)).normalized()
        n_use = (0.5 * ideal + 0.5 * n.normalized()).normalized()
        pos = lift(Vector((sign * abs(p.x), p.y, p.z)), n_use, 0.004)
        # re-bind vertex
        i2, _, _ = nearest_on_parts(pos, muzzle if muzzle else head, None)
        return i2, pos, n_use

    iWL, posWL, nWL = pick_whisker(1.0)
    iWR, posWR, nWR = pick_whisker(-1.0)

    # remove old anchor empties
    for o in list(bpy.context.scene.objects):
        if o.name.startswith("anchor_"):
            bpy.data.objects.remove(o, do_unlink=True)

    anchors = {}
    specs = [
        ("eyeL", iL, posL, nL_use),
        ("eyeR", iR, posR, nR_use),
        ("mouth", iM, posM, nM_use),
        ("whiskerL", iWL, posWL, nWL),
        ("whiskerR", iWR, posWR, nWR),
    ]
    for name, vi, pos, nrm in specs:
        empty = bpy.data.objects.new(f"anchor_{name}", None)
        empty.empty_display_type = "SINGLE_ARROW"
        empty.empty_display_size = 0.05
        empty.location = bb.t2b(pos)
        empty.parent = arm_obj
        empty["anchorName"] = name
        empty["normal"] = [round(nrm.x, 5), round(nrm.y, 5), round(nrm.z, 5)]
        empty["vertexIndex"] = int(vi)
        bpy.context.collection.objects.link(empty)
        anchors[name] = {
            "vertexIndex": int(vi),
            "pos": [round(pos.x, 5), round(pos.y, 5), round(pos.z, 5)],
            "normal": [round(nrm.x, 5), round(nrm.y, 5), round(nrm.z, 5)],
        }

    fa = json.dumps(anchors)
    obj["faceAnchors"] = fa
    obj.data["faceAnchors"] = fa
    arm_obj["faceAnchors"] = fa

    meta = {
        "head_bbox": {
            "ymin": round(head_ymin, 4),
            "ymax": round(head_ymax, 4),
            "zmax": round(head_zmax, 4),
            "half_w": round(half_w, 4),
        },
        "muzzle_n": len(muzzle),
        "head_n": len(head),
        "eye_y": round(eye_y_s, 4),
        "eye_x_abs": round(eye_x_s, 4),
        "mouth_y": round(posM.y, 4),
        "mouth_z": round(posM.z, 4),
        "old_vs_new_note": "v1 used production template eye y=0.895 z~0.79; Innerscene head ymax~0.87 zmax~0.66",
        "anchors": anchors,
    }
    return anchors, meta


def inject_glb_extras(glb_path: Path, anchors: dict, target_names: list[str]):
    buf = bytearray(glb_path.read_bytes())
    json_len = struct.unpack_from("<I", buf, 12)[0]
    json_start = 20
    json_bytes = bytes(buf[json_start : json_start + json_len])
    gltf = json.loads(json_bytes)
    fa = json.dumps(anchors)
    for m in gltf.get("meshes", []):
        extras = m.setdefault("extras", {})
        extras["faceAnchors"] = fa
        extras["targetNames"] = target_names
    for n in gltf.get("nodes", []):
        if n.get("mesh") is not None or "faceAnchors" in (n.get("extras") or {}):
            extras = n.setdefault("extras", {})
            extras["faceAnchors"] = fa
    # also set on armature-like nodes
    new_json = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    pad_n = (4 - (len(new_json) % 4)) % 4
    new_json_padded = new_json + (b" " * pad_n)
    old_bin_start = 20 + json_len
    old_bin_start_aligned = old_bin_start + ((4 - (json_len % 4)) % 4)
    bin_rest = bytes(buf[old_bin_start_aligned:])
    new_buf = bytearray()
    new_buf += buf[:12]
    new_buf += struct.pack("<I", len(new_json_padded))
    new_buf += b"JSON"
    new_buf += new_json_padded
    new_buf += bin_rest
    struct.pack_into("<I", new_buf, 8, len(new_buf))
    glb_path.write_bytes(new_buf)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    clear()
    bpy.ops.import_scene.gltf(filepath=str(SRC_GLB))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    assert meshes and arms, "need mesh+armature"
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = "cat_base"
    arm = arms[0]

    before = audit_weights(obj)
    AUDIT_BEFORE.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[v2] skin BEFORE", json.dumps(before, indent=2))

    clean_report = clean_weights(obj)
    AUDIT_AFTER.write_text(json.dumps(clean_report["after"], ensure_ascii=False, indent=2), encoding="utf-8")
    print("[v2] skin AFTER", json.dumps(clean_report["after"], indent=2))
    print("[v2] clean ops", {k: clean_report[k] for k in ("shear_fixed_ops", "belly_fixed_ops", "seam_buckets_synced")})

    # iterate clean once more if still high
    if clean_report["after"]["upper_leg_shear"] > 5 or clean_report["after"]["belly_midline_leakage"] > 10:
        clean_report2 = clean_weights(obj)
        AUDIT_AFTER.write_text(json.dumps(clean_report2["after"], ensure_ascii=False, indent=2), encoding="utf-8")
        print("[v2] skin AFTER2", json.dumps(clean_report2["after"], indent=2))
        clean_report = clean_report2

    anchors, anchor_meta = resample_face_anchors(obj, arm)
    ANCHORS_META.write_text(json.dumps(anchor_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[v2] anchors", json.dumps(anchors, indent=2))

    # export
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    arm.select_set(True)
    for o in bpy.context.scene.objects:
        if o.name.startswith("anchor_"):
            o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_attributes=True,
        export_morph=True,
        export_morph_normal=False,
        export_skins=True,
        export_all_influences=False,
        export_animations=False,
        export_extras=True,
    )

    bones = json.loads(SRC_BONES.read_text(encoding="utf-8"))
    bones["anchors"] = anchors
    bones["intake"] = "innerscene_miemie_v2_face_anchors_weight_clean"
    bones["skin_audit_before"] = before
    bones["skin_audit_after"] = clean_report["after"]
    bones["weight_clean"] = {
        "shear_fixed_ops": clean_report["shear_fixed_ops"],
        "belly_fixed_ops": clean_report["belly_fixed_ops"],
        "seam_buckets_synced": clean_report["seam_buckets_synced"],
    }
    OUT_BONES.write_text(json.dumps(bones, ensure_ascii=False, indent=2), encoding="utf-8")

    sk_names = []
    if obj.data.shape_keys:
        sk_names = [kb.name for kb in obj.data.shape_keys.key_blocks if kb.name != "Basis"]
    if not sk_names:
        sk_names = ["headRound", "weight", "earSize", "tailFluff", "cheekFluff", "muzzleSize"]
    inject_glb_extras(OUT_GLB, anchors, sk_names)

    # final audit reload
    clear()
    bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
    obj2 = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    final = audit_weights(obj2)
    (OUT / "skin_audit_final.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[v2] FINAL audit", json.dumps(final, indent=2))
    print("[v2] DONE", OUT_GLB, OUT_GLB.stat().st_size)


if __name__ == "__main__":
    main()
