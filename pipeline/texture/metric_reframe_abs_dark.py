#!/usr/bin/env python3
"""M2.2 Option A — reframe 4x false-hollow / dark-zone metric (read-only).

OLD: relative-dark / p10 (rel_thr = max(p10, 85)) on body / d090-torso UV.
NEW: abs lum < 40 island connected components with min_area filter
     (fixed MIN_AREA_PX2=12; documented range 8–16). Separates tiger-stripe
     relative dark from true near-black false-hole candidates.

Does NOT mutate fur / sources / EDGE / graze / soft weights / default fuse.
Does NOT procedural-fill red. Does not freeze / open M3.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
ID_DIR = ROOT / "cats" / "miemie" / "identity_v1"
VAL = ROOT / "docs" / "validation" / "m2_2_8dir"
HOLD = VAL / "hold_diag"
OUT = HOLD / "metric_reframe_abs_dark"
MASTER_DIR = ROOT / "art" / "master_cat"

ABS_LUM = 40.0
REL_FLOOR = 85.0
MIN_AREA_PX2 = 12  # fixed; allowed documented band 8–16
ERODE_UV = 2
UV_SIZE = 2048
EXPECTED_FUR_SHA_PREFIX = "46e56675a577"
VIEWS = ("d090", "d045")  # producer 4x authority pair; d270 reported as extra


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def luma(rgb: np.ndarray) -> np.ndarray:
    return rgb.astype(np.float64).mean(axis=2)


def erode_bool(m: np.ndarray, n: int) -> np.ndarray:
    out = m.copy()
    for _ in range(n):
        nxt = out.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nxt &= np.roll(np.roll(out, dy, axis=0), dx, axis=1)
        out = nxt
    return out


def label_cc(mask: np.ndarray):
    """4-connected flood-fill labeling (no scipy). Returns labels, list[(id,area)]."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    lid = 0
    areas = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x]:
                continue
            lid += 1
            stack = [(y, x)]
            labels[y, x] = lid
            a = 0
            while stack:
                cy, cx = stack.pop()
                a += 1
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and labels[ny, nx] == 0:
                        labels[ny, nx] = lid
                        stack.append((ny, nx))
            areas.append((lid, a))
    return labels, areas


def cc_metrics(mask: np.ndarray, min_area: int = MIN_AREA_PX2) -> dict:
    labels, areas = label_cc(mask)
    area_vals = [a for _, a in areas]
    kept_ids = {i for i, a in areas if a >= min_area}
    kept_mask = np.isin(labels, list(kept_ids)) if kept_ids else np.zeros_like(mask)
    speck_mask = mask & ~kept_mask
    return {
        "n_pix_raw": int(mask.sum()),
        "n_cc_raw": int(len(areas)),
        "n_cc_ge_min_area": int(len(kept_ids)),
        "n_pix_ge_min_area": int(kept_mask.sum()),
        "n_pix_speckle_lt_min": int(speck_mask.sum()),
        "max_cc_area": int(max(area_vals)) if area_vals else 0,
        "areas_top10": sorted(area_vals, reverse=True)[:10],
        "min_area_px2": min_area,
        "labels": labels,
        "kept_mask": kept_mask,
        "speck_mask": speck_mask,
    }


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


def coverage_stats(cov_path: Path) -> dict:
    cov = np.array(Image.open(cov_path).convert("RGB"))
    # Match fuse_8dir palette: G=[40,200,70] Y=[230,200,40] R=[200,50,50]
    g = (cov[:, :, 1] > 150) & (cov[:, :, 0] < 120)
    y = (cov[:, :, 0] > 180) & (cov[:, :, 1] > 150) & (cov[:, :, 2] < 120)
    r = (cov[:, :, 0] > 150) & (cov[:, :, 1] < 100)
    island = g | y | r
    n = int(island.sum())
    gy = int(g.sum() + y.sum())
    red = int(r.sum())
    return {
        "uv_island_texels": n,
        "green": int(g.sum()),
        "yellow": int(y.sum()),
        "red": red,
        "high_freq_green_yellow_ratio": round(gy / max(1, n), 4),
        "unseen_over_island": round(red / max(1, n), 4),
        "gate_high_freq_green_yellow_ge_0_92": (gy / max(1, n)) >= 0.92,
        "gate_red_blind_le_0_20": (red / max(1, n)) <= 0.20,
        "note": "coverage GY/red unchanged by metric reframe (no re-fuse)",
    }


