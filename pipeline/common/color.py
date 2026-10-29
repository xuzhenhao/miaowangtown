"""sRGB / CIE Lab helpers for CatGenome color extraction (no external deps beyond numpy)."""
from __future__ import annotations

import numpy as np


def srgb_u8_to_linear(c: np.ndarray) -> np.ndarray:
    c = c.astype(np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb_u8(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    s = np.where(c <= 0.0031308, 12.92 * c, 1.055 * (c ** (1.0 / 2.4)) - 0.055)
    return np.clip(np.round(s * 255.0), 0, 255).astype(np.uint8)


def rgb_u8_to_lab(rgb: np.ndarray) -> np.ndarray:
    """rgb (... ,3) uint8/float -> Lab (... ,3)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    single = rgb.ndim == 1
    if single:
        rgb = rgb[None, :]
    flat = rgb.reshape(-1, 3)
    lin = srgb_u8_to_linear(flat)
    m = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ],
        dtype=np.float64,
    )
    xyz = lin @ m.T
    xn, yn, zn = 0.95047, 1.0, 1.08883
    x, y, z = xyz[:, 0] / xn, xyz[:, 1] / yn, xyz[:, 2] / zn

    def f(t: np.ndarray) -> np.ndarray:
        return np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16.0 / 116.0)

    fx, fy, fz = f(x), f(y), f(z)
    lab = np.stack([116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)], axis=1)
    out = lab.reshape(rgb.shape[:-1] + (3,))
    return out[0] if single else out


def lab_to_srgb_hex(lab: list[float] | np.ndarray) -> str:
    L, a, b = [float(x) for x in lab]
    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    def finv(t: float) -> float:
        t3 = t ** 3
        return t3 if t3 > 0.008856 else (t - 16.0 / 116.0) / 7.787

    xn, yn, zn = 0.95047, 1.0, 1.08883
    X, Y, Z = xn * finv(fx), yn * finv(fy), zn * finv(fz)
    m_inv = np.array(
        [
            [3.2404542, -1.5371385, -0.4985314],
            [-0.9692660, 1.8760108, 0.0415560],
            [0.0556434, -0.2040259, 1.0572252],
        ],
        dtype=np.float64,
    )
    rgb_lin = m_inv @ np.array([X, Y, Z])
    u8 = linear_to_srgb_u8(rgb_lin)
    return "#%02X%02X%02X" % (int(u8[0]), int(u8[1]), int(u8[2]))


def rgb_to_hex(rgb) -> str:
    r, g, b = [int(round(float(x))) for x in rgb]
    return "#%02X%02X%02X" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def drop_highlights_shadows(rgb_pixels: np.ndarray, drop_pct: float = 5.0) -> np.ndarray:
    """Keep midtones by dropping top/bottom `drop_pct` luminance percentiles."""
    pix = np.asarray(rgb_pixels, dtype=np.float64).reshape(-1, 3)
    if len(pix) == 0:
        return pix
    luma = 0.299 * pix[:, 0] + 0.587 * pix[:, 1] + 0.114 * pix[:, 2]
    lo, hi = np.percentile(luma, [drop_pct, 100.0 - drop_pct])
    keep = pix[(luma >= lo) & (luma <= hi)]
    return keep if len(keep) else pix


def mean_lab_hex(rgb_pixels: np.ndarray, drop_pct: float = 5.0) -> dict:
    keep = drop_highlights_shadows(rgb_pixels, drop_pct=drop_pct)
    mean = keep.mean(axis=0)
    lab = rgb_u8_to_lab(mean)
    return {
        "srgb": rgb_to_hex(mean),
        "rgb": [round(float(c), 2) for c in mean],
        "lab": [round(float(c), 2) for c in lab],
        "sample_count": int(len(keep)),
        "drop_highlights_shadows_pct": drop_pct,
    }
