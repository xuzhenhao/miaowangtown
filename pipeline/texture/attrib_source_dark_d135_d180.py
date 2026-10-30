#!/usr/bin/env python3
"""Read-only: map d135/d180 source albedo pixels that write into d090 torso relative-dark UV.

No fuse / no regen / no gate change. Outputs hold_diag/source_dark_d135_d180/.
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
CTRL = ID_DIR / "control_views"
OUT = ROOT / "docs" / "validation" / "m2_2_8dir" / "hold_diag" / "source_dark_d135_d180"
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
FOCUS = ("d090", "d135", "d180", "d045")  # d090 defines set; d045 control
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


def prepare_view_rgba(dname: str):
    if dname == "d045":
        return np.array(Image.open(ANCHOR_D045).convert("RGBA"))
    path = ALB_DIR / f"{dname}_unlit_albedo.png"
    if not path.is_file():
        return None
    return np.array(Image.open(path).convert("RGBA"))


def build_edge_ok(anchor_rgba, body_mask_hi):
    m = body_mask_hi.copy()
    for _ in range(EDGE_ERODE):
        nxt = m.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt &= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
        m = nxt
    return m & (anchor_rgba[:, :, 3] > 128)


def erode_bool(m: np.ndarray, n: int) -> np.ndarray:
    out = m.copy()
    for _ in range(n):
        nxt = out.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt &= np.roll(np.roll(out, dy, axis=0), dx, axis=1)
        out = nxt
    return out


def dilate_bool(m: np.ndarray, n: int) -> np.ndarray:
    out = m.copy()
    for _ in range(n):
        nxt = out.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt |= np.roll(np.roll(out, dy, axis=0), dx, axis=1)
        out = nxt
    return out


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


def clay_body_mask(dname: str, aw: int, ah: int) -> np.ndarray:
    clay_path = CTRL / dname / "clay.png"
    if not clay_path.is_file():
        return np.zeros((ah, aw), dtype=bool)
    clay = np.array(Image.open(clay_path).convert("RGBA"))
    a = clay[:, :, 3]
    return np.array(Image.fromarray(a).resize((aw, ah), Image.Resampling.BILINEAR)) > 128


def depth_edge_mask(dname: str, aw: int, ah: int, thr: float = 18.0) -> np.ndarray:
    """Sobel-ish depth gradient high = depth discontinuity (silhouette/occlusion)."""
    dp = CTRL / dname / "depth.png"
    if not dp.is_file():
        return np.zeros((ah, aw), dtype=bool)
    d = np.array(Image.open(dp).convert("L"), dtype=np.float64)
    d = np.array(Image.fromarray(d.astype(np.uint8)).resize((aw, ah), Image.Resampling.BILINEAR), dtype=np.float64)
    gx = np.zeros_like(d)
    gy = np.zeros_like(d)
    gx[:, 1:-1] = d[:, 2:] - d[:, :-2]
    gy[1:-1, :] = d[2:, :] - d[:-2, :]
    mag = np.sqrt(gx * gx + gy * gy)
    return mag >= thr


def project_view(dname, yaw, vs, loop_tris, tris_uv, tris_nrm, store_src=False):
    """Return view_w, sample_lum_wsum, and optional source heatmaps."""
    anchor = prepare_view_rgba(dname)
    if anchor is None:
        return None
    e_u, e_v, e_w = get_camera_basis(yaw)
    px_all = ORIG_LOG[0] + (vs @ e_u) / S_LOG
    py_all = ORIG_LOG[1] - (vs @ e_v) / S_LOG
    ah, aw = anchor.shape[:2]
    sx = aw / float(GW)
    sy = ah / float(GH)
    im_a = Image.new("L", (GW * 4, GH * 4), 0)
    draw = ImageDraw.Draw(im_a)
    tris_px = np.array(
        [[px_all[lt.vertices[0]], px_all[lt.vertices[1]], px_all[lt.vertices[2]]] for lt in loop_tris],
        dtype=np.float64,
    )
    tris_py = np.array(
        [[py_all[lt.vertices[0]], py_all[lt.vertices[1]], py_all[lt.vertices[2]]] for lt in loop_tris],
        dtype=np.float64,
    )
    for t in range(len(tris_px)):
        pts = [
            ((tris_px[t, 0] + 0.35) * 4, (tris_py[t, 0] + 0.35) * 4),
            ((tris_px[t, 1] + 0.35) * 4, (tris_py[t, 1] + 0.35) * 4),
            ((tris_px[t, 2] + 0.35) * 4, (tris_py[t, 2] + 0.35) * 4),
        ]
        draw.polygon(pts, fill=255)
    body_mask = (
        np.array(im_a.resize((aw, ah), Image.Resampling.BILINEAR), dtype=np.float32) > 128
    )
    edge_ok = build_edge_ok(anchor, body_mask)
    edge_ring = body_mask & ~edge_ok  # outside eroded ok but still in silhouette

    view_w = np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64)
    lum_wsum = np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64)
    # For focus views we also need UV->source mapping into dark set later;
    # accumulate source heatmaps unconditionally for focus; dark mask applied after.
    src_w = np.zeros((ah, aw), dtype=np.float64) if store_src else None
    src_w_darkuv = np.zeros((ah, aw), dtype=np.float64) if store_src else None
    # deferred: we don't know dark_uv yet on first pass for d135/d180.
    # Store UV sample indices via sparse maps: for each UV texel keep last/mean src.
    # Memory: store ax/ay only where view writes — use int16 maps.
    src_ax = np.full((UV_SIZE, UV_SIZE), -1, dtype=np.int16) if store_src else None
    src_ay = np.full((UV_SIZE, UV_SIZE), -1, dtype=np.int16) if store_src else None
    src_ndotv = np.zeros((UV_SIZE, UV_SIZE), dtype=np.float32) if store_src else None

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
        lum = sampled[:, :, :3].mean(axis=2)
        sub_w = view_w[ymin : ymax + 1, xmin : xmax + 1]
        sub_ls = lum_wsum[ymin : ymax + 1, xmin : xmax + 1]
        sub_w[use] += w_face
        sub_ls[use] += lum[use] * w_face
        if store_src:
            # Prefer higher ndotv source coord for each UV (overwrite if stronger)
            sub_nd = src_ndotv[ymin : ymax + 1, xmin : xmax + 1]
            stronger = use & (w_face >= sub_nd)
            sy_idx, sx_idx = np.where(stronger)
            if len(sy_idx):
                src_ax[ymin : ymax + 1, xmin : xmax + 1][stronger] = ax[stronger].astype(np.int16)
                src_ay[ymin : ymax + 1, xmin : xmax + 1][stronger] = ay[stronger].astype(np.int16)
                sub_nd[stronger] = w_face
            # accumulate all contributions into source heatmap (all writes)
            np.add.at(src_w, (ay[use], ax[use]), w_face)
        written += int(use.sum())
    print(f"attrib {dname}: {written} texels", flush=True)
    return {
        "anchor": anchor,
        "body_mask": body_mask,
        "edge_ok": edge_ok,
        "edge_ring": edge_ring,
        "view_w": view_w,
        "lum_wsum": lum_wsum,
        "src_w": src_w,
        "src_ax": src_ax,
        "src_ay": src_ay,
        "src_ndotv": src_ndotv,
    }


def lum_hist(vals: np.ndarray) -> dict:
    if vals.size == 0:
        return {"n": 0}
    return {
        "n": int(vals.size),
        "mean": round(float(vals.mean()), 2),
        "p05": round(float(np.percentile(vals, 5)), 2),
        "p10": round(float(np.percentile(vals, 10)), 2),
        "p25": round(float(np.percentile(vals, 25)), 2),
        "p50": round(float(np.percentile(vals, 50)), 2),
        "p75": round(float(np.percentile(vals, 75)), 2),
        "p90": round(float(np.percentile(vals, 90)), 2),
        "frac_lt40": round(float((vals < 40).mean()), 4),
        "frac_lt60": round(float((vals < 60).mean()), 4),
        "frac_lt85": round(float((vals < 85).mean()), 4),
        "frac_lt_rel85": round(float((vals <= 85.33).mean()), 4),
    }


def colorize_heat(w: np.ndarray, base_rgb: np.ndarray) -> np.ndarray:
    """Magenta heat overlay on base image."""
    out = base_rgb.astype(np.float64).copy()
    if w.max() <= 0:
        return out.astype(np.uint8)
    # log scale for visibility
    h = np.log1p(w)
    h = h / (h.max() + 1e-9)
    mask = h > 0.02
    # blend toward magenta
    heat = np.zeros_like(out)
    heat[..., 0] = 255
    heat[..., 1] = 40 + 80 * (1 - h)
    heat[..., 2] = 255
    a = (0.25 + 0.7 * h)[..., None]
    out[mask] = (1 - a[mask]) * out[mask] + a[mask] * heat[mask]
    return np.clip(out, 0, 255).astype(np.uint8)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fur_path = ID_DIR / "fur_albedo.png"
    fur = np.array(Image.open(fur_path).convert("RGBA"))
    fur_file_sha = hashlib.sha256(fur_path.read_bytes()).hexdigest()
    fur_sha = hashlib.sha256(fur.tobytes()).hexdigest()
    fur_lum = fur[:, :, :3].astype(np.float64).mean(axis=2)
    fur_a = fur[:, :, 3] > 128
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

    tris_uv, tris_nrm = [], []
    loop_tris = list(mesh.loop_triangles)
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
    tris_uv = np.array(tris_uv)
    tris_nrm = np.array(tris_nrm)

    views = {}
    for dname in FOCUS:
        yaw = DIRECTIONS[dname]
        store = dname in ("d135", "d180", "d090", "d045")
        views[dname] = project_view(
            dname, yaw, vs, loop_tris, tris_uv, tris_nrm, store_src=store
        )

    d090_vis = views["d090"]["view_w"] > 0
    d090_torso = fur_a & torso & d090_vis
    p10 = float(np.percentile(fur_lum[d090_torso], 10))
    rel_thr = max(p10, 85.0)
    dark_uv = d090_torso & (fur_lum <= rel_thr)
    dark_uv_inner = dark_uv & erode_bool(fur_a, ERODE_ROI)
    n_dark = int(dark_uv_inner.sum())
    print(f"dark_uv_inner={n_dark} rel_thr={rel_thr:.2f} fur={fur_file_sha[:12]}", flush=True)

    # UV contribution heat for focus views on dark set
    uv_crop = (0, int((1 - 0.75) * 2047), int(0.75 * 2047), int((1 - 0.5) * 2047))
    x0, y0, x1, y1 = uv_crop

    per_view = {}
    overlay_rows = []

    for dname in ("d135", "d180", "d090", "d045"):
        v = views[dname]
        anchor = v["anchor"]
        ah, aw = anchor.shape[:2]
        lum = anchor[:, :, :3].astype(np.float64).mean(axis=2)
        ww = v["view_w"]
        mask = dark_uv_inner & (ww > 0)
        w_on_dark = float(ww[mask].sum()) if np.any(mask) else 0.0
        # sample lum on dark UV (weight-averaged)
        if np.any(mask) and w_on_dark > 0:
            mean_lum = float(v["lum_wsum"][mask].sum() / ww[mask].sum())
            # per-texel sample mean
            sample_mean = np.zeros_like(fur_lum)
            good = ww > 0
            sample_mean[good] = v["lum_wsum"][good] / ww[good]
            sample_lums = sample_mean[mask]
            pull = mask & (sample_mean < (fur_lum - 5.0))
            pull_w = float(ww[pull].sum())
        else:
            mean_lum = None
            sample_lums = np.array([])
            pull_w = 0.0

        # Map dark UV texels -> source pixels via stored ax/ay
        src_ax = v["src_ax"]
        src_ay = v["src_ay"]
        valid = mask & (src_ax >= 0)
        sax = src_ax[valid].astype(np.int32)
        say = src_ay[valid].astype(np.int32)
        sw = ww[valid]
        src_heat = np.zeros((ah, aw), dtype=np.float64)
        if sax.size:
            np.add.at(src_heat, (say, sax), sw)

        clay_body = clay_body_mask(dname, aw, ah)
        # Prefer projected body_mask (matches fuse); clay as secondary label
        body = v["body_mask"]
        edge_ok = v["edge_ok"]
        # near-edge band: within 12px of silhouette boundary, still inside edge_ok
        eroded2 = erode_bool(edge_ok, 12)
        near_edge = edge_ok & ~eroded2
        interior = eroded2
        depth_e = depth_edge_mask(dname, aw, ah, thr=18.0)
        # background-ish: not in projected body (shouldn't write) OR clay says out
        bg_like = ~body

        # contributing source pixels (where heat>0)
        contrib = src_heat > 0
        n_contrib_px = int(contrib.sum())
        src_lums = lum[contrib] if n_contrib_px else np.array([])
        # weight-weighted classification
        tw = float(src_heat.sum()) or 1.0

        def wfrac(m):
            return round(100.0 * float(src_heat[contrib & m].sum()) / tw, 2) if n_contrib_px else 0.0

        cls = {
            "weight_pct_interior": wfrac(interior),
            "weight_pct_near_edge_band12": wfrac(near_edge),
            "weight_pct_depth_edge": wfrac(depth_e),
            "weight_pct_outside_projected_body": wfrac(bg_like),  # should ~0
            "weight_pct_outside_clay_body": wfrac(~clay_body) if clay_body.any() else None,
            "weight_pct_src_lum_lt40": wfrac(lum < 40),
            "weight_pct_src_lum_lt60": wfrac(lum < 60),
            "weight_pct_src_lum_lt85": wfrac(lum <= rel_thr),
            "weight_pct_src_lum_ge_rel": wfrac(lum > rel_thr),
        }

        # bbox of contributing heat for crop
        if n_contrib_px:
            ys, xs = np.where(contrib)
            pad = 40
            by0, by1 = max(0, int(ys.min()) - pad), min(ah, int(ys.max()) + pad + 1)
            bx0, bx1 = max(0, int(xs.min()) - pad), min(aw, int(xs.max()) + pad + 1)
        else:
            by0, by1, bx0, bx1 = 0, min(ah, 400), 0, min(aw, 400)

        base_rgb = anchor[:, :, :3].copy()
        heat_img = colorize_heat(src_heat, base_rgb)
        # mark near-edge / depth-edge contributing pixels in cyan / yellow outline on crop
        mark = heat_img.copy()
        ce = contrib & near_edge
        cd = contrib & depth_e & ~near_edge
        ci_dark = contrib & interior & (lum <= rel_thr)
        mark[ce] = np.array([0, 255, 255], dtype=np.uint8)  # cyan = near silhouette edge
        mark[cd] = np.array([255, 220, 0], dtype=np.uint8)  # yellow = depth edge interior
        # keep magenta heat for interior dark via heat_img; add green dots for bright contrib
        bright = contrib & interior & (lum > rel_thr)
        mark[bright] = (0.5 * mark[bright] + 0.5 * np.array([40, 220, 40])).astype(np.uint8)

        crop_raw = base_rgb[by0:by1, bx0:bx1]
        crop_heat = heat_img[by0:by1, bx0:bx1]
        crop_mark = mark[by0:by1, bx0:bx1]
        # silhouette outline on crop
        ring = body & ~erode_bool(body, 1)
        outline = Image.fromarray(crop_mark)
        # UV weight heat panel
        uv_w = ww.copy()
        uv_w[~dark_uv_inner] = 0
        uv_base = fur[y0:y1, x0:x1, :3].copy()
        uv_heat = colorize_heat(uv_w[y0:y1, x0:x1], uv_base)
        dm = dark_uv_inner[y0:y1, x0:x1]
        uv_dark = uv_base.copy()
        uv_dark[dm] = np.array([255, 40, 255], dtype=np.uint8)

        # sheet: UV dark | UV weight | source crop | source heat | classified
        ch = by1 - by0
        cw = bx1 - bx0
        uv_h = y1 - y0
        uv_wdt = x1 - x0
        # scale source crops to uv_h height
        def fit_h(arr, th):
            im = Image.fromarray(arr)
            nh = th
            nw = max(1, int(round(arr.shape[1] * (th / max(1, arr.shape[0])))))
            return np.array(im.resize((nw, nh), Image.Resampling.NEAREST))

        c1 = fit_h(crop_raw, uv_h)
        c2 = fit_h(crop_heat, uv_h)
        c3 = fit_h(crop_mark, uv_h)
        gap = 12
        total_w = uv_wdt * 2 + c1.shape[1] + c2.shape[1] + c3.shape[1] + gap * 6
        sheet = Image.new("RGB", (total_w, uv_h + 70), (18, 20, 26))
        dr = ImageDraw.Draw(sheet)
        x = gap
        for img, label in [
            (uv_dark, f"{dname}: UV magenta=d090-dark"),
            (uv_heat, f"{dname}: UV write-weight on dark"),
            (c1, f"{dname}: source crop"),
            (c2, f"{dname}: source heat (contrib)"),
            (c3, "cyan=near-edge yellow=depth-edge"),
        ]:
            sheet.paste(Image.fromarray(img), (x, 50))
            dr.text((x, 8), label, fill=(220, 220, 230))
            x += img.shape[1] + gap
        sheet_path = OUT / f"overlay_{dname}_source_on_d090_dark.png"
        sheet.save(sheet_path)

        # also save full-res source heat
        Image.fromarray(heat_img).save(OUT / f"source_heat_full_{dname}.png")

        alb_path = ALB_DIR / f"{dname}_unlit_albedo.png"
        if dname == "d045":
            alb_sha = hashlib.sha256(ANCHOR_D045.read_bytes()).hexdigest()
        else:
            alb_sha = hashlib.sha256(alb_path.read_bytes()).hexdigest() if alb_path.is_file() else None

        # whole-body source stats for context
        body_lums = lum[edge_ok]
        per_view[dname] = {
            "albedo_file_sha256": alb_sha,
            "n_dark_uv_with_write": int(mask.sum()),
            "weight_on_dark_set": round(w_on_dark, 4),
            "pull_down_weight": round(pull_w, 4),
            "mean_sample_lum_on_dark_uv": None if mean_lum is None else round(mean_lum, 2),
            "sample_lum_hist_on_dark_uv": lum_hist(sample_lums),
            "n_unique_source_px_contributing": n_contrib_px,
            "source_lum_hist_contributing_px": lum_hist(src_lums),
            "source_lum_hist_edge_ok_body": lum_hist(body_lums),
            "classification_weight_pct": cls,
            "contrib_bbox_xyxy": [bx0, by0, bx1, by1],
            "overlay": str(sheet_path.relative_to(ROOT)),
        }
        print(
            f"{dname}: mean_sample={mean_lum} interior%={cls['weight_pct_interior']} "
            f"near_edge%={cls['weight_pct_near_edge_band12']} depth_edge%={cls['weight_pct_depth_edge']} "
            f"lt85%={cls['weight_pct_src_lum_lt85']}",
            flush=True,
        )

    # Compare d135/d180 vs d090 source on same dark UV set
    # Honest call
    def call_for(d):
        c = per_view[d]["classification_weight_pct"]
        hist = per_view[d]["source_lum_hist_contributing_px"]
        mean_s = per_view[d]["mean_sample_lum_on_dark_uv"]
        parts = []
        if c["weight_pct_outside_projected_body"] > 5:
            parts.append("投影落到剪影外（背景泄漏）")
        if c["weight_pct_near_edge_band12"] >= 35:
            parts.append("贡献集中在 depth/剪影近缘带")
        if c["weight_pct_depth_edge"] >= 25 and c["weight_pct_near_edge_band12"] < 35:
            parts.append("贡献叠在 depth 不连续带（遮挡/褶皱边缘）")
        if c["weight_pct_interior"] >= 55 and c["weight_pct_src_lum_lt85"] >= 40:
            parts.append("主责=源图岛内躯干相对过暗（非边缘泄漏）")
        if c["weight_pct_interior"] >= 55 and c["weight_pct_src_lum_lt85"] < 40:
            parts.append("源采样并不特别暗→更像多向加权/几何把偏暗邻域平均进来")
        if mean_s is not None and mean_s > rel_thr + 10:
            parts.append(f"该向写入暗带的均亮 {mean_s:.0f}>rel_thr，自身不是拉低主因")
        if mean_s is not None and mean_s <= rel_thr:
            parts.append(f"该向写入暗带的均亮 {mean_s:.0f}≤rel_thr，确认拉低")
        if not parts:
            parts.append("混合：见 classification 与 hist")
        return "；".join(parts)

    # total weight shares among d135/d180/d090/d045 on dark set
    wsum = sum(per_view[d]["weight_on_dark_set"] for d in ("d135", "d180", "d090", "d045")) or 1.0
    share4 = {
        d: round(100.0 * per_view[d]["weight_on_dark_set"] / wsum, 2)
        for d in ("d135", "d180", "d090", "d045")
    }
    psum = sum(per_view[d]["pull_down_weight"] for d in ("d135", "d180", "d090", "d045")) or 1.0
    pull4 = {
        d: round(100.0 * per_view[d]["pull_down_weight"] / psum, 2)
        for d in ("d135", "d180", "d090", "d045")
    }

    # Combined verdict
    verdict_parts = []
    for d in ("d135", "d180"):
        verdict_parts.append(f"{d}: {call_for(d)}")
    # Suggest regen?
    suggest = []
    for d in ("d135", "d180"):
        c = per_view[d]["classification_weight_pct"]
        mean_s = per_view[d]["mean_sample_lum_on_dark_uv"]
        if mean_s is not None and mean_s <= rel_thr and c["weight_pct_interior"] >= 50:
            suggest.append(
                {
                    "view": d,
                    "action": "controlled_local_ROI_regen_candidate",
                    "reason": (
                        f"写入 d090 相对暗带的源均亮 {mean_s}≤rel_thr，"
                        f"且 {c['weight_pct_interior']}% 权重在岛内（非边缘主责）；"
                        "可考虑仅侧躯干 ROI / 调提示提亮躯干 / 换 seed——"
                        "禁止整向假绿、禁程序化填红；等制作人拍板。"
                    ),
                }
            )
        elif c["weight_pct_near_edge_band12"] >= 40:
            suggest.append(
                {
                    "view": d,
                    "action": "no_blind_regen_check_edge_or_prompt_fringe",
                    "reason": "贡献偏近缘→先查源边缘脏边/提示，不整向重生。",
                }
            )
        else:
            suggest.append(
                {
                    "view": d,
                    "action": "hold_for_producer",
                    "reason": call_for(d),
                }
            )

    one_liner = (
        "d135/d180 写入 d090 侧躯干相对暗带的采样，主责偏源图岛内躯干偏暗（非背景近黑泄漏）；"
        f"四向对照权重 d135={share4['d135']}% d180={share4['d180']}% "
        f"d090={share4['d090']}% d045={share4['d045']}%。"
    )
    # refine one_liner from actual classification
    int_dark = all(
        per_view[d]["classification_weight_pct"]["weight_pct_interior"] >= 50
        and per_view[d]["mean_sample_lum_on_dark_uv"] is not None
        and per_view[d]["mean_sample_lum_on_dark_uv"] <= rel_thr + 5
        for d in ("d135", "d180")
    )
    edge_dom = any(
        per_view[d]["classification_weight_pct"]["weight_pct_near_edge_band12"] >= 40
        for d in ("d135", "d180")
    )
    if int_dark and not edge_dom:
        one_liner = (
            "主责= d135/d180 源图岛内躯干相对过暗被投影写入 d090 侧躯干相对暗带；"
            "非剪影外背景泄漏，近缘带非主导；graze 拧不动符合此结论。"
        )
    elif edge_dom:
        one_liner = (
            "主责偏 d135/d180 源近缘/depth 边缘脏采样写入；"
            "非单纯岛内过暗——结构上仍禁盲拧 view-weight。"
        )

    report = {
        "stage": "d135_d180_source_dark_on_d090_torso",
        "read_only": True,
        "fur_file_sha256": fur_file_sha,
        "fur_sha256_pixels": fur_sha,
        "uv_hash": measured,
        "constants": {
            "EDGE_ERODE": EDGE_ERODE,
            "NDOTV_GRAZE": NDOTV_GRAZE,
            "rel_thr": rel_thr,
            "p10_d090_torso": p10,
            "ERODE_ROI_alpha": ERODE_ROI,
            "view_weight": "attribution all 1.0 (matches prior UV attrib; no fuse)",
        },
        "n_dark_uv_inner": n_dark,
        "focus_weight_share_pct_on_dark": share4,
        "focus_pull_down_share_pct": pull4,
        "per_view": per_view,
        "call_per_view": {d: call_for(d) for d in ("d135", "d180", "d090", "d045")},
        "one_line_verdict": one_liner,
        "regen_suggestions_for_producer_only": suggest,
        "constraints": (
            "No auto regen / no fuse / no freeze / no M3 / no procedural red fill / "
            "no view-weight. d270 stays rolled-back PASS. EDGE/graze unchanged."
        ),
    }

    out_json = OUT / "d135_d180_source_dark_on_d090_torso.json"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    # Markdown (Chinese)
    md_lines = [
        "# d135/d180 源图暗采样 → d090 侧躯干相对暗带（只读归因）",
        "",
        f"**时间**：2026-10-30（Asia/Shanghai）",
        f"**fur file sha**：`{fur_file_sha[:12]}…`（工作树未改）",
        f"**rel_thr**：{rel_thr:.2f}（p10={p10:.2f}）· **n_dark_inner**：{n_dark}",
        f"**参数**：EDGE_ERODE={EDGE_ERODE}，NDOTV_GRAZE={NDOTV_GRAZE}（未改）；不 fuse / 不重生 / 不冻",
        "",
        "## 一句话结论",
        "",
        one_liner,
        "",
        "## 四向对照（仅权重记账，非全 8 向）",
        "",
        "| 向 | 暗带写入权重% | pull-down% | 源均亮@暗带 | 岛内% | 近缘带12px% | depth缘% | 源≤rel% |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for d in ("d135", "d180", "d090", "d045"):
        c = per_view[d]["classification_weight_pct"]
        ml = per_view[d]["mean_sample_lum_on_dark_uv"]
        md_lines.append(
            f"| {d} | {share4[d]} | {pull4[d]} | {ml} | "
            f"{c['weight_pct_interior']} | {c['weight_pct_near_edge_band12']} | "
            f"{c['weight_pct_depth_edge']} | {c['weight_pct_src_lum_lt85']} |"
        )
    md_lines += ["", "## 分向判定", ""]
    for d in ("d135", "d180", "d090", "d045"):
        md_lines.append(f"- **{d}**：{call_for(d)}")
        h = per_view[d]["source_lum_hist_contributing_px"]
        if h.get("n"):
            md_lines.append(
                f"  - 贡献源像素 lum：n={h['n']} mean={h['mean']} "
                f"p10={h['p10']} p50={h['p50']} frac≤85={h['frac_lt_rel85']} frac<40={h['frac_lt40']}"
            )
    md_lines += [
        "",
        "## 是否建议受控重生（仅候选，等制作人拍板）",
        "",
    ]
    for s in suggest:
        md_lines.append(f"- **{s['view']}** · `{s['action']}`：{s['reason']}")
    md_lines += [
        "",
        "## 分类图例（overlay）",
        "",
        "- 品红热力：该向对 d090 相对暗带 UV 的写入权重 / 源像素贡献",
        "- 青：近剪影缘带（edge_ok 内 12px）",
        "- 黄：depth 梯度高且非近缘（遮挡/褶皱）",
        "- 绿偏：岛内但源 lum > rel_thr（亮采样仍写入暗带）",
        "",
        "## 路径",
        "",
        f"- 目录：`{OUT.relative_to(ROOT)}/`",
        f"- json：`{out_json.relative_to(ROOT)}`",
        f"- 本文：`{(OUT / 'D135_D180_SOURCE_DARK_ON_D090_TORSO.md').relative_to(ROOT)}`",
        "- overlays：`overlay_{d135,d180,d090,d045}_source_on_d090_dark.png`",
        "",
        "## 约束（本任务已遵守）",
        "",
        "- 只读归因；未改 fur / 未 fuse / 未重生 / 未动 EDGE·graze·view-weight",
        "- d270 维持回滚 PASS；不冻、不开 M3、禁程序化填红、不交用户点2",
        "",
    ]
    md_path = OUT / "D135_D180_SOURCE_DARK_ON_D090_TORSO.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    # short alias
    (OUT / "SOURCE_DARK_ATTRIB.md").write_text(
        "\n".join(
            [
                "# 源图暗采样归因（短）",
                "",
                one_liner,
                "",
                f"详情见 `D135_D180_SOURCE_DARK_ON_D090_TORSO.md` / `{out_json.name}`。",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # also copy key md name at hold_diag root for discoverability
    root_md = OUT.parent / "D135_D180_SOURCE_DARK_ON_D090_TORSO.md"
    root_md.write_text(
        f"# 见子目录\n\n完整报告：[`source_dark_d135_d180/D135_D180_SOURCE_DARK_ON_D090_TORSO.md`]"
        f"(source_dark_d135_d180/D135_D180_SOURCE_DARK_ON_D090_TORSO.md)\n\n"
        f"**一句话**：{one_liner}\n",
        encoding="utf-8",
    )

    print(json.dumps({"ok": True, "one_line": one_liner, "json": str(out_json)}, ensure_ascii=False), flush=True)
    ev.to_mesh_clear()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
