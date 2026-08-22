# PDF tools

Put PDFs in **`pdfs/`**, images in **`images/`**, and videos in **`videos/`**. The input order controls the output order for merge.

## Setup

Requires Python and `uv`. Video compression also needs `ffmpeg` on your PATH (`brew install ffmpeg`).

```bash
uv sync
```

## Merge or convert

From the project root:

```bash
uv run pdf-merge pdfs/first.pdf images/photo.png pdfs/second.pdf -o pdfs/merged.pdf
```

Use your real names instead of `first.pdf` / `photo.png` / `second.pdf` / `merged.pdf`. You can pass one or more inputs, mixing PDFs and images in any order.

To convert a single image into a PDF:

```bash
uv run pdf-merge images/photo.png -o pdfs/photo.pdf
```

Supported image types: `.bmp`, `.gif`, `.jpeg`, `.jpg`, `.png`, `.tif`, `.tiff`, `.webp`.

## Pad image to square

Make a rectangular image square by adding black borders. The original image is not modified.

```bash
uv run image-pad-square images/photo.png -o images/photo-square.png
```

The output canvas is `max(width, height) x max(width, height)`, with your image centered.

For an exact upload size like 1024×1024:

```bash
uv run image-pad-square images/photo.png --size 1024 -o images/photo-1024.png
```

If the image is larger than the target, it is scaled down to fit first, then padded with black borders.

The output path must be different from the input path.

## Compress

Create a smaller PDF copy. The original PDF is not modified.

Target a percentage of the original file size:

```bash
uv run pdf-compress pdfs/input.pdf --size-percent 10 -o pdfs/compressed.pdf
```

The example above aims for about 10% of the input size, so roughly 100 KB from a 1 MB file.

Or set image quality directly:

```bash
uv run pdf-compress pdfs/input.pdf --image-quality 30 -o pdfs/compressed.pdf
```

Best results come from image-heavy PDFs. Text-only PDFs may not shrink much.

The output path must be different from the input path, so commands cannot overwrite the original PDF.

## Compress an image

Create a smaller image copy. The original image is not modified.

```bash
uv run image-compress images/photo.png --quality 75 -o images/photo.jpg
```

Optional: cap dimensions while compressing:

```bash
uv run image-compress images/photo.png --quality 70 --max-width 1600 --max-height 1600 -o images/photo.jpg
```

JPEG and WebP use `--quality` (default 75). PNG output is lossless and only packed more tightly.

The output path must be different from the input path.

## Compress a video

Requires `ffmpeg` on your PATH (`brew install ffmpeg`). The original video is not modified.

```bash
uv run video-compress videos/input.mov --screenshare -o videos/input-compressed.mp4
```

`--screenshare` scales height to at most 1080 and uses 30 fps. That is the right default for UI recordings.

Or set the knobs yourself:

```bash
uv run video-compress videos/input.mov --crf 28 --preset medium --max-height 1080 --fps 30 -o videos/input-compressed.mp4
```

Lower CRF keeps more quality (and a larger file). `--crf 32` is smaller; `--crf 24` is sharper.

Drop the soundtrack:

```bash
uv run video-compress videos/input.mov --screenshare --no-audio -o videos/input-compressed.mp4
```

Supported video types: `.avi`, `.m4v`, `.mkv`, `.mov`, `.mp4`, `.mpeg`, `.mpg`, `.webm`. Output is `.mp4`, `.mov`, or `.mkv`.

The output path must be different from the input path.

## Remove pages

Create a new PDF with selected pages removed. The original PDF is not modified.

```bash
uv run pdf-remove-pages pdfs/input.pdf --pages "1,3,5-7" -o pdfs/output.pdf
```

Page numbers are 1-based. The example removes pages 1, 3, 5, 6, and 7.

The output path must be different from the input path, so commands cannot overwrite the original PDF.

## Redact searchable text

Create a new PDF with matching text redacted. The original PDF is not modified.

```bash
uv run pdf-redact pdfs/input.pdf --term "secret name" --term "account number" -o pdfs/redacted.pdf
```

For a list of terms, use a comma-separated list:

```bash
uv run pdf-redact pdfs/input.pdf --terms "secret name,account number,email@example.com" -o pdfs/redacted.pdf
```

Or put terms in a text file, one per line:

```bash
uv run pdf-redact pdfs/input.pdf --terms-file terms.txt -o pdfs/redacted.pdf
```

Blank lines are ignored. Lines starting with `#` are treated as comments.

By default, matches are blacked out. You can also remove text visually with a white blank area:

```bash
uv run pdf-redact pdfs/input.pdf --term "secret name" --mode remove -o pdfs/redacted.pdf
```

Or replace matching text with another label:

```bash
uv run pdf-redact pdfs/input.pdf --term "secret name" --replacement "REDACTED" -o pdfs/redacted.pdf
```

This works on searchable/text PDFs. Scanned PDFs or image-only PDFs may not work unless they have an OCR text layer.

The output path must be different from the input path, so commands cannot overwrite the original PDF.

## Redact an area or image block

Render a page preview first:

```bash
uv run pdf-render-page pdfs/input.pdf --page 1 -o previews/page-1.png
```

The command prints the PDF size, image size, and render scale. Open the PNG and note the rectangle pixel coordinates for the area you want to hide.

For easier coordinate picking, render with a labeled grid:

```bash
uv run pdf-render-page pdfs/input.pdf --page 1 --grid-size 100 -o previews/page-1-grid.png
```

Use a smaller grid size, like `--grid-size 50`, when you need a tighter estimate.

Then redact that rectangle:

```bash
uv run pdf-redact-area pdfs/input.pdf --page 1 --pixels "200,300,600,420" --scale 2 -o pdfs/redacted.pdf
```

Pixel coordinates use `x0,y0,x1,y1` from the rendered preview. The `--scale` value should match the scale printed by `pdf-render-page`.

You can also use direct PDF-point coordinates:

```bash
uv run pdf-redact-area pdfs/input.pdf --area "1:100,150,300,210" -o pdfs/redacted.pdf
```

By default, areas are blacked out. Use `--mode remove` or `--mode white` for a blank white area.

The output path must be different from the input path, so commands cannot overwrite the original PDF.

Optional: add `-v` to any command for debug logs.
