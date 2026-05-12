"""PDF and image utility functions."""

from pdf_tools.merge import merge_files, merge_pdfs, merge_two_pdfs
from pdf_tools.redact import redact_pdf
from pdf_tools.redact_area import PageArea, redact_areas
from pdf_tools.remove_pages import parse_page_ranges, remove_pages
from pdf_tools.render_page import render_page

__all__ = [
    "PageArea",
    "merge_files",
    "merge_pdfs",
    "merge_two_pdfs",
    "parse_page_ranges",
    "redact_pdf",
    "redact_areas",
    "remove_pages",
    "render_page",
]
