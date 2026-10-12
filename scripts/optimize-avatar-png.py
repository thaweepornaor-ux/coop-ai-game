#!/usr/bin/env python3
"""Optimize transparent PNG character parts with a strict 150 KiB output budget.

Usage: python scripts/optimize-avatar-png.py source.png output.png
Requires Pillow. Original assets are not modified.
"""
import argparse
import io
from pathlib import Path
from PIL import Image

MAX_BYTES = 150 * 1024
MAX_DIMENSION = 1024
MIN_DIMENSION = 160
SIZES = (1024, 896, 768, 640, 512, 448, 384, 320, 256, 224, 192, 160)

def _encode(image, indexed_colors=None):
    stream = io.BytesIO()
    if indexed_colors is None:
        image.save(stream, format="PNG", optimize=True, compress_level=9)
        return stream.getvalue(), "RGBA"
    indexed = image.quantize(colors=indexed_colors, method=Image.Quantize.FASTOCTREE,
                             dither=Image.Dither.NONE)
    indexed.save(stream, format="PNG", optimize=True, compress_level=9)
    result = stream.getvalue()
    with Image.open(io.BytesIO(result)) as decoded:
        if decoded.convert("RGBA").getchannel("A").getextrema()[0] == 255:
            raise ValueError("Indexed output lost transparency")
    return result, f"indexed-{indexed_colors}"

def optimize(source: Path, target: Path, limit: int = MAX_BYTES):
    if limit <= 0 or limit > MAX_BYTES:
        raise ValueError("Size limit must be between 1 and 150 KiB")
    if source.resolve() == target.resolve():
        raise ValueError("Input and output must be different files")
    with Image.open(source) as original:
        if original.format != "PNG":
            raise ValueError("Source must be PNG")
        if "A" not in original.getbands() and "transparency" not in original.info:
            raise ValueError("Source must include transparency")
        image = original.convert("RGBA")
        if image.getchannel("A").getextrema()[0] == 255:
            raise ValueError("Source PNG is fully opaque")
        # Choose the largest image that fits, preferring full color at equal size.
        # This avoids the old failure mode: a tiny RGBA image winning over
        # a much clearer 768px indexed image within the same byte budget.
        frames = []
        seen = set()
        for size in SIZES:
            frame = image.copy()
            frame.thumbnail((size, size), Image.Resampling.LANCZOS)
            if frame.size not in seen:
                frames.append(frame)
                seen.add(frame.size)
        for frame in frames:
            if max(frame.size) < MIN_DIMENSION and frame.size != image.size:
                continue
            for colors in (None, 256, 192, 128):
                try:
                    data, mode = _encode(frame, indexed_colors=colors)
                except ValueError:
                    continue
                if len(data) <= limit:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    return frame.size, len(data), mode
    raise ValueError("PNG exceeds budget without excessive quality loss; review source manually")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--max-kib", type=int, default=150)
    args = parser.parse_args()
    if not 1 <= args.max_kib <= 150:
        parser.error("--max-kib must be between 1 and 150")
    dimensions, byte_count, mode = optimize(args.source, args.destination, args.max_kib * 1024)
    print(f"{args.destination}: {dimensions[0]}x{dimensions[1]}, {byte_count/1024:.1f} KiB, {mode}")
