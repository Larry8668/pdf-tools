"""CLI: compress an image into a new smaller output image."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.compress_image import compress_image
from pdf_tools.formatting import format_bytes


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compress an image and write a new smaller image.",
    )
    p.add_argument("input", type=Path, help="Input image path")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path for the compressed image",
    )
    p.add_argument(
        "--quality",
        type=int,
        help="JPEG/WebP quality from 1 (smallest) to 95 (largest). Default: 75.",
    )
    p.add_argument(
        "--max-width",
        type=int,
        help="Scale down so width is at most this many pixels.",
    )
    p.add_argument(
        "--max-height",
        type=int,
        help="Scale down so height is at most this many pixels.",
    )
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
        input_bytes, output_bytes = compress_image(
            args.input,
            args.output,
            quality=args.quality,
            max_width=args.max_width,
            max_height=args.max_height,
        )
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1

    print(
        f"Compressed: {format_bytes(input_bytes)} -> {format_bytes(output_bytes)} "
        f"({output_bytes / input_bytes * 100:.1f}% of original)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
