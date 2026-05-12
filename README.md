# PDF merger

Put the PDFs you want to merge in **`pdfs/`** (any filenames). The input order controls the output order.

## Run

From the project root:

```bash
uv sync
uv run pdf-merge pdfs/first.pdf pdfs/second.pdf pdfs/third.pdf -o pdfs/merged.pdf
```

Use your real names instead of `first.pdf` / `second.pdf` / `third.pdf` / `merged.pdf`. You can pass two or more input PDFs. Paths can be absolute if the files live elsewhere.

Optional: `uv run pdf-merge ... -v` for debug logs.
