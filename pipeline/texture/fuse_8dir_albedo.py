#!/usr/bin/env python3
"""
M2.2 — Fuse multi-view unlit albedos into fur_albedo.png + coverage.png.

Inputs:
  - d045: already projected M2.1 (kept as authoritative front-right)
  - complementary: cats/miemie/identity_v1/complementary_albedos/{d}_unlit_albedo.png
    ONLY if each has passed 4x fur-flow + markings gate (gates/*.json ok=true)

Hard rules:
  - Never mutate master UV / blend
  - Skip any view lacking a PASS gate JSON
  - Never invent procedural fur for missing views
  - Weighted by max(N·V,0)^2 per FUSED spec §4.2
"""
from __future__ import annotations

import argparse
import hashlib
import os
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
MASTER_DIR = ROOT / "art" / "master_cat"
ID_DIR = ROOT / "cats" / "miemie" / "identity_v1"
ALB_DIR = ID_DIR / "complementary_albedos"
GATE_DIR = ROOT / "docs" / "validation" / "m2_2_8dir" / "gates"
VAL_DIR = ROOT / "docs" / "validation" / "m2_2_8dir"
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
NDOTV_DIRECT = 0.50
NDOTV_GRAZE = 0.20

# --- CONTRAST EXPERIMENT ONLY (not a freeze path) ---
# Per-view multipliers on FUSED §4.2 weight max(N·V,0)^2.
# Default all 1.0. Low-d090-weight A/B test uses e.g. d090=d270=0.4.
# Env: M22_VIEW_WEIGHT_JSON='{"d090":0.4,"d270":0.4}' or CLI --view-weight d090=0.4
# Optional: reject samples darker than DARK_REJECT_LUM from down-weighted views
# (env M22_DARK_REJECT_LUM, default 0=off). Does NOT invent fur / fill red.
# Edge/graze knobs (defaults match module constants):
#   --ndotv-graze / M22_NDOTV_GRAZE  (default 0.20)
#   --edge-erode  / M22_EDGE_ERODE   (default 10)
# Raising graze reduces back/oblique writes; does NOT invent fur / fill red.
# ROI soft-down (contrast only; does NOT change default view-weight table):
#   --roi-mask PATH / M22_ROI_MASK   UV L-mask (255=ROI), typically d090 dark-inner
#   --roi-view-soft d135=0.35 / M22_ROI_VIEW_SOFT_JSON='{"d135":0.35}'
#   Inside ROI only: that view's write weight *= soft; outside ROI unchanged.
DEFAULT_VIEW_WEIGHT = {d: 1.0 for d in (
    "d000", "d045", "d090", "d135", "d180", "d225", "d270", "d315"
)}
DARK_REJECT_LUM = 0.0  # mean RGB; 0 disables

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

