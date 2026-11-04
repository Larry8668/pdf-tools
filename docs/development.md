# Development

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Larry8668/pdf-tools.git
cd pdf-tools
uv sync
uv run pdf-tools --help
```

The repo has empty `pdfs/`, `images/`, `videos/` and `previews/` folders, ignored by git, for keeping your own files out of commits.

## Running tests

```bash
uv run pytest
```

Tests build their own small PDFs, images and videos, so no sample files are needed. `video-compress` tests skip without `ffmpeg`. Background removal is tested with a tiny stand-in model; tests against the real models run only when those are already downloaded (run `pdf-tools image-remove-bg` once). GitHub Actions runs the suite on macOS and Linux for every push.

## Changing dependencies

The Homebrew formula installs the exact wheels in `requirements.lock.txt`, checking each hash. After changing dependencies in `pyproject.toml`, refresh both lock files:

```bash
uv lock
uv export --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock.txt
```

To release, tag `vX.Y.Z` (matching `version` in `pyproject.toml`), then update `url` and `sha256` in [homebrew-pdf-tools](https://github.com/Larry8668/homebrew-pdf-tools).

Back to the [README](../README.md).
