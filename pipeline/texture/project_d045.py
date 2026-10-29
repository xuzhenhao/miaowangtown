#!/usr/bin/env python3
"""
M2.1 Step1 — Project Route A v4.1 unlit albedo anchor into frozen 2048 UV (d045 only).

Hard rules:
  - Never mutate master_cat.blend / topology / uv_hash
  - Never project life photos; only route_a_v4_1_unlit_albedo_anchor_hi.png
  - Silhouette-edge texels are stripped (not written); interior fur-flow extrapolated
  - Camera matches M1 validate_master d045: yaw=-45, pitch=35, s_log=0.004, origin=(52.7,94.0)
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path("/workspace/miaowangtown")
MASTER_DIR = ROOT / "art" / "master_cat"
ANCHOR_PATH = ROOT / "docs" / "validation" / "route_a_v4_1_ultimate" / "route_a_v4_1_unlit_albedo_anchor_hi.png"
OUT_DIR = ROOT / "cats" / "miemie" / "identity_v1"
VAL_DIR = ROOT / "docs" / "validation" / "m2_1_d045"
UV_SIZE = 2048
GW, GH = 114, 104
S_LOG = 0.0040
ORIG_LOG = (52.7, 94.0)
YAW_DEG = -45.0
PITCH_DEG = 35.0
EDGE_ERODE_HI_PX = 10  # ~1.3 logical px on 901-wide anchor
NDOTV_DIRECT = 0.50
NDOTV_GRAZE = 0.20


def get_camera_basis(yaw_deg: float = YAW_DEG, pitch_deg: float = PITCH_DEG):
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
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def barycentric_raster_uv(
    tris_uv: np.ndarray,
    tris_pos: np.ndarray,
    tris_nrm: np.ndarray,
    tris_px: np.ndarray,
    tris_py: np.ndarray,
    tris_pw: np.ndarray,
    anchor_rgba: np.ndarray,
    edge_ok: np.ndarray,
    e_w: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """
    Rasterize body triangles into UV space and sample the d045 unlit anchor.
    Returns albedo RGBA u8, weight float, coverage class u8 (0 unseen, 1 graze, 2 direct), stats.
    """
    ah, aw = anchor_rgba.shape[:2]
    sx = aw / float(GW)
    sy = ah / float(GH)

    albedo = np.zeros((UV_SIZE, UV_SIZE, 4), dtype=np.float64)
    weight = np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64)
    best_ndotv = np.full((UV_SIZE, UV_SIZE), -1.0, dtype=np.float64)
    zbuf = np.full((UV_SIZE, UV_SIZE), -1e9, dtype=np.float64)

    n_tris = len(tris_uv)
    written = 0
    stripped_edge = 0
    backface = 0

    for i in range(n_tris):
        uv = tris_uv[i]  # 3x2 in [0,1]
        # Convert to pixel space (V=0 at bottom in Blender → image row from bottom)
        u_px = uv[:, 0] * (UV_SIZE - 1)
        v_px = (1.0 - uv[:, 1]) * (UV_SIZE - 1)  # image row from top
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
            backface += 1
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

        # Screen logical coords via barycentric of vertex projections
        px = w0 * tris_px[i, 0] + w1 * tris_px[i, 1] + w2 * tris_px[i, 2]
        py = w0 * tris_py[i, 0] + w1 * tris_py[i, 1] + w2 * tris_py[i, 2]
        pw = w0 * tris_pw[i, 0] + w1 * tris_pw[i, 1] + w2 * tris_pw[i, 2]

        ax = np.clip(np.round(px * sx).astype(np.int32), 0, aw - 1)
        ay = np.clip(np.round(py * sy).astype(np.int32), 0, ah - 1)

        sub_w = weight[ymin : ymax + 1, xmin : xmax + 1]
        sub_a = albedo[ymin : ymax + 1, xmin : xmax + 1]
        sub_z = zbuf[ymin : ymax + 1, xmin : xmax + 1]
        sub_n = best_ndotv[ymin : ymax + 1, xmin : xmax + 1]

        # Edge strip: only write if anchor edge_ok
        ok_edge = edge_ok[ay, ax]
        facing = inside & (pw >= sub_z - 1e-6)
        stripped_edge += int((inside & (~ok_edge)).sum())
        # Record facing N·V even for edge-stripped (enables interior fur-flow fill later)
        face_upd = facing & ((ndotv > sub_n + 0.02) | ((ndotv >= sub_n - 0.02) & (pw >= sub_z)))
        if np.any(face_upd):
            sub_n[face_upd] = np.maximum(sub_n[face_upd], ndotv)
            sub_z[face_upd] = np.maximum(sub_z[face_upd], pw[face_upd])

        vis = facing & ok_edge
        prefer = vis & ((ndotv > sub_n - 0.05) | (weight[ymin:ymax+1, xmin:xmax+1] == 0))
        # tighten prefer using same depth rule
        prefer = vis & (pw >= sub_z - 1e-4)
        if not np.any(prefer):
            continue

        sampled = anchor_rgba[ay, ax].astype(np.float64)
        w_face = max(0.0, ndotv) ** 1.5
        # Only overwrite when better or empty
        empty_or_better = prefer & ((sub_w == 0) | (ndotv >= sub_n - 0.02))
        if not np.any(empty_or_better):
            continue
        sub_a[empty_or_better] = sampled[empty_or_better]
        sub_w[empty_or_better] = w_face
        written += int(empty_or_better.sum())

    # Coverage classification from best_ndotv
    coverage = np.zeros((UV_SIZE, UV_SIZE), dtype=np.uint8)  # 0 unseen
    coverage[best_ndotv >= NDOTV_GRAZE] = 1  # yellow graze
    coverage[best_ndotv >= NDOTV_DIRECT] = 2  # green direct

    # Interior fur-flow extrapolation: fill UV texels that are in body islands
    # but were edge-stripped or lightly missed, from written neighbors.
    written_mask = weight > 0
    rgb = albedo[:, :, :3].copy()
    alpha = (written_mask.astype(np.float64) * 255.0)
    # Grow fill into near-misses within UV islands that already have some writes
    # Use iterative dilate of colors into empty texels adjacent to written ones (8-conn), 48 passes
    val = written_mask.copy()
    rgb_f = rgb.copy()
    for _ in range(48):
        if np.all(val):
            break
        acc = np.zeros_like(rgb_f)
        cnt = np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64)
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            sv = np.roll(np.roll(val, dy, axis=0), dx, axis=1)
            sc = np.roll(np.roll(rgb_f, dy, axis=0), dx, axis=1)
            acc += sc * sv[:, :, None]
            cnt += sv.astype(np.float64)
        # Only extrapolate into front-facing (graze/direct) texels — never flood the whole atlas.
        fill = (~val) & (cnt > 0) & (coverage > 0)
        if not np.any(fill):
            break
        rgb_f[fill] = acc[fill] / cnt[fill][:, None]
        val[fill] = True

    # Soft blur only on extrapolated band (not on direct samples) to keep fur grain
    direct = written_mask
    extrapolated = val & (~direct)
    rgb_out = rgb_f.copy()
    if np.any(extrapolated):
        blur = np.array(
            Image.fromarray(np.clip(rgb_f, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=1.2)),
            dtype=np.float64,
        )
        rgb_out[extrapolated] = 0.65 * rgb_f[extrapolated] + 0.35 * blur[extrapolated]

    rgba = np.zeros((UV_SIZE, UV_SIZE, 4), dtype=np.uint8)
    rgba[:, :, :3] = np.clip(rgb_out, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = np.where(val, 255, 0).astype(np.uint8)

    # Seed remaining empty body UVs (unseen back) with genome base midtone so atlas isn't transparent holes
    # Caller may overwrite; for now leave alpha=0 on true unseen.

    stats = {
        "triangles": int(n_tris),
        "texels_direct_written": int(written),
        "texels_edge_stripped": int(stripped_edge),
        "triangles_backface_or_graze_skip": int(backface),
        "texels_after_extrapolate": int(val.sum()),
        "coverage_direct_texels": int((coverage == 2).sum()),
        "coverage_graze_texels": int((coverage == 1).sum()),
        "coverage_unseen_texels": int((coverage == 0).sum()),
    }
    return rgba, weight, coverage, stats


def build_edge_ok_mask(anchor_rgba: np.ndarray, body_mask_hi: np.ndarray) -> np.ndarray:
    """Erode the projected body silhouette so edge-misaligned texels are not written."""
    m = body_mask_hi.copy()
    for _ in range(EDGE_ERODE_HI_PX):
        nxt = m.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt &= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
        m = nxt
    # Also require anchor alpha
    return m & (anchor_rgba[:, :, 3] > 128)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    VAL_DIR.mkdir(parents=True, exist_ok=True)

    blend = MASTER_DIR / "master_cat.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend))

    # Assert pure Basis / no cal_*
    for name in ["CAT_BODY", "CAT_EYE_L", "CAT_EYE_R", "CAT_TONGUE"]:
        obj = bpy.data.objects[name]
        if obj.data.shape_keys:
            for kb in obj.data.shape_keys.key_blocks:
                if kb.name.startswith("cal_"):
                    raise RuntimeError(f"Forbidden cal_ key present: {name}:{kb.name}")
                if kb.name != "Basis" and abs(kb.value) > 1e-7:
                    kb.value = 0.0

    body = bpy.data.objects["CAT_BODY"]
    measured_hash = compute_uv_hash(body.data)
    expected = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
    if measured_hash != expected:
        raise RuntimeError(f"uv_hash mismatch: {measured_hash} != {expected}")

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active.data

    e_u, e_v, e_w = get_camera_basis()
    vs = np.array([list(ev.matrix_world @ v.co) for v in mesh.vertices], dtype=np.float64)
    # loop normals

    tris_uv = []
    tris_pos = []
    tris_nrm = []
    tris_px = []
    tris_py = []
    tris_pw = []

    px_all = ORIG_LOG[0] + (vs @ e_u) / S_LOG
    py_all = ORIG_LOG[1] - (vs @ e_v) / S_LOG
    pw_all = vs @ e_w

    for lt in mesh.loop_triangles:
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
        tris_pos.append(pos)
        tris_nrm.append(nrm)
        tris_px.append([px_all[i0], px_all[i1], px_all[i2]])
        tris_py.append([py_all[i0], py_all[i1], py_all[i2]])
        tris_pw.append([pw_all[i0], pw_all[i1], pw_all[i2]])

    tris_uv = np.array(tris_uv, dtype=np.float64)
    tris_pos = np.array(tris_pos, dtype=np.float64)
    tris_nrm = np.array(tris_nrm, dtype=np.float64)
    tris_px = np.array(tris_px, dtype=np.float64)
    tris_py = np.array(tris_py, dtype=np.float64)
    tris_pw = np.array(tris_pw, dtype=np.float64)

    # Build hi-res body silhouette for edge erosion (same projection as M1)
    anchor = np.array(Image.open(ANCHOR_PATH).convert("RGBA"))
    ah, aw = anchor.shape[:2]
    ss = 4
    hi_w, hi_h = GW * ss, GH * ss
    im_a = Image.new("L", (hi_w, hi_h), 0)
    draw = ImageDraw.Draw(im_a)
    for t in range(len(tris_px)):
        pts = [
            ((tris_px[t, 0] + 0.35) * ss, (tris_py[t, 0] + 0.35) * ss),
            ((tris_px[t, 1] + 0.35) * ss, (tris_py[t, 1] + 0.35) * ss),
            ((tris_px[t, 2] + 0.35) * ss, (tris_py[t, 2] + 0.35) * ss),
        ]
        draw.polygon(pts, fill=255)
    # Resize silhouette to anchor resolution
    body_mask_hi = (
        np.array(im_a.resize((aw, ah), Image.Resampling.BILINEAR), dtype=np.float32) > 128
    )
    edge_ok = build_edge_ok_mask(anchor, body_mask_hi)

    # Strip emerald/catchlight/pupil eye pixels from the 2D anchor so they never bake into CAT_BODY UV.
    # Independent CAT_EYE_* meshes own eye shading at render time.
    ar = anchor[:, :, 0].astype(np.int16)
    ag = anchor[:, :, 1].astype(np.int16)
    ab = anchor[:, :, 2].astype(np.int16)
    is_eye_col = (
        ((ag > ar + 8) & (ag > 70))
        | ((ar > 220) & (ag > 205) & (ab > 190))
        | ((ar < 45) & (ag < 45) & (ab < 45) & (anchor[:, :, 3] > 128))
    )
    # Only clear eye colors inside the upper-left head band of the d045 sprite (logical eye zone scaled to hi-res)
    ah, aw = anchor.shape[:2]
    yy, xx = np.mgrid[0:ah, 0:aw]
    # logical eye box ~ x[10..35], y[30..48] on 114x104
    in_eye_band = (xx >= int(8 * aw / GW)) & (xx <= int(38 * aw / GW)) & (yy >= int(28 * ah / GH)) & (yy <= int(52 * ah / GH))
    eye_kill = is_eye_col & in_eye_band
    if np.any(eye_kill):
        # Replace with local fur by dilating non-eye valid colors
        fur_valid = (anchor[:, :, 3] > 128) & (~eye_kill)
        rgb_fix = anchor[:, :, :3].astype(np.float64)
        val = fur_valid.copy()
        for _ in range(24):
            if not np.any(eye_kill & (~val)):
                break
            acc = np.zeros_like(rgb_fix)
            cnt = np.zeros(eye_kill.shape, dtype=np.float64)
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                sv = np.roll(np.roll(val, dy, axis=0), dx, axis=1)
                sc = np.roll(np.roll(rgb_fix, dy, axis=0), dx, axis=1)
                acc += sc * sv[:, :, None]
                cnt += sv.astype(np.float64)
            fill = eye_kill & (~val) & (cnt > 0)
            rgb_fix[fill] = acc[fill] / cnt[fill][:, None]
            val[fill] = True
        anchor = anchor.copy()
        anchor[:, :, :3] = np.clip(rgb_fix, 0, 255).astype(np.uint8)

    rgba, weight, coverage, stats = barycentric_raster_uv(
        tris_uv, tris_pos, tris_nrm, tris_px, tris_py, tris_pw, anchor, edge_ok, e_w
    )

    # Fill remaining empty UV with genome base so later 8-dir has a neutral seed (alpha kept 0 for unseen?)
    # Spec: unseen = red in coverage; keep a soft base color with alpha=255 only inside UV islands that have any coverage neighbor.
    genome = json.loads((OUT_DIR / "genome.json").read_text())
    base_hex = genome["coat"]["colors"]["base"].lstrip("#")
    base_rgb = np.array([int(base_hex[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.uint8)
    empty = rgba[:, :, 3] == 0
    # Only seed texels that are clearly part of UV packing: use coverage==0 but within dilated written region
    dil = weight > 0
    for _ in range(8):
        nxt = dil.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt |= np.roll(np.roll(dil, dy, axis=0), dx, axis=1)
        dil = nxt
    # For true unseen (no graze/direct), still write base with alpha=255 inside UV island bbox from any triangle
    # Build UV occupancy from all triangles regardless of facing
    uv_occ = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    im_occ = Image.new("L", (UV_SIZE, UV_SIZE), 0)
    d_occ = ImageDraw.Draw(im_occ)
    for uvs in tris_uv:
        pts = [
            (float(uvs[j, 0] * (UV_SIZE - 1)), float((1.0 - uvs[j, 1]) * (UV_SIZE - 1)))
            for j in range(3)
        ]
        d_occ.polygon(pts, fill=255)
    uv_occ = np.array(im_occ) > 0
    seed = empty & uv_occ
    rgba[seed, 0] = base_rgb[0]
    rgba[seed, 1] = base_rgb[1]
    rgba[seed, 2] = base_rgb[2]
    rgba[seed, 3] = 255

    # coverage.png visualization: G=direct, Y=graze, R=unseen-in-island, black=outside
    cov_img = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    cov_img[(coverage == 2)] = [40, 200, 70]
    cov_img[(coverage == 1)] = [230, 200, 40]
    cov_img[(coverage == 0) & uv_occ] = [200, 50, 50]
    # Mark extrapolated band as slightly darker green/yellow
    extrapolated = (weight == 0) & (rgba[:, :, 3] > 0) & (coverage >= 1)
    cov_img[extrapolated & (coverage == 2)] = [20, 150, 90]
    cov_img[extrapolated & (coverage == 1)] = [180, 160, 30]

    Image.fromarray(rgba, mode="RGBA").save(OUT_DIR / "fur_albedo.png")
    Image.fromarray(cov_img, mode="RGB").save(OUT_DIR / "coverage.png")

    # Also save a small preview of UV albedo
    prev = Image.fromarray(rgba, mode="RGBA").resize((512, 512), Image.Resampling.BILINEAR)
    prev.save(VAL_DIR / "m2_1_fur_albedo_uv_preview_512.png")
    Image.fromarray(cov_img, mode="RGB").resize((512, 512), Image.Resampling.NEAREST).save(
        VAL_DIR / "m2_1_coverage_preview_512.png"
    )

    # Align preview: project body with albedo back to d045 logical for quick look
    # (full Layer A/B done in run_m2_1_gates.py)

    direct_n = int((coverage == 2).sum())
    graze_n = int((coverage == 1).sum())
    island_n = int(uv_occ.sum())
    unseen_in_island = int(((coverage == 0) & uv_occ).sum())
    high_freq_visible = direct_n + graze_n
    # High-identity regions approx: head+torso UV quadrants (top half + belly) — report raw ratios
    report = {
        "ok": True,
        "uv_hash": measured_hash,
        "uv_hash_unchanged": measured_hash == expected,
        "anchor": str(ANCHOR_PATH.relative_to(ROOT)),
        "camera": {
            "yaw_deg": YAW_DEG,
            "pitch_deg": PITCH_DEG,
            "scale_m_per_logical_px": S_LOG,
            "origin_logical_px": list(ORIG_LOG),
            "edge_erode_hi_px": EDGE_ERODE_HI_PX,
            "ndotv_direct": NDOTV_DIRECT,
            "ndotv_graze": NDOTV_GRAZE,
        },
        "stats": stats,
        "coverage": {
            "uv_island_texels": island_n,
            "direct_controlled": direct_n,
            "grazing_interpolated": graze_n,
            "unseen_inpainted_or_seed": unseen_in_island,
            "direct_plus_graze_over_island": round(high_freq_visible / max(1, island_n), 4),
            "unseen_over_island": round(unseen_in_island / max(1, island_n), 4),
            "note": "M2.1 is d045-only; unseen back/underside expected until M2.2. Seed uses genome base midtone.",
        },
        "outputs": {
            "fur_albedo": str((OUT_DIR / "fur_albedo.png").relative_to(ROOT)),
            "coverage": str((OUT_DIR / "coverage.png").relative_to(ROOT)),
        },
    }
    (VAL_DIR / "m2_1_project_d045_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT_DIR / "project_d045_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))

    ev.to_mesh_clear()
    # Do NOT save the blend
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
