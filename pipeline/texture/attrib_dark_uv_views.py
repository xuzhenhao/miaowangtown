#!/usr/bin/env python3
"""Read-only UV attribution for d090-visible fused torso relative-dark texels."""
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
DARK_LUM = 40.0
ERODE_ROI = 2

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


def main() -> int:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    ap = argparse.ArgumentParser(description="d090 torso dark UV attribution (read-only)")
    ap.add_argument("--ndotv-graze", type=float, default=None,
                    help="Must match fuse graze floor (default module 0.20 / env M22_NDOTV_GRAZE).")
    ap.add_argument("--edge-erode", type=int, default=None,
                    help="Must match fuse EDGE_ERODE (default 10 / env M22_EDGE_ERODE).")
    ap.add_argument("--tag", default="", help="Suffix for output json/md (e.g. graze035).")
    args = ap.parse_args(argv)
    global NDOTV_GRAZE, EDGE_ERODE
    if args.ndotv_graze is not None:
        NDOTV_GRAZE = float(args.ndotv_graze)
    elif os.environ.get("M22_NDOTV_GRAZE", "").strip():
        NDOTV_GRAZE = float(os.environ["M22_NDOTV_GRAZE"])
    if args.edge_erode is not None:
        EDGE_ERODE = int(args.edge_erode)
    elif os.environ.get("M22_EDGE_ERODE", "").strip():
        EDGE_ERODE = int(os.environ["M22_EDGE_ERODE"])
    out_tag = (args.tag or os.environ.get("M22_ATTRIB_TAG", "")).strip()

    out_dir = OUT / out_tag if out_tag else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
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

    view_w = {d: np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64) for d in DIRECTIONS}
    view_dark_w = {d: np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64) for d in DIRECTIONS}
    view_sample_lum_sum = {d: np.zeros((UV_SIZE, UV_SIZE), dtype=np.float64) for d in DIRECTIONS}

    for dname, yaw in DIRECTIONS.items():
        anchor = prepare_view_rgba(dname)
        if anchor is None:
            print(f"skip {dname}: missing albedo", flush=True)
            continue
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
            sub_w = view_w[dname][ymin : ymax + 1, xmin : xmax + 1]
            sub_dw = view_dark_w[dname][ymin : ymax + 1, xmin : xmax + 1]
            sub_ls = view_sample_lum_sum[dname][ymin : ymax + 1, xmin : xmax + 1]
            sub_w[use] += w_face
            dark_s = use & (lum < DARK_LUM)
            sub_dw[dark_s] += w_face
            sub_ls[use] += lum[use] * w_face
            written += int(use.sum())
        print(f"attrib {dname}: {written} texels", flush=True)

    d090_vis = view_w["d090"] > 0
    d090_torso = fur_a & torso & d090_vis
    if not np.any(d090_torso):
        raise RuntimeError("no d090-visible torso texels")
    p10 = float(np.percentile(fur_lum[d090_torso], 10))
    rel_thr = max(p10, 85.0)
    dark_uv = d090_torso & (fur_lum <= rel_thr)
    dark_uv_abs40 = d090_torso & (fur_lum < DARK_LUM)
    dark_uv_inner = dark_uv & erode_bool(fur_a, ERODE_ROI)

    shares = {}
    dark_src_shares = {}
    n_dark = int(dark_uv_inner.sum())
    for d in DIRECTIONS:
        shares[d] = float(view_w[d][dark_uv_inner].sum()) if n_dark else 0.0
        dark_src_shares[d] = float(view_dark_w[d][dark_uv_inner].sum()) if n_dark else 0.0

    wtot = sum(shares.values()) or 1.0
    dwtot = sum(dark_src_shares.values()) or 1.0
    share_pct = {d: round(100.0 * shares[d] / wtot, 2) for d in DIRECTIONS}
    dark_src_pct = {d: round(100.0 * dark_src_shares[d] / dwtot, 2) for d in DIRECTIONS}
    ranked = sorted(DIRECTIONS.keys(), key=lambda d: dark_src_shares[d], reverse=True)
    ranked_weight = sorted(DIRECTIONS.keys(), key=lambda d: shares[d], reverse=True)

    pull_down = {d: 0.0 for d in DIRECTIONS}
    mean_sample_lum = {}
    for d in DIRECTIONS:
        mask = dark_uv_inner & (view_w[d] > 0)
        if not np.any(mask):
            mean_sample_lum[d] = None
            continue
        mean_sample_lum[d] = round(
            float(view_sample_lum_sum[d][mask].sum() / view_w[d][mask].sum()), 2
        )
        sample_mean = np.zeros_like(fur_lum)
        ww = view_w[d]
        good = ww > 0
        sample_mean[good] = view_sample_lum_sum[d][good] / ww[good]
        pull = mask & (sample_mean < (fur_lum - 5.0))
        pull_down[d] = float(ww[pull].sum())

    pull_tot = sum(pull_down.values()) or 1.0
    pull_pct = {d: round(100.0 * pull_down[d] / pull_tot, 2) for d in DIRECTIONS}
    ranked_pull = sorted(DIRECTIONS.keys(), key=lambda d: pull_down[d], reverse=True)

    # overlay
    x0, y0 = 0, int((1 - 0.75) * 2047)
    x1, y1 = int(0.75 * 2047), int((1 - 0.5) * 2047)
    base = fur[y0:y1, x0:x1, :3].copy()
    ov = base.copy()
    dm = dark_uv_inner[y0:y1, x0:x1]
    ov[dm] = np.array([255, 40, 255], dtype=np.uint8)
    sheet = Image.new("RGB", ((x1 - x0) * 2 + 30, (y1 - y0) + 40), (20, 22, 28))
    sheet.paste(Image.fromarray(base), (10, 30))
    sheet.paste(Image.fromarray(ov), (x1 - x0 + 20, 30))
    dr = ImageDraw.Draw(sheet)
    dr.text(
        (10, 8),
        f"fur torso UV | magenta=d090-vis relative-dark <=max(p10,85)={rel_thr:.1f}",
        fill=(220, 220, 230),
    )
    sheet_path = out_dir / "d090_torso_dark_uv_attrib_overlay.png"
    sheet.save(sheet_path)

    d045_vis = view_w["d045"] > 0
    d045_torso = fur_a & torso & d045_vis
    dark_d045 = d045_torso & (fur_lum <= rel_thr) if np.any(d045_torso) else np.zeros_like(fur_a)
    dark_d045_inner = dark_d045 & erode_bool(fur_a, ERODE_ROI)
    dark_d045_abs40 = (
        d045_torso & (fur_lum < DARK_LUM) if np.any(d045_torso) else np.zeros_like(fur_a)
    )

    top = [d for d in ranked if dark_src_shares[d] > 0][:4]
    top_pull = [d for d in ranked_pull if pull_down[d] > 0][:4]
    call_parts = []
    if share_pct.get("d090", 0) >= 40:
        call_parts.append(f"d090 占总写入权重 {share_pct['d090']}%（同向主导；禁止盲降权）")
    if pull_pct.get("d090", 0) >= 30:
        call_parts.append(f"d090 pull-down {pull_pct['d090']}% → 优先查/重生 d090 源")
    if pull_pct.get("d045", 0) >= 20:
        call_parts.append(f"d045 邻向 pull-down {pull_pct['d045']}% → 查 EDGE/graze")
    if pull_pct.get("d135", 0) >= 20:
        call_parts.append(f"d135 邻向 pull-down {pull_pct['d135']}% → 查 EDGE/graze")
    if pull_pct.get("d000", 0) >= 15:
        call_parts.append(f"d000 pull-down {pull_pct['d000']}%")
    if dark_src_pct.get("d270", 0) >= 10 or pull_pct.get("d270", 0) >= 10:
        call_parts.append("d270 对 d090 可见相对暗带仍有贡献")
    if not call_parts:
        call_parts.append(
            f"权重榜 {ranked_weight[:3]}；pull-down 榜 {top_pull}；abs-dark-sample 榜 {top}"
        )
    if mean_sample_lum.get("d090") is not None and mean_sample_lum["d090"] > rel_thr + 5:
        call_parts.append(
            f"d090 源均亮 {mean_sample_lum['d090']:.1f} > rel_thr → 更像邻向拉低/加权平均"
        )

    report = {
        "stage": "d090_torso_dark_uv_attribution",
        "fur_sha256_pixels": fur_sha,
        "fur_file_sha256": fur_file_sha,
        "uv_hash": measured,
        "constants": {
            "EDGE_ERODE": EDGE_ERODE,
            "NDOTV_GRAZE": NDOTV_GRAZE,
            "DARK_LUM_abs": DARK_LUM,
            "rel_thr": rel_thr,
            "p10_d090_torso": p10,
            "ERODE_ROI_alpha": ERODE_ROI,
            "view_weight": "all 1.0 (no contrast knobs)",
        },
        "set_definition": (
            "fur alpha ∩ torso UV(B1-B4) ∩ d090 weight>0 ∩ fused_lum<=max(p10,85) ∩ alpha-erode2. "
            "Absolute lum<40 nearly empty — false-hollow is relative on black bg. Authority=4x."
        ),
        "n_d090_torso": int(d090_torso.sum()),
        "n_dark_uv_raw": int(dark_uv.sum()),
        "n_dark_uv_inner": n_dark,
        "n_dark_uv_abs40": int(dark_uv_abs40.sum()),
        "n_dark_d045_inner_control": int(dark_d045_inner.sum()),
        "n_dark_d045_abs40_control": int(dark_d045_abs40.sum()),
        "weight_share_pct_on_dark_set": share_pct,
        "dark_sample_weight_share_pct": dark_src_pct,
        "pull_down_weight_share_pct": pull_pct,
        "mean_source_sample_lum_on_dark_set": mean_sample_lum,
        "ranked_by_dark_sample_weight": ranked,
        "ranked_by_total_weight_on_dark": ranked_weight,
        "ranked_by_pull_down": ranked_pull,
        "pollution_call": "；".join(call_parts),
        "top_dark_sample_views": top,
        "top_pull_down_views": top_pull,
        "overlay": str(sheet_path.relative_to(ROOT)),
        "note_opus_align": (
            "Do NOT blind-lower d090 / no view-weight. Screen body-only dark_opaque@40 is "
            "edge-polluted; use UV relative-dark ranking + 4x. d270 stays rolled-back PASS. "
            "This round: NDOTV_GRAZE contrast only (EDGE_ERODE unchanged)."
        ),
    }

    out_json = out_dir / "d090_torso_dark_uv_attrib.json"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    md = out_dir / "D090_TORSO_DARK_UV_ATTRIB.md"
    lines = [
        "# d090 合拢板躯干暗斑 UV 归因（只读）",
        "",
        f"**fur file sha**: `{fur_file_sha[:12]}…`",
        f"**集合**: {report['set_definition']}",
        f"**rel_thr**: {rel_thr:.2f} (p10={p10:.2f})",
        f"**n_dark_inner**: {n_dark}（abs&lt;40: {int(dark_uv_abs40.sum())}；d045 对照: {report['n_dark_d045_inner_control']}）",
        "",
        "## 污染源判定（工作结论）",
        "",
        report["pollution_call"],
        "",
        "## 总写入权重占比（相对暗带上）",
        "",
    ]
    for d in ranked_weight:
        lines.append(f"- **{d}**: {share_pct[d]}%（mean sample lum={mean_sample_lum[d]}）")
    lines += ["", "## pull-down 占比（源比 fused 更暗 ≥5）", ""]
    for d in ranked_pull:
        lines.append(f"- **{d}**: {pull_pct[d]}%")
    lines += [
        "",
        "## abs dark_sample（源 lum&lt;40）占比",
        "",
    ]
    for d in ranked:
        lines.append(f"- **{d}**: {dark_src_pct[d]}%")
    lines += [
        "",
        "## 下一步（仍 HOLD）",
        "",
        "- 禁止盲降 d090 权重；禁止再拧 view-weight。",
        "- 同向主导 → 重生/修该向源；邻向 pull-down → graze/EDGE 小对照，保留旧候选。",
        "- d270 维持回滚 PASS `98a81074…`；本档只动 NDOTV_GRAZE（EDGE 不动）。",
        f"- overlay: `{sheet_path.relative_to(ROOT)}`",
        f"- json: `{out_json.relative_to(ROOT)}`",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ev.to_mesh_clear()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        raise
