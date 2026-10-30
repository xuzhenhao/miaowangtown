#!/usr/bin/env python3
"""M2.2 — Theoretical N·V coverage gain if V1 belly view (yaw=0, pitch=-30)
were fused. Read-only: no fuse / no SDXL / no fur mutate / no fill-red.

Uses honest bary island + graze=0.20 (same as coverage_island_honest).
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
CTRL = ID_DIR / "control_views" / "v1_belly"
HOLD = ROOT / "docs" / "validation" / "m2_2_8dir" / "hold_diag"
OUT = HOLD / "v1_belly_control"
EXPECTED_UV = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
EXPECTED_FUR_PREFIX = "46e56675a577"
UV_SIZE = 2048
PITCH_8 = 35.0
V1_YAW = 0.0
V1_PITCH = -30.0
NDOTV_GRAZE = 0.20
BASELINE_GY = 0.8117  # honest whole-island from 6743e87

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
    "head": ["A1_head_front", "A2_head_back", "A3_muzzle_chin", "A4_ears_LR"],
    "torso_side": ["B1_torso_L", "B2_torso_R"],
    "torso_back": ["B3_torso_back"],
    "belly": ["B4_torso_belly"],
    "legs": ["C1_leg_FL", "C2_leg_FR", "C3_leg_BL", "C4_leg_BR"],
    "tail": ["D1_tail"],
    "face_detail": ["D2_eyes_LR", "D3_nose_pads_tongue"],
    "reserved": ["D4_reserved"],
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")

    if not CTRL.is_dir():
        raise RuntimeError(f"missing V1 control dir {CTRL}")

    fur_path = ID_DIR / "fur_albedo.png"
    cov_path = ID_DIR / "coverage.png"
    fur_sha = hashlib.sha256(fur_path.read_bytes()).hexdigest()
    cov_sha = hashlib.sha256(cov_path.read_bytes()).hexdigest()
    if not fur_sha.startswith(EXPECTED_FUR_PREFIX):
        print(f"WARN fur sha {fur_sha[:16]} != {EXPECTED_FUR_PREFIX}…", flush=True)

    # Copy control previews into hold_diag
    preview_dir = OUT / "control_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for fn in [
        "depth.png",
        "normal.png",
        "clay.png",
        "part_mask.png",
        "depth_768.png",
        "normal_768.png",
        "clay_768.png",
        "part_mask_768.png",
    ]:
        src = CTRL / fn
        if src.is_file():
            shutil.copy2(src, preview_dir / fn)

    # Contact sheet
    depth = Image.open(CTRL / "depth.png").convert("RGB")
    normal = Image.open(CTRL / "normal.png").convert("RGB")
    clay = Image.open(CTRL / "clay.png").convert("RGBA")
    sheet = Image.new("RGB", (456 * 3 + 24, 416 + 48), (18, 20, 26))
    sheet.paste(depth.resize((456, 416)), (8, 36))
    sheet.paste(normal.resize((456, 416)), (8 + 456 + 4, 36))
    clay_rgb = Image.new("RGB", clay.size, (18, 20, 26))
    clay_rgb.paste(clay, mask=clay.split()[-1] if clay.mode == "RGBA" else None)
    sheet.paste(clay_rgb.resize((456, 416)), (8 + 2 * (456 + 4), 36))
    dr = ImageDraw.Draw(sheet)
    dr.text(
        (8, 8),
        f"V1 belly  yaw={V1_YAW} pitch={V1_PITCH}  depth | normal | clay  (no SDXL)",
        fill=(220, 220, 230),
    )
    sheet.save(OUT / "v1_belly_control_sheet.png")

    margins = {
        "depth": margin_stats(CTRL / "depth.png"),
        "clay": margin_stats(CTRL / "clay.png"),
        "normal": margin_stats(CTRL / "normal.png"),
    }

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

    # Honest bary island
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
    print(
        f"island={n_island} gy={n_gy} red={n_red} GY={gy_now:.4f} red_r={red_now:.4f}",
        flush=True,
    )

    # best N·V over 8-dir
    best8 = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    for dname, yaw in DIRECTIONS_8.items():
        _, _, e_w = get_camera_basis(yaw, PITCH_8)
        raster_ndotv(tris_uv, tris_nrm_u, e_w, best8)
        print(f"ndotv8 {dname} done", flush=True)

    # V1
    v1 = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    _, _, e_w_v1 = get_camera_basis(V1_YAW, V1_PITCH)
    raster_ndotv(tris_uv, tris_nrm_u, e_w_v1, v1)
    print("ndotv V1 done", flush=True)

    best_with_v1 = np.maximum(best8, v1)

    geo_blind = red & (best8 < 0.0)
    thresh = red & (best8 >= 0.0) & (best8 < NDOTV_GRAZE)
    rmasks = region_masks()
    belly_m = rmasks["B4_torso_belly"]
    face_m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for nm in PART_BUCKETS["face_detail"]:
        face_m |= rmasks[nm]
    legs_m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for nm in PART_BUCKETS["legs"]:
        legs_m |= rmasks[nm]

    # V1 can cover if ndotv >= graze (occlusion-free theory, same as prior attrib)
    v1_covers = red & (v1 >= NDOTV_GRAZE)
    # Newly coverable = currently red, not already graze-reachable by 8-dir
    already_graze_capable = red & (best8 >= NDOTV_GRAZE)  # anomaly red
    newly = v1_covers & (best8 < NDOTV_GRAZE)
    # Also count all red that V1 makes >= graze (incl. lifting thresh→graze)
    n_v1_covers = int(v1_covers.sum())
    n_newly = int(newly.sum())

    n_geo = int(geo_blind.sum())
    n_geo_eaten = int((geo_blind & (v1 >= NDOTV_GRAZE)).sum())
    n_belly_red = int((red & belly_m).sum())
    n_belly_eaten = int((red & belly_m & (v1 >= NDOTV_GRAZE)).sum())
    n_face_red = int((red & face_m).sum())
    n_face_eaten = int((red & face_m & (v1 >= NDOTV_GRAZE)).sum())
    n_legs_red = int((red & legs_m).sum())
    n_legs_eaten = int((red & legs_m & (v1 >= NDOTV_GRAZE)).sum())
    n_thresh = int(thresh.sum())
    n_thresh_eaten = int((thresh & (v1 >= NDOTV_GRAZE)).sum())

    # Estimated post-V1 (theory): newly covered → GY
    n_gy_est = n_gy + n_newly
    n_red_est = n_red - n_newly
    gy_est = n_gy_est / max(1, n_island)
    red_est = n_red_est / max(1, n_island)

    def pct(n, d):
        return round(100.0 * n / max(1, d), 2)

    # Heat overlay: honest red; cyan=V1 eats; orange=still red
    heat = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    heat[island] = (36, 40, 48)
    heat[gy] = (40, 160, 70)
    heat[red & ~v1_covers] = (200, 50, 50)
    heat[v1_covers] = (60, 220, 230)  # cyan = theoretically eaten by V1
    heat[geo_blind & (v1 >= NDOTV_GRAZE)] = (80, 180, 255)  # light blue = backface eaten
    heat[red & belly_m & (v1 >= NDOTV_GRAZE)] = (255, 220, 60)  # yellow = belly eaten
    Image.fromarray(heat).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "theory_v1_eat_red_512.png"
    )
    Image.fromarray(heat).save(OUT / "theory_v1_eat_red_2048.png")

    # V1 ndotv heat on honest red
    vheat = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    vheat[:] = (18, 20, 26)
    vheat[island] = (30, 32, 40)
    mask = red
    if np.any(mask):
        t = np.clip((v1 + 1.0) / 2.0, 0, 1)  # map [-1,1]→[0,1]
        r = np.zeros_like(t)
        g = np.zeros_like(t)
        b = np.zeros_like(t)
        # blue (backface) → yellow (0) → red/green (>=graze)
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
        # mark graze threshold band
        vheat[mask, 0] = np.clip(r[mask], 0, 255).astype(np.uint8)
        vheat[mask, 1] = np.clip(g[mask], 0, 255).astype(np.uint8)
        vheat[mask, 2] = np.clip(b[mask], 0, 255).astype(np.uint8)
        ge = mask & (v1 >= NDOTV_GRAZE)
        # bump green on graze+
        vheat[ge, 1] = np.maximum(vheat[ge, 1], 200)
    Image.fromarray(vheat).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "theory_v1_ndotv_on_red_512.png"
    )

    ctrl_rep = {}
    er = ID_DIR / "control_views" / "export_report.json"
    if er.is_file():
        ctrl_rep = json.loads(er.read_text()).get("directions", {}).get("v1_belly", {})

    report = {
        "stage": "v1_belly_control_theory",
        "time_asia_shanghai": now,
        "fur_file_sha256": fur_sha,
        "coverage_sha256": cov_sha,
        "uv_hash": measured,
        "mutated_fur": False,
        "ran_sdxl": False,
        "ran_fuse": False,
        "fill_red": False,
        "camera": {
            "name": "v1_belly",
            "yaw_deg": V1_YAW,
            "pitch_deg": V1_PITCH,
            "fit_margin": ctrl_rep.get("refit_margin", 0.08),
            "scale_m_per_logical_px": ctrl_rep.get("scale_m_per_logical_px"),
            "origin_logical_px": ctrl_rep.get("origin_logical_px"),
            "visible_px": ctrl_rep.get("visible_px"),
        },
        "margins": margins,
        "constants": {
            "NDOTV_GRAZE": NDOTV_GRAZE,
            "baseline_GY_honest_island": BASELINE_GY,
            "theory_note": (
                "Occlusion-free face N·V (same as coverage_island_honest / attrib). "
                "Optimistic upper bound; real fuse may be lower due to occlusion/graze weighting."
            ),
        },
        "baseline_honest": {
            "island": n_island,
            "n_gy": n_gy,
            "n_red": n_red,
            "GY_over_island": round(gy_now, 4),
            "red_over_island": round(red_now, 4),
        },
        "v1_theory": {
            "n_honest_red_v1_ge_graze": n_v1_covers,
            "pct_honest_red_v1_ge_graze": pct(n_v1_covers, n_red),
            "n_newly_coverable_best8_lt_graze": n_newly,
            "pct_honest_red_newly": pct(n_newly, n_red),
            "backface_red_n": n_geo,
            "backface_red_eaten_by_v1": n_geo_eaten,
            "pct_backface_red_eaten": pct(n_geo_eaten, n_geo),
            "belly_red_n": n_belly_red,
            "belly_red_eaten_by_v1": n_belly_eaten,
            "pct_belly_red_eaten": pct(n_belly_eaten, n_belly_red),
            "thresh_red_n": n_thresh,
            "thresh_red_eaten_by_v1": n_thresh_eaten,
            "pct_thresh_red_eaten": pct(n_thresh_eaten, n_thresh),
            "legs_red_n": n_legs_red,
            "legs_red_eaten_by_v1": n_legs_eaten,
            "pct_legs_red_eaten": pct(n_legs_eaten, n_legs_red),
            "face_detail_red_n": n_face_red,
            "face_detail_red_eaten_by_v1": n_face_eaten,
            "pct_face_detail_red_eaten": pct(n_face_eaten, n_face_red),
            "face_detail_note": "V1 不吃鼻垫/face_detail——不进本战役成功标准",
        },
        "estimated_after_v1": {
            "n_gy": n_gy_est,
            "n_red": n_red_est,
            "GY_over_island": round(gy_est, 4),
            "red_over_island": round(red_est, 4),
            "delta_GY_pp": round((gy_est - gy_now) * 100, 2),
            "delta_red_pp": round((red_est - red_now) * 100, 2),
            "GY_vs_baseline_0_8117": round(gy_est, 4),
            "still_short_of_0_92_by": round(max(0.0, 0.92 - gy_est), 4),
            "red_gate_still_pass_le_0_20": red_est <= 0.20,
        },
        "verdict": {
            "control_exported": True,
            "margin_ge_16": margins["depth"]["margin_ge_16"],
            "sdxl_status": "控图已出·等 SDXL 点头",
            "one_liner": (
                f"V1 yaw=0 pitch=-30 边距≥16；理论可新吃诚实红 {n_newly} "
                f"({pct(n_newly, n_red)}%) → GY {gy_now:.4f}→{gy_est:.4f} "
                f"(+{round((gy_est - gy_now) * 100, 2)}pp)；"
                f"背向红可吃 {pct(n_geo_eaten, n_geo)}%、belly 红可吃 {pct(n_belly_eaten, n_belly_red)}%；"
                f"face_detail 可吃 {pct(n_face_eaten, n_face_red)}%（V1不吃·非本战役标准）。"
                f"未开 SDXL/fuse。"
            ),
        },
        "outputs": [
            "v1_belly_control_sheet.png",
            "control_preview/",
            "theory_v1_eat_red_512.png",
            "theory_v1_ndotv_on_red_512.png",
            "theory_v1_belly_coverage.json",
            "V1_BELLY_CONTROL.md",
        ],
    }

    (OUT / "theory_v1_belly_coverage.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )

    md = "\n".join(
        [
            "# V1 腹底控图 + 理论 N·V 覆盖",
            "",
            f"**时间**：{now}（Asia/Shanghai）",
            f"**状态**：控图已出 · **等 SDXL 点头**（本轮未跑 SDXL / fuse）",
            f"**fur**：baseline `{fur_sha[:12]}…`（未改）",
            "",
            "> 硬门不降。禁假绿填红 / 软降 / 拧 EDGE·graze / regen / 冻 / 开 M3。",
            "",
            "## 相机",
            "",
            "| 项 | 值 |",
            "|---|---|",
            f"| name | `v1_belly`（alias `pitch_m30`） |",
            f"| yaw | **{V1_YAW}°** |",
            f"| pitch | **{V1_PITCH}°**（负=低机位仰视腹底） |",
            f"| fit_margin | {ctrl_rep.get('refit_margin', 0.08)} |",
            f"| visible_px (hi) | {ctrl_rep.get('visible_px')} |",
            f"| 路径 | `cats/miemie/identity_v1/control_views/v1_belly/` |",
            "",
            "## 边距自检（hi 456×416）",
            "",
            "| 图 | T | B | L | R | ≥16 |",
            "|---|---:|---:|---:|---:|:---:|",
            (
                f"| depth | {margins['depth']['margin_top']} | {margins['depth']['margin_bottom']} | "
                f"{margins['depth']['margin_left']} | {margins['depth']['margin_right']} | "
                f"{'YES' if margins['depth']['margin_ge_16'] else 'NO'} |"
            ),
            (
                f"| clay | {margins['clay']['margin_top']} | {margins['clay']['margin_bottom']} | "
                f"{margins['clay']['margin_left']} | {margins['clay']['margin_right']} | "
                f"{'YES' if margins['clay']['margin_ge_16'] else 'NO'} |"
            ),
            "",
            "## 理论覆盖（诚实 bary 岛 · graze=0.20 · 无遮挡上限）",
            "",
            f"基线 GY/岛 = **{gy_now:.4f}**（对标 0.8117）· 红/岛 = **{red_now:.4f}**",
            "",
            "| 指标 | n | % |",
            "|---|---:|---:|",
            f"| 诚实红被 V1 N·V≥graze | {n_v1_covers} | {pct(n_v1_covers, n_red)} |",
            f"| 其中相对 8 向**新**可吃（best8&lt;graze） | {n_newly} | {pct(n_newly, n_red)} |",
            f"| 背向红（best8&lt;0）可吃 | {n_geo_eaten}/{n_geo} | {pct(n_geo_eaten, n_geo)} |",
            f"| belly 红可吃 | {n_belly_eaten}/{n_belly_red} | {pct(n_belly_eaten, n_belly_red)} |",
            f"| 阈值带红（0≤best8&lt;graze）可吃 | {n_thresh_eaten}/{n_thresh} | {pct(n_thresh_eaten, n_thresh)} |",
            f"| legs 红可吃 | {n_legs_eaten}/{n_legs_red} | {pct(n_legs_eaten, n_legs_red)} |",
            f"| face_detail 红可吃（**V1 不吃·非战役标准**） | {n_face_eaten}/{n_face_red} | {pct(n_face_eaten, n_face_red)} |",
            "",
            "### 估算合拢后",
            "",
            "| | 现在 | +V1 理论 | Δ |",
            "|---|---:|---:|---:|",
            f"| GY/岛 | {gy_now:.4f} | **{gy_est:.4f}** | +{round((gy_est - gy_now) * 100, 2)} pp |",
            f"| 红/岛 | {red_now:.4f} | **{red_est:.4f}** | {round((red_est - red_now) * 100, 2)} pp |",
            f"| 距 GY 门 0.92 | {round(0.92 - gy_now, 4)} | {round(max(0.0, 0.92 - gy_est), 4)} | — |",
            "",
            f"**一句话**：{report['verdict']['one_liner']}",
            "",
            "## 非目标",
            "",
            "- face_detail / 鼻垫红：**V1 不吃**，不进本战役成功标准。",
            "- 旧 8 向控图：**未**重渲。",
            "- SDXL / fuse：**未**开跑。",
            "",
            "## 产出",
            "",
            "- `v1_belly_control_sheet.png`",
            "- `control_preview/`",
            "- `theory_v1_eat_red_512.png`（青=V1可吃 · 黄=肚皮可吃 · 红=仍盲）",
            "- `theory_v1_ndotv_on_red_512.png`",
            "- `theory_v1_belly_coverage.json`",
            "",
            f"路径：`{OUT.relative_to(ROOT)}/`",
        ]
    )
    (OUT / "V1_BELLY_CONTROL.md").write_text(md + "\n")
    print(json.dumps(report["verdict"], ensure_ascii=False, indent=2))
    print(json.dumps(report["estimated_after_v1"], indent=2))
    ev.to_mesh_clear()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
