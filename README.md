# PDF tools

Offline command-line tools for PDFs, images and videos. Everything runs on your machine; nothing is uploaded.

Everything is one command, `pdf-tools`, followed by what you want to do:

| Command | What it does |
| --- | --- |
| `pdf-tools merge` | Merge PDFs and images into one PDF, or turn an image into a PDF |
| `pdf-tools compress` | Shrink a PDF by recompressing its images |
| `pdf-tools remove-pages` | Drop pages from a PDF |
| `pdf-tools redact` | Remove searchable text, such as names or account numbers |
| `pdf-tools render-page` | Render a page to an image, optionally with a pixel grid |
| `pdf-tools redact-area` | Black out or blank a rectangle, such as a signature or photo |
| `pdf-tools image-pad-square` | Pad an image to a square, for avatar or upload size limits |
| `pdf-tools image-compress` | Shrink an image, optionally capping its dimensions |
| `pdf-tools image-remove-bg` | Remove the background from a photo, like remove.bg but on your machine |
| `pdf-tools video-compress` | Shrink a video with FFmpeg, with a screen-recording preset |

## Help

```bash
pdf-tools                  # list every command, with examples
pdf-tools help redact      # options for one command
pdf-tools redact --help    # same thing
pdf-tools --version
```

A mistyped command suggests the closest one, for example `pdf-tools mrge` asks whether you meant `merge`.

## Install

### Homebrew (macOS)

```bash
brew tap Larry8668/pdf-tools
brew trust Larry8668/pdf-tools     # Homebrew 7+: third-party taps must be trusted
brew install pdf-tools
```

This puts `pdf-tools` on your PATH and installs `ffmpeg` and Python 3.13 as dependencies, if you don't have them. Update with `brew upgrade pdf-tools`.

Upgrading from 0.1.0: the separate `pdf-merge`, `pdf-redact`, … commands were replaced by `pdf-tools merge`, `pdf-tools redact`, …, with the same options.

### From source

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/). `pdf-tools video-compress` also needs `ffmpeg` on your PATH (`brew install ffmpeg`).

```bash
git clone https://github.com/Larry8668/pdf-tools.git
cd pdf-tools
uv sync
```

From a source checkout, put `uv run` in front of every command in this README, for example `uv run pdf-tools merge ...`.

## Where files go

There is no fixed folder. Every input and output path is relative to the folder you run the command in, and you can also give absolute paths or `~/...`.

- **Output folders are created for you.** `-o out/merged.pdf` writes `./out/merged.pdf`, creating `out/` if it doesn't exist.
- **An existing output file is overwritten without asking.** Pick a new name if you want to keep the old one.
- **The input is never modified.** Every command writes a new file, and refuses an output path that points at its input, even when spelled differently (for example `./a.pdf` and `a.pdf`).

The repo has empty `pdfs/`, `images/`, `videos/` and `previews/` folders, ignored by git, for keeping your files out of commits in a source checkout. The examples below use them, but they're only a convention: with a Homebrew install, run the commands wherever your files are.

## Merge or convert

The input order is the page order in the output.

```bash
pdf-tools merge pdfs/first.pdf images/photo.png pdfs/second.pdf -o pdfs/merged.pdf
```

Use your real names instead of `first.pdf` / `photo.png` / `second.pdf` / `merged.pdf`. You can pass one or more inputs, mixing PDFs and images in any order.

To convert a single image into a PDF:

```bash
pdf-tools merge images/photo.png -o pdfs/photo.pdf
```

Supported image types: `.bmp`, `.gif`, `.jpeg`, `.jpg`, `.png`, `.tif`, `.tiff`, `.webp`.

## Pad image to square

Make a rectangular image square by adding black borders. The original image is not modified.

```bash
pdf-tools image-pad-square images/photo.png -o images/photo-square.png
```

The output canvas is `max(width, height) x max(width, height)`, with your image centered.

For an exact upload size like 1024×1024:

