"""Replace text in a PDF in place, keeping its font, size, colour and position.

A PDF has no paragraphs to reflow: each piece of text is drawn at a fixed spot
in a fixed font. To change a word we remove just its glyphs (leaving whatever
is behind them), draw the new text on the same baseline in the same style, and
slide the rest of that line over by the change in width.

The document's own font is reused when it contains every letter needed. PDFs
usually embed only the letters they use, so when one is missing we fall back
to the closest standard font (Times, Helvetica or Courier, matching bold and
italic) and say so.
"""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf

from pdf_tools.remove_pages import parse_page_ranges

logger = logging.getLogger(__name__)

# Expand ligatures (Quartz writes "ff" as one glyph) so "Jeff" can be found.
_TEXT_FLAGS = pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP

# New text may shrink to this fraction of its size to fit; below it we overflow.
_MIN_SHRINK = 0.8

_BOLD_WORDS = ("bold", "black", "heavy", "semibold", "demi", "medi")
_ITALIC_WORDS = ("italic", "oblique", "-it", "bdit", "ital")
_SERIF_WORDS = ("times", "georgia", "serif", "roman", "garamond", "didot", "nimbusrom",
                "cambria", "palatino", "baskerville", "bodoni", "book antiqua", "minion",
                "caslon", "charter", "cmr", "lmroman", "sfrm")
_SANS_WORDS = ("arial", "helvetica", "verdana", "calibri", "segoe", "tahoma", "avenir",
               "futura", "gill", "franklin", "frutiger", "myriad", "roboto", "opensans",
               "lato", "inter", "sfpro", "sansserif", "sans", "optima", "trebuchet")
_MONO_WORDS = ("courier", "mono", "menlo", "consolas", "code", "sftt", "cmtt", "inconsolata")
_BASE14 = {  # (serif|sans|mono, bold, italic) -> PyMuPDF base-14 name
    ("serif", False, False): "tiro", ("serif", True, False): "tibo",
    ("serif", False, True): "tiit", ("serif", True, True): "tibi",
    ("sans", False, False): "helv", ("sans", True, False): "hebo",
    ("sans", False, True): "heit", ("sans", True, True): "hebi",
    ("mono", False, False): "cour", ("mono", True, False): "cobo",
    ("mono", False, True): "coit", ("mono", True, True): "cobi",
}
_BASE14_NAMES = {
    "tiro": "Times-Roman", "tibo": "Times-Bold", "tiit": "Times-Italic", "tibi": "Times-BoldItalic",
    "helv": "Helvetica", "hebo": "Helvetica-Bold", "heit": "Helvetica-Oblique",
    "hebi": "Helvetica-BoldOblique", "cour": "Courier", "cobo": "Courier-Bold",
    "coit": "Courier-Oblique", "cobi": "Courier-BoldOblique",
}
# Fonts PDF viewers must provide; when a PDF names one without embedding it,
# drawing with the same base-14 font is an exact match.
_STANDARD_ALIASES = {name.lower(): alias for alias, name in _BASE14_NAMES.items()} | {
    "arial": "helv", "arialmt": "helv", "arial-boldmt": "hebo", "arial,bold": "hebo",
    "timesnewroman": "tiro", "timesnewromanpsmt": "tiro", "timesnewromanps-boldmt": "tibo",
}


@dataclass
class Edit:
    """One replacement that was (or, with dry_run, would be) made."""

    page: int
    old: str
    new: str
    font: str
    fallback_reason: str | None = None
    fit: str = "exact"  # exact, shifted, shrunk, overflow, centred, form field, property
    term: str = ""  # page 0 means a document-wide property (title, bookmark, ...)


@dataclass
class EditReport:
    edits: list[Edit]
    not_found: list[str]
    warnings: list[str]


