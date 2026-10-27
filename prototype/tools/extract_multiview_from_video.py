#!/usr/bin/env python3
"""
从绕喵一圈的视频中自动抽取最清晰的多视角帧，供腾讯混元 3D 多视图模式上传。

用法：
  python3 prototype/tools/extract_multiview_from_video.py path/to/orbit.mp4
  python3 prototype/tools/extract_multiview_from_video.py path/to/orbit.mov --out docs/hunyuan_multiview/from_video

依赖：ffmpeg（必需）+ numpy/Pillow（必需）。若安装了 opencv-python 则用其算 Laplacian 清晰度，否则用 numpy 近似。
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image


SLOT_ORDER = [
    ("01_front", 0.0),
    ("05_left45", 45.0),
    ("02_left", 90.0),
    ("04_back", 180.0),
    ("03_right", 270.0),
    ("06_right45", 315.0),
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def video_meta(path: Path) -> tuple[float, float]:
    """Return (duration_sec, fps) via ffprobe."""
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ],
        text=True,
    )
    data = json.loads(out)
    duration = None
    fps = 30.0
    if data.get("streams"):
        s = data["streams"][0]
        if s.get("duration"):
            duration = float(s["duration"])
        fr = s.get("r_frame_rate", "30/1")
        if "/" in fr:
            a, b = fr.split("/")
            fps = float(a) / max(float(b), 1e-6)
    if duration is None and data.get("format", {}).get("duration"):
        duration = float(data["format"]["duration"])
    if duration is None:
        raise RuntimeError("无法读取视频时长")
    return duration, fps


def laplacian_var(gray: np.ndarray) -> float:
    """Variance of Laplacian — higher = sharper."""
    try:
        import cv2  # type: ignore
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        # numpy fallback: simple second-derivative approx
        g = gray.astype(np.float64)
        lap = (
            -4 * g
            + np.roll(g, 1, 0) + np.roll(g, -1, 0)
            + np.roll(g, 1, 1) + np.roll(g, -1, 1)
        )
        return float(lap.var())


def load_gray(path: Path) -> np.ndarray:
    im = Image.open(path).convert("L")
    return np.asarray(im)


def autocrop_subject(im: Image.Image, pad_ratio: float = 0.08) -> Image.Image:
    """Center-crop around non-background subject using simple luminance threshold."""
    arr = np.asarray(im.convert("RGB"))
    # assume background is relatively bright or dark uniform; use edge of color variance
    gray = arr.mean(axis=2)
    # subject mask: deviation from border median
    border = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
    bg = float(np.median(border))
    mask = np.abs(gray - bg) > 18
    if mask.sum() < 100:
        return im
    ys, xs = np.where(mask)
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    h, w = gray.shape
    pad_x = int((x1 - x0) * pad_ratio) + 4
    pad_y = int((y1 - y0) * pad_ratio) + 4
    x0 = max(0, x0 - pad_x)
    x1 = min(w - 1, x1 + pad_x)
    y0 = max(0, y0 - pad_y)
    y1 = min(h - 1, y1 + pad_y)
    # square crop centered on subject
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    side = max(x1 - x0, y1 - y0)
    half = side / 2
    sx0 = int(max(0, cx - half))
    sy0 = int(max(0, cy - half))
    sx1 = int(min(w, cx + half))
    sy1 = int(min(h, cy + half))
    cropped = im.crop((sx0, sy0, sx1, sy1))
    return cropped


def extract(video: Path, out_dir: Path, samples_per_slot: int = 7, size: int = 1024) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_frames_raw"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    duration, fps = video_meta(video)
    # Sample densely along the orbit (assume roughly one full turn over the clip)
    n_sample = max(48, int(duration * min(fps, 12)))
    # ffmpeg extract at even intervals
    run([
        "ffmpeg", "-y", "-i", str(video),
        "-vf", f"fps={n_sample / max(duration, 0.1)}",
        str(tmp / "frame_%04d.png"),
    ])
    frames = sorted(tmp.glob("frame_*.png"))
    if len(frames) < 6:
        raise RuntimeError(f"抽帧过少：仅 {len(frames)} 帧")

    # Score sharpness
    scored = []
    for i, fp in enumerate(frames):
        gray = load_gray(fp)
        scored.append((laplacian_var(gray), i, fp))

    n = len(scored)
    results = []
    manifest = []
    for slot_name, angle in SLOT_ORDER:
        # Map angle 0..360 to frame index assuming constant orbit speed starting at front
        center = (angle / 360.0) * n
        window = max(2, n // 16)
        candidates = []
        for sharp, i, fp in scored:
            # circular distance
            d = min(abs(i - center), n - abs(i - center))
            if d <= window:
                candidates.append((sharp, i, fp))
        if not candidates:
            # fallback nearest
            candidates = sorted(scored, key=lambda t: min(abs(t[1] - center), n - abs(t[1] - center)))[:samples_per_slot]
        candidates.sort(key=lambda t: -t[0])
        best = candidates[0]
        im = Image.open(best[2]).convert("RGB")
        im = autocrop_subject(im)
        # pad to square then resize
        w, h = im.size
        side = max(w, h)
        canvas = Image.new("RGB", (side, side), (230, 232, 234))
        canvas.paste(im, ((side - w) // 2, (side - h) // 2))
        canvas = canvas.resize((size, size), Image.Resampling.LANCZOS)
        out_path = out_dir / f"{slot_name}.png"
        canvas.save(out_path)
        results.append(out_path)
        manifest.append({
            "slot": slot_name,
            "angle_deg": angle,
            "source_frame": best[2].name,
            "sharpness": best[0],
            "output": str(out_path),
        })
        print(f"[slot] {slot_name} angle={angle} sharp={best[0]:.1f} -> {out_path}")

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"[done] wrote {len(results)} frames to {out_dir}")
    return results


def main():
    ap = argparse.ArgumentParser(description="Extract Hunyuan multiview frames from an orbit video of Miemie")
    ap.add_argument("video", type=Path, help="Input .mp4 / .mov orbit video")
    ap.add_argument("--out", type=Path, default=None, help="Output directory")
    ap.add_argument("--size", type=int, default=1024)
    args = ap.parse_args()
    if not args.video.exists():
        print(f"视频不存在: {args.video}", file=sys.stderr)
        sys.exit(1)
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("需要系统安装 ffmpeg / ffprobe", file=sys.stderr)
        sys.exit(1)
    repo = Path(__file__).resolve().parents[2]
    out = args.out or (repo / "docs" / "hunyuan_multiview" / "from_video")
    extract(args.video, out, size=args.size)


if __name__ == "__main__":
    main()
