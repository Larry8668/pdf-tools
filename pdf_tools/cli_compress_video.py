"""CLI: compress a video into a new smaller output video."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.compress_video import FFMPEG_PRESETS, compress_video
from pdf_tools.formatting import format_bytes


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compress a video with FFmpeg and write a new smaller video.",
    )
    p.add_argument("input", type=Path, help="Input video path")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path for the compressed video",
    )
    p.add_argument(
        "--crf",
        type=int,
        default=28,
        help="x264 quality from 0 (largest) to 51 (smallest). Default: 28.",
    )
    p.add_argument(
        "--preset",
        choices=sorted(FFMPEG_PRESETS),
        default="medium",
        help="x264 speed/size tradeoff. Default: medium.",
    )
    p.add_argument(
        "--screenshare",
        action="store_true",
        help="Use screenshare defaults: max height 1080 and 30 fps unless overridden.",
    )
    p.add_argument(
        "--max-height",
        type=int,
        help="Scale down so height is at most this many pixels.",
    )
    p.add_argument(
        "--fps",
        type=float,
        help="Output frame rate. Use 24 or 30 for typical screenshares.",
    )
    p.add_argument(
        "--no-audio",
        action="store_true",
        help="Drop the audio track.",
    )
    p.add_argument(
        "--start",
        type=float,
        help="Start encoding at this many seconds.",
    )
    p.add_argument(
        "--duration",
        type=float,
        help="Encode only this many seconds from the start point.",
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
        input_bytes, output_bytes = compress_video(
            args.input,
            args.output,
            crf=args.crf,
            preset=args.preset,
            screenshare=args.screenshare,
            max_height=args.max_height,
            fps=args.fps,
            keep_audio=not args.no_audio,
            start=args.start,
            duration=args.duration,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read or write files: %s", e)
        return 1

    print(
        f"Compressed: {format_bytes(input_bytes)} -> {format_bytes(output_bytes)} "
        f"({output_bytes / input_bytes * 100:.1f}% of original)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
