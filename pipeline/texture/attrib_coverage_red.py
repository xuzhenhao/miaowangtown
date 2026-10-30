#!/usr/bin/env python3
"""Read-only attribution of coverage RED (unseen) texels — no fuse / no param knobs."""
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
OUT = ROOT / "docs" / "validation" / "m2_2_8dir" / "hold_diag" / "coverage_red_attrib"
EXPECTED_UV = "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f"
UV_SIZE = 2048
PITCH = 35.0
NDOTV_GRAZE = 0.20
NDOTV_DIRECT = 0.50
SEAM_DILATE = 3  # px band for island-edge / seam class

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

# Aggregate buckets for report
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


def dilate_bool(m: np.ndarray, n: int) -> np.ndarray:
    out = m.copy()
    for _ in range(n):
        nxt = out.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nxt |= np.roll(np.roll(out, dy, axis=0), dx, axis=1)
        out = nxt
    return out


def heat_rgb(vals: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Map float vals on mask to blue→cyan→yellow→red heat; elsewhere dark."""
    img = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    img[:] = (18, 20, 26)
    if not np.any(mask):
        return img
    v = vals[mask].astype(np.float64)
    lo = float(np.percentile(v, 2)) if v.size else 0.0
    hi = float(np.percentile(v, 98)) if v.size else 1.0
    if hi <= lo:
        hi = lo + 1e-6
    t = np.clip((vals - lo) / (hi - lo), 0, 1)
    # simple 4-stop ramp
    r = np.zeros_like(t)
    g = np.zeros_like(t)
    b = np.zeros_like(t)
    # 0..0.33 blue→cyan, 0.33..0.66 cyan→yellow, 0.66..1 yellow→red
    s1 = t < 0.33
    s2 = (t >= 0.33) & (t < 0.66)
    s3 = t >= 0.66
    u1 = np.clip(t / 0.33, 0, 1)
    u2 = np.clip((t - 0.33) / 0.33, 0, 1)
    u3 = np.clip((t - 0.66) / 0.34, 0, 1)
    r[s1] = 40
    g[s1] = 80 + 140 * u1[s1]
    b[s1] = 220
    r[s2] = 40 + 190 * u2[s2]
    g[s2] = 220
    b[s2] = 220 - 180 * u2[s2]
    r[s3] = 230
    g[s3] = 220 - 180 * u3[s3]
    b[s3] = 40
    img[mask, 0] = (r[mask] * 255 / 255.0).astype(np.uint8)  # already 0-255-ish
    img[mask, 0] = np.clip(r[mask], 0, 255).astype(np.uint8)
    img[mask, 1] = np.clip(g[mask], 0, 255).astype(np.uint8)
    img[mask, 2] = np.clip(b[mask], 0, 255).astype(np.uint8)
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")

    cov_path = ID_DIR / "coverage.png"
    fur_path = ID_DIR / "fur_albedo.png"
    cov = np.array(Image.open(cov_path).convert("RGB"))
    fur_sha = hashlib.sha256(fur_path.read_bytes()).hexdigest()
    cov_sha = hashlib.sha256(cov_path.read_bytes()).hexdigest()

    green = (cov[:, :, 0] == 40) & (cov[:, :, 1] == 200) & (cov[:, :, 2] == 70)
    yellow = (cov[:, :, 0] == 230) & (cov[:, :, 1] == 200) & (cov[:, :, 2] == 40)
    red = (cov[:, :, 0] == 200) & (cov[:, :, 1] == 50) & (cov[:, :, 2] == 50)
    island = green | yellow | red
    n_red = int(red.sum())
    n_island = int(island.sum())
    print(f"coverage island={n_island} red={n_red} GY={int((green|yellow).sum())}", flush=True)

    # Blender mesh
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
    tris_uv, tris_nrm = [], []
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
    # normalize once
    nlen = np.linalg.norm(tris_nrm, axis=1, keepdims=True)
    nlen = np.maximum(nlen, 1e-12)
    tris_nrm_u = tris_nrm / nlen

    # Per-view max N·V on UV (no graze cull — track all front/back)
    view_ndotv = {d: np.full((UV_SIZE, UV_SIZE), -2.0, dtype=np.float64) for d in DIRECTIONS}
    # also track whether any triangle covers the texel (UV raster hit)
    uv_hit = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)

    for dname, yaw in DIRECTIONS.items():
        _, _, e_w = get_camera_basis(yaw)
        nd = view_ndotv[dname]
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
            sub = nd[ymin : ymax + 1, xmin : xmax + 1]
            better = inside & (ndotv > sub)
            sub[better] = ndotv
            if dname == "d000":
                uv_hit[ymin : ymax + 1, xmin : xmax + 1] |= inside
        print(f"ndotv map {dname} done", flush=True)

    # best across views
    stack = np.stack([view_ndotv[d] for d in DIRECTIONS], axis=0)
    best = stack.max(axis=0)
    best_view_idx = stack.argmax(axis=0)
    view_names = list(DIRECTIONS.keys())

    # Classification on red
    # geometric blind: best < 0 (all backface or uncovered → -2)
    # threshold-strict: 0 <= best < GRAZE  (would be GY if graze lowered)
    # graze-reachable-but-red: best >= GRAZE — inconsistency / seam / packing (shouldn't be red if fuse tracked)
    # uncovered: best <= -1.5 (never hit by any triangle in our raster)
    # barycentric miss vs PIL island = edge fringe (fuse uv_occ uses PIL fill)
    bary_miss = red & (best <= -1.5)
    geo_blind = red & (best < 0.0) & ~bary_miss
    thresh_strict = red & (best >= 0.0) & (best < NDOTV_GRAZE)
    should_have_cov = red & (best >= NDOTV_GRAZE)

    exterior = ~island
    near_exterior = dilate_bool(exterior, SEAM_DILATE) & island
    seam_band = red & near_exterior

    # exclusive: fringe(seam∩bary_miss) > packing_hole(bary_miss) > anomaly > thresh > geo
    cls_fringe = bary_miss & seam_band
    cls_pack = bary_miss & ~seam_band
    cls_anomaly = should_have_cov & ~bary_miss
    cls_thresh = thresh_strict & ~bary_miss
    cls_geo = geo_blind
    cls_other = red & ~(cls_fringe | cls_pack | cls_anomaly | cls_thresh | cls_geo)
    # aliases for later references
    cls_uncovered = cls_pack  # true packing hole only

    def pct(n: int) -> float:
        return round(100.0 * n / max(1, n_red), 2)

    class_counts = {
        "true_camera_blind_backface": {"n": int(cls_geo.sum()), "pct_of_red": pct(int(cls_geo.sum()))},
        "threshold_strict_0_le_ndotv_lt_graze": {
            "n": int(cls_thresh.sum()),
            "pct_of_red": pct(int(cls_thresh.sum())),
        },
        "anomaly_ndotv_ge_graze_but_red": {
            "n": int(cls_anomaly.sum()),
            "pct_of_red": pct(int(cls_anomaly.sum())),
            "note": "fuse should have marked GY if same mesh/params; likely UV packing fringe or raster diverge",
        },
        "seam_raster_fringe_bary_miss": {
            "n": int(cls_fringe.sum()),
            "pct_of_red": pct(int(cls_fringe.sum())),
            "note": "PIL uv_occ island edge vs barycentric miss; 接缝/光栅边缘",
        },
        "packing_hole_bary_miss_interior": {
            "n": int(cls_pack.sum()),
            "pct_of_red": pct(int(cls_pack.sum())),
        },
        "other_residual": {"n": int(cls_other.sum()), "pct_of_red": pct(int(cls_other.sum()))},
        "seam_band_overlap_any_class": {
            "n": int(seam_band.sum()),
            "pct_of_red": pct(int(seam_band.sum())),
            "dilate_px": SEAM_DILATE,
        },
        "bary_miss_total": {
            "n": int(bary_miss.sum()),
            "pct_of_red": pct(int(bary_miss.sum())),
        },
    }

    # Part distribution
    rmasks = region_masks()
    region_stats = {}
    for name, m in rmasks.items():
        n = int((red & m).sum())
        region_stats[name] = {
            "n_red": n,
            "pct_of_red": pct(n),
            "pct_of_island_region": round(100.0 * n / max(1, int((island & m).sum())), 2),
            "n_island_in_region": int((island & m).sum()),
        }
    bucket_stats = {}
    for bname, names in PART_BUCKETS.items():
        m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
        for nm in names:
            m |= rmasks[nm]
        n = int((red & m).sum())
        bucket_stats[bname] = {
            "n_red": n,
            "pct_of_red": pct(n),
            "regions": names,
            "n_island": int((island & m).sum()),
            "red_over_island_in_bucket": round(n / max(1, int((island & m).sum())), 4),
        }
    ranked_buckets = sorted(bucket_stats.items(), key=lambda kv: kv[1]["n_red"], reverse=True)
    ranked_regions = sorted(region_stats.items(), key=lambda kv: kv[1]["n_red"], reverse=True)

    # Per-view theoretical reach on RED (max N·V and weight^2)
    view_reach = {}
    for di, dname in enumerate(view_names):
        nd = view_ndotv[dname]
        on_red = nd[red]
        # how many red texels this view faces (ndotv>=0 / >=graze / >=direct)
        n_face0 = int((red & (nd >= 0.0)).sum())
        n_graze = int((red & (nd >= NDOTV_GRAZE)).sum())
        n_direct = int((red & (nd >= NDOTV_DIRECT)).sum())
        # if we LOWERED graze to 0.05 / 0.0, how many MORE red become GY from this view alone
        n_if_graze_005 = int((red & (nd >= 0.05)).sum())
        n_if_graze_000 = n_face0
        # theoretical write weight max(N·V,0)^2 on red where this view is best
        is_best = red & (best_view_idx == di) & (nd >= 0.0)
        w = np.maximum(nd, 0.0) ** 2
        view_reach[dname] = {
            "yaw_deg": DIRECTIONS[dname],
            "n_red_ndotv_ge_0": n_face0,
            "n_red_ndotv_ge_graze_0_20": n_graze,
            "n_red_ndotv_ge_direct_0_50": n_direct,
            "n_red_if_graze_0_05": n_if_graze_005,
            "n_red_if_graze_0_00": n_if_graze_000,
            "pct_red_ndotv_ge_0": pct(n_face0),
            "pct_red_ndotv_ge_graze": pct(n_graze),
            "mean_ndotv_on_red_where_best_and_facing": (
                round(float(nd[is_best].mean()), 4) if np.any(is_best) else None
            ),
            "sum_weight_sq_on_red_where_best_facing": (
                round(float(w[is_best].sum()), 2) if np.any(is_best) else 0.0
            ),
            "n_red_where_best_facing": int(is_best.sum()),
            "note_raise_view_weight": "view_weight only scales color accum; coverage class uses N·V only → 升权不能吃红",
        }

    # Global: if graze lowered, how many red convert (union across views)
    convert_if_005 = int((red & (best >= 0.05) & (best < NDOTV_GRAZE)).sum())
    convert_if_000 = int((red & (best >= 0.0) & (best < NDOTV_GRAZE)).sum())
    # best<0 includes bary_miss(-2); do NOT double-count
    still_blind_if_000 = int((red & (best < 0.0)).sum())

    # Heatmaps / overlays
    # 1) red overlay on coverage
    ov = cov.copy()
    ov[red] = (255, 40, 255)  # magenta highlight all red
    Image.fromarray(ov).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "coverage_red_overlay_512.png"
    )

    # 2) class colored map on UV
    class_img = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    class_img[island] = (40, 40, 48)
    class_img[cls_geo] = (220, 60, 60)  # red = true blind
    class_img[cls_thresh] = (230, 180, 40)  # yellow = threshold
    class_img[cls_anomaly] = (80, 200, 255)  # cyan = anomaly
    class_img[cls_fringe] = (255, 140, 40)  # orange = seam raster fringe
    class_img[cls_pack] = (180, 80, 255)  # purple = packing hole
    class_img[cls_other] = (255, 255, 255)
    Image.fromarray(class_img).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "red_class_map_512.png"
    )
    Image.fromarray(class_img).save(OUT / "red_class_map_2048.png")

    # 3) best_ndotv heat on red
    heat = heat_rgb(np.clip(best, -0.2, 1.0), red)
    Image.fromarray(heat).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "red_best_ndotv_heat_512.png"
    )

    # 4) part bucket color map of red
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
    part_img[island] = (35, 36, 42)
    for bname, names in PART_BUCKETS.items():
        m = np.zeros((UV_SIZE, UV_SIZE), dtype=bool)
        for nm in names:
            m |= rmasks[nm]
        part_img[red & m] = part_colors[bname]
    Image.fromarray(part_img).resize((512, 512), Image.Resampling.NEAREST).save(
        OUT / "red_by_part_512.png"
    )

    # legend board
    board = Image.new("RGB", (1100, 560), (20, 22, 28))
    board.paste(Image.fromarray(class_img).resize((512, 512), Image.Resampling.NEAREST), (10, 30))
    board.paste(Image.fromarray(part_img).resize((512, 512), Image.Resampling.NEAREST), (540, 30))
    dr = ImageDraw.Draw(board)
    dr.text((10, 8), "LEFT: R=geo Y=thresh C=anom O=seam-fringe P=pack-hole", fill=(220, 220, 230))
    dr.text((540, 8), "RIGHT: red by part bucket", fill=(220, 220, 230))
    board.save(OUT / "red_attrib_board_512.png")

    # One-line next-step
    top_bucket = ranked_buckets[0][0]
    top_pct = ranked_buckets[0][1]["pct_of_red"]
    geo_pct = class_counts["true_camera_blind_backface"]["pct_of_red"]
    thr_pct = class_counts["threshold_strict_0_le_ndotv_lt_graze"]["pct_of_red"]
    fringe_pct = class_counts["seam_raster_fringe_bary_miss"]["pct_of_red"]
    pack_pct = class_counts["packing_hole_bary_miss_interior"]["pct_of_red"]
    geomish = geo_pct + fringe_pct  # 几何/接缝主导
    if geomish >= 55:
        one_liner = (
            f"红盲主因是几何+接缝（背向 {geo_pct}% + 岛边光栅 {fringe_pct}%），部件顶 {top_bucket}（{top_pct}%）；"
            "升权/降 graze 吃不掉大头；下一刀应加视角或改投影（腹底/低 pitch/腿内侧），禁假绿填红。"
        )
    elif thr_pct >= 40:
        one_liner = (
            f"红盲主因是 graze 阈值过严（0≤N·V<{NDOTV_GRAZE} 占 {thr_pct}%）；"
            "理论上降 graze 可吃一部分，但曾证 graze↑有害——下一刀优先补向/改投影几何，不盲降 graze。"
        )
    else:
        one_liner = (
            f"红盲混合：几何 {geo_pct}% + 岛边 {fringe_pct}% + 阈值 {thr_pct}%（pack {pack_pct}%），顶 {top_bucket} {top_pct}%；"
            "升权吃不到红；下一刀接受几何盲需加视角（或低 pitch 腹底），不拧 EDGE/graze。"
        )

    report = {
        "stage": "coverage_red_blind_attribution_readonly",
        "time_asia_shanghai": now,
        "fur_file_sha256": fur_sha,
        "coverage_sha256": cov_sha,
        "uv_hash": measured,
        "constants": {
            "NDOTV_GRAZE": NDOTV_GRAZE,
            "NDOTV_DIRECT": NDOTV_DIRECT,
            "PITCH": PITCH,
            "SEAM_DILATE": SEAM_DILATE,
            "note": "read-only; did not mutate fur/coverage/EDGE/graze/weights",
        },
        "baseline_coverage": {
            "island": n_island,
            "green": int(green.sum()),
            "yellow": int(yellow.sum()),
            "red": n_red,
            "GY_ratio": round(int((green | yellow).sum()) / max(1, n_island), 4),
            "red_ratio": round(n_red / max(1, n_island), 4),
        },
        "class_counts": class_counts,
        "bucket_stats_ranked": [
            {"bucket": k, **v} for k, v in ranked_buckets
        ],
        "region_stats_ranked": [
            {"region": k, **v} for k, v in ranked_regions
        ],
        "view_reach_on_red": view_reach,
        "theory_if_lower_graze": {
            "convert_red_if_graze_0_05": convert_if_005,
            "convert_red_if_graze_0_00": convert_if_000,
            "pct_convert_if_0_05": pct(convert_if_005),
            "pct_convert_if_0_00": pct(convert_if_000),
            "still_blind_or_uncovered_if_graze_0": still_blind_if_000,
            "pct_still_blind_if_graze_0": pct(still_blind_if_000),
            "raise_view_weight_eats_red": False,
            "raise_view_weight_reason": "coverage class = f(best N·V); view_weight only multiplies accum_rgb",
        },
        "one_liner_next": one_liner,
        "outputs": [
            "coverage_red_overlay_512.png",
            "red_class_map_512.png",
            "red_class_map_2048.png",
            "red_best_ndotv_heat_512.png",
            "red_by_part_512.png",
            "red_attrib_board_512.png",
            "coverage_red_attrib.json",
            "COVERAGE_RED_ATTRIB.md",
        ],
    }

    (OUT / "coverage_red_attrib.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )

    # Markdown
    lines = []
    lines.append("# coverage 红盲归因（只读）")
    lines.append("")
    lines.append(f"**时间**：{now}（Asia/Shanghai）")
    lines.append(f"**fur**：baseline `{fur_sha[:16]}…`（未改）")
    lines.append(f"**coverage SHA**：`{cov_sha[:16]}…`")
    lines.append(f"**UV**：`{measured}`")
    lines.append("")
    lines.append("> 假透空口径（abs&lt;40+CC≥12）已解；**整体 HOLD = coverage 红盲**（GY 70.32% / 红 29.68% FAIL）。本轮不动 fur/源/EDGE/graze/软降/regen，禁假绿填红。")
    lines.append("")
    lines.append("## 基线 coverage")
    lines.append("")
    lines.append(f"| 岛 | 绿 | 黄 | 红 | GY比 | 红比 |")
    lines.append(f"|---:|---:|---:|---:|---:|---:|")
    lines.append(
        f"| {n_island} | {int(green.sum())} | {int(yellow.sum())} | {n_red} | "
        f"{report['baseline_coverage']['GY_ratio']} | {report['baseline_coverage']['red_ratio']} |"
    )
    lines.append("")
    lines.append("## 红 texel 部件占比 top")
    lines.append("")
    lines.append("| 桶 | n_red | 占红% | 桶内红/岛 |")
    lines.append("|---|---:|---:|---:|")
    for k, v in ranked_buckets:
        lines.append(
            f"| **{k}** | {v['n_red']} | {v['pct_of_red']} | {v['red_over_island_in_bucket']} |"
        )
    lines.append("")
    lines.append("### 细区 top-8")
    lines.append("")
    lines.append("| region | n_red | 占红% |")
    lines.append("|---|---:|---:|")
    for k, v in ranked_regions[:8]:
        lines.append(f"| {k} | {v['n_red']} | {v['pct_of_red']} |")
    lines.append("")
    lines.append("## 盲区类型（互斥主类）")
    lines.append("")
    lines.append("| 类型 | n | 占红% | 含义 |")
    lines.append("|---|---:|---:|---|")
    lines.append(
        f"| 真相机盲（背向） | {class_counts['true_camera_blind_backface']['n']} | "
        f"{class_counts['true_camera_blind_backface']['pct_of_red']} | 8 向 max N·V &lt; 0 |"
    )
    lines.append(
        f"| 阈值过严（0≤N·V&lt;0.20） | {class_counts['threshold_strict_0_le_ndotv_lt_graze']['n']} | "
        f"{class_counts['threshold_strict_0_le_ndotv_lt_graze']['pct_of_red']} | 降 graze 理论上可吃 |"
    )
    lines.append(
        f"| 异常（N·V≥graze 仍红） | {class_counts['anomaly_ndotv_ge_graze_but_red']['n']} | "
        f"{class_counts['anomaly_ndotv_ge_graze_but_red']['pct_of_red']} | 接缝/光栅差 |"
    )
    lines.append(
        f"| 岛边光栅差（PIL vs 重心） | {class_counts['seam_raster_fringe_bary_miss']['n']} | "
        f"{class_counts['seam_raster_fringe_bary_miss']['pct_of_red']} | 接缝/光栅边缘 |"
    )
    lines.append(
        f"| 打包内洞 | {class_counts['packing_hole_bary_miss_interior']['n']} | "
        f"{class_counts['packing_hole_bary_miss_interior']['pct_of_red']} | 岛内无重心命中 |"
    )
    lines.append(
        f"| 缝带重叠（非互斥） | {class_counts['seam_band_overlap_any_class']['n']} | "
        f"{class_counts['seam_band_overlap_any_class']['pct_of_red']} | 距岛外 ≤{SEAM_DILATE}px |"
    )
    lines.append("")
    lines.append("## 各向对红区「最大可达」（只记账）")
    lines.append("")
    lines.append("> **升权不能吃红**：coverage 只看 best N·V；`view_weight` 只乘颜色累加。")
    lines.append("")
    lines.append("| 向 | N·V≥0 红数 | ≥graze0.20 | ≥direct0.50 | 若 graze=0.05 | 若 graze=0 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for d in DIRECTIONS:
        vr = view_reach[d]
        lines.append(
            f"| {d} | {vr['n_red_ndotv_ge_0']} | {vr['n_red_ndotv_ge_graze_0_20']} | "
            f"{vr['n_red_ndotv_ge_direct_0_50']} | {vr['n_red_if_graze_0_05']} | {vr['n_red_if_graze_0_00']} |"
        )
    lines.append("")
    lines.append("### 全局降 graze 理论可转化")
    lines.append("")
    t = report["theory_if_lower_graze"]
    lines.append(
        f"- graze→0.05：可转化红 **{t['convert_red_if_graze_0_05']}**（{t['pct_convert_if_0_05']}%）"
    )
    lines.append(
        f"- graze→0.00：可转化红 **{t['convert_red_if_graze_0_00']}**（{t['pct_convert_if_0_00']}%）"
    )
    lines.append(
        f"- 即便 graze=0 仍盲/无命中：**{t['still_blind_or_uncovered_if_graze_0']}**（{t['pct_still_blind_if_graze_0']}%）"
    )
    lines.append("")
    lines.append("## 一句话下一刀")
    lines.append("")
    lines.append(one_liner)
    lines.append("")
    lines.append("## 产出")
    lines.append("")
    for p in report["outputs"]:
        lines.append(f"- `{p}`")
    lines.append("")
    lines.append("锁：不冻、不开 M3、不交用户点2、不动 fur/源/EDGE/graze。")
    lines.append("")
    (OUT / "COVERAGE_RED_ATTRIB.md").write_text("\n".join(lines) + "\n")

    print(json.dumps({
        "ok": True,
        "n_red": n_red,
        "top_buckets": [(k, v["pct_of_red"]) for k, v in ranked_buckets[:5]],
        "class": {k: v["pct_of_red"] for k, v in class_counts.items() if "n" in v},
        "one_liner": one_liner,
    }, ensure_ascii=False, indent=2))
    ev.to_mesh_clear()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
