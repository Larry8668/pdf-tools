"""edit-text: replacing text in place.

The PDFs are built here from MuPDF's own fonts, so the tests run anywhere.
Subsetting a document after writing text leaves an embedded font that only
has the letters used, like most real PDFs, which exercises the fallback path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import warnings

import numpy as np
import pymupdf
import pypdf
import pytest

from conftest import sha256
from pdf_tools.edit_text import _cff_kind, edit_text

PDF_TOOLS = Path(sys.executable).parent / "pdf-tools"


def make(path: Path, lines, *, embed: str | None = None, subset: bool = False,
         width: float = 420, height: float = 200, rotate: int = 0) -> Path:
    """Write ``lines`` of ``(x, y, text, size, options)`` to a one-page PDF.

    With ``embed`` (a built-in font alias such as "tiro"), the text uses an
    embedded copy of that font; ``subset`` then trims it to the letters used.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    fontname = "helv"
    if embed:
        page.insert_font(fontname="EMB", fontbuffer=pymupdf.Font(embed).buffer)
        fontname = "EMB"
    for x, y, text, size, *opts in lines:
        kw = {"fontname": fontname, "fontsize": size, **(opts[0] if opts else {})}
        page.insert_text((x, y), text, **kw)
    if subset:
        doc.subset_fonts()
    if rotate:
        page.set_rotation(rotate)
    doc.save(path)
    return path


def text(path: Path, page: int = 0) -> str:
    # In on-page order: redrawn lines are appended to the page, so the raw
    # extraction order puts them last.
    with pymupdf.open(path) as doc:
        return " ".join(doc[page].get_text(sort=True).split())


def pixels(path: Path) -> np.ndarray:
    with pymupdf.open(path) as doc:
        pix = doc[0].get_pixmap(dpi=72)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n).astype(int)


def changed_rows(before: Path, after: Path) -> set[int]:
    diff = np.abs(pixels(before) - pixels(after)).max(axis=2) > 40
    return set(np.nonzero(diff.any(axis=1))[0].tolist())


