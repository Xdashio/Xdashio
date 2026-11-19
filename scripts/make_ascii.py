#!/usr/bin/env python3
"""Turn a portrait photo into ASCII art for the profile card.

Run locally only (the photo is never committed):
    python make_ascii.py photo.png ../data

Needs: pillow, numpy, rembg. Writes portrait_dark.txt and portrait_light.txt.
Prepare the photo first (crop to head and shoulders, remove any overlay text).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from rembg import new_session, remove

COLS = 64
CHAR_ASPECT = 0.5  # glyph width / line height in the card
RAMP = " .'`:;-=+ox*#%&@"  # sparse to dense; space is reserved for background
WORK_WIDTH = 640  # processing width in pixels
LOCAL_RADIUS = 30  # local-contrast radius at WORK_WIDTH
GLOBAL_WEIGHT = 0.6  # share of global tone vs local contrast
GAMMA = 0.8
MODEL = "u2net_human_seg"


def _blur(a: np.ndarray, radius: float) -> np.ndarray:
    img = Image.fromarray((a.clip(0, 1) * 255).astype("uint8"))
    return np.array(img.filter(ImageFilter.GaussianBlur(radius)), dtype=float) / 255


def _stretch(a: np.ndarray, fg: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(a[fg], [2, 98])
    return ((a - lo) / (hi - lo)).clip(0, 1)


def subject_mask(photo: Image.Image) -> Image.Image:
    return remove(photo, session=new_session(MODEL)).split()[3]


def to_grid(photo: Image.Image, mask: Image.Image) -> np.ndarray:
    box = mask.point(lambda v: 255 if v > 128 else 0).getbbox()
    if box is None:
        raise ValueError("no subject found in photo")
    photo, mask = photo.crop(box), mask.crop(box)
    size = (WORK_WIDTH, round(photo.height * WORK_WIDTH / photo.width))
    photo = photo.resize(size, Image.Resampling.LANCZOS)
    mask = mask.resize(size, Image.Resampling.LANCZOS)
    fg = np.array(mask, dtype=float) / 255 > 0.5
    value = np.array(photo.convert("HSV").split()[2], dtype=float) / 255
    mean = _blur(value, LOCAL_RADIUS)
    spread = np.sqrt(_blur((value - mean) ** 2, LOCAL_RADIUS)) + 0.03
    local = _stretch((value - mean) / spread, fg)
    tone = (GLOBAL_WEIGHT * _stretch(value, fg) + (1 - GLOBAL_WEIGHT) * local) ** GAMMA
    tone[~fg] = 0
    rows = round(COLS * photo.height / photo.width * CHAR_ASPECT)
    tone_img = Image.fromarray((tone * 255).astype("uint8"))
    small = np.array(tone_img.resize((COLS, rows), Image.Resampling.BOX), dtype=float) / 255
    alpha = np.array(mask.resize((COLS, rows), Image.Resampling.BOX), dtype=float) / 255
    small = np.where(alpha > 0.05, small / np.maximum(alpha, 1e-3), 0).clip(0, 1)
    small[alpha < 0.5] = np.nan
    return small


def render(grid: np.ndarray, bright_is_dense: bool) -> str:
    levels = len(RAMP) - 1
    lines = []
    for row in grid:
        chars = []
        for v in row:
            if np.isnan(v):
                chars.append(" ")
                continue
            t = v if bright_is_dense else 1 - v
            chars.append(RAMP[1 + min(levels - 1, int(t * levels))])
        lines.append("".join(chars).rstrip())
    return "\n".join(lines) + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: make_ascii.py <photo> <out_dir>")
    photo = ImageOps.exif_transpose(Image.open(sys.argv[1])).convert("RGB")
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    grid = to_grid(photo, subject_mask(photo))
    (out / "portrait_dark.txt").write_text(render(grid, bright_is_dense=True))
    (out / "portrait_light.txt").write_text(render(grid, bright_is_dense=False))
    print(f"wrote {grid.shape[1]}x{grid.shape[0]} portrait to {out}")


if __name__ == "__main__":
    main()
