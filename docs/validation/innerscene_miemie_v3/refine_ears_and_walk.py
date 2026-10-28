#!/usr/bin/env python3
"""
Innerscene miemie v3: fix ear bone height/orientation + ear weights + earSize morph,
and soften torso junction weights to reduce walk side-view sawtooth.
Isolation only — never touches prototype/public/base permanently.
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
OUT = ROOT / "docs/validation/innerscene_miemie_v3"
SRC_GLB = OUT / "cat_base_src.glb"
SRC_BONES = OUT / "bones_src.json"
OUT_GLB = OUT / "cat_base.glb"
OUT_BONES = OUT / "bones.json"
EAR_META = OUT / "ear_fix_meta.json"
WALK_META = OUT / "walk_polish_meta.json"
AUDIT_BEFORE = OUT / "skin_audit_before.json"
AUDIT_AFTER = OUT / "skin_audit_after.json"


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for a in list(bpy.data.armatures):
        bpy.data.armatures.remove(a)


def audit_weights(mesh_obj) -> dict:
    mesh = mesh_obj.data
    vg_index = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
    weights = []
    for v in mesh.vertices:
        wmap = {vg_index[g.group]: g.weight for g in v.groups}
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
            if w.get("fpawL", 0) + w.get("fpawR", 0) > 0.15:
                shear += 1
        if p.y > 0.35 and p.z < -0.05 and abs(p.x) > 0.08:
            if w.get("hpawL", 0) + w.get("hpawR", 0) > 0.15:
                shear += 1

    belly_leak = 0
    for i, v in enumerate(mesh.vertices):
        p = bb.b2t(v.co)
        if abs(p.x) <= 0.05 and 0.22 < p.y < 0.38 and abs(p.z) < 0.22:
            limb = sum(
                wv
                for k, wv in weights[i].items()
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
        out.append({vg_index[g.group]: g.weight for g in v.groups})
    return out


def set_weight_map(obj, weights: list[dict[str, float]]):
    for vg in obj.vertex_groups:
        vg.add(list(range(len(obj.data.vertices))), 0.0, "REPLACE")
    name_to_vg = {vg.name: vg for vg in obj.vertex_groups}
    for vi, wmap in enumerate(weights):
        s = sum(max(0.0, w) for w in wmap.values())
        if s <= 1e-8:
            if "spine" in name_to_vg:
                name_to_vg["spine"].add([vi], 1.0, "REPLACE")
            continue
        for name, w in wmap.items():
            if name not in name_to_vg or w <= 0:
                continue
            name_to_vg[name].add([vi], w / s, "REPLACE")


def sync_seam_weights(obj, weights):
    buckets = defaultdict(list)
    for i, v in enumerate(obj.data.vertices):
        p = bb.b2t(v.co)
        key = (round(p.x, 4), round(p.y, 4), round(p.z, 4))
        buckets[key].append(i)
    synced = 0
    for idxs in buckets.values():
        if len(idxs) < 2:
            continue
        keys = set()
        for i in idxs:
            keys |= set(weights[i])
        avg = {k: sum(weights[i].get(k, 0.0) for i in idxs) / len(idxs) for k in keys}
        for i in idxs:
            weights[i] = dict(avg)
        synced += 1
    return synced


def measure_ear_geometry(obj) -> dict:
    me = obj.data
    part = me.attributes.get("_PART")
    assert part is not None
    ears = {"L": [], "R": []}
    for i, v in enumerate(me.vertices):
        pid = int(round(part.data[i].value))
        p = bb.b2t(v.co)
        if pid == 8:
            ears["L"].append((i, p))
        elif pid == 9:
            ears["R"].append((i, p))

    out = {}
    for side, pts in ears.items():
        assert len(pts) >= 10, f"ear{side} too few: {len(pts)}"
        tip = max(pts, key=lambda t: t[1].y)[1]
        # base = lower third centroid (attachment toward head)
        by_y = sorted(pts, key=lambda t: t[1].y)
        base_pool = by_y[: max(3, len(by_y) // 3)]
        base = sum((p for _, p in base_pool), Vector((0, 0, 0))) / len(base_pool)
        cen = sum((p for _, p in pts), Vector((0, 0, 0))) / len(pts)
        # bone head slightly above base toward tip (~35% up ear)
        bone = base.lerp(tip, 0.28)
        # symmetrize will happen later
        out[side] = {
            "n": len(pts),
            "tip": tip,
            "base": base,
            "cen": cen,
            "bone": bone,
            "indices": [i for i, _ in pts],
            "y_span": [round(by_y[0][1].y, 4), round(by_y[-1][1].y, 4)],
            "z_span": [
                round(min(p.z for _, p in pts), 4),
                round(max(p.z for _, p in pts), 4),
            ],
        }
    # symmetrize L/R bone |x|,y,z
    bL, bR = out["L"]["bone"], out["R"]["bone"]
    ax = 0.5 * (abs(bL.x) + abs(bR.x))
    ay = 0.5 * (bL.y + bR.y)
    az = 0.5 * (bL.z + bR.z)
    out["L"]["bone_sym"] = Vector((ax, ay, az))
    out["R"]["bone_sym"] = Vector((-ax, ay, az))
    tL, tR = out["L"]["tip"], out["R"]["tip"]
    tx = 0.5 * (abs(tL.x) + abs(tR.x))
    ty = 0.5 * (tL.y + tR.y)
    tz = 0.5 * (tL.z + tR.z)
    out["L"]["tip_sym"] = Vector((tx, ty, tz))
    out["R"]["tip_sym"] = Vector((-tx, ty, tz))
    return out


def fix_ear_bones(arm, ear_geo) -> dict:
    """Move earL/earR edit bones to ear base; tip as tail direction."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    old = {}
    for side, name in (("L", "earL"), ("R", "earR")):
        bone = eb.get(name)
        assert bone is not None, name
        old[name] = {
            "head": [round(c, 5) for c in bb.b2t(bone.head.copy())],
            "tail": [round(c, 5) for c in bb.b2t(bone.tail.copy())],
        }
        head_t = ear_geo[side]["bone_sym"]
        tip_t = ear_geo[side]["tip_sym"]
        # short bone along ear up-axis
        direction = (tip_t - head_t).normalized()
        length = max(0.045, min(0.09, (tip_t - head_t).length * 0.55))
        bone.head = bb.t2b(head_t)
        bone.tail = bb.t2b(head_t + direction * length)
        # parent stays head
        if eb.get("head"):
            bone.parent = eb["head"]
    bpy.ops.object.mode_set(mode="OBJECT")
    new = {}
    bpy.ops.object.mode_set(mode="EDIT")
    for name in ("earL", "earR"):
        bone = eb[name]
        new[name] = {
            "head": [round(c, 5) for c in bb.b2t(bone.head.copy())],
            "tail": [round(c, 5) for c in bb.b2t(bone.tail.copy())],
        }
    bpy.ops.object.mode_set(mode="OBJECT")
    return {"old": old, "new": new}


