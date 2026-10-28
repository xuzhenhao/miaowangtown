#!/usr/bin/env python3
"""
Route B (Refined v2): Hand-crafted Layered UV Texture Master + Miemie Photo Palette & 5-Markings Mask
+ 2-Tone Warm Lantern Shading on `cat_chibi_base.glb` + Low-res Pixelation + 1px Outline.
Uses continuous 3D surface coordinates + organic fur-tuft edge modulation so markings flow smoothly
across head/neck/body/limbs without artificial UV-part boundary steps.
"""
import math
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector, Euler
from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
GLB_PATH = OUT_DIR / "cat_chibi_base.glb"
ATLAS_SIZE = 1024

HEAD_YAW = math.radians(16.0)
HEAD_PIVOT = np.array([0.0, 0.72, 0.32], dtype=np.float32)


def inv_rotate_head_np(pts: np.ndarray) -> np.ndarray:
    rel = pts - HEAD_PIVOT
    c = math.cos(-HEAD_YAW)
    s = math.sin(-HEAD_YAW)
    out = pts.copy()
    out[..., 0] = HEAD_PIVOT[0] + rel[..., 0] * c + rel[..., 2] * s
    out[..., 2] = HEAD_PIVOT[2] - rel[..., 0] * s + rel[..., 2] * c
    return out


def build_rest_map_from_glb():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(GLB_PATH))
    obj = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
    me = obj.data
    me.calc_loop_triangles()

    n_verts = len(me.vertices)
    verts_t = np.zeros((n_verts, 3), dtype=np.float32)
    norms_t = np.zeros((n_verts, 3), dtype=np.float32)
    parts = np.zeros(n_verts, dtype=np.int32)
    part_attr = me.attributes.get("_PART")

    for i, v in enumerate(me.vertices):
        verts_t[i] = (v.co.x, v.co.z, -v.co.y)
        norms_t[i] = (v.normal.x, v.normal.z, -v.normal.y)
        if part_attr:
            parts[i] = int(round(part_attr.data[i].value))

    uv_layer = me.uv_layers.active.data

    valid = np.zeros((ATLAS_SIZE, ATLAS_SIZE), dtype=np.uint8)
    part_map = np.full((ATLAS_SIZE, ATLAS_SIZE), -1, dtype=np.int32)
    pos_map = np.zeros((ATLAS_SIZE, ATLAS_SIZE, 3), dtype=np.float32)
    norm_map = np.zeros((ATLAS_SIZE, ATLAS_SIZE, 3), dtype=np.float32)

    for tri in me.loop_triangles:
        l0, l1, l2 = tri.loops
        v0, v1, v2 = tri.vertices
        uv0 = uv_layer[l0].uv
        uv1 = uv_layer[l1].uv
        uv2 = uv_layer[l2].uv

        u0, w0_y = uv0.x * ATLAS_SIZE, (1.0 - uv0.y) * ATLAS_SIZE
        u1, w1_y = uv1.x * ATLAS_SIZE, (1.0 - uv1.y) * ATLAS_SIZE
        u2, w2_y = uv2.x * ATLAS_SIZE, (1.0 - uv2.y) * ATLAS_SIZE

        min_x = max(0, int(math.floor(min(u0, u1, u2) - 0.5)))
        max_x = min(ATLAS_SIZE - 1, int(math.ceil(max(u0, u1, u2) + 0.5)))
        min_y = max(0, int(math.floor(min(w0_y, w1_y, w2_y) - 0.5)))
        max_y = min(ATLAS_SIZE - 1, int(math.ceil(max(w0_y, w1_y, w2_y) + 0.5)))

        denom = (w1_y - w2_y) * (u0 - u2) + (u2 - u1) * (w0_y - w2_y)
        if abs(denom) < 1e-8:
            continue
        inv_d = 1.0 / denom
        pid = parts[v0]
        p0, p1, p2 = verts_t[v0], verts_t[v1], verts_t[v2]
        n0, n1, n2 = norms_t[v0], norms_t[v1], norms_t[v2]

        xs = np.arange(min_x, max_x + 1, dtype=np.float32) + 0.5
        ys = np.arange(min_y, max_y + 1, dtype=np.float32) + 0.5
        gx, gy = np.meshgrid(xs, ys)

        b0 = ((w1_y - w2_y) * (gx - u2) + (u2 - u1) * (gy - w2_y)) * inv_d
        b1 = ((w2_y - w0_y) * (gx - u2) + (u0 - u2) * (gy - w2_y)) * inv_d
        b2 = 1.0 - b0 - b1

        mask = (b0 >= -0.025) & (b1 >= -0.025) & (b2 >= -0.025)
        if not np.any(mask):
            continue

        b0c = np.maximum(0.0, b0[mask])
        b1c = np.maximum(0.0, b1[mask])
        b2c = np.maximum(0.0, b2[mask])
        bsum = np.maximum(1e-6, b0c + b1c + b2c)
        b0c /= bsum
        b1c /= bsum
        b2c /= bsum

        py_idx, px_idx = np.where(mask)
        py_idx += min_y
        px_idx += min_x

        valid[py_idx, px_idx] = 1
        part_map[py_idx, px_idx] = pid
        pos_map[py_idx, px_idx] = b0c[:, None] * p0 + b1c[:, None] * p1 + b2c[:, None] * p2
        n_interp = b0c[:, None] * n0 + b1c[:, None] * n1 + b2c[:, None] * n2
        n_len = np.maximum(1e-6, np.linalg.norm(n_interp, axis=1, keepdims=True))
        norm_map[py_idx, px_idx] = n_interp / n_len

    for _ in range(6):
        empty = valid == 0
        if not np.any(empty):
            break
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            shifted_v = np.roll(np.roll(valid, dy, axis=0), dx, axis=1)
            fill = empty & (shifted_v == 1)
            if np.any(fill):
                valid[fill] = 1
                part_map[fill] = np.roll(np.roll(part_map, dy, axis=0), dx, axis=1)[fill]
                pos_map[fill] = np.roll(np.roll(pos_map, dy, axis=0), dx, axis=1)[fill]
                norm_map[fill] = np.roll(np.roll(norm_map, dy, axis=0), dx, axis=1)[fill]
                empty = valid == 0

    return obj, valid, part_map, pos_map, norm_map


