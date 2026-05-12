"""Redact searchable text from PDFs without modifying the original file."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

RedactionMode = str
REDACTION_MODES = {"black", "white", "remove"}


def redact_pdf(
    input_pdf: Path | str,
    terms: Sequence[str],
    output_pdf: Path | str,
    *,
    mode: RedactionMode = "black",
    replacement: str | None = None,
) -> int:
    """Redact matching searchable text terms and write a new PDF.

    Returns the number of matches redacted.
    """
    source = Path(input_pdf).expanduser().resolve()
    out = Path(output_pdf).expanduser().resolve()
    clean_terms = _clean_terms(terms)

    if not source.is_file():
        raise FileNotFoundError(f"Input PDF not found: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a PDF: {source}")
    if out == source:
        raise ValueError("Output PDF path must be different from the input PDF path.")
    if mode not in REDACTION_MODES:
        modes = ", ".join(sorted(REDACTION_MODES))
        raise ValueError(f"Unsupported redaction mode: {mode!r}. Use one of: {modes}")

    fill_color = _fill_color(mode, replacement)
    redacted_rects: list[tuple[int, pymupdf.Rect]] = []

    with pymupdf.open(str(source)) as doc:
        if doc.is_encrypted:
            raise ValueError(f"Input PDF is encrypted; provide an unlocked copy: {source}")

        for page_index, page in enumerate(doc):
            for term in clean_terms:
                rects = page.search_for(term)
                for rect in rects:
                    page.add_redact_annot(rect, fill=fill_color)
                    redacted_rects.append((page_index, rect))

        if not redacted_rects:
            raise ValueError(
                "No matching searchable text was found. "
                "Scanned PDFs may not work without OCR."
            )

        for page in doc:
            page.apply_redactions()

        if replacement:
            for page_index, rect in redacted_rects:
                page = doc[page_index]
                _insert_replacement(page, rect, replacement)

        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))

    logger.info("Wrote redacted PDF (%d matches): %s", len(redacted_rects), out)
    return len(redacted_rects)


def _clean_terms(terms: Sequence[str]) -> list[str]:
    clean_terms = [term.strip() for term in terms if term.strip()]
    if not clean_terms:
        raise ValueError("Provide at least one non-empty term to redact.")
    return clean_terms


def _fill_color(mode: RedactionMode, replacement: str | None) -> tuple[float, float, float]:
    if replacement or mode in {"white", "remove"}:
        return (1, 1, 1)
    return (0, 0, 0)


def _insert_replacement(page: pymupdf.Page, rect: pymupdf.Rect, replacement: str) -> None:
    font_size = max(5, min(10, rect.height * 0.65))
    page.insert_text(
        (rect.x0, rect.y1 - 1),
        replacement,
        fontsize=font_size,
        fontname="helv",
        color=(0, 0, 0),
    )
