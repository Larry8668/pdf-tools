"""Remove the background from images with a local segmentation model.

The image never leaves the machine. The model (an ONNX file) is downloaded once
into a cache folder, checked against a pinned SHA-256, and reused from then on.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import time
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageColor, ImageOps, UnidentifiedImageError

from pdf_tools.merge import IMAGE_SUFFIXES

logger = logging.getLogger(__name__)

_RELEASE = "https://github.com/danielgatis/rembg/releases/download/v0.0.0"


@dataclass(frozen=True)
class BgModel:
    name: str
    filename: str
    url: str
    sha256: str
    size_mb: int
    summary: str
    mean: tuple[float, float, float]
    std: tuple[float, float, float]
    # BiRefNet returns logits; IS-Net already returns probabilities.
    sigmoid: bool
    input_size: int = 1024


MODELS: dict[str, BgModel] = {
    m.name: m
    for m in (
        BgModel(
            "birefnet-lite",
            "birefnet-general-lite.onnx",
            f"{_RELEASE}/BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx",
            "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333",
            224,
            "Default. Clean edges on hair, fur and busy backgrounds.",
            (0.485, 0.456, 0.406),
            (0.229, 0.224, 0.225),
            sigmoid=True,
        ),
        BgModel(
            "birefnet",
            "birefnet-general.onnx",
            f"{_RELEASE}/BiRefNet-general-epoch_244.onnx",
            "58f621f00f5d756097615970a88a791584600dcf7c45b18a0a6267535a1ebd3c",
            973,
            "Largest; slightly finer edges, but may keep only the main subject. Slowest.",
            (0.485, 0.456, 0.406),
            (0.229, 0.224, 0.225),
            sigmoid=True,
        ),
        BgModel(
            "isnet",
            "isnet-general-use.onnx",
            f"{_RELEASE}/isnet-general-use.onnx",
            "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a",
            179,
            "Fastest and lightest on memory; good on products, weaker on hair and clutter.",
            (0.5, 0.5, 0.5),
            (1.0, 1.0, 1.0),
            sigmoid=False,
        ),
    )
}
DEFAULT_MODEL = "birefnet-lite"

# Formats that keep transparency. Anything else is flattened onto a background.
_ALPHA_SUFFIXES = {".png", ".webp", ".tif", ".tiff"}
_FLAT_SUFFIXES = {".jpg", ".jpeg", ".bmp"}
OUTPUT_SUFFIXES = _ALPHA_SUFFIXES | _FLAT_SUFFIXES
_FLAT_DEFAULT_BG = (255, 255, 255)


def model_dir() -> Path:
    """Folder that holds downloaded models.

    ``PDF_TOOLS_MODEL_DIR`` wins, then ``$XDG_CACHE_HOME/pdf-tools/models``,
    then ``~/.cache/pdf-tools/models``.
    """
    override = os.environ.get("PDF_TOOLS_MODEL_DIR")
    if override:
        return Path(override).expanduser()
    cache = os.environ.get("XDG_CACHE_HOME") or "~/.cache"
    return Path(cache).expanduser() / "pdf-tools" / "models"


def ensure_model(name: str, *, download: bool = True) -> Path:
    """Return the path of a verified model file, downloading it if needed."""
    model = _get_model(name)
    path = model_dir() / model.filename
    if path.is_file():
        return path
    if not download:
        raise FileNotFoundError(
            f"Model '{name}' is not downloaded yet ({path}). "
            "Run without --no-download to fetch it once."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    print(
        f"Downloading the '{name}' model (~{model.size_mb} MB, one time only) to {path.parent}",
        file=sys.stderr,
    )
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(model.url, timeout=60) as response, open(partial, "wb") as f:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            last_shown = 0.0
            while chunk := response.read(1 << 20):
                f.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                now = time.monotonic()
                if total and sys.stderr.isatty() and now - last_shown > 0.2:
                    print(f"\r  {done * 100 // total:3d}%  {done >> 20} / {total >> 20} MB",
                          end="", file=sys.stderr)
                    last_shown = now
        if sys.stderr.isatty():
            print(file=sys.stderr)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    if digest.hexdigest() != model.sha256:
        partial.unlink(missing_ok=True)
        raise ValueError(
            f"Downloaded model '{name}' failed its checksum; nothing was saved. Try again."
        )
    partial.replace(path)
    return path


@dataclass
class RemoveBgResult:
    source: Path
    output: Path
    size: tuple[int, int]
    seconds: float


class BackgroundRemover:
    """Holds a loaded model so a batch of images pays the load cost once."""

    def __init__(self, model: str = DEFAULT_MODEL, *, download: bool = True) -> None:
        import onnxruntime as ort

        self.model = _get_model(model)
        path = ensure_model(model, download=download)
        options = ort.SessionOptions()
        options.log_severity_level = 3
        # CPU only: Core ML takes minutes to compile BiRefNet on every load, which
        # costs far more than it saves.
        self._session = ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self._input = self._session.get_inputs()[0].name

    def mask(self, image: Image.Image) -> Image.Image:
        """Return the foreground probability as an ``L`` image the size of ``image``."""
        m = self.model
        resized = image.convert("RGB").resize((m.input_size, m.input_size),
                                              Image.Resampling.BILINEAR)
        x = np.asarray(resized, dtype=np.float32) / 255.0
        x = (x - np.array(m.mean, np.float32)) / np.array(m.std, np.float32)
        x = x.transpose(2, 0, 1)[np.newaxis]

        pred = self._session.run(None, {self._input: x})[0][0, 0]
        if m.sigmoid:
            pred = 1.0 / (1.0 + np.exp(-pred))
        pred = np.clip(pred, 0.0, 1.0)

        small = Image.fromarray((pred * 255).round().astype(np.uint8), mode="L")
        return small.resize(image.size, Image.Resampling.BILINEAR)


def remove_backgrounds(
    inputs: Sequence[Path | str],
    output: Path | str,
    *,
    model: str = DEFAULT_MODEL,
    bg_color: str | None = None,
    crop: bool = False,
    mask_only: bool = False,
    refine_edges: bool = True,
    download: bool = True,
) -> list[RemoveBgResult]:
    """Remove the background from one or more images.

    ``output`` is a file when it has an extension and there is one input.
    Otherwise it is a folder and each result is written there as
    ``<name>-no-bg.png``.
    """
    if not inputs:
        raise ValueError("Give at least one input image.")
    sources = [_check_input(p) for p in inputs]
    out = Path(output).expanduser().resolve()
    color = _parse_color(bg_color) if bg_color else None

    if out.suffix and len(sources) == 1:
        targets = [out]
    else:
        if out.suffix:
            raise ValueError(
                "With several inputs, -o must be a folder (for example -o out/), not a file."
            )
        targets = [out / f"{s.stem}-no-bg.png" for s in sources]
        if len(set(targets)) != len(targets):
            raise ValueError("Two inputs share a file name; their outputs would collide.")

    for source, target in zip(sources, targets):
        if target.suffix.lower() not in OUTPUT_SUFFIXES:
            supported = ", ".join(sorted(OUTPUT_SUFFIXES))
            raise ValueError(f"Output must be one of: {supported} (got {target.name})")
        if target == source:
            raise ValueError("Output path must be different from the input path.")
        if target.suffix.lower() in _FLAT_SUFFIXES and color is None and not mask_only:
            logger.info("%s has no transparency; using a white background. "
                        "Save as .png or .webp to keep it transparent, "
                        "or pass --bg-color.", target.name)

    remover = BackgroundRemover(model, download=download)
    results = []
    for source, target in zip(sources, targets):
        start = time.monotonic()
        try:
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened)
                existing_alpha = _existing_alpha(image)
                image = image.convert("RGB")
        except UnidentifiedImageError as e:
            raise ValueError(f"Input image could not be read: {source}") from e

        alpha = remover.mask(image)
        if existing_alpha is not None:
            # Whatever was already transparent stays transparent.
            alpha = ImageChops.multiply(alpha, existing_alpha)
        if mask_only:
            result = alpha
        else:
            result = cutout(image, alpha, refine_edges=refine_edges)
        if crop:
            result = _crop_to_subject(result, alpha)
        if not mask_only:
            flat = color or (_FLAT_DEFAULT_BG if target.suffix.lower() in _FLAT_SUFFIXES else None)
            if flat is not None:
                result = _flatten(result, flat)

        target.parent.mkdir(parents=True, exist_ok=True)
        result.save(target, **_save_options(target))
        seconds = time.monotonic() - start
        logger.debug("%s -> %s in %.1fs", source, target, seconds)
        results.append(RemoveBgResult(source, target, result.size, seconds))
    return results


def cutout(image: Image.Image, alpha: Image.Image, *, refine_edges: bool = True) -> Image.Image:
    """Combine an RGB image and an alpha mask into an RGBA cutout.

    With ``refine_edges``, colours on soft edges (hair, fur, motion blur) are
    re-estimated so the old background does not show as a halo.
    """
    if not refine_edges:
        rgba = image.convert("RGBA")
        rgba.putalpha(alpha)
        return rgba
    rgb = np.asarray(image)
    a = np.asarray(alpha)
    out = np.empty((*a.shape, 4), dtype=np.uint8)
    out[..., 3] = a
    # Work in horizontal strips so a large photo doesn't need gigabytes of float
    # temporaries. A row's result only depends on rows within _REACH of it, so
    # with that much overlap the strips stitch together exactly.
    height = a.shape[0]
    for top in range(0, height, _STRIP_ROWS):
        bottom = min(height, top + _STRIP_ROWS)
        lo, hi = max(0, top - _REACH), min(height, bottom + _REACH)
        fg = estimate_foreground(rgb[lo:hi].astype(np.float32) / 255.0,
                                 a[lo:hi].astype(np.float32) / 255.0)
        out[top:bottom, :, :3] = (fg[top - lo:bottom - lo] * 255.0).round()
    return Image.fromarray(out, mode="RGBA")


_COARSE_RADIUS, _FINE_RADIUS = 90, 6
_REACH = _COARSE_RADIUS + _FINE_RADIUS
_STRIP_ROWS = 512


def estimate_foreground(image: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Recover the un-blended foreground colour at every pixel.

    Blur-fusion estimator from Forte & Pitié, "Approximate Fast Foreground
    Colour Estimation" (ICIP 2021): a coarse pass with a large window, then a
    fine pass seeded with the coarse foreground and background.
    """
    a = alpha[..., np.newaxis]
    fg, bg = _blur_fusion(image, image, image, a, _COARSE_RADIUS)
    fg, _ = _blur_fusion(image, fg, bg, a, _FINE_RADIUS)
    return fg


