"""CLI: merge PDFs and images in order into one output PDF."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_merger.merge import merge_files


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Merge or convert PDFs and images into one output PDF.",
    )
    p.add_argument(
        "inputs",
        type=Path,
        nargs="+",
        help="Input PDF/image paths, in the order they should appear",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path for the merged PDF",
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
        merge_files(args.inputs, args.output)
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
