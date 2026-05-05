"""Merge two PDF files: first file's pages, then second file's pages."""

from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def merge_two_pdfs(
    first_pdf: Path | str,
    second_pdf: Path | str,
    output_pdf: Path | str,
) -> None:
    """Write a new PDF containing all pages from *first_pdf*, then *second_pdf*."""
    first = Path(first_pdf).expanduser().resolve()
    second = Path(second_pdf).expanduser().resolve()
    out = Path(output_pdf).expanduser().resolve()

    if not first.is_file():
        raise FileNotFoundError(f"First PDF not found: {first}")
    if not second.is_file():
        raise FileNotFoundError(f"Second PDF not found: {second}")

    writer = PdfWriter()
    for label, path in (("first", first), ("second", second)):
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ValueError(
                f"{label} PDF is encrypted; provide an unlocked copy or extend the tool with a password option."
            )
        writer.append(reader)
        logger.debug("Appended %s (%d pages): %s", label, len(reader.pages), path)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    logger.info("Wrote merged PDF (%d pages): %s", len(writer.pages), out)