def assert_valid(path: Path) -> None:
    """A second, strict PDF reader opens it without complaint, and every
    simple font with a CFF program labels it /Type1C as the spec requires."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for page in pypdf.PdfReader(path, strict=True).pages:
            page.extract_text()
    with pymupdf.open(path) as doc:
        for xref in range(1, doc.xref_length()):
            if doc.xref_get_key(xref, "Subtype")[1] not in ("/Type1", "/TrueType"):
                continue
            descriptor = doc.xref_get_key(xref, "FontDescriptor")
            if descriptor[0] != "xref":
                continue
            program = doc.xref_get_key(int(descriptor[1].split()[0]), "FontFile3")
            if program[0] == "xref":
                assert doc.xref_get_key(int(program[1].split()[0]), "Subtype")[1] == "/Type1C"


def line_extent(path: Path, needle: str) -> pymupdf.Rect:
    with pymupdf.open(path) as doc:
        for block in doc[0].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                if needle in "".join(s["text"] for s in line["spans"]):
                    return pymupdf.Rect(line["bbox"])
    raise AssertionError(f"{needle!r} not on page")


# the main path

def test_replaces_and_moves_rest_of_line(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Dear Jon Smith, welcome aboard.", 14),
                                    (30, 120, "Unrelated line stays put.", 14)])
    before = sha256(src)
    out = tmp_path / "out.pdf"
    report = edit_text(src, out, [("Jon Smith", "Jonathan Smith")])

    assert [(e.old, e.new) for e in report.edits] == [("Jon Smith", "Jonathan Smith")]
    assert report.edits[0].fit == "shifted"
    assert text(out) == "Dear Jonathan Smith, welcome aboard. Unrelated line stays put."
    assert sha256(src) == before
    # Only the edited line's pixels changed.
    assert all(40 <= row <= 66 for row in changed_rows(src, out))


def test_reuses_embedded_font_when_it_has_the_letters(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Issued to Jon Smith and Jonas.", 14)],
               embed="tiro", subset=True)
    report = edit_text(src, tmp_path / "o.pdf", [("Jon Smith", "Jonas Smith")])
    assert report.edits[0].fallback_reason is None
    assert text(tmp_path / "o.pdf") == "Issued to Jonas Smith and Jonas."


def test_falls_back_when_subset_lacks_a_letter(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Issued to Jon Smith.", 14)],
               embed="tiro", subset=True)
    report = edit_text(src, tmp_path / "o.pdf", [("Jon", "Zoë")])
    edit = report.edits[0]
    assert edit.font == "Times-Roman"  # same family as the embedded Nimbus Roman
    assert "'Z'" in edit.fallback_reason and "'ë'" in edit.fallback_reason
    assert text(tmp_path / "o.pdf") == "Issued to Zoë Smith."


def test_font_without_space_glyph_keeps_word_gap(tmp_path):
    # Words drawn one by one, as LaTeX does, so the subset has no space glyph.
    words = [(30, "Authors:"), (95, "Noam"), (140, "Shazeer"), (205, "et"), (222, "al.")]
    src = make(tmp_path / "a.pdf", [(x, 60, w, 14) for x, w in words], embed="tibo", subset=True)
    out = tmp_path / "o.pdf"
    edit_text(src, out, [("Noam Shazeer", "Noam Shazir")])
    with pymupdf.open(out) as doc:
        found = doc[0].search_for("Noam Shazir")
    assert found, text(out)
    assert "NoamShazir" not in text(out)


def test_centred_line_is_recentred(tmp_path):
    page_w = 420
    title = "Certificate for Jon Smith"
    width = pymupdf.get_text_length(title, "helv", 18)
    src = make(tmp_path / "a.pdf", [((page_w - width) / 2, 80, title, 18)], width=page_w)
    out = tmp_path / "o.pdf"
    report = edit_text(src, out, [("Jon Smith", "Jonathan Smithson")])
    assert report.edits[0].fit == "centred"
    line = line_extent(out, "Jonathan")
    assert abs((line.x0 + line.x1) / 2 - page_w / 2) < 1.5


def test_full_width_line_shrinks_the_new_text(tmp_path):
    line = "Applicant Jon Smith confirms every detail written on this page."
    size = 12
    width = pymupdf.get_text_length(line, "helv", size)
    src = make(tmp_path / "a.pdf", [(20, 60, line, size)], width=width + 40)
    report = edit_text(src, tmp_path / "o.pdf", [("Jon Smith", "Jon Smiths")])
    assert report.edits[0].fit == "shrunk"
    assert line_extent(tmp_path / "o.pdf", "Smiths").x1 <= width + 20 + 1


def test_far_too_long_reports_overflow(tmp_path):
    line = "Applicant Jon Smith confirms every detail written on this page."
    width = pymupdf.get_text_length(line, "helv", 12)
    src = make(tmp_path / "a.pdf", [(20, 60, line, 12)], width=width + 40)
    report = edit_text(src, tmp_path / "o.pdf", [("Jon Smith", "Jonathan Smithsonian")])
    assert report.edits[0].fit == "overflow"


def test_several_matches_and_ignore_case(tmp_path):
    src = make(tmp_path / "a.pdf", [(20, 60, "jon met JON, and Jon left.", 13)])
    report = edit_text(src, tmp_path / "o.pdf", [("Jon", "Joe")], ignore_case=True)
    assert len(report.edits) == 3
    assert text(tmp_path / "o.pdf") == "Joe met Joe, and Joe left."


def test_several_pairs(tmp_path):
    src = make(tmp_path / "a.pdf", [(20, 60, "Jon Smith, 12 May 2025", 13)])
    edit_text(src, tmp_path / "o.pdf", [("Jon", "John"), ("2025", "2026")])
    assert text(tmp_path / "o.pdf") == "John Smith, 12 May 2026"


def test_delete_word_with_its_space(tmp_path):
    src = make(tmp_path / "a.pdf", [(20, 60, "Hello very cruel world", 13)])
    edit_text(src, tmp_path / "o.pdf", [("cruel ", "")])
    assert text(tmp_path / "o.pdf") == "Hello very world"


def test_keeps_superscript_position(tmp_path):
    src = make(tmp_path / "a.pdf", [(20, 60, "Noam Shazeer", 13), (105, 54, "*", 8)])
    out = tmp_path / "o.pdf"
    edit_text(src, out, [("Noam Shazeer", "Noam Shazir")])
    with pymupdf.open(out) as doc:
        star = [s for b in doc[0].get_text("dict")["blocks"] for l in b.get("lines", [])
                for s in l["spans"] if s["text"].strip() == "*"]
    assert star and abs(star[0]["origin"][1] - 54) < 0.5


def test_mixed_bold_and_regular_in_one_match(tmp_path):
    path = tmp_path / "a.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=120)
    writer = pymupdf.TextWriter(page.rect)
    x = 20
    for chunk, alias in (("Name: ", "helv"), ("Jon", "hebo"), (" Smith (applicant)", "helv")):
        font = pymupdf.Font(alias)
        writer.append((x, 60), chunk, font=font, fontsize=13)
        x += font.text_length(chunk, fontsize=13)
    writer.write_text(page)
    doc.save(path)

    report = edit_text(path, tmp_path / "o.pdf", [("Jon Smith", "John Smith")])
    assert report.edits[0].fallback_reason is None
    assert text(tmp_path / "o.pdf") == "Name: John Smith (applicant)"
    # The bold font is reused from its CFF program: it must stay well formed.
    assert_valid(tmp_path / "o.pdf")


def test_cff_kind():
    def cff(top_dict: bytes) -> bytes:
        name = b"\x00\x01\x01\x01\x02A"  # Name INDEX holding "A"
        top = b"\x00\x01\x01\x01" + bytes([len(top_dict) + 1]) + top_dict
        return b"\x01\x00\x04\x01" + name + top

    assert _cff_kind(cff(b"\x8b\x00")) == "bare"  # version 0
    assert _cff_kind(cff(b"\xf8\x1b\xf8\x1c\x8b\x0c\x1e")) == "cid"  # ROS 391 392 0
    assert _cff_kind(pymupdf.Font("helv").buffer) == "bare"
    assert _cff_kind(b"\x00\x01\x00\x00 TrueType") is None


def test_text_over_image_keeps_the_image(tmp_path):
    from PIL import Image
    src = tmp_path / "a.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=120)
    png = tmp_path / "g.png"
    Image.linear_gradient("L").resize((300, 120)).convert("RGB").save(png)
    page.insert_image(page.rect, filename=str(png))
    page.insert_text((20, 70), "By Jon Smith", fontname="tibo", fontsize=16, color=(1, 1, 1))
    doc.save(src)

    out = tmp_path / "o.pdf"
    edit_text(src, out, [("Jon", "Joan")])
    assert text(out) == "By Joan Smith"
    # The gradient around the text is untouched (no box painted over it).
    assert all(52 <= row <= 76 for row in changed_rows(src, out))


def test_rotated_page(tmp_path):
    src = make(tmp_path / "a.pdf", [(40, 80, "Issued to Jon Smith on Monday.", 14)], rotate=90)
    report = edit_text(src, tmp_path / "o.pdf", [("Jon", "John")])
    assert report.edits[0].fit == "shifted"
    assert text(tmp_path / "o.pdf") == "Issued to John Smith on Monday."


def test_rotated_text_is_skipped_with_warning(tmp_path):
    src = make(tmp_path / "a.pdf", [(60, 180, "Vertical Jon", 12, {"rotate": 90}),
                                    (150, 60, "Flat Jon here", 12)], height=260)
    report = edit_text(src, tmp_path / "o.pdf", [("Jon", "John")])
    assert len(report.edits) == 1
    assert any("rotated" in w for w in report.warnings)
    assert "Flat John here" in text(tmp_path / "o.pdf")


def test_form_field_value(tmp_path):
    src = tmp_path / "form.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "name"
    widget.field_value = "Jon Smith"
    widget.rect = pymupdf.Rect(90, 28, 300, 46)
    page.add_widget(widget)
    doc.save(src)

    report = edit_text(src, tmp_path / "o.pdf", [("Jon", "John")])
    assert report.edits[0].fit == "form field"
    with pymupdf.open(tmp_path / "o.pdf") as doc:
        assert [w.field_value for w in doc[0].widgets()] == ["John Smith"]


@pytest.mark.parametrize("new, family", [("Жанна", "Helvetica"), ("Ζωή", "Helvetica"),
                                         ("李明", "Droid Sans Fallback")])
def test_non_latin_replacements(tmp_path, new, family):
    src = make(tmp_path / "a.pdf", [(30, 60, "Name: Jon", 14)])
    out = tmp_path / "o.pdf"
    report = edit_text(src, out, [("Jon", new)])
    assert report.edits[0].font.startswith(family)
    assert text(out) == f"Name: {new}"
    # The 3.5 MB CJK font is trimmed to the glyphs used.
    assert out.stat().st_size < 200_000


def test_signed_pdf_warns(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Signed by Jon", 14)])
    doc = pymupdf.open(src)
    form = doc.get_new_xref()
    doc.update_object(form, "<< /Fields [] /SigFlags 3 >>")
    doc.xref_set_key(doc.pdf_catalog(), "AcroForm", f"{form} 0 R")
    signed = tmp_path / "signed.pdf"
    doc.save(signed)

    report = edit_text(signed, tmp_path / "o.pdf", [("Jon", "John")])
    assert any("digitally signed" in w for w in report.warnings)


def test_document_properties_and_bookmarks(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Offer for Jon Smith", 14)])
    doc = pymupdf.open(src)
    doc.set_metadata({"title": "Offer - Jon Smith", "author": "HR", "subject": "For Jon Smith"})
    doc.set_xml_metadata('<x:xmpmeta xmlns:x="adobe:ns:meta/"><t>Jon Smith &amp; co</t></x:xmpmeta>')
    info = int(doc.xref_get_key(-1, "Info")[1].split()[0])
    doc.xref_set_key(info, "Custom", "(kept)")
    doc.set_toc([[1, "Letter to Jon Smith", 1]])
    doc.saveIncr()
    doc.close()

    out = tmp_path / "o.pdf"
    report = edit_text(src, out, [("Jon Smith", "John O'Brien & Smith")])
    assert {e.font for e in report.edits} == {"Helvetica", "document title",
                                              "document subject", "bookmark"}
    assert not report.warnings  # nothing of the old name left anywhere
    with pymupdf.open(out) as doc:
        assert doc.metadata["title"] == "Offer - John O'Brien & Smith"
        assert doc.metadata["subject"] == "For John O'Brien & Smith"
        assert doc.metadata["author"] == "HR"
        info = int(doc.xref_get_key(-1, "Info")[1].split()[0])
        assert doc.xref_get_key(info, "Custom") == ("string", "kept")
        assert "John O&#x27;Brien &amp; Smith &amp; co" in doc.get_xml_metadata()
        assert doc.get_toc() == [[1, "Letter to John O'Brien & Smith", 1]]
    assert_valid(out)


def test_pages_option_leaves_properties_and_says_so(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Offer for Jon", 14)])
    with pymupdf.open(src) as doc:
        doc.set_metadata({"title": "Jon"})
        doc.saveIncr()
    report = edit_text(src, tmp_path / "o.pdf", [("Jon", "John")], pages="1")
    assert [e.page for e in report.edits] == [1]
    assert any("document properties" in w for w in report.warnings)


def test_warns_about_old_text_left_in_an_attachment(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Offer for Jon Smith", 14)])
    with pymupdf.open(src) as doc:
        doc.embfile_add("notes.txt", b"Notes about Jon  Smith")
        doc.saveIncr()
    report = edit_text(src, tmp_path / "o.pdf", [("Jon Smith", "John Smith")])
    assert report.warnings == ["'Jon Smith' still appears in an attached or embedded file; "
                               "this tool edits page text, form fields and document "
                               "properties only."]


def test_dry_run_writes_nothing(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Name: Jon", 14)])
    out = tmp_path / "o.pdf"
    report = edit_text(src, out, [("Jon", "John")], dry_run=True)
    assert len(report.edits) == 1 and not out.exists()


def test_pages_option(tmp_path):
    src = tmp_path / "two.pdf"
    doc = pymupdf.open()
    for _ in range(2):
        doc.new_page().insert_text((50, 80), "Name: Jon", fontname="helv")
    doc.save(src)
    out = tmp_path / "o.pdf"
    edit_text(src, out, [("Jon", "John")], pages="2")
    assert text(out, 0) == "Name: Jon" and text(out, 1) == "Name: John"


def test_unmatched_term_is_reported(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Name: Jon", 14)])
    report = edit_text(src, tmp_path / "o.pdf", [("Jon", "John"), ("Nobody", "x")])
    assert report.not_found == ["Nobody"]


# errors

def test_no_match_at_all(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Name: Jon", 14)])
    with pytest.raises(ValueError, match="No match for 'Nobody'.*spelling"):
        edit_text(src, tmp_path / "o.pdf", [("Nobody", "x")])


def test_scanned_pdf_hint(tmp_path):
    src = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    doc.new_page().draw_rect(pymupdf.Rect(10, 10, 100, 100), fill=(0, 0, 0))
    doc.save(src)
    with pytest.raises(ValueError, match="scan"):
        edit_text(src, tmp_path / "o.pdf", [("Jon", "John")])


@pytest.mark.parametrize("kwargs, message", [
    ({"replacements": []}, "at least one"),
    ({"replacements": [(" ", "x")]}, "must not be empty"),
    ({"output": "same"}, "different"),
    ({"output": "o.png"}, ".pdf"),
    ({"pages": "9"}, "outside"),
])
def test_bad_arguments(tmp_path, kwargs, message):
    src = make(tmp_path / "a.pdf", [(30, 60, "Name: Jon", 14)])
    output = kwargs.pop("output", "o.pdf")
    output = src if output == "same" else tmp_path / output
    kwargs.setdefault("replacements", [("Jon", "John")])
    with pytest.raises(ValueError, match=message):
        edit_text(src, output, **kwargs)


def test_encrypted_pdf(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Name: Jon", 14)])
    locked = tmp_path / "locked.pdf"
    with pymupdf.open(src) as doc:
        doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    with pytest.raises(ValueError, match="encrypted"):
        edit_text(locked, tmp_path / "o.pdf", [("Jon", "John")])


# CLI

def test_cli(tmp_path):
    src = make(tmp_path / "a.pdf", [(30, 60, "Name: Jon", 14)])
    out = tmp_path / "o.pdf"
    result = subprocess.run(
        [PDF_TOOLS, "edit-text", src, "--find", "Jon", "--replace", "John", "-o", out],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Page 1: 'Jon' -> 'John'" in result.stdout
    assert text(out) == "Name: John"


@pytest.mark.parametrize("args, message", [
    (["--find", "a", "--find", "b", "--replace", "x"], "one --replace for each --find"),
    (["--find", "a", "--replace", "x"], "-o/--output is required"),
])
def test_cli_usage_errors(tmp_path, args, message):
    src = make(tmp_path / "a.pdf", [(30, 60, "Name: Jon", 14)])
    result = subprocess.run([PDF_TOOLS, "edit-text", src, *args], capture_output=True, text=True)
    assert result.returncode == 2
    assert message in result.stderr