def synthesize_route_b_atlas(valid, part_map, pos_map, norm_map) -> Image.Image:
    """
    Synthesize Route B 1024x1024 layered coat + facial feature atlas from Miemie's real photo palette
    and 5 asymmetric markings, using continuous 3D coordinates + fur-tuft edge modulation.
    """
    H, W = ATLAS_SIZE, ATLAS_SIZE
    atlas = np.zeros((H, W, 3), dtype=np.float32)

    # Warm brown mackerel tabby palette matched to red-box cat & Miemie photos:
    C_BASE_WARM = np.array([138, 95, 54], dtype=np.float32)
    C_STRIPE_DARK = np.array([50, 29, 15], dtype=np.float32)
    C_STRIPE_MID = np.array([86, 52, 26], dtype=np.float32)
    C_CREAM_WHITE = np.array([224, 204, 178], dtype=np.float32)
    C_WHITE_SHADE = np.array([188, 168, 142], dtype=np.float32)
    C_CARAMEL = np.array([162, 106, 60], dtype=np.float32)
    C_APRICOT = np.array([186, 132, 84], dtype=np.float32)
    C_EAR_PINK = np.array([194, 138, 120], dtype=np.float32)
    C_EAR_DARK = np.array([54, 31, 16], dtype=np.float32)

    atlas[:, :] = C_BASE_WARM

    p = pos_map
    px_3d = p[..., 0]
    py_3d = p[..., 1]
    pz_3d = p[..., 2]
    nx_3d = norm_map[..., 0]
    ny_3d = norm_map[..., 1]
    nz_3d = norm_map[..., 2]

    p_head = inv_rotate_head_np(p)
    hx = p_head[..., 0]
    hy = p_head[..., 1]
    hz = p_head[..., 2]

    # Subtle fur-tuft wave along 3D surface so color transitions look hand-painted rather than geometric cuts
    fur_wave = 0.014 * np.sin(px_3d * 55.0 + pz_3d * 45.0) + 0.009 * np.cos(py_3d * 65.0 - pz_3d * 38.0)

    is_head = (part_map == 0)
    is_muzzle = (part_map == 1)
    is_neck = (part_map == 2)
    is_body = (part_map == 3)
    is_fLegL = (part_map == 4)
    is_fLegR = (part_map == 5)
    is_hLegL = (part_map == 6)
    is_hLegR = (part_map == 7)
    is_earL = (part_map == 8)
    is_earR = (part_map == 9)
    is_tail = (part_map == 10)
    is_legs = is_fLegL | is_fLegR | is_hLegL | is_hLegR

    # --- Layer 1: Continuous Mackerel Tabby Stripes across torso, shoulders, hind thighs, head & tail ---
    # 1a. Curved mackerel rib stripes (flow continuously across body and upper legs)
    rib_coord = pz_3d - (0.52 - py_3d) * 0.24 + fur_wave * 0.6
    rib_phase = np.sin(rib_coord * 6.5 * math.pi * 2.0)
    torso_zone = (is_body | is_neck) & (py_3d > 0.28) & (pz_3d < 0.22)
    atlas[torso_zone & (rib_phase > 0.16)] = C_STRIPE_MID
    atlas[torso_zone & (rib_phase > 0.44)] = C_STRIPE_DARK

    # Dorsal spine stripe
    dorsal_line = is_body & (np.abs(px_3d) < 0.048 + fur_wave * 0.5) & (py_3d > 0.50)
    atlas[dorsal_line] = C_STRIPE_DARK

    # 1b. Hind legs & upper front legs horizontal tabby stripes
    leg_phase = np.sin((py_3d + fur_wave * 0.4) * 10.0 * math.pi * 2.0)
    hind_stripes = (is_hLegL | is_hLegR) & (py_3d > 0.15) & (leg_phase > 0.24)
    front_stripes = (is_fLegL | is_fLegR) & (py_3d > 0.23) & (leg_phase > 0.30)
    atlas[front_stripes] = C_STRIPE_MID
    atlas[hind_stripes] = C_STRIPE_DARK

    # 1c. Tail rings & dark tail tip
    tail_dist = np.sqrt((pz_3d - (-0.32)) ** 2 + (py_3d - 0.48) ** 2)
    tail_rings = is_tail & (np.sin(tail_dist * 9.2 * math.pi * 2.0) > 0.22)
    tail_tip = is_tail & (pz_3d < -0.78)
    atlas[tail_rings] = C_STRIPE_DARK
    atlas[tail_tip] = C_STRIPE_DARK

    # 1d. Forehead M-stripes & cheek tabby lines
    crown_stripes = is_head & (hy > 0.77) & (np.sin(hx * 11.0 * math.pi * 2.0) > 0.26)
    cheek_stripes = is_head & (hy > 0.65) & (hy < 0.81) & (np.abs(hx) > 0.14) & (np.sin((hy - 0.68) * 12.0 * math.pi * 2.0) > 0.30)
    atlas[crown_stripes] = C_STRIPE_DARK
    atlas[cheek_stripes] = C_STRIPE_DARK

    # --- Layer 2: Continuous Miemie 5-Markings (evaluated in 3D space across head+neck+body+legs!) ---
    # 2a. Continuous White Muzzle + Lower Cheek + Chest Bib + Belly + Left Flank White Cloud
    # Muzzle & lower cheek white region (in head-local coords, smoothly merging into neck bib)
    d_muzzle_white = (
        ((hx - 0.015) / 0.235) ** 2
        + ((hy - 0.635) / 0.125) ** 2
        + ((hz - 0.48) / 0.22) ** 2
    )
    # Nose blaze extending up between the eyes (slightly left-biased like Miemie)
    d_blaze = (
        ((hx - 0.018) / 0.042) ** 2
        + ((hy - 0.745) / 0.085) ** 2
        + ((hz - 0.54) / 0.12) ** 2
    )
    # Continuous chest bib (spans lower head, neck, and front chest seamlessly without part boundaries!)
    d_bib = (
        (px_3d / 0.175) ** 2
        + ((py_3d - 0.48) / 0.21) ** 2
        + ((pz_3d - 0.28) / 0.19) ** 2
    )
    # Belly underside & Left flank (+X) upward white cloud patch
    is_belly_white = (is_body | is_neck) & ((py_3d < 0.30 + fur_wave) | (ny_3d < -0.48))
    d_left_cloud = (
        ((px_3d - 0.14) / 0.13) ** 2
        + ((py_3d - 0.33) / 0.105) ** 2
        + ((pz_3d - 0.03) / 0.165) ** 2
    )

    white_zone = (
        ((is_head | is_muzzle | is_neck) & ((d_muzzle_white < 1.0 + fur_wave * 2.5) | (d_blaze < 1.0)))
        | ((is_head | is_neck | is_body) & (d_bib < 1.0 + fur_wave * 2.5) & (pz_3d > 0.12))
        | is_belly_white
        | (is_body & (px_3d > 0.03) & (d_left_cloud < 1.0 + fur_wave * 2.0))
    )
    atlas[white_zone] = C_CREAM_WHITE

    # 2b. Belly warm apricot-orange transition spot along the border of the left flank white cloud
    d_belly_orange = (
        ((px_3d - 0.14) / 0.095) ** 2
        + ((py_3d - 0.32) / 0.052) ** 2
        + ((pz_3d - (-0.06)) / 0.095) ** 2
    )
    atlas[is_body & (d_belly_orange < 1.0 + fur_wave)] = C_APRICOT

    # 2c. Four white socks: higher front socks (y < 0.235), shorter hind ankle socks (y < 0.150)
    front_socks = (is_fLegL | is_fLegR) & (py_3d < 0.235 + fur_wave)
    hind_socks = (is_hLegL | is_hLegR) & (py_3d < 0.150 + fur_wave)
    atlas[front_socks | hind_socks] = C_CREAM_WHITE
    # Miemie's right front wrist inner caramel spot
    right_wrist_spot = is_fLegR & (py_3d > 0.14) & (py_3d < 0.22) & (px_3d > -0.075)
    atlas[right_wrist_spot] = C_CARAMEL

    # 2d. Miemie's Asymmetric Muzzle: Right muzzle (`-X`, screen left) warm caramel patch, Left muzzle (`+X`, screen right) clean white + apricot lower lip
    d_right_caramel = (
        ((hx - (-0.065)) / 0.068) ** 2
        + ((hy - 0.688) / 0.052) ** 2
        + ((hz - 0.56) / 0.09) ** 2
    )
    right_muzzle_caramel = (is_muzzle | is_head) & (hx < -0.010) & (d_right_caramel < 1.0 + fur_wave)
    atlas[right_muzzle_caramel] = C_CARAMEL

    left_lip_apricot = (is_muzzle | is_head) & (hz > 0.50) & (hx > 0.02) & (hx < 0.10) & (hy > 0.60) & (hy < 0.638)
    atlas[left_lip_apricot] = C_APRICOT

    # 2e. Ears: dark brown outer rim & tip, soft pink inner concha
    for side, ear_mask in ((1.0, is_earL), (-1.0, is_earR)):
        inner_e = ear_mask & (hz > 0.35) & (hy > 0.95) & (hy < 1.15) & (np.abs(hx - side * 0.185) < 0.075)
        tip_e = ear_mask & (hy >= 1.13)
        rim_e = ear_mask & (~inner_e)
        atlas[rim_e] = C_BASE_WARM * 0.84
        atlas[tip_e] = C_EAR_DARK
        atlas[inner_e] = C_EAR_PINK

    # --- Layer 3: Cohesive 2-Tone Warm Lantern Lighting (top-right warm highlight, lower/left soft shadow) ---
    # Light direction in Three.js space: coming from front-left-top (+X=0.45, +Y=0.75, +Z=0.48)
    light_dir = np.array([0.45, 0.75, 0.48], dtype=np.float32)
    light_dir /= np.linalg.norm(light_dir)
    ndotl = nx_3d * light_dir[0] + ny_3d * light_dir[1] + nz_3d * light_dir[2]
    # 2-step clean pixel-art shading: underside & lower legs get 0.84x warm shade, upper/lit surfaces get 1.04x warm lantern tint
    shade_mask = (ndotl < -0.12) | (py_3d < 0.08) | (is_body & (py_3d < 0.29))
    highlight_mask = (ndotl > 0.48) & (py_3d > 0.38)
    atlas[shade_mask] *= np.array([0.84, 0.82, 0.80], dtype=np.float32)
    atlas[highlight_mask] *= np.array([1.05, 1.03, 0.98], dtype=np.float32)

    # --- Layer 4: Large Expressive Almond Emerald-Green Eyes + Pink Nose + Mouth Line (drawn after shading so eyes stay super crisp!) ---
    C_EYE_OUTLINE = np.array([28, 16, 10], dtype=np.float32)
    C_IRIS_DARK = np.array([42, 92, 40], dtype=np.float32)
    C_IRIS_MID = np.array([78, 146, 70], dtype=np.float32)
    C_IRIS_BRIGHT = np.array([128, 198, 106], dtype=np.float32)
    C_PUPIL = np.array([18, 26, 16], dtype=np.float32)
    C_HIGHLIGHT = np.array([250, 248, 242], dtype=np.float32)
    C_NOSE_PINK = np.array([198, 96, 80], dtype=np.float32)

    front_face = (is_head | is_muzzle) & (hz > 0.40)
    for side, ex_c in ((1.0, 0.118), (-1.0, -0.112)):
        ey_c = 0.758
        rx_e = 0.068
        ry_e = 0.064
        dx_e = (hx - ex_c) / rx_e
        dy_e = (hy - ey_c) / ry_e
        r2_e = dx_e ** 2 + dy_e ** 2

        upper_lash = front_face & (r2_e <= 1.28) & (dy_e > -0.85)
        eye_interior = front_face & (r2_e <= 0.92)
        iris_mid = front_face & (r2_e <= 0.76)
        iris_bright = front_face & (r2_e <= 0.68) & (dy_e < 0.15)
        pupil_mask = front_face & (((hx - ex_c) / (rx_e * 0.34)) ** 2 + ((hy - ey_c) / (ry_e * 0.78)) ** 2 <= 1.0)
        hl_mask = front_face & (
            ((hx - (ex_c + 0.022)) / (rx_e * 0.28)) ** 2 + ((hy - (ey_c + 0.022)) / (ry_e * 0.28)) ** 2 <= 1.0
        )

        atlas[upper_lash] = C_EYE_OUTLINE
        atlas[eye_interior] = C_IRIS_DARK
        atlas[iris_mid] = C_IRIS_MID
        atlas[iris_bright] = C_IRIS_BRIGHT
        atlas[pupil_mask] = C_PUPIL
        atlas[hl_mask] = C_HIGHLIGHT

    nose_mask = front_face & (hz > 0.54) & (hy > 0.678) & (hy < 0.715) & (
        np.abs(hx) < (0.012 + (hy - 0.678) * 0.65)
    )
    nose_rim = front_face & (hz > 0.54) & (hy > 0.645) & (hy <= 0.678) & (np.abs(hx) < 0.010)
    mouth_w = front_face & (hz > 0.52) & (hy > 0.632) & (hy <= 0.655) & (np.abs(hx) >= 0.008) & (np.abs(hx) < 0.042) & (
        np.abs(hy - (0.638 + (np.abs(hx) - 0.024) ** 2 * 12.0)) < 0.009
    )
    atlas[nose_mask] = C_NOSE_PINK
    atlas[nose_rim | mouth_w] = C_EYE_OUTLINE

    atlas_u8 = np.clip(atlas, 0, 255).astype(np.uint8)
    im = Image.fromarray(atlas_u8, mode="RGB")
    im.save(OUT_DIR / "route_b_atlas_1024.png")
    return im