def bind_ear_weights(obj, ear_geo) -> dict:
    """Assign part8/9 verts primarily to earL/earR with soft falloff to head."""
    weights = get_weight_map(obj)
    me = obj.data
    part = me.attributes["_PART"]
    touched = 0
    for side, ear_name in (("L", "earL"), ("R", "earR")):
        tip = ear_geo[side]["tip_sym"]
        base = ear_geo[side]["bone_sym"]
        axis = (tip - base).normalized()
        height = max(1e-4, (tip - base).length)
        for i in ear_geo[side]["indices"]:
            p = bb.b2t(me.vertices[i].co)
            # projection along ear axis from base
            rel = p - base
            t = max(0.0, min(1.0, rel.dot(axis) / height))
            # near tip: almost pure ear; near base: blend to head
            ear_w = 0.35 + 0.65 * (t ** 0.85)
            head_w = 1.0 - ear_w
            w = dict(weights[i])
            # strip other influences lightly on ear verts
            for k in list(w.keys()):
                if k not in (ear_name, "head", "neck"):
                    w[k] = w.get(k, 0.0) * 0.15
            w[ear_name] = ear_w
            w["head"] = w.get("head", 0.0) * 0.2 + head_w
            weights[i] = w
            touched += 1

        # also soft-pull nearby head verts (part0) that sit in ear vicinity
        for i, v in enumerate(me.vertices):
            pid = int(round(part.data[i].value))
            if pid != 0:
                continue
            p = bb.b2t(v.co)
            if (side == "L" and p.x < 0.03) or (side == "R" and p.x > -0.03):
                continue
            # near ear base band
            if p.y < base.y - 0.02 or p.y > tip.y + 0.02:
                continue
            if abs(p.z - base.z) > 0.12:
                continue
            dist = (p - base).length
            if dist > 0.07:
                continue
            blend = max(0.0, 1.0 - dist / 0.07) * 0.35
            if blend < 0.05:
                continue
            w = dict(weights[i])
            # steal a bit from head toward ear
            take = min(blend, w.get("head", 0.0) * 0.5 + 0.1)
            w["head"] = max(0.0, w.get("head", 0.0) - take * 0.6)
            w[ear_name] = w.get(ear_name, 0.0) + take
            weights[i] = w
            touched += 1

    seam = sync_seam_weights(obj, weights)
    set_weight_map(obj, weights)
    # count ear influence
    ear_infl = 0
    for w in weights:
        if w.get("earL", 0) + w.get("earR", 0) > 0.1:
            ear_infl += 1
    return {"touched_ops": touched, "seam_synced": seam, "ear_influence_verts": ear_infl}


