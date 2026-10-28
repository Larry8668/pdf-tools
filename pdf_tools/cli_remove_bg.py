"""CLI: remove the background from images with a local model."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pdf_tools.remove_bg import DEFAULT_MODEL, MODELS, model_dir, remove_backgrounds


def _parse_args() -> argparse.Namespace:
    models = "\n".join(
        f"  {m.name:<14} ~{m.size_mb} MB. {m.summary}" for m in MODELS.values()
    )
    p = argparse.ArgumentParser(
        description=(
            "Remove the background from images. Runs entirely on this machine; "
            "the model is downloaded once and cached."
        ),
        epilog=(
            f"Models (--model, default {DEFAULT_MODEL}):\n{models}\n\n"
            f"Models are cached in {model_dir()} (set PDF_TOOLS_MODEL_DIR to change).\n\n"
            "Examples:\n"
            "  %(prog)s photo.jpg -o photo.png\n"
            "  %(prog)s photo.jpg --bg-color white --crop -o product.jpg\n"
            "  %(prog)s a.jpg b.jpg c.jpg -o cutouts/"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("inputs", nargs="+", type=Path, help="Input image(s)")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help=(
            "Output image (.png or .webp keep transparency). "
            "With several inputs, a folder: each result is saved as <name>-no-bg.png."
        ),
    )
    p.add_argument(
        "--model",
        choices=list(MODELS),
        default=DEFAULT_MODEL,
        help=f"Segmentation model. Default: {DEFAULT_MODEL}.",
    )
    p.add_argument(
        "--bg-color",
        help="Fill the background with a colour instead of leaving it transparent, "
        "for example white or '#1e90ff'.",
    )
    p.add_argument(
        "--crop",
        action="store_true",
        help="Trim the output to the subject, with a small margin.",
    )
    p.add_argument(
        "--mask-only",
        action="store_true",
        help="Write the black-and-white mask instead of the cutout.",
    )
    p.add_argument(
        "--no-refine",
        action="store_true",
        help="Skip edge colour clean-up (faster, but may leave a halo around hair).",
    )
    p.add_argument(
        "--no-download",
        action="store_true",
        help="Fail instead of downloading a model that is not cached yet.",
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
        results = remove_backgrounds(
            args.inputs,
            args.output,
            model=args.model,
            bg_color=args.bg_color,
            crop=args.crop,
            mask_only=args.mask_only,
            refine_edges=not args.no_refine,
            download=not args.no_download,
        )
    except (FileNotFoundError, ValueError) as e:
        logging.error("%s", e)
        return 1
    except OSError as e:
        logging.error("Could not read, write or download files: %s", e)
        return 1
    except KeyboardInterrupt:
        return 130

    for r in results:
        width, height = r.size
        print(f"Removed background: {r.source.name} -> {r.output} ({width}x{height}, {r.seconds:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