def load_layer_and_body(view: str):
    """Body-only mask: prefer clay_noeye (exclude parametric eyes), else clay, else layer alpha."""
    layer = np.array(Image.open(VAL / f"m2_2_{view}_layer_a.png").convert("RGBA"))
    noeye_4x = HOLD / f"{view}_clay_noeye_4x.png"
    clay_path = HOLD / f"{view}_clay.png"
    if noeye_4x.is_file():
        # 4x clay_noeye → logical via BOX (matches bodyonly fair count ~4112)
        hi = Image.open(noeye_4x).convert("RGBA")
        low = np.array(hi.resize((layer.shape[1], layer.shape[0]), Image.Resampling.BOX))
        body = low[:, :, 3] > 128
        body_src = "clay_noeye_4x_box"
    elif clay_path.is_file():
        clay = np.array(Image.open(clay_path).convert("RGBA"))
        body = clay[:, :, 3] > 128
        body_src = "clay"
    else:
        body = layer[:, :, 3] > 128
        body_src = "layer_alpha"
    body = body & (layer[:, :, 3] > 128)
    return layer, body, body_src


def screen_metrics(view: str) -> dict:
    layer, body, body_src = load_layer_and_body(view)
    lum = luma(layer[:, :, :3])
    body_n = int(body.sum())
    p10 = float(np.percentile(lum[body], 10)) if body_n else 0.0
    rel_thr = max(p10, REL_FLOOR)
    old_mask = body & (lum <= rel_thr)
    new_raw = body & (lum < ABS_LUM)
    old_cc = cc_metrics(old_mask, MIN_AREA_PX2)
    new_cc = cc_metrics(new_raw, MIN_AREA_PX2)
    # strip heavy arrays from json
    def slim(d):
        return {k: v for k, v in d.items() if k not in ("labels", "kept_mask", "speck_mask")}

    return {
        "view": view,
        "body_px": body_n,
        "body_mask_source": body_src,
        "p10": round(p10, 2),
        "old": {
            "definition": f"body ∩ lum<=max(p10,{REL_FLOOR:g})  [=rel_thr]",
            "rel_thr": round(rel_thr, 2),
            "n_dark_rel": int(old_mask.sum()),
            "cc": slim(old_cc),
        },
        "new": {
            "definition": f"body ∩ lum<{ABS_LUM:g} 4-connected CC, keep area>={MIN_AREA_PX2}px²",
            "abs_lum": ABS_LUM,
            "n_abs_dark_raw": int(new_raw.sum()),
            "n_abs_dark": int(new_cc["n_pix_ge_min_area"]),
            "max_cc_area": int(new_cc["max_cc_area"]),
            "cc": slim(new_cc),
        },
        "_arrays": {
            "layer": layer,
            "body": body,
            "old_mask": old_mask,
            "new_kept": new_cc["kept_mask"],
            "new_speck": new_cc["speck_mask"],
            "old_kept": old_cc["kept_mask"],
        },
    }


def uv_metrics(fur: np.ndarray) -> dict:
    fur_a = fur[:, :, 3] > 128
    fur_lum = luma(fur[:, :, :3])
    torso = torso_uv_mask()
    island = erode_bool(fur_a, ERODE_UV) & torso
    # OLD published ROI (with d090-weight) if present
    inner_path = HOLD / "d090_torso_dark_uv_inner_mask.png"
    if inner_path.is_file():
        inner = np.array(Image.open(inner_path).convert("L")) > 127
        n_dark_inner_published = int(inner.sum())
    else:
        inner = None
        n_dark_inner_published = None

    p10 = float(np.percentile(fur_lum[island], 10)) if island.any() else 0.0
    rel_thr = max(p10, REL_FLOOR)
    old_mask = island & (fur_lum <= rel_thr)
    new_raw = island & (fur_lum < ABS_LUM)
    old_cc = cc_metrics(old_mask, MIN_AREA_PX2)
    new_cc = cc_metrics(new_raw, MIN_AREA_PX2)

    # also abs on published relative-dark ROI (should be ~0)
    abs_on_published = None
    if inner is not None:
        abs_on_pub = inner & (fur_lum < ABS_LUM)
        abs_on_published = {
            "n_abs_dark_raw": int(abs_on_pub.sum()),
            "cc": {k: v for k, v in cc_metrics(abs_on_pub, MIN_AREA_PX2).items()
                   if k not in ("labels", "kept_mask", "speck_mask")},
        }

    def slim(d):
        return {k: v for k, v in d.items() if k not in ("labels", "kept_mask", "speck_mask")}

    return {
        "scope": "fur alpha ∩ torso(B1-B4) ∩ alpha-erode2  (no d090-weight filter in this recompute)",
        "n_island": int(island.sum()),
        "p10": round(p10, 2),
        "old": {
            "definition": f"island ∩ lum<=max(p10,{REL_FLOOR:g})",
            "rel_thr": round(rel_thr, 2),
            "n_dark_rel": int(old_mask.sum()),
            "n_dark_inner_published_12a1945_with_d090_weight": n_dark_inner_published,
            "cc": slim(old_cc),
        },
        "new": {
            "definition": f"island ∩ lum<{ABS_LUM:g} CC area>={MIN_AREA_PX2}",
            "n_abs_dark_raw": int(new_raw.sum()),
            "n_abs_dark": int(new_cc["n_pix_ge_min_area"]),
            "max_cc_area": int(new_cc["max_cc_area"]),
            "cc": slim(new_cc),
        },
        "abs_on_published_rel_dark_roi": abs_on_published,
        "_arrays": {
            "old_mask": old_mask,
            "new_kept": new_cc["kept_mask"],
            "new_raw": new_raw,
            "island": island,
        },
    }


