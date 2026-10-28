"""Background removal.

Most tests use a tiny stand-in ONNX model (built here with the ``onnx`` package)
that has the same input and output shapes as the real ones: it marks bright
pixels as foreground. That exercises the whole pipeline in milliseconds and
without a 220 MB download. Tests marked ``real_model`` use the actual model and
are skipped unless it is already cached.
"""

from __future__ import annotations

import dataclasses
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from conftest import sha256
from pdf_tools import remove_bg as rb

PDF_TOOLS = Path(sys.executable).parent / "pdf-tools"


def _write_fake_model(path):
    import onnx
    from onnx import TensorProto, helper

    size = rb.MODELS[rb.DEFAULT_MODEL].input_size
    # logits = 10 * mean(normalised RGB): positive for bright pixels, negative for dark.
    graph = helper.make_graph(
        [
            helper.make_node("ReduceMean", ["x"], ["m"], axes=[1], keepdims=1),
            helper.make_node("Mul", ["m", "k"], ["y"]),
        ],
        "fake",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, size, size])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 1, size, size])],
        [helper.make_tensor("k", TensorProto.FLOAT, [], [10.0])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.save(model, path)


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    _write_fake_model(models / rb.MODELS[rb.DEFAULT_MODEL].filename)
    monkeypatch.setenv("PDF_TOOLS_MODEL_DIR", str(models))
    return models


@pytest.fixture
def square_photo(tmp_path):
    """A white square on black: the fake model's foreground is the square."""
    im = Image.new("RGB", (300, 200), "black")
    im.paste((255, 255, 255), (100, 50, 200, 150))
    path = tmp_path / "square.jpg"
    im.save(path, quality=95)
    return path


def _alpha(path):
    return np.asarray(Image.open(path).getchannel("A"))


# end to end with the stand-in model

def test_cutout_is_transparent_outside_subject(fake_model, square_photo, tmp_path):
    before = sha256(square_photo)
    out = tmp_path / "out.png"
    [result] = rb.remove_backgrounds([square_photo], out)
    im = Image.open(out)
    assert im.mode == "RGBA" and im.size == (300, 200) == result.size
    alpha = _alpha(out)
    assert alpha[100, 150] > 240  # inside the square
    assert alpha[10, 10] < 15     # background
    assert sha256(square_photo) == before


def test_bg_color_crop_and_jpeg(fake_model, square_photo, tmp_path):
    out = tmp_path / "out.jpg"
    rb.remove_backgrounds([square_photo], out, bg_color="#1e90ff", crop=True)
    im = Image.open(out)
    assert im.mode == "RGB"
    # Cropped to the 100x100 square plus a small margin.
    assert 100 <= im.width < 120 and 100 <= im.height < 120
    r, g, b = im.getpixel((0, 0))
    assert abs(r - 0x1E) < 20 and abs(g - 0x90) < 20 and abs(b - 0xFF) < 20


def test_jpeg_without_color_gets_white(fake_model, square_photo, tmp_path):
    out = tmp_path / "out.jpg"
    rb.remove_backgrounds([square_photo], out)
    assert min(Image.open(out).getpixel((5, 5))) > 235


def test_mask_only(fake_model, square_photo, tmp_path):
    out = tmp_path / "mask.png"
    rb.remove_backgrounds([square_photo], out, mask_only=True)
    assert Image.open(out).mode == "L"


def test_existing_transparency_is_kept(fake_model, tmp_path):
    im = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
    im.paste((255, 255, 255, 0), (0, 0, 100, 200))  # left half already transparent
    src = tmp_path / "t.png"
    im.save(src)
    out = tmp_path / "out.png"
    rb.remove_backgrounds([src], out)
    alpha = _alpha(out)
    assert alpha[:, :100].max() == 0
    assert alpha[100, 150] > 240


def test_exif_rotation_is_applied(fake_model, square_photo, tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90
    src = tmp_path / "rot.jpg"
    Image.open(square_photo).save(src, exif=exif)
    out = tmp_path / "out.png"
    rb.remove_backgrounds([src], out)
    assert Image.open(out).size == (200, 300)


@pytest.mark.parametrize("mode", ["L", "CMYK", "P", "I;16"])
def test_unusual_input_modes(fake_model, tmp_path, mode):
    im = Image.new("RGB", (64, 48), "white")
    src = tmp_path / ("in.tif" if mode == "CMYK" else "in.png")
    (im.convert("L").convert("I;16") if mode == "I;16" else im.convert(mode)).save(src)
    out = tmp_path / "out.png"
    rb.remove_backgrounds([src], out)
    assert Image.open(out).size == (64, 48)


def test_tiny_and_extreme_sizes(fake_model, tmp_path):
    for size in [(1, 1), (3000, 2)]:
        src = tmp_path / f"{size[0]}x{size[1]}.png"
        Image.new("RGB", size, "white").save(src)
        out = tmp_path / f"out-{size[0]}.png"
        rb.remove_backgrounds([src], out)
        assert Image.open(out).size == size


def test_crop_with_no_subject_keeps_full_image(fake_model, tmp_path):
    src = tmp_path / "dark.png"
    Image.new("RGB", (120, 80), "black").save(src)
    out = tmp_path / "out.png"
    rb.remove_backgrounds([src], out, crop=True)
    assert Image.open(out).size == (120, 80)


def test_batch_writes_to_folder(fake_model, square_photo, tmp_path):
    second = tmp_path / "second.png"
    Image.open(square_photo).save(second)
    results = rb.remove_backgrounds([square_photo, second], tmp_path / "out")
    assert sorted(r.output.name for r in results) == ["second-no-bg.png", "square-no-bg.png"]
    assert all(r.output.is_file() for r in results)


def test_single_input_to_folder(fake_model, square_photo, tmp_path):
    [result] = rb.remove_backgrounds([square_photo], tmp_path / "out")
    assert result.output == (tmp_path / "out" / "square-no-bg.png").resolve()


def test_batch_with_bad_file_writes_nothing(fake_model, square_photo, tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="could not be read"):
        rb.remove_backgrounds([square_photo, bad], tmp_path / "out")
    assert not (tmp_path / "out").exists()


# validation (no model needed: these fail before it loads)

@pytest.mark.parametrize("kwargs, message", [
    ({"output": "x.gif"}, "Output must be"),
    ({"output": "same"}, "different"),
    ({"bg_color": "notacolour"}, "Unknown colour"),
    ({"model": "nope"}, "Unknown model"),
])
def test_rejects_bad_arguments(square_photo, tmp_path, kwargs, message):
    output = kwargs.pop("output", tmp_path / "o.png")
    if output == "same":
        output = square_photo
    elif isinstance(output, str):
        output = tmp_path / output
    with pytest.raises(ValueError, match=message):
        rb.remove_backgrounds([square_photo], output, **kwargs)


def test_several_inputs_need_a_folder(square_photo, tmp_path):
    with pytest.raises(ValueError, match="folder"):
        rb.remove_backgrounds([square_photo, square_photo], tmp_path / "o.png")


def test_missing_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        rb.remove_backgrounds([tmp_path / "nope.jpg"], tmp_path / "o.png")


def test_no_download_when_model_missing(square_photo, tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_TOOLS_MODEL_DIR", str(tmp_path / "empty"))
    with pytest.raises(FileNotFoundError, match="not downloaded"):
        rb.remove_backgrounds([square_photo], tmp_path / "o.png", download=False)


# model download, against a local file:// "server"

def _point_model_at(monkeypatch, tmp_path, payload: bytes, sha: str):
    source = tmp_path / "server.onnx"
    source.write_bytes(payload)
    model = dataclasses.replace(rb.MODELS["isnet"], url=source.as_uri(), sha256=sha)
    monkeypatch.setitem(rb.MODELS, "isnet", model)
    monkeypatch.setenv("PDF_TOOLS_MODEL_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache" / model.filename


def test_download_verifies_and_caches(tmp_path, monkeypatch):
    payload = b"model bytes"
    target = _point_model_at(monkeypatch, tmp_path, payload, hashlib.sha256(payload).hexdigest())
    assert rb.ensure_model("isnet") == target
    assert target.read_bytes() == payload


def test_download_with_bad_checksum_leaves_nothing(tmp_path, monkeypatch):
    target = _point_model_at(monkeypatch, tmp_path, b"tampered", "0" * 64)
    with pytest.raises(ValueError, match="checksum"):
        rb.ensure_model("isnet")
    assert list(target.parent.iterdir()) == []


def test_model_dir_env(monkeypatch, tmp_path):
    monkeypatch.delenv("PDF_TOOLS_MODEL_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert rb.model_dir() == tmp_path / "pdf-tools" / "models"
    monkeypatch.setenv("PDF_TOOLS_MODEL_DIR", "/somewhere")
    assert str(rb.model_dir()) == "/somewhere"


# edge refinement maths

def test_box_blur_matches_brute_force():
    rng = np.random.default_rng(0)
    arr = rng.random((20, 30, 1)).astype(np.float32)
    r = 3
    padded = np.pad(arr, ((r, r), (r, r), (0, 0)), mode="edge")
    expected = np.array([[padded[y:y + 2 * r + 1, x:x + 2 * r + 1].mean(axis=(0, 1))
                          for x in range(30)] for y in range(20)])
    np.testing.assert_allclose(rb._box_blur(arr, r), expected, atol=1e-5)


def test_refinement_removes_background_tint():
    # A red subject on a blue background, with a 12 px soft edge between them.
    h, w = 64, 200
    row = np.clip((112 - np.arange(w)) / 12, 0, 1).astype(np.float32)
    alpha = np.tile(row, (h, 1))
    red, blue = np.array([1, 0, 0], np.float32), np.array([0, 0, 1], np.float32)
    image = alpha[..., None] * red + (1 - alpha[..., None]) * blue
    fg = rb.estimate_foreground(image, alpha)
    edge = (alpha > 0.2) & (alpha < 0.8)
    # Blue leaks into the raw colours on the edge; the estimate should be nearly pure red.
    assert image[edge][:, 2].mean() > 0.3
    assert fg[edge][:, 2].mean() < 0.05


def test_strip_processing_matches_whole_image(monkeypatch):
    rng = np.random.default_rng(1)
    rgb = Image.fromarray((rng.random((700, 50, 3)) * 255).astype(np.uint8))
    alpha = Image.fromarray(np.tile(np.linspace(0, 255, 50).astype(np.uint8), (700, 1)))
    stripped = np.asarray(rb.cutout(rgb, alpha)).astype(int)
    monkeypatch.setattr(rb, "_STRIP_ROWS", 10_000)
    whole = np.asarray(rb.cutout(rgb, alpha)).astype(int)
    visible = np.asarray(alpha) > 12
    assert np.abs(stripped - whole)[visible].max() <= 1


# CLI

def test_cli_end_to_end(fake_model, square_photo, tmp_path):
    out = tmp_path / "cli.png"
    result = subprocess.run(
        [PDF_TOOLS, "image-remove-bg", str(square_photo),
         "-o", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Removed background" in result.stdout
    assert out.is_file()


def test_cli_error_exit_code(tmp_path):
    result = subprocess.run(
        [PDF_TOOLS, "image-remove-bg", str(tmp_path / "nope.jpg"),
         "-o", str(tmp_path / "o.png")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "not found" in result.stderr


# the real models, only when already downloaded

def _cached(name):
    return (rb.model_dir() / rb.MODELS[name].filename).is_file()


@pytest.mark.real_model
@pytest.mark.parametrize("name", list(rb.MODELS))
def test_real_model_separates_subject(name, tmp_path):
    if not _cached(name):
        pytest.skip(f"{name} model not downloaded")
    # A bright disc on a dark, textured background.
    rng = np.random.default_rng(2)
    bg = (rng.random((512, 512, 3)) * 60).astype(np.uint8)
    yy, xx = np.mgrid[:512, :512]
    disc = (yy - 256) ** 2 + (xx - 256) ** 2 < 120 ** 2
    bg[disc] = (230, 120, 40)
    src = tmp_path / "disc.png"
    Image.fromarray(bg).save(src)
    out = tmp_path / "out.png"
    rb.remove_backgrounds([src], out, model=name)
    alpha = _alpha(out)
    assert alpha[256, 256] > 200
    assert alpha[20, 20] < 50
