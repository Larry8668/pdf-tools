# Redact an area or image block

Render a page preview first:

```bash
pdf-tools render-page input.pdf --page 1 -o page-1.png
```

The command prints the PDF size, image size, and render scale. Open the PNG and note the rectangle pixel coordinates for the area you want to hide.

For easier coordinate picking, render with a labeled grid:

```bash
pdf-tools render-page input.pdf --page 1 --grid-size 100 -o page-1-grid.png
```

Use a smaller grid size, like `--grid-size 50`, when you need a tighter estimate.

Then redact that rectangle:

```bash
pdf-tools redact-area input.pdf --page 1 --pixels "200,300,600,420" --scale 2 -o redacted.pdf
```

Pixel coordinates use `x0,y0,x1,y1` from the rendered preview. The `--scale` value should match the scale printed by `pdf-tools render-page`.

You can also use direct PDF-point coordinates:

```bash
pdf-tools redact-area input.pdf --area "1:100,150,300,210" -o redacted.pdf
```

By default, areas are blacked out. Use `--mode remove` or `--mode white` for a blank white area.

All options: `pdf-tools help redact-area`. Back to the [README](../README.md).
