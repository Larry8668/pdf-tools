# PDF tools

Offline command-line tools for PDFs, images and videos. Everything runs on your machine; nothing is uploaded.

## Install

With Homebrew (macOS):

```bash
brew tap Larry8668/pdf-tools
brew trust Larry8668/pdf-tools     # Homebrew 7+: third-party taps must be trusted
brew install pdf-tools
```

This also installs `ffmpeg` and Python 3.13 if you don't have them. Update with `brew upgrade pdf-tools`.

From source, see [Development](docs/development.md), and put `uv run` in front of each command.

## Use

```bash
pdf-tools merge a.pdf photo.png b.pdf -o merged.pdf
pdf-tools edit-text offer.pdf --find "Jon Smith" --replace "John Smith" -o fixed.pdf
pdf-tools                     # list every command, with examples
pdf-tools help edit-text      # options for one command
```

| Command | What it does | Guide |
| --- | --- | --- |
| `merge` | Merge PDFs and images into one PDF, or turn an image into a PDF | [merge](docs/merge.md) |
| `compress` | Shrink a PDF by recompressing its images | [compress](docs/compress.md) |
| `remove-pages` | Drop pages from a PDF | [remove-pages](docs/remove-pages.md) |
| `edit-text` | Fix text in place, such as a misspelled name, in the same font and position | [edit-text](docs/edit-text.md) |
| `redact` | Remove searchable text, such as names or account numbers | [redact](docs/redact.md) |
| `render-page` | Render a page to an image, optionally with a pixel grid | [redact-area](docs/redact-area.md) |
| `redact-area` | Black out or blank a rectangle, such as a signature or photo | [redact-area](docs/redact-area.md) |
| `image-pad-square` | Pad an image to a square, for avatar or upload size limits | [image-pad-square](docs/image-pad-square.md) |
| `image-compress` | Shrink an image, optionally capping its dimensions | [image-compress](docs/image-compress.md) |
| `image-remove-bg` | Remove the background from a photo, like remove.bg but on your machine | [image-remove-bg](docs/image-remove-bg.md) |
| `video-compress` | Shrink a video with FFmpeg, with a screen-recording preset | [video-compress](docs/video-compress.md) |

Paths are relative to the folder you run the command in. Output folders are created for you, and an existing output file is overwritten. The input is never modified: every command writes a new file and refuses an output path that points at its input. Add `-v` to any command for debug logs.

## Development

Tests, dependencies and releases: [docs/development.md](docs/development.md).
