# Compress an image

Create a smaller image copy. The original image is not modified.

```bash
pdf-tools image-compress photo.png --quality 75 -o photo.jpg
```

Optional: cap dimensions while compressing:

```bash
pdf-tools image-compress photo.png --quality 70 --max-width 1600 --max-height 1600 -o photo.jpg
```

JPEG and WebP use `--quality` (default 75). PNG output is lossless and only packed more tightly.

All options: `pdf-tools help image-compress`. Back to the [README](../README.md).