def edit_text(
    input_pdf: Path | str,
    output_pdf: Path | str,
    replacements: Sequence[tuple[str, str]],
    *,
    pages: str | None = None,
    ignore_case: bool = False,
    dry_run: bool = False,
) -> EditReport:
    """Replace each ``(old, new)`` pair everywhere it appears and write a new PDF."""
    source = Path(input_pdf).expanduser().resolve()
    out = Path(output_pdf).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input PDF not found: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Input must be a PDF: {source}")
    if out == source:
        raise ValueError("Output PDF path must be different from the input PDF path.")
    if out.suffix.lower() != ".pdf":
        raise ValueError(f"Output must be a .pdf file: {out.name}")
    if not replacements:
        raise ValueError("Give at least one --find/--replace pair.")
    for old, _ in replacements:
        if not old.strip():
            raise ValueError("--find text must not be empty.")

    # Damaged PDFs make MuPDF print errors it recovers from; keep the output clean.
    pymupdf.TOOLS.mupdf_display_errors(False)
    flags = re.IGNORECASE if ignore_case else 0
    patterns = [(_pattern(old, flags), old, new) for old, new in replacements]

    edits: list[Edit] = []
    warnings: list[str] = []
    with pymupdf.open(source) as doc:
        if doc.needs_pass:
            raise ValueError(f"Input PDF is encrypted; provide an unlocked copy: {source}")
        page_numbers = (sorted(parse_page_ranges(pages, doc.page_count)) if pages
                        else range(1, doc.page_count + 1))
        if doc.get_sigflags() > 0:
            warnings.append("This PDF is digitally signed. Editing it invalidates the "
                            "signature, so the signer would need to sign again.")
        fonts = _FontCache(doc)
        text_found = False
        for number in page_numbers:
            page = doc[number - 1]
            text_found |= bool(page.get_text("text").strip())
            edits += _edit_form_fields(page, number, patterns, dry_run)
            edits += _edit_page(page, number, patterns, fonts, dry_run, warnings)

        if not pages:  # properties are document-wide; --pages means "only there"
            edits += _edit_properties(doc, patterns, dry_run)

        found = {e.term for e in edits}
        not_found = [old for _, old, _ in patterns if old not in found]
        if not edits:
            hint = ("The pages have no selectable text; this looks like a scan, which "
                    "would need OCR." if not text_found else
                    "Check the spelling and spacing, or whether the text breaks "
                    "across two lines; matches must sit on one line.")
            raise ValueError(f"No match for {', '.join(repr(o) for o in not_found)}. {hint}")

        if not dry_run:
            if fonts.embedded_fallback:
                # Keep only the glyphs used: the CJK fallback alone is 3.5 MB.
                doc.subset_fonts()
            out.parent.mkdir(parents=True, exist_ok=True)
            doc.save(out, garbage=3, deflate=True)
            warnings += _leftovers(out, [old for _, old, _ in patterns], ignore_case)
    logger.debug("%d edit(s) in %s", len(edits), out)
    return EditReport(edits, not_found, warnings)


def _pattern(old: str, flags: int) -> re.Pattern[str]:
    # Any run of whitespace in the search text matches any run in the PDF,
    # including at the ends, so "--find 'cruel '" also takes the space.
    parts = [re.escape(p) for p in old.split()]
    lead = r"\s+" if old[:1].isspace() else ""
    trail = r"\s+" if old[-1:].isspace() else ""
    return re.compile(lead + r"\s+".join(parts) + trail, flags)


# Text on the page

@dataclass
class _Char:
    c: str
    bbox: pymupdf.Rect
    origin: pymupdf.Point
    span: dict


@dataclass
class _Run:
    """Text to draw: one replacement, or one word of the original line."""

    text: str
    x: float
    y: float  # baseline; superscripts and subscripts keep their own
    span: dict
    is_new: bool = False
    shrink: float = 1.0


def _lines(page: pymupdf.Page):
    for block in page.get_text("rawdict", flags=_TEXT_FLAGS)["blocks"]:
        for line in block.get("lines", []):
            chars = [
                _Char(ch["c"], pymupdf.Rect(ch["bbox"]), pymupdf.Point(ch["origin"]), span)
                for span in line["spans"] for ch in span["chars"]
            ]
            if chars:
                yield line, chars


