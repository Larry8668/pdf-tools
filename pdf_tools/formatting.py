"""Shared display helpers."""

from __future__ import annotations


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024**2:
        return f"{size / 1024:.1f} KB"
    if size < 1024**3:
        return f"{size / (1024**2):.1f} MB"
    return f"{size / (1024**3):.1f} GB"
