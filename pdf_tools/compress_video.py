"""Compress videos with FFmpeg without modifying the original file."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from pdf_tools.formatting import format_bytes

logger = logging.getLogger(__name__)

VIDEO_SUFFIXES = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}
OUTPUT_SUFFIXES = {".mkv", ".mov", ".mp4"}
FFMPEG_PRESETS = {
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
}

_SCREENSHARE_MAX_HEIGHT = 1080
_SCREENSHARE_FPS = 30
_DEFAULT_CRF = 28
_DEFAULT_PRESET = "medium"
_AUDIO_BITRATE = "96k"


def compress_video(
    input_video: Path | str,
    output_video: Path | str,
    *,
    crf: int = _DEFAULT_CRF,
    preset: str = _DEFAULT_PRESET,
    screenshare: bool = False,
    max_height: int | None = None,
    fps: float | None = None,
    keep_audio: bool = True,
    start: float | None = None,
    duration: float | None = None,
) -> tuple[int, int]:
    """Write a compressed video copy using FFmpeg.

    Returns ``(input_bytes, output_bytes)``.
    """
    source = Path(input_video).expanduser().resolve()
    out = Path(output_video).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Input video not found: {source}")
    if source.suffix.lower() not in VIDEO_SUFFIXES:
        supported = ", ".join(sorted(VIDEO_SUFFIXES))
        raise ValueError(f"Input must be a video. Supported extensions: {supported}")
    if out.suffix.lower() not in OUTPUT_SUFFIXES:
        supported = ", ".join(sorted(OUTPUT_SUFFIXES))
        raise ValueError(f"Output must be a video. Supported extensions: {supported}")
    if out == source:
        raise ValueError("Output path must be different from the input path.")
    if not 0 <= crf <= 51:
        raise ValueError("CRF must be between 0 (largest) and 51 (smallest).")
    if preset not in FFMPEG_PRESETS:
        allowed = ", ".join(sorted(FFMPEG_PRESETS))
        raise ValueError(f"Unknown FFmpeg preset {preset!r}. Allowed: {allowed}")
    if max_height is not None and max_height <= 0:
        raise ValueError("Max height must be greater than 0.")
    if fps is not None and fps <= 0:
        raise ValueError("FPS must be greater than 0.")
    if start is not None and start < 0:
        raise ValueError("Start must be 0 or greater.")
    if duration is not None and duration <= 0:
        raise ValueError("Duration must be greater than 0.")

    if screenshare:
        if max_height is None:
            max_height = _SCREENSHARE_MAX_HEIGHT
        if fps is None:
            fps = _SCREENSHARE_FPS
        logger.info(
            "Screenshare profile: max height %d, fps %s, CRF %d",
            max_height,
            fps,
            crf,
        )

    ffmpeg = _require_binary("ffmpeg")
    probe = _probe_video(source)
    if probe:
        logger.info("Input video: %s", probe)
    if start is not None or duration is not None:
        logger.info("Encoding a clip only; reported input size is still the full file.")

    input_bytes = source.stat().st_size
    cmd = _build_ffmpeg_command(
        ffmpeg,
        source,
        out,
        crf=crf,
        preset=preset,
        max_height=max_height,
        fps=fps,
        keep_audio=keep_audio,
        start=start,
        duration=duration,
        has_audio=probe.has_audio if probe else True,
    )
    logger.info("Running: %s", " ".join(cmd))
    out.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed with exit code {result.returncode}. "
            "Re-run with -v if you need more detail."
        )
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg did not write an output file: {out}")

    output_bytes = out.stat().st_size
    logger.info(
        "Compressed video: %s -> %s (%.1f%% of original)",
        format_bytes(input_bytes),
        format_bytes(output_bytes),
        (output_bytes / input_bytes) * 100 if input_bytes else 0,
    )
    return input_bytes, output_bytes


class VideoProbe:
    def __init__(
        self,
        *,
        width: int | None,
        height: int | None,
        fps: str | None,
        duration_seconds: float | None,
        has_audio: bool,
        video_codec: str | None,
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.duration_seconds = duration_seconds
        self.has_audio = has_audio
        self.video_codec = video_codec

    def __str__(self) -> str:
        size = ""
        if self.width and self.height:
            size = f"{self.width}x{self.height} "
        fps = f"{self.fps}fps " if self.fps else ""
        codec = self.video_codec or "unknown"
        duration = ""
        if self.duration_seconds is not None:
            minutes = self.duration_seconds / 60
            duration = f", {minutes:.1f} min"
        audio = ", audio" if self.has_audio else ", no audio"
        return f"{size}{fps}{codec}{duration}{audio}"


def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(
            f"{name} was not found on PATH. Install it (for example: brew install ffmpeg)."
        )
    return path


def _probe_video(source: Path) -> VideoProbe | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        logger.warning("ffprobe not found; skipping input probe")
        return None

    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of",
        "json",
        str(source),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("Could not probe video: %s", result.stderr.strip() or "ffprobe failed")
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("Could not parse ffprobe output")
        return None

    streams = payload.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration_raw = (payload.get("format") or {}).get("duration")
    try:
        duration_seconds = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration_seconds = None

    fps = None
    if video_stream:
        rate = video_stream.get("r_frame_rate")
        fps = _format_frame_rate(rate)

    return VideoProbe(
        width=int(video_stream["width"]) if video_stream and video_stream.get("width") else None,
        height=int(video_stream["height"]) if video_stream and video_stream.get("height") else None,
        fps=fps,
        duration_seconds=duration_seconds,
        has_audio=has_audio,
        video_codec=video_stream.get("codec_name") if video_stream else None,
    )


def _build_ffmpeg_command(
    ffmpeg: str,
    source: Path,
    out: Path,
    *,
    crf: int,
    preset: str,
    max_height: int | None,
    fps: float | None,
    keep_audio: bool,
    start: float | None,
    duration: float | None,
    has_audio: bool,
) -> list[str]:
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y"]
    if not logger.isEnabledFor(logging.DEBUG):
        cmd.extend(["-loglevel", "error", "-stats"])
    if start is not None:
        cmd.extend(["-ss", _format_seconds(start)])
    cmd.extend(["-i", str(source)])
    if duration is not None:
        cmd.extend(["-t", _format_seconds(duration)])

    cmd.extend(["-map", "0:v:0", "-c:v", "libx264", "-crf", str(crf), "-preset", preset])
    cmd.extend(["-pix_fmt", "yuv420p"])

    filters = _video_filters(max_height=max_height, fps=fps)
    if filters:
        cmd.extend(["-vf", ",".join(filters)])

    if keep_audio and has_audio:
        cmd.extend(["-map", "0:a:0?", "-c:a", "aac", "-b:a", _AUDIO_BITRATE])
    else:
        cmd.append("-an")

    if out.suffix.lower() in {".mp4", ".mov"}:
        cmd.extend(["-movflags", "+faststart"])

    cmd.append(str(out))
    return cmd


def _video_filters(*, max_height: int | None, fps: float | None) -> list[str]:
    filters: list[str] = []
    if max_height is not None:
        even_height = max_height - (max_height % 2)
        filters.append(f"scale=-2:'min({even_height},ih)'")
    if fps is not None:
        filters.append(f"fps={fps:g}")
    return filters


def _format_frame_rate(rate: object) -> str | None:
    if not rate or rate == "0/0":
        return None
    text = str(rate)
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            value = float(numerator) / float(denominator)
        except (TypeError, ValueError, ZeroDivisionError):
            return text
        return f"{value:g}"
    return text


def _format_seconds(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")
