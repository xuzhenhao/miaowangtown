#!/usr/bin/env python3
"""Export baseline d090-torso relative-dark UV ROI mask (n_dark_inner) for fuse soft-down.

ROI = fur alpha ∩ torso(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2
Matches attrib_dark_uv_views.py (12a1945). Read-only; does not mutate fur.
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

ROOT = Path(__file__).resolve().parents[2]
MASTER_DIR = ROOT / "art" / "master_cat"
ID_DIR = ROOT / "cats" / "miemie" / "identity_v1"
ALB_DIR = ID_DIR / "complementary_albedos"
OUT = ROOT / "docs" / "validation" / "m2_2_8dir" / "hold_diag"
ANCHOR_D045 = (
    ROOT
    / "docs"
    / "validation"
    / "route_a_v4_1_ultimate"
    / "route_a_v4_1_unlit_albedo_anchor_hi.png"
)
EXPECTED_UV = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
UV_SIZE = 2048
GW, GH = 114, 104
S_LOG = 0.0040
ORIG_LOG = (52.7, 94.0)
PITCH = 35.0
EDGE_ERODE = 10
NDOTV_GRAZE = 0.20
ERODE_ROI = 2


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


def torso_uv_mask() -> np.ndarray:
    man = json.loads((MASTER_DIR / "uv_manifest.json").read_text())
    m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for name in ("B1_torso_L", "B2_torso_R", "B3_torso_back", "B4_torso_belly"):
        info = man["regions"][name]
        u0, u1 = info["u_range"]
        v0, v1 = info["v_range"]
        x0 = int(u0 * (UV_SIZE - 1))
        x1 = int(u1 * (UV_SIZE - 1))
        y0 = int((1.0 - v1) * (UV_SIZE - 1))
        y1 = int((1.0 - v0) * (UV_SIZE - 1))
        m[y0 : y1 + 1, x0 : x1 + 1] = True
    return m


def erode_bool(m: np.ndarray, n: int) -> np.ndarray:
    out = m.copy()
    for _ in range(n):
        nxt = out.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt &= np.roll(np.roll(out, dy, axis=0), dx, axis=1)
        out = nxt
    return out


def build_edge_ok(anchor_rgba, body_mask_hi):
    m = body_mask_hi.copy()
    for _ in range(EDGE_ERODE):
        nxt = m.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt &= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
        m = nxt
    return m & (anchor_rgba[:, :, 3] > 128)


def prepare_view_rgba(dname: str):
    if dname == "d045":
        return np.array(Image.open(ANCHOR_D045).convert("RGBA"))
    path = ALB_DIR / f"{dname}_unlit_albedo.png"
    return np.array(Image.open(path).convert("RGBA"))


def main() -> int:
    out_dir = OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    fur_path = ID_DIR / "fur_albedo.png"
    fur = np.array(Image.open(fur_path).convert("RGBA"))
    fur_file_sha = hashlib.sha256(fur_path.read_bytes()).hexdigest()
    fur_a = fur[:, :, 3] > 128
    fur_lum = fur[:, :, :3].astype(np.float64).mean(axis=2)
    torso = torso_uv_mask()

    bpy.ops.wm.open_mainfile(filepath=str(MASTER_DIR / "master_cat.blend"))
    body = bpy.data.objects["CAT_BODY"]
    measured = compute_uv_hash(body.data)
    if measured != EXPECTED_UV:
        raise RuntimeError(f"uv_hash mismatch {measured}")
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active.data
    vs = np.array([list(ev.matrix_world @ v.co) for v in mesh.vertices], dtype=np.float64)
    loop_tris = list(mesh.loop_triangles)

    # Only d090 visibility needed for ROI
    dname = "d090"
    yaw = -90.0
    anchor = prepare_view_rgba(dname)
    e_u, e_v, e_w = get_camera_basis(yaw)
    px_all = ORIG_LOG[0] + (vs @ e_u) / S_LOG
    py_all = ORIG_LOG[1] - (vs @ e_v) / S_LOG
    ah, aw = anchor.shape[:2]
    sx = aw / float(GW)
    sy = ah / float(GH)
    im_a = Image.new("L", (GW * 4, GH * 4), 0)
    draw = ImageDraw.Draw(im_a)
    tris_uv, tris_nrm, tris_px, tris_py = [], [], [], []
    for lt in loop_tris:
        i0, i1, i2 = lt.vertices
        l0, l1, l2 = lt.loops
        uvs = np.array(
            [
                [uv_layer[l0].uv.x, uv_layer[l0].uv.y],
                [uv_layer[l1].uv.x, uv_layer[l1].uv.y],
                [uv_layer[l2].uv.x, uv_layer[l2].uv.y],
            ],
            dtype=np.float64,
        )
        pos = np.array([vs[i0], vs[i1], vs[i2]], dtype=np.float64)
        nrm = np.cross(pos[1] - pos[0], pos[2] - pos[0])
        tris_uv.append(uvs)
        tris_nrm.append(nrm)
        tris_px.append([px_all[i0], px_all[i1], px_all[i2]])
        tris_py.append([py_all[i0], py_all[i1], py_all[i2]])
        pts = [
            ((px_all[i0] + 0.35) * 4, (py_all[i0] + 0.35) * 4),
            ((px_all[i1] + 0.35) * 4, (py_all[i1] + 0.35) * 4),
            ((px_all[i2] + 0.35) * 4, (py_all[i2] + 0.35) * 4),
        ]
        draw.polygon(pts, fill=255)
    tris_uv = np.array(tris_uv)
    tris_nrm = np.array(tris_nrm)
    tris_px = np.array(tris_px)
    tris_py = np.array(tris_py)
    body_mask = (
        np.array(im_a.resize((aw, ah), Image.Resampling.BILINEAR), dtype=np.float32) > 128
    )
    edge_ok = build_edge_ok(anchor, body_mask)
    view_w = np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64)
    written = 0
    for i in range(len(tris_uv)):
        uv = tris_uv[i]
        u_px = uv[:, 0] * (UV_SIZE - 1)
        v_px = (1.0 - uv[:, 1]) * (UV_SIZE - 1)
        xmin = max(0, int(math.floor(u_px.min())))
        xmax = min(UV_SIZE - 1, int(math.ceil(u_px.max())))
        ymin = max(0, int(math.floor(v_px.min())))
        ymax = min(UV_SIZE - 1, int(math.ceil(v_px.max())))
        if xmax < xmin or ymax < ymin:
            continue
        x0, y0 = u_px[0], v_px[0]
        x1, y1 = u_px[1], v_px[1]
        x2, y2 = u_px[2], v_px[2]
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-10:
            continue
        nrm = tris_nrm[i]
        nlen = np.linalg.norm(nrm)
        if nlen < 1e-10:
            continue
        nrm = nrm / nlen
        ndotv = float(nrm @ e_w)
        if ndotv < NDOTV_GRAZE:
            continue
        yy, xx = np.meshgrid(
            np.arange(ymin, ymax + 1) + 0.5,
            np.arange(xmin, xmax + 1) + 0.5,
            indexing="ij",
        )
        w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
        w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not np.any(inside):
            continue
        px = w0 * tris_px[i, 0] + w1 * tris_px[i, 1] + w2 * tris_px[i, 2]
        py = w0 * tris_py[i, 0] + w1 * tris_py[i, 1] + w2 * tris_py[i, 2]
        ax = np.clip(np.round(px * sx).astype(np.int32), 0, aw - 1)
        ay = np.clip(np.round(py * sy).astype(np.int32), 0, ah - 1)
        vis = inside & edge_ok[ay, ax]
        if not np.any(vis):
            continue
        sampled = anchor[ay, ax].astype(np.float64)
        sa = sampled[:, :, 3] > 128
        use = vis & sa
        if not np.any(use):
            continue
        w_face = max(0.0, ndotv) ** 2
        sub_w = view_w[ymin : ymax + 1, xmin : xmax + 1]
        sub_w[use] += w_face
        written += int(use.sum())
    print(f"d090 vis texels written={written}", flush=True)

    d090_vis = view_w > 0
    d090_torso = fur_a & torso & d090_vis
    p10 = float(np.percentile(fur_lum[d090_torso], 10))
    rel_thr = max(p10, 85.0)
    dark_uv = d090_torso & (fur_lum <= rel_thr)
    dark_uv_inner = dark_uv & erode_bool(fur_a, ERODE_ROI)
    n = int(dark_uv_inner.sum())
    mask_path = out_dir / "d090_torso_dark_uv_inner_mask.png"
    Image.fromarray((dark_uv_inner.astype(np.uint8) * 255)).save(mask_path)
    meta = {
        "stage": "export_dark_roi_mask",
        "fur_file_sha256": fur_file_sha,
        "n_dark_uv_inner": n,
        "n_d090_torso": int(d090_torso.sum()),
        "rel_thr": rel_thr,
        "p10_d090_torso": p10,
        "mask": str(mask_path.relative_to(ROOT)),
        "expected_n_dark_inner_12a1945": 6283,
        "match_12a1945": n == 6283,
    }
    (out_dir / "d090_torso_dark_uv_inner_mask.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    ev.to_mesh_clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