def rebuild_ear_size_shape_key(obj, ear_geo) -> dict:
    """Rewrite earSize morph to scale actual ear parts (8/9), not tail y>0.98."""
    me = obj.data
    assert me.shape_keys is not None
    basis = me.shape_keys.key_blocks["Basis"]
    ear_kb = me.shape_keys.key_blocks.get("earSize")
    if ear_kb is None:
        ear_kb = obj.shape_key_add(name="earSize", from_mix=False)

    # reset to basis first
    for i in range(len(me.vertices)):
        ear_kb.data[i].co = basis.data[i].co.copy()

    part = me.attributes["_PART"]
    moved = 0
    max_disp = 0.0
    max_at = None
    for side, ear_name in (("L", "earL"), ("R", "earR")):
        tip = ear_geo[side]["tip_sym"]
        base = ear_geo[side]["bone_sym"]
        axis = (tip - base).normalized()
        height = max(1e-4, (tip - base).length)
        side_sign = 1.0 if side == "L" else -1.0
        for i, v in enumerate(me.vertices):
            pid = int(round(part.data[i].value))
            if pid not in (8, 9, 0):
                continue
            if pid == 8 and side != "L":
                continue
            if pid == 9 and side != "R":
                continue
            if pid == 0:
                # only tiny halo near ear base
                p = bb.b2t(basis.data[i].co)
                if (side == "L" and p.x < 0.04) or (side == "R" and p.x > -0.04):
                    continue
                if (p - base).length > 0.055:
                    continue
            p = bb.b2t(basis.data[i].co)
            rel = p - base
            t = max(0.0, min(1.2, rel.dot(axis) / height))
            if pid == 0:
                w = 0.25 * max(0.0, 1.0 - (p - base).length / 0.055)
            else:
                w = max(0.0, min(1.0, (t / 1.05) ** 0.9))
            if w < 0.02:
                continue
            # enlarge away from base + slight outward/up
            radial = rel - axis * rel.dot(axis)
            delta_t = (
                radial * 0.28 * w
                + axis * (0.10 * height) * w
                + Vector((side_sign * 0.012 * w, 0.018 * w, 0.004 * w))
            )
            new_p = p + delta_t
            ear_kb.data[i].co = bb.t2b(new_p)
            d = delta_t.length
            if d > max_disp:
                max_disp = d
                max_at = [round(c, 4) for c in new_p]
            moved += 1

    return {"moved_verts": moved, "max_disp": round(max_disp, 5), "max_at": max_at}


