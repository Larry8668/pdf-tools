"""CLI: render one PDF page to an image preview."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.render_page import render_page


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Render one PDF page to an image preview for coordinate picking.",
    )
    p.add_argument("input", type=Path, help="Input PDF path")
    p.add_argument("--page", type=int, required=True, help="1-based page number")
    p.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="Render scale. 2.0 means PDF points are doubled into image pixels.",
    )
    p.add_argument(
        "--grid-size",
        type=int,
        help="Draw a labeled pixel grid every N pixels, with lighter half-step lines.",
    )
    p.add_argument("-o", "--output", type=Path, required=True, help="Output image path")
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log debug messages",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        pdf_width, pdf_height, image_width, image_height = render_page(
            args.input,
            args.page,
            args.output,
            scale=args.scale,
            grid_size=args.grid_size,
        )
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1

    print(f"Rendered page {args.page}: {args.output}")
    print(f"PDF size: {pdf_width:g} x {pdf_height:g} points")
    print(f"Image size: {image_width} x {image_height} pixels")
    print(f"Scale: {args.scale:g}")
    if args.grid_size:
        print(f"Grid size: {args.grid_size} pixels")
    print(
        "Use pixel coordinates from this image with "
        f"`uv run pdf-redact-area {args.input} --page {args.page} --pixels "
        '"x0,y0,x1,y1" --scale '
        f"{args.scale:g} -o pdfs/output.pdf`"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
