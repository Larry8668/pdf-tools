"""Remove selected pages from a PDF without modifying the original file."""

from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def remove_pages(
    input_pdf: Path | str,
    page_ranges: str,
    output_pdf: Path | str,
) -> None:
    """Write a copy of *input_pdf* without pages listed in *page_ranges*."""
    source = Path(input_pdf).expanduser().resolve()
    out = Path(output_pdf).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Input PDF not found: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a PDF: {source}")
    if out == source:
        raise ValueError("Output PDF path must be different from the input PDF path.")

    reader = PdfReader(str(source))
    if reader.is_encrypted:
        raise ValueError(f"Input PDF is encrypted; provide an unlocked copy: {source}")

    page_count = len(reader.pages)
    pages_to_remove = parse_page_ranges(page_ranges, page_count)
    if len(pages_to_remove) == page_count:
        raise ValueError("Cannot remove every page; output PDF would be empty.")

    writer = PdfWriter()
    for page_number, page in enumerate(reader.pages, start=1):
        if page_number not in pages_to_remove:
            writer.add_page(page)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    logger.info(
        "Wrote PDF (%d pages, removed %d): %s",
        len(writer.pages),
        len(pages_to_remove),
        out,
    )


def parse_page_ranges(page_ranges: str, page_count: int | None = None) -> set[int]:
    """Parse 1-based page ranges like ``1,3,5-7`` into page numbers."""
    if not page_ranges.strip():
        raise ValueError("Provide at least one page number or range.")

    pages: set[int] = set()
    for raw_token in page_ranges.split(","):
        token = raw_token.strip()
        if not token:
            raise ValueError(f"Invalid page range expression: {page_ranges!r}")

        if "-" in token:
            start_text, end_text = _split_range(token)
            start = _parse_positive_page_number(start_text)
            end = _parse_positive_page_number(end_text)
            if start > end:
                raise ValueError(f"Invalid descending page range: {token!r}")
            pages.update(range(start, end + 1))
        else:
            pages.add(_parse_positive_page_number(token))

    if page_count is not None:
        out_of_bounds = [page for page in sorted(pages) if page > page_count]
        if out_of_bounds:
            raise ValueError(
                f"Page {out_of_bounds[0]} is outside the PDF's {page_count} pages."
            )

    return pages


def _split_range(token: str) -> tuple[str, str]:
    parts = token.split("-")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(f"Invalid page range: {token!r}")
    return parts[0], parts[1]


def _parse_positive_page_number(value: str) -> int:
    try:
        page_number = int(value.strip())
    except ValueError as e:
        raise ValueError(f"Invalid page number: {value!r}") from e

    if page_number < 1:
        raise ValueError(f"Page numbers are 1-based; got {page_number}.")
    return page_number
