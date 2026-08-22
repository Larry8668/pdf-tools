"""Compress images without modifying the original file."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from pdf_tools.formatting import format_bytes
from pdf_tools.merge import IMAGE_SUFFIXES

logger = logging.getLogger(__name__)

_LOSSY_SUFFIXES = {".jpg", ".jpeg", ".webp"}
_DEFAULT_QUALITY = 75


def compress_image(
    input_image: Path | str,
    output_image: Path | str,
    *,
    quality: int | None = None,
    max_height: int | None = None,
    max_width: int | None = None,
) -> tuple[int, int]:
    """Write a compressed image copy.

    Returns ``(input_bytes, output_bytes)``.
    """
    source = Path(input_image).expanduser().resolve()
    out = Path(output_image).expanduser().resolve()
    out_suffix = out.suffix.lower()

    if not source.is_file():
        raise FileNotFoundError(f"Input image not found: {source}")
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        supported = ", ".join(sorted(IMAGE_SUFFIXES))
        raise ValueError(f"Input must be an image. Supported extensions: {supported}")
    if out_suffix not in IMAGE_SUFFIXES:
        supported = ", ".join(sorted(IMAGE_SUFFIXES))
        raise ValueError(f"Output must be an image. Supported extensions: {supported}")
    if out == source:
        raise ValueError("Output path must be different from the input path.")
    if quality is not None and not 1 <= quality <= 95:
        raise ValueError("Quality must be between 1 and 95.")
    if max_height is not None and max_height <= 0:
        raise ValueError("Max height must be greater than 0.")
    if max_width is not None and max_width <= 0:
        raise ValueError("Max width must be greater than 0.")

    save_quality = quality if quality is not None else _DEFAULT_QUALITY
    input_bytes = source.stat().st_size

    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            resized = _fit_within(image, max_width=max_width, max_height=max_height)
            out.parent.mkdir(parents=True, exist_ok=True)
            _save_image(resized, out, save_quality)
    except UnidentifiedImageError as e:
        raise ValueError(f"Input image could not be read: {source}") from e

    output_bytes = out.stat().st_size
    logger.info(
        "Compressed image: %s -> %s (%.1f%% of original)",
        format_bytes(input_bytes),
        format_bytes(output_bytes),
        (output_bytes / input_bytes) * 100 if input_bytes else 0,
    )
    return input_bytes, output_bytes


def _fit_within(
    image: Image.Image,
    *,
    max_width: int | None,
    max_height: int | None,
) -> Image.Image:
    width, height = image.size
    scale = 1.0
    if max_width is not None:
        scale = min(scale, max_width / width)
    if max_height is not None:
        scale = min(scale, max_height / height)
    if scale >= 1.0:
        return image
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    logger.info("Resizing image %dx%d -> %dx%d", width, height, new_width, new_height)
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def _save_image(image: Image.Image, output: Path, quality: int) -> None:
    suffix = output.suffix.lower()
    save_kwargs: dict[str, object] = {}

    if suffix in _LOSSY_SUFFIXES:
        to_save = _flatten_to_rgb(image)
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
        if suffix == ".webp":
            save_kwargs["method"] = 4
        else:
            save_kwargs["progressive"] = True
    elif suffix == ".png":
        to_save = image
        save_kwargs["optimize"] = True
        save_kwargs["compress_level"] = 9
    else:
        to_save = image

    to_save.save(output, **save_kwargs)


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image
