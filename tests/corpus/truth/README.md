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
- Text that must not be read aloud (running heads and footers, page numbers, line numbers, the
  arXiv side stamp, the venue footer on page 1, the JOSS metadata sidebar, a printed table of contents) is
  listed as **furniture**. After layout it must sit in `furniture` blocks only; in the listening script it must not appear at all.
- Footnotes, tables, figures, algorithms and equation numbers are listed with their printed
  labels and pages, so later stages can link references ("see Table 2", "Eq. (9)") and exports
  can name them. They describe what is printed, whatever the layout stage decides about blocks.

## File name and format

`tests/corpus/truth/<corpus file name without extension>.toml`, e.g.
`acl2023-nowak-prefix-probabilities.toml` for `papers/acl2023-nowak-prefix-probabilities.pdf`.
TOML is read with Python's built-in `tomllib`, so no dependency is needed. Comments (`#`) are
welcome wherever a reviewer needs a reason.

Text is written as printed, with the file's own Unicode punctuation (’ “ ” – —). Line breaks inside
a sentence become one space; a hyphen at a line end is dropped when it only splits a word
("subop-/timal" becomes "suboptimal") and kept when the word is really hyphenated. A URL or DOI
broken across lines is joined without a space.

A footnote mark and inline maths (sub- and superscripts, Greek letters, symbols) are written in
line, as the characters the page prints, at the place they stand: "the environment.3" for mark 3
after a full stop, "ObjP" for Obj with subscript P, "the ith row" for i with superscript th.
Symbols and Greek letters are their Unicode characters (∗, σ, ℏ). A space is written only where
the page shows one: as wide as a word space between the two pieces, as in Hardt's "sets. 1"; a
mark or script set close to its neighbour gets none. Where a superscript stands above a
subscript, the superscript is written first. The mark stays in the truth even though a text
step later leaves it out of the script (TP-05): the truth describes what layout reads.

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
| `headings` | list of `{ level, text }` | Every heading in reading order, from "Abstract" to the last appendix heading. `level` 1 = section (also Abstract, References, unnumbered end sections, appendices), 2 = subsection, 3 = sub-subsection. When the appendices sit under a common title ("Supplementary Material: Appendices"), that title is level 1 and each appendix moves one level down. `text` includes the printed number, e.g. "2.1 Setup". Paragraph run-in heads ("Proof.", "Definition 1.", PRL-style "Introduction.") are not headings. Empty when the paper prints no headings, with a comment saying so |
| `footnotes` | list of `{ page, marks }` | Notes printed at the foot of a page below a short rule, by page in reading order, with their marks as printed ("1", "∗"); `""` for a note without a mark. A reference list is not footnotes |
| `tables` | list of `{ page, labels }` | Tables by page in reading order, with their caption labels ("Table 2"); `""` for a table without a caption |
| `figures` | list of `{ page, labels }` | Figures, images and charts by page, with their caption labels ("Figure 1"); `""` for one without a caption. Logos and icons are not figures |
| `algorithms` | list of `{ page, labels }` | Pseudocode blocks ("Algorithm 3") by page, also those inside a figure |
| `formula_numbers` | list of `{ page, numbers }` | The equation numbers printed next to display formulas, as text without brackets ("12", "16a"), in reading order and grouped by page. A display spanning several lines under one number lists it once; a number printed again (an equation restated in an appendix) is listed again. Empty when the paper numbers no formulas |
| `unnumbered_formulas` | list of `{ page, count }` | How many display formulas without a number each page has |

| `verbatim` | list of tables, 3 to 7 | Sentences that must come out word for word (see below) |
| `furniture` | list of tables | Text that must not be read aloud (see below) |

The lists from `footnotes` to `unnumbered_formulas` may be empty. Each names a page at most
once, in page order.

Each `[[verbatim]]` entry:

| Key | Type | Meaning |
|---|---|---|
| `where` | string | `plain`, `column-break` (the sentence runs from one column into the next), `page-break` (runs onto the next page), `hyphenation` (a word in it is split across lines with a hyphen), `footnote-mark` (it holds a footnote mark that the page's `footnotes` list) or `inline-maths` (it holds a sub- or superscript) |
| `page` | integer | Page where it starts, counted from 1 |
| `text` | string | The sentence. Where a sentence runs very long, or holds maths that cannot be written in line (a fraction, a stacked formula), a fragment of at least six words is used instead, and a comment says so |

Include one `column-break`, one `page-break`, one `hyphenation`, one `footnote-mark` and one
`inline-maths` entry where the paper has them, and say in a comment when it has none (#39).

Each `furniture` entry (an inline table, one per line):

| Key | Type | Meaning |
|---|---|---|
| `kind` | string | `running-head` (a line repeated at the top or bottom of pages), `page-number`, `line-number`, `side-stamp` (e.g. the arXiv id along the margin), `footer` (one-off venue or licence lines), `sidebar` (the JOSS metadata column on page 1: DOI, links, editor, reviewers, dates, licence) or `contents` (a printed table of contents, its title and page numbers; chapter navigation replaces it) |
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