def _edit_page(page, number, patterns, fonts, dry_run, warnings) -> list[Edit]:
    all_lines = list(_lines(page))
    if not all_lines:
        return []
    # The text area: from the leftmost text to whichever is further right, the
    # widest line or a right margin mirroring the left one.
    box = page.cropbox  # text coordinates ignore page rotation, and so does this
    left = min(pymupdf.Rect(line["bbox"]).x0 for line, _ in all_lines)
    right = max(max(pymupdf.Rect(line["bbox"]).x1 for line, _ in all_lines),
                box.x1 - (left - box.x0))
    column = (left, right)
    planned: list[tuple[list[_Char], list[_Run]]] = []
    edits: list[Edit] = []

    for line, chars in all_lines:
        text = "".join(ch.c for ch in chars)
        matches = _drop_overlaps(sorted(
            (m.start(), m.end(), new, old)
            for pattern, old, new in patterns for m in pattern.finditer(text)
        ))
        if not matches:
            continue
        if abs(line["dir"][0] - 1) > 1e-3 or abs(line["dir"][1]) > 1e-3:
            warnings.append(f"Page {number}: skipped a match in rotated text "
                            f"({text[matches[0][0]:matches[0][1]]!r}).")
            continue
        remove, runs, line_edits = _plan_line(page, number, chars, matches, fonts, column)
        planned.append((remove, runs))
        edits += line_edits

    if planned and not dry_run:
        _apply(page, planned, fonts)
    return edits


def _drop_overlaps(matches):
    kept, end = [], -1
    for match in matches:
        if match[0] >= end:
            kept.append(match)
            end = match[1]
    return kept


def _plan_line(page, number, chars, matches, fonts, column):
    """Work out which glyphs to remove from one line and what to draw instead.

    Normally everything from the first match to the end of the line is redrawn,
    so later words slide over by the change in width. If any of those words is
    in a font we can't reuse, redrawing them would change how they look; then
    only the matches are replaced and each must fit in its old width.
    """
    first = matches[0][0]
    tail_ok = all(
        fonts.choose(r.span, r.text, []).fallback_reason is None
        for r in _words(_unmatched(chars, matches, first), 0)
    )
    # Redrawing the words before the first match too keeps the line one piece of
    # text, so copying or searching "Dear <new name>" still works.
    head_ok = tail_ok and all(
        fonts.choose(r.span, r.text, []).fallback_reason is None
        for r in _words(chars[:first], 0)
    )
    line_x0 = chars[0].bbox.x0
    line_end = max(ch.bbox.x1 for ch in chars)
    # Centred: on the page's centre line and either indented from the other
    # text or clearly narrower than the page (a justified line is neither).
    box = page.cropbox
    centred = (tail_ok and abs((line_x0 + line_end) / 2 - (box.x0 + box.x1) / 2) < 3
               and (line_x0 - column[0] > 5 or line_end - line_x0 < 0.7 * box.width))

    edits: list[Edit] = []
    runs: list[_Run] = []
    delta = 0.0  # how far later text moves right because of earlier replacements
    for i, (start, stop, new, term) in enumerate(matches):
        span = chars[start].span
        x_start = chars[start].origin.x
        x_after = chars[stop].origin.x if stop < len(chars) else chars[stop - 1].bbox.x1
        old_width = x_after - x_start
        font = fonts.choose(span, new, [ch.c for ch in chars[first:]])
        words, new_width = font.layout(new, span["size"], _word_gap(chars, start, stop))
        edit = Edit(number, "".join(ch.c for ch in chars[start:stop]), new, font.label,
                    font.fallback_reason, term=term)

        grow = new_width - old_width
        trailing = bool("".join(ch.c for ch in chars[stop:]).strip())
        if centred:
            # It can grow on both sides, up to a half-inch page margin.
            room = (page.cropbox.width - 72) - (line_end - line_x0 + delta)
        elif tail_ok or not trailing:
            room = column[1] - (line_end + delta)
        else:
            room = 0.0  # the next word stays where it is
        shrink = 1.0
        if grow > 0.5 and grow > room:
            needed = (old_width + max(room, 0)) / new_width
            shrink = max(needed, _MIN_SHRINK)
            edit.fit = "shrunk" if needed >= _MIN_SHRINK else "overflow"
            grow = new_width * shrink - old_width
        if edit.fit == "exact" and abs(grow) > 0.5 and (trailing or centred):
            edit.fit = "centred" if centred else "shifted"
        y = chars[start].origin.y
        runs += [_Run(word, x_start + delta + offset * shrink, y, span, True, shrink)
                 for word, offset in words]
        if tail_ok:
            delta += grow
            next_start = matches[i + 1][0] if i + 1 < len(matches) else len(chars)
            runs += _words(chars[stop:next_start], delta)
        edits.append(edit)

    if tail_ok:
        remove = chars[first:]
        shift = -delta / 2 if centred and abs(delta) > 0.5 else 0.0
        if head_ok or shift:
            runs = _words(chars[:first], shift) + [
                _Run(r.text, r.x + shift, r.y, r.span, r.is_new, r.shrink) for r in runs]
            remove = chars
    else:
        remove = [ch for start, stop, *_ in matches for ch in chars[start:stop]]
        for e in edits:
            if e.fit == "exact" and e.new != e.old:
                e.fit = "kept rest of line"
    return remove, runs, edits