```bash
pdf-tools image-pad-square images/photo.png --size 1024 -o images/photo-1024.png
```

If the image is larger than the target, it is scaled down to fit first, then padded with black borders.

The output path must be different from the input path.

## Compress

Create a smaller PDF copy. The original PDF is not modified.

Target a percentage of the original file size:

```bash
pdf-tools compress pdfs/input.pdf --size-percent 10 -o pdfs/compressed.pdf
```

The example above aims for about 10% of the input size, so roughly 100 KB from a 1 MB file.

Or set image quality directly:

```bash
pdf-tools compress pdfs/input.pdf --image-quality 30 -o pdfs/compressed.pdf
```

Best results come from image-heavy PDFs. Text-only PDFs may not shrink much.

The output path must be different from the input path, so commands cannot overwrite the original PDF.

## Compress an image

Create a smaller image copy. The original image is not modified.

```bash
pdf-tools image-compress images/photo.png --quality 75 -o images/photo.jpg
```

Optional: cap dimensions while compressing:

```bash
pdf-tools image-compress images/photo.png --quality 70 --max-width 1600 --max-height 1600 -o images/photo.jpg
```

JPEG and WebP use `--quality` (default 75). PNG output is lossless and only packed more tightly.

The output path must be different from the input path.

## Remove an image background

Cut the subject out of a photo and save it with a transparent background. The original image is not modified, and the image never leaves your machine.

```bash
pdf-tools image-remove-bg images/photo.jpg -o images/photo-no-bg.png
```

The first run downloads the model once (about 220 MB) to `~/.cache/pdf-tools/models`, checks it against a pinned SHA-256, and reuses it from then on. Set `PDF_TOOLS_MODEL_DIR` to keep models somewhere else.

Put the subject on a solid colour, cropped tight, for example for a product listing:

```bash
pdf-tools image-remove-bg images/photo.jpg --bg-color white --crop -o images/product.jpg
```

`--bg-color` takes a name like `white` or a hex value like `'#1e90ff'`. Use `.png` or `.webp` to keep transparency; `.jpg` has none, so it gets a white background unless you pick a colour.

Several images at once, written to a folder as `<name>-no-bg.png`:

```bash
pdf-tools image-remove-bg images/a.jpg images/b.jpg images/c.jpg -o images/no-bg/
```

`--mask-only` writes the black-and-white mask instead of the cutout.

Pick a model with `--model`:

| Model | Download | Time per photo* | Peak memory | Notes |
| --- | --- | --- | --- | --- |
| `birefnet-lite` (default) | 224 MB | ~5 s | ~9 GB | Clean edges on hair, fur and busy backgrounds |
| `birefnet` | 973 MB | ~11 s | ~11 GB | Slightly finer edges; may keep only the main subject |
| `isnet` | 179 MB | ~1.5 s | ~2.5 GB | Fastest; fine for products, weaker on hair and clutter |

\*On an Apple M4 CPU, for a typical photo. On a Mac with 8 GB of memory, use `--model isnet`.

