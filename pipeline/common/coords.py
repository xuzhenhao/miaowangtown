"""Coordinate conversion utilities between Blender UV (bottom-left) and Image pixels (top-left)."""
from typing import Tuple


def uv_to_pixel(u: float, v: float, width: int, height: int) -> Tuple[float, float]:
    """Convert Blender UV (origin bottom-left) to image pixel coordinates (origin top-left)."""
    x = float(u) * (width - 1)
    y = (1.0 - float(v)) * (height - 1)
    return x, y


def pixel_to_uv(x: float, y: float, width: int, height: int) -> Tuple[float, float]:
    """Convert image pixel coordinates (origin top-left) to Blender UV (origin bottom-left)."""
    u = float(x) / max(width - 1, 1)
    v = 1.0 - float(y) / max(height - 1, 1)
    return u, v