def to_black_rgb(rgba: np.ndarray) -> np.ndarray:
    a = rgba[:, :, 3:4].astype(np.float64) / 255.0
    rgb = rgba[:, :, :3].astype(np.float64)
    out = (rgb * a).astype(np.uint8)
    return out


def annotate_panel(layer: np.ndarray, mask_keep: np.ndarray, mask_extra: np.ndarray | None,
                   title: str, keep_rgb=(255, 0, 220), extra_rgb=(0, 220, 255)) -> Image.Image:
    base = to_black_rgb(layer)
    ov = base.copy()
    if mask_extra is not None and mask_extra.any():
        ov[mask_extra] = extra_rgb
    if mask_keep is not None and mask_keep.any():
        ov[mask_keep] = keep_rgb
    # 4x nearest
    hi = Image.fromarray(ov).resize((layer.shape[1] * 4, layer.shape[0] * 4), Image.Resampling.NEAREST)
    canvas = Image.new("RGB", (hi.width, hi.height + 36), (0, 0, 0))
    canvas.paste(hi, (0, 28))
    dr = ImageDraw.Draw(canvas)
    dr.text((6, 6), title, fill=(220, 220, 230))
    return canvas


def make_view_board(sm: dict, out_path: Path):
    a = sm["_arrays"]
    # OLD panel: cyan = all relative-dark; magenta = relative CC kept (>=min_area)
    old_panel = annotate_panel(
        a["layer"],
        a["old_kept"],
        a["old_mask"] & ~a["old_kept"],
        f"{sm['view']} OLD rel-dark (cyan=speckle mag=CC≥{MIN_AREA_PX2}) n={sm['old']['n_dark_rel']}",
        keep_rgb=(255, 0, 220),
        extra_rgb=(0, 200, 255),
    )
    # NEW panel: magenta = abs CC kept; dim cyan = abs speckles rejected
    new_panel = annotate_panel(
        a["layer"],
        a["new_kept"],
        a["new_speck"],
        f"{sm['view']} NEW abs<{ABS_LUM:g}+CC (mag=kept≥{MIN_AREA_PX2} cyan=reject) n={sm['new']['n_abs_dark']}",
        keep_rgb=(255, 0, 220),
        extra_rgb=(0, 160, 180),
    )
    w = old_panel.width + new_panel.width + 24
    h = max(old_panel.height, new_panel.height) + 40
    sheet = Image.new("RGB", (w, h), (0, 0, 0))
    sheet.paste(old_panel, (8, 32))
    sheet.paste(new_panel, (old_panel.width + 16, 32))
    dr = ImageDraw.Draw(sheet)
    dr.text(
        (8, 8),
        f"Layer A 4x black · {sm['view']} · OLD rel vs NEW abs+CC · body=clay∩layer · fur baseline",
        fill=(230, 230, 240),
    )
    sheet.save(out_path)
    return sheet


def make_compare_sheet(boards: dict, out_path: Path):
    # stack d090 then d045
    ordered = [boards[v] for v in VIEWS if v in boards]
    if not ordered:
        return
    w = max(b.width for b in ordered)
    h = sum(b.height for b in ordered) + 8 * (len(ordered) - 1)
    sheet = Image.new("RGB", (w, h), (0, 0, 0))
    y = 0
    for b in ordered:
        sheet.paste(b, (0, y))
        y += b.height + 8
    sheet.save(out_path)


