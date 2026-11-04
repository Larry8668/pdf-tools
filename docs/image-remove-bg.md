# Remove an image background

Cut the subject out of a photo and save it with a transparent background. The original image is not modified, and the image never leaves your machine.

```bash
pdf-tools image-remove-bg photo.jpg -o photo-no-bg.png
```

The first run downloads the model once (about 220 MB) to `~/.cache/pdf-tools/models`, checks it against a pinned SHA-256, and reuses it from then on. Set `PDF_TOOLS_MODEL_DIR` to keep models somewhere else.

Put the subject on a solid colour, cropped tight, for example for a product listing:

```bash
pdf-tools image-remove-bg photo.jpg --bg-color white --crop -o product.jpg
```

`--bg-color` takes a name like `white` or a hex value like `'#1e90ff'`. Use `.png` or `.webp` to keep transparency; `.jpg` has none, so it gets a white background unless you pick a colour.

Several images at once, written to a folder as `<name>-no-bg.png`:

```bash
pdf-tools image-remove-bg a.jpg b.jpg c.jpg -o no-bg/
```

`--mask-only` writes the black-and-white mask instead of the cutout.

Pick a model with `--model`:

| Model | Download | Time per photo* | Peak memory | Notes |
| --- | --- | --- | --- | --- |
| `birefnet-lite` (default) | 224 MB | ~5 s | ~9 GB | Clean edges on hair, fur and busy backgrounds |
| `birefnet` | 973 MB | ~11 s | ~11 GB | Slightly finer edges; may keep only the main subject |
| `isnet` | 179 MB | ~1.5 s | ~2.5 GB | Fastest; fine for products, weaker on hair and clutter |

\*On an Apple M4 CPU, for a typical photo. On a Mac with 8 GB of memory, use `--model isnet`.

The models are [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) (MIT) and [IS-Net](https://github.com/xuebinqin/DIS) (Apache-2.0), using the ONNX exports published by [rembg](https://github.com/danielgatis/rembg).

All options: `pdf-tools help image-remove-bg`. Back to the [README](../README.md).
