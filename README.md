# PDF merger

Put PDFs in **`pdfs/`** and images in **`images/`**. The input order controls the output order.

## Run

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

Optional: `uv run pdf-merge ... -v` for debug logs.