def _blur_fusion(image, fg, bg, a, r):
    eps = 1e-5
    blurred_a = _box_blur(a, r)
    blurred_fg = _box_blur(fg * a, r) / (blurred_a + eps)
    blurred_bg = _box_blur(bg * (1 - a), r) / ((1 - blurred_a) + eps)
    fg = blurred_fg + a * (image - a * blurred_fg - (1 - a) * blurred_bg)
    return np.clip(fg, 0.0, 1.0), blurred_bg


def _box_blur(arr: np.ndarray, r: int) -> np.ndarray:
    """Mean over a (2r+1) square window, with edges clamped, via summed areas."""
    out = arr
    for axis in (0, 1):
        n = out.shape[axis]
        k = min(r, n - 1)
        pad = [(0, 0)] * out.ndim
        pad[axis] = (k + 1, k)
        csum = np.cumsum(np.pad(out, pad, mode="edge"), axis=axis, dtype=np.float32)
        hi = np.take(csum, np.arange(2 * k + 1, 2 * k + 1 + n), axis=axis)
        lo = np.take(csum, np.arange(0, n), axis=axis)
        out = (hi - lo) / (2 * k + 1)
    return out


def _crop_to_subject(image: Image.Image, alpha: Image.Image) -> Image.Image:
    # Ignore faint haze so a few stray low-alpha pixels don't defeat the crop.
    box = alpha.point(lambda v: 255 if v > 16 else 0).getbbox()
    if box is None:
        logger.warning("No subject found; skipping --crop.")
        return image
    left, top, right, bottom = box
    pad = round(0.02 * max(right - left, bottom - top))
    return image.crop((max(0, left - pad), max(0, top - pad),
                       min(image.width, right + pad), min(image.height, bottom + pad)))


