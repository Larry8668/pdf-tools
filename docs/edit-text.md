# Edit text

Fix a word or name in a PDF, such as a misspelled name, without going back to the original document. The new text uses the same font, size, colour and position, and the rest of the line moves over to fit. The original PDF is not modified.

## Steps

**1. Preview the change.** `--dry-run` lists every place that would change and writes nothing:

```bash
pdf-tools edit-text offer.pdf --find "Jon Smith" --replace "John Smith" --dry-run
```

```
Page 1: 'Jon Smith' -> 'John Smith' (Georgia; rest of the line moved to fit)
Page 2: 'Jon Smith' -> 'John Smith' (Georgia; line re-centred)
Document title: 'Offer - Jon Smith' -> 'Offer - John Smith'
Would change 3 place(s)
```

If it says `No match`, copy the text exactly as it appears in the PDF; see [Troubleshooting](#troubleshooting).

**2. Write the fixed copy.**

```bash
pdf-tools edit-text offer.pdf --find "Jon Smith" --replace "John Smith" -o offer-fixed.pdf
```

**3. Check the result.** Open `offer-fixed.pdf`, or render a page to an image:

```bash
pdf-tools render-page offer-fixed.pdf --page 1 -o page-1.png
```

Read any line that says `used instead because ...`: the document's font lacked a letter you needed, so a close standard font was used. That difference can be visible up close.

## Options

| Option | What it does |
| --- | --- |
| `--find TEXT --replace TEXT` | One change. Repeat the pair for several changes at once. |
| `--replace ""` | Delete the text. Include the space (`--find "very "`) to delete it too. |
| `--pages "1,3-4"` | Only these pages. Document properties are then left alone. |
| `--ignore-case` | Match regardless of case. |
| `--dry-run` | Show what would change; write nothing. |
| `-o PATH` | Where to write the edited PDF. |

Every match on the chosen pages is changed.

## What gets changed

- **Page text:** the old letters are removed from the file, not covered up, and the new text is drawn in their place. Everything around it stays the same.
- **Font:** if the document's font contains every letter of the new text, that font is reused and the edit is invisible. Otherwise the closest standard font (Times, Helvetica or Courier, in the same weight and slant) is used, and the output says which letters were missing. Greek, Cyrillic, Chinese, Japanese and Korean work this way too.
- **Fit:** a longer replacement moves the rest of the line right, and centred lines are re-centred. Without room, the new text shrinks slightly (down to 80%), and beyond that you're warned that it overflows.
- **Form fields, title, author, subject, keywords and bookmarks** are fixed too.
- **Leftovers:** if the old text is still somewhere the tool doesn't edit, such as a comment or an attached file, you're warned.

## Troubleshooting

- **`No match`, but you can see the text:** the text may break across two lines; search for the part on one line. The PDF may also be a scan, a picture of text with nothing to edit; the message says so when the pages have no text.
- **Rotated or vertical text** is skipped, with a warning.
- **Signed PDFs:** any edit invalidates a digital signature, so the signer would need to sign again. You're warned when a PDF is signed.
- **Paragraphs don't reflow.** A much longer replacement in a full-width line will be squeezed or overflow; shorten it or edit the source document.
- **"Select all" order:** edited lines are redrawn, so selecting all text in a viewer may list them after the rest of the page. Searching and copying the line itself work normally.

All options: `pdf-tools help edit-text`. Back to the [README](../README.md).
