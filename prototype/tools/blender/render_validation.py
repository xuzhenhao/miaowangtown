#!/usr/bin/env python3
"""Render Stage-1 clay 4-views, Hunyuan multiview set, and run skin-weight audits."""
import json
import math
import os
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Euler

# Reuse coordinate helpers from build_base by exec'ing key bits
SCRIPT_DIR = Path(__file__).resolve().parent
PROTO = SCRIPT_DIR.parent.parent
REPO = PROTO.parent
sys.path.insert(0, str(SCRIPT_DIR))

OUT_VAL = REPO / "docs" / "validation"
OUT_HV = REPO / "docs" / "hunyuan_multiview"
OUT_VAL.mkdir(parents=True, exist_ok=True)
OUT_HV.mkdir(parents=True, exist_ok=True)

GLB = PROTO / "public" / "base" / "cat_base.glb"
COAT = PROTO / "public" / "pets" / "mimi_coat.png"
MIMI = PROTO / "public" / "pets" / "mimi.json"


def t2b(v):
    return Vector((v.x, -v.z, v.y))


def b2t(v):
    return Vector((v.x, v.z, -v.y))


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_cat():
    clear()
    bpy.ops.import_scene.gltf(filepath=str(GLB))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    mesh = meshes[0]
    mesh.name = "cat_base"
    # Apply shape keys for mimi look
    shape = {"headRound": 0.55, "weight": 0.36, "earSize": 0.45, "tailFluff": 0.38, "cheekFluff": 0.62, "muzzleSize": 0.52}
    if MIMI.exists():
        shape.update(json.loads(MIMI.read_text()).get("shape", {}))
    if mesh.data.shape_keys:
        for key, val in shape.items():
            kb = mesh.data.shape_keys.key_blocks.get(key)
            if kb:
                kb.value = float(val)
    return mesh, arms[0] if arms else None


def setup_studio_lights(clay=True):
    scene = bpy.context.scene
    # Prefer EEVEE for headless speed; fall back to Cycles without denoising
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        try:
            scene.render.engine = "BLENDER_EEVEE"
        except Exception:
            scene.render.engine = "CYCLES"
            scene.cycles.samples = 32
            scene.cycles.use_denoising = False
            try:
                scene.cycles.device = "CPU"
            except Exception:
                pass
    # world
    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.82, 0.84, 0.86, 1.0) if clay else (0.92, 0.93, 0.94, 1.0)
    bg.inputs[1].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs[0])

    def add_area(name, loc, energy, size, color=(1, 1, 1)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        L = bpy.context.active_object
        L.name = name
        L.data.energy = energy
        L.data.size = size
        L.data.color = color
        return L

    key = add_area("Key", (1.6, -1.8, 2.2), 250, 1.4)
    key.rotation_euler = Euler((math.radians(55), 0, math.radians(35)), "XYZ")
    fill = add_area("Fill", (-1.8, -1.2, 1.6), 90, 2.0, (0.85, 0.9, 1.0))
    fill.rotation_euler = Euler((math.radians(50), 0, math.radians(-40)), "XYZ")
    rim = add_area("Rim", (0.2, 2.0, 1.8), 120, 1.2, (1.0, 0.95, 0.9))
    rim.rotation_euler = Euler((math.radians(-40), 0, math.radians(180)), "XYZ")


def clay_material(obj):
    mat = bpy.data.materials.new("Clay")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.78, 0.76, 0.72, 1)
    bsdf.inputs["Roughness"].default_value = 0.55
    # mild cavity via AO if available
    try:
        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.inputs["Distance"].default_value = 0.04
        mix = nt.nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs["Fac"].default_value = 0.35
        mix.inputs["Color1"].default_value = (0.78, 0.76, 0.72, 1)
        nt.links.new(ao.outputs["Color"], mix.inputs["Color2"])
        nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    except Exception:
        pass
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def coat_material(obj):
    mat = bpy.data.materials.new("MimiCoat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.62
    tex = nt.nodes.new("ShaderNodeTexImage")
    if COAT.exists():
        img = bpy.data.images.load(str(COAT))
        tex.image = img
        # glTF UV is already on UVMap; Blender import keeps it
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.66, 0.49, 0.34, 1)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def setup_camera(azimuth_deg, elevation_deg=6.0, distance=3.8, ortho_scale=1.75, perspective=False):
    """glTF 导入后：Blender Z-up，鼻尖朝 -Y，高度为 +Z。"""
    target = Vector((0.0, 0.05, 0.62))  # 胸肩中心，保证头顶与四掌同框
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    # az=0 从 -Y（正脸）看过来
    loc = Vector((
        target.x + distance * math.cos(el) * math.sin(az),
        target.y - distance * math.cos(el) * math.cos(az),
        target.z + distance * math.sin(el),
    ))
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.data.clip_start = 0.05
    cam.data.clip_end = 20.0
    if perspective:
        cam.data.type = "PERSP"
        cam.data.lens = 70
    else:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho_scale
    direction = target - loc
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render_to(path: Path, size=1024):
    scene = bpy.context.scene
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    bpy.ops.render.render(write_still=True)
    print(f"[render] wrote {path}")


