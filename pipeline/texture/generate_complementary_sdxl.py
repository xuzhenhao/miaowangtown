#!/usr/bin/env python3
"""
M2.2 — Generate complementary-view unlit fur albedo via locked commercial stack.

Locked Hugging Face repos + model-card licenses (from DEVELOPMENT_PLAN v1.3):
  - stabilityai/stable-diffusion-xl-base-1.0     CreativeML OpenRAIL++-M
  - diffusers/controlnet-depth-sdxl-1.0         CreativeML OpenRAIL++-M
  - xinsir/controlnet-union-sdxl-1.0            Apache-2.0 (Depth/Normal)
  - h94/IP-Adapter  ip-adapter-plus_sdxl_vit-h.bin  Apache-2.0

FORBIDDEN: FLUX.1-dev family; any non-commercial weight; procedural fur as default fill.

This script refuses to invent fur when neither CUDA nor Apple MPS GPU is available, or weights are missing.
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


def _load_dotenv_file(path: Path) -> None:
    """Minimal KEY=VALUE loader. Does not override already-set env vars."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def _bootstrap_m22_env() -> Path:
    """Load .env.m22 then resolve repo root. HF_HOME must land before hub imports."""
    here = Path(__file__).resolve()
    script_root = here.parents[2]  # pipeline/texture/ -> repo root
    candidates = []
    if os.environ.get("MIAOWANGTOWN_ROOT"):
        candidates.append(Path(os.environ["MIAOWANGTOWN_ROOT"]).expanduser())
    candidates.append(script_root)
    candidates.append(Path.cwd())
    env_file = None
    for c in candidates:
        p = (c / ".env.m22").resolve()
        if p.is_file():
            env_file = p
            break
    if env_file is not None:
        _load_dotenv_file(env_file)
    root = Path(
        os.environ.get("MIAOWANGTOWN_ROOT", str(script_root))
    ).expanduser().resolve()
    # Prefer repo-local .env.m22 once root is known (in case cwd differed).
    _load_dotenv_file(root / ".env.m22")
    return root


ROOT = _bootstrap_m22_env()
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

# Canonical local snapshot root (curl download_m22.sh). HF_HOME is incidental only.
DEFAULT_M22_MODELS = Path("/Users/cloud/dev/models/m22")


def models_root() -> Path:
    raw = os.environ.get("M22_MODELS_ROOT", "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_M22_MODELS


def local_model(name: str) -> Path:
    return models_root() / name


REQUIRED_LOCAL_WEIGHTS = [
    "controlnet-depth-sdxl-1.0/diffusion_pytorch_model.fp16.safetensors",
    "controlnet-depth-sdxl-1.0/config.json",
    "stable-diffusion-xl-base-1.0/model_index.json",
    "stable-diffusion-xl-base-1.0/unet/diffusion_pytorch_model.fp16.safetensors",
    "stable-diffusion-xl-base-1.0/unet/config.json",
    "stable-diffusion-xl-base-1.0/text_encoder/model.fp16.safetensors",
    "stable-diffusion-xl-base-1.0/text_encoder/config.json",
    "stable-diffusion-xl-base-1.0/text_encoder_2/model.fp16.safetensors",
    "stable-diffusion-xl-base-1.0/text_encoder_2/config.json",
    "stable-diffusion-xl-base-1.0/vae/diffusion_pytorch_model.fp16.safetensors",
    "stable-diffusion-xl-base-1.0/vae/config.json",
    "stable-diffusion-xl-base-1.0/scheduler/scheduler_config.json",
]

# text_encoder_2 fp16 expected size (bytes); incomplete downloads must not pass.
TE2_FP16_MIN_BYTES = 1_300_000_000
IP_ADAPTER_REL = "IP-Adapter/sdxl_models/ip-adapter-plus_sdxl_vit-h.bin"


def missing_local_weights() -> list[str]:
    root = models_root()
    missing: list[str] = []
    for rel in REQUIRED_LOCAL_WEIGHTS:
        p = root / rel
        if not p.is_file():
            missing.append(rel)
            continue
        if rel.endswith("text_encoder_2/model.fp16.safetensors") and p.stat().st_size < TE2_FP16_MIN_BYTES:
            missing.append(f"{rel} (incomplete size={p.stat().st_size})")
    return missing


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
    # Identity + five markings FIRST (CLIP ~77 token budget; keep head dense).
    "single intact calico tabby cat, asymmetric yin-yang muzzle mark_01 "
    "(anatomical RIGHT warm caramel peanut patch, LEFT cream cheek), "
    "mark_02 white chest bib into left-rib cloud, mark_03 warm apricot belly edge, "
    "mark_04 asymmetric white socks (front high / rear ankle) with rear tabby pants, "
    "mark_05 forehead M + mackerel back stripes + ringed tabby tail black tip, "
    "emerald almond eyes, brick-pink nose, white paws zero grey fringe, "
    # Style / lighting AFTER identity (may truncate).
    "orthographic unlit fur albedo, soft fur clumps, flat ambient, no cast shadows, "
    "high-frequency fur grain matching reference"
)
NEGATIVE = (
    "harsh sunlight, rim light, studio lighting, glossy specular, "
    "plastic skin, ellipse blobs, flat vector shapes, text, watermark, "
    "deformed anatomy, extra legs, mirrored markings"
)