# High-frequency identity UV regions (from uv_manifest names)
HIGH_FREQ_REGIONS = [
    "A1_head_front",
    "A3_muzzle_chin",
    "A4_ears_LR",
    "B1_torso_L",
    "B2_torso_R",
    "B3_torso_back",
    "C1_leg_FL",
    "C2_leg_FR",
    "C3_leg_BL",
    "C4_leg_BR",
    "D1_tail",
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


def region_masks_from_manifest() -> dict[str, np.ndarray]:
    man = json.loads((MASTER_DIR / "uv_manifest.json").read_text())
    masks = {}
    for name, info in man["regions"].items():
        # expect u0,v0,u1,v1 in 0..1 or pixel boxes
        if isinstance(info, dict):
            if "uv_rect" in info:
                u0, v0, u1, v1 = info["uv_rect"]
            elif "rect" in info:
                # pixel rect on 2048
                x0, y0, x1, y1 = info["rect"]
                u0, u1 = x0 / UV_SIZE, x1 / UV_SIZE
                v0, v1 = 1.0 - y1 / UV_SIZE, 1.0 - y0 / UV_SIZE
            elif all(k in info for k in ("u0", "v0", "u1", "v1")):
                u0, v0, u1, v1 = info["u0"], info["v0"], info["u1"], info["v1"]
            else:
                continue
        else:
            continue
        m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
        # image row from top
        x0 = int(max(0, min(UV_SIZE - 1, round(u0 * (UV_SIZE - 1)))))
        x1 = int(max(0, min(UV_SIZE, round(u1 * (UV_SIZE - 1)) + 1)))
        y_top = int(max(0, min(UV_SIZE - 1, round((1.0 - v1) * (UV_SIZE - 1)))))
        y_bot = int(max(0, min(UV_SIZE, round((1.0 - v0) * (UV_SIZE - 1)) + 1)))
        m[y_top:y_bot, x0:x1] = True
        masks[name] = m
    return masks


def load_gate_passed(dname: str) -> bool:
    if dname == "d045":
        # M2.1 already user-approved
        return True
    p = GATE_DIR / f"{dname}_fur_flow_gate.json"
    if not p.is_file():
        return False
    try:
        g = json.loads(p.read_text())
        return bool(g.get("pass") or g.get("ok"))
    except Exception:
        return False


def prepare_view_rgba(dname: str) -> np.ndarray | None:
    if dname == "d045":
        return np.array(Image.open(ANCHOR_D045).convert("RGBA"))
    path = ALB_DIR / f"{dname}_unlit_albedo.png"
    if not path.is_file():
        return None
    return np.array(Image.open(path).convert("RGBA"))


def project_view_into_accum(
    tris_uv,
    tris_nrm,
    tris_px,
    tris_py,
    tris_pw,
    e_w,
    anchor_rgba,
    edge_ok,
    accum_rgb,
    accum_w,
    best_ndotv,
    coverage_best,
    view_weight: float = 1.0,
    dark_reject_lum: float = 0.0,
    roi_mask: np.ndarray | None = None,
    roi_soft: float = 1.0,
):
    """Accumulate one view into UV buffers. Returns texels written."""
    ah, aw = anchor_rgba.shape[:2]
    sx = aw / float(GW)
    sy = ah / float(GH)
    written = 0
    n_tris = len(tris_uv)
    for i in range(n_tris):
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
        ok_edge = edge_ok[ay, ax]
        vis = inside & ok_edge
        if not np.any(vis):
            # still track ndotv for coverage graze on facing
            sub_n = best_ndotv[ymin : ymax + 1, xmin : xmax + 1]
            face = inside & (ndotv > sub_n)
            if np.any(face):
                sub_n[face] = ndotv
            continue
        sampled = anchor_rgba[ay, ax].astype(np.float64)
        # FUSED §4.2 weight: max(N·V,0)^2 * per-view contrast multiplier
        w_face = (max(0.0, ndotv) ** 2) * float(view_weight)
        if w_face <= 0.0:
            continue
        sub_a = accum_rgb[ymin : ymax + 1, xmin : xmax + 1]
        sub_w = accum_w[ymin : ymax + 1, xmin : xmax + 1]
        sub_n = best_ndotv[ymin : ymax + 1, xmin : xmax + 1]
        # alpha of sample
        sa = sampled[:, :, 3] > 128
        use = vis & sa
        if dark_reject_lum > 0.0:
            lum = sampled[:, :, :3].mean(axis=2)
            use = use & (lum >= dark_reject_lum)
        if not np.any(use):
            continue
        # Optional ROI soft-down: only texels inside roi_mask get w *= roi_soft
        if roi_mask is not None and float(roi_soft) < 0.999:
            sub_roi = roi_mask[ymin : ymax + 1, xmin : xmax + 1]
            w_map = np.full(use.shape, w_face, dtype=np.float64)
            w_map[use & sub_roi] = w_face * float(roi_soft)
            sub_a[use] += sampled[use, :3] * w_map[use, None]
            sub_w[use] += w_map[use]
        else:
            sub_a[use] += sampled[use, :3] * w_face
            sub_w[use] += w_face
        better = use & (ndotv > sub_n)
        sub_n[better] = ndotv
        written += int(use.sum())
    coverage_best[best_ndotv >= NDOTV_GRAZE] = np.maximum(
        coverage_best[best_ndotv >= NDOTV_GRAZE], 1
    )
    coverage_best[best_ndotv >= NDOTV_DIRECT] = 2
    return written


def build_edge_ok(anchor_rgba, body_mask_hi):
    m = body_mask_hi.copy()
    for _ in range(EDGE_ERODE):
        nxt = m.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt &= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
        m = nxt
    return m & (anchor_rgba[:, :, 3] > 128)


def frequency_preserving_modulate(rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mild along-fur Gaussian on extrapolated/seed band only; return before/after."""
    before = rgb.copy()
    if not np.any(mask):
        return before, before
    blur = np.array(
        Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=1.25)
        ),
        dtype=np.float64,
    )
    # Preserve local luminance ratio (frequency-preserving)
    eps = 1e-3
    lum = rgb.mean(axis=2, keepdims=True) + eps
    lum_b = blur.mean(axis=2, keepdims=True) + eps
    modulated = blur * (lum / lum_b)
    after = rgb.copy()
    after[mask] = 0.7 * rgb[mask] + 0.3 * modulated[mask]
    return before, np.clip(after, 0, 255)


def parse_view_weights(cli_pairs: list[str] | None = None) -> dict[str, float]:
    """Merge DEFAULT ← env JSON ← CLI dXXX=float. Contrast experiment only."""
    weights = dict(DEFAULT_VIEW_WEIGHT)
    env = os.environ.get("M22_VIEW_WEIGHT_JSON", "").strip()
    if env:
        weights.update({k: float(v) for k, v in json.loads(env).items()})
    for pair in cli_pairs or []:
        k, v = pair.split("=", 1)
        weights[k.strip()] = float(v)
    return weights


def parse_dark_reject() -> float:
    env = os.environ.get("M22_DARK_REJECT_LUM", "").strip()
    if env:
        return float(env)
    return float(DARK_REJECT_LUM)


def parse_ndotv_graze(cli: float | None) -> float:
    if cli is not None:
        return float(cli)
    env = os.environ.get("M22_NDOTV_GRAZE", "").strip()
    if env:
        return float(env)
    return float(NDOTV_GRAZE)


def parse_edge_erode(cli: int | None) -> int:
    if cli is not None:
        return int(cli)
    env = os.environ.get("M22_EDGE_ERODE", "").strip()
    if env:
        return int(env)
    return int(EDGE_ERODE)


def parse_roi_mask(cli: str | None) -> np.ndarray | None:
    """Load UV L-mask (nonzero=ROI). CLI --roi-mask or env M22_ROI_MASK."""
    path_s = (cli or "").strip() or os.environ.get("M22_ROI_MASK", "").strip()
    if not path_s:
        return None
    p = Path(path_s)
    if not p.is_file():
        p = ROOT / path_s
    if not p.is_file():
        raise FileNotFoundError(f"ROI mask not found: {path_s}")
    arr = np.array(Image.open(p).convert("L"))
    if arr.shape != (UV_SIZE, UV_SIZE):
        raise RuntimeError(f"ROI mask shape {arr.shape} != ({UV_SIZE},{UV_SIZE})")
    return arr > 0


def parse_roi_view_soft(cli_pairs: list[str] | None = None) -> dict[str, float]:
    """Per-view soft multipliers applied ONLY inside ROI. Default empty (=1.0)."""
    soft: dict[str, float] = {}
    env = os.environ.get("M22_ROI_VIEW_SOFT_JSON", "").strip()
    if env:
        soft.update({k: float(v) for k, v in json.loads(env).items()})
    for pair in cli_pairs or []:
        k, v = pair.split("=", 1)
        soft[k.strip()] = float(v)
    return soft


def main() -> int:
    # Blender passes script args after "--"
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    ap = argparse.ArgumentParser(description="M2.2 fuse 8-dir albedo (contrast knobs optional)")
    ap.add_argument(
        "--view-weight",
        action="append",
        default=[],
        help="Contrast only: d090=0.4 (repeatable). Not a freeze path.",
    )
    ap.add_argument(
        "--dark-reject-lum",
        type=float,
        default=None,
        help="Contrast only: skip samples with mean RGB < this on down-weighted views (0=off).",
    )
    ap.add_argument(
        "--contrast-tag",
        default="",
        help="Label written into fuse report (e.g. low_d090_weight).",
    )
    ap.add_argument(
        "--ndotv-graze",
        type=float,
        default=None,
        help="Contrast: raise N·V graze floor (default 0.20). Env M22_NDOTV_GRAZE.",
    )
    ap.add_argument(
        "--edge-erode",
        type=int,
        default=None,
        help="Contrast: silhouette erode iters (default 10). Env M22_EDGE_ERODE.",
    )
    ap.add_argument(
        "--roi-mask",
        default=None,
        help="Contrast: UV L-mask path (255=ROI). Env M22_ROI_MASK. Soft applies only inside.",
    )
    ap.add_argument(
        "--roi-view-soft",
        action="append",
        default=[],
        help="Contrast: d135=0.35 soft mult inside ROI only (repeatable). Env M22_ROI_VIEW_SOFT_JSON.",
    )
    args = ap.parse_args(argv)

    VAL_DIR.mkdir(parents=True, exist_ok=True)
    ID_DIR.mkdir(parents=True, exist_ok=True)

    view_weights = parse_view_weights(args.view_weight)
    dark_reject = (
        float(args.dark_reject_lum)
        if args.dark_reject_lum is not None
        else parse_dark_reject()
    )
    contrast_tag = args.contrast_tag or os.environ.get("M22_CONTRAST_TAG", "")
    global NDOTV_GRAZE, EDGE_ERODE
    NDOTV_GRAZE = parse_ndotv_graze(args.ndotv_graze)
    EDGE_ERODE = parse_edge_erode(args.edge_erode)
    roi_mask = parse_roi_mask(args.roi_mask)
    roi_view_soft = parse_roi_view_soft(args.roi_view_soft)

    views_to_use = []
    skip = {}
    for dname in DIRECTIONS:
        if not load_gate_passed(dname):
            skip[dname] = "gate_not_passed_or_missing"
            continue
        rgba = prepare_view_rgba(dname)
        if rgba is None:
            skip[dname] = "albedo_file_missing"
            continue
        views_to_use.append(dname)

    report = {
        "ok": False,
        "stage": "M2.2_fuse_8dir",
        "views_used": views_to_use,
        "views_skipped": skip,
        "uv_hash_expected": EXPECTED_UV,
        "contrast_experiment": {
            "tag": contrast_tag or None,
            "view_weight_mult": view_weights,
            "dark_reject_lum": dark_reject,
            "ndotv_graze": NDOTV_GRAZE,
            "edge_erode": EDGE_ERODE,
            "ndotv_direct": NDOTV_DIRECT,
            "roi_mask_enabled": roi_mask is not None,
            "roi_mask_texels": int(roi_mask.sum()) if roi_mask is not None else 0,
            "roi_view_soft": roi_view_soft or None,
            "note": (
                "CONTRAST ONLY — view-weight / dark-reject / ndotv-graze / edge-erode / "
                "ROI soft-down knobs. Not a freeze; does not procedural-fill red coverage. "
                "ROI soft does not change the default global view-weight table."
            ),
        },
    }

    if "d045" not in views_to_use:
        report["error"] = "d045 anchor missing — cannot fuse"
        (VAL_DIR / "m2_2_fuse_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
        print(json.dumps(report, indent=2))
        return 2

    if len(views_to_use) < 2:
        report["blocked"] = True
        report["reason"] = (
            "Only d045 available. Complementary SDXL views not generated/gated. "
            "Refusing to fill with procedural fur. Keeping M2.1 fur_albedo as-is."
        )
        # Recompute coverage stats from existing coverage.png for honesty
        cov = np.array(Image.open(ID_DIR / "coverage.png").convert("RGB"))
        uv_man = json.loads((MASTER_DIR / "uv_manifest.json").read_text())
        # Approximate island: non-black coverage
        island = ~((cov[:, :, 0] < 10) & (cov[:, :, 1] < 10) & (cov[:, :, 2] < 10))
        green = (cov[:, :, 1] > 150) & (cov[:, :, 0] < 100) & island
        yellow = (cov[:, :, 0] > 150) & (cov[:, :, 1] > 120) & (cov[:, :, 2] < 100) & island
        red = (cov[:, :, 0] > 150) & (cov[:, :, 1] < 100) & island
        island_n = int(island.sum())
        gpy = int(green.sum() + yellow.sum())
        report["coverage"] = {
            "uv_island_texels": island_n,
            "direct_plus_graze": gpy,
            "direct_plus_graze_over_island": round(gpy / max(1, island_n), 4),
            "unseen_over_island": round(int(red.sum()) / max(1, island_n), 4),
            "gate_high_freq_green_yellow_ge_0_92": False,
            "gate_red_blind_le_0_20": False,
            "note": "M2.1 d045-only coverage retained; M2.2 fusion blocked pending GPU generation.",
        }
        report["fur_albedo_unchanged"] = True
        (VAL_DIR / "m2_2_fuse_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 2

    # Full multi-view fuse path
    blend = MASTER_DIR / "master_cat.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    body = bpy.data.objects["CAT_BODY"]
    measured = compute_uv_hash(body.data)
    if measured != EXPECTED_UV:
        raise RuntimeError(f"uv_hash mismatch {measured}")
    report["uv_hash"] = measured
    report["uv_hash_unchanged"] = True

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active.data
    vs = np.array([list(ev.matrix_world @ v.co) for v in mesh.vertices], dtype=np.float64)

    accum_rgb = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.float64)
    accum_w = np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64)
    best_ndotv = np.full((UV_SIZE, UV_SIZE), -1.0, dtype=np.float64)
    coverage = np.zeros((UV_SIZE, UV_SIZE), dtype=np.uint8)

    view_stats = {}
    for dname in views_to_use:
        yaw = DIRECTIONS[dname]
        e_u, e_v, e_w = get_camera_basis(yaw)
        px_all = ORIG_LOG[0] + (vs @ e_u) / S_LOG
        py_all = ORIG_LOG[1] - (vs @ e_v) / S_LOG
        pw_all = vs @ e_w
        tris_uv, tris_nrm, tris_px, tris_py, tris_pw = [], [], [], [], []
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
            tris_nrm.append(nrm)
            tris_px.append([px_all[i0], px_all[i1], px_all[i2]])
            tris_py.append([py_all[i0], py_all[i1], py_all[i2]])
            tris_pw.append([pw_all[i0], pw_all[i1], pw_all[i2]])
        tris_uv = np.array(tris_uv)
        tris_nrm = np.array(tris_nrm)
        tris_px = np.array(tris_px)
        tris_py = np.array(tris_py)
        tris_pw = np.array(tris_pw)

        anchor = prepare_view_rgba(dname)
        # Build silhouette mask at anchor res
        ah, aw = anchor.shape[:2]
        im_a = Image.new("L", (GW * 4, GH * 4), 0)
        draw = ImageDraw.Draw(im_a)
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
        vw = float(view_weights.get(dname, 1.0))
        # Only apply dark-reject on down-weighted views (protect d045 etc.)
        dr = dark_reject if vw < 0.999 else 0.0
        rs = float(roi_view_soft.get(dname, 1.0))
        use_roi = roi_mask if (roi_mask is not None and rs < 0.999) else None
        wcount = project_view_into_accum(
            tris_uv,
            tris_nrm,
            tris_px,
            tris_py,
            tris_pw,
            e_w,
            anchor,
            edge_ok,
            accum_rgb,
            accum_w,
            best_ndotv,
            coverage,
            view_weight=vw,
            dark_reject_lum=dr,
            roi_mask=use_roi,
            roi_soft=rs,
        )
        view_stats[dname] = {
            "texels_weighted": int(wcount),
            "yaw_deg": yaw,
            "view_weight_mult": vw,
            "dark_reject_lum_applied": dr,
            "roi_soft_mult": rs if use_roi is not None else 1.0,
            "roi_soft_active": use_roi is not None,
        }
        print(f"fused {dname}: {wcount} texels", flush=True)

    # Normalize
    rgba = np.zeros((UV_SIZE, UV_SIZE, 4), dtype=np.uint8)
    has = accum_w > 0
    rgba[has, :3] = np.clip(accum_rgb[has] / accum_w[has][:, None], 0, 255).astype(np.uint8)
    rgba[has, 3] = 255

    # UV occupancy
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

    # Seed unseen with genome base (not procedural fur grain)
    genome = json.loads((ID_DIR / "genome.json").read_text())
    base_hex = genome["coat"]["colors"]["base"].lstrip("#")
    base_rgb = np.array([int(base_hex[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.uint8)
    seed = (~has) & uv_occ
    rgba[seed, :3] = base_rgb
    rgba[seed, 3] = 255

    # Soft modulate only on graze/extrapolated band
    graze_band = (coverage == 1) & has
    before, after = frequency_preserving_modulate(rgba[:, :, :3].astype(np.float64), graze_band)
    rgba[:, :, :3] = np.clip(after, 0, 255).astype(np.uint8)

    # coverage image
    cov_img = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    cov_img[coverage == 2] = [40, 200, 70]
    cov_img[coverage == 1] = [230, 200, 40]
    cov_img[(coverage == 0) & uv_occ] = [200, 50, 50]

    Image.fromarray(rgba).save(ID_DIR / "fur_albedo.png")
    Image.fromarray(cov_img).save(ID_DIR / "coverage.png")

    # Modulation 4x compare crop
    crop = (700, 500, 900, 700)
    bf = Image.fromarray(np.clip(before, 0, 255).astype(np.uint8)).crop(crop).resize(
        (800, 800), Image.Resampling.NEAREST
    )
    af = Image.fromarray(np.clip(after, 0, 255).astype(np.uint8)).crop(crop).resize(
        (800, 800), Image.Resampling.NEAREST
    )
    cmp = Image.new("RGB", (1620, 840), (20, 22, 28))
    cmp.paste(bf, (10, 30))
    cmp.paste(af, (820, 30))
    dr = ImageDraw.Draw(cmp)
    dr.text((10, 8), "BEFORE frequency-preserving modulate (4x)", fill=(220, 220, 230))
    dr.text((820, 8), "AFTER (4x)", fill=(220, 220, 230))
    cmp.save(VAL_DIR / "m2_2_modulation_4x_compare.png")

    # Coverage gates
    island_n = int(uv_occ.sum())
    direct_n = int((coverage == 2).sum())
    graze_n = int((coverage == 1).sum())
    unseen_n = int(((coverage == 0) & uv_occ).sum())
    # High-freq mask
    try:
        rmasks = region_masks_from_manifest()
        hf = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
        for name in HIGH_FREQ_REGIONS:
            if name in rmasks:
                hf |= rmasks[name]
        if not np.any(hf):
            hf = uv_occ
    except Exception:
        hf = uv_occ
    hf_n = int(hf.sum())
    hf_gy = int(((coverage >= 1) & hf).sum())
    gy_ratio = hf_gy / max(1, hf_n)
    red_ratio = unseen_n / max(1, island_n)

    report.update(
        {
            "ok": True,
            "view_stats": view_stats,
            "coverage": {
                "uv_island_texels": island_n,
                "direct_controlled": direct_n,
                "grazing_interpolated": graze_n,
                "unseen_inpainted_or_seed": unseen_n,
                "high_freq_texels": hf_n,
                "high_freq_green_yellow": hf_gy,
                "high_freq_green_yellow_ratio": round(gy_ratio, 4),
                "unseen_over_island": round(red_ratio, 4),
                "gate_high_freq_green_yellow_ge_0_92": gy_ratio >= 0.92,
                "gate_red_blind_le_0_20": red_ratio <= 0.20,
            },
        }
    )
    (VAL_DIR / "m2_2_fuse_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    (ID_DIR / "fuse_8dir_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ev.to_mesh_clear()
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
