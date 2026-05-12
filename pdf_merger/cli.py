"""CLI: merge PDFs in order into one output file."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_merger.merge import merge_pdfs


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Merge PDFs in order: all pages from each input, then the next.",
    )
    p.add_argument(
        "pdfs",
        type=Path,
        nargs="+",
        help="Input PDF paths, in the order they should appear",
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
        merge_pdfs(args.pdfs, args.output)
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