def _word_gap(chars, start, stop) -> float | None:
    """The gap between words as originally drawn, preferring the matched text."""
    def gaps(lo, hi):
        return [chars[i + 1].origin.x - chars[i - 1].bbox.x1
                for i in range(max(lo, 1), min(hi, len(chars) - 1))
                if chars[i].c.isspace() and not chars[i - 1].c.isspace()]
    found = gaps(start, stop) or gaps(0, len(chars))
    return sorted(found)[len(found) // 2] if found else None


def _unmatched(chars, matches, first):
    taken = {i for start, stop, *_ in matches for i in range(start, stop)}
    return [ch for i, ch in enumerate(chars) if i >= first and i not in taken]


def _words(chars: list[_Char], dx: float) -> list[_Run]:
    """Group characters into words (split at spaces and style changes), moved by dx."""
    runs: list[_Run] = []
    current: list[_Char] = []

    def flush():
        if current:
            runs.append(_Run("".join(c.c for c in current), current[0].origin.x + dx,
                             current[0].origin.y, current[0].span))
            current.clear()

    for ch in chars:
        if ch.c.isspace():
            flush()
        else:
            if current and current[-1].span is not ch.span:
                flush()
            current.append(ch)
    flush()
    return runs


def _apply(page, planned, fonts):
    for remove, _ in planned:
        for ch in remove:
            # Spaces too: some producers draw them as real glyphs.
            if ch.bbox.is_empty:
                continue
            # A thin box at the glyph's middle: removes it without touching
            # neighbours or the lines above and below.
            r = ch.bbox
            mid = (r.y0 + r.y1) / 2
            band = max((r.y1 - r.y0) * 0.15, 0.2)
            inset = min((r.x1 - r.x0) * 0.3, 1.0)
            page.add_redact_annot(pymupdf.Rect(r.x0 + inset, mid - band, r.x1 - inset, mid + band),
                                  fill=False, cross_out=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)

    for remove, runs in planned:
        context = [ch.c for ch in remove]
        for run in runs:
            font = fonts.choose(run.span, run.text, context if run.is_new else [])
            name = fonts.register(font, page, simple=all(ord(c) < 256 for c in run.text))
            page.insert_text((run.x, run.y), run.text, fontname=name,
                             fontsize=run.span["size"] * run.shrink,
                             color=pymupdf.sRGB_to_pdf(run.span["color"]))


# Form fields: fillable PDFs keep their values outside the page text.

def _substitute(patterns, value: str, escape=lambda t: t) -> tuple[str, list[str]]:
    """Apply every pattern to a plain string; return it and the terms that matched."""
    terms = []
    for pattern, old, new in patterns:
        value, count = pattern.subn(lambda _m, new=new: escape(new), value)
        terms += [old] * bool(count)
    return value, terms


def _edit_form_fields(page, number, patterns, dry_run) -> list[Edit]:
    edits = []
    for widget in page.widgets() or []:
        value = widget.field_value
        if not isinstance(value, str) or not value:
            continue
        new_value, terms = _substitute(patterns, value)
        if new_value != value:
            edits.append(Edit(number, value, new_value, "form field", fit="form field",
                              term=terms[0]))
            if not dry_run:
                widget.field_value = new_value
                widget.update()
    return edits


_INFO_KEYS = ("Title", "Author", "Subject", "Keywords")


def _edit_properties(doc, patterns, dry_run) -> list[Edit]:
    """Fix the old text in the title, author, subject, keywords and bookmarks.

    Viewers show these in File > Properties, the window title and the sidebar,
    so a misspelled name there would survive an edit of the pages alone.
    """
    edits = []
    info = doc.xref_get_key(-1, "Info")
    if info[0] == "xref":
        xref = int(info[1].split()[0])
        for key in _INFO_KEYS:
            value = doc.metadata.get(key.lower()) or ""
            new_value, terms = _substitute(patterns, value)
            if new_value != value:
                edits.append(Edit(0, value, new_value, f"document {key.lower()}",
                                  fit="property", term=terms[0]))
                if not dry_run:
                    doc.xref_set_key(xref, key, pymupdf.get_pdf_str(new_value))

    xml = doc.get_xml_metadata()
    if xml:
        # The same properties again, as XML: escape the new text for it.
        new_xml, terms = _substitute(patterns, xml, html.escape)
        if new_xml != xml:
            if not any(e.fit == "property" for e in edits):
                new = next(n for _, o, n in patterns if o == terms[0])
                edits.append(Edit(0, terms[0], new, "XMP metadata", fit="property",
                                  term=terms[0]))
            if not dry_run:
                doc.set_xml_metadata(new_xml)

    toc = doc.get_toc(simple=False)
    changed = False
    for entry in toc:
        new_title, terms = _substitute(patterns, entry[1])
        if new_title != entry[1]:
            edits.append(Edit(0, entry[1], new_title, "bookmark", fit="property", term=terms[0]))
            entry[1], changed = new_title, True
    if changed and not dry_run:
        doc.set_toc(toc)
    return edits


def _leftovers(path: Path, terms: list[str], ignore_case: bool) -> list[str]:
    """Warn about places outside the page text where an old term still appears.

    Comments, attachments and the like can hold a copy of the text. We don't
    edit those, but the user should know the old spelling is still in the file.
    """
    found: dict[str, set[str]] = {}
    with pymupdf.open(path) as doc:
        content = {x for page in doc for x in page.get_contents()}
        annots = {a.xref for page in doc for a in page.annots() or []}
        info = doc.xref_get_key(-1, "Info")
        info_xref = int(info[1].split()[0]) if info[0] == "xref" else 0
        for xref in range(1, doc.xref_length()):
            if xref in content:
                continue
            try:
                kind = doc.xref_get_key(xref, "Type")[1]
                subtype = doc.xref_get_key(xref, "Subtype")[1]
                if subtype == "/Image" or doc.xref_get_key(xref, "Length1")[0] != "null":
                    continue  # pictures and font programs
                blob = doc.xref_object(xref)
                if doc.xref_is_stream(xref):
                    blob += (doc.xref_stream(xref) or b"").decode("latin-1")
            except Exception:  # damaged object; nothing useful to report
                continue
            if xref == info_xref or kind == "/Metadata":
                where = "the document properties"
            elif xref in annots or kind == "/Annot":
                where = "a comment or annotation"
            elif kind in ("/EmbeddedFile", "/Filespec"):
                where = "an attached or embedded file"
            elif subtype == "/Form":
                where = "a drawing reused on the page (form XObject)"
            else:
                where = "other data inside the PDF"
            for term in terms:
                flags = re.IGNORECASE if ignore_case else 0
                if re.search(r"\s+".join(map(re.escape, term.split())), blob, flags):
                    found.setdefault(term, set()).add(where)
    return [f"{term!r} still appears in {', '.join(sorted(places))}; this tool edits "
            "page text, form fields and document properties only."
            for term, places in found.items()]


# Fonts

@dataclass
class _Font:
    label: str
    fallback_reason: str | None
    _font: pymupdf.Font
    _alias: str
    _buffer: bytes | None = None

    def layout(self, text: str, size: float, gap: float | None):
        """Place ``text`` word by word; return ``[(word, x offset)]`` and the width.

        With a space glyph the text is one string, so it copies with its spaces.
        Some embedded fonts have none (LaTeX spaces words by position); then the
        words go one by one, the gap measured from the original text.
        """
        if self._font.has_glyph(32):
            return [(text, 0.0)], self._font.text_length(text, fontsize=size)
        space = gap if gap is not None else 0.25 * size
        placed, x = [], 0.0
        for i, word in enumerate(text.split(" ")):
            if i:
                x += space
            if word:
                placed.append((word, x))
                x += self._font.text_length(word, fontsize=size)
        return placed, x


class _FontCache:
    """Finds, for a span, a font that can draw the text we need."""

    def __init__(self, doc: pymupdf.Document) -> None:
        self._doc = doc
        self._by_name: dict[str, list[tuple[int, pymupdf.Font, bytes]]] = {}
        self._all: list[tuple[int, set[str], pymupdf.Font, bytes]] | None = None
        self._base14: dict[str, pymupdf.Font] = {}
        self._on_page: set[tuple[int, str]] = set()
        self.embedded_fallback = False
        self._ink: dict[tuple[int, str], bool] = {}

    def register(self, font: _Font, page: pymupdf.Page, *, simple: bool) -> str:
        """Make ``font`` usable on ``page`` and return the name to draw with.

        Latin-1 text uses the font as a simple (single-byte) font: its text then
        copies and searches correctly, where the composite form can map a
        hyphen to a soft hyphen or a space to a no-break space.
        """
        if font._buffer is None:
            return font._alias
        cff = _cff_kind(font._buffer)
        # A CID-keyed CFF program is only valid inside a composite font.
        simple = simple and cff != "cid"
        alias = font._alias + ("S" if simple else "")
        if font._alias.endswith("U"):
            self.embedded_fallback = True
        if (page.number, alias) not in self._on_page:
            xref = page.insert_font(fontname=alias, fontbuffer=font._buffer, set_simple=simple)
            if simple and cff == "bare":
                _label_type1c(page.parent, xref)
            self._on_page.add((page.number, alias))
        return alias

    def _candidates(self, name: str):
        key = _name_key(name)
        if key not in self._by_name:
            self._by_name[key] = [
                (xref, font, buffer) for xref, names, font, buffer in self._embedded()
                if key in names
                # MuPDF can shorten names in the text layer ("...Std-Dem" for
                # "...Std-Demi"); allow that, but not "Arial" for "Arial-BoldMT".
                or any(n.startswith(key) and len(n) - len(key) <= 2 for n in names)
            ]
        return self._by_name[key]

    def _embedded(self):
        """Every embedded font once, with the names it may appear under.

        The text layer names a font either as the PDF does ("Helvetica") or as
        the font program itself does ("NimbusSans-Regular"), so keep both.
        """
        if self._all is None:
            self._all = []
            seen = set()
            for page in self._doc:
                for xref, _, _, base, *_ in page.get_fonts(full=True):
                    if xref in seen:
                        continue
                    seen.add(xref)
                    try:
                        _, ext, _, buffer = self._doc.extract_font(xref)
                        if not buffer or ext == "n/a":
                            continue
                        font = pymupdf.Font(fontbuffer=buffer)
                    except Exception as e:  # damaged or unusual font program
                        logger.debug("Cannot reuse font %s: %s", base, e)
                        continue
                    names = {_name_key(base), _name_key(font.name)}
                    self._all.append((xref, names, font, buffer))
        return self._all

    def choose(self, span: dict, text: str, context: list[str]) -> _Font:
        """Pick the span's own font when it has every glyph in ``text``."""
        name = _strip_subset(span["font"])
        needed = {c for c in text if not c.isspace()}
        best = None
        for xref, font, buffer in self._candidates(name):
            if self._drawable(xref, font, needed) == needed:
                # Prefer the subset that also covers the surrounding text: that
                # is most likely the one this span was drawn with.
                score = len(self._drawable(xref, font, set(context)))
                if best is None or score > best[0]:
                    best = (score, xref, font, buffer)
        if best is not None:
            _, xref, font, buffer = best
            return _Font(name, None, font, f"ED{xref}", buffer)

        standard = _STANDARD_ALIASES.get(name.lower())
        if standard and not self._candidates(name):
            # A standard font the PDF doesn't embed: drawing it is an exact match.
            return self._standard(standard, needed, name, None)

        alias = _BASE14[_classify(name, span["flags"])]
        if self._candidates(name):
            missing = sorted(needed - set().union(
                *(self._drawable(x, f, needed) for x, f, _ in self._candidates(name))))
            reason = (f"the document's {name} font doesn't include "
                      f"{', '.join(repr(c) for c in missing)}" if missing else
                      f"the document's {name} font can't be reused")
        else:
            reason = f"the document's {name} font isn't embedded"
        return self._standard(alias, needed, _BASE14_NAMES[alias], reason)

    def _drawable(self, xref: int, font: pymupdf.Font, chars: set[str]) -> set[str]:
        """The characters in ``chars`` that ``font`` can actually draw.

        A subset font may still list a letter but with an empty outline (MuPDF
        and some other tools subset that way), so a listed glyph must also
        leave ink when drawn. Results are cached per font and character.
        """
        unknown = [c for c in chars if (xref, c) not in self._ink and not c.isspace()]
        listed = [c for c in unknown if font.has_glyph(ord(c))]
        for c in set(unknown) - set(listed):
            self._ink[(xref, c)] = False
        if listed:
            for c, inked in zip(listed, _inked(font, listed)):
                self._ink[(xref, c)] = inked
        return {c for c in chars if c.isspace() or self._ink[(xref, c)]}

    def _standard(self, alias: str, needed: set[str], label: str,
                  reason: str | None) -> _Font:
        """A font MuPDF ships with, embedded unless the text is plain Latin-1."""
        font = self._builtin(alias)
        if all(ord(c) < 256 for c in needed):
            # Viewers provide the 14 standard fonts, so nothing needs embedding.
            return _Font(label, reason, font, alias)
        if all(font.has_glyph(ord(c)) for c in needed):
            # Greek, Cyrillic and more: the same design, embedded for Unicode.
            return _Font(label, reason, font, alias + "U", font.buffer)
        wide = self._builtin("cjk")
        unsupported = [c for c in needed if not wide.has_glyph(ord(c))]
        if unsupported:
            raise ValueError(
                f"Can't draw {''.join(unsupported)!r}: no available font has "
                f"{'it' if len(unsupported) == 1 else 'them'}."
            )
        why = reason or f"{label} has no {', '.join(sorted(c for c in needed if ord(c) > 255))}"
        return _Font(wide.name, why, wide, "CJKU", wide.buffer)

    def _builtin(self, alias: str) -> pymupdf.Font:
        if alias not in self._base14:
            self._base14[alias] = pymupdf.Font(alias)
        return self._base14[alias]


def _cff_kind(buffer: bytes) -> str | None:
    """"cid" or "bare" for a CFF font program (by its Top DICT), else None.

    CID-keyed CFF starts its Top DICT with the ROS operator (12 30).
    """
    try:
        if len(buffer) < 4 or buffer[0] != 1 or buffer[1] != 0:
            return None
        pos = buffer[2]

        def skip_index(pos):
            count = int.from_bytes(buffer[pos:pos + 2], "big")
            if count == 0:
                return pos + 2, b""
            size = buffer[pos + 2]
            offsets = [int.from_bytes(buffer[pos + 3 + i * size:pos + 3 + (i + 1) * size], "big")
                       for i in range(count + 1)]
            data = pos + 3 + (count + 1) * size - 1
            return data + offsets[-1], buffer[data + offsets[0]:data + offsets[1]]

        pos, _ = skip_index(pos)  # Name INDEX
        _, top = skip_index(pos)  # Top DICT INDEX: its first DICT
        i = 0
        while i < len(top):  # skip operands up to the first operator
            b = top[i]
            if b <= 21:
                return "cid" if b == 12 and top[i + 1:i + 2] == b"\x1e" else "bare"
            if b == 28:
                i += 3
            elif b == 29:
                i += 5
            elif b == 30:  # real number: nibbles until one is 0xf
                i += 1
                while i < len(top) and 0xF not in (top[i] >> 4, top[i] & 0xF):
                    i += 1
                i += 1
            elif b >= 247:
                i += 2
            else:
                i += 1
        return "bare"
    except IndexError:
        return None


def _label_type1c(doc: pymupdf.Document, font_xref: int) -> None:
    """Mark a simple font's CFF program as /Type1C, as the PDF spec requires.

    MuPDF labels every CFF program /CIDFontType0C, which only suits composite
    fonts; macOS logs an error for it and strict tools reject it.
    """
    descriptor = doc.xref_get_key(font_xref, "FontDescriptor")
    if descriptor[0] != "xref":
        return
    program = doc.xref_get_key(int(descriptor[1].split()[0]), "FontFile3")
    if program[0] == "xref":
        doc.xref_set_key(int(program[1].split()[0]), "Subtype", "/Type1C")


def _inked(font: pymupdf.Font, chars: list[str]) -> list[bool]:
    """Draw each character in its own cell and report which left any ink."""
    cell = 60
    scratch = pymupdf.open()
    page = scratch.new_page(width=cell * len(chars), height=cell)
    writer = pymupdf.TextWriter(page.rect)
    for i, c in enumerate(chars):
        writer.append((i * cell + 10, 42), c, font=font, fontsize=36)
    writer.write_text(page)
    pix = page.get_pixmap(dpi=36, colorspace=pymupdf.csGRAY)
    scratch.close()
    gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    step = pix.w / len(chars)
    return [bool((gray[:, round(i * step):round((i + 1) * step)] < 200).any())
            for i in range(len(chars))]


def _name_key(name: str) -> str:
    """Compare "NimbusSans-Regular" and "Nimbus Sans Regular" as the same font."""
    return re.sub(r"[\s_-]", "", _strip_subset(name)).lower()


def _strip_subset(name: str) -> str:
    # Embedded subsets are named like "ABCDEF+Georgia".
    return name.split("+", 1)[1] if re.match(r"^[A-Z]{6}\+", name) else name


def _classify(name: str, flags: int) -> tuple[str, bool, bool]:
    lower = name.lower().replace(" ", "")
    bold = bool(flags & pymupdf.TEXT_FONT_BOLD) or any(w in lower for w in _BOLD_WORDS)
    italic = bool(flags & pymupdf.TEXT_FONT_ITALIC) or any(w in lower for w in _ITALIC_WORDS)
    # A known family name beats the PDF's flags, which producers often get wrong.
    if any(w in lower for w in _MONO_WORDS):
        family = "mono"
    elif any(w in lower for w in _SANS_WORDS):
        family = "sans"
    elif any(w in lower for w in _SERIF_WORDS):
        family = "serif"
    elif flags & pymupdf.TEXT_FONT_MONOSPACED:
        family = "mono"
    elif flags & pymupdf.TEXT_FONT_SERIFED:
        family = "serif"
    else:
        family = "sans"
    return family, bold, italic
