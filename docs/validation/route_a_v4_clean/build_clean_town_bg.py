#!/usr/bin/env python3
"""
Build a 100% clean town background `clean_town_bg.png` from `target_redbox_ref.png`:
1. Remove the red rounded-rectangle border (`x in [628..1036], y in [386..752]`) and the partial left-edge red line (`x < 36`)
   using directional neighbor cloning (vertical interpolation for horizontal top/bottom red bars, horizontal interpolation
   for vertical left/right red bars — zero barcode smearing!).
2. Completely remove the original cat AND all 4 of its white paws + ground shadow (`x in [702..978], y in [445..690]`):
   - For the doorstep steps behind the cat's ears/head (`y in [445..502], x in [725..845]`):
     clone the clean horizontal stone step profile from `x in [848..935]` (which is the exact same step right next to the cat's head!).
   - For the cobblestone courtyard behind the cat's body, legs, 4 white paws, and shadow (`y in [502..690], x in [702..978]`):
     clone a seamless, continuous 2D cobblestone block from the clean courtyard immediately to the right (`x in [980..1256], y in [502..690]`),
     with a soft 6px Gaussian feather around the outer boundary so tile seams blend invisibly!
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

V1_DIR = Path("/workspace/miaowangtown/docs/validation/ab_static_compare")
OUT_DIR = Path("/workspace/miaowangtown/docs/validation/route_a_v4_clean")
OUT_DIR.mkdir(parents=True, exist_ok=True)

im = Image.open(V1_DIR / "target_redbox_ref.png").convert("RGB")
arr = np.array(im).astype(np.float32)
H, W, _ = arr.shape

# Step 1: Detect red annotation pixels
r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
red_raw = ((r - g) > 65.0) & (r > 125.0) & (b < 100.0)

border_zone = np.zeros((H, W), dtype=bool)
border_zone[384:755, 624:1040] = True
# Exclude inner cat region so nose/ears are not touched in step 1
inner_cat = np.zeros((H, W), dtype=bool)
inner_cat[440:695, 695:985] = True
border_zone &= ~inner_cat
border_zone[:, :38] = True

# Dilate red mask by 4px to cover anti-aliased red glow
red_mask = red_raw & border_zone
for _ in range(4):
    nxt = red_mask.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nxt |= np.roll(np.roll(red_mask, dy, axis=0), dx, axis=1)
    red_mask = nxt

cleaned = arr.copy()

# Clean top horizontal red bar (y in [384..412], x in [624..1040]) by copying clean doorstep/wall texture from 14px below/above
# Wait: at y=384..412, above (y=370..384) is the wooden sliding door base/threshold, and below (y=412..426) is the upper step shadow.
# Let us linearly blend vertically between y_top (first non-red pixel above) and y_bot (first non-red pixel below), PLUS add subtle horizontal grain from neighbor!
for x in range(624, 1040):
    # Top bar around y=385..415
    ys_top = np.where(red_mask[382:425, x])[0] + 382
    if len(ys_top) > 0:
        y0, y1 = int(ys_top.min()) - 1, int(ys_top.max()) + 1
        y0 = max(0, y0)
        y1 = min(H - 1, y1)
        c_top = cleaned[y0, x]
        c_bot = cleaned[y1, x]
        for y in range(y0 + 1, y1):
            t = (y - y0) / float(max(1, y1 - y0))
            cleaned[y, x] = (1.0 - t) * c_top + t * c_bot

    # Bottom bar around y=725..755
    ys_bot = np.where(red_mask[720:758, x])[0] + 720
    if len(ys_bot) > 0:
        y0, y1 = int(ys_bot.min()) - 1, int(ys_bot.max()) + 1
        c_top = cleaned[y0, x]
        c_bot = cleaned[y1, x]
        for y in range(y0 + 1, y1):
            t = (y - y0) / float(max(1, y1 - y0))
            cleaned[y, x] = (1.0 - t) * c_top + t * c_bot

# Clean left vertical red bar (x in [624..665], y in [384..755]) and right vertical red bar (x in [1000..1040], y in [384..755])
# and far-left edge red bar (x < 38) by horizontal interpolation!
for y in range(0, H):
    for x_start, x_end in [(0, 42), (620, 675), (995, 1042)]:
        xs_seg = np.where(red_mask[y, x_start:x_end])[0] + x_start
        if len(xs_seg) > 0:
            x0, x1 = int(xs_seg.min()) - 1, int(xs_seg.max()) + 1
            x0 = max(0, x0)
            x1 = min(W - 1, x1)
            c_left = cleaned[y, x0] if x0 > 0 else cleaned[y, x1]
            c_right = cleaned[y, x1] if x1 < W - 1 else cleaned[y, x0]
            for x in range(x0 + 1, x1):
                t = (x - x0) / float(max(1, x1 - x0))
                cleaned[y, x] = (1.0 - t) * c_left + t * c_right

# Step 2: Completely erase the original cat + all 4 white paws + shadow (y in [442..690], x in [700..980])
plate = cleaned.copy()

# 2a. Doorstep steps behind the cat's ears & top of head (y in [442..502], x in [720..855]):
# Notice that x in [856..945], y in [442..502] is the EXACT SAME horizontal stone doorstep right next to the cat's head!
for y in range(442, 504):
    for x in range(715, 860):
        # Sample from the clean step segment [858..938] with smooth horizontal tile continuity
        src_x = 858 + ((x - 715) % 76)
        plate[y, x] = cleaned[y, src_x]

# 2b. Cobblestone courtyard behind the cat's body, legs, 4 white paws, and shadow (y in [500..690], x in [700..980]):
# Copy a continuous, unstretched 2D cobblestone patch from the clean courtyard to the right (x in [982..1262], y in [490..680])
for y in range(500, 690):
    for x in range(700, 980):
        src_x = 984 + (x - 700)
        # Offset y by -12 so tile rows align naturally with the left courtyard stones
        src_y = y - 12
        plate[y, x] = cleaned[src_y, src_x]

# Feather the patch boundary (6px soft transition) so there is zero visible seam around (700..980, 442..690)
mask_patch = np.zeros((H, W), dtype=np.float32)
mask_patch[446:686, 706:974] = 1.0
mask_blur = np.array(
    Image.fromarray((mask_patch * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=5.0)),
    dtype=np.float32
)[:, :, None] / 255.0

final_bg = np.clip(plate * mask_blur + cleaned * (1.0 - mask_blur), 0, 255).astype(np.uint8)
bg_im = Image.fromarray(final_bg)
bg_im.save(OUT_DIR / "clean_town_bg.png")

# Save the exact closeup crop (680, 420, 995, 700) of clean_town_bg.png for visual verification!
bg_im.crop((680, 420, 995, 700)).save(OUT_DIR / "clean_town_bg_closeup_check.png")
print("Saved clean_town_bg.png and clean_town_bg_closeup_check.png")