The models are [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) (MIT) and [IS-Net](https://github.com/xuebinqin/DIS) (Apache-2.0), using the ONNX exports published by [rembg](https://github.com/danielgatis/rembg).

## Compress a video

Requires `ffmpeg` on your PATH (`brew install ffmpeg`). The original video is not modified.

```bash
pdf-tools video-compress videos/input.mov --screenshare -o videos/input-compressed.mp4
```

`--screenshare` scales height to at most 1080 and uses 30 fps. That is the right default for UI recordings.

Or set the knobs yourself:

```bash
pdf-tools video-compress videos/input.mov --crf 28 --preset medium --max-height 1080 --fps 30 -o videos/input-compressed.mp4
```

Lower CRF keeps more quality (and a larger file). `--crf 32` is smaller; `--crf 24` is sharper.

Drop the soundtrack:

```bash
pdf-tools video-compress videos/input.mov --screenshare --no-audio -o videos/input-compressed.mp4
```

Supported video types: `.avi`, `.m4v`, `.mkv`, `.mov`, `.mp4`, `.mpeg`, `.mpg`, `.webm`. Output is `.mp4`, `.mov`, or `.mkv`.

The output path must be different from the input path.

## Remove pages

Create a new PDF with selected pages removed. The original PDF is not modified.

```bash
pdf-tools remove-pages pdfs/input.pdf --pages "1,3,5-7" -o pdfs/output.pdf
```

Page numbers are 1-based. The example removes pages 1, 3, 5, 6, and 7.

The output path must be different from the input path, so commands cannot overwrite the original PDF.

## Redact searchable text

Create a new PDF with matching text redacted. The original PDF is not modified.

```bash
pdf-tools redact pdfs/input.pdf --term "secret name" --term "account number" -o pdfs/redacted.pdf
```

For a list of terms, use a comma-separated list:

```bash
pdf-tools redact pdfs/input.pdf --terms "secret name,account number,email@example.com" -o pdfs/redacted.pdf
```

Or put terms in a text file, one per line:

```bash
pdf-tools redact pdfs/input.pdf --terms-file terms.txt -o pdfs/redacted.pdf
```

Blank lines are ignored. Lines starting with `#` are treated as comments.

By default, matches are blacked out. You can also remove text visually with a white blank area:

```bash
pdf-tools redact pdfs/input.pdf --term "secret name" --mode remove -o pdfs/redacted.pdf
```

Or replace matching text with another label:

```bash
pdf-tools redact pdfs/input.pdf --term "secret name" --replacement "REDACTED" -o pdfs/redacted.pdf
```

This works on searchable/text PDFs. Scanned PDFs or image-only PDFs may not work unless they have an OCR text layer.

The output path must be different from the input path, so commands cannot overwrite the original PDF.

## Redact an area or image block

Render a page preview first:

```bash
pdf-tools render-page pdfs/input.pdf --page 1 -o previews/page-1.png
```

The command prints the PDF size, image size, and render scale. Open the PNG and note the rectangle pixel coordinates for the area you want to hide.

For easier coordinate picking, render with a labeled grid:

```bash
pdf-tools render-page pdfs/input.pdf --page 1 --grid-size 100 -o previews/page-1-grid.png
```

Use a smaller grid size, like `--grid-size 50`, when you need a tighter estimate.

Then redact that rectangle:

```bash
pdf-tools redact-area pdfs/input.pdf --page 1 --pixels "200,300,600,420" --scale 2 -o pdfs/redacted.pdf
```

Pixel coordinates use `x0,y0,x1,y1` from the rendered preview. The `--scale` value should match the scale printed by `pdf-tools render-page`.

You can also use direct PDF-point coordinates:

```bash
pdf-tools redact-area pdfs/input.pdf --area "1:100,150,300,210" -o pdfs/redacted.pdf
```

By default, areas are blacked out. Use `--mode remove` or `--mode white` for a blank white area.

The output path must be different from the input path, so commands cannot overwrite the original PDF.

Optional: add `-v` to any command for debug logs.

## Running tests

```bash
uv run pytest
```

Tests build their own small PDFs, images and videos, so no sample files are needed. `video-compress` tests skip without `ffmpeg`. Background removal is tested with a tiny stand-in model; tests against the real models run only when those are already downloaded (run `pdf-tools image-remove-bg` once). GitHub Actions runs the suite on macOS and Linux for every push.

## Changing dependencies

The Homebrew formula installs the exact wheels in `requirements.lock.txt`, checking each hash. After changing dependencies in `pyproject.toml`, refresh both lock files:

```bash
uv lock
uv export --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock.txt
```

To release, tag `vX.Y.Z` (matching `version` in `pyproject.toml`), then update `url` and `sha256` in [homebrew-pdf-tools](https://github.com/Larry8668/homebrew-pdf-tools).
