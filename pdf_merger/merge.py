"""Merge PDFs and images in the order provided."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
import logging
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

PDF_SUFFIX = ".pdf"
IMAGE_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def merge_files(input_files: Sequence[Path | str], output_pdf: Path | str) -> None:
    """Write a PDF containing each input PDF/image in order."""
    paths = [Path(input_file).expanduser().resolve() for input_file in input_files]
    out = Path(output_pdf).expanduser().resolve()

    if not paths:
        raise ValueError("Provide at least one input file.")

    for index, path in enumerate(paths, start=1):
        if not path.is_file():
            raise FileNotFoundError(f"Input file {index} not found: {path}")
        if path.suffix.lower() not in {PDF_SUFFIX, *IMAGE_SUFFIXES}:
            supported = ", ".join(sorted({PDF_SUFFIX, *IMAGE_SUFFIXES}))
            raise ValueError(
                f"Input file {index} has unsupported type: {path}. "
                f"Supported extensions: {supported}"
            )

    if out in paths:
        raise ValueError("Output PDF path must be different from every input path.")

    writer = PdfWriter()
    for index, path in enumerate(paths, start=1):
        if path.suffix.lower() == PDF_SUFFIX:
            _append_pdf(writer, path, index)
        else:
            _append_image(writer, path, index)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    logger.info("Wrote merged PDF (%d pages): %s", len(writer.pages), out)


def merge_pdfs(input_pdfs: Sequence[Path | str], output_pdf: Path | str) -> None:
    """Write a new PDF containing all pages from each input PDF, in order."""
    merge_files(input_pdfs, output_pdf)


def merge_two_pdfs(
    first_pdf: Path | str,
    second_pdf: Path | str,
    output_pdf: Path | str,
) -> None:
    """Write a new PDF containing all pages from *first_pdf*, then *second_pdf*."""
    merge_pdfs([first_pdf, second_pdf], output_pdf)


def _append_pdf(writer: PdfWriter, path: Path, index: int) -> None:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ValueError(
            f"Input PDF {index} is encrypted; provide an unlocked copy: {path}"
        )
    writer.append(reader)
    logger.debug("Appended PDF input %d (%d pages): %s", index, len(reader.pages), path)


def _append_image(writer: PdfWriter, path: Path, index: int) -> None:
    try:
        with Image.open(path) as image:
            pdf_buffer = BytesIO()
            _prepare_image_for_pdf(ImageOps.exif_transpose(image)).save(
                pdf_buffer,
                format="PDF",
            )
    except UnidentifiedImageError as e:
        raise ValueError(f"Input image {index} could not be read: {path}") from e

    pdf_buffer.seek(0)
    reader = PdfReader(pdf_buffer)
    writer.append(reader)
    logger.debug("Appended image input %d (1 page): %s", index, path)


def _prepare_image_for_pdf(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        background = Image.new("RGB", image.size, "white")
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image.copy()