def polish_torso_weights(obj) -> dict:
    """
    Soften hard torso junctions that cause walk side-view sawtooth:
    - body/side verts near shoulder: blend shoulder <-> chest more gently
    - mid-body: reduce hip/shoulder extremes, favor spine/chest mix
    - keep paw shear / belly audits green
    """
    weights = get_weight_map(obj)
    me = obj.data
    part = me.attributes.get("_PART")
    ops = {
        "shoulder_chest_blend": 0,
        "hip_spine_blend": 0,
        "body_chain_smooth": 0,
        "limb_body_guard": 0,
    }

    for i, v in enumerate(me.vertices):
        p = bb.b2t(v.co)
        pid = int(round(part.data[i].value)) if part else -1
        w = dict(weights[i])
        changed = False

        # --- front shoulder / chest crease (body + upper fleg roots) ---
        if pid in (3, 4, 5) and 0.42 < p.y < 0.62 and 0.15 < p.z < 0.50 and abs(p.x) > 0.04:
            side = "L" if p.x >= 0 else "R"
            sh = f"shoulder{side}"
            sh_w = w.get(sh, 0.0)
            chest_w = w.get("chest", 0.0)
            spine_w = w.get("spine", 0.0)
            # if shoulder dominates body flank, pull toward chest
            if sh_w > 0.35 and pid == 3:
                give = (sh_w - 0.28) * 0.65
                w[sh] = sh_w - give
                w["chest"] = chest_w + give * 0.7
                w["spine"] = spine_w + give * 0.3
                ops["shoulder_chest_blend"] += 1
                changed = True
            # upper leg root: don't let chest steal too much, but soften binary
            if pid in (4, 5) and p.y > 0.48 and sh_w > 0.55 and chest_w < 0.12:
                move = 0.12
                w[sh] = sh_w - move
                w["chest"] = chest_w + move
                ops["shoulder_chest_blend"] += 1
                changed = True

        # --- hind hip / spine crease ---
        if pid in (3, 6, 7) and 0.42 < p.y < 0.62 and -0.45 < p.z < -0.05 and abs(p.x) > 0.04:
            side = "L" if p.x >= 0 else "R"
            hip = f"hip{side}"
            hip_w = w.get(hip, 0.0)
            if hip_w > 0.35 and pid == 3:
                give = (hip_w - 0.28) * 0.65
                w[hip] = hip_w - give
                w["hips"] = w.get("hips", 0.0) + give * 0.55
                w["spine"] = w.get("spine", 0.0) + give * 0.45
                ops["hip_spine_blend"] += 1
                changed = True

        # --- mid-body chain smooth: avoid single-bone spikes on torso ---
        if pid == 3 and 0.45 < p.y < 0.68 and abs(p.z) < 0.40:
            chain = ("hips", "spine", "chest")
            cw = {k: w.get(k, 0.0) for k in chain}
            s = sum(cw.values())
            if s > 0.35:
                # dilate toward neighbors: pull max down a bit
                mx_k = max(cw, key=cw.get)
                if cw[mx_k] / max(s, 1e-6) > 0.72:
                    extra = (cw[mx_k] - 0.55 * s)
                    if extra > 0.04:
                        w[mx_k] = cw[mx_k] - extra
                        others = [k for k in chain if k != mx_k]
                        for k in others:
                            w[k] = w.get(k, 0.0) + extra / len(others)
                        ops["body_chain_smooth"] += 1
                        changed = True

        # --- guard: body verts shouldn't carry strong elbow/knee/paw ---
        if pid == 3:
            limb_far = 0.0
            for k in list(w.keys()):
                if any(t in k for t in ("elbow", "knee", "fpaw", "hpaw")):
                    limb_far += w.get(k, 0.0)
            if limb_far > 0.12:
                for k in list(w.keys()):
                    if any(t in k for t in ("elbow", "knee", "fpaw", "hpaw")):
                        give = w.get(k, 0.0)
                        w[k] = 0.0
                        # dump to nearest body / upper limb root
                        if "fpaw" in k or "elbow" in k:
                            side = "L" if "L" in k else "R"
                            w[f"shoulder{side}"] = w.get(f"shoulder{side}", 0.0) + give * 0.4
                            w["chest"] = w.get("chest", 0.0) + give * 0.6
                        else:
                            side = "L" if "L" in k else "R"
                            w[f"hip{side}"] = w.get(f"hip{side}", 0.0) + give * 0.4
                            w["hips"] = w.get("hips", 0.0) + give * 0.6
                ops["limb_body_guard"] += 1
                changed = True

        # re-apply shear/belly safety (same thresholds as audit)
        if p.y > 0.32 and abs(p.z - 0.30) < 0.20 and abs(p.x) > 0.08:
            side = "L" if p.x >= 0 else "R"
            fpaw_k = f"fpaw{side}"
            if w.get(fpaw_k, 0) > 0.15:
                give = w[fpaw_k]
                w[fpaw_k] = 0.0
                w[f"elbow{side}"] = w.get(f"elbow{side}", 0.0) + give * 0.55
                w[f"shoulder{side}"] = w.get(f"shoulder{side}", 0.0) + give * 0.45
                changed = True
        if p.y > 0.35 and p.z < -0.05 and abs(p.x) > 0.08:
            side = "L" if p.x >= 0 else "R"
            hpaw_k = f"hpaw{side}"
            if w.get(hpaw_k, 0) > 0.15:
                give = w[hpaw_k]
                w[hpaw_k] = 0.0
                w[f"knee{side}"] = w.get(f"knee{side}", 0.0) + give * 0.55
                w[f"hip{side}"] = w.get(f"hip{side}", 0.0) + give * 0.45
                changed = True
        if abs(p.x) <= 0.05 and 0.22 < p.y < 0.38 and abs(p.z) < 0.22:
            limb = {k: wv for k, wv in w.items() if any(t in k for t in ("shoulder", "elbow", "fpaw", "hip", "knee", "hpaw"))}
            limb_sum = sum(limb.values())
            if limb_sum > 0.08:
                for k in limb:
                    w[k] = 0.0
                body_w = {k: w.get(k, 0.0) for k in ("spine", "hips", "chest")}
                body_s = sum(body_w.values())
                if body_s < 1e-6:
                    for k in ("spine", "hips", "chest"):
                        w[k] = w.get(k, 0.0) + limb_sum / 3.0
                else:
                    for k, bw in body_w.items():
                        w[k] = w.get(k, 0.0) + limb_sum * (bw / body_s)
                changed = True

        if changed:
            weights[i] = w

    seam = sync_seam_weights(obj, weights)
    set_weight_map(obj, weights)
    ops["seam_synced"] = seam
    return ops


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
        # also update ear node translation if present as separate nodes — skinned bones come from skin inverse binds; blender export handles that
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


