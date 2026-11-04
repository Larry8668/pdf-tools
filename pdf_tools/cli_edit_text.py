"""CLI: replace text in a PDF, keeping its font, size and position."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.edit_text import edit_text

_FIT_NOTES = {
    "shifted": "rest of the line moved to fit",
    "centred": "line re-centred",
    "shrunk": "slightly smaller to fit",
    "overflow": "too long to fit; check it",
    "kept rest of line": "rest of the line left as is",
    "form field": "form field value",
}
_PLACE = {"form field": None, "property": None}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Replace text in a PDF, for example a misspelled name, keeping the "
            "original font, size, colour and position."
        ),
        epilog=(
            "Each --find needs a matching --replace; give several pairs to make "
            "several changes.\n\n"
            "Examples:\n"
            '  %(prog)s offer.pdf --find "Jon Smith" --replace "John Smith" -o fixed.pdf\n'
            '  %(prog)s form.pdf --find 2025 --replace 2026 --pages 1-2 --dry-run\n\n'
            "When the document's font lacks a letter you need, the closest standard\n"
            "font is used instead and the output says so. Check the result with\n"
            "'pdf-tools render-page'. Scanned PDFs (images of text) can't be edited."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("input", type=Path, help="Input PDF path")
    p.add_argument("--find", action="append", required=True, metavar="TEXT",
                   help="Text to replace. Repeat for several changes.")
    p.add_argument("--replace", action="append", required=True, metavar="TEXT",
                   help="Replacement for the matching --find (may be empty to delete).")
    p.add_argument("--pages", help='Only these pages, for example "1,3-4". Default: all.')
    p.add_argument("--ignore-case", action="store_true", help="Match regardless of case.")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change without writing a file.")
    p.add_argument("-o", "--output", type=Path,
                   help="Path for the edited PDF (required unless --dry-run)")
    p.add_argument("-v", "--verbose", action="store_true", help="Log debug messages")
    args = p.parse_args()
    if len(args.find) != len(args.replace):
        p.error(f"got {len(args.find)} --find but {len(args.replace)} --replace; "
                "give one --replace for each --find.")
    if args.output is None and not args.dry_run:
        p.error("-o/--output is required (or pass --dry-run).")
    return args


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    output = args.output or args.input.with_name(args.input.stem + ".dry-run.pdf")
    try:
        report = edit_text(
            args.input,
            output,
            list(zip(args.find, args.replace)),
            pages=args.pages,
            ignore_case=args.ignore_case,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1

    for warning in report.warnings:
        logging.warning("%s", warning)
    for e in report.edits:
        details = [e.font if e.fit not in _PLACE else None, _FIT_NOTES.get(e.fit)]
        if e.fallback_reason:
            details.append(f"used instead because {e.fallback_reason}")
        detail = "; ".join(d for d in details if d)
        where = f"Page {e.page}" if e.page else e.font.capitalize()
        suffix = f" ({detail})" if detail else ""
        print(f"{where}: {e.old!r} -> {e.new!r}{suffix}")
    for term in report.not_found:
        logging.warning("No match for %r.", term)
    verb = "Would change" if args.dry_run else "Changed"
    where = "" if args.dry_run else f" -> {output}"
    print(f"{verb} {len(report.edits)} place(s){where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
