"""CLI: redact searchable text terms from a PDF into a new output PDF."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.redact import REDACTION_MODES, redact_pdf


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Redact searchable text terms from a PDF and write a new PDF.",
    )
    p.add_argument("input", type=Path, help="Input PDF path")
    p.add_argument(
        "--term",
        action="append",
        default=[],
        help="Text term or phrase to redact. Repeat for multiple terms.",
    )
    p.add_argument(
        "--terms",
        action="append",
        default=[],
        help='Comma-separated text terms to redact, for example "name,email,phone". Repeatable.',
    )
    p.add_argument(
        "--terms-file",
        type=Path,
        action="append",
        default=[],
        help="Text file with one redaction term per line. Repeatable.",
    )
    p.add_argument(
        "--mode",
        choices=sorted(REDACTION_MODES),
        default="black",
        help="Redaction fill style. 'remove' leaves a blank white area.",
    )
    p.add_argument(
        "--replacement",
        help="Optional replacement text. This redacts the original text, then writes the replacement.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path for the new redacted PDF",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log debug messages",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        redact_pdf(
            args.input,
            _collect_terms(args.term, args.terms, args.terms_file),
            args.output,
            mode=args.mode,
            replacement=args.replacement,
        )
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1
    return 0


def _collect_terms(
    single_terms: list[str],
    comma_term_groups: list[str],
    term_files: list[Path],
) -> list[str]:
    terms: list[str] = []
    terms.extend(single_terms)

    for group in comma_term_groups:
        terms.extend(term.strip() for term in group.split(","))

    for term_file in term_files:
        path = term_file.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Terms file not found: {path}")
        terms.extend(_terms_from_file(path))

    clean_terms = [term for term in terms if term.strip()]
    if not clean_terms:
        raise ValueError(
            "Provide at least one term using --term, --terms, or --terms-file."
        )
    return clean_terms


def _terms_from_file(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


if __name__ == "__main__":
    sys.exit(main())
