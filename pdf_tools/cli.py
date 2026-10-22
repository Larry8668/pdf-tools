"""CLI: `pdf-tools <command> ...`, a single entry point for every tool."""

from __future__ import annotations

import difflib
import importlib
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

PROG = "pdf-tools"


@dataclass(frozen=True)
class Command:
    name: str
    module: str
    summary: str
    example: str


GROUPS: list[tuple[str, list[Command]]] = [
    (
        "PDF",
        [
            Command("merge", "cli_merge", "Merge PDFs and images into one PDF, or turn an image into a PDF",
                    "merge a.pdf photo.png b.pdf -o merged.pdf"),
            Command("compress", "cli_compress", "Shrink a PDF by recompressing its images",
                    "compress big.pdf --size-percent 20 -o small.pdf"),
            Command("remove-pages", "cli_remove_pages", "Drop pages from a PDF",
                    'remove-pages doc.pdf --pages "1,3,5-7" -o trimmed.pdf'),
            Command("redact", "cli_redact", "Remove searchable text, such as names or account numbers",
                    'redact doc.pdf --terms "Jane Doe,12345" -o redacted.pdf'),
            Command("render-page", "cli_render_page", "Render a page to an image, optionally with a pixel grid",
                    "render-page doc.pdf --page 1 --grid-size 100 -o page1.png"),
            Command("redact-area", "cli_redact_area", "Black out or blank a rectangle on a page",
                    'redact-area doc.pdf --page 1 --pixels "200,300,600,420" -o redacted.pdf'),
        ],
    ),
    (
        "Images",
        [
            Command("image-compress", "cli_compress_image", "Shrink an image, optionally capping its size",
                    "image-compress photo.png --quality 70 -o photo.jpg"),
            Command("image-pad-square", "cli_image_pad_square", "Pad an image to a square",
                    "image-pad-square photo.png --size 1024 -o square.png"),
        ],
    ),
    (
        "Video",
        [
            Command("video-compress", "cli_compress_video", "Shrink a video with FFmpeg",
                    "video-compress rec.mov --screenshare -o rec.mp4"),
        ],
    ),
]

COMMANDS: dict[str, Command] = {cmd.name: cmd for _, cmds in GROUPS for cmd in cmds}

HELP_FLAGS = {"-h", "--help"}


def _version() -> str:
    try:
        return version("pdf-tools")
    except PackageNotFoundError:
        return "unknown"


def overview() -> str:
    width = max(len(name) for name in COMMANDS)
    lines = [
        f"{PROG} {_version()}: offline tools for PDFs, images and videos.",
        "",
        f"Usage: {PROG} <command> [options]",
    ]
    for group, cmds in GROUPS:
        lines += ["", f"{group}:"]
        lines += [f"  {cmd.name:<{width}}  {cmd.summary}" for cmd in cmds]
    lines += [
        "",
        "Examples:",
        *(f"  {PROG} {COMMANDS[name].example}" for name in ("merge", "compress", "redact")),
        "",
        f"Run '{PROG} help <command>' (or '{PROG} <command> --help') for that command's options.",
        "Paths are relative to the current folder. Inputs are never modified; an existing",
        "output file is overwritten.",
    ]
    return "\n".join(lines)


def _unknown(name: str) -> int:
    msg = f"{PROG}: unknown command '{name}'."
    close = difflib.get_close_matches(name, list(COMMANDS), n=1)
    if close:
        msg += f" Did you mean '{close[0]}'?"
    print(f"{msg}\nRun '{PROG}' to list commands.", file=sys.stderr)
    return 2


def run(name: str, args: list[str]) -> int:
    cmd = COMMANDS.get(name)
    if cmd is None:
        return _unknown(name)
    module = importlib.import_module(f"pdf_tools.{cmd.module}")
    # Each tool's argparse reads sys.argv; its first element becomes the usage line.
    sys.argv = [f"{PROG} {cmd.name}", *args]
    return module.main()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in HELP_FLAGS:
        print(overview())
        return 0
    if args[0] in {"-V", "--version"}:
        print(f"{PROG} {_version()}")
        return 0
    if args[0] == "help":
        if len(args) == 1:
            print(overview())
            return 0
        return run(args[1], ["--help"])
    return run(args[0], args[1:])


if __name__ == "__main__":
    sys.exit(main())
