"""CLI: compress a PDF into a new smaller output PDF."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.compress import _format_bytes, compress_pdf


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compress a PDF and write a new smaller PDF.",
    )
    p.add_argument("input", type=Path, help="Input PDF path")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path for the compressed PDF",
    )
    size_group = p.add_mutually_exclusive_group(required=True)
    size_group.add_argument(
        "--size-percent",
        type=float,
        help="Target output size as a percent of the input file size, for example 10 for ~100 KB from 1 MB.",
    )
    size_group.add_argument(
        "--image-quality",
        type=int,
        help="JPEG image quality from 1 (smallest) to 100 (largest).",
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
        input_bytes, output_bytes = compress_pdf(
            args.input,
            args.output,
            size_percent=args.size_percent,
            image_quality=args.image_quality,
        )
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1

    print(
        f"Compressed: {_format_bytes(input_bytes)} -> {_format_bytes(output_bytes)} "
        f"({output_bytes / input_bytes * 100:.1f}% of original)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
