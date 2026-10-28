#!/usr/bin/env python3
"""Render Stage-1 clay 4-views, Hunyuan 8-view multiview set (with 3D eyes/nose/paw-pads), and run skin-weight audits."""
import json
import math
import os
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Euler
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
PROTO = SCRIPT_DIR.parent.parent
REPO = PROTO.parent
sys.path.insert(0, str(SCRIPT_DIR))

OUT_VAL = REPO / "docs" / "validation"
OUT_HV = REPO / "docs" / "hunyuan_multiview"
OUT_VAL.mkdir(parents=True, exist_ok=True)
OUT_HV.mkdir(parents=True, exist_ok=True)

GLB = PROTO / "public" / "base" / "cat_base.glb"
BONES_JSON = PROTO / "public" / "base" / "bones.json"
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
    shape = {
        "headRound": 0.55,
        "weight": 0.36,
        "earSize": 0.45,
        "tailFluff": 0.38,
        "cheekFluff": 0.62,
        "muzzleSize": 0.52,
    }
    if MIMI.exists():
        shape.update(json.loads(MIMI.read_text()).get("shape", {}))
    if mesh.data.shape_keys:
        for key, val in shape.items():
            kb = mesh.data.shape_keys.key_blocks.get(key)
            if kb:
                kb.value = float(val)
    return mesh, arms[0] if arms else None


def evaluated_vertex_three(mesh_obj, vi: int) -> Vector:
    """Return deformed vertex position in Three.js coordinates after ShapeKeys."""
    mesh = mesh_obj.data
    base = Vector(mesh.vertices[vi].co)
    if mesh.shape_keys and mesh.shape_keys.key_blocks:
        basis = mesh.shape_keys.key_blocks[0]
        bco = Vector(basis.data[vi].co)
        delta = Vector((0.0, 0.0, 0.0))
        for kb in mesh.shape_keys.key_blocks[1:]:
            if abs(kb.value) > 1e-6:
                delta += (Vector(kb.data[vi].co) - bco) * kb.value
        base = bco + delta
    return b2t(base)


