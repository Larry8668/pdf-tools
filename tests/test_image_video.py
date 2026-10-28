"""Image pad/compress, and video compression (skipped without ffmpeg)."""

from __future__ import annotations

import shutil
import subprocess

import pytest
from PIL import Image

from conftest import sha256
from pdf_tools import compress_image, compress_video, pad_image_to_square


# image-pad-square

def test_pad_to_square_centres_image(make_image, tmp_path):
    src = make_image("wide.png", (400, 200), "white")
    out = tmp_path / "sq.png"
    assert pad_image_to_square(src, out) == (400, 200, 400, 400)
    im = Image.open(out)
    assert im.size == (400, 400)
    assert im.getpixel((200, 10)) == (0, 0, 0)       # padding
    assert im.getpixel((200, 200)) == (255, 255, 255)  # original


def test_pad_to_exact_size_scales_down(make_image, tmp_path):
    out = tmp_path / "sq.png"
    pad_image_to_square(make_image(size=(2000, 1000)), out, size=1024)
    assert Image.open(out).size == (1024, 1024)


def test_pad_rejects_same_path_and_bad_size(make_image):
    src = make_image()
    with pytest.raises(ValueError):
        pad_image_to_square(src, src)
    with pytest.raises(ValueError):
        pad_image_to_square(src, src.with_name("o.png"), size=0)


# image-compress

def test_compress_image_to_jpeg(tmp_path, noisy_image):
    src = tmp_path / "photo.png"
    noisy_image.save(src)
    before = sha256(src)
    out = tmp_path / "photo.jpg"
    in_bytes, out_bytes = compress_image(src, out, quality=50, max_width=300)
    assert out_bytes < in_bytes
    assert Image.open(out).size == (300, 200)
    assert sha256(src) == before


def test_compress_image_flattens_transparency_for_jpeg(make_image, tmp_path):
    src = make_image("t.png", color=(255, 0, 0, 0), mode="RGBA")
    out = tmp_path / "t.jpg"
    compress_image(src, out)
    assert Image.open(out).mode == "RGB"


@pytest.mark.parametrize("kwargs", [{"quality": 0}, {"quality": 96}, {"max_width": 0}])
def test_compress_image_rejects_bad_options(make_image, tmp_path, kwargs):
    with pytest.raises(ValueError):
        compress_image(make_image(), tmp_path / "o.jpg", **kwargs)


# video-compress

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@needs_ffmpeg
def test_video_compress(tmp_path):
    src = tmp_path / "in.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc=duration=1:size=640x480:rate=30", str(src)],
        check=True,
    )
    out = tmp_path / "out.mp4"
    compress_video(src, out, screenshare=True, max_height=240, keep_audio=False)
    assert out.stat().st_size > 0


def test_video_rejects_bad_options(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    with pytest.raises(ValueError):
        compress_video(src, tmp_path / "out.mp4", crf=99)
    with pytest.raises(ValueError):
        compress_video(src, tmp_path / "out.gif")