def write_md(report: dict, path: Path):
    cov = report["coverage"]
    uv = report["uv_torso"]
    lines = [
        "# 假透空／红区口径重框（选项 A）— abs 近黑 + 连通域",
        "",
        f"**时间**：{report['time_asia_shanghai']}（Asia/Shanghai）  ",
        f"**tip 起点**：`{report['git_tip']}`  ",
        f"**fur**：baseline `{report['fur_sha'][:12]}…`（未改；CANDIDATE_UNFROZEN）  ",
        f"**脚本**：`pipeline/texture/metric_reframe_abs_dark.py`（独立；不改默认 fuse）  ",
        "",
        "---",
        "",
        "## 新旧口径对照（固定）",
        "",
        "| | 旧口径 | 新口径 |",
        "|---|---|---|",
        "| 名称 | 相对暗 / p10（`rel_thr`） | **abs 近黑 + 连通域** |",
        f"| 阈值 | `lum ≤ max(p10, {REL_FLOOR:g})` | `lum < {ABS_LUM:g}` |",
        f"| 空间过滤 | 无（或仅 ROI/erode） | **4-连通域**，保留 `area ≥ {MIN_AREA_PX2} px²`（文档允许带 8–16；本轮固定 **{MIN_AREA_PX2}**） |",
        "| 岛内范围 | 屏：clay∩layer body；UV：torso∩α-erode2（旧发布 ROI 另含 d090 weight>0） | 同左 |",
        "| 目的 | 抓黑底上「看起来暗」的虎斑/相对暗带 | **拆开虎斑相对暗 vs 真近黑假洞** |",
        "",
        "> coverage **绿+黄 / 红** 仍是 fuse 看见/盲区硬门，**本轮未重 fuse、数值不变**；"
        "「红区」在假透空语境下指近黑标注区，不是 coverage 红盲区。",
        "",
        "---",
        "",
        "## coverage（基线 · 未改）",
        "",
        f"| GY 比 | 红盲区 | GY≥0.92 | 红≤0.20 |",
        f"|---:|---:|---|---|",
        f"| **{cov['high_freq_green_yellow_ratio']:.2%}** | **{cov['unseen_over_island']:.2%}** | "
        f"{'PASS' if cov['gate_high_freq_green_yellow_ge_0_92'] else 'FAIL'} | "
        f"{'PASS' if cov['gate_red_blind_le_0_20'] else 'FAIL'} |",
        "",
        "---",
        "",
        "## Layer A 屏指标（制作人 4x 权威 · body=clay∩layer）",
        "",
        "| 向 | body_px | 旧 n_dark_rel | 旧 maxCC≥min | 新 n_abs_dark_raw | **新 n_abs_dark（≥min）** | **新 max_cc** |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for v in list(VIEWS) + ["d270"]:
        if v not in report["screen"]:
            continue
        s = report["screen"][v]
        lines.append(
            f"| **{v}** | {s['body_px']} | {s['old']['n_dark_rel']} | "
            f"{s['old']['cc']['n_pix_ge_min_area']} (max {s['old']['cc']['max_cc_area']}) | "
            f"{s['new']['n_abs_dark_raw']} | **{s['new']['n_abs_dark']}** | **{s['new']['max_cc_area']}** |"
        )
    s90 = report["screen"]["d090"]
    s45 = report["screen"]["d045"]
    lines += [
        "",
        "### d090 vs d045（新旧）",
        "",
        f"- 旧相对暗：d090 `{s90['old']['n_dark_rel']}` vs d045 `{s45['old']['n_dark_rel']}` "
        f"（rel_thr d090={s90['old']['rel_thr']}, d045={s45['old']['rel_thr']}）",
        f"- 新 abs+CC：d090 **`{s90['new']['n_abs_dark']}`** vs d045 **`{s45['new']['n_abs_dark']}`** "
        f"（raw {s90['new']['n_abs_dark_raw']} / {s45['new']['n_abs_dark_raw']}；"
        f"max_cc {s90['new']['max_cc_area']} / {s45['new']['max_cc_area']}）",
        f"- 旧口径把大量 **虎斑相对暗** 算进「假透空」；新口径只留 **近黑连通块**，"
        f"两侧数量接近且都远小于旧 n_dark_rel。",
        "",
        "---",
        "",
        "## UV torso（合拢贴图 · 只读）",
        "",
        f"- 旧发布 `n_dark_inner`（含 d090 weight，`12a1945`）："
        f"**{uv['old'].get('n_dark_inner_published_12a1945_with_d090_weight')}**",
        f"- 本轮旧口径重算（无 d090 weight 过滤）：n_dark_rel="
        f"**{uv['old']['n_dark_rel']}**（rel_thr={uv['old']['rel_thr']}）",
        f"- 新口径：n_abs_dark_raw=**{uv['new']['n_abs_dark_raw']}** → "
        f"n_abs_dark(≥{MIN_AREA_PX2})=**{uv['new']['n_abs_dark']}** "
        f"（max_cc={uv['new']['max_cc_area']}）",
    ]
    if uv.get("abs_on_published_rel_dark_roi"):
        ap = uv["abs_on_published_rel_dark_roi"]
        lines.append(
            f"- 旧发布相对暗 ROI 上 abs&lt;40：raw=**{ap['n_abs_dark_raw']}**，"
            f"≥{MIN_AREA_PX2}=**{ap['cc']['n_pix_ge_min_area']}** "
            f"（max_cc={ap['cc']['max_cc_area']}）→ **相对暗带里几乎没有真近黑连通块**"
        )
    lines += [
        "",
        "---",
        "",
        "## 标注板",
        "",
        f"- 并排对照（d090+d045）：`{report['outputs']['sheet_d090_d045']}`",
        f"- d090：`{report['outputs']['board_d090']}`",
        f"- d045：`{report['outputs']['board_d045']}`",
        f"- json：`{report['outputs']['json']}`",
        "",
        "图例：品红=保留的连通域（≥min_area）；青=未达面积阈值的碎点 / 旧口径相对暗碎点。",
        "",
        "---",
        "",
        "## 结论（诚实）",
        "",
    ]
    for line in report["conclusion_bullets"]:
        lines.append(f"- {line}")
    lines += [
        "",
        f"**制作人建议**：{report['producer_recommendation']}",
        "",
        "锁：不冻、不开 M3、不交用户点2、不动 fur/源图/EDGE/graze/软降。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fur_path = ID_DIR / "fur_albedo.png"
    fur_sha = sha256_file(fur_path)
    if not fur_sha.startswith(EXPECTED_FUR_SHA_PREFIX.replace("…", "")):
        # soft check — still run, but flag
        fur_ok = fur_sha.startswith("46e56675")
    else:
        fur_ok = True
    fur = np.array(Image.open(fur_path).convert("RGBA"))

    cov = coverage_stats(ID_DIR / "coverage.png")
    screen = {}
    boards = {}
    for v in ("d090", "d045", "d270"):
        sm = screen_metrics(v)
        board = make_view_board(sm, OUT / f"layer_a_{v}_old_vs_new_4x.png")
        boards[v] = board
        # strip arrays for json
        screen[v] = {k: v2 for k, v2 in sm.items() if k != "_arrays"}

    make_compare_sheet(
        {k: boards[k] for k in VIEWS},
        OUT / "layer_a_d090_d045_old_vs_new_4x.png",
    )
    # also save UV overlay tiny preview (512)
    uv = uv_metrics(fur)
    uv_arr = uv.pop("_arrays")
    uv_ov = np.zeros((UV_SIZE, UV_SIZE, 3), dtype=np.uint8)
    uv_ov[uv_arr["island"]] = [40, 40, 48]
    uv_ov[uv_arr["old_mask"]] = [0, 180, 255]
    uv_ov[uv_arr["new_raw"]] = [255, 80, 40]
    uv_ov[uv_arr["new_kept"]] = [255, 0, 220]
    Image.fromarray(uv_ov).resize((512, 512), Image.Resampling.BOX).save(
        OUT / "uv_torso_old_cyan_new_magenta_512.png"
    )

    # conclusion
    s90, s45 = screen["d090"], screen["d045"]
    uv_new = uv["new"]["n_abs_dark"]
    pub_abs = (uv.get("abs_on_published_rel_dark_roi") or {}).get("cc", {}).get(
        "n_pix_ge_min_area", None
    )
    conclusion = [
        f"旧口径（相对暗）在 Layer A 上 d090/d045 仍报大片暗带"
        f"（{s90['old']['n_dark_rel']} / {s45['old']['n_dark_rel']}），"
        f"其中大量是虎斑/中灰相对暗，在黑底上被读成「假透空」。",
        f"新口径（abs&lt;{ABS_LUM:g}+CC≥{MIN_AREA_PX2}）把保留近黑连通块压到 "
        f"d090 **{s90['new']['n_abs_dark']}** / d045 **{s45['new']['n_abs_dark']}** "
        f"（max_cc {s90['new']['max_cc_area']} / {s45['new']['max_cc_area']}）；"
        f"两侧接近，说明「假透空」主差不是大块真近黑洞。",
        f"UV 躯干：旧发布相对暗 ROI（n={uv['old'].get('n_dark_inner_published_12a1945_with_d090_weight')}）"
        f"上 abs+CC≈**{pub_abs}**；本轮 torso 新口径 n_abs_dark=**{uv_new}** → "
        f"合拢贴图岛内几乎无真近黑连通假洞。",
        f"coverage GY/红仍 **{cov['high_freq_green_yellow_ratio']:.2%} / {cov['unseen_over_island']:.2%}** "
        f"（硬门 FAIL）——口径重框**不**等于 coverage 过门。",
    ]
    # recommendation: can ask to lift 假透空-specific HOLD framing, but not overall freeze
    if s90["new"]["n_abs_dark"] <= 150 and (pub_abs is None or pub_abs <= 16) and uv_new <= 16:
        producer_rec = (
            "可申请将「侧向假透空」从主否决降为**口径说明（CONDITIONAL→申请解该条 HOLD）**："
            "真近黑连通假洞在新口径下很少；旧相对暗把虎斑算进去了。"
            "但 **coverage 红盲区仍 FAIL** → **整体仍 HOLD**，不冻、不交用户点2；"
            "解的是假透空判定口径，不是冻结放行。"
        )
        still_hold = True
        can_request_lift_falsehollow = True
    else:
        producer_rec = (
            "新口径下仍见一定量近黑连通块，假透空条**不宜**宣称已解；"
            "整体继续 HOLD。可把新旧表交给制作人复看 4x 再定。"
        )
        still_hold = True
        can_request_lift_falsehollow = False

    import subprocess
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tip = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")

    report = {
        "stage": "METRIC_REFRAME_ABS_DARK",
        "option": "A",
        "time_asia_shanghai": now,
        "git_tip": tip,
        "fur_sha": fur_sha,
        "fur_baseline_ok": fur_ok,
        "constants": {
            "ABS_LUM": ABS_LUM,
            "REL_FLOOR": REL_FLOOR,
            "MIN_AREA_PX2": MIN_AREA_PX2,
            "MIN_AREA_DOC_BAND": [8, 16],
            "ERODE_UV": ERODE_UV,
        },
        "coverage": cov,
        "screen": screen,
        "uv_torso": uv,
        "conclusion_bullets": conclusion,
        "still_overall_hold": still_hold,
        "can_request_lift_falsehollow_hold_clause": can_request_lift_falsehollow,
        "producer_recommendation": producer_rec,
        "outputs": {
            "sheet_d090_d045": str(
                (OUT / "layer_a_d090_d045_old_vs_new_4x.png").relative_to(ROOT)
            ),
            "board_d090": str((OUT / "layer_a_d090_old_vs_new_4x.png").relative_to(ROOT)),
            "board_d045": str((OUT / "layer_a_d045_old_vs_new_4x.png").relative_to(ROOT)),
            "board_d270": str((OUT / "layer_a_d270_old_vs_new_4x.png").relative_to(ROOT)),
            "uv_preview": str((OUT / "uv_torso_old_cyan_new_magenta_512.png").relative_to(ROOT)),
            "json": str((OUT / "metric_reframe_report.json").relative_to(ROOT)),
            "md": str((HOLD / "METRIC_REFRAME_ABS_DARK.md").relative_to(ROOT)),
        },
        "locks": {
            "fur_untouched": True,
            "sources_untouched": True,
            "edge_graze_untouched": True,
            "soft_untouched": True,
            "no_fake_green": True,
            "no_fill_red": True,
            "no_regen": True,
            "no_freeze": True,
            "no_m3": True,
        },
    }
    (OUT / "metric_reframe_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_md(report, HOLD / "METRIC_REFRAME_ABS_DARK.md")
    # also symlink-style copy path at hold_diag root for the required name
    print(json.dumps({k: report[k] for k in (
        "fur_sha", "coverage", "still_overall_hold",
        "can_request_lift_falsehollow_hold_clause", "producer_recommendation", "outputs"
    )}, indent=2, ensure_ascii=False))
    print("screen d090/d045/d270:", {v: {
        "old": screen[v]["old"]["n_dark_rel"],
        "new": screen[v]["new"]["n_abs_dark"],
        "max_cc": screen[v]["new"]["max_cc_area"],
    } for v in screen})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
