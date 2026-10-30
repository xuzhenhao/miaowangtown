#!/bin/bash
# Contrast: ROI soft-down d135/d180 matrix (opus fef6a7d follow-up).
# Usage: run_fuse_soft_d135_d180_roi.sh <tag> <d135_soft> <d180_soft>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
MASK="docs/validation/m2_2_8dir/hold_diag/d090_torso_dark_uv_inner_mask.png"
OUT="docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_d180_roi"
BASELINE_FUR_SHA="46e56675a577390d70724e803a37c39b8cc79e070a5434c336a042da502a08dd"
ARCH="$(cat logs/m22/pre_fuse_soft_d135_archive.path)"
TAG="${1:?tag e.g. A_d180x035}"
D135="${2:?d135 soft}"
D180="${3:?d180 soft}"
DEST="$OUT/$TAG"
mkdir -p "$DEST" logs/m22

echo "=== restore baseline fur before fuse tag=$TAG d135=$D135 d180=$D180 ==="
cp -p "$ARCH/fur_albedo.png" cats/miemie/identity_v1/fur_albedo.png
cp -p "$ARCH/coverage.png" cats/miemie/identity_v1/coverage.png
CUR=$(shasum -a 256 cats/miemie/identity_v1/fur_albedo.png | awk '{print $1}')
test "$CUR" = "$BASELINE_FUR_SHA"

ROI_SOFT_CLI=()
# bash 3.2 friendly: build args without mapfile
D135_F=$(python3 -c "print(float('$D135'))")
D180_F=$(python3 -c "print(float('$D180'))")
if python3 -c "import sys; sys.exit(0 if float('$D135') < 0.999 else 1)"; then
  ROI_SOFT_CLI+=(--roi-view-soft "d135=$D135")
fi
if python3 -c "import sys; sys.exit(0 if float('$D180') < 0.999 else 1)"; then
  ROI_SOFT_CLI+=(--roi-view-soft "d180=$D180")
fi
if [ ${#ROI_SOFT_CLI[@]} -eq 0 ]; then
  echo "ERROR: need at least one soft <1.0" >&2
  exit 2
fi

echo "=== fuse tag=$TAG soft=${ROI_SOFT_CLI[*]} ==="
blender -b --python pipeline/texture/fuse_8dir_albedo.py -- \
  --roi-mask "$MASK" \
  "${ROI_SOFT_CLI[@]}" \
  --contrast-tag "fuse_soft_d135_d180_roi_$TAG" \
  > "logs/m22/fuse_soft_d135_d180_${TAG}.log" 2>&1
tail -n 50 "logs/m22/fuse_soft_d135_d180_${TAG}.log"
FUR_SHA=$(shasum -a 256 cats/miemie/identity_v1/fur_albedo.png | awk '{print $1}')
echo "fur_sha=$FUR_SHA"

echo "=== review boards ==="
blender -b --python pipeline/bake/run_m2_2_review.py \
  > "logs/m22/review_soft_d135_d180_${TAG}.log" 2>&1
tail -n 20 "logs/m22/review_soft_d135_d180_${TAG}.log"

echo "=== attrib dark UV ==="
blender -b --python pipeline/texture/attrib_dark_uv_views.py -- \
  --tag "fuse_soft_d135_d180_roi/$TAG" \
  > "logs/m22/attrib_soft_d135_d180_${TAG}.log" 2>&1
tail -n 40 "logs/m22/attrib_soft_d135_d180_${TAG}.log"

echo "=== collect artifacts ==="
cp -p cats/miemie/identity_v1/fur_albedo.png "$DEST/fur_albedo.png"
cp -p cats/miemie/identity_v1/coverage.png "$DEST/coverage.png"
cp -p cats/miemie/identity_v1/fuse_8dir_report.json "$DEST/fuse_8dir_report.json"
cp -p docs/validation/m2_2_8dir/m2_2_fuse_report.json "$DEST/m2_2_fuse_report.json" 2>/dev/null || true
cp -p docs/validation/m2_2_8dir/identity_review_layer_a.png "$DEST/" 2>/dev/null || true
cp -p docs/validation/m2_2_8dir/m2_2_d090_layer_a.png "$DEST/" 2>/dev/null || true
cp -p docs/validation/m2_2_8dir/m2_2_d045_layer_a.png "$DEST/" 2>/dev/null || true
cp -p docs/validation/m2_2_8dir/m2_2_d090_layer_a_4x_crop.png "$DEST/"
cp -p docs/validation/m2_2_8dir/m2_2_d045_layer_a_4x_crop.png "$DEST/"
echo "$FUR_SHA" > "$DEST/fur_sha.txt"
echo "done tag=$TAG fur=$FUR_SHA dest=$DEST"