# Per-view knobs for targeted FAIL reruns. Views absent keep defaults.
VIEW_TUNING = {
    # prompt_extra = view-only deltas; identity/five-marks live in base PROMPT head.
    "d000": {
        "prompt_extra": (
            ", front three-quarter face readable, do NOT flatten muzzle into blank white mask"
        ),
        "negative_extra": (
            ", symmetric white face mask, blank muzzle, missing facial markings, "
            "overexposed white face"
        ),
        "control_scale": [1.05, 0.8],
        "ip_scale": 0.78,
        "guidance": 5.5,
    },
    "d090": {
        "prompt_extra": (
            ", silhouette strictly matches depth map, no floating shards or ghost limbs"
        ),
        "negative_extra": (
            ", texture atlas, UV unwrap, duplicated body parts, floating fur patches, "
            "smeared edges outside silhouette, glitch fragments"
        ),
        "control_scale": [1.15, 0.95],
        "ip_scale": 0.6,
        "guidance": 5.0,
    },
    "d225": {
        "prompt_extra": (
            ", body aligned to depth/part mask, continuous silhouette, no disconnected shards"
        ),
        "negative_extra": (
            ", exploded parts, floating fragments, severed limbs, atlas layout, "
            "depth leak, duplicated tails"
        ),
        "control_scale": [1.2, 1.0],
        "ip_scale": 0.58,
        "guidance": 5.0,
    },
    "d315": {
        "prompt_extra": (
            ", intact pointed ears, ringed tabby tail length matches reference, clean silhouette"
        ),
        "negative_extra": (
            ", stretched ear polygons, elongated spike from head, stubby broken tail, "
            "mesh artifacts, shearing"
        ),
        "control_scale": [1.1, 0.9],
        "ip_scale": 0.62,
        "guidance": 5.2,
    },
}

DEFAULT_CONTROL_SCALE = [0.85, 0.65]
DEFAULT_IP_SCALE = 0.65
DEFAULT_GUIDANCE = 5.0



