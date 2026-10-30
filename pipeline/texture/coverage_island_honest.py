#!/usr/bin/env python3
"""M2.2 — coverage island honesty (metering only; no fur mutate / no fill-red).

OLD island = PIL polygon fill (uv_occ) used by fuse coverage.png red paint.
NEW / honest island = barycentric texel-center hit (same raster as fuse accumulate).

Hard gates unchanged numerically (GY≥0.92 / red≤0.20) — only the island
denominator & which red texels count. Switch for future fuse:
  --island-mode bary|pil   (default bary) / env M22_ISLAND_MODE

Does NOT: fill red, soft-down, twist EDGE/graze, regen, lower gates, freeze, M3.
"""
from __future__ import annotations

import hashlib
import json
import math
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
OUT = HOLD / "coverage_island_honest"
EXPECTED_UV = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
EXPECTED_FUR_PREFIX = "46e56675a577"
UV_SIZE = 2048
PITCH = 35.0
NDOTV_GRAZE = 0.20
NDOTV_DIRECT = 0.50
GATE_GY = 0.92
GATE_RED = 0.20

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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")

    cov_path = ID_DIR / "coverage.png"
    fur_path = ID_DIR / "fur_albedo.png"
    fur_sha = hashlib.sha256(fur_path.read_bytes()).hexdigest()
    cov_sha = hashlib.sha256(cov_path.read_bytes()).hexdigest()
    if not fur_sha.startswith(EXPECTED_FUR_PREFIX):
        print(f"WARN: fur sha {fur_sha[:16]} != expected {EXPECTED_FUR_PREFIX}…", flush=True)

    cov = np.array(Image.open(cov_path).convert("RGB"))
    green = (cov[:, :, 0] == 40) & (cov[:, :, 1] == 200) & (cov[:, :, 2] == 70)
    yellow = (cov[:, :, 0] == 230) & (cov[:, :, 1] == 200) & (cov[:, :, 2] == 40)
    red_pil = (cov[:, :, 0] == 200) & (cov[:, :, 1] == 50) & (cov[:, :, 2] == 50)
    island_pil = green | yellow | red_pil
    gy = green | yellow
    n_gy = int(gy.sum())

    # --- Blender: barycentric UV hit + best N·V ---
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

    # Honest island = any triangle covers texel center (bary)
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
    print(f"bary uv_hit={int(uv_hit.sum())} pil_island={int(island_pil.sum())}", flush=True)

    # best N·V across 8 views (for remaining-red class)
    best = np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64)
    for dname, yaw in DIRECTIONS.items():
        _, _, e_w = get_camera_basis(yaw)
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
            sub = best[ymin : ymax + 1, xmin : xmax + 1]
            better = inside & (ndotv > sub)
            sub[better] = ndotv
        print(f"ndotv {dname} done", flush=True)

    # --- Metrics ---
    # OLD (pil): island = PIL colors; red = red_pil
    island_old = island_pil
    red_old = red_pil
    n_island_old = int(island_old.sum())
    n_red_old = int(red_old.sum())
    gy_old = n_gy / max(1, n_island_old)
    red_r_old = n_red_old / max(1, n_island_old)

    # NEW (bary/honest): island = bary hit; red = red_pil ∩ bary (exclude fringe)
    # Also: GY that somehow lack bary are excluded from honest island
    # (GY should almost always be bary-hit; assert-ish)
    island_new = uv_hit.copy()
    # Keep GY inside honest island even if rare raster diverge (fuse already wrote them)
    island_new |= gy
    red_new = red_pil & uv_hit  # honest red = PIL-red that has bary hit
    fringe_excluded = red_pil & ~uv_hit  # bary_miss fringe removed from denom+numer
    n_island_new = int(island_new.sum())
    n_red_new = int(red_new.sum())
    n_fringe = int(fringe_excluded.sum())
    gy_new = n_gy / max(1, n_island_new)
    red_r_new = n_red_new / max(1, n_island_new)

    # high-freq GY (same region list as fuse; intersect with each island)
    rmasks = region_masks()
    hf = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
    for name in HIGH_FREQ_REGIONS:
        if name in rmasks:
            hf |= rmasks[name]
    if not np.any(hf):
        hf = island_old
    hf_old = hf & island_old
    hf_new = hf & island_new
    hf_gy_old = int((gy & hf_old).sum()) / max(1, int(hf_old.sum()))
    hf_gy_new = int((gy & hf_new).sum()) / max(1, int(hf_new.sum()))

    pass_gy_old = hf_gy_old >= GATE_GY
    pass_red_old = red_r_old <= GATE_RED
    pass_gy_new = hf_gy_new >= GATE_GY
    pass_red_new = red_r_new <= GATE_RED

    # Remaining honest-red class
    bary_miss_on_old_red = fringe_excluded  # already
    geo_blind = red_new & (best < 0.0)
    thresh = red_new & (best >= 0.0) & (best < NDOTV_GRAZE)
    anomaly = red_new & (best >= NDOTV_GRAZE)
    other = red_new & ~(geo_blind | thresh | anomaly)

    def pct_of(n: int, den: int) -> float:
        return round(100.0 * n / max(1, den), 2)

    class_remaining = {
        "true_camera_blind_backface": {
            "n": int(geo_blind.sum()),
            "pct_of_honest_red": pct_of(int(geo_blind.sum()), n_red_new),
        },
        "threshold_strict_0_le_ndotv_lt_graze": {
            "n": int(thresh.sum()),
            "pct_of_honest_red": pct_of(int(thresh.sum()), n_red_new),
        },
        "anomaly_ndotv_ge_graze_but_red": {
            "n": int(anomaly.sum()),
            "pct_of_honest_red": pct_of(int(anomaly.sum()), n_red_new),
        },
        "other": {"n": int(other.sum()), "pct_of_honest_red": pct_of(int(other.sum()), n_red_new)},
    }

    # Part buckets on honest red
    bucket_stats = {}
    for bname, names in PART_BUCKETS.items():
        m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
        for nm in names:
            m |= rmasks[nm]
        n = int((red_new & m).sum())
        bucket_stats[bname] = {
            "n_red": n,
            "pct_of_honest_red": pct_of(n, n_red_new),
            "n_island_honest_in_bucket": int((island_new & m).sum()),
            "red_over_honest_island_in_bucket": round(
                n / max(1, int((island_new & m).sum())), 4
            ),
        }
    ranked_buckets = sorted(bucket_stats.items(), key=lambda kv: kv[1]["n_red"], reverse=True)

    # Focus trio: belly / legs / backface share of remaining
    n_belly = bucket_stats["belly"]["n_red"]
    n_legs = bucket_stats["legs"]["n_red"]
    n_geo = int(geo_blind.sum())

    delta_island = n_island_old - n_island_new
    delta_red = n_red_old - n_red_new
    # How far from gates
    gy_gap_new = round(GATE_GY - hf_gy_new, 4)
    red_gap_new = round(red_r_new - GATE_RED, 4)

    gates_pass_new = pass_gy_new and pass_red_new
    gates_pass_old = pass_gy_old and pass_red_old

    # --- Images ---
    # 1) fringe excluded map
    fringe_img = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    fringe_img[island_old] = (40, 40, 48)
    fringe_img[island_new] = (50, 90, 70)  # honest island teal-ish
    fringe_img[fringe_excluded] = (255, 140, 40)  # orange = removed fringe
    fringe_img[red_new] = (200, 50, 50)  # remaining red
    fringe_img[gy] = (40, 200, 70)
    Image.fromarray(fringe_img).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "island_old_vs_honest_512.png"
    )
    Image.fromarray(fringe_img).save(OUT / "island_old_vs_honest_2048.png")

    # 2) remaining red by class
    cls_img = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    cls_img[island_new] = (40, 40, 48)
    cls_img[geo_blind] = (220, 60, 60)
    cls_img[thresh] = (230, 180, 40)
    cls_img[anomaly] = (80, 200, 255)
    cls_img[fringe_excluded] = (90, 90, 100)  # dim = no longer counted
    Image.fromarray(cls_img).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "honest_red_class_512.png"
    )

    # 3) remaining red by part
    part_colors = {
        "head": (235, 110, 95),
        "torso_side": (85, 185, 215),
        "torso_back": (105, 145, 235),
        "belly": (155, 125, 235),
        "legs": (235, 115, 155),
        "tail": (115, 175, 195),
        "face_detail": (85, 210, 135),
        "reserved": (130, 135, 145),
    }
    part_img = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    part_img[island_new] = (35, 36, 42)
    for bname, names in PART_BUCKETS.items():
        m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
        for nm in names:
            m |= rmasks[nm]
        part_img[red_new & m] = part_colors[bname]
    Image.fromarray(part_img).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "honest_red_by_part_512.png"
    )

    # 4) compare board
    board = Image.new("RGB", (1580, 560), (20, 22, 28))
    board.paste(
        Image.fromarray(fringe_img).resize((512, 512), Image.Resampling.NEAREST), (10, 30)
    )
    board.paste(
        Image.fromarray(cls_img).resize((512, 512), Image.Resampling.NEAREST), (530, 30)
    )
    board.paste(
        Image.fromarray(part_img).resize((512, 512), Image.Resampling.NEAREST), (1050, 30)
    )
    dr = ImageDraw.Draw(board)
    dr.text((10, 8), "OLD island vs HONEST (orange=excluded fringe)", fill=(220, 220, 230))
    dr.text((530, 8), "HONEST red class: R=geo Y=thresh C=anom", fill=(220, 220, 230))
    dr.text((1050, 8), "HONEST red by part", fill=(220, 220, 230))
    board.save(OUT / "island_honest_board_512.png")

    tip = "awaiting_git"  # filled by wrapper / report

    report = {
        "stage": "coverage_island_honest_metering",
        "time_asia_shanghai": now,
        "fur_file_sha256": fur_sha,
        "coverage_sha256": cov_sha,
        "uv_hash": measured,
        "mutated_fur": False,
        "mutated_coverage_png": False,
        "fill_red": False,
        "constants": {
            "NDOTV_GRAZE": NDOTV_GRAZE,
            "GATE_GY": GATE_GY,
            "GATE_RED": GATE_RED,
            "island_mode_default_for_fuse": "bary",
            "note": (
                "OLD=PIL uv_occ island; NEW=barycentric texel-center hit. "
                "Hard gate thresholds unchanged. Seed band in fuse still uses PIL uv_occ "
                "(fur fill safety); only GY/red gate denom+numer use honest island when "
                "--island-mode bary."
            ),
        },
        "old_pil": {
            "island": n_island_old,
            "green": int(green.sum()),
            "yellow": int(yellow.sum()),
            "red": n_red_old,
            "GY_over_island": round(gy_old, 4),
            "red_over_island": round(red_r_old, 4),
            "high_freq_GY_ratio": round(hf_gy_old, 4),
            "gate_GY_ge_0_92": pass_gy_old,
            "gate_red_le_0_20": pass_red_old,
            "gates_both_pass": gates_pass_old,
        },
        "new_bary_honest": {
            "island": n_island_new,
            "green": int(green.sum()),
            "yellow": int(yellow.sum()),
            "red": n_red_new,
            "fringe_bary_miss_excluded": n_fringe,
            "GY_over_island": round(gy_new, 4),
            "red_over_island": round(red_r_new, 4),
            "high_freq_GY_ratio": round(hf_gy_new, 4),
            "gate_GY_ge_0_92": pass_gy_new,
            "gate_red_le_0_20": pass_red_new,
            "gates_both_pass": gates_pass_new,
            "gy_gap_to_0_92": gy_gap_new,
            "red_gap_above_0_20": red_gap_new,
        },
        "delta_old_minus_new": {
            "island_texels_removed": delta_island,
            "red_texels_removed": delta_red,
            "pct_old_red_was_fringe": pct_of(n_fringe, n_red_old),
            "pct_old_island_was_fringe": pct_of(n_fringe, n_island_old),
        },
        "remaining_honest_red_class": class_remaining,
        "remaining_honest_red_buckets_ranked": [
            {"bucket": k, **v} for k, v in ranked_buckets
        ],
        "remaining_structure_focus": {
            "geo_blind_n": n_geo,
            "geo_blind_pct_of_honest_red": pct_of(n_geo, n_red_new),
            "belly_n": n_belly,
            "belly_pct_of_honest_red": pct_of(n_belly, n_red_new),
            "legs_n": n_legs,
            "legs_pct_of_honest_red": pct_of(n_legs, n_red_new),
        },
        "verdict": {
            "old_gates_pass": gates_pass_old,
            "new_gates_pass": gates_pass_new,
            "red_gate_flipped_to_pass": (not pass_red_old) and pass_red_new,
            "gy_still_fail": not pass_gy_new,
            "one_liner": None,  # filled below
        },
        "outputs": [
            "island_old_vs_honest_512.png",
            "island_old_vs_honest_2048.png",
            "honest_red_class_512.png",
            "honest_red_by_part_512.png",
            "island_honest_board_512.png",
            "coverage_island_honest.json",
            "COVERAGE_ISLAND_HONEST.md",
        ],
    }

    if gates_pass_new:
        one = (
            f"修岛后 GY={hf_gy_new:.4f} / 红={red_r_new:.4f} → **双门 PASS** "
            f"（剔除 fringe {n_fringe}={pct_of(n_fringe, n_red_old)}% 旧红）。"
            "仍不冻；coverage.png 未改写本轮。"
        )
    elif pass_red_new and not pass_gy_new:
        one = (
            f"修岛后红门 PASS（{red_r_new:.4f}≤0.20），GY 仍 FAIL（{hf_gy_new:.4f}，差 {gy_gap_new}）。"
            f"剩余红结构：背向 {pct_of(n_geo, n_red_new)}% + legs {pct_of(n_legs, n_red_new)}% + "
            f"belly {pct_of(n_belly, n_red_new)}%；下一刀仍是加视角/低 pitch，不降硬门。"
        )
    elif pass_gy_new and not pass_red_new:
        one = (
            f"修岛后 GY PASS，红仍 FAIL（{red_r_new:.4f}，超 {red_gap_new}）。"
            f"剩余红：背向 {pct_of(n_geo, n_red_new)}% / legs {pct_of(n_legs, n_red_new)}% / "
            f"belly {pct_of(n_belly, n_red_new)}%。"
        )
    else:
        one = (
            f"修岛后双门仍 FAIL：GY {hf_gy_new:.4f}（差 {gy_gap_new}）/ 红 {red_r_new:.4f}"
            f"（超 {red_gap_new}）；剔除 fringe {n_fringe}（占旧红 {pct_of(n_fringe, n_red_old)}%）。"
            f"剩余红：背向 {pct_of(n_geo, n_red_new)}% / legs {pct_of(n_legs, n_red_new)}% / "
            f"belly {pct_of(n_belly, n_red_new)}%。不降硬门；见 ADD_VIEW_MIN_PLAN。"
        )
    report["verdict"]["one_liner"] = one

    (OUT / "coverage_island_honest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )

    # Markdown
    lines = [
        "# coverage 岛诚实（计量对照）",
        "",
        f"**时间**：{now}（Asia/Shanghai）",
        f"**fur**：baseline `{fur_sha[:16]}…`（**未改**）",
        f"**coverage.png SHA**：`{cov_sha[:16]}…`（本轮**未改写**；仅重算门禁分母/分子）",
        f"**UV**：`{measured}`",
        "",
        "> 假透空口径已解。本轮只改 **coverage 岛计量**：剔除 PIL vs 重心光栅差（bary_miss fringe）。",
        "> 硬门阈值不变：GY≥0.92 / 红≤0.20。禁假绿填红 / 软降 / 拧 EDGE·graze / regen / 降硬门。",
        "",
        "## 口径",
        "",
        "| 模式 | 岛定义 | 红计数 |",
        "|---|---|---|",
        "| **OLD (pil)** | PIL polygon fill（`uv_occ`） | `coverage==0 ∩ PIL岛` |",
        "| **NEW (bary / honest)** | 重心命中（texel 中心 bary） | `coverage==0 ∩ bary岛`（剔除 fringe） |",
        "",
        "fuse 开关：`--island-mode bary|pil`（默认 `bary`）/ 环境变量 `M22_ISLAND_MODE`。",
        "种子填色仍用 PIL `uv_occ`（防 fur 留洞）；**仅门禁统计**切诚实岛。",
        "",
        "## 新旧对照",
        "",
        "| | 岛 | 红 | GY/岛 | 红/岛 | hf GY | GY门 | 红门 | 双过 |",
        "|---|---:|---:|---:|---:|---:|:---:|:---:|:---:|",
        (
            f"| OLD pil | {n_island_old} | {n_red_old} | {gy_old:.4f} | {red_r_old:.4f} | "
            f"{hf_gy_old:.4f} | {'PASS' if pass_gy_old else 'FAIL'} | "
            f"{'PASS' if pass_red_old else 'FAIL'} | {'YES' if gates_pass_old else 'NO'} |"
        ),
        (
            f"| NEW bary | {n_island_new} | {n_red_new} | {gy_new:.4f} | {red_r_new:.4f} | "
            f"{hf_gy_new:.4f} | {'PASS' if pass_gy_new else 'FAIL'} | "
            f"{'PASS' if pass_red_new else 'FAIL'} | {'YES' if gates_pass_new else 'NO'} |"
        ),
        "",
        f"- 剔除 fringe（bary_miss）：**{n_fringe}**（占旧红 {pct_of(n_fringe, n_red_old)}%，占旧岛 {pct_of(n_fringe, n_island_old)}%）",
        f"- 距门：GY 差 `{gy_gap_new}`（正=未过）；红超 `{red_gap_new}`（正=未过）",
        "",
        "## 剩余诚实红结构",
        "",
        "### 类型",
        "",
        "| 类型 | n | 占诚实红% |",
        "|---|---:|---:|",
        (
            f"| 真相机盲（背向） | {class_remaining['true_camera_blind_backface']['n']} | "
            f"{class_remaining['true_camera_blind_backface']['pct_of_honest_red']} |"
        ),
        (
            f"| 阈值过严（0≤N·V&lt;0.20） | {class_remaining['threshold_strict_0_le_ndotv_lt_graze']['n']} | "
            f"{class_remaining['threshold_strict_0_le_ndotv_lt_graze']['pct_of_honest_red']} |"
        ),
        (
            f"| 异常（N·V≥graze 仍红） | {class_remaining['anomaly_ndotv_ge_graze_but_red']['n']} | "
            f"{class_remaining['anomaly_ndotv_ge_graze_but_red']['pct_of_honest_red']} |"
        ),
        "",
        "### 部件桶（诚实红）",
        "",
        "| 桶 | n_red | 占诚实红% | 桶内红/诚实岛 |",
        "|---|---:|---:|---:|",
    ]
    for k, v in ranked_buckets:
        lines.append(
            f"| **{k}** | {v['n_red']} | {v['pct_of_honest_red']} | "
            f"{v['red_over_honest_island_in_bucket']} |"
        )
    lines += [
        "",
        f"焦点：背向 {pct_of(n_geo, n_red_new)}% · legs {pct_of(n_legs, n_red_new)}% · "
        f"belly {pct_of(n_belly, n_red_new)}%",
        "",
        "## 判定",
        "",
        one,
        "",
        "## 产出",
        "",
    ]
    for p in report["outputs"]:
        lines.append(f"- `{p}`")
    lines += [
        "",
        "相关：`ADD_VIEW_MIN_PLAN.md`（半页计划，**未执行**）。",
        "",
        "锁：fur baseline；不冻不开 M3；不交用户点2。",
        "",
    ]
    (OUT / "COVERAGE_ISLAND_HONEST.md").write_text("\n".join(lines) + "\n")
    # also drop a short pointer at hold_diag root
    (HOLD / "COVERAGE_ISLAND_HONEST.md").write_text(
        "# coverage 岛诚实\n\n"
        "权威报告见目录：[`coverage_island_honest/COVERAGE_ISLAND_HONEST.md`]"
        "(coverage_island_honest/COVERAGE_ISLAND_HONEST.md)\n"
    )

    print(
        json.dumps(
            {
                "ok": True,
                "old": {
                    "GY": round(hf_gy_old, 4),
                    "red": round(red_r_old, 4),
                    "pass": gates_pass_old,
                },
                "new": {
                    "GY": round(hf_gy_new, 4),
                    "red": round(red_r_new, 4),
                    "pass": gates_pass_new,
                    "fringe_excl": n_fringe,
                },
                "one_liner": one,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    ev.to_mesh_clear()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
