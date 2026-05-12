"""Merge PDF files in the order provided."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from pathlib import Path

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def merge_pdfs(input_pdfs: Sequence[Path | str], output_pdf: Path | str) -> None:
    """Write a new PDF containing all pages from each input PDF, in order."""
    paths = [Path(pdf).expanduser().resolve() for pdf in input_pdfs]
    out = Path(output_pdf).expanduser().resolve()

    if len(paths) < 2:
        raise ValueError("Provide at least two PDFs to merge.")

    for index, path in enumerate(paths, start=1):
        if not path.is_file():
            raise FileNotFoundError(f"Input PDF {index} not found: {path}")

    if out in paths:
        raise ValueError("Output PDF path must be different from every input PDF path.")

    writer = PdfWriter()
    for index, path in enumerate(paths, start=1):
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ValueError(
                f"Input PDF {index} is encrypted; provide an unlocked copy: {path}"
            )
        writer.append(reader)
        logger.debug("Appended input %d (%d pages): %s", index, len(reader.pages), path)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    logger.info("Wrote merged PDF (%d pages): %s", len(writer.pages), out)


def merge_two_pdfs(
    first_pdf: Path | str,
    second_pdf: Path | str,
    output_pdf: Path | str,
) -> None:
    """Write a new PDF containing all pages from *first_pdf*, then *second_pdf*."""
    merge_pdfs([first_pdf, second_pdf], output_pdf)
