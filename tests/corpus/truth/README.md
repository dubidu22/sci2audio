# Ground truth for the sample corpus

One hand-checked file per corpus file says what a listener should get from it (D-60). It comes from
no code at all: Claude drafts it from the PDF or EPUB, Colin checks it against the file. Extraction
and layout tests compare their output with it; it is written before that code exists.

`tests/unit/test_corpus_truth.py` checks every file against the format below and that each corpus
file has exactly one truth file.

## What the truth describes

The **reading result**, not what extraction finds (D-63). Extraction records everything on the
page; the layout stage decides reading order, blocks and sections. So:

- Headings and sentences are given in reading order, as a reader would follow the page.
- Text that must not be read aloud (running heads, page numbers, line numbers, the arXiv side
  stamp, the venue footer on page 1) is listed as **furniture**. After layout it must sit in
  `furniture` blocks only; in the listening script it must not appear at all.
- Counts describe what is printed, so they hold whatever the layout stage decides about blocks.

## File name and format

`tests/corpus/truth/<corpus file name without extension>.toml`, e.g.
`acl2023-nowak-prefix-probabilities.toml` for `papers/acl2023-nowak-prefix-probabilities.pdf`.
TOML is read with Python's built-in `tomllib`, so no dependency is needed. Comments (`#`) are
welcome wherever a reviewer needs a reason.

Text is written as printed, with the file's own Unicode punctuation (’ “ ” – —). Line breaks inside
a sentence become one space; a hyphen at a line end is dropped when it only splits a word
("subop-/timal" becomes "suboptimal") and kept when the word is really hyphenated.

### Keys for every file

| Key | Type | Meaning |
|---|---|---|
| `file` | string | Path of the corpus file below `tests/corpus/`, e.g. `papers/x.pdf` |
| `drafted_from` | list of strings | What the draft was made from: `pdf`, `epub`, `latex` (arXiv source), `markdown` (JOSS source). Author sources are only a check; they are never added to the repo |
| `title` | string | The title as printed |

### Papers (`papers/*.pdf`)

| Key | Type | Meaning |
|---|---|---|
| `pages` | integer | Number of pages |
| `columns` | list of 1 or 2 | Text columns on each page, one entry per page. A page with a full-width float or formula above two columns counts as 2 |
| `headings` | list of `{ level, text }` | Every heading in reading order, from "Abstract" to the last appendix heading. `level` 1 = section (also Abstract, References, unnumbered end sections, appendices), 2 = subsection, 3 = sub-subsection. `text` includes the printed number, e.g. "2.1 Setup". Paragraph run-in heads ("Proof.", "Definition 1.") are not headings |
| `counts.footnotes` | integer | Footnotes printed at the foot of a page (by their marks; a JOSS reference list is not footnotes) |
| `counts.tables` | integer | Tables with a "Table N" caption, plus uncaptioned tables |
| `counts.figures` | integer | Figures with a "Figure N" caption, plus uncaptioned images and charts. Logos and icons are not figures |
| `counts.algorithms` | integer | Pseudocode blocks ("Algorithm N"), also those inside a figure. Optional, 0 when left out |
| `counts.numbered_formulas` | integer | Equation numbers printed next to display formulas. A display spanning several lines under one number counts once; (16a) to (16f) count six times; an equation restated in an appendix with its number counts again |
| `counts.unnumbered_formulas` | integer | Display formulas set apart from the text without a number |
| `verbatim` | list of tables, 3 to 5 | Sentences that must come out word for word (see below) |
| `furniture` | list of tables | Text that must not be read aloud (see below) |

Each `[[verbatim]]` entry:

| Key | Type | Meaning |
|---|---|---|
| `where` | string | `plain`, `column-break` (the sentence runs from one column into the next), `page-break` (runs onto the next page) or `hyphenation` (a word in it is split across lines with a hyphen) |
| `page` | integer | Page where it starts, counted from 1 |
| `text` | string | The sentence. Where a sentence holds inline maths, a fragment of at least six words without maths is used instead, and a comment says so |

Include one `column-break`, one `page-break` and one `hyphenation` entry where the paper has them.

Each `furniture` entry (an inline table, one per line):

| Key | Type | Meaning |
|---|---|---|
| `kind` | string | `running-head`, `page-number`, `line-number`, `side-stamp` (e.g. the arXiv id along the margin) or `footer` (venue or licence lines) |
| `pages` | list of integers | Pages it appears on, counted from 1 |
| `text` | string | The text as printed on those pages. Tying it to pages keeps short strings such as a page number checkable |

### EPUB (`epub/*.epub`)

| Key | Type | Meaning |
|---|---|---|
| `chapters` | list of strings | Chapter titles in reading order, as printed |
| `endnotes` | list of `{ chapter, text }` | Each endnote: the chapter title it is referenced from, and its text |

## Drafting and checking

1. Claude drafts the file from the corpus file, using the author's source (arXiv LaTeX, JOSS
   Markdown) where it is openly available as a check.
2. Colin checks it against the PDF or EPUB and ticks it in the pull request.
3. A later change to a truth file needs the same check, and the PR says why the old value was wrong.
