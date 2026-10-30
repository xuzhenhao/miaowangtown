#!/bin/bash
# Contrast experiment: ROI soft-down d135 only (d180 locked). Two tiers: 0.35 / 0.15.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
MASK="docs/validation/m2_2_8dir/hold_diag/d090_torso_dark_uv_inner_mask.png"
OUT="docs/validation/m2_2_8dir/hold_diag/fuse_soft_d135_roi"
BASELINE_FUR_SHA="46e56675a577390d70724e803a37c39b8cc79e070a5434c336a042da502a08dd"
ARCH="$(cat logs/m22/pre_fuse_soft_d135_archive.path)"
SOFT="${1:?soft factor e.g. 0.35}"
TAG="x$(echo "$SOFT" | tr -d '.')"
DEST="$OUT/$TAG"
mkdir -p "$DEST" logs/m22

echo "=== restore baseline fur before fuse soft=$SOFT ==="
cp -p "$ARCH/fur_albedo.png" cats/miemie/identity_v1/fur_albedo.png
cp -p "$ARCH/coverage.png" cats/miemie/identity_v1/coverage.png
CUR=$(shasum -a 256 cats/miemie/identity_v1/fur_albedo.png | awk '{print $1}')
test "$CUR" = "$BASELINE_FUR_SHA"

echo "=== fuse soft=$SOFT tag=$TAG ==="
blender -b --python pipeline/texture/fuse_8dir_albedo.py -- \
  --roi-mask "$MASK" \
  --roi-view-soft "d135=$SOFT" \
  --contrast-tag "fuse_soft_d135_roi_$TAG" \
  > "logs/m22/fuse_soft_d135_${TAG}.log" 2>&1
tail -n 40 "logs/m22/fuse_soft_d135_${TAG}.log" | head -n 40
FUR_SHA=$(shasum -a 256 cats/miemie/identity_v1/fur_albedo.png | awk '{print $1}')
echo "fur_sha=$FUR_SHA"

echo "=== review boards ==="
blender -b --python pipeline/bake/run_m2_2_review.py \
  > "logs/m22/review_soft_d135_${TAG}.log" 2>&1
tail -n 20 "logs/m22/review_soft_d135_${TAG}.log"

echo "=== attrib dark UV ==="
blender -b --python pipeline/texture/attrib_dark_uv_views.py -- \
  --tag "fuse_soft_d135_roi/$TAG" \
  > "logs/m22/attrib_soft_d135_${TAG}.log" 2>&1
tail -n 30 "logs/m22/attrib_soft_d135_${TAG}.log"

echo "=== collect artifacts ==="
cp -p cats/miemie/identity_v1/fur_albedo.png "$DEST/fur_albedo.png"
cp -p cats/miemie/identity_v1/coverage.png "$DEST/coverage.png"
cp -p cats/miemie/identity_v1/fuse_8dir_report.json "$DEST/fuse_8dir_report.json"
cp -p docs/validation/m2_2_8dir/m2_2_fuse_report.json "$DEST/m2_2_fuse_report.json"
cp -p docs/validation/m2_2_8dir/identity_review_layer_a.png "$DEST/"
cp -p docs/validation/m2_2_8dir/m2_2_d090_layer_a.png "$DEST/" 2>/dev/null || true
cp -p docs/validation/m2_2_8dir/m2_2_d045_layer_a.png "$DEST/" 2>/dev/null || true
cp -p docs/validation/m2_2_8dir/m2_2_d090_layer_a_4x_crop.png "$DEST/"
cp -p docs/validation/m2_2_8dir/m2_2_d045_layer_a_4x_crop.png "$DEST/"
# attrib writes into hold_diag/fuse_soft_d135_roi/$TAG via --tag
echo "done soft=$SOFT fur=$FUR_SHA dest=$DEST"
