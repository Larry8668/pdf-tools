"""Shared fixtures: small PDFs and images built on the fly, so tests need no files."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
import pytest
from PIL import Image


@pytest.fixture
def make_pdf(tmp_path: Path):
    """Write a PDF with one page per text, and return its path."""

    def make(name: str = "doc.pdf", texts: tuple[str, ...] = ("Page 1",), *,
             image: Image.Image | None = None) -> Path:
        path = tmp_path / name
        doc = pymupdf.open()
        for text in texts:
            page = doc.new_page(width=400, height=300)
            page.insert_text((40, 60), text, fontsize=14)
            if image is not None:
                png = tmp_path / "_embed.png"
                image.save(png)
                page.insert_image(pymupdf.Rect(40, 80, 360, 280), filename=str(png))
        doc.save(path)
        doc.close()
        return path

    return make


@pytest.fixture
def make_image(tmp_path: Path):
    """Write a solid-colour image and return its path."""

    def make(name: str = "img.png", size: tuple[int, int] = (400, 300),
             color: str | tuple = "red", mode: str = "RGB") -> Path:
        path = tmp_path / name
        Image.new(mode, size, color).save(path)
        return path

    return make


@pytest.fixture
def noisy_image() -> Image.Image:
    """A photo-like image that compresses poorly, so size reductions are visible."""
    return Image.effect_noise((600, 400), 64).convert("RGB")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def page_count(path: Path) -> int:
    with pymupdf.open(path) as doc:
        return doc.page_count


def page_text(path: Path) -> str:
    with pymupdf.open(path) as doc:
        return "".join(page.get_text() for page in doc)
