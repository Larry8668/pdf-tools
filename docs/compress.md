# Compress

Create a smaller PDF copy. The original PDF is not modified.

Target a percentage of the original file size:

```bash
pdf-tools compress input.pdf --size-percent 10 -o compressed.pdf
```

The example above aims for about 10% of the input size, so roughly 100 KB from a 1 MB file.

Or set image quality directly:

```bash
pdf-tools compress input.pdf --image-quality 30 -o compressed.pdf
```

Best results come from image-heavy PDFs. Text-only PDFs may not shrink much.

All options: `pdf-tools help compress`. Back to the [README](../README.md).
