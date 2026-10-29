#!/usr/bin/env python3
"""
M2.1 Step A — Freeze miemie CatGenome + five markings from life photos (Lab midtones)
and Route A v4.1 / fused-spec anatomical evidence. Never projects photos into UV.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path("/workspace/miaowangtown")
sys.path.insert(0, str(ROOT))
from pipeline.common.color import mean_lab_hex, rgb_to_hex, rgb_u8_to_lab  # noqa: E402

PHOTOS = ROOT / "reference" / "miemie_photos"
OUT = ROOT / "cats" / "miemie" / "identity_v1"
UV_MANIFEST = ROOT / "art" / "master_cat" / "uv_manifest.json"
MASTER_SPEC = ROOT / "art" / "master_cat" / "master_spec.json"


def load_rgb(name: str) -> np.ndarray:
    return np.array(Image.open(PHOTOS / name).convert("RGB"))


def mask_sample(im: np.ndarray, mask: np.ndarray, drop: float = 5.0) -> dict:
    pix = im[mask]
    return mean_lab_hex(pix, drop_pct=drop)


def extract_colors() -> dict:
    front = load_rgb("miemie_ref_01_front45_loaf.jpg")
    muzzle = load_rgb("reference_muzzle_closeup.jpg")
    flank = load_rgb("miemie_ref_02_left_flank_white_patch.jpg")
    belly = load_rgb("miemie_ref_08_left_side_orange_belly.jpg")
    eye_src = load_rgb("photo_03_top_angle.jpg")
    eye_src2 = load_rgb("photo_04_front_loaf.jpg")

    def luma(a):
        return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]

    # Base warm tabby midtones (forehead / dorsal, drop extremes)
    h, w = front.shape[:2]
    base_roi = front[int(h * 0.12) : int(h * 0.38), int(w * 0.30) : int(w * 0.72)]
    r, g, b = base_roi[:, :, 0], base_roi[:, :, 1], base_roi[:, :, 2]
    lu = luma(base_roi)
    base_m = (lu > 70) & (lu < 160) & (r > 60) & (r < 180) & (b < g + 5)
    base = mask_sample(base_roi, base_m, 15)

    # Dark mackerel stripes
    stripe_m = (lu < 70) & (r > 20)
    stripe = mask_sample(base_roi, stripe_m, 5)

    # White chest / bib
    mh, mw = muzzle.shape[:2]
    chest_roi = muzzle[int(mh * 0.62) : int(mh * 0.92), int(mw * 0.25) : int(mw * 0.75)]
    cl = luma(chest_roi)
    white_m = (cl > 175) & (np.abs(chest_roi[:, :, 0].astype(int) - chest_roi[:, :, 1]) < 30)
    white = mask_sample(chest_roi, white_m, 8)

    # Left-flank white cloud
    fh, fw = flank.shape[:2]
    fl_roi = flank[int(fh * 0.35) : int(fh * 0.80), int(fw * 0.15) : int(fw * 0.70)]
    fl = luma(fl_roi)
    cloud_m = (fl > 185) & (np.abs(fl_roi[:, :, 0].astype(int) - fl_roi[:, :, 1]) < 28)
    cloud = mask_sample(fl_roi, cloud_m, 8)

    # Right-muzzle caramel peanut (warm mid brown, mid face)
    car_roi = muzzle[int(mh * 0.42) : int(mh * 0.68), int(mw * 0.18) : int(mw * 0.48)]
    cr, cg, cb = car_roi[:, :, 0], car_roi[:, :, 1], car_roi[:, :, 2]
    clu = luma(car_roi)
    car_m = (cr > cb + 18) & (cr > 90) & (cr < 200) & (cg < cr * 0.98) & (clu > 70) & (clu < 170)
    caramel = mask_sample(car_roi, car_m, 12)

    # Apricot / warm belly-edge transition
    bh, bw = belly.shape[:2]
    bel_roi = belly[int(bh * 0.40) : int(bh * 0.75), int(bw * 0.20) : int(bw * 0.70)]
    br, bg, bb = bel_roi[:, :, 0], bel_roi[:, :, 1], bel_roi[:, :, 2]
    blu = luma(bel_roi)
    apr_m = (br > bb + 22) & (br > 115) & (br < 210) & (bg > 75) & (blu > 90) & (blu < 170)
    apricot = mask_sample(bel_roi, apr_m, 12)

    # Emerald iris from photos (aggregate green-dominant pixels)
    def eye_mask(im):
        r, g, b = im[:, :, 0].astype(np.int16), im[:, :, 1].astype(np.int16), im[:, :, 2].astype(np.int16)
        return (g > r + 10) & (g > b + 6) & (g > 55) & (g < 190) & (r > 25) & (b > 15)

    eye_pix = np.concatenate([eye_src[eye_mask(eye_src)], eye_src2[eye_mask(eye_src2)]], axis=0)
    eye = mean_lab_hex(eye_pix, drop_pct=10)

    # Brick-pink nose leather: reddish midtones near face center of muzzle shot
    nose_roi = muzzle[int(mh * 0.38) : int(mh * 0.55), int(mw * 0.38) : int(mw * 0.58)]
    nr, ng, nb = nose_roi[:, :, 0], nose_roi[:, :, 1], nose_roi[:, :, 2]
    nlu = luma(nose_roi)
    # Prefer warmer / pinker: R clearly above G and B, not too dark
    nose_m = (nr > ng + 12) & (nr > nb + 18) & (nr > 100) & (nr < 210) & (ng > 40) & (nlu > 55) & (nlu < 160)
    if int(nose_m.sum()) < 40:
        # fallback: any warm mid face
        nose_m = (nr > nb + 15) & (nr > 90) & (nlu > 50) & (nlu < 150)
    nose = mask_sample(nose_roi, nose_m, 10)

    return {
        "base_tabby": base,
        "stripe_dark": stripe,
        "white_cream": white,
        "white_flank_cloud": cloud,
        "caramel_peanut_R": caramel,
        "apricot_belly_edge": apricot,
        "eye_emerald": eye,
        "nose_brick": nose,
    }


def build_markings(colors: dict, uv_version: int) -> dict:
    """
    Anatomical L/R freeze (cat body axes):
      - caramel peanut on muzzle _R / X>0
      - left-face cream + left-flank white cloud on _L / X<0
      - chest bib → belly white
      - apricot transition on left belly edge
      - front-high / hind-short white socks
    UV polygons sit inside the frozen 4x4 asymmetric islands (approximate centers).
    """
    c_car = colors["caramel_peanut_R"]["srgb"]
    c_white = colors["white_cream"]["srgb"]
    c_cloud = colors["white_flank_cloud"]["srgb"]
    c_apr = colors["apricot_belly_edge"]["srgb"]
    c_stripe = colors["stripe_dark"]["srgb"]
    c_base = colors["base_tabby"]["srgb"]

    markers = [
        {
            "id": "mark_01_muzzle_peanut",
            "name": "阴阳花生嘴套（右满暖焦糖 / 左浅奶油白）",
            "semantic_part": "head_muzzle",
            "anatomical_side": "asymmetric_LR",
            "space": "uv",
            "components": [
                {
                    "id": "mark_01_caramel_R",
                    "side": "_R",
                    "x_sign": ">0",
                    "uv_region": "A3_muzzle_chin",
                    "polygon": [[0.58, 0.86], [0.64, 0.90], [0.62, 0.94], [0.56, 0.91]],
                    "color": c_car,
                    "note": "猫右嘴套暖焦糖花生斑；正面/d045 画面偏左",
                },
                {
                    "id": "mark_01_cream_L",
                    "side": "_L",
                    "x_sign": "<0",
                    "uv_region": "A3_muzzle_chin",
                    "polygon": [[0.66, 0.85], [0.72, 0.88], [0.70, 0.93], [0.64, 0.90]],
                    "color": c_white,
                    "note": "猫左脸颊奶油白；正面/d045 画面偏右",
                },
            ],
            "color": c_car,
            "edge_color": c_base,
            "source_type": "observed",
            "confidence": 0.98,
            "crosses_uv_seam": False,
            "source_photos": [
                {"slot": "muzzle_closeup", "file": "reference_muzzle_closeup.jpg"},
                {"slot": "asymmetry", "file": "photo_07_closeup_asymmetry.jpg"},
                {"slot": "v4_1_anchor", "file": "docs/validation/route_a_v4_1_ultimate/route_a_v4_1_unlit_albedo_anchor_hi.png", "role": "stylized_evidence"},
            ],
            "user_confirmed": True,
        },
        {
            "id": "mark_02_chest_bib_and_left_cloud",
            "name": "胸前白围脖连左肋白云",
            "semantic_part": "torso_front+torso_L",
            "anatomical_side": "_L",
            "space": "uv",
            "components": [
                {
                    "id": "mark_02_chest_bib",
                    "side": "C",
                    "uv_region": "B4_torso_belly",
                    "polygon": [[0.82, 0.58], [0.92, 0.58], [0.92, 0.68], [0.82, 0.68]],
                    "color": c_white,
                },
                {
                    "id": "mark_02_left_flank_cloud",
                    "side": "_L",
                    "x_sign": "<0",
                    "uv_region": "B1_torso_L",
                    "polygon": [[0.06, 0.56], [0.18, 0.56], [0.18, 0.68], [0.06, 0.68]],
                    "color": c_cloud,
                    "note": "左肋腹向上漫延白云；d045 画面偏右下腹侧",
                },
            ],
            "color": c_cloud,
            "edge_color": c_base,
            "source_type": "observed",
            "confidence": 0.97,
            "crosses_uv_seam": True,
            "source_photos": [
                {"slot": "left_flank", "file": "miemie_ref_02_left_flank_white_patch.jpg"},
                {"slot": "front_sofa", "file": "miemie_ref_03_front_sofa_bell.jpg"},
            ],
            "user_confirmed": True,
        },
        {
            "id": "mark_03_belly_orange_transition",
            "name": "左腹缘暖杏橘过渡",
            "semantic_part": "torso_L_belly_edge",
            "anatomical_side": "_L",
            "space": "uv",
            "components": [
                {
                    "id": "mark_03_apricot_L",
                    "side": "_L",
                    "x_sign": "<0",
                    "uv_region": "B1_torso_L",
                    "polygon": [[0.14, 0.54], [0.22, 0.54], [0.22, 0.62], [0.14, 0.62]],
                    "color": c_apr,
                }
            ],
            "color": c_apr,
            "edge_color": c_base,
            "source_type": "observed",
            "confidence": 0.94,
            "crosses_uv_seam": False,
            "source_photos": [
                {"slot": "orange_belly", "file": "miemie_ref_08_left_side_orange_belly.jpg"},
            ],
            "user_confirmed": True,
        },
        {
            "id": "mark_04_asymmetric_white_socks",
            "name": "前高后低四白袜（右前腕内侧小焦糖）",
            "semantic_part": "leg_FL/FR/BL/BR",
            "anatomical_side": "asymmetric_LR",
            "space": "uv",
            "components": [
                {"id": "sock_FL", "side": "_L", "uv_region": "C1_leg_FL", "height": "over_wrist", "polygon": [[0.06, 0.28], [0.18, 0.28], [0.18, 0.40], [0.06, 0.40]], "color": c_white},
                {"id": "sock_FR", "side": "_R", "uv_region": "C2_leg_FR", "height": "over_wrist", "polygon": [[0.32, 0.28], [0.44, 0.28], [0.44, 0.40], [0.32, 0.40]], "color": c_white, "inner_caramel_hint": c_car},
                {"id": "sock_BL", "side": "_L", "uv_region": "C3_leg_BL", "height": "ankle_short", "polygon": [[0.56, 0.28], [0.68, 0.28], [0.68, 0.36], [0.56, 0.36]], "color": c_white},
                {"id": "sock_BR", "side": "_R", "uv_region": "C4_leg_BR", "height": "ankle_short", "polygon": [[0.82, 0.28], [0.94, 0.28], [0.94, 0.36], [0.82, 0.36]], "color": c_white},
            ],
            "color": c_white,
            "edge_color": c_base,
            "source_type": "observed",
            "confidence": 0.96,
            "crosses_uv_seam": False,
            "source_photos": [
                {"slot": "front45", "file": "miemie_ref_01_front45_loaf.jpg"},
                {"slot": "belly_legs", "file": "miemie_ref_06_belly_and_leg_spots.jpg"},
            ],
            "user_confirmed": True,
        },
        {
            "id": "mark_05_tabby_and_ringed_tail",
            "name": "背部鲭鱼虎斑与环纹黑尾尖",
            "semantic_part": "torso_back+tail",
            "anatomical_side": "C",
            "space": "uv",
            "components": [
                {"id": "mark_05_back_stripes", "side": "C", "uv_region": "B3_torso_back", "polygon": [[0.56, 0.56], [0.70, 0.56], [0.70, 0.70], [0.56, 0.70]], "color": c_stripe},
                {"id": "mark_05_tail_rings", "side": "C", "uv_region": "D1_tail", "polygon": [[0.06, 0.06], [0.20, 0.06], [0.20, 0.20], [0.06, 0.20]], "color": c_stripe},
            ],
            "color": c_stripe,
            "edge_color": c_base,
            "source_type": "observed",
            "confidence": 0.95,
            "crosses_uv_seam": False,
            "source_photos": [
                {"slot": "top_stripes", "file": "miemie_ref_05_top_front_back_stripes.jpg"},
            ],
            "user_confirmed": True,
        },
    ]
    return {
        "uv_version": uv_version,
        "identity_version": 1,
        "cat_id": "miemie",
        "anatomical_lr_convention": {
            "left_suffix": "_L",
            "left_x": "<0",
            "right_suffix": "_R",
            "right_x": ">0",
            "note": "永远以猫自身解剖学左右为准，不以屏幕左右为准。焦糖花生斑在 _R/X>0（正面看在画面左侧）；左肋白云在 _L/X<0。",
        },
        "markers": markers,
        "lab_color_sources": {k: v for k, v in colors.items()},
        "frozen_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "frozen_by": "m2_1_manual",
    }


def build_genome(colors: dict, uv_version: int, mesh_version: int, rig_version: int) -> dict:
    eye = colors["eye_emerald"]
    nose = colors["nose_brick"]
    return {
        "schema_version": 1,
        "cat_id": "miemie",
        "display_name": "咩咩",
        "identity_version": 1,
        "master": {
            "mesh": "master_cat",
            "mesh_version": mesh_version,
            "uv_version": uv_version,
            "rig_version": rig_version,
            "uv_hash": "sha256:bbbc4394d847af26ea16f9416ed3c23c996a68afcb0fbd7962c20ddcef15c27f",
        },
        "identity_shape": {
            "id_body_fat": 0.42,
            "id_belly": 0.38,
            "id_leg_len": 0.45,
            "id_neck_len": 0.48,
            "id_face_round": 0.62,
            "id_muzzle_len": 0.46,
            "id_ear_size": 0.52,
            "id_ear_fold": 0.0,
            "tail_len": 0.95,
            "tail_bob": 0.0,
        },
        "style_shape": {
            "sty_head_enlarge": 0.0,
            "sty_leg_shorten": 0.0,
            "sty_eye_enlarge": 0.0,
            "sty_face_chibi_cheek": 0.0,
            "sty_paw_round": 0.0,
            "note": "M1 原生微 Q Basis 已含 40%~43% 头高；M2.1 冻结时 sty_* 全 0，不二次放大头。",
        },
        "coat": {
            "pattern": "tabby_mackerel",
            "fur_length": "short",
            "colors": {
                "base": colors["base_tabby"]["srgb"],
                "secondary": colors["stripe_dark"]["srgb"],
                "tertiary": colors["apricot_belly_edge"]["srgb"],
                "white": colors["white_cream"]["srgb"],
                "caramel_peanut": colors["caramel_peanut_R"]["srgb"],
            },
            "colors_lab": {
                "base": colors["base_tabby"]["lab"],
                "secondary": colors["stripe_dark"]["lab"],
                "tertiary": colors["apricot_belly_edge"]["lab"],
                "white": colors["white_cream"]["lab"],
                "caramel_peanut": colors["caramel_peanut_R"]["lab"],
            },
            "white_regions": {
                "chin": 1.0,
                "chest": 0.85,
                "paw_FL": 1.0,
                "paw_FR": 1.0,
                "paw_BL": 0.45,
                "paw_BR": 0.45,
            },
            "pattern_params": {"density": 0.55, "contrast": 0.68, "seed": 45045},
        },
        "eyes": {
            "left": {"srgb": eye["srgb"], "lab": eye["lab"], "source": "photo_lab_midtone"},
            "right": {"srgb": eye["srgb"], "lab": eye["lab"], "source": "photo_lab_midtone"},
            "render_lock_emerald_layers": {
                "outer": "#2B7A3D",
                "inner_bright": "#68C864",
                "pupil": "#121C16",
                "eyelid": "#1B100A",
                "catchlight": "#FCF8F0",
                "note": "独立眼材质四要素渲染锁色（与 M1/validate_master 参数一致）；genome.eyes.*.lab 保留生活照实测。",
            },
        },
        "nose": nose["srgb"],
        "nose_lab": nose["lab"],
        "pads": "#6B5555",
        "markers_ref": "markings.json",
        "texture": {
            "uv_version": uv_version,
            "size": 2048,
            "albedo": "fur_albedo.png",
            "coverage": "coverage.png",
        },
        "personality": {
            "clingy": 0.85,
            "brave": 0.35,
            "greedy": 0.55,
            "active": 0.45,
        },
        "approval": {
            "status": "pending_m2_1_producer_review",
            "approved_by": None,
            "approved_at": None,
        },
        "provenance": {
            "capture_version": 1,
            "extraction": "pipeline/texture/extract_genome.py",
            "method": "manual_freeze_markings + Lab midtone (drop 5% hi/lo) from reference/miemie_photos",
            "automatic_fields": [
                "coat.colors",
                "coat.colors_lab",
                "eyes.left",
                "eyes.right",
                "nose",
            ],
            "user_edited_fields": [],
            "lab_samples": colors,
            "extracted_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        },
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    uv_version = json.loads(UV_MANIFEST.read_text())["uv_version"]
    master = json.loads(MASTER_SPEC.read_text())
    colors = extract_colors()
    markings = build_markings(colors, uv_version)
    genome = build_genome(
        colors,
        uv_version=uv_version,
        mesh_version=master.get("master_mesh_version", 1),
        rig_version=master.get("rig_version", 1),
    )
    assert genome["master"]["uv_version"] == markings["uv_version"]
    (OUT / "markings.json").write_text(json.dumps(markings, indent=2, ensure_ascii=False) + "\n")
    (OUT / "genome.json").write_text(json.dumps(genome, indent=2, ensure_ascii=False) + "\n")
    report = {
        "ok": True,
        "out_dir": str(OUT),
        "marker_count": len(markings["markers"]),
        "colors": {k: {"srgb": v["srgb"], "lab": v["lab"], "n": v["sample_count"]} for k, v in colors.items()},
        "uv_hash_locked": genome["master"]["uv_hash"],
    }
    (OUT / "extract_genome_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
