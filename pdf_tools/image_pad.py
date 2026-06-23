"""Pad images to a square canvas without modifying the original file."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from pdf_tools.merge import IMAGE_SUFFIXES

logger = logging.getLogger(__name__)


def pad_image_to_square(
    input_image: Path | str,
    output_image: Path | str,
    *,
    size: int | None = None,
    background: tuple[int, int, int] = (0, 0, 0),
) -> tuple[int, int, int, int]:
    """Pad an image to a square canvas and return old and new sizes."""
    source = Path(input_image).expanduser().resolve()
    out = Path(output_image).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Input image not found: {source}")
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        supported = ", ".join(sorted(IMAGE_SUFFIXES))
        raise ValueError(
            f"Input must be an image. Supported extensions: {supported}"
        )
    if out == source:
        raise ValueError("Output path must be different from the input path.")
    if size is not None and size <= 0:
        raise ValueError("Size must be greater than 0.")

    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            prepared = _prepare_for_paste(image)

            if size is None:
                square_size = max(width, height)
                fitted = prepared
            else:
                square_size = size
                fitted = _fit_inside(prepared, size)

            fitted_width, fitted_height = fitted.size
            offset = (
                (square_size - fitted_width) // 2,
                (square_size - fitted_height) // 2,
            )

            canvas = Image.new("RGB", (square_size, square_size), background)
            canvas.paste(fitted, offset)
            out.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(out)
    except UnidentifiedImageError as e:
        raise ValueError(f"Input image could not be read: {source}") from e

    logger.info(
        "Padded image to square: %dx%d -> %dx%d (%s)",
        width,
        height,
        square_size,
        square_size,
        out,
    )
    return width, height, square_size, square_size


def _fit_inside(image: Image.Image, size: int) -> Image.Image:
    width, height = image.size
    scale = min(size / width, size / height, 1.0)
    if scale == 1.0:
        return image
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def _prepare_for_paste(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", image.size, (0, 0, 0))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image.copy()
