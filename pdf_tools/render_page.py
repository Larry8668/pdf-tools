"""Render PDF pages to image previews for coordinate picking."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pymupdf

logger = logging.getLogger(__name__)


def render_page(
    input_pdf: Path | str,
    page_number: int,
    output_image: Path | str,
    *,
    scale: float = 2.0,
    grid_size: int | None = None,
) -> tuple[float, float, int, int]:
    """Render a 1-based PDF page to an image and return size metadata."""
    source = Path(input_pdf).expanduser().resolve()
    out = Path(output_image).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Input PDF not found: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a PDF: {source}")
    if page_number < 1:
        raise ValueError(f"Page numbers are 1-based; got {page_number}.")
    if scale <= 0:
        raise ValueError("Scale must be greater than 0.")
    if grid_size is not None and grid_size <= 0:
        raise ValueError("Grid size must be greater than 0.")

    with pymupdf.open(str(source)) as doc:
        if doc.is_encrypted:
            raise ValueError(f"Input PDF is encrypted; provide an unlocked copy: {source}")
        if page_number > doc.page_count:
            raise ValueError(
                f"Page {page_number} is outside the PDF's {doc.page_count} pages."
            )

        page = doc[page_number - 1]
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            alpha=False,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        image_width = pixmap.width
        image_height = pixmap.height

        if grid_size is None:
            pixmap.save(str(out))
        else:
            image = Image.frombytes("RGB", (image_width, image_height), pixmap.samples)
            _draw_grid(image, grid_size)
            image.save(out)

        pdf_width = float(page.rect.width)
        pdf_height = float(page.rect.height)

    logger.info("Rendered page %d to %s", page_number, out)
    return pdf_width, pdf_height, image_width, image_height


def _draw_grid(image: Image.Image, grid_size: int) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    major_color = (255, 0, 0, 120)
    minor_color = (0, 0, 255, 65)
    label_color = (255, 0, 0, 230)
    label_bg_color = (255, 255, 255, 180)
    minor_step = max(10, grid_size // 2)
    font = ImageFont.load_default()

    for x in range(0, width + 1, minor_step):
        color = major_color if x % grid_size == 0 else minor_color
        draw.line((x, 0, x, height), fill=color, width=1)

    for y in range(0, height + 1, minor_step):
        color = major_color if y % grid_size == 0 else minor_color
        draw.line((0, y, width, y), fill=color, width=1)

    for x in range(0, width, grid_size):
        _draw_label(draw, (x + 2, 2), str(x), font, label_color, label_bg_color)

    for y in range(grid_size, height, grid_size):
        _draw_label(draw, (2, y + 2), str(y), font, label_color, label_bg_color)


def _draw_label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    color: tuple[int, int, int, int],
    bg_color: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = draw.textbbox(xy, text, font=font)
    draw.rectangle((left - 1, top - 1, right + 1, bottom + 1), fill=bg_color)
    draw.text(xy, text, font=font, fill=color)
