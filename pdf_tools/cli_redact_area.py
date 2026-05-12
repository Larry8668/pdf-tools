"""CLI: redact rectangular PDF areas into a new output PDF."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.redact_area import (
    AREA_REDACTION_MODES,
    PageArea,
    parse_area_expression,
    parse_pixel_rect,
    redact_areas,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Redact rectangular areas from a PDF and write a new PDF.",
    )
    p.add_argument("input", type=Path, help="Input PDF path")
    p.add_argument(
        "--area",
        action="append",
        default=[],
        help="PDF-point area as page:x0,y0,x1,y1. Repeatable.",
    )
    p.add_argument(
        "--page",
        type=int,
        help="1-based page number for --pixels coordinates.",
    )
    p.add_argument(
        "--pixels",
        action="append",
        default=[],
        help="Pixel rectangle x0,y0,x1,y1 from a pdf-render-page preview. Repeatable.",
    )
    p.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="Render scale used for --pixels. Match the value from pdf-render-page.",
    )
    p.add_argument(
        "--mode",
        choices=sorted(AREA_REDACTION_MODES),
        default="black",
        help="Redaction fill style. 'remove' leaves a blank white area.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path for the new redacted PDF",
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
        redact_areas(
            args.input,
            _collect_areas(args.area, args.page, args.pixels, args.scale),
            args.output,
            mode=args.mode,
        )
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1
    return 0


def _collect_areas(
    area_expressions: list[str],
    page_number: int | None,
    pixel_rects: list[str],
    scale: float,
) -> list[PageArea]:
    areas = [parse_area_expression(expression) for expression in area_expressions]

    if pixel_rects:
        if page_number is None:
            raise ValueError("--page is required when using --pixels.")
        if page_number < 1:
            raise ValueError(f"Page numbers are 1-based; got {page_number}.")
        areas.extend(parse_pixel_rect(page_number, coords, scale) for coords in pixel_rects)

    if not areas:
        raise ValueError("Provide at least one --area or --pixels rectangle.")
    return areas


if __name__ == "__main__":
    sys.exit(main())
