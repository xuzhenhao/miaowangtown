#!/usr/bin/env python3
"""Remap Innerscene Path B UVs into production PART_RECTS atlas WITHOUT changing topology.
Preserves _PART, ShapeKeys, Armature weights, faceAnchors.
"""
import json
import math
import struct
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, "/workspace/miaowangtown/prototype/tools/blender")
import build_base as bb

ROOT = Path("/workspace/miaowangtown")
SRC = ROOT / "docs/validation/innerscene_miemie_v1/cat_base.glb"
BONES = ROOT / "docs/validation/innerscene_miemie_v1/bones.json"
OUT_GLB = ROOT / "docs/validation/innerscene_miemie_v1/cat_base.glb"


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for arm in list(bpy.data.armatures):
        bpy.data.armatures.remove(arm)


def remap_uv(obj: bpy.types.Object):
    me = obj.data
    if "_PART" not in me.attributes:
        raise RuntimeError("missing _PART")
    part_attr = me.attributes["_PART"]
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    # Ensure we edit via bmesh for loop UVs
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")

    # vertex normals in three-space
    normals = []
    for v in bm.verts:
        normals.append(bb.b2t(v.normal.copy()).normalized())

    for f in bm.faces:
        # majority part of face verts
        pids = [int(round(part_attr.data[v.index].value)) for v in f.verts]
        pid = max(set(pids), key=pids.count)
        pid = max(0, min(10, pid))
        rx, ry, rw, rh = bb.PART_RECTS[pid]
        pad = 2.5
        transpose = pid == 10
        raw = []
        for v in f.verts:
            p = bb.b2t(v.co.copy())
            n = normals[v.index]
            s, t = bb.compute_part_uv(pid, p, n)
            raw.append((s, t))
        s_vals = [st[0] for st in raw]
        spans_seam = (max(s_vals) - min(s_vals)) > 0.55
        for loop, (s, t) in zip(f.loops, raw):
            s_adj = min(1.0, s + (1.0 if (spans_seam and s < 0.35) else 0.0))
            a = t if transpose else s_adj
            b = s_adj if transpose else t
            px = rx + pad + a * (rw - 2.0 * pad)
            py = ry + pad + b * (rh - 2.0 * pad)
            u = bb.clamp(px / bb.ATLAS_SIZE, 0.001, 0.999)
            v_uv = bb.clamp(1.0 - py / bb.ATLAS_SIZE, 0.001, 0.999)
            loop[uv_layer].uv = (u, v_uv)

    bm.to_mesh(me)
    bm.free()
    me.update()


def main():
    clear()
    bpy.ops.import_scene.gltf(filepath=str(SRC))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        try:
            bpy.ops.object.join()
        except Exception as e:
            print("[remap] join skip", e)
    obj = bpy.context.active_object
    obj.name = "cat_base"
    arm = arms[0] if arms else None

    bones = json.loads(BONES.read_text(encoding="utf-8"))
    face_anchors = json.dumps(bones.get("anchors", {}))
    obj["faceAnchors"] = face_anchors
    if arm:
        arm["faceAnchors"] = face_anchors

    # single material
    mat = bpy.data.materials.new(name="miemie_coat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.66, 0.49, 0.34, 1.0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    remap_uv(obj)
    print(f"[remap] verts={len(obj.data.vertices)} polys={len(obj.data.polygons)} sk={bool(obj.data.shape_keys)}")

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    if arm:
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

    # patch extras
    buf = bytearray(OUT_GLB.read_bytes())
    json_len = struct.unpack_from("<I", buf, 12)[0]
    json_start = 20
    gltf = json.loads(bytes(buf[json_start:json_start + json_len]))
    for m in gltf.get("meshes", []):
        extras = m.setdefault("extras", {})
        extras["targetNames"] = ["headRound", "weight", "earSize", "tailFluff", "cheekFluff", "muzzleSize"]
        extras["faceAnchors"] = face_anchors
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
    OUT_GLB.write_bytes(new_buf)
    print("[remap] prims", [len(m.get("primitives", [])) for m in gltf.get("meshes", [])])
    print("[remap] DONE", OUT_GLB, "bytes", OUT_GLB.stat().st_size)


if __name__ == "__main__":
    main()
