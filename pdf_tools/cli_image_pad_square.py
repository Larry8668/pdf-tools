"""CLI: pad an image to a square canvas."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.image_pad import pad_image_to_square


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pad an image to a square canvas with black borders.",
    )
    p.add_argument("input", type=Path, help="Input image path")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path for the square output image",
    )
    p.add_argument(
        "--size",
        type=int,
        help="Exact square output size in pixels, for example 1024 for 1024x1024.",
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
        width, height, square_width, square_height = pad_image_to_square(
            args.input,
            args.output,
            size=args.size,
        )
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1

    print(f"Padded: {width}x{height} -> {square_width}x{square_height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
