#!/usr/bin/env python3
"""
Create a clean town background plate `town_clean_plate.png` from `target_redbox_ref.png`:
1. Remove the red rounded-rectangle annotation border (`x in [625..1038], y in [382..755]`) and the partial left-edge red line (`x < 35`) via iterative neighbor inpainting.
2. Remove the original cat inside `x in [700..990], y in [445..670]` by reconstructing the cobblestone pavement, doorstep steps, and foreground bush top using surrounding clean stone tile patches.
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

OUT_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
im = Image.open(OUT_DIR / "target_redbox_ref.png").convert("RGB")
arr = np.array(im)
H, W, _ = arr.shape

def dilate_bool(mask: np.ndarray, iters: int = 3) -> np.ndarray:
    m = mask.copy()
    for _ in range(iters):
        nxt = m.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                nxt |= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
        m = nxt
    return m

def inpaint_mask(img_arr: np.ndarray, mask: np.ndarray, passes: int = 24) -> np.ndarray:
    out = img_arr.astype(np.float32).copy()
    valid = ~mask
    for _ in range(passes):
        if np.all(valid):
            break
        acc = np.zeros_like(out)
        cnt = np.zeros((H, W, 1), dtype=np.float32)
        for dy, dx, w in [(-1,0,1.0),(1,0,1.0),(0,-1,1.0),(0,1,1.0),(-1,-1,0.7),(1,-1,0.7),(-1,1,0.7),(1,1,0.7)]:
            sv = np.roll(np.roll(valid, dy, axis=0), dx, axis=1)
            so = np.roll(np.roll(out, dy, axis=0), dx, axis=1)
            m = (~valid) & sv
            acc[m] += so[m] * w
            cnt[m, 0] += w
        fill = (~valid) & (cnt[:, :, 0] > 0)
        out[fill] = acc[fill] / cnt[fill]
        valid[fill] = True
    return np.clip(out, 0, 255).astype(np.uint8)

# 1. Remove red annotation border and left-edge red line
red_raw = (arr[:, :, 0].astype(int) - arr[:, :, 1].astype(int) > 85) & (arr[:, :, 0] > 140) & (arr[:, :, 2] < 90)
# Keep only border regions (outer ring of redbox + left edge)
border_zone = np.zeros((H, W), dtype=bool)
border_zone[380:758, 624:1040] = True
# Exclude inner cat nose/ear area from red_raw just in case
inner_cat_safe = np.zeros((H, W), dtype=bool)
inner_cat_safe[430:700, 680:990] = True
border_zone &= ~inner_cat_safe
border_zone[:, :36] = True

red_mask = dilate_bool(red_raw & border_zone, iters=4)
clean_border_arr = inpaint_mask(arr, red_mask, passes=20)
Image.fromarray(clean_border_arr).save(OUT_DIR / "town_no_redbox_with_refcat.png")

# 2. Now reconstruct the cobblestone & doorstep background behind the original cat
# Original cat occupies roughly x in [712..975], y in [450..662] (in full image coords: crop starts at x0=644, y0=401)
plate = clean_border_arr.copy()

# Let us inspect what is behind the cat in full image coordinates:
# y in [445..495]: stone doorstep steps below the inn sliding door (horizontal steps at y~450..490, extending across x=[700..960])
# y in [495..655]: dark grey cobblestone courtyard (same tile pattern as x=[975..1180, y=495..665])
# y in [645..670], x in [790..910]: top of the green bush / stone railing

# Reconstruct doorstep steps (y in [445..500], x in [705..955]) by horizontal continuation from left/right doorstep + upper step
for y in range(445, 502):
    # Blend horizontally from x=700..725 and x=945..975 with slight tile texture from x+180
    for x in range(708, 955):
        t = (x - 708) / float(955 - 708)
        left_col = plate[y, 704 - (x % 6)].astype(np.float32)
        right_col = plate[y, 958 + (x % 6)].astype(np.float32)
        plate[y, x] = np.clip((1.0 - t) * left_col + t * right_col, 0, 255).astype(np.uint8)

# Reconstruct cobblestone courtyard (y in [496..660], x in [708..976])
# Copy structured cobblestone patch from the clean courtyard immediately to the right (x in [980..1248], same y band!)
for y in range(496, 662):
    for x in range(708, 976):
        # Protect the bush & stone railing at the bottom (y > 635)
        # In the original image, the green bush is around x=[800..930], y=[645..730], and stone railing at x=[680..795], y=[625..730]
        if y > 622 and x < 785:
            # Stone railing top-left corner: only replace if it was actually cat paw/shadow (y < 642 and x > 740)
            if not (y < 648 and x > 738):
                continue
        if y > 642 and 795 <= x <= 935:
            # Green bush top: only replace above y=654
            if y >= 654:
                continue
        src_x = 982 + ((x - 708) % 240)
        src_y = y
        plate[y, x] = plate[src_y, src_x]

# Feather the boundary of the reconstructed patch (4px soft blend)
feather_mask = np.zeros((H, W), dtype=np.float32)
feather_mask[448:652, 712:972] = 1.0
# Keep railing and lower bush out of feather mask
feather_mask[625:, :742] = 0.0
feather_mask[652:, 795:935] = 0.0
feather_im = Image.fromarray((feather_mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=3.5))
alpha = np.array(feather_im, dtype=np.float32)[:, :, None] / 255.0

final_plate = np.clip(plate.astype(np.float32) * alpha + clean_border_arr.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)
Image.fromarray(final_plate).save(OUT_DIR / "town_clean_plate.png")
print("Saved town_clean_plate.png")
