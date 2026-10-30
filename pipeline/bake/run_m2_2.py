#!/usr/bin/env python3
"""
M2.2 orchestrator (local box only — no CloudAgent).

Steps:
  1) export_control_views.py   (Blender) — Depth/Normal/Mask
  2) generate_complementary_sdxl.py --run  — may BLOCK without CUDA
  3) fuse_8dir_albedo.py       (Blender if multi-view ready; else honest block)
  4) run_m2_2_review.py        (Blender) — dual-layer 8-dir boards
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VAL = ROOT / "docs" / "validation" / "m2_2_8dir"


def run(cmd: list[str], blender_py: bool = False) -> int:
    if blender_py:
        full = ["blender", "-b", "--python", cmd[0]]
    else:
        full = cmd
    print("+", " ".join(full), flush=True)
    p = subprocess.run(full, cwd=str(ROOT))
    return p.returncode


def main() -> int:
    VAL.mkdir(parents=True, exist_ok=True)
    summary = {"stage": "M2.2", "steps": {}}

    rc = run([str(ROOT / "pipeline/texture/export_control_views.py")], blender_py=True)
    summary["steps"]["export_control_views"] = {"rc": rc}
    if rc != 0:
        (VAL / "m2_2_orchestrator_report.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )
        return rc

    rc = run(
        [sys.executable, str(ROOT / "pipeline/texture/generate_complementary_sdxl.py"), "--run"]
    )
    summary["steps"]["generate_complementary_sdxl"] = {"rc": rc, "blocked": rc == 2}

    # Fuse: Blender only needed when multi-view ready; script self-detects and may exit 2 without opening blend
    # Always try via system python first for blocked path; if it needs bpy it re-invokes? Our fuse uses bpy always at top.
    # So for blocked path we need a non-bpy early exit — fuse already returns 2 before bpy when only d045.
    # But fuse imports bpy at module level. Run under blender always.
    rc_fuse = run([str(ROOT / "pipeline/texture/fuse_8dir_albedo.py")], blender_py=True)
    summary["steps"]["fuse_8dir_albedo"] = {"rc": rc_fuse}

    rc_rev = run([str(ROOT / "pipeline/bake/run_m2_2_review.py")], blender_py=True)
    summary["steps"]["run_m2_2_review"] = {"rc": rc_rev}

    summary["ok"] = False  # M2.2 not complete until GPU generation + gates + coverage
    summary["note"] = (
        "See generated/m2_2_generation_BLOCKED.json and PRODUCER_SUMMARY_ZH.md. "
        "Pipeline is reproducible; commercial licenses declared; no procedural default fur."
    )
    (VAL / "m2_2_orchestrator_report.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    # Exit 0 if pipeline ran to completion with honest blockers recorded
    return 0 if rc_rev == 0 else rc_rev


if __name__ == "__main__":
    raise SystemExit(main())