def audit_weights(mesh_obj):
    """UV-seam weight mismatch / upper-leg shear / belly midline leakage."""
    mesh = mesh_obj.data
    # Build bone weight maps
    vg_index = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
    weights = []
    for v in mesh.vertices:
        wmap = {}
        for g in v.groups:
            wmap[vg_index[g.group]] = g.weight
        weights.append(wmap)

    # Spatial buckets for seam check
    from collections import defaultdict
    buckets = defaultdict(list)
    for i, v in enumerate(mesh.vertices):
        p = b2t(v.co)
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

    # Upper-leg shear: verts above elbow/knee axis receiving lower-limb weight
    shear = 0
    for i, v in enumerate(mesh.vertices):
        p = b2t(v.co)
        w = weights[i]
        # front: elbow at y=0.30; verts y>0.32 should not have significant fpaw
        if p.y > 0.32 and abs(p.z - 0.30) < 0.20 and abs(p.x) > 0.08:
            fpaw = w.get("fpawL", 0) + w.get("fpawR", 0)
            if fpaw > 0.15:
                shear += 1
        # hind: knee at y=0.33; verts y>0.35 should not have significant hpaw
        if p.y > 0.35 and p.z < -0.05 and abs(p.x) > 0.08:
            hpaw = w.get("hpawL", 0) + w.get("hpawR", 0)
            if hpaw > 0.15:
                shear += 1

    belly_leak = 0
    for i, v in enumerate(mesh.vertices):
        p = b2t(v.co)
        # 腹底正中线：|x|<=0.05, 肚皮下表面
        if abs(p.x) <= 0.05 and 0.22 < p.y < 0.38 and abs(p.z) < 0.22:
            limb = sum(w for k, w in weights[i].items() if any(s in k for s in ("shoulder", "elbow", "fpaw", "hip", "knee", "hpaw")))
            if limb > 0.08:
                belly_leak += 1

    report = {
        "verts": len(mesh.vertices),
        "tris": len(mesh.polygons),
        "unique_positions": len(buckets),
        "uv_seam_weight_mismatches": seam_mismatch,
        "upper_leg_shear": shear,
        "belly_midline_leakage": belly_leak,
    }
    print("[audit]", json.dumps(report, indent=2))
    (OUT_VAL / "stage1_skin_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def collage(paths, out_path, labels=None, cols=2):
    from PIL import Image, ImageDraw, ImageFont
    imgs = [Image.open(p).convert("RGB") for p in paths]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    pad = 8
    label_h = 36
    sheet = Image.new("RGB", (cols * w + (cols + 1) * pad, rows * (h + label_h) + (rows + 1) * pad), (32, 34, 38))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        x = pad + c * (w + pad)
        y = pad + r * (h + label_h + pad)
        lab = labels[i] if labels else Path(paths[i]).stem
        draw.text((x + 8, y + 6), lab, fill=(240, 240, 240), font=font)
        sheet.paste(im, (x, y + label_h))
    sheet.save(out_path)
    print(f"[collage] {out_path}")


def main():
    mesh, arm = import_cat()
    report = audit_weights(mesh)

    # --- Stage 1 clay 4-views ---
    setup_studio_lights(clay=True)
    clay_material(mesh)
    views = [
        ("front", 0),
        ("left", -90),
        ("right", 90),
        ("three_quarter", -40),
    ]
    clay_paths = []
    for name, az in views:
        # remove old cams
        for o in list(bpy.data.objects):
            if o.type == "CAMERA":
                bpy.data.objects.remove(o, do_unlink=True)
        setup_camera(az, elevation_deg=5, distance=4.0, ortho_scale=1.85)
        p = OUT_VAL / f"_tmp_clay_{name}.png"
        render_to(p, 896)
        clay_paths.append(p)
    collage(
        clay_paths,
        OUT_VAL / "stage1_clay_anatomy_4views.png",
        labels=["Front (正视)", "Left (左侧视)", "Right (右侧视)", "45° (四分之三)"],
        cols=2,
    )
    for p in clay_paths:
        p.unlink(missing_ok=True)

    # --- Hunyuan multiview (coat textured) ---
    # Re-import clean so shape keys + coat apply fresh
    mesh, arm = import_cat()
    setup_studio_lights(clay=False)
    coat_material(mesh)
    # transparent-ish light gray bg for Hunyuan
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.90, 0.91, 0.92, 1)

    hv_defs = [
        ("01_front", 0, "混元「上传正图」"),
        ("02_left", -90, "混元「上传左图」(展示猫自身右侧)"),
        ("03_right", 90, "混元「上传右图」(展示猫自身左侧)"),
        ("04_back", 180, "混元「上传背图」"),
        ("05_left45", -45, "混元「上传左45°图」"),
        ("06_right45", 45, "混元「上传右45°图」"),
    ]
    hv_paths = []
    hv_labels = []
    for name, az, label in hv_defs:
        for o in list(bpy.data.objects):
            if o.type == "CAMERA":
                bpy.data.objects.remove(o, do_unlink=True)
        setup_camera(az, elevation_deg=4, distance=4.2, ortho_scale=1.80)
        p = OUT_HV / f"{name}.png"
        render_to(p, 1024)
        hv_paths.append(p)
        hv_labels.append(f"{name}\n{label}")

    collage(hv_paths, OUT_VAL / "miemie_hunyuan_multiview_sheet.png", labels=hv_labels, cols=3)

    # Simple in-engine stand-in: coat front+side collage labeled anatomical
    collage(
        [hv_paths[0], hv_paths[1], hv_paths[2], hv_paths[4]],
        OUT_VAL / "miemie_anatomical_in_engine.png",
        labels=["Front textured", "Left", "Right", "Left45°"],
        cols=2,
    )

    print("[done] audit", report)


if __name__ == "__main__":
    main()