def mask_bg_by_depth(rgb_img, depth_img, dilate_px: int = 3):
    """Clear ghost pixels outside depth silhouette; fill with neutral grey.
    Does NOT invent fur inside the cat body.
    """
    import numpy as np
    from PIL import Image, ImageFilter

    rgb = np.array(rgb_img.convert("RGB"))
    depth = depth_img.convert("L").resize(rgb_img.size, Image.Resampling.LANCZOS)
    darr = np.array(depth)
    # Near-black = background on our depth maps
    mask = (darr > 12).astype(np.uint8) * 255
    mask_img = Image.fromarray(mask, mode="L")
    if dilate_px > 0:
        # MaxFilter size must be odd
        k = dilate_px * 2 + 1
        mask_img = mask_img.filter(ImageFilter.MaxFilter(size=k))
    m = np.array(mask_img) > 127
    out = rgb.copy()
    out[~m] = (128, 128, 128)
    return Image.fromarray(out, mode="RGB"), True


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
        "hf_home": os.environ.get("HF_HOME"),
        "miaowangtown_root": str(ROOT),
        "env_m22_loaded": (ROOT / ".env.m22").is_file(),
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

    info["mps_available"] = False
    info["m22_models_root"] = str(models_root())
    info["m22_missing_weights"] = missing_local_weights()
    info["m22_ip_adapter_present"] = (models_root() / IP_ADAPTER_REL).is_file()
    info["compute_device"] = None
    try:
        import torch

        info["torch_installed"] = True
        info["torch_version"] = torch.__version__
        info["cuda_available"] = bool(torch.cuda.is_available())
        info["mps_available"] = bool(
            getattr(torch.backends, "mps", None) is not None
            and torch.backends.mps.is_available()
        )
        if info["cuda_available"]:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["compute_device"] = "cuda"
        elif info["mps_available"]:
            info["gpu_name"] = "Apple MPS"
            info["compute_device"] = "mps"
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
            "Provision a CUDA GPU (>=12GB VRAM) or Apple Silicon Mac with MPS (16GB+ unified memory preferred).",
            "Copy .env.m22.example to .env.m22; set M22_MODELS_ROOT=/Users/cloud/dev/models/m22, HF_HOME=$M22_MODELS_ROOT/hf_home, MIAOWANGTOWN_ROOT.",
            "pip install torch (CUDA or Mac MPS), diffusers, transformers, accelerate, safetensors, opencv-python, Pillow.",
            "Finish download_m22.sh under M22_MODELS_ROOT (not ~/.cache/huggingface; obsolete /Users/cloud/dev/models/huggingface).",
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


