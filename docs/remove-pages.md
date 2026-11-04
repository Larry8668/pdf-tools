# Remove pages

Create a new PDF with selected pages removed. The original PDF is not modified.

```bash
pdf-tools remove-pages input.pdf --pages "1,3,5-7" -o output.pdf
```

Page numbers are 1-based. The example removes pages 1, 3, 5, 6, and 7.

All options: `pdf-tools help remove-pages`. Back to the [README](../README.md).
