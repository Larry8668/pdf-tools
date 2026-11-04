# Compress a video

Requires `ffmpeg` on your PATH (`brew install ffmpeg`). The original video is not modified.

```bash
pdf-tools video-compress input.mov --screenshare -o input-compressed.mp4
```

`--screenshare` scales height to at most 1080 and uses 30 fps. That is the right default for UI recordings.

Or set the knobs yourself:

```bash
pdf-tools video-compress input.mov --crf 28 --preset medium --max-height 1080 --fps 30 -o input-compressed.mp4
```

Lower CRF keeps more quality (and a larger file). `--crf 32` is smaller; `--crf 24` is sharper.

Drop the soundtrack:

```bash
pdf-tools video-compress input.mov --screenshare --no-audio -o input-compressed.mp4
```

Supported video types: `.avi`, `.m4v`, `.mkv`, `.mov`, `.mp4`, `.mpeg`, `.mpg`, `.webm`. Output is `.mp4`, `.mov`, or `.mkv`.

All options: `pdf-tools help video-compress`. Back to the [README](../README.md).