def try_generate(env: dict, selected_views: list[str], seed_offset: int = 0, merge_report: bool = False) -> int:
    """Real generation path — only when CUDA or MPS + deps present."""
    import torch
    from diffusers import (
        ControlNetModel,
        ControlNetUnionModel,
        StableDiffusionXLControlNetPipeline,
        StableDiffusionXLControlNetUnionPipeline,
    )
    from PIL import Image
    import numpy as np

    OUT_ALB.mkdir(parents=True, exist_ok=True)
    VAL.mkdir(parents=True, exist_ok=True)

    device = env.get("compute_device") or ("cuda" if env.get("cuda_available") else "mps")
    # MPS float16 is supported on modern Apple Silicon; fall back to float32 if needed.
    dtype = torch.float16 if device in ("cuda", "mps") else torch.float32
    miss = missing_local_weights()
    if miss:
        raise FileNotFoundError(
            "M22 local weights incomplete under "
            + str(models_root())
            + ": "
            + ", ".join(miss)
        )

    depth_local = local_model("controlnet-depth-sdxl-1.0")
    sdxl_local = local_model("stable-diffusion-xl-base-1.0")
    ip_local = local_model("IP-Adapter")
    union_local = local_model("controlnet-union-sdxl-1.0")
    # xinsir ControlNetPlus modes: 0 openpose, 1 depth, 4 normal
    UNION_MODE_DEPTH = 1
    UNION_MODE_NORMAL = 4

    use_union = False
    union_error = None
    if (union_local / "config.json").is_file() and (
        union_local / "diffusion_pytorch_model.safetensors"
    ).is_file():
        try:
            union = ControlNetUnionModel.from_pretrained(
                str(union_local), torch_dtype=dtype, local_files_only=True
            )
            pipe = StableDiffusionXLControlNetUnionPipeline.from_pretrained(
                str(sdxl_local),
                controlnet=union,
                torch_dtype=dtype,
                variant="fp16",
                use_safetensors=True,
                local_files_only=True,
            ).to(device)
            use_union = True
        except Exception as exc:  # noqa: BLE001
            union_error = f"{type(exc).__name__}: {exc}"
            print("ERROR: ControlNetUnion load/pipeline failed:", union_error)
            raise RuntimeError(
                "Locked stack requires xinsir ControlNetUnion; refusing silent depth-only degrade. "
                + union_error
            ) from exc
    else:
        raise FileNotFoundError(
            "Locked ControlNetUnion missing under "
            + str(union_local)
            + " (need config.json + diffusion_pytorch_model.safetensors)"
        )

    # Do NOT force VAE to float32 on MPS — mixing Half latents with float VAE bias crashes decode.
    # Prefer enable_vae_slicing for memory instead.
    if device == "mps":
        try:
            pipe.enable_vae_slicing()
        except Exception as exc:
            print("enable_vae_slicing skipped:", exc)

    # IP-Adapter (image encoder lives under models/image_encoder)
    try:
        ip_weight = ip_local / "sdxl_models" / "ip-adapter-plus_sdxl_vit-h.bin"
        ip_enc = ip_local / "models" / "image_encoder"
        if not ip_weight.is_file():
            raise FileNotFoundError(str(ip_weight))
        if not (ip_enc / "config.json").is_file():
            raise FileNotFoundError(str(ip_enc))
        pipe.load_ip_adapter(
            str(ip_local),
            subfolder="sdxl_models",
            weight_name="ip-adapter-plus_sdxl_vit-h.bin",
            image_encoder_folder="models/image_encoder",
            local_files_only=True,
        )
        pipe.set_ip_adapter_scale(DEFAULT_IP_SCALE)
        ip_ok = True
    except Exception as exc:  # noqa: BLE001
        print("IP-Adapter load failed:", exc)
        ip_ok = False

    # Attention slicing conflicts with IP-Adapter attn processors on MPS (tuple encoder_hidden_states).
    if device == "mps" and not ip_ok:
        try:
            pipe.enable_attention_slicing()
        except Exception as exc:
            print("enable_attention_slicing skipped:", exc)
    elif device == "mps" and ip_ok:
        print("MPS: skip attention slicing because IP-Adapter is active")

    anchor = Image.open(ANCHOR).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
    report_path = VAL / "m2_2_generation_report.json"
    prior_views = {}
    if merge_report and report_path.is_file():
        try:
            prior = json.loads(report_path.read_text())
            prior_views = dict(prior.get("views") or {})
        except Exception as exc:  # noqa: BLE001
            print("merge-report: could not load prior views:", exc)

    results = {
        "ok": True,
        "device": device,
        "dtype": str(dtype),
        "use_union": use_union,
        "union_modes": {"depth": UNION_MODE_DEPTH, "normal": UNION_MODE_NORMAL},
        "union_error": union_error,
        "ip_adapter": ip_ok,
        "m22_models_root": str(models_root()),
        "views": dict(prior_views) if merge_report else {},
        "root": str(ROOT),
        "seed_offset": seed_offset,
        "selected_views": list(selected_views),
        "rerun_of_fails": bool(seed_offset or set(selected_views) != set(COMPLEMENTARY)),
        "view_tuning_applied": {},
        "merge_report": bool(merge_report),
    }

    for dname in selected_views:
        tuning = VIEW_TUNING.get(dname, {})
        prompt_extra = tuning.get("prompt_extra", "")
        negative_extra = tuning.get("negative_extra", "")
        control_scale = list(tuning.get("control_scale", DEFAULT_CONTROL_SCALE))
        ip_scale = float(tuning.get("ip_scale", DEFAULT_IP_SCALE))
        guidance = float(tuning.get("guidance", DEFAULT_GUIDANCE))
        results["view_tuning_applied"][dname] = {
            "prompt_extra": prompt_extra,
            "negative_extra": negative_extra,
            "control_scale": control_scale,
            "ip_scale": ip_scale,
            "guidance": guidance,
        }

        depth_path = CTRL / dname / "depth_768.png"
        if not depth_path.is_file():
            depth_path = CTRL / dname / "depth.png"
        depth = Image.open(depth_path).convert("RGB").resize(
            (1024, 1024), Image.Resampling.LANCZOS
        )
        normal = Image.open(CTRL / dname / "normal_768.png").convert("RGB").resize(
            (1024, 1024), Image.Resampling.LANCZOS
        )
        gen_device = "cpu" if device == "mps" else device
        view_seed = SEED + seed_offset + (hash(dname) % 1000)
        generator = torch.Generator(device=gen_device).manual_seed(view_seed)
        kwargs = dict(
            prompt=PROMPT + f", view {dname}" + prompt_extra,
            negative_prompt=NEGATIVE + negative_extra,
            num_inference_steps=30,
            guidance_scale=guidance,
            generator=generator,
            width=1024,
            height=1024,
        )
        if ip_ok:
            pipe.set_ip_adapter_scale(ip_scale)
            kwargs["ip_adapter_image"] = anchor
        # Locked stack: ControlNetUnion depth(1)+normal(4); no silent depth-only path.
        kwargs["control_image"] = [depth, normal]
        kwargs["control_mode"] = [UNION_MODE_DEPTH, UNION_MODE_NORMAL]
        kwargs["controlnet_conditioning_scale"] = control_scale

        out = pipe(**kwargs).images[0]
        # Optional: clear ghost pixels outside depth silhouette (no fur invent inside).
        out, bg_masked = mask_bg_by_depth(out, depth, dilate_px=3)
        out_path = OUT_ALB / f"{dname}_unlit_albedo.png"
        out.save(out_path)
        out.resize((768, 768), Image.Resampling.LANCZOS).save(
            VAL / f"{dname}_unlit_albedo_768.png"
        )
        normal.save(VAL / f"{dname}_control_normal_used.png")
        results["views"][dname] = {
            "path": str(out_path.relative_to(ROOT)),
            "seed": view_seed,
            "seed_offset": seed_offset,
            "gate_status": "pending_4x_fur_flow_and_markings",
            "control_scale": control_scale,
            "ip_scale": ip_scale,
            "guidance": guidance,
            "bg_masked_by_depth": bool(bg_masked),
            "rerun": True,
        }
        print("generated", dname, out_path, "seed=", view_seed)

    report_path.write_text(
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
    ap.add_argument(
        "--views",
        type=str,
        default="",
        help="Comma-separated views to generate (default: all COMPLEMENTARY)",
    )
    ap.add_argument(
        "--seed-offset",
        type=int,
        default=0,
        help="Added to SEED + hash(view) for deterministic reruns (e.g. 10007)",
    )
    ap.add_argument(
        "--merge-report",
        action="store_true",
        help="Merge into existing m2_2_generation_report.json; keep non-rerun view entries",
    )
    args = ap.parse_args()
    env = detect_environment()

    if args.views.strip():
        selected_views = [v.strip() for v in args.views.split(",") if v.strip()]
        unknown = [v for v in selected_views if v not in COMPLEMENTARY]
        if unknown:
            print("ERROR: unknown views:", unknown, "allowed:", COMPLEMENTARY)
            return 2
    else:
        selected_views = list(COMPLEMENTARY)

    # Only require control maps for selected views
    missing_ctrl = [
        d
        for d in selected_views
        if not (
            env["control_maps_present"].get(d, {}).get("depth_768")
            and env["control_maps_present"].get(d, {}).get("normal_768")
        )
    ]
    if missing_ctrl:
        path = write_blocker(
            f"Control maps missing for {missing_ctrl}. Run export_control_views.py first.",
            env,
        )
        print("BLOCKED:", path)
        return 2

    if not env.get("compute_device"):
        path = write_blocker(
            "No CUDA or Apple MPS GPU available (nvidia-smi empty / torch.cuda and torch.backends.mps unavailable). "
            "SDXL + ControlNet + IP-Adapter cannot run. Refusing procedural substitute.",
            env,
        )
        print("BLOCKED:", path)
        print(json.dumps({"blocked": True, "reason": "no_cuda_or_mps", "report": str(path)}, indent=2))
        return 2

    if not env["torch_installed"] or not env["diffusers_installed"]:
        path = write_blocker(
            "GPU device detected but torch/diffusers not installed. Install deps then re-run --run.",
            env,
        )
        print("BLOCKED:", path)
        return 2

    if args.check_only:
        print(json.dumps({"ready": True, "env": env, "selected_views": selected_views}, indent=2))
        return 0

    if not args.run:
        print("Environment looks GPU-capable. Pass --run to generate.")
        print(json.dumps({"env": env, "selected_views": selected_views}, indent=2))
        return 0

    return try_generate(
        env,
        selected_views=selected_views,
        seed_offset=args.seed_offset,
        merge_report=args.merge_report,
    )


if __name__ == "__main__":
    raise SystemExit(main())
