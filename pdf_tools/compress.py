"""Compress PDFs without modifying the original file."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

_MIN_IMAGE_QUALITY = 5
_MAX_IMAGE_QUALITY = 95


def compress_pdf(
    input_pdf: Path | str,
    output_pdf: Path | str,
    *,
    size_percent: float | None = None,
    image_quality: int | None = None,
) -> tuple[int, int]:
    """Write a compressed PDF copy.

    Returns ``(input_bytes, output_bytes)``.
    """
    source = Path(input_pdf).expanduser().resolve()
    out = Path(output_pdf).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Input PDF not found: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a PDF: {source}")
    if out == source:
        raise ValueError("Output PDF path must be different from the input PDF path.")
    if size_percent is None and image_quality is None:
        raise ValueError("Provide --size-percent or --image-quality.")
    if size_percent is not None and not 0 < size_percent <= 100:
        raise ValueError("Size percent must be between 0 and 100.")
    if image_quality is not None and not 1 <= image_quality <= 100:
        raise ValueError("Image quality must be between 1 and 100.")

    input_bytes = source.stat().st_size
    if size_percent is not None:
        target_bytes = int(input_bytes * size_percent / 100)
        quality = _find_image_quality(source, target_bytes)
        logger.info("Using image quality %d for ~%g%% target size", quality, size_percent)
    else:
        quality = image_quality
        assert quality is not None

    _write_compressed_pdf(source, out, quality)
    output_bytes = out.stat().st_size
    logger.info(
        "Compressed PDF: %s -> %s (%.1f%% of original)",
        _format_bytes(input_bytes),
        _format_bytes(output_bytes),
        (output_bytes / input_bytes) * 100 if input_bytes else 0,
    )
    return input_bytes, output_bytes


def _find_image_quality(source: Path, target_bytes: int) -> int:
    low = _MIN_IMAGE_QUALITY
    high = _MAX_IMAGE_QUALITY
    best_quality = low
    best_size = source.stat().st_size

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        probe = tmp_path / "probe.pdf"

        while low <= high:
            mid = (low + high) // 2
            size = _write_compressed_pdf(source, probe, mid)
            if size <= target_bytes:
                best_quality = mid
                best_size = size
                low = mid + 1
            else:
                high = mid - 1

        if best_size > target_bytes:
            logger.warning(
                "Could not reach target size %s; best effort is %s at quality %d",
                _format_bytes(target_bytes),
                _format_bytes(best_size),
                best_quality,
            )

    return best_quality


def _write_compressed_pdf(source: Path, output: Path, image_quality: int) -> int:
    with pymupdf.open(str(source)) as doc:
        if doc.is_encrypted:
            raise ValueError(f"Input PDF is encrypted; provide an unlocked copy: {source}")

        doc.rewrite_images(quality=image_quality, lossy=True, lossless=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        doc.save(
            str(output),
            garbage=4,
            deflate=True,
            clean=True,
        )
    return output.stat().st_size


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"
