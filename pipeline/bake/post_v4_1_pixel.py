#!/usr/bin/env python3
"""
Route A v4.1 pixel post: mask-aware Box downsample, edge cleanup, optional lantern+AO,
optional palette quantize (none / lut36 / lut48, dither=none).
Used by M2.1 Layer A/B and the quantize experiment.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ALPHA_THR = 162


def get_4conn_boundary(mask: np.ndarray) -> np.ndarray:
    er = mask.copy()
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        s = np.zeros_like(mask)
        if dy == -1:
            s[:-1, :] = mask[1:, :]
        elif dy == 1:
            s[1:, :] = mask[:-1, :]
        elif dx == -1:
            s[:, :-1] = mask[:, 1:]
        elif dx == 1:
            s[:, 1:] = mask[:, :-1]
        er &= s
    return mask & (~er)


def extrapolate_rgb(rgb: np.ndarray, alpha: np.ndarray, passes: int = 14) -> np.ndarray:
    rgb_c = rgb.astype(np.float32).copy()
    val = alpha.copy()
    for _ in range(passes):
        if np.all(val):
            break
        acc = np.zeros_like(rgb_c)
        cnt = np.zeros(alpha.shape, dtype=np.float32)
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            sv = np.roll(np.roll(val, dy, axis=0), dx, axis=1)
            sc = np.roll(np.roll(rgb_c, dy, axis=0), dx, axis=1)
            acc += sc * sv[:, :, None]
            cnt += sv.astype(np.float32)
        fill = (~val) & (cnt > 0)
        if not np.any(fill):
            break
        rgb_c[fill] = acc[fill] / cnt[fill][:, None]
        val[fill] = True
    return rgb_c


def apply_lantern_ao(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Runtime-matching top-right warm lantern + underbelly AO (Upgrade 3 from build_route_a_v4_1)."""
    sh, sw = rgb.shape[:2]
    yy, xx = np.meshgrid(
        np.linspace(0.0, 1.0, sh, dtype=np.float32),
        np.linspace(0.0, 1.0, sw, dtype=np.float32),
        indexing="ij",
    )
    key_light = np.clip(1.0 - ((xx - 0.38) ** 2 / 0.28 + (yy - 0.18) ** 2 / 0.18), 0.0, 1.0)

    def soft_field(cx, cy, rx, ry, blur):
        d2 = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
        raw = np.exp(-0.5 * d2)
        im = Image.fromarray(np.clip(raw * 255.0, 0, 255).astype(np.uint8), mode="L")
        im = im.filter(ImageFilter.GaussianBlur(radius=blur))
        return np.array(im, dtype=np.float32) / 255.0

    # Scale blur with resolution (tuned on 901x823)
    blur_scale = max(1.0, sh / 823.0)
    ao_belly = soft_field(0.48, 0.76, 0.22, 0.10, 24.0 * blur_scale)
    ao_chin = soft_field(0.22, 0.54, 0.08, 0.04, 16.0 * blur_scale)
    ao_total = np.clip(ao_belly * 0.75 + ao_chin * 0.45, 0.0, 1.0)

    work = rgb.astype(np.float32)
    is_eye = ((work[:, :, 1] - work[:, :, 0]) > 10.0) & (work[:, :, 1] > 70.0)
    env = np.ones_like(work)
    env[:, :, 0] += key_light * 0.055
    env[:, :, 1] += key_light * 0.025
    env[:, :, 2] -= key_light * 0.015
    env[:, :, 0] -= ao_total * 0.10
    env[:, :, 1] -= ao_total * 0.11
    env[:, :, 2] -= ao_total * 0.12
    env[is_eye] = 1.0
    out = np.clip(work * env, 0, 255)
    out[~alpha] = 0
    return out


