#!/usr/bin/env python3
"""Innerscene Standing cat: audit + UV-preserving clean export (~8k-12k tris)."""
import json
import math
import os
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

SRC = "/workspace/miaowangtown/reference/open_cat_bases/innerscene_standing_cat/cat-original.glb"
OUT_DIR = Path("/workspace/miaowangtown/reference/open_cat_bases/innerscene_standing_cat")
VAL_DIR = Path("/workspace/miaowangtown/docs/validation/innerscene_intake")
CLEAN_GLB = OUT_DIR / "cat_clean.glb"
AUDIT_JSON = VAL_DIR / "innerscene_standing_cat_audit.json"
META_JSON = VAL_DIR / "clean_export_meta.json"
TARGET_TRIS = 10000


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mesh_stats(obj):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    n_tris = len(bm.faces)
    bm.free()
    verts = [v.co.copy() for v in me.vertices]
    if not verts:
        return {}
    min_v = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    max_v = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    size = max_v - min_v
    has_uv = bool(me.uv_layers)
    mats = []
    for slot in obj.material_slots:
        m = slot.material
        if not m:
            continue
        info = {"name": m.name, "images": []}
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    img = n.image
                    info["images"].append({
                        "name": img.name,
                        "size": list(img.size),
                        "colorspace": getattr(img.colorspace_settings, "name", None),
                    })
        mats.append(info)
    eps = size.z * 0.02 + 1e-4
    low = [v for v in verts if v.z <= min_v.z + eps]
    cx = 0.5 * (min_v.x + max_v.x)
    cy = 0.5 * (min_v.y + max_v.y)
    clusters = {"FL": 0, "FR": 0, "HL": 0, "HR": 0}
    for v in low:
        # glTF yup -> Blender: forward typically -Y
        fore = "F" if v.y < cy else "H"
        key = fore + ("L" if v.x > cx else "R")
        clusters[key] = clusters.get(key, 0) + 1
    # paw contact centroids for four quadrants
    paw_centroids = {}
    for key, xsign, yfore in (
        ("FL", 1, True), ("FR", -1, True), ("HL", 1, False), ("HR", -1, False)
    ):
        pts = []
        for v in low:
            if (v.x - cx) * xsign <= 0:
                continue
            is_fore = v.y < cy
            if is_fore != yfore:
                continue
            pts.append(v)
        if pts:
            paw_centroids[key] = {
                "n": len(pts),
                "mean": [
                    round(sum(p.x for p in pts) / len(pts), 5),
                    round(sum(p.y for p in pts) / len(pts), 5),
                    round(sum(p.z for p in pts) / len(pts), 5),
                ],
            }
        else:
            paw_centroids[key] = None
    return {
        "name": obj.name,
        "verts": len(me.vertices),
        "tris_approx": n_tris,
        "has_uv": has_uv,
        "uv_layers": [uv.name for uv in me.uv_layers],
        "materials": mats,
        "bbox_min": [round(min_v.x, 5), round(min_v.y, 5), round(min_v.z, 5)],
        "bbox_max": [round(max_v.x, 5), round(max_v.y, 5), round(max_v.z, 5)],
        "bbox_size": [round(size.x, 5), round(size.y, 5), round(size.z, 5)],
        "min_z": round(min_v.z, 5),
        "ground_eps": round(eps, 5),
        "ground_vert_count": len(low),
        "ground_clusters_guess": clusters,
        "paw_centroids": paw_centroids,
        "ground_mean_xy": [
            round(sum(v.x for v in low) / max(1, len(low)), 5),
            round(sum(v.y for v in low) / max(1, len(low)), 5),
        ] if low else None,
    }


