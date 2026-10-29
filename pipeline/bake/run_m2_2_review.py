#!/usr/bin/env python3
"""
M2.2 — Build 8-direction dual-layer identity review boards from current fur_albedo.

Honesty:
  - If complementary views were not AI-generated/gated, boards are labeled INCOMPLETE
    (d045 content only; backs show genome seed midtone — not a pass).
  - Silhouette for d045 inherits M1 Alpha lock note from M2.1; not new evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path("/workspace/miaowangtown")
sys.path.insert(0, str(ROOT))
from pipeline.bake.post_v4_1_pixel import (  # noqa: E402
    ALPHA_THR,
    apply_lantern_ao,
    downsample_to_logical,
    logical_to_canvas_2x,
)

MASTER_DIR = ROOT / "art" / "master_cat"
ID_DIR = ROOT / "cats" / "miemie" / "identity_v1"
OUT_DIR = ROOT / "docs" / "validation" / "m2_2_8dir"
EXPECTED_UV = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
GW, GH = 114, 104
SS = 4
S_LOG = 0.0040
ORIG_LOG = (52.7, 94.0)
PITCH = 35.0
DIRECTIONS = [
    ("d000", 0.0),
    ("d045", -45.0),
    ("d090", -90.0),
    ("d135", -135.0),
    ("d180", 180.0),
    ("d225", 135.0),
    ("d270", 90.0),
    ("d315", 45.0),
]


def get_camera_basis(yaw_deg: float, pitch_deg: float = PITCH):
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


def render_hi(fur_rgba: np.ndarray, yaw_deg: float) -> np.ndarray:
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    e_u, e_v, e_w = get_camera_basis(yaw_deg)
    hi_w, hi_h = GW * SS, GH * SS
    zbuf = np.full((hi_h, hi_w), -1e9, dtype=np.float64)
    rgb = np.zeros((hi_h, hi_w, 3), dtype=np.uint8)
    alpha = np.zeros((hi_h, hi_w), dtype=bool)

    ev = bpy.data.objects["CAT_BODY"].evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active.data
    vs = np.array([list(ev.matrix_world @ v.co) for v in mesh.vertices], dtype=np.float64)
    px = (ORIG_LOG[0] + (vs @ e_u) / S_LOG + 0.35) * SS
    py = (ORIG_LOG[1] - (vs @ e_v) / S_LOG + 0.35) * SS
    pw = vs @ e_w
    usz = fur_rgba.shape[0]

    for lt in mesh.loop_triangles:
        i0, i1, i2 = lt.vertices
        v0, v1, v2 = vs[i0], vs[i1], vs[i2]
        fn = np.cross(v1 - v0, v2 - v0)
        if float(fn @ e_w) < 0.0:
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
        if abs(denom) < 1e-8:
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
        l0, l1, l2 = lt.loops
        u0, v0u = uv_layer[l0].uv
        u1, v1u = uv_layer[l1].uv
        u2, v2u = uv_layer[l2].uv
        u_p = w0[vis] * u0 + w1[vis] * u1 + w2[vis] * u2
        v_p = w0[vis] * v0u + w1[vis] * v1u + w2[vis] * v2u
        tx = np.clip(np.round(u_p * (usz - 1)).astype(np.int32), 0, usz - 1)
        ty = np.clip(np.round((1.0 - v_p) * (usz - 1)).astype(np.int32), 0, usz - 1)
        cols = fur_rgba[ty, tx]
        sub_z[vis] = z_pix[vis]
        rgb[ymin : ymax + 1, xmin : xmax + 1][vis] = cols[:, :3]
        alpha[ymin : ymax + 1, xmin : xmax + 1][vis] = True
    ev.to_mesh_clear()

    # Eyes (parametric) — same as M2.1
    for name, u_b in [("CAT_EYE_L", (0.265, 0.365)), ("CAT_EYE_R", (0.385, 0.485))]:
        ev = bpy.data.objects[name].evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        mesh.calc_loop_triangles()
        vs = np.array([list(ev.matrix_world @ v.co) for v in mesh.vertices], dtype=np.float64)
        uv_layer = mesh.uv_layers.active.data
        px = (ORIG_LOG[0] + (vs @ e_u) / S_LOG + 0.35) * SS
        py = (ORIG_LOG[1] - (vs @ e_v) / S_LOG + 0.35) * SS
        pw = vs @ e_w
        for lt in mesh.loop_triangles:
            i0, i1, i2 = lt.vertices
            v0, v1, v2 = vs[i0], vs[i1], vs[i2]
            fn = np.cross(v1 - v0, v2 - v0)
            if float(fn @ e_w) < 0.0:
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
            if abs(denom) < 1e-8:
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
            l0, l1, l2 = lt.loops
            u0, v0u = uv_layer[l0].uv
            u1, v1u = uv_layer[l1].uv
            u2, v2u = uv_layer[l2].uv
            u_p = w0[vis] * u0 + w1[vis] * u1 + w2[vis] * u2
            v_p = w0[vis] * v0u + w1[vis] * v1u + w2[vis] * v2u
            ux = (u_p - u_b[0]) / (u_b[1] - u_b[0])
            vz = (v_p - 0.020) / (0.230 - 0.020)
            ex = (ux - 0.5) / 0.42
            ez = (vz - 0.5) / 0.42
            c_pix = np.full((len(ex), 3), [43, 122, 61], dtype=np.uint8)
            is_bright = ez < 0.05
            c_pix[is_bright] = [104, 200, 100]
            is_pupil = (np.abs(ex) < 0.25) & (ez > -0.62) & (ez < 0.52)
            c_pix[is_pupil] = [18, 28, 22]
            is_hl = ((ex - 0.30) ** 2 + (ez - 0.26) ** 2) < 0.11
            c_pix[is_hl] = [252, 248, 240]
            is_lid = ez > 0.55
            c_pix[is_lid] = [27, 16, 10]
            sub_z[vis] = z_pix[vis]
            rgb[ymin : ymax + 1, xmin : xmax + 1][vis] = c_pix
            alpha[ymin : ymax + 1, xmin : xmax + 1][vis] = True
        ev.to_mesh_clear()

    rgba = np.zeros((hi_h, hi_w, 4), dtype=np.uint8)
    rgba[:, :, :3] = rgb
    rgba[:, :, 3] = np.where(alpha, 255, 0).astype(np.uint8)
    return rgba


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fur_path = ID_DIR / "fur_albedo.png"
    if not fur_path.is_file():
        raise FileNotFoundError(fur_path)
    fur = np.array(Image.open(fur_path).convert("RGBA"))

    gen_blocked = (OUT_DIR / "generated" / "m2_2_generation_BLOCKED.json").is_file()
    fuse_report_path = OUT_DIR / "m2_2_fuse_report.json"
    fuse = json.loads(fuse_report_path.read_text()) if fuse_report_path.is_file() else {}
    incomplete = bool(gen_blocked or fuse.get("blocked") or len(fuse.get("views_used", ["d045"])) < 2)

    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    for name in ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]:
        obj = bpy.data.objects[name]
        if obj.data.shape_keys:
            for kb in obj.data.shape_keys.key_blocks:
                if kb.name != "Basis" and abs(kb.value) > 1e-7:
                    kb.value = 0.0
    measured = compute_uv_hash(bpy.data.objects["CAT_BODY"].data)
    if measured != EXPECTED_UV:
        raise RuntimeError(f"uv_hash mismatch {measured}")

    cells_a = []
    cells_b = []
    per_dir = {}
    for dname, yaw in DIRECTIONS:
        print(f"review {dname}", flush=True)
        hi = render_hi(fur, yaw)
        logical = downsample_to_logical(hi, GW, GH)
        layer_a = logical.copy()
        lit = apply_lantern_ao(logical[:, :, :3], logical[:, :, 3] > ALPHA_THR)
        layer_b = logical.copy()
        layer_b[:, :, :3] = lit
        ca = logical_to_canvas_2x(layer_a)
        cb = logical_to_canvas_2x(layer_b)
        # pad to cell with label
        cell_w, cell_h = 240, 240
        for layer_im, bucket in [(ca, cells_a), (cb, cells_b)]:
            cell = Image.new("RGBA", (cell_w, cell_h), (30, 32, 40, 255))
            # center paste
            im = Image.fromarray(layer_im, mode="RGBA")
            # scale to fit
            im_r = im.resize((228, 208), Image.Resampling.NEAREST)
            cell.paste(im_r, (6, 22), im_r)
            dr = ImageDraw.Draw(cell)
            tag = dname
            if incomplete and dname != "d045":
                tag += " [SEED/INCOMPLETE]"
            elif dname == "d045":
                tag += " [M2.1 OK]"
            dr.text((6, 4), tag, fill=(230, 230, 240, 255))
            bucket.append(cell)
        Image.fromarray(layer_a).save(OUT_DIR / f"m2_2_{dname}_layer_a.png")
        Image.fromarray(layer_b).save(OUT_DIR / f"m2_2_{dname}_layer_b.png")
        # 4x crops for back views of interest
        if dname in ("d045", "d135", "d180", "d225", "d090", "d270"):
            crop = Image.fromarray(layer_a).crop((20, 20, 90, 90)).resize(
                (280, 280), Image.Resampling.NEAREST
            )
            crop.save(OUT_DIR / f"m2_2_{dname}_layer_a_4x_crop.png")
        per_dir[dname] = {"yaw_deg": yaw, "incomplete_seed": incomplete and dname != "d045"}

    def make_sheet(cells, title, path):
        sheet = Image.new("RGBA", (240 * 4 + 20, 240 * 2 + 50), (18, 20, 26, 255))
        dr = ImageDraw.Draw(sheet)
        dr.text((10, 8), title, fill=(235, 235, 245, 255))
        for i, c in enumerate(cells):
            sheet.paste(c, (10 + (i % 4) * 240, 40 + (i // 4) * 240), c)
        sheet.convert("RGB").save(path)

    status = "INCOMPLETE — complementary AI blocked" if incomplete else "COMPLETE"
    make_sheet(
        cells_a,
        f"M2.2 identity_review Layer A (pure albedo) — {status}",
        OUT_DIR / "identity_review_layer_a.png",
    )
    make_sheet(
        cells_b,
        f"M2.2 identity_review Layer B (lantern+AO) — {status}",
        OUT_DIR / "identity_review_layer_b.png",
    )
    # Combined stacked
    a = Image.open(OUT_DIR / "identity_review_layer_a.png")
    b = Image.open(OUT_DIR / "identity_review_layer_b.png")
    combo = Image.new("RGB", (a.width, a.height + b.height + 8), (12, 14, 18))
    combo.paste(a, (0, 0))
    combo.paste(b, (0, a.height + 8))
    combo.save(OUT_DIR / "identity_review.png")
    # Also copy into identity_v1
    combo.save(ID_DIR / "identity_review.png")

    report = {
        "ok": not incomplete,
        "incomplete": incomplete,
        "uv_hash": measured,
        "uv_hash_unchanged": measured == EXPECTED_UV,
        "honesty": {
            "d045_silhouette": "M1 Alpha lock inherited for geometry; not new M2.2 silhouette evidence",
            "complementary_views": (
                "SEED midtone from M2.1 genome fill — NOT AI fur. Do not treat as pass."
                if incomplete
                else "AI complementary views fused"
            ),
            "authority": "4x eyeball for fur-flow and markings; auto zones soft",
        },
        "directions": per_dir,
        "outputs": {
            "identity_review": str((OUT_DIR / "identity_review.png").relative_to(ROOT)),
            "layer_a_sheet": str((OUT_DIR / "identity_review_layer_a.png").relative_to(ROOT)),
            "layer_b_sheet": str((OUT_DIR / "identity_review_layer_b.png").relative_to(ROOT)),
        },
    }
    (OUT_DIR / "m2_2_review_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
