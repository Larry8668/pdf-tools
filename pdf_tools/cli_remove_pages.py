"""CLI: remove selected pages from a PDF into a new output PDF."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.remove_pages import remove_pages


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Remove selected pages from a PDF and write a new PDF.",
    )
    p.add_argument("input", type=Path, help="Input PDF path")
    p.add_argument(
        "--pages",
        required=True,
        help='1-based page numbers/ranges to remove, for example "1,3,5-7"',
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path for the new PDF",
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
        remove_pages(args.input, args.pages, args.output)
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