def asymmetry_score(obj, n_samples=800):
    import random
    me = obj.data
    verts = [v.co.copy() for v in me.vertices]
    if len(verts) < 10:
        return None
    min_v = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    max_v = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    cx = 0.5 * (min_v.x + max_v.x)
    right = [v for v in verts if v.x >= cx]
    left = [v for v in verts if v.x < cx]
    if not right or not left:
        return None
    rng = random.Random(42)
    sample = rng.sample(right, min(n_samples, len(right)))
    dists = []
    for v in sample:
        target = Vector((2 * cx - v.x, v.y, v.z))
        best = 1e9
        for u in rng.sample(left, min(400, len(left))):
            d = (u - target).length
            if d < best:
                best = d
        dists.append(best)
    dists.sort()
    def pct(p):
        i = min(len(dists) - 1, int(p / 100.0 * (len(dists) - 1)))
        return dists[i]
    span = max(max_v.x - min_v.x, max_v.y - min_v.y, max_v.z - min_v.z)
    return {
        "median": round(pct(50), 5),
        "p90": round(pct(90), 5),
        "max": round(dists[-1], 5),
        "median_norm": round(pct(50) / span, 5),
        "p90_norm": round(pct(90) / span, 5),
        "samples": len(dists),
        "bbox_span_max": round(span, 5),
        "note": "Blender space; high p90 suggests mid-stride / asymmetric Rest",
    }


def main():
    VAL_DIR.mkdir(parents=True, exist_ok=True)
    clear()
    bpy.ops.import_scene.gltf(filepath=SRC)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert meshes, "no mesh"
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = "innerscene_standing_cat"

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    raw = mesh_stats(obj)
    asym = asymmetry_score(obj)
    clusters = raw.get("ground_clusters_guess") or {}
    four_paws = all((clusters.get(k, 0) or 0) > 0 for k in ("FL", "FR", "HL", "HR"))
    # Rest gate heuristic: 4-paw contact + low relative asymmetry
    p90_norm = (asym or {}).get("p90_norm")
    rest_likely = bool(four_paws and p90_norm is not None and p90_norm < 0.08)

    audit = {
        "source": SRC,
        "license": "CC0 1.0",
        "page": "https://www.innerscene.com/tools/library/3d-parts/standing-cat-cda42538",
        "raw": raw,
        "asymmetry": asym,
        "armatures": [o.name for o in bpy.context.scene.objects if o.type == "ARMATURE"],
        "four_paw_contact": four_paws,
        "rest_gate_heuristic": {
            "four_paws": four_paws,
            "p90_norm": p90_norm,
            "threshold_p90_norm": 0.08,
            "likely_symmetric_standing": rest_likely,
        },
        "pose_guess": "alert standing (Innerscene description); confirm via 4-paw clusters + asymmetry",
        "facing_note": f"bbox size XYZ={raw.get('bbox_size')}; after glTF import Z=up.",
    }

    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
    print("AUDIT", json.dumps(audit, ensure_ascii=False, indent=2))

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    n_tris = len(obj.data.polygons)
    ratio = 1.0
    if n_tris > TARGET_TRIS:
        ratio = max(0.02, TARGET_TRIS / float(n_tris))
        dec = obj.modifiers.new(name="DecimateClean", type="DECIMATE")
        dec.decimate_type = "COLLAPSE"
        dec.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=dec.name)

    min_z = min(v.co.z for v in obj.data.vertices)
    for v in obj.data.vertices:
        v.co.z -= min_z

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=str(CLEAN_GLB),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_skins=False,
        export_animations=False,
        export_morph=False,
    )

    clean_stats = mesh_stats(obj)
    meta = {
        "source": SRC,
        "clean_glb": str(CLEAN_GLB),
        "target_tris": TARGET_TRIS,
        "decimate_ratio": ratio,
        "pre_decimate_tris": n_tris,
        "clean": clean_stats,
        "materials_preserved": True,
        "uv_preserved_intent": True,
        "notes": "Collapse decimate; no Voxel Remesh; feet z=0 in Blender before yup export",
    }
    with open(META_JSON, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("CLEAN META", json.dumps(meta, ensure_ascii=False, indent=2))
    print("WROTE", CLEAN_GLB, CLEAN_GLB.stat().st_size)


if __name__ == "__main__":
    main()
