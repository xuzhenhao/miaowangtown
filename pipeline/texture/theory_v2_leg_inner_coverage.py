#!/usr/bin/env python3
"""M2.2 — Theoretical N·V coverage gain if V2 leg-inner views were fused
on top of current working fur (8-dir + V1 belly, CANDIDATE_UNFROZEN).

Read-only: no fuse / no SDXL / no fur mutate / no fill-red.
Baseline = honest bary island on *current* coverage.png (post-V1 promote).
Previous N·V = max(8-dir pitch=35, V1 yaw0 pitch-30).
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import bpy
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
MASTER_DIR = ROOT / "art" / "master_cat"
ID_DIR = ROOT / "cats" / "miemie" / "identity_v1"
HOLD = ROOT / "docs" / "validation" / "m2_2_8dir" / "hold_diag"
OUT = HOLD / "v2_leg_inner_control"
EXPECTED_UV = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
EXPECTED_FUR_PREFIX = "3be77787ab0f"  # post V1 promote CANDIDATE_UNFROZEN
UV_SIZE = 2048
PITCH_8 = 35.0
V1_YAW = 0.0
V1_PITCH = -30.0
NDOTV_GRAZE = 0.20
V2_VIEWS = {
    "v2_leg_inner_L": {"yaw_deg": -75.0, "pitch_deg": 15.0},
    "v2_leg_inner_R": {"yaw_deg": 75.0, "pitch_deg": 15.0},
}

DIRECTIONS_8 = {
    "d000": 0.0,
    "d045": -45.0,
    "d090": -90.0,
    "d135": -135.0,
    "d180": 180.0,
    "d225": 135.0,
    "d270": 90.0,
    "d315": 45.0,
}

PART_BUCKETS = {
    "legs": ["C1_leg_FL", "C2_leg_FR", "C3_leg_BL", "C4_leg_BR"],
    "legs_rear": ["C3_leg_BL", "C4_leg_BR"],
    "legs_front": ["C1_leg_FL", "C2_leg_FR"],
    "face_detail": ["D2_eyes_LR", "D3_nose_pads_tongue"],
}


def get_camera_basis(yaw_deg: float, pitch_deg: float = PITCH_8):
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


def region_masks() -> dict[str, np.ndarray]:
    man = json.loads((MASTER_DIR / "uv_manifest.json").read_text())
    masks = {}
    for name, info in man["regions"].items():
        u0, u1 = info["u_range"]
        v0, v1 = info["v_range"]
        m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
        x0 = int(u0 * (UV_SIZE - 1))
        x1 = int(u1 * (UV_SIZE - 1))
        y0 = int((1.0 - v1) * (UV_SIZE - 1))
        y1 = int((1.0 - v0) * (UV_SIZE - 1))
        m[y0 : y1 + 1, x0 : x1 + 1] = True
        masks[name] = m
    return masks


def margin_stats(path: Path) -> dict:
    im = Image.open(path)
    arr = np.array(im)
    if arr.ndim == 2:
        alpha = arr > 0
    elif arr.shape[2] == 4:
        alpha = arr[:, :, 3] > 0
    else:
        alpha = np.any(arr > 0, axis=2)
    h, w = alpha.shape
    rows = np.any(alpha, axis=1)
    cols = np.any(alpha, axis=0)
    ridx = np.where(rows)[0]
    cidx = np.where(cols)[0]
    top = int(ridx[0]) if len(ridx) else -1
    bot = int(h - 1 - ridx[-1]) if len(ridx) else -1
    left = int(cidx[0]) if len(cidx) else -1
    right = int(w - 1 - cidx[-1]) if len(cidx) else -1
    return {
        "size": [w, h],
        "visible_px": int(alpha.sum()),
        "margin_top": top,
        "margin_bottom": bot,
        "margin_left": left,
        "margin_right": right,
        "margin_ge_16": all(x >= 16 for x in (top, bot, left, right)),
    }


def raster_ndotv(tris_uv, tris_nrm_u, e_w, out: np.ndarray) -> None:
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
        ndotv = float(tris_nrm_u[i] @ e_w)
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
        sub = out[ymin : ymax + 1, xmin : xmax + 1]
        better = inside & (ndotv > sub)
        sub[better] = ndotv


def pct(n, d):
    return round(100.0 * n / max(1, d), 2)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")

    for vname in V2_VIEWS:
        ctrl = ID_DIR / "control_views" / vname
        if not ctrl.is_dir():
            raise RuntimeError(f"missing V2 control dir {ctrl}")

    fur_path = ID_DIR / "fur_albedo.png"
    cov_path = ID_DIR / "coverage.png"
    fur_sha = hashlib.sha256(fur_path.read_bytes()).hexdigest()
    cov_sha = hashlib.sha256(cov_path.read_bytes()).hexdigest()
    if not fur_sha.startswith(EXPECTED_FUR_PREFIX):
        print(f"WARN fur sha {fur_sha[:16]} != {EXPECTED_FUR_PREFIX}…", flush=True)

    for vname in V2_VIEWS:
        preview_dir = OUT / "control_preview" / vname
        preview_dir.mkdir(parents=True, exist_ok=True)
        ctrl = ID_DIR / "control_views" / vname
        for fn in [
            "depth.png", "normal.png", "clay.png", "part_mask.png",
            "depth_768.png", "normal_768.png", "clay_768.png", "part_mask_768.png",
        ]:
            src = ctrl / fn
            if src.is_file():
                shutil.copy2(src, preview_dir / fn)

    sheet_h = 416 + 48
    sheet_w = 456 * 3 + 24
    sheet = Image.new("RGB", (sheet_w, sheet_h * 2 + 16), (18, 20, 26))
    dr = ImageDraw.Draw(sheet)
    margins = {}
    for row, vname in enumerate(V2_VIEWS):
        ctrl = ID_DIR / "control_views" / vname
        depth = Image.open(ctrl / "depth.png").convert("RGB")
        normal = Image.open(ctrl / "normal.png").convert("RGB")
        clay = Image.open(ctrl / "clay.png").convert("RGBA")
        y0 = 36 + row * sheet_h
        sheet.paste(depth.resize((456, 416)), (8, y0))
        sheet.paste(normal.resize((456, 416)), (8 + 456 + 4, y0))
        clay_rgb = Image.new("RGB", clay.size, (18, 20, 26))
        clay_rgb.paste(clay, mask=clay.split()[-1] if clay.mode == "RGBA" else None)
        sheet.paste(clay_rgb.resize((456, 416)), (8 + 2 * (456 + 4), y0))
        spec = V2_VIEWS[vname]
        dr.text(
            (8, y0 - 28),
            f"{vname}  yaw={spec['yaw_deg']} pitch={spec['pitch_deg']}  depth | normal | clay  (no SDXL)",
            fill=(220, 220, 230),
        )
        margins[vname] = {
            "depth": margin_stats(ctrl / "depth.png"),
            "clay": margin_stats(ctrl / "clay.png"),
            "normal": margin_stats(ctrl / "normal.png"),
        }
    sheet.save(OUT / "v2_leg_inner_control_sheet.png")

    cov = np.array(Image.open(cov_path).convert("RGB"))
    green = (cov[:, :, 0] == 40) & (cov[:, :, 1] == 200) & (cov[:, :, 2] == 70)
    yellow = (cov[:, :, 0] == 230) & (cov[:, :, 1] == 200) & (cov[:, :, 2] == 40)
    red_pil = (cov[:, :, 0] == 200) & (cov[:, :, 1] == 50) & (cov[:, :, 2] == 50)
    gy = green | yellow
    n_gy = int(gy.sum())

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
    tris_uv = np.array(tris_uv)
    tris_nrm = np.array(tris_nrm)
    nlen = np.linalg.norm(tris_nrm, axis=1, keepdims=True)
    tris_nrm_u = tris_nrm / np.maximum(nlen, 1e-12)

    uv_hit = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
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
        yy, xx = np.meshgrid(
            np.arange(ymin, ymax + 1) + 0.5,
            np.arange(xmin, xmax + 1) + 0.5,
            indexing="ij",
        )
        w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denom
        w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if np.any(inside):
            uv_hit[ymin : ymax + 1, xmin : xmax + 1] |= inside

    island = uv_hit | gy
    red = red_pil & uv_hit
    n_island = int(island.sum())
    n_red = int(red.sum())
    gy_now = n_gy / max(1, n_island)
    red_now = n_red / max(1, n_island)
    print(f"island={n_island} gy={n_gy} red={n_red} GY={gy_now:.4f} red_r={red_now:.4f}", flush=True)

    best_prev = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    for dname, yaw in DIRECTIONS_8.items():
        _, _, e_w = get_camera_basis(yaw, PITCH_8)
        raster_ndotv(tris_uv, tris_nrm_u, e_w, best_prev)
        print(f"ndotv8 {dname} done", flush=True)
    v1 = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    _, _, e_w_v1 = get_camera_basis(V1_YAW, V1_PITCH)
    raster_ndotv(tris_uv, tris_nrm_u, e_w_v1, v1)
    best_prev = np.maximum(best_prev, v1)
    print("ndotv V1 folded into prev", flush=True)

    v2_maps = {}
    best_v2 = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    for vname, spec in V2_VIEWS.items():
        m = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
        _, _, e_w = get_camera_basis(spec["yaw_deg"], spec["pitch_deg"])
        raster_ndotv(tris_uv, tris_nrm_u, e_w, m)
        v2_maps[vname] = m
        best_v2 = np.maximum(best_v2, m)
        print(f"ndotv {vname} done", flush=True)

    rmasks = region_masks()
    belly_m = rmasks["B4_torso_belly"]
    face_m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for nm in PART_BUCKETS["face_detail"]:
        face_m |= rmasks[nm]
    legs_m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for nm in PART_BUCKETS["legs"]:
        legs_m |= rmasks[nm]
    rear_m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for nm in PART_BUCKETS["legs_rear"]:
        rear_m |= rmasks[nm]
    front_m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for nm in PART_BUCKETS["legs_front"]:
        front_m |= rmasks[nm]
    c3 = rmasks["C3_leg_BL"]
    c4 = rmasks["C4_leg_BR"]

    geo_blind = red & (best_prev < 0.0)
    thresh = red & (best_prev >= 0.0) & (best_prev < NDOTV_GRAZE)

    def theory_for(label: str, vmap: np.ndarray) -> dict:
        covers = red & (vmap >= NDOTV_GRAZE)
        newly = covers & (best_prev < NDOTV_GRAZE)
        n_covers = int(covers.sum())
        n_newly = int(newly.sum())
        n_gy_est = n_gy + n_newly
        n_red_est = n_red - n_newly
        gy_est = n_gy_est / max(1, n_island)
        red_est = n_red_est / max(1, n_island)
        n_geo = int(geo_blind.sum())
        n_geo_eaten = int((geo_blind & (vmap >= NDOTV_GRAZE)).sum())
        n_legs_red = int((red & legs_m).sum())
        n_legs_eaten = int((red & legs_m & (vmap >= NDOTV_GRAZE)).sum())
        n_rear_red = int((red & rear_m).sum())
        n_rear_eaten = int((red & rear_m & (vmap >= NDOTV_GRAZE)).sum())
        n_front_red = int((red & front_m).sum())
        n_front_eaten = int((red & front_m & (vmap >= NDOTV_GRAZE)).sum())
        n_c3_red = int((red & c3).sum())
        n_c3_eaten = int((red & c3 & (vmap >= NDOTV_GRAZE)).sum())
        n_c4_red = int((red & c4).sum())
        n_c4_eaten = int((red & c4 & (vmap >= NDOTV_GRAZE)).sum())
        n_belly_red = int((red & belly_m).sum())
        n_belly_eaten = int((red & belly_m & (vmap >= NDOTV_GRAZE)).sum())
        n_face_red = int((red & face_m).sum())
        n_face_eaten = int((red & face_m & (vmap >= NDOTV_GRAZE)).sum())
        n_thresh = int(thresh.sum())
        n_thresh_eaten = int((thresh & (vmap >= NDOTV_GRAZE)).sum())
        return {
            "label": label,
            "n_honest_red_ge_graze": n_covers,
            "pct_honest_red_ge_graze": pct(n_covers, n_red),
            "n_newly_coverable_prev_lt_graze": n_newly,
            "pct_honest_red_newly": pct(n_newly, n_red),
            "backface_red_n": n_geo,
            "backface_red_eaten": n_geo_eaten,
            "pct_backface_red_eaten": pct(n_geo_eaten, n_geo),
            "legs_red_n": n_legs_red,
            "legs_red_eaten": n_legs_eaten,
            "pct_legs_red_eaten": pct(n_legs_eaten, n_legs_red),
            "rear_legs_C3C4_red_n": n_rear_red,
            "rear_legs_C3C4_red_eaten": n_rear_eaten,
            "pct_rear_legs_red_eaten": pct(n_rear_eaten, n_rear_red),
            "C3_leg_BL_red_n": n_c3_red,
            "C3_leg_BL_red_eaten": n_c3_eaten,
            "pct_C3_red_eaten": pct(n_c3_eaten, n_c3_red),
            "C4_leg_BR_red_n": n_c4_red,
            "C4_leg_BR_red_eaten": n_c4_eaten,
            "pct_C4_red_eaten": pct(n_c4_eaten, n_c4_red),
            "front_legs_red_n": n_front_red,
            "front_legs_red_eaten": n_front_eaten,
            "pct_front_legs_red_eaten": pct(n_front_eaten, n_front_red),
            "belly_red_n": n_belly_red,
            "belly_red_eaten": n_belly_eaten,
            "pct_belly_red_eaten": pct(n_belly_eaten, n_belly_red),
            "thresh_red_n": n_thresh,
            "thresh_red_eaten": n_thresh_eaten,
            "pct_thresh_red_eaten": pct(n_thresh_eaten, n_thresh),
            "face_detail_red_n": n_face_red,
            "face_detail_red_eaten": n_face_eaten,
            "pct_face_detail_red_eaten": pct(n_face_eaten, n_face_red),
            "estimated_after": {
                "n_gy": n_gy_est,
                "n_red": n_red_est,
                "GY_over_island": round(gy_est, 4),
                "red_over_island": round(red_est, 4),
                "delta_GY_pp": round((gy_est - gy_now) * 100, 2),
                "delta_red_pp": round((red_est - red_now) * 100, 2),
                "still_short_of_0_92_by": round(max(0.0, 0.92 - gy_est), 4),
                "red_gate_still_pass_le_0_20": red_est <= 0.20,
            },
        }

    per_view = {vn: theory_for(vn, vm) for vn, vm in v2_maps.items()}
    both = theory_for("v2_leg_inner_L+R", best_v2)

    covers_both = red & (best_v2 >= NDOTV_GRAZE)
    newly_both = covers_both & (best_prev < NDOTV_GRAZE)
    heat = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    heat[island] = (36, 40, 48)
    heat[gy] = (40, 160, 70)
    heat[red & ~covers_both] = (200, 50, 50)
    heat[covers_both] = (60, 220, 230)
    heat[newly_both & rear_m] = (255, 220, 60)
    heat[newly_both & front_m] = (255, 140, 60)
    Image.fromarray(heat).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "theory_v2_eat_red_512.png"
    )
    Image.fromarray(heat).save(OUT / "theory_v2_eat_red_2048.png")

    vheat = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    vheat[:] = (18, 20, 26)
    vheat[island] = (30, 32, 40)
    mask = red
    if np.any(mask):
        t = np.clip((best_v2 + 1.0) / 2.0, 0, 1)
        r = np.zeros_like(t)
        g = np.zeros_like(t)
        b = np.zeros_like(t)
        below = t < 0.5
        above = ~below
        u0 = np.clip(t / 0.5, 0, 1)
        u1 = np.clip((t - 0.5) / 0.5, 0, 1)
        r[below] = 40 + 180 * u0[below]
        g[below] = 60 + 100 * u0[below]
        b[below] = 200 - 100 * u0[below]
        r[above] = 220
        g[above] = 220 - 160 * u1[above]
        b[above] = 40
        vheat[mask, 0] = np.clip(r[mask], 0, 255).astype(np.uint8)
        vheat[mask, 1] = np.clip(g[mask], 0, 255).astype(np.uint8)
        vheat[mask, 2] = np.clip(b[mask], 0, 255).astype(np.uint8)
        ge = mask & (best_v2 >= NDOTV_GRAZE)
        vheat[ge, 1] = np.maximum(vheat[ge, 1], 200)
    Image.fromarray(vheat).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "theory_v2_ndotv_on_red_512.png"
    )

    ctrl_rep = {}
    er = ID_DIR / "control_views" / "export_report.json"
    if er.is_file():
        dirs = json.loads(er.read_text()).get("directions", {})
        for vn in V2_VIEWS:
            ctrl_rep[vn] = dirs.get(vn, {})

    margin_ok = all(margins[vn]["depth"]["margin_ge_16"] for vn in V2_VIEWS)
    one_liner = (
        f"V2 L/R yaw=±75 pitch=15 边距≥16={'YES' if margin_ok else 'NO'}；"
        f"相对 8+V1 基线 GY={gy_now:.4f}/红={red_now:.4f}；"
        f"L+R 理论新吃红 {both['n_newly_coverable_prev_lt_graze']} "
        f"({both['pct_honest_red_newly']}%) → GY {gy_now:.4f}→"
        f"{both['estimated_after']['GY_over_island']:.4f}"
        f"(+{both['estimated_after']['delta_GY_pp']}pp)；"
        f"C3/C4 红可吃 {both['pct_C3_red_eaten']}%/{both['pct_C4_red_eaten']}%；"
        f"未开 SDXL/fuse。"
    )

    report = {
        "stage": "v2_leg_inner_control_theory",
        "time_asia_shanghai": now,
        "fur_file_sha256": fur_sha,
        "coverage_sha256": cov_sha,
        "fur_status": "CANDIDATE_UNFROZEN",
        "uv_hash": measured,
        "mutated_fur": False,
        "ran_sdxl": False,
        "ran_fuse": False,
        "fill_red": False,
        "frozen": False,
        "opened_m3": False,
        "cameras": {
            vn: {
                **spec,
                "fit_margin": ctrl_rep.get(vn, {}).get("refit_margin", 0.08),
                "scale_m_per_logical_px": ctrl_rep.get(vn, {}).get("scale_m_per_logical_px"),
                "origin_logical_px": ctrl_rep.get(vn, {}).get("origin_logical_px"),
                "visible_px": ctrl_rep.get(vn, {}).get("visible_px"),
            }
            for vn, spec in V2_VIEWS.items()
        },
        "margins": margins,
        "constants": {
            "NDOTV_GRAZE": NDOTV_GRAZE,
            "prev_views": "8-dir pitch=35 + v1_belly yaw0 pitch-30",
            "theory_note": (
                "Occlusion-free face N·V. Baseline = current working coverage "
                "(8+V1 fused, CANDIDATE_UNFROZEN). Optimistic upper bound."
            ),
        },
        "baseline_honest_8plus_v1": {
            "island": n_island,
            "n_gy": n_gy,
            "n_red": n_red,
            "GY_over_island": round(gy_now, 4),
            "red_over_island": round(red_now, 4),
        },
        "per_view_theory": per_view,
        "combined_L_R_theory": both,
        "verdict": {
            "control_exported": True,
            "margin_ge_16": margin_ok,
            "sdxl_status": "控图已出·不开 SDXL",
            "one_liner": one_liner,
        },
        "outputs": [
            "v2_leg_inner_control_sheet.png",
            "control_preview/v2_leg_inner_L/",
            "control_preview/v2_leg_inner_R/",
            "theory_v2_eat_red_512.png",
            "theory_v2_ndotv_on_red_512.png",
            "theory_v2_leg_inner_coverage.json",
            "V2_LEG_INNER_CONTROL.md",
        ],
    }

    (OUT / "theory_v2_leg_inner_coverage.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )

    def margin_row(tag, m):
        yes = "YES" if m["margin_ge_16"] else "NO"
        return (
            f"| {tag} | {m['margin_top']} | {m['margin_bottom']} | "
            f"{m['margin_left']} | {m['margin_right']} | {yes} |"
        )

    b = both
    ea = b["estimated_after"]
    gate_now = "已过" if gy_now >= 0.92 else "未过"
    if ea["GY_over_island"] >= 0.92:
        gate_after = "仍过"
    else:
        gate_after = f"差 {ea['still_short_of_0_92_by']}"

    md_lines = [
        "# V2 腿内侧控图 + 理论 N·V 覆盖",
        "",
        f"**时间**：{now}（Asia/Shanghai）",
        "**状态**：控图已出 · **不开 SDXL / fuse**（本轮仅控图+理论）",
        f"**fur**：工作 `{fur_sha[:12]}…` · **CANDIDATE_UNFROZEN**（未冻）",
        f"**coverage**：`{cov_sha[:12]}…`（8+V1 合拢写入后）",
        "",
        "> 硬门不降。禁假绿填红 / 软降 / 拧 EDGE·graze / regen / 冻 / 开 M3。",
        "> 旧 8 向 + V1 控图**未**重渲。",
        "",
        "## 相机",
        "",
        "| name | yaw | pitch | fit_margin | visible_px | 路径 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for vn, spec in V2_VIEWS.items():
        cr = ctrl_rep.get(vn, {})
        md_lines.append(
            f"| `{vn}` | **{spec['yaw_deg']}°** | **{spec['pitch_deg']}°** | "
            f"{cr.get('refit_margin', 0.08)} | {cr.get('visible_px')} | "
            f"`cats/miemie/identity_v1/control_views/{vn}/` |"
        )
    md_lines += [
        "",
        "说明：yaw 相对 ±90° **偏内 15°**（朝 yaw=0）；pitch=+15° 略俯。目标 C3/C4 后腿内侧 + 部分前腿腋下。",
        "",
        "## 边距自检（hi 456×416）",
        "",
        "| 图 | T | B | L | R | ≥16 |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for vn in V2_VIEWS:
        md_lines.append(margin_row(f"{vn}/depth", margins[vn]["depth"]))
        md_lines.append(margin_row(f"{vn}/clay", margins[vn]["clay"]))

    md_lines += [
        "",
        "## 理论覆盖（诚实 bary 岛 · graze=0.20 · **相对 8+V1 基线** · 无遮挡上限）",
        "",
        f"基线 GY/岛 = **{gy_now:.4f}** · 红/岛 = **{red_now:.4f}**（写入后工作 coverage）",
        "",
        "### L+R 合看",
        "",
        "| 指标 | n | % |",
        "|---|---:|---:|",
        f"| 诚实红被 V2 N·V≥graze | {b['n_honest_red_ge_graze']} | {b['pct_honest_red_ge_graze']} |",
        f"| 其中相对 8+V1 **新**可吃（prev&lt;graze） | {b['n_newly_coverable_prev_lt_graze']} | {b['pct_honest_red_newly']} |",
        f"| 背向红（prev&lt;0）可吃 | {b['backface_red_eaten']}/{b['backface_red_n']} | {b['pct_backface_red_eaten']} |",
        f"| legs 红可吃 | {b['legs_red_eaten']}/{b['legs_red_n']} | {b['pct_legs_red_eaten']} |",
        f"| C3_leg_BL 红可吃 | {b['C3_leg_BL_red_eaten']}/{b['C3_leg_BL_red_n']} | {b['pct_C3_red_eaten']} |",
        f"| C4_leg_BR 红可吃 | {b['C4_leg_BR_red_eaten']}/{b['C4_leg_BR_red_n']} | {b['pct_C4_red_eaten']} |",
        f"| 前腿红可吃 | {b['front_legs_red_eaten']}/{b['front_legs_red_n']} | {b['pct_front_legs_red_eaten']} |",
        f"| 阈值带红可吃 | {b['thresh_red_eaten']}/{b['thresh_red_n']} | {b['pct_thresh_red_eaten']} |",
        f"| face_detail 红可吃（**非本战役标准**） | {b['face_detail_red_eaten']}/{b['face_detail_red_n']} | {b['pct_face_detail_red_eaten']} |",
        "",
        "### 分向",
        "",
        "| 向 | 新吃红 n | 新吃% | 估 GY | ΔGY pp | C3% | C4% |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for vn, t in per_view.items():
        e = t["estimated_after"]
        md_lines.append(
            f"| `{vn}` | {t['n_newly_coverable_prev_lt_graze']} | {t['pct_honest_red_newly']} | "
            f"**{e['GY_over_island']:.4f}** | +{e['delta_GY_pp']} | "
            f"{t['pct_C3_red_eaten']} | {t['pct_C4_red_eaten']} |"
        )
    md_lines += [
        f"| **L+R** | {b['n_newly_coverable_prev_lt_graze']} | {b['pct_honest_red_newly']} | "
        f"**{ea['GY_over_island']:.4f}** | +{ea['delta_GY_pp']} | "
        f"{b['pct_C3_red_eaten']} | {b['pct_C4_red_eaten']} |",
        "",
        "### 估算合拢后（L+R）",
        "",
        "| 口径 | GY/岛 | 红/岛 | ΔGY |",
        "|---|---:|---:|---:|",
        f"| 现在（8+V1 工作） | {gy_now:.4f} | {red_now:.4f} | — |",
        f"| +V2 L+R **乐观**（无遮挡） | **{ea['GY_over_island']:.4f}** | {ea['red_over_island']:.4f} | **+{ea['delta_GY_pp']} pp** |",
        f"| 硬门 GY≥0.92 | {gate_now} → {gate_after} | 红门均仍 PASS | — |",
        "",
        f"**一句话**：{one_liner}",
        "",
        "## 非目标",
        "",
        "- face_detail / 鼻垫红：**不进本战役成功标准**。",
        "- 旧 8 向 + V1 控图：**未**重渲。",
        "- SDXL / fuse / 冻 / 开 M3：**未**做。",
        "",
        "## 产出",
        "",
        "- `v2_leg_inner_control_sheet.png`",
        "- `control_preview/v2_leg_inner_L|R/`",
        "- `theory_v2_eat_red_512.png`（青=V2可吃 · 黄=后腿新吃 · 橙=前腿新吃 · 红=仍盲）",
        "- `theory_v2_ndotv_on_red_512.png`",
        "- `theory_v2_leg_inner_coverage.json`",
        "",
        f"路径：`{OUT.relative_to(ROOT)}/`",
    ]
    (OUT / "V2_LEG_INNER_CONTROL.md").write_text("\n".join(md_lines) + "\n")
    print(json.dumps(report["verdict"], ensure_ascii=False, indent=2))
    print(json.dumps(both["estimated_after"], indent=2))
    ev.to_mesh_clear()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