def _flatten(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    background = Image.new("RGB", image.size, color)
    background.paste(image, mask=image.getchannel("A"))
    return background


def _save_options(target: Path) -> dict[str, object]:
    suffix = target.suffix.lower()
    if suffix == ".png":
        return {"optimize": True}
    if suffix == ".webp":
        return {"lossless": True}
    if suffix in {".jpg", ".jpeg"}:
        return {"quality": 92}
    return {}


def _parse_color(value: str) -> tuple[int, int, int]:
    try:
        return ImageColor.getrgb(value)[:3]
    except ValueError as e:
        raise ValueError(
            f"Unknown colour '{value}'. Use a name like white or a hex value like '#1e90ff'."
        ) from e


def _check_input(path: Path | str) -> Path:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input image not found: {source}")
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        supported = ", ".join(sorted(IMAGE_SUFFIXES))
        raise ValueError(f"Input must be an image. Supported extensions: {supported}")
    # Read the header now, so a bad file in a batch fails before any output is written.
    try:
        with Image.open(source):
            pass
    except UnidentifiedImageError as e:
        raise ValueError(f"Input image could not be read: {source}") from e
    return source


def _existing_alpha(image: Image.Image) -> Image.Image | None:
    if image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info:
        return image.convert("RGBA").getchannel("A")
    return None


def _get_model(name: str) -> BgModel:
    try:
        return MODELS[name]
    except KeyError:
        raise ValueError(
            f"Unknown model '{name}'. Choose one of: {', '.join(MODELS)}"
        ) from None

