"""PDF tools: merge, remove-pages, compress, redact, render-page, redact-area."""

from __future__ import annotations

import pymupdf
import pytest
from PIL import Image

from conftest import page_count, page_text, sha256
from pdf_tools import (
    compress_pdf,
    merge_files,
    parse_page_ranges,
    redact_areas,
    redact_pdf,
    remove_pages,
    render_page,
)
from pdf_tools.redact_area import parse_area_expression, parse_pixel_rect


# merge

def test_merge_keeps_input_order_and_inputs(make_pdf, make_image, tmp_path):
    a = make_pdf("a.pdf", ("A1", "A2"))
    img = make_image("photo.png")
    b = make_pdf("b.pdf", ("B1",))
    before = {p: sha256(p) for p in (a, img, b)}

    out = tmp_path / "nested" / "merged.pdf"
    merge_files([a, img, b], out)

    assert page_count(out) == 4
    with pymupdf.open(out) as doc:
        texts = [page.get_text().strip() for page in doc]
    assert texts[0] == "A1" and texts[1] == "A2" and texts[3] == "B1"
    assert texts[2] == ""  # the image page
    assert {p: sha256(p) for p in before} == before


def test_merge_single_image_to_pdf(make_image, tmp_path):
    out = tmp_path / "photo.pdf"
    merge_files([make_image()], out)
    assert page_count(out) == 1


def test_merge_rejects_output_equal_to_input(make_pdf, tmp_path):
    a = make_pdf("a.pdf")
    with pytest.raises(ValueError, match="different"):
        merge_files([a], tmp_path / "." / "a.pdf")


def test_merge_rejects_missing_and_unsupported(make_pdf, tmp_path):
    with pytest.raises(FileNotFoundError):
        merge_files([tmp_path / "nope.pdf"], tmp_path / "out.pdf")
    txt = tmp_path / "notes.txt"
    txt.write_text("hi")
    with pytest.raises(ValueError, match="unsupported"):
        merge_files([txt], tmp_path / "out.pdf")


# remove-pages

@pytest.mark.parametrize("expr, count, expected", [
    ("1", 5, {1}),
    ("1,3,5-7", 10, {1, 3, 5, 6, 7}),
    (" 2 - 3 , 2 ", 5, {2, 3}),
])
def test_parse_page_ranges(expr, count, expected):
    assert parse_page_ranges(expr, count) == expected


@pytest.mark.parametrize("expr", ["", "0", "3-1", "a", "1,,2", "9"])
def test_parse_page_ranges_rejects(expr):
    with pytest.raises(ValueError):
        parse_page_ranges(expr, 5)


def test_remove_pages(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", ("P1", "P2", "P3", "P4"))
    out = tmp_path / "trim.pdf"
    remove_pages(src, "2,4", out)
    assert page_text(out).split() == ["P1", "P3"]
    assert page_count(src) == 4


def test_remove_every_page_is_refused(make_pdf, tmp_path):
    with pytest.raises(ValueError, match="every page"):
        remove_pages(make_pdf("doc.pdf", ("P1", "P2")), "1-2", tmp_path / "out.pdf")


# compress

def test_compress_shrinks_image_heavy_pdf(make_pdf, noisy_image, tmp_path):
    src = make_pdf("big.pdf", ("x",), image=noisy_image.resize((1600, 1000)))
    out = tmp_path / "small.pdf"
    before, after = compress_pdf(src, out, image_quality=20)
    assert after < before
    assert page_count(out) == 1


@pytest.mark.parametrize("kwargs", [{}, {"size_percent": 0}, {"size_percent": 150},
                                    {"image_quality": 0}])
def test_compress_rejects_bad_options(make_pdf, tmp_path, kwargs):
    with pytest.raises(ValueError):
        compress_pdf(make_pdf(), tmp_path / "out.pdf", **kwargs)


# redact

def test_redact_removes_text(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", ("Account 12345 Jane Doe",))
    out = tmp_path / "red.pdf"
    assert redact_pdf(src, ["12345", "Jane Doe"], out) >= 2
    text = page_text(out)
    assert "12345" not in text and "Jane" not in text
    assert "Account" in text
    assert "12345" in page_text(src)


def test_redact_with_no_match_fails(make_pdf, tmp_path):
    with pytest.raises(ValueError, match="No matching"):
        redact_pdf(make_pdf(), ["absent"], tmp_path / "out.pdf")


# render-page and redact-area

def test_render_page_size_and_grid(make_pdf, tmp_path):
    src = make_pdf()
    out = tmp_path / "p.png"
    width_pt, height_pt, width_px, height_px = render_page(src, 1, out, scale=2, grid_size=50)
    assert (width_pt, height_pt) == (400, 300)
    assert Image.open(out).size == (width_px, height_px) == (800, 600)


def test_render_page_out_of_range(make_pdf, tmp_path):
    with pytest.raises(ValueError):
        render_page(make_pdf(), 3, tmp_path / "p.png")


def test_area_parsing():
    area = parse_area_expression("2:10,20,110,70")
    assert area.page_number == 2 and tuple(area.rect) == (10, 20, 110, 70)
    pixel = parse_pixel_rect(1, "20,40,220,140", scale=2)
    assert tuple(pixel.rect) == (10, 20, 110, 70)
    for bad in ("10,20,30,40", "0:1,2,3,4", "1:5,5,1,1", "1:a,b,c,d"):
        with pytest.raises(ValueError):
            parse_area_expression(bad)


def test_redact_area_removes_text_under_box(make_pdf, tmp_path):
    src = make_pdf("doc.pdf", ("Secret",))
    out = tmp_path / "red.pdf"
    redact_areas(src, [parse_area_expression("1:30,40,200,70")], out)
    assert "Secret" not in page_text(out)


def test_redact_area_outside_page(make_pdf, tmp_path):
    with pytest.raises(ValueError, match="outside"):
        redact_areas(make_pdf(), [parse_area_expression("1:1000,1000,1100,1100")],
                     tmp_path / "out.pdf")
