#!/usr/bin/env python3
"""
M2.2 — Export orthographic Depth / Camera-Normal / part-semantic Mask
for all 8 directions (pitch=35°) from frozen master_cat.blend (read-only).

Does NOT mutate topology / UV / blend on disk.
Fixed seed metadata written for downstream SDXL generation.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT / "art" / "master_cat"
OUT_CTRL = ROOT / "cats" / "miemie" / "identity_v1" / "control_views"
VAL_DIR = ROOT / "docs" / "validation" / "m2_2_8dir" / "control_maps"
EXPECTED_UV = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
PITCH_DEG = 35.0
# Match M2.1 / validate_master logical projection for d045; reuse for all yaws.
GW, GH = 114, 104
SS = 4  # hi = 456 x 416; pad later to 768 square contact if needed
S_LOG = 0.0040
ORIG_LOG = (52.7, 94.0)
SEED = 20261029

DIRECTIONS = {
    "d000": 0.0,
    "d045": -45.0,
    "d090": -90.0,
    "d135": -135.0,
    "d180": 180.0,
    "d225": 135.0,
    "d270": 90.0,
    "d315": 45.0,
}
# Complementary = all except the already-projected d045 anchor view.
COMPLEMENTARY = ["d000", "d090", "d180", "d270", "d135", "d225", "d315"]

# Part palette (semantic mask RGB, non-overlapping)
PART_COLORS = {
    "head": (220, 60, 60),
    "torso": (60, 180, 80),
    "leg_FL": (60, 120, 220),
    "leg_FR": (40, 80, 200),
    "leg_BL": (120, 80, 220),
    "leg_BR": (100, 60, 180),
    "tail": (220, 180, 40),
    "eye": (0, 255, 255),
}


def get_camera_basis(yaw_deg: float, pitch_deg: float = PITCH_DEG):
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cy, sy = math.cos(-yaw), math.sin(-yaw)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    e_u0 = np.array([-1.0, 0.0, 0.0], dtype=np.float64)
    e_v0 = np.array([0.0, -math.sin(pitch), math.cos(pitch)], dtype=np.float64)
    e_w0 = np.array([0.0, math.cos(pitch), math.sin(pitch)], dtype=np.float64)
    return rz @ e_u0, rz @ e_v0, rz @ e_w0


def compute_uv_hash(mesh) -> str:
    uv = mesh.uv_layers.active.data
    rows = [
        [loop.vertex_index, round(uv[loop.index].uv.x, 6), round(uv[loop.index].uv.y, 6)]
        for loop in mesh.loops
    ]
    return "sha256:" + hashlib.sha256(
        json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def classify_vertex_part(co: np.ndarray) -> str:
    """Coarse anatomical part from world coords (Basis rest). X>0 = anatomical Right."""
    x, y, z = float(co[0]), float(co[1]), float(co[2])
    # Tail: behind and lowish
    if y < -0.12 and z < 0.28:
        return "tail"
    # Legs: low Z
    if z < 0.14:
        if y >= 0.02:
            return "leg_FR" if x >= 0 else "leg_FL"
        return "leg_BR" if x >= 0 else "leg_BL"
    # Head
    if z > 0.28 and y > 0.05:
        return "head"
    return "torso"


def raster_view(yaw_deg: float, body_mesh, body_vs, eye_meshes) -> dict:
    e_u, e_v, e_w = get_camera_basis(yaw_deg)
    hi_w, hi_h = GW * SS, GH * SS
    zbuf = np.full((hi_h, hi_w), -1e9, dtype=np.float64)
    depth = np.zeros((hi_h, hi_w), dtype=np.float64)
    normal_cam = np.zeros((hi_h, hi_w, 3), dtype=np.float64)
    part_rgb = np.zeros((hi_h, hi_w, 3), dtype=np.uint8)
    alpha = np.zeros((hi_h, hi_w), dtype=bool)
    clay = np.zeros((hi_h, hi_w, 3), dtype=np.uint8)

    px = (ORIG_LOG[0] + (body_vs @ e_u) / S_LOG + 0.35) * SS
    py = (ORIG_LOG[1] - (body_vs @ e_v) / S_LOG + 0.35) * SS
    pw = body_vs @ e_w

    # Precompute vertex parts
    v_parts = [classify_vertex_part(body_vs[i]) for i in range(len(body_vs))]

    body_mesh.calc_loop_triangles()
    for lt in body_mesh.loop_triangles:
        i0, i1, i2 = lt.vertices
        v0, v1, v2 = body_vs[i0], body_vs[i1], body_vs[i2]
        fn = np.cross(v1 - v0, v2 - v0)
        nlen = np.linalg.norm(fn)
        if nlen < 1e-12:
            continue
        fn = fn / nlen
        ndotv = float(fn @ e_w)
        if ndotv <= 0.0:
            continue
        x0, y0, z0 = px[i0], py[i0], pw[i0]
        x1, y1, z1 = px[i1], py[i1], pw[i1]
        x2, y2, z2 = px[i2], py[i2], pw[i2]
        xmin = max(0, int(math.floor(min(x0, x1, x2))))
        xmax = min(hi_w - 1, int(math.ceil(max(x0, x1, x2))))
        ymin = max(0, int(math.floor(min(y0, y1, y2))))
        ymax = min(hi_h - 1, int(math.ceil(max(y0, y1, y2))))
        if xmax < xmin or ymax < ymin:
            continue
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-10:
            continue
        yy, xx = np.meshgrid(
            np.arange(ymin, ymax + 1) + 0.5,
            np.arange(xmin, xmax + 1) + 0.5,
            indexing="ij",
        )
        w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
        w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
        w2 = 1.0 - w0 - w1
        z_pix = w0 * z0 + w1 * z1 + w2 * z2
        sub_z = zbuf[ymin : ymax + 1, xmin : xmax + 1]
        vis = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4) & (z_pix >= sub_z)
        if not np.any(vis):
            continue
        # Camera-space normal (OpenGL: +X right, +Y up, +Z toward camera = e_w)
        n_cam = np.array([float(fn @ e_u), float(fn @ e_v), float(fn @ e_w)], dtype=np.float64)
        # Majority vote part from vertices
        votes = [v_parts[i0], v_parts[i1], v_parts[i2]]
        part = max(set(votes), key=votes.count)
        col = PART_COLORS[part]
        # Soft clay shade
        shade = 0.35 + 0.65 * max(0.0, ndotv)
        clay_col = np.array([int(180 * shade), int(170 * shade), int(160 * shade)], dtype=np.uint8)

        sub_z[vis] = z_pix[vis]
        depth[ymin : ymax + 1, xmin : xmax + 1][vis] = z_pix[vis]
        normal_cam[ymin : ymax + 1, xmin : xmax + 1][vis] = n_cam
        part_rgb[ymin : ymax + 1, xmin : xmax + 1][vis] = col
        clay[ymin : ymax + 1, xmin : xmax + 1][vis] = clay_col
        alpha[ymin : ymax + 1, xmin : xmax + 1][vis] = True

    # Eyes overlay as cyan mask (for ControlNet guidance, not albedo)
    for eye_mesh, eye_vs in eye_meshes:
        eye_mesh.calc_loop_triangles()
        epx = (ORIG_LOG[0] + (eye_vs @ e_u) / S_LOG + 0.35) * SS
        epy = (ORIG_LOG[1] - (eye_vs @ e_v) / S_LOG + 0.35) * SS
        epw = eye_vs @ e_w
        for lt in eye_mesh.loop_triangles:
            i0, i1, i2 = lt.vertices
            v0, v1, v2 = eye_vs[i0], eye_vs[i1], eye_vs[i2]
            fn = np.cross(v1 - v0, v2 - v0)
            if float(fn @ e_w) <= 0:
                continue
            x0, y0, z0 = epx[i0], epy[i0], epw[i0]
            x1, y1, z1 = epx[i1], epy[i1], epw[i1]
            x2, y2, z2 = epx[i2], epy[i2], epw[i2]
            xmin = max(0, int(math.floor(min(x0, x1, x2))))
            xmax = min(hi_w - 1, int(math.ceil(max(x0, x1, x2))))
            ymin = max(0, int(math.floor(min(y0, y1, y2))))
            ymax = min(hi_h - 1, int(math.ceil(max(y0, y1, y2))))
            if xmax < xmin or ymax < ymin:
                continue
            denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(denom) < 1e-10:
                continue
            yy, xx = np.meshgrid(
                np.arange(ymin, ymax + 1) + 0.5,
                np.arange(xmin, xmax + 1) + 0.5,
                indexing="ij",
            )
            w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
            w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
            w2 = 1.0 - w0 - w1
            z_pix = w0 * z0 + w1 * z1 + w2 * z2
            sub_z = zbuf[ymin : ymax + 1, xmin : xmax + 1]
            vis = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4) & (z_pix >= sub_z - 1e-4)
            if not np.any(vis):
                continue
            part_rgb[ymin : ymax + 1, xmin : xmax + 1][vis] = PART_COLORS["eye"]
            # do not overwrite body depth/normal for eyes much — mark alpha
            alpha[ymin : ymax + 1, xmin : xmax + 1][vis] = True
            sub_z[vis] = np.maximum(sub_z[vis], z_pix[vis])

    # Normalize depth to 0..1 within visible (far=0 near=1 style for ControlNet depth)
    depth_u8 = np.zeros((hi_h, hi_w), dtype=np.uint8)
    if np.any(alpha):
        dvis = depth[alpha]
        dmin, dmax = float(dvis.min()), float(dvis.max())
        span = max(dmax - dmin, 1e-6)
        norm = np.zeros_like(depth)
        norm[alpha] = (depth[alpha] - dmin) / span
        depth_u8 = np.clip(norm * 255.0, 0, 255).astype(np.uint8)

    # Camera normal → RGB
    nrgb = np.zeros((hi_h, hi_w, 3), dtype=np.uint8)
    if np.any(alpha):
        n = normal_cam.copy()
        nlen = np.linalg.norm(n, axis=2, keepdims=True)
        nlen = np.maximum(nlen, 1e-9)
        n = n / nlen
        enc = n * 0.5 + 0.5
        nrgb[alpha] = np.clip(enc[alpha] * 255.0, 0, 255).astype(np.uint8)

    # Alpha RGBA clay
    clay_rgba = np.zeros((hi_h, hi_w, 4), dtype=np.uint8)
    clay_rgba[:, :, :3] = clay
    clay_rgba[:, :, 3] = np.where(alpha, 255, 0).astype(np.uint8)

    mask_rgba = np.zeros((hi_h, hi_w, 4), dtype=np.uint8)
    mask_rgba[:, :, :3] = part_rgb
    mask_rgba[:, :, 3] = np.where(alpha, 255, 0).astype(np.uint8)

    return {
        "depth_u8": depth_u8,
        "normal_rgb": nrgb,
        "part_mask": mask_rgba,
        "clay_rgba": clay_rgba,
        "alpha": alpha,
        "hi_size": (hi_w, hi_h),
    }


def pad_to_square(im: Image.Image, size: int = 768, fill=(0, 0, 0, 0)) -> Image.Image:
    w, h = im.size
    canvas = Image.new(im.mode, (size, size), fill if im.mode == "RGBA" else fill[:3])
    canvas.paste(im, ((size - w) // 2, (size - h) // 2))
    return canvas


def main() -> int:
    OUT_CTRL.mkdir(parents=True, exist_ok=True)
    VAL_DIR.mkdir(parents=True, exist_ok=True)

    blend = MASTER_DIR / "master_cat.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend))

    for name in ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]:
        obj = bpy.data.objects[name]
        if obj.data.shape_keys:
            for kb in obj.data.shape_keys.key_blocks:
                if kb.name.startswith("cal_"):
                    raise RuntimeError(f"Forbidden cal_ key: {name}:{kb.name}")
                if kb.name != "Basis" and abs(kb.value) > 1e-7:
                    kb.value = 0.0

    body = bpy.data.objects["CAT_BODY"]
    measured = compute_uv_hash(body.data)
    if measured != EXPECTED_UV:
        raise RuntimeError(f"uv_hash mismatch: {measured}")

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    vs = np.array([list(ev.matrix_world @ v.co) for v in mesh.vertices], dtype=np.float64)

    eye_meshes = []
    for ename in ["CAT_EYE_L", "CAT_EYE_R"]:
        eev = bpy.data.objects[ename].evaluated_get(depsgraph)
        em = eev.to_mesh()
        evs = np.array([list(eev.matrix_world @ v.co) for v in em.vertices], dtype=np.float64)
        eye_meshes.append((em, evs))

    meta = {
        "ok": True,
        "uv_hash": measured,
        "uv_hash_unchanged": True,
        "pitch_deg": PITCH_DEG,
        "seed": SEED,
        "scale_m_per_logical_px": S_LOG,
        "origin_logical_px": list(ORIG_LOG),
        "logical_grid": [GW, GH],
        "supersample": SS,
        "hi_size": [GW * SS, GH * SS],
        "sdxl_canvas": 768,
        "directions": {},
        "complementary": COMPLEMENTARY,
        "part_colors": PART_COLORS,
        "note": "Control maps only. Complementary albedo must come from locked commercial SDXL stack; never procedural default.",
    }

    sheet_cells = []
    for dname, yaw in DIRECTIONS.items():
        print(f"export {dname} yaw={yaw}", flush=True)
        r = raster_view(yaw, mesh, vs, eye_meshes)
        ddir = OUT_CTRL / dname
        ddir.mkdir(parents=True, exist_ok=True)
        depth_im = Image.fromarray(r["depth_u8"], mode="L")
        normal_im = Image.fromarray(r["normal_rgb"], mode="RGB")
        mask_im = Image.fromarray(r["part_mask"], mode="RGBA")
        clay_im = Image.fromarray(r["clay_rgba"], mode="RGBA")
        depth_im.save(ddir / "depth.png")
        normal_im.save(ddir / "normal.png")
        mask_im.save(ddir / "part_mask.png")
        clay_im.save(ddir / "clay.png")
        # 768 padded for SDXL ControlNet
        pad_to_square(depth_im.convert("RGB"), 768, (0, 0, 0)).save(ddir / "depth_768.png")
        pad_to_square(normal_im, 768, (128, 128, 255)).save(ddir / "normal_768.png")
        pad_to_square(mask_im, 768, (0, 0, 0, 0)).save(ddir / "part_mask_768.png")
        pad_to_square(clay_im, 768, (0, 0, 0, 0)).save(ddir / "clay_768.png")
        # Also copy to validation
        vdir = VAL_DIR / dname
        vdir.mkdir(parents=True, exist_ok=True)
        for fn in ["depth.png", "normal.png", "part_mask.png", "clay.png"]:
            Image.open(ddir / fn).save(vdir / fn)
        meta["directions"][dname] = {
            "yaw_deg": yaw,
            "pitch_deg": PITCH_DEG,
            "is_complementary": dname in COMPLEMENTARY,
            "is_m2_1_anchor": dname == "d045",
            "visible_px": int(r["alpha"].sum()),
            "paths": {
                "depth": str((ddir / "depth.png").relative_to(ROOT)),
                "normal": str((ddir / "normal.png").relative_to(ROOT)),
                "part_mask": str((ddir / "part_mask.png").relative_to(ROOT)),
                "depth_768": str((ddir / "depth_768.png").relative_to(ROOT)),
                "normal_768": str((ddir / "normal_768.png").relative_to(ROOT)),
            },
        }
        # contact sheet cell
        cell = Image.new("RGB", (456 + 8, 416 * 2 + 40), (24, 26, 32))
        cell.paste(Image.fromarray(r["depth_u8"]).convert("RGB"), (4, 28))
        cell.paste(normal_im, (4, 28 + 416))
        dr = ImageDraw.Draw(cell)
        dr.text((8, 6), f"{dname} yaw={yaw} depth|normal", fill=(220, 220, 230))
        sheet_cells.append(cell)

    # Contact sheet 4x2
    cw, ch = sheet_cells[0].size
    sheet = Image.new("RGB", (cw * 4, ch * 2), (18, 20, 26))
    for i, cell in enumerate(sheet_cells):
        sheet.paste(cell, ((i % 4) * cw, (i // 4) * ch))
    sheet.save(VAL_DIR / "m2_2_control_depth_normal_sheet.png")

    (OUT_CTRL / "export_report.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
    )
    (VAL_DIR / "export_report.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps({"ok": True, "dirs": list(DIRECTIONS), "uv_hash": measured}, indent=2))
    ev.to_mesh_clear()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
