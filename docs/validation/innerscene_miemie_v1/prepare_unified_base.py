#!/usr/bin/env python3
"""
Prepare Innerscene Path B for miemie v1 validation:
- load out_b cat_base.glb
- collapse multi-materials → single Principled (coat atlas target)
- keep _PART / ShapeKeys / Armature / UV / faceAnchors extras
- export single-primitive GLB + copy bones.json
Does NOT touch prototype/public/base or assets/.
"""
import json
import shutil
import sys
from pathlib import Path

import bpy

ROOT = Path("/workspace/miaowangtown")
SRC_GLB = ROOT / "docs/validation/innerscene_intake/out_b/cat_base.glb"
SRC_BONES = ROOT / "docs/validation/innerscene_intake/out_b/bones.json"
OUT = ROOT / "docs/validation/innerscene_miemie_v1"
OUT.mkdir(parents=True, exist_ok=True)

# clear
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
for arm in list(bpy.data.armatures):
    bpy.data.armatures.remove(arm)

bpy.ops.import_scene.gltf(filepath=str(SRC_GLB))
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
print(f"[prepare] imported meshes={len(meshes)} arms={len(arms)}")

# join meshes if multiple
bpy.ops.object.select_all(action="DESELECT")
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.active_object
obj.name = "cat_base"

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

# ensure faceAnchors extras survive — copy from armature if present
arm = arms[0] if arms else None
face_anchors = None
if arm and "faceAnchors" in arm:
    face_anchors = arm["faceAnchors"]
elif "faceAnchors" in obj:
    face_anchors = obj["faceAnchors"]
# also try mesh extras via bones.json
bones = json.loads(SRC_BONES.read_text(encoding="utf-8"))
if not face_anchors and "anchors" in bones:
    face_anchors = json.dumps(bones["anchors"])
if face_anchors:
    obj["faceAnchors"] = face_anchors
    if arm:
        arm["faceAnchors"] = face_anchors
    # Blender glTF exports mesh extras from obj data custom props sometimes via
    # assigning to mesh too
    obj.data["faceAnchors"] = face_anchors

# shape key names check
sk_names = []
if obj.data.shape_keys:
    sk_names = [kb.name for kb in obj.data.shape_keys.key_blocks]
print(f"[prepare] verts={len(obj.data.vertices)} polys={len(obj.data.polygons)} sk={sk_names}")
print(f"[prepare] has _PART={' _PART' in obj.data.attributes or '_PART' in obj.data.attributes}")
has_part = "_PART" in obj.data.attributes
print(f"[prepare] _PART={has_part} uv_layers={len(obj.data.uv_layers)} mats={len(obj.material_slots)}")

# Export selection: mesh + armature + anchors
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
if arm:
    arm.select_set(True)
for o in bpy.context.scene.objects:
    if o.name.startswith("anchor_"):
        o.select_set(True)

out_glb = OUT / "cat_base.glb"
bpy.ops.export_scene.gltf(
    filepath=str(out_glb),
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

shutil.copy2(SRC_BONES, OUT / "bones.json")

# Inject targetNames + faceAnchors into exported GLB mesh extras if missing
# (Blender sometimes drops them)
import struct
buf = bytearray(out_glb.read_bytes())
json_len = struct.unpack_from("<I", buf, 12)[0]
json_start = 20
json_bytes = bytes(buf[json_start:json_start + json_len])
# pad was included in chunk
pad = (4 - (json_len % 4)) % 4
gltf = json.loads(json_bytes)
changed = False
for m in gltf.get("meshes", []):
    extras = m.setdefault("extras", {})
    if "targetNames" not in extras:
        extras["targetNames"] = ["headRound", "weight", "earSize", "tailFluff", "cheekFluff", "muzzleSize"]
        changed = True
    if face_anchors and "faceAnchors" not in extras:
        extras["faceAnchors"] = face_anchors if isinstance(face_anchors, str) else json.dumps(face_anchors)
        changed = True
    # ensure only useful
print("[prepare] prims", [len(m.get("primitives", [])) for m in gltf.get("meshes", [])])
print("[prepare] materials", len(gltf.get("materials", [])))
if changed or True:
    new_json = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    # realign with padding
    pad_n = (4 - (len(new_json) % 4)) % 4
    new_json_padded = new_json + (b" " * pad_n)
    # find bin chunk
    bin_chunk_start = json_start + json_len + pad
    # After JSON chunk there is: pad already counted in chunk length for glTF —
    # GLB layout: 12 header + 8 chunk0hdr + json_len (+implicit?); chunk length includes only json, then pad to 4, then chunk1
    # Actually: chunk0 length = json_len (unpadded content length), then padding bytes, then chunk1 header
    old_bin_start = 20 + json_len
    # skip padding to 4-byte boundary
    old_bin_start_aligned = old_bin_start + ((4 - (json_len % 4)) % 4)
    bin_rest = bytes(buf[old_bin_start_aligned:])
    new_buf = bytearray()
    new_buf += buf[:12]  # magic/version/placeholder length
    # json chunk
    new_buf += struct.pack("<I", len(new_json_padded))
    new_buf += b"JSON"
    new_buf += new_json_padded
    new_buf += bin_rest
    total = len(new_buf)
    struct.pack_into("<I", new_buf, 8, total)
    out_glb.write_bytes(new_buf)

meta = {
    "src": str(SRC_GLB),
    "out_glb": str(out_glb),
    "verts": len(obj.data.vertices),
    "polys": len(obj.data.polygons),
    "shape_keys": sk_names,
    "has_part": has_part,
    "materials": 1,
    "face_anchors_injected": bool(face_anchors),
}
(OUT / "prepare_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
print("[prepare] DONE", json.dumps(meta, ensure_ascii=False, indent=2))