def vec_round(v: Vector):
    return [round(float(v.x), 5), round(float(v.y), 5), round(float(v.z), 5)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    clear()
    bpy.ops.import_scene.gltf(filepath=str(SRC_GLB))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and len(o.data.vertices) > 1000]
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    assert meshes and arms, "need mesh+armature"
    # drop leftover icosphere etc
    for o in list(bpy.context.scene.objects):
        if o.type == "MESH" and o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    obj = meshes[0]
    obj.name = "cat_base"
    arm = arms[0]
    arm.name = "cat_armature"

    before = audit_weights(obj)
    AUDIT_BEFORE.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[v3] skin BEFORE", json.dumps(before))

    ear_geo = measure_ear_geometry(obj)
    print(
        "[v3] earL tip",
        vec_round(ear_geo["L"]["tip"]),
        "bone",
        vec_round(ear_geo["L"]["bone_sym"]),
        "n",
        ear_geo["L"]["n"],
    )
    print(
        "[v3] earR tip",
        vec_round(ear_geo["R"]["tip"]),
        "bone",
        vec_round(ear_geo["R"]["bone_sym"]),
        "n",
        ear_geo["R"]["n"],
    )

    bone_fix = fix_ear_bones(arm, ear_geo)
    print("[v3] ear bones", json.dumps(bone_fix, indent=2))

    ear_bind = bind_ear_weights(obj, ear_geo)
    print("[v3] ear bind", json.dumps(ear_bind))

    ear_sk = rebuild_ear_size_shape_key(obj, ear_geo)
    print("[v3] earSize sk", json.dumps(ear_sk))

    walk_ops = polish_torso_weights(obj)
    print("[v3] walk polish", json.dumps(walk_ops))

    after = audit_weights(obj)
    AUDIT_AFTER.write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[v3] skin AFTER", json.dumps(after))

    # preserve face anchors from source empties / mesh extras
    anchors = None
    if "faceAnchors" in obj:
        try:
            anchors = json.loads(obj["faceAnchors"])
        except Exception:
            anchors = None
    if anchors is None:
        # from bones_src
        bones_src = json.loads(SRC_BONES.read_text(encoding="utf-8"))
        anchors = bones_src.get("anchors")
    assert anchors, "missing faceAnchors"

    # re-write empties if missing
    existing = {o.name for o in bpy.context.scene.objects}
    for name, data in anchors.items():
        ename = f"anchor_{name}"
        if ename in existing:
            continue
        empty = bpy.data.objects.new(ename, None)
        empty.empty_display_type = "SINGLE_ARROW"
        empty.empty_display_size = 0.05
        empty.location = bb.t2b(Vector(data["pos"]))
        empty.parent = arm
        empty["anchorName"] = name
        empty["normal"] = data.get("normal", [0, 0, 1])
        empty["vertexIndex"] = int(data.get("vertexIndex", 0))
        bpy.context.collection.objects.link(empty)

    fa = json.dumps(anchors)
    obj["faceAnchors"] = fa
    obj.data["faceAnchors"] = fa
    arm["faceAnchors"] = fa

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
    # update ear bone positions in bones.json
    for name in ("earL", "earR"):
        bones["bones"][name]["pos"] = bone_fix["new"][name]["head"]
    bones["anchors"] = anchors
    bones["intake"] = "innerscene_miemie_v3_ears_walk_polish"
    bones["skin_audit_before"] = before
    bones["skin_audit_after"] = after
    bones["ear_fix"] = bone_fix
    bones["ear_bind"] = ear_bind
    bones["earSize_rebuild"] = ear_sk
    bones["walk_polish"] = walk_ops
    # update landmarks ears to true tips
    bones.setdefault("landmarks", {})
    bones["landmarks"]["earL"] = vec_round(ear_geo["L"]["tip_sym"])
    bones["landmarks"]["earR"] = vec_round(ear_geo["R"]["tip_sym"])
    OUT_BONES.write_text(json.dumps(bones, ensure_ascii=False, indent=2), encoding="utf-8")

    ear_meta = {
        "root_cause": (
            "Path B top-verts heuristic picked tail (part10 y<=1.25) as ears; "
            "true ears are part8/9 y∈[0.75,0.93]. earSize morph used production y>0.98 threshold → deformed tail."
        ),
        "old_bones": bone_fix["old"],
        "new_bones": bone_fix["new"],
        "earL": {
            "n": ear_geo["L"]["n"],
            "tip": vec_round(ear_geo["L"]["tip"]),
            "tip_sym": vec_round(ear_geo["L"]["tip_sym"]),
            "bone_sym": vec_round(ear_geo["L"]["bone_sym"]),
            "y_span": ear_geo["L"]["y_span"],
            "z_span": ear_geo["L"]["z_span"],
        },
        "earR": {
            "n": ear_geo["R"]["n"],
            "tip": vec_round(ear_geo["R"]["tip"]),
            "tip_sym": vec_round(ear_geo["R"]["tip_sym"]),
            "bone_sym": vec_round(ear_geo["R"]["bone_sym"]),
            "y_span": ear_geo["R"]["y_span"],
            "z_span": ear_geo["R"]["z_span"],
        },
        "ear_bind": ear_bind,
        "earSize_rebuild": ear_sk,
    }
    EAR_META.write_text(json.dumps(ear_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    WALK_META.write_text(
        json.dumps(
            {
                "method": "soften shoulder↔chest / hip↔hips+spine on body flank; smooth mid-body chain spikes; guard body vs elbow/knee/paw",
                "ops": walk_ops,
                "skin_before": before,
                "skin_after": after,
                "note": "Does not change walk.ts amplitude (would affect production). Visual polish via weights only.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    sk_names = [kb.name for kb in obj.data.shape_keys.key_blocks if kb.name != "Basis"]
    inject_glb_extras(OUT_GLB, anchors, sk_names)

    # final audit reload
    clear()
    bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
    obj2 = max(
        (o for o in bpy.context.scene.objects if o.type == "MESH"),
        key=lambda o: len(o.data.vertices),
    )
    final = audit_weights(obj2)
    # verify ear bones
    arm2 = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    bpy.context.view_layer.objects.active = arm2
    bpy.ops.object.mode_set(mode="EDIT")
    ear_verify = {}
    for name in ("earL", "earR", "head"):
        b = arm2.data.edit_bones[name]
        ear_verify[name] = {
            "head": [round(c, 5) for c in bb.b2t(b.head.copy())],
            "tail": [round(c, 5) for c in bb.b2t(b.tail.copy())],
        }
    bpy.ops.object.mode_set(mode="OBJECT")
    # earSize peak
    sk = obj2.data.shape_keys
    basis = sk.key_blocks["Basis"]
    ear_kb = sk.key_blocks["earSize"]
    mx = 0
    at = None
    part = obj2.data.attributes.get("_PART")
    for i in range(len(obj2.data.vertices)):
        d = (ear_kb.data[i].co - basis.data[i].co).length
        if d > mx:
            mx = d
            pid = int(round(part.data[i].value)) if part else -1
            at = {"pos": vec_round(bb.b2t(basis.data[i].co)), "part": pid, "disp": round(mx, 5)}
    final_extra = {
        "audit": final,
        "ear_bones_reimport": ear_verify,
        "earSize_peak": at,
    }
    (OUT / "skin_audit_final.json").write_text(
        json.dumps(final_extra, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("[v3] FINAL", json.dumps(final_extra, indent=2))
    print("[v3] DONE", OUT_GLB, OUT_GLB.stat().st_size)


if __name__ == "__main__":
    main()
