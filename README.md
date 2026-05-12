# PDF tools

Put PDFs in **`pdfs/`** and images in **`images/`**. The input order controls the output order.

## Setup

Requires Python and `uv`.

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
