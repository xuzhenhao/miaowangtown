#!/usr/bin/env bash
# Download M2.2 locked commercial weights into M22_MODELS_ROOT (local snapshots).
# Do NOT use ~/.cache/huggingface as the primary tree.
# Licenses: see docs/validation/m2_2_8dir/generated/LICENSED_STACK.md
set -euo pipefail

ROOT="${M22_MODELS_ROOT:-/Users/cloud/dev/models/m22}"
HF_HOME_DIR="${HF_HOME:-$ROOT/hf_home}"
export HF_HOME="$HF_HOME_DIR"
export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"

mkdir -p "$ROOT" "$HF_HOME_DIR"
cd "$ROOT"

have_cli=0
if command -v huggingface-cli >/dev/null 2>&1; then
  have_cli=1
elif command -v hf >/dev/null 2>&1; then
  have_cli=1
  huggingface-cli() { hf "$@"; }
fi

download_repo() {
  local repo="$1"
  local dest="$2"
  local include_extra="${3:-}"
  if [[ -f "$dest/config.json" || -f "$dest/model_index.json" ]]; then
    echo "[skip] $dest already present"
    return 0
  fi
  echo "[get] $repo -> $dest"
  if [[ "$have_cli" -eq 1 ]]; then
    # Prefer fp16 / safetensors where available; exclude huge unused shards.
    huggingface-cli download "$repo" \
      --local-dir "$dest" \
      --local-dir-use-symlinks False \
      --exclude "*.msgpack" "*.h5" "*/diffusion_pytorch_model.safetensors" \
      ${include_extra}
  else
    echo "ERROR: need huggingface-cli or hf (pip install -U huggingface_hub)." >&2
    echo "Then: huggingface-cli download $repo --local-dir $dest" >&2
    exit 1
  fi
}

echo "M22_MODELS_ROOT=$ROOT"
echo "HF_HOME=$HF_HOME_DIR"

# 1) SDXL base (CreativeML OpenRAIL++-M)
download_repo "stabilityai/stable-diffusion-xl-base-1.0" \
  "$ROOT/stable-diffusion-xl-base-1.0"

# 2) Depth ControlNet (CreativeML OpenRAIL++-M)
download_repo "diffusers/controlnet-depth-sdxl-1.0" \
  "$ROOT/controlnet-depth-sdxl-1.0"

# 3) Union ControlNet Depth/Normal (Apache-2.0)
download_repo "xinsir/controlnet-union-sdxl-1.0" \
  "$ROOT/controlnet-union-sdxl-1.0"

# 4) IP-Adapter plus SDXL (Apache-2.0) — file under sdxl_models/
IP_DEST="$ROOT/IP-Adapter"
IP_FILE="$IP_DEST/sdxl_models/ip-adapter-plus_sdxl_vit-h.bin"
if [[ -f "$IP_FILE" ]]; then
  echo "[skip] $IP_FILE already present"
else
  echo "[get] h94/IP-Adapter ip-adapter-plus_sdxl_vit-h.bin"
  if [[ "$have_cli" -eq 1 ]]; then
    huggingface-cli download "h94/IP-Adapter" \
      "sdxl_models/ip-adapter-plus_sdxl_vit-h.bin" \
      --local-dir "$IP_DEST" \
      --local-dir-use-symlinks False
  else
    echo "ERROR: need huggingface-cli to fetch IP-Adapter weight." >&2
    exit 1
  fi
fi

# Hard gate checklist (must match generate_complementary_sdxl.py REQUIRED_LOCAL_WEIGHTS)
fail=0
check() {
  local rel="$1"
  local min="${2:-0}"
  local p="$ROOT/$rel"
  if [[ ! -f "$p" ]]; then
    echo "MISSING $rel" >&2
    fail=1
    return
  fi
  local sz
  sz=$(wc -c <"$p" | tr -d ' ')
  if [[ "$min" -gt 0 && "$sz" -lt "$min" ]]; then
    echo "INCOMPLETE $rel size=$sz (need >= $min)" >&2
    fail=1
  else
    echo "OK $rel ($sz bytes)"
  fi
}

echo "--- verify ---"
check "controlnet-depth-sdxl-1.0/diffusion_pytorch_model.fp16.safetensors"
check "controlnet-depth-sdxl-1.0/config.json"
check "stable-diffusion-xl-base-1.0/model_index.json"
check "stable-diffusion-xl-base-1.0/unet/diffusion_pytorch_model.fp16.safetensors"
check "stable-diffusion-xl-base-1.0/unet/config.json"
check "stable-diffusion-xl-base-1.0/text_encoder/model.fp16.safetensors"
check "stable-diffusion-xl-base-1.0/text_encoder/config.json"
check "stable-diffusion-xl-base-1.0/text_encoder_2/model.fp16.safetensors" 1300000000
check "stable-diffusion-xl-base-1.0/text_encoder_2/config.json"
check "stable-diffusion-xl-base-1.0/vae/diffusion_pytorch_model.fp16.safetensors"
check "stable-diffusion-xl-base-1.0/vae/config.json"
check "stable-diffusion-xl-base-1.0/scheduler/scheduler_config.json"
if [[ -f "$IP_FILE" ]]; then
  echo "OK IP-Adapter/sdxl_models/ip-adapter-plus_sdxl_vit-h.bin ($(wc -c <"$IP_FILE" | tr -d ' ') bytes)"
else
  echo "WARN missing IP-Adapter (weak identity lock; script may still --run)" >&2
fi

if [[ "$fail" -ne 0 ]]; then
  echo "download_m22.sh: REQUIRED weights incomplete." >&2
  exit 1
fi
echo "download_m22.sh: ready. Next: source .env.m22 && .venv-m22/bin/python pipeline/texture/generate_complementary_sdxl.py --run"
