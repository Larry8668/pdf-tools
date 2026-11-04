# Redact searchable text

Create a new PDF with matching text redacted. The original PDF is not modified.

```bash
pdf-tools redact input.pdf --term "secret name" --term "account number" -o redacted.pdf
```

For a list of terms, use a comma-separated list:

```bash
pdf-tools redact input.pdf --terms "secret name,account number,email@example.com" -o redacted.pdf
```

Or put terms in a text file, one per line:

```bash
pdf-tools redact input.pdf --terms-file terms.txt -o redacted.pdf
```

Blank lines are ignored. Lines starting with `#` are treated as comments.

By default, matches are blacked out. You can also remove text visually with a white blank area:

```bash
pdf-tools redact input.pdf --term "secret name" --mode remove -o redacted.pdf
```

Or replace matching text with another label:

```bash
pdf-tools redact input.pdf --term "secret name" --replacement "REDACTED" -o redacted.pdf
```

This works on searchable/text PDFs. Scanned PDFs or image-only PDFs may not work unless they have an OCR text layer.

All options: `pdf-tools help redact`. Back to the [README](../README.md).