def render_chibi_with_atlas(obj, atlas_path: Path, out_highres_path: Path):
    mat = bpy.data.materials.new("ChibiPixelMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(atlas_path))
    tex.interpolation = "Closest"

    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    emit.inputs["Strength"].default_value = 1.0
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    obj.data.materials.clear()
    obj.data.materials.append(mat)

    for o in list(bpy.data.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o, do_unlink=True)

    target = Vector((-0.02, 0.08, 0.56))
    az = math.radians(52.0)
    el = math.radians(20.0)
    dist = 4.0
    loc = Vector((
        target.x + dist * math.cos(el) * math.sin(az),
        target.y - dist * math.cos(el) * math.cos(az),
        target.z + dist * math.sin(el),
    ))
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 1.62
    direction = target - loc
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.film_transparent = True
    scene.render.filepath = str(out_highres_path)
    bpy.ops.render.render(write_still=True)


def pixelate_and_outline(highres_path: Path, out_sprite_path: Path, grid_size: int = 84):
    im = Image.open(highres_path).convert("RGBA")
    arr = np.array(im)
    ys, xs = np.where(arr[:, :, 3] > 32)
    pad_hi = 28
    x0 = max(0, xs.min() - pad_hi)
    x1 = min(im.width, xs.max() + pad_hi)
    y0 = max(0, ys.min() - pad_hi)
    y1 = min(im.height, ys.max() + pad_hi)
    side = max(x1 - x0, y1 - y0)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, (side // 2 - cx, side // 2 - cy))

    low = sq.resize((grid_size, grid_size), Image.Resampling.NEAREST)
    low_arr = np.array(low)
    alpha = low_arr[:, :, 3] > 110
    low_arr[~alpha] = [0, 0, 0, 0]
    low_arr[alpha, 3] = 255

    outline_col = np.array([27, 16, 10, 255], dtype=np.uint8)
    dilated = np.zeros_like(alpha)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dilated |= np.roll(np.roll(alpha, dy, axis=0), dx, axis=1)
    edge = dilated & (~alpha)
    low_arr[edge] = outline_col

    w_mask = alpha & (low_arr[:, :, 0] > 180) & (low_arr[:, :, 1] > 160)
    wys, wxs = np.where(w_mask & (np.arange(grid_size)[:, None] < grid_size * 0.58))
    if len(wxs) > 0:
        wx_min = int(np.percentile(wxs, 5))
        wy_med = int(np.median(wys[wxs <= wx_min + 3]))
        for wy_off, wx_len in [(-1, 3), (2, 3)]:
            wy = wy_med + wy_off
            for step in range(1, wx_len + 1):
                wx = wx_min - step
                if 0 <= wx < grid_size and 0 <= wy < grid_size:
                    low_arr[wy, wx] = [228, 212, 192, 255]

    low_im = Image.fromarray(low_arr, mode="RGBA")
    low_im.save(OUT_DIR / f"{out_sprite_path.stem}_lowres.png")
    up_im = low_im.resize((grid_size * 3, grid_size * 3), Image.Resampling.NEAREST)
    up_im.save(out_sprite_path)
    print(f"[route_b] Saved pixel sprite {out_sprite_path} ({up_im.size})")


def main():
    obj, valid, part_map, pos_map, norm_map = build_rest_map_from_glb()
    synthesize_route_b_atlas(valid, part_map, pos_map, norm_map)
    render_chibi_with_atlas(obj, OUT_DIR / "route_b_atlas_1024.png", OUT_DIR / "route_b_highres_render.png")
    pixelate_and_outline(OUT_DIR / "route_b_highres_render.png", OUT_DIR / "route_b_sprite.png", grid_size=84)


if __name__ == "__main__":
    main()