def make_eye_texture(path: Path, size: int = 256) -> Path:
    """Generate high-res Miemie emerald-green cat eye texture with vertical slit pupil and catchlights."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    cx, cy = size // 2, size // 2
    r_outer = int(size * 0.46)
    r_iris = int(size * 0.40)
    # Eyeliner dark rim
    draw.ellipse((cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer), fill=(27, 17, 11, 255))
    # Outer emerald-olive ring
    draw.ellipse((cx - r_iris, cy - r_iris, cx + r_iris, cy + r_iris), fill=(92, 122, 64, 255))
    # Main emerald-amber iris
    r_mid = int(size * 0.34)
    draw.ellipse((cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid), fill=(143, 179, 105, 255))
    # Lower bright emerald crescent
    r_inner = int(size * 0.27)
    draw.ellipse((cx - r_inner, cy - r_inner + int(size * 0.04), cx + r_inner, cy + r_inner + int(size * 0.04)), fill=(168, 204, 126, 255))
    # Vertical slit pupil
    pw = int(size * 0.13)
    ph = int(size * 0.33)
    draw.ellipse((cx - pw, cy - ph, cx + pw, cy + ph), fill=(18, 24, 16, 255))
    # Main top-left catchlight
    hl1 = int(size * 0.085)
    hx1, hy1 = cx - int(size * 0.13), cy - int(size * 0.14)
    draw.ellipse((hx1 - hl1, hy1 - hl1, hx1 + hl1, hy1 + hl1), fill=(255, 255, 255, 255))
    # Secondary bottom-right catchlight
    hl2 = int(size * 0.04)
    hx2, hy2 = cx + int(size * 0.12), cy + int(size * 0.15)
    draw.ellipse((hx2 - hl2, hy2 - hl2, hx2 + hl2, hy2 + hl2), fill=(255, 255, 255, 235))
    im.save(path)
    return path


def make_Solid_mat(name: str, rgba: tuple[float, float, float, float], roughness: float = 0.45):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def add_face_and_paw_features(mesh_obj):
    """Add 3D eyes, terracotta-pink nose, mouth line, whiskers, and pink paw pads for Hunyuan 8-view reconstruction."""
    anchors = {}
    if BONES_JSON.exists():
        anchors = json.loads(BONES_JSON.read_text()).get("anchors", {})

    eye_tex_path = OUT_VAL / "_tmp_eye_tex.png"
    make_eye_texture(eye_tex_path, 256)

    # Eye material with UV-mapped iris texture on front hemisphere
    eye_mat = bpy.data.materials.new("MimiEyeMat")
    eye_mat.use_nodes = True
    nt = eye_mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.12
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(eye_tex_path))
    tex.extension = "EXTEND"
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    # Map local X,Z of flattened eye disc to 0..1 UV
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    for key, side in [("eyeL", 1.0), ("eyeR", -1.0)]:
        info = anchors.get(key, {})
        vi = info.get("vertexIndex")
        if vi is not None and vi < len(mesh_obj.data.vertices):
            p3 = evaluated_vertex_three(mesh_obj, vi)
        else:
            p3 = Vector((side * 0.108, 0.895, 0.805))
        n3 = Vector(info.get("normal", [side * 0.26, 0.04, 0.96])).normalized()
        center3 = p3 + n3 * 0.008
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=24, radius=0.072, location=t2b(center3))
        eye = bpy.context.active_object
        eye.name = f"Feature_{key}"
        # Orient sphere so its +Z pole points along outward normal in Blender space, then flatten depth
        n_b = t2b(n3).normalized()
        eye.rotation_euler = n_b.to_track_quat("Z", "Y").to_euler()
        eye.scale = Vector((1.0, 0.95, 0.32))
        eye.data.materials.append(eye_mat)
        for poly in eye.data.polygons:
            poly.use_smooth = True

    # Terracotta-pink 3D Nose Leather (#C85A48) + dark mouth line
    m_info = anchors.get("mouth", {})
    m_vi = m_info.get("vertexIndex")
    if m_vi is not None and m_vi < len(mesh_obj.data.vertices):
        mp3 = evaluated_vertex_three(mesh_obj, m_vi)
    else:
        mp3 = Vector((0.0, 0.822, 0.862))

    nose_mat = make_Solid_mat("MimiNoseMat", (0.784, 0.353, 0.282, 1.0), roughness=0.35)
    mouth_line_mat = make_Solid_mat("MimiMouthLineMat", (0.14, 0.09, 0.07, 1.0), roughness=0.6)

    nose_p3 = mp3 + Vector((0.0, 0.022, 0.010))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.036, location=t2b(nose_p3))
    nose = bpy.context.active_object
    nose.name = "Feature_Nose"
    nose.scale = Vector((1.15, 0.65, 0.78))
    nose.data.materials.append(nose_mat)
    for poly in nose.data.polygons:
        poly.use_smooth = True

    # Philtrum & inverted-W mouth arcs
    for side in (-1.0, 1.0):
        arc_p3 = mp3 + Vector((side * 0.024, -0.016, 0.006))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=0.014, location=t2b(arc_p3))
        arc = bpy.context.active_object
        arc.name = f"Feature_MouthArc_{side}"
        arc.scale = Vector((1.6, 0.55, 0.55))
        arc.rotation_euler = Euler((0, math.radians(side * -18), 0), "XYZ")
        arc.data.materials.append(mouth_line_mat)

    # Subtle 3D white whiskers on cheeks
    whisker_mat = make_Solid_mat("MimiWhiskerMat", (0.97, 0.97, 0.97, 1.0), roughness=0.3)
    for side in (-1.0, 1.0):
        for wi, (dy, pitch) in enumerate([(0.008, 4.0), (-0.010, -5.0)]):
            wp3 = Vector((side * 0.175, 0.812 + dy, 0.775 - wi * 0.01))
            bpy.ops.mesh.primitive_cylinder_add(radius=0.0045, depth=0.14, location=t2b(wp3))
            wobj = bpy.context.active_object
            wobj.name = f"Feature_Whisker_{side}_{wi}"
            # Point outward-left/right and slightly forward/down
            dir_3 = Vector((side * 0.92, math.sin(math.radians(pitch)), 0.32)).normalized()
            wobj.rotation_euler = t2b(dir_3).to_track_quat("Z", "Y").to_euler()
            wobj.data.materials.append(whisker_mat)

    # Pink paw pads on the bottom of all 4 paws (clearly visible in 08_bottom.png!)
    pad_mat = make_Solid_mat("MimiPawPadMat", (0.86, 0.55, 0.57, 1.0), roughness=0.5)
    paw_centers = [
        ("fL", 0.14, 0.35),
        ("fR", -0.14, 0.35),
        ("hL", 0.15, -0.21),
        ("hR", -0.15, -0.21),
    ]
    for pname, px, pz in paw_centers:
        # Main metacarpal/metatarsal pad
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=0.026, location=t2b(Vector((px, 0.004, pz - 0.01))))
        mpad = bpy.context.active_object
        mpad.name = f"Feature_PadMain_{pname}"
        mpad.scale = Vector((1.15, 0.95, 0.18))
        mpad.data.materials.append(pad_mat)
        # 4 digital toe beans in front arc
        for ti, ang in enumerate([-0.48, -0.16, 0.16, 0.48]):
            tx = px + math.sin(ang) * 0.036
            tz = pz + 0.028 + math.cos(ang) * 0.016
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=10, radius=0.012, location=t2b(Vector((tx, 0.004, tz))))
            tpad = bpy.context.active_object
            tpad.name = f"Feature_PadToe_{pname}_{ti}"
            tpad.scale = Vector((0.9, 1.1, 0.22))
            tpad.data.materials.append(pad_mat)


def setup_studio_lights(clay=True):
    scene = bpy.context.scene
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
    world = bpy.data.worlds.new("Studio")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.82, 0.84, 0.86, 1.0) if clay else (0.90, 0.91, 0.92, 1.0)
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
    fill = add_area("Fill", (-1.8, -1.2, 1.6), 110, 2.0, (0.90, 0.93, 1.0))
    fill.rotation_euler = Euler((math.radians(50), 0, math.radians(-40)), "XYZ")
    rim = add_area("Rim", (0.2, 2.0, 1.8), 130, 1.2, (1.0, 0.96, 0.92))
    rim.rotation_euler = Euler((math.radians(-40), 0, math.radians(180)), "XYZ")
    # Bottom bounce light so 08_bottom view is evenly lit without harsh black shadows
    bottom_fill = add_area("BottomBounce", (0.0, -0.2, -1.8), 140, 2.4, (0.98, 0.97, 0.95))
    bottom_fill.rotation_euler = Euler((math.radians(180), 0, 0), "XYZ")


def clay_material(obj):
    mat = bpy.data.materials.new("Clay")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.78, 0.76, 0.72, 1)
    bsdf.inputs["Roughness"].default_value = 0.55
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
    bsdf.inputs["Roughness"].default_value = 0.65
    tex = nt.nodes.new("ShaderNodeTexImage")
    if COAT.exists():
        img = bpy.data.images.load(str(COAT))
        tex.image = img
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.66, 0.49, 0.34, 1)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def setup_camera(azimuth_deg, elevation_deg=6.0, distance=3.8, ortho_scale=1.75, perspective=False):
    """glTF 导入后：Blender Z-up，鼻尖朝 -Y，高度为 +Z。"""
    # Top/bottom views center slightly further back (y=0.12) to include nose tip to tail tip
    if abs(elevation_deg) > 75.0:
        target = Vector((0.0, 0.14, 0.52))
    else:
        target = Vector((0.0, 0.05, 0.62))
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
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
    up_axis = "Y"
    cam.rotation_euler = direction.to_track_quat("-Z", up_axis).to_euler()
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
    vg_index = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
    weights = []
    for v in mesh.vertices:
        wmap = {}
        for g in v.groups:
            wmap[vg_index[g.group]] = g.weight
        weights.append(wmap)

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

    shear = 0
    for i, v in enumerate(mesh.vertices):
        p = b2t(v.co)
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
        p = b2t(v.co)
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
    imgs = [Image.open(p).convert("RGB") for p in paths]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    pad = 8
    label_h = 44
    sheet = Image.new("RGB", (cols * w + (cols + 1) * pad, rows * (h + label_h) + (rows + 1) * pad), (32, 34, 38))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 22)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except Exception:
            font = ImageFont.load_default()
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        x = pad + c * (w + pad)
        y = pad + r * (h + label_h + pad)
        lab = labels[i] if labels else Path(paths[i]).stem
        draw.text((x + 8, y + 8), lab, fill=(240, 240, 240), font=font)
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

    # --- Hunyuan 8-view multiview (coat textured + 3D eyes/nose/paw-pads) ---
    mesh, arm = import_cat()
    setup_studio_lights(clay=False)
    coat_material(mesh)
    add_face_and_paw_features(mesh)
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.90, 0.91, 0.92, 1)

    # 8 slots matching Tencent Hunyuan 3D V3.1 star/cross UI:
    # 1. 正视图 (Front)  2. 左视图 (Left)  3. 右视图 (Right)  4. 背视图 (Back)
    # 5. 左45°图 (Left45) 6. 右45°图 (Right45) 7. 顶视图 (Top) 8. 底视图 (Bottom)
    hv_defs = [
        ("01_front", 0.0, 4.0, 1.80, "01_front · 混元「正视图」"),
        ("02_left", -90.0, 4.0, 1.80, "02_left · 混元「左视图」"),
        ("03_right", 90.0, 4.0, 1.80, "03_right · 混元「右视图」"),
        ("04_back", 180.0, 4.0, 1.80, "04_back · 混元「背视图」"),
        ("05_left45", -45.0, 4.0, 1.80, "05_left45 · 混元「左45°图」"),
        ("06_right45", 45.0, 4.0, 1.80, "06_right45 · 混元「右45°图」"),
        ("07_top", 0.0, 88.5, 1.95, "07_top · 混元「顶视图」"),
        ("08_bottom", 0.0, -88.5, 1.95, "08_bottom · 混元「底视图」"),
    ]
    hv_paths = []
    hv_labels = []
    for name, az, el, oscale, label in hv_defs:
        for o in list(bpy.data.objects):
            if o.type == "CAMERA":
                bpy.data.objects.remove(o, do_unlink=True)
        setup_camera(az, elevation_deg=el, distance=4.2, ortho_scale=oscale)
        p = OUT_HV / f"{name}.png"
        render_to(p, 1024)
        hv_paths.append(p)
        hv_labels.append(label)

    (OUT_VAL / "_tmp_eye_tex.png").unlink(missing_ok=True)
    collage(hv_paths, OUT_VAL / "miemie_hunyuan_multiview_sheet.png", labels=hv_labels, cols=4)

    collage(
        [hv_paths[0], hv_paths[1], hv_paths[2], hv_paths[4]],
        OUT_VAL / "miemie_anatomical_in_engine.png",
        labels=["Front (正视)", "Left (左视)", "Right (右视)", "Left 45° (左前45°)"],
        cols=2,
    )

    print("[done] audit", report)


if __name__ == "__main__":
    main()