def downsample_to_logical(
    rgba_hi: np.ndarray,
    gw: int = 114,
    gh: int = 104,
    alpha_thr: int = ALPHA_THR,
    protect_eyes: bool = True,
) -> np.ndarray:
    """Mask-aware Box downsample + unsharp + eye nearest protect + speckle cleanup."""
    rgb = rgba_hi[:, :, :3].astype(np.float32)
    alpha = rgba_hi[:, :, 3] > 128
    rgb_x = extrapolate_rgb(rgb, alpha, passes=16)
    # mild median denoise
    med = np.array(
        Image.fromarray(np.clip(rgb_x, 0, 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(size=3)),
        dtype=np.float32,
    )
    work = 0.65 * med + 0.35 * rgb_x

    im_rgb = Image.fromarray(np.clip(work, 0, 255).astype(np.uint8), mode="RGB")
    box = np.array(im_rgb.resize((gw, gh), Image.Resampling.BOX).filter(
        ImageFilter.UnsharpMask(radius=1.0, percent=115, threshold=2)
    ), dtype=np.uint8)
    near = np.array(im_rgb.resize((gw, gh), Image.Resampling.NEAREST), dtype=np.uint8)

    if protect_eyes:
        eye_zone = np.zeros((gh, gw), dtype=bool)
        eye_zone[31:47, 10:35] = True
        is_eye = eye_zone & (
            ((near[:, :, 1].astype(int) - near[:, :, 0].astype(int)) > 8)
            | (near[:, :, 0] > 220)
            | ((near[:, :, 0] < 45) & (near[:, :, 1] < 45))
        )
        box[is_eye] = near[is_eye]

    a_hi = Image.fromarray((alpha.astype(np.uint8) * 255), mode="L")
    a_low = np.array(a_hi.resize((gw, gh), Image.Resampling.BOX))
    alpha_low = a_low > alpha_thr
    nb = np.zeros_like(alpha_low, dtype=np.int32)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nb += np.roll(np.roll(alpha_low, dy, axis=0), dx, axis=1).astype(np.int32)
    alpha_low &= nb >= 2

    # isolated luma outlier cleanup outside eyes
    low = box.astype(np.float32)
    luma = 0.299 * low[:, :, 0] + 0.587 * low[:, :, 1] + 0.114 * low[:, :, 2]
    nb_l = np.stack(
        [
            np.roll(luma, -1, axis=0),
            np.roll(luma, 1, axis=0),
            np.roll(luma, -1, axis=1),
            np.roll(luma, 1, axis=1),
        ],
        axis=0,
    )
    nb_rgb = np.stack(
        [
            np.roll(low, -1, axis=0),
            np.roll(low, 1, axis=0),
            np.roll(low, -1, axis=1),
            np.roll(low, 1, axis=1),
        ],
        axis=0,
    )
    med_l = np.median(nb_l, axis=0)
    med_rgb = np.median(nb_rgb, axis=0)
    eye_zone = np.zeros((gh, gw), dtype=bool)
    eye_zone[31:47, 10:35] = True
    outlier = (np.abs(luma - med_l) > 28) & (~eye_zone) & alpha_low
    low[outlier] = med_rgb[outlier]

    out = np.zeros((gh, gw, 4), dtype=np.uint8)
    out[:, :, :3] = np.clip(low, 0, 255).astype(np.uint8)
    out[:, :, 3] = np.where(alpha_low, 255, 0).astype(np.uint8)
    # 1px dark outline
    dil = alpha_low.copy()
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        dil |= np.roll(np.roll(alpha_low, dy, axis=0), dx, axis=1)
    outline = dil & (~alpha_low)
    out[outline, :3] = (27, 16, 10)
    out[outline, 3] = 255
    return out


def build_palette(rgb_samples: np.ndarray, n_colors: int, lock_colors: list[tuple[int, int, int]]) -> np.ndarray:
    """Simple farthest-point / residual k-means-ish palette in RGB; lock forced colors first."""
    locks = np.array(lock_colors, dtype=np.float64)
    pix = rgb_samples.reshape(-1, 3).astype(np.float64)
    # subsample
    if len(pix) > 20000:
        rng = np.random.default_rng(42)
        pix = pix[rng.choice(len(pix), 20000, replace=False)]
    palette = list(locks)
    # greedy farthest point
    while len(palette) < n_colors:
        P = np.array(palette, dtype=np.float64)
        d = ((pix[:, None, :] - P[None, :, :]) ** 2).sum(axis=2).min(axis=1)
        idx = int(np.argmax(d))
        palette.append(pix[idx])
    # a few mean-shift refinements
    pal = np.array(palette[:n_colors], dtype=np.float64)
    n_lock = len(locks)
    for _ in range(8):
        d = ((pix[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        lab = d.argmin(axis=1)
        for k in range(n_lock, n_colors):
            m = lab == k
            if m.any():
                pal[k] = pix[m].mean(axis=0)
    return np.clip(np.round(pal), 0, 255).astype(np.uint8)


def quantize_rgb(rgba: np.ndarray, palette: np.ndarray) -> np.ndarray:
    rgb = rgba[:, :, :3].astype(np.float64)
    a = rgba[:, :, 3]
    flat = rgb.reshape(-1, 3)
    d = ((flat[:, None, :] - palette[None, :, :].astype(np.float64)) ** 2).sum(axis=2)
    idx = d.argmin(axis=1)
    out = palette[idx].reshape(rgb.shape)
    rgba_o = np.zeros_like(rgba)
    rgba_o[:, :, :3] = out
    rgba_o[:, :, 3] = a
    return rgba_o


def palette_hash(palette: np.ndarray) -> str:
    payload = palette.astype(np.uint8).tobytes()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def logical_to_canvas_2x(logical_rgba: np.ndarray) -> np.ndarray:
    """2x2 integer canvas blocks (nearest)."""
    im = Image.fromarray(logical_rgba, mode="RGBA")
    return np.array(im.resize((logical_rgba.shape[1] * 2, logical_rgba.shape[0] * 2), Image.Resampling.NEAREST))


def scale_nearest(rgba: np.ndarray, scale: int) -> np.ndarray:
    im = Image.fromarray(rgba, mode="RGBA")
    return np.array(im.resize((rgba.shape[1] * scale, rgba.shape[0] * scale), Image.Resampling.NEAREST))
