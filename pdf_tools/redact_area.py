"""Redact rectangular areas from PDFs without modifying the original file."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

AreaRedactionMode = str
AREA_REDACTION_MODES = {"black", "white", "remove"}


@dataclass(frozen=True)
class PageArea:
    """A 1-based page number and PDF-point rectangle."""

    page_number: int
    rect: pymupdf.Rect


def redact_areas(
    input_pdf: Path | str,
    areas: list[PageArea],
    output_pdf: Path | str,
    *,
    mode: AreaRedactionMode = "black",
) -> int:
    """Redact PDF-point rectangles and write a new PDF."""
    source = Path(input_pdf).expanduser().resolve()
    out = Path(output_pdf).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Input PDF not found: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a PDF: {source}")
    if out == source:
        raise ValueError("Output PDF path must be different from the input PDF path.")
    if not areas:
        raise ValueError("Provide at least one area to redact.")
    if mode not in AREA_REDACTION_MODES:
        modes = ", ".join(sorted(AREA_REDACTION_MODES))
        raise ValueError(f"Unsupported redaction mode: {mode!r}. Use one of: {modes}")

    fill_color = (1, 1, 1) if mode in {"white", "remove"} else (0, 0, 0)

    with pymupdf.open(str(source)) as doc:
        if doc.is_encrypted:
            raise ValueError(f"Input PDF is encrypted; provide an unlocked copy: {source}")

        for area in areas:
            if area.page_number < 1 or area.page_number > doc.page_count:
                raise ValueError(
                    f"Page {area.page_number} is outside the PDF's {doc.page_count} pages."
                )
            page = doc[area.page_number - 1]
            rect = _validated_rect(area.rect, page.rect, area.page_number)
            page.add_redact_annot(rect, fill=fill_color)

        for page in doc:
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                text=pymupdf.PDF_REDACT_TEXT_REMOVE,
            )

        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))

    logger.info("Wrote area-redacted PDF (%d areas): %s", len(areas), out)
    return len(areas)


def parse_area_expression(expression: str) -> PageArea:
    """Parse ``page:x0,y0,x1,y1`` as PDF-point coordinates."""
    page_text, coords_text = _split_page_and_coords(expression)
    return PageArea(
        page_number=_parse_page_number(page_text),
        rect=_parse_rect(coords_text),
    )


def parse_pixel_rect(page_number: int, coords_text: str, scale: float) -> PageArea:
    """Parse pixel coordinates from a rendered preview into PDF points."""
    if scale <= 0:
        raise ValueError("Scale must be greater than 0.")
    rect = _parse_rect(coords_text)
    return PageArea(
        page_number=page_number,
        rect=pymupdf.Rect(
            rect.x0 / scale,
            rect.y0 / scale,
            rect.x1 / scale,
            rect.y1 / scale,
        ),
    )


def _split_page_and_coords(expression: str) -> tuple[str, str]:
    if ":" not in expression:
        raise ValueError(f"Expected area format page:x0,y0,x1,y1, got: {expression!r}")
    page_text, coords_text = expression.split(":", 1)
    if not page_text.strip() or not coords_text.strip():
        raise ValueError(f"Invalid area expression: {expression!r}")
    return page_text, coords_text


def _parse_page_number(value: str) -> int:
    try:
        page_number = int(value.strip())
    except ValueError as e:
        raise ValueError(f"Invalid page number: {value!r}") from e
    if page_number < 1:
        raise ValueError(f"Page numbers are 1-based; got {page_number}.")
    return page_number


def _parse_rect(coords_text: str) -> pymupdf.Rect:
    raw_coords = [part.strip() for part in coords_text.split(",")]
    if len(raw_coords) != 4:
        raise ValueError(f"Expected four coordinates x0,y0,x1,y1, got: {coords_text!r}")
    try:
        x0, y0, x1, y1 = (float(coord) for coord in raw_coords)
    except ValueError as e:
        raise ValueError(f"Coordinates must be numbers: {coords_text!r}") from e
    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"Coordinates must form a positive rectangle: {coords_text!r}")
    return pymupdf.Rect(x0, y0, x1, y1)


def _validated_rect(
    rect: pymupdf.Rect,
    page_rect: pymupdf.Rect,
    page_number: int,
) -> pymupdf.Rect:
    clipped = rect & page_rect
    if clipped.is_empty:
        raise ValueError(f"Area is outside page {page_number}: {rect}")
    if clipped != rect:
        logger.warning("Clipped area to page %d bounds: %s", page_number, clipped)
    return clipped
