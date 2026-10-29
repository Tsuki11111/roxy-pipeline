#!/usr/bin/env python3
"""Normalize a character illustration into a 1080x1920 transparent PNG.

Assumes a clean, near-white background (e.g. ChatGPT image output). Removes only
background connected to the image border, so ivory clothing is preserved.

Usage:
    python scripts/tools/prepare_character_asset.py input.webp output.png
    python scripts/tools/prepare_character_asset.py input.webp output.png --preview preview.png
    python scripts/tools/prepare_character_asset.py input.webp output.png --keep-largest-component
    python scripts/tools/prepare_character_asset.py input.webp output.png --remove-corner-watermark
    python scripts/tools/prepare_character_asset.py input.webp output.png --crop-bottom 160 --keep-largest-component
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def remove_white_background(im: Image.Image, threshold: int = 242) -> Image.Image:
    arr = np.asarray(im.convert("RGB"))
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    spread = arr.max(axis=2).astype(int) - arr.min(axis=2).astype(int)
    near_white = (r >= threshold) & (g >= threshold) & (b >= threshold - 4) & (spread <= 8)

    labels, _ = ndimage.label(near_white)
    border_labels = (
        set(labels[0, :])
        | set(labels[-1, :])
        | set(labels[:, 0])
        | set(labels[:, -1])
    )
    # label 0 is every pixel that is not near-white; never treat it as background
    border_labels.discard(0)
    background = np.isin(labels, list(border_labels))
    # Remove the anti-aliased white fringe, but keep dark outlines and tinted clothing.
    halo = ndimage.binary_dilation(background, iterations=2) & (arr.min(axis=2) > 225)
    background |= halo

    alpha = np.where(background, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([arr, alpha]), "RGBA")


def keep_largest_component(im: Image.Image) -> Image.Image:
    arr = np.asarray(im).copy()
    foreground = arr[..., 3] > 0
    labels, count = ndimage.label(foreground)
    if count <= 1:
        return im
    sizes = ndimage.sum(foreground, labels, range(1, count + 1))
    keep = int(np.argmax(sizes)) + 1
    arr[labels != keep, 3] = 0
    return Image.fromarray(arr, "RGBA")


def remove_corner_watermark(
    im: Image.Image,
    width_ratio: float = 0.36,
    height_ratio: float = 0.20,
    min_brightness: int = 195,
    max_saturation: int = 24,
    dilate: int = 2,
) -> Image.Image:
    """Erase a light, low-saturation corner watermark from the foreground.

    The watermark often overlaps the character (e.g. Doubao text over a braid),
    so it cannot be dropped as a separate component. Mask bright, low-saturation
    pixels in the bottom-right region and fill them from the nearest opaque
    pixel; pixels over the already-transparent background are left untouched.
    """
    arr = np.array(im)
    h, w = arr.shape[:2]
    x0 = int(w * (1 - width_ratio))
    y0 = int(h * (1 - height_ratio))
    roi = arr[y0:, x0:]
    rgb = roi[..., :3].astype(int)
    alpha = roi[..., 3] > 0
    low = rgb.min(axis=2)
    sat = rgb.max(axis=2) - low
    mask = np.zeros((h, w), dtype=bool)
    mask[y0:, x0:] = alpha & (low >= min_brightness) & (sat <= max_saturation)
    if not mask.any():
        return im
    mask = ndimage.binary_dilation(mask, iterations=dilate) & (arr[..., 3] > 0)
    valid = (~mask) & (arr[..., 3] > 0)
    if not valid.any():
        return im
    indices = ndimage.distance_transform_edt(
        ~valid, return_distances=False, return_indices=True
    )
    filled = arr[..., :3][indices[0], indices[1]]
    arr[..., :3][mask] = filled[mask]
    arr[..., 3][mask] = 255
    return Image.fromarray(arr, "RGBA")


def fit_canvas(
    im: Image.Image,
    canvas: tuple[int, int],
    top_margin: int,
    bottom_padding: int = 0,
) -> Image.Image:
    alpha = np.asarray(im)[..., 3]
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0:
        raise SystemExit("no foreground pixels left after background removal")
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    crop = im.crop(bbox)
    cw, ch = crop.size
    max_w, max_h = canvas[0], canvas[1] - top_margin - bottom_padding
    scale = min(max_w / cw, max_h / ch)
    nw, nh = max(1, round(cw * scale)), max(1, round(ch * scale))
    resized = crop.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    x = (canvas[0] - nw) // 2
    y = canvas[1] - bottom_padding - nh
    out.alpha_composite(resized, (x, y))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--canvas", default="1080x1920")
    parser.add_argument("--top-margin", type=int, default=60)
    parser.add_argument(
        "--bottom-padding",
        type=int,
        default=0,
        help="keep space below the lowest pixel (use for jump/air poses)",
    )
    parser.add_argument("--threshold", type=int, default=242)
    parser.add_argument(
        "--keep-largest-component",
        action="store_true",
        help="drop small isolated foreground elements such as a corner watermark",
    )
    parser.add_argument(
        "--remove-corner-watermark",
        action="store_true",
        help="erase a light bottom-right watermark that overlaps the character",
    )
    parser.add_argument(
        "--crop-bottom",
        type=int,
        default=0,
        help="crop this many pixels from the bottom before processing (watermark-safe)",
    )
    parser.add_argument("--preview", type=Path, help="optional paper-background preview")
    parser.add_argument(
        "--tight",
        action="store_true",
        help="save a tight crop instead of 1080x1920 (for scene/prop assets)",
    )
    args = parser.parse_args()

    width, height = (int(x) for x in args.canvas.lower().split("x"))
    im = Image.open(args.input).convert("RGB")
    if args.crop_bottom:
        im = im.crop((0, 0, im.width, im.height - args.crop_bottom))
    rgba = remove_white_background(im, args.threshold)
    if args.remove_corner_watermark:
        rgba = remove_corner_watermark(rgba)
    if args.keep_largest_component:
        rgba = keep_largest_component(rgba)
    if args.tight:
        alpha = np.asarray(rgba)[..., 3]
        ys, xs = np.where(alpha > 0)
        if len(xs) == 0:
            raise SystemExit("no foreground pixels left after background removal")
        result = rgba.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    else:
        result = fit_canvas(rgba, (width, height), args.top_margin, args.bottom_padding)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)
    print(f"saved {args.output} {result.size}")

    if args.preview:
        paper = Image.new("RGBA", result.size, (245, 240, 230, 255))
        paper.alpha_composite(result)
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        paper.convert("RGB").save(args.preview)
        print(f"preview {args.preview}")


if __name__ == "__main__":
    main()
