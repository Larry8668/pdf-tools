# PDF tools

Put PDFs in **`pdfs/`** and images in **`images/`**. The input order controls the output order.

## Merge or convert

From the project root:

```bash
uv sync
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

Optional: add `-v` to either command for debug logs.
