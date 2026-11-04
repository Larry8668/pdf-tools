# Merge or convert

The input order is the page order in the output.

```bash
pdf-tools merge first.pdf photo.png second.pdf -o merged.pdf
```

Use your real names instead of `first.pdf` / `photo.png` / `second.pdf` / `merged.pdf`. You can pass one or more inputs, mixing PDFs and images in any order.

To convert a single image into a PDF:

```bash
pdf-tools merge photo.png -o photo.pdf
```

Supported image types: `.bmp`, `.gif`, `.jpeg`, `.jpg`, `.png`, `.tif`, `.tiff`, `.webp`.

All options: `pdf-tools help merge`. Back to the [README](../README.md).
