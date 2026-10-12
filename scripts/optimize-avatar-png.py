#!/usr/bin/env python3
"""Prepare a transparent PNG for the game's 150 KiB per-part loading budget.

Usage: python scripts/optimize-avatar-png.py source.png public/avatar-parts/face.png
Requires Pillow: python -m pip install Pillow
"""
import argparse
from pathlib import Path
from PIL import Image

MAX_BYTES = 150 * 1024
MAX_DIMENSION = 1024
SIZES = (768, 640, 512, 448, 384, 320, 256, 224, 192, 160)

def optimize(source: Path, target: Path, limit: int = MAX_BYTES):
    if source.resolve() == target.resolve():
        raise ValueError("Input and output must be different files")
    with Image.open(source) as original:
        if original.format != "PNG":
            raise ValueError("Source must be a PNG file")
        if "A" not in original.getbands() and "transparency" not in original.info:
            raise ValueError("Source must have alpha/transparency")
        image = original.convert("RGBA")
        if not image.getchannel("A").getextrema()[0] < 255:
            raise ValueError("Source is fully opaque; an avatar part needs transparency")
        target.parent.mkdir(parents=True, exist_ok=True)
        for size in SIZES:
            frame = image.copy()
            frame.thumbnail((min(size,MAX_DIMENSION),min(size,MAX_DIMENSION)),Image.Resampling.LANCZOS)
            # Try true RGBA first, before considering indexed transparency.
            import io
            buf = io.BytesIO()
            frame.save(buf,format="PNG",optimize=True,compress_level=9)
            if buf.tell() <= limit:
                target.write_bytes(buf.getvalue())
                return frame.size, buf.tell(), "RGBA"
            for colors in (256,192,128):
                indexed=frame.quantize(colors=colors,method=Image.Quantize.FASTOCTREE,dither=Image.Dither.NONE)
                buf=io.BytesIO()
                indexed.save(buf,format="PNG",optimize=True,compress_level=9)
                if buf.tell() <= limit:
                    # Check alpha before accepting a paletted candidate.
                    check=Image.open(io.BytesIO(buf.getvalue())).convert("RGBA")
                    if check.getchannel("A").getextrema()[0] == 255:
                        continue
                    target.write_bytes(buf.getvalue())
                    return frame.size,buf.tell(),f"indexed-{colors}"
    raise ValueError("Cannot fit within budget without downsizing below 160px; review asset manually")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("destination",type=Path)
    parser.add_argument("--max-kib",type=int,default=150)
    args=parser.parse_args()
    if args.max_kib<=0 or args.max_kib>150:
        parser.error("max-kib must be between 1 and 150")
    dimensions,bytes_written,mode=optimize(args.source,args.destination,args.max_kib*1024)
    print(f"{args.destination}: {dimensions[0]}x{dimensions[1]}, {bytes_written/1024:.1f} KiB, {mode}")
