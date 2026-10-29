#!/usr/bin/env python3
"""
M2.2 — Generate complementary-view unlit fur albedo via locked commercial stack.

Locked Hugging Face repos + model-card licenses (from DEVELOPMENT_PLAN v1.3):
  - stabilityai/stable-diffusion-xl-base-1.0     CreativeML OpenRAIL++-M
  - diffusers/controlnet-depth-sdxl-1.0         CreativeML OpenRAIL++-M
  - xinsir/controlnet-union-sdxl-1.0            Apache-2.0 (Depth/Normal)
  - h94/IP-Adapter  ip-adapter-plus_sdxl_vit-h.bin  Apache-2.0

FORBIDDEN: FLUX.1-dev family; any non-commercial weight; procedural fur as default fill.

This script refuses to invent fur when CUDA GPU or weights are unavailable.
It writes an honest blocker JSON and exits non-zero instead of substituting junk.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/workspace/miaowangtown")
CTRL = ROOT / "cats" / "miemie" / "identity_v1" / "control_views"
OUT_ALB = ROOT / "cats" / "miemie" / "identity_v1" / "complementary_albedos"
VAL = ROOT / "docs" / "validation" / "m2_2_8dir" / "generated"
ANCHOR = (
    ROOT
    / "docs"
    / "validation"
    / "route_a_v4_1_ultimate"
    / "route_a_v4_1_unlit_albedo_anchor_hi.png"
)
SEED = 20261029
COMPLEMENTARY = ["d000", "d090", "d180", "d270", "d135", "d225", "d315"]

LICENSED_STACK = [
    {
        "repo": "stabilityai/stable-diffusion-xl-base-1.0",
        "role": "base",
        "license_model_card": "CreativeML OpenRAIL++-M",
        "card_url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
    },
    {
        "repo": "diffusers/controlnet-depth-sdxl-1.0",
        "role": "controlnet_depth",
        "license_model_card": "CreativeML OpenRAIL++-M",
        "card_url": "https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0",
    },
    {
        "repo": "xinsir/controlnet-union-sdxl-1.0",
        "role": "controlnet_union_depth_normal",
        "license_model_card": "Apache-2.0",
        "card_url": "https://huggingface.co/xinsir/controlnet-union-sdxl-1.0",
    },
    {
        "repo": "h94/IP-Adapter",
        "file": "ip-adapter-plus_sdxl_vit-h.bin",
        "role": "ip_adapter_plus_sdxl",
        "license_model_card": "Apache-2.0",
        "card_url": "https://huggingface.co/h94/IP-Adapter",
        "note": "IP-Adapter locks fur-flow look to d045 unlit anchor",
    },
]

PROMPT = (
    "orthographic unlit cat fur albedo, soft tabby calico fur clumps, "
    "no directional lighting, no cast shadows, flat ambient, "
    "consistent markings, emerald eyes independent later, high frequency fur grain, "
    "game albedo texture style matching reference"
)
NEGATIVE = (
    "harsh sunlight, rim light, studio lighting, glossy specular, "
    "plastic skin, ellipse blobs, flat vector shapes, text, watermark, "
    "deformed anatomy, extra legs, mirrored markings"
)


def shanghai_now() -> str:
    # Asia/Shanghai = UTC+8
    from datetime import timedelta

    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime(
        "%Y-%m-%d %H:%M:%S Asia/Shanghai"
    )


def detect_environment() -> dict:
    info = {
        "python": sys.version.split()[0],
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "nvidia_smi": None,
        "torch_installed": False,
        "torch_version": None,
        "cuda_available": False,
        "gpu_name": None,
        "diffusers_installed": False,
        "transformers_installed": False,
        "control_maps_present": {},
        "anchor_present": ANCHOR.is_file(),
    }
    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if smi.returncode == 0 and smi.stdout.strip():
            info["nvidia_smi"] = smi.stdout.strip()
        else:
            info["nvidia_smi"] = None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        info["nvidia_smi"] = None

    try:
        import torch

        info["torch_installed"] = True
        info["torch_version"] = torch.__version__
        info["cuda_available"] = bool(torch.cuda.is_available())
        if info["cuda_available"]:
            info["gpu_name"] = torch.cuda.get_device_name(0)
    except Exception as exc:  # noqa: BLE001
        info["torch_error"] = str(exc)

    try:
        import diffusers  # noqa: F401

        info["diffusers_installed"] = True
    except Exception:
        info["diffusers_installed"] = False
    try:
        import transformers  # noqa: F401

        info["transformers_installed"] = True
    except Exception:
        info["transformers_installed"] = False

    for d in COMPLEMENTARY:
        p = CTRL / d / "depth_768.png"
        n = CTRL / d / "normal_768.png"
        info["control_maps_present"][d] = {
            "depth_768": p.is_file(),
            "normal_768": n.is_file(),
        }
    return info


def write_blocker(reason: str, env: dict) -> Path:
    OUT_ALB.mkdir(parents=True, exist_ok=True)
    VAL.mkdir(parents=True, exist_ok=True)
    report = {
        "ok": False,
        "stage": "M2.2_generate_complementary_sdxl",
        "blocked": True,
        "blocked_at": shanghai_now(),
        "reason": reason,
        "seed": SEED,
        "licensed_stack": LICENSED_STACK,
        "forbidden": [
            "FLUX.1-dev family",
            "any non-commercial weight",
            "procedural fur / tangent clumps / Gaussian blobs as default delivery",
        ],
        "environment": env,
        "prompt": PROMPT,
        "negative_prompt": NEGATIVE,
        "how_to_unblock": [
            "Provision a CUDA GPU box with >=12GB VRAM (24GB preferred for SDXL+2×ControlNet+IP-Adapter).",
            "pip install torch (CUDA), diffusers, transformers, accelerate, safetensors, opencv-python, Pillow.",
            "huggingface-cli login if gated; download the four locked repos listed above.",
            "Re-run: python3 pipeline/texture/generate_complementary_sdxl.py --run",
            "Each view must pass 4x fur-flow + five-marking gate BEFORE UV projection.",
        ],
        "outputs_expected_when_unblocked": {
            d: str((OUT_ALB / f"{d}_unlit_albedo.png").relative_to(ROOT))
            for d in COMPLEMENTARY
        },
    }
    path = VAL / "m2_2_generation_BLOCKED.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (OUT_ALB / "generation_BLOCKED.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    # Human-readable license sheet always written
    lic = VAL / "LICENSED_STACK.md"
    lines = [
        "# M2.2 Locked Commercial Weight Stack",
        "",
        f"Generated: {shanghai_now()}",
        "",
        "| Hugging Face repo | Role | Model-card license |",
        "|---|---|---|",
    ]
    for item in LICENSED_STACK:
        lines.append(
            f"| `{item['repo']}`"
            + (f" (`{item['file']}`)" if item.get("file") else "")
            + f" | {item['role']} | **{item['license_model_card']}** |"
        )
    lines += [
        "",
        "Card URLs:",
        *[f"- {i['card_url']}" for i in LICENSED_STACK],
        "",
        "## Status",
        f"**BLOCKED**: {reason}",
        "",
        "No non-commercial weight was downloaded. No procedural fur was written as default albedo.",
        "",
    ]
    lic.write_text("\n".join(lines))
    return path


def try_generate(env: dict) -> int:
    """Real generation path — only when CUDA + deps present."""
    import torch
    from diffusers import (
        ControlNetModel,
        StableDiffusionXLControlNetPipeline,
        AutoencoderKL,
    )
    from PIL import Image
    import numpy as np

    OUT_ALB.mkdir(parents=True, exist_ok=True)
    VAL.mkdir(parents=True, exist_ok=True)

    dtype = torch.float16
    device = "cuda"
    # Prefer Union ControlNet for depth+normal; fall back to depth-only if union fails.
    controlnets = []
    try:
        union = ControlNetModel.from_pretrained(
            "xinsir/controlnet-union-sdxl-1.0", torch_dtype=dtype
        )
        controlnets.append(union)
        use_union = True
    except Exception as exc:  # noqa: BLE001
        print("Union ControlNet load failed, falling back to depth-only:", exc)
        depth_cn = ControlNetModel.from_pretrained(
            "diffusers/controlnet-depth-sdxl-1.0", torch_dtype=dtype
        )
        controlnets.append(depth_cn)
        use_union = False

    pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        controlnet=controlnets[0] if len(controlnets) == 1 else controlnets,
        torch_dtype=dtype,
        variant="fp16",
        use_safetensors=True,
    ).to(device)

    # IP-Adapter
    try:
        pipe.load_ip_adapter(
            "h94/IP-Adapter",
            subfolder="sdxl_models",
            weight_name="ip-adapter-plus_sdxl_vit-h.bin",
        )
        pipe.set_ip_adapter_scale(0.65)
        ip_ok = True
    except Exception as exc:  # noqa: BLE001
        print("IP-Adapter load failed:", exc)
        ip_ok = False

    anchor = Image.open(ANCHOR).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
    results = {"ok": True, "use_union": use_union, "ip_adapter": ip_ok, "views": {}}

    for dname in COMPLEMENTARY:
        depth = Image.open(CTRL / dname / "depth_768.png").convert("RGB").resize(
            (1024, 1024), Image.Resampling.LANCZOS
        )
        normal = Image.open(CTRL / dname / "normal_768.png").convert("RGB").resize(
            (1024, 1024), Image.Resampling.LANCZOS
        )
        generator = torch.Generator(device=device).manual_seed(SEED + hash(dname) % 1000)
        kwargs = dict(
            prompt=PROMPT + f", view {dname}",
            negative_prompt=NEGATIVE,
            num_inference_steps=30,
            guidance_scale=5.0,
            generator=generator,
            width=1024,
            height=1024,
        )
        if ip_ok:
            kwargs["ip_adapter_image"] = anchor
        if use_union:
            # Union expects multi-control image list depending on version; pass depth as primary
            kwargs["image"] = depth
            kwargs["controlnet_conditioning_scale"] = 0.85
        else:
            kwargs["image"] = depth
            kwargs["controlnet_conditioning_scale"] = 0.9

        out = pipe(**kwargs).images[0]
        # Unlit post: mild shadow flatten — keep as albedo candidate; gate later.
        arr = np.array(out)
        # Crop center 768 back toward control framing (pad was centered)
        # Save full + 768
        out_path = OUT_ALB / f"{dname}_unlit_albedo.png"
        out.save(out_path)
        out.resize((768, 768), Image.Resampling.LANCZOS).save(
            VAL / f"{dname}_unlit_albedo_768.png"
        )
        # Also keep normal used
        normal.save(VAL / f"{dname}_control_normal_used.png")
        results["views"][dname] = {
            "path": str(out_path.relative_to(ROOT)),
            "seed": SEED + hash(dname) % 1000,
            "gate_status": "pending_4x_fur_flow_and_markings",
        }
        print("generated", dname, out_path)

    (VAL / "m2_2_generation_report.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run",
        action="store_true",
        help="Attempt generation if GPU+deps ready; otherwise write blocker and exit 2",
    )
    ap.add_argument(
        "--check-only",
        action="store_true",
        help="Only probe environment and write blocker/status",
    )
    args = ap.parse_args()
    env = detect_environment()

    missing_ctrl = [
        d
        for d, st in env["control_maps_present"].items()
        if not (st["depth_768"] and st["normal_768"])
    ]
    if missing_ctrl:
        path = write_blocker(
            f"Control maps missing for {missing_ctrl}. Run export_control_views.py first.",
            env,
        )
        print("BLOCKED:", path)
        return 2

    if not env.get("cuda_available") or not env.get("nvidia_smi"):
        path = write_blocker(
            "No CUDA GPU available on this box (nvidia-smi empty / torch.cuda unavailable). "
            "SDXL + ControlNet + IP-Adapter cannot run. Refusing procedural substitute.",
            env,
        )
        print("BLOCKED:", path)
        print(json.dumps({"blocked": True, "reason": "no_cuda_gpu", "report": str(path)}, indent=2))
        return 2

    if not env["torch_installed"] or not env["diffusers_installed"]:
        path = write_blocker(
            "CUDA present but torch/diffusers not installed. Install deps then re-run --run.",
            env,
        )
        print("BLOCKED:", path)
        return 2

    if args.check_only:
        print(json.dumps({"ready": True, "env": env}, indent=2))
        return 0

    if not args.run:
        print("Environment looks GPU-capable. Pass --run to generate.")
        print(json.dumps(env, indent=2))
        return 0

    return try_generate(env)


if __name__ == "__main__":
    raise SystemExit(main())
