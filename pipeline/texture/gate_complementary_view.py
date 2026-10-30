#!/usr/bin/env python3
"""
Per-view 4x fur-flow + five-marking gate BEFORE UV projection.

Usage (after SDXL generation on a GPU box):
  python3 pipeline/texture/gate_complementary_view.py --view d180 \
    --albedo cats/miemie/identity_v1/complementary_albedos/d180_unlit_albedo.png

Writes docs/validation/m2_2_8dir/gates/{view}_fur_flow_gate.json
Authority = human 4x eyeball; this script only records checklist + soft heuristics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
GATE_DIR = ROOT / "docs" / "validation" / "m2_2_8dir" / "gates"
VAL = ROOT / "docs" / "validation" / "m2_2_8dir"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", required=True)
    ap.add_argument("--albedo", required=True, type=Path)
    ap.add_argument("--human-pass", action="store_true", help="Producer marks 4x fur-flow OK")
    ap.add_argument("--human-fail", action="store_true")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    if not args.albedo.is_file():
        raise SystemExit(f"missing albedo {args.albedo}")

    im = Image.open(args.albedo).convert("RGBA")
    # 4x crop sheet for producer
    w, h = im.size
    crops = []
    boxes = [
        (w // 4, h // 8, w // 2, h // 3),
        (w // 3, h // 3, 2 * w // 3, 2 * h // 3),
        (w // 2, h // 2, 3 * w // 4, 7 * h // 8),
    ]
    sheet = Image.new("RGB", (900, 320), (22, 24, 30))
    dr = ImageDraw.Draw(sheet)
    for i, box in enumerate(boxes):
        c = im.crop(box).resize((280, 280), Image.Resampling.NEAREST)
        sheet.paste(c, (10 + i * 295, 30))
    dr.text((10, 6), f"{args.view} 4x fur-flow crops — producer authority", fill=(230, 230, 240))
    sheet.save(VAL / f"gates_preview_{args.view}_4x.png")

    passed = bool(args.human_pass) and not args.human_fail
    report = {
        "view": args.view,
        "albedo": str(args.albedo),
        "ok": passed,
        "pass": passed,
        "checklist": {
            "fur_flow_natural_4x": passed,
            "no_plastic_ellipse_blobs": passed,
            "five_markings_side_correct": passed,
            "white_socks_no_gray_fringe_soft": None,
            "producer_notes": args.notes,
        },
        "honesty": "Auto heuristics intentionally soft; 4x human eyeball is authority.",
        "blocked_reason_if_not_passed": None
        if passed
        else "Awaiting producer --human-pass after 4x review",
    }
    out = GATE_DIR / f"{args.view}_fur_flow_gate.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
