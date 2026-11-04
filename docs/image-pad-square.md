# Pad image to square

Make a rectangular image square by adding black borders. The original image is not modified.

```bash
pdf-tools image-pad-square photo.png -o photo-square.png
```

The output canvas is `max(width, height) x max(width, height)`, with your image centered.

For an exact upload size like 1024×1024:

```bash
pdf-tools image-pad-square photo.png --size 1024 -o photo-1024.png
```

If the image is larger than the target, it is scaled down to fit first, then padded with black borders.

All options: `pdf-tools help image-pad-square`. Back to the [README](../README.md).
