# Plan: #75 layout for documents without positions (EPUB, Markdown, text)

Thread "Add layout for documents without positions", 13 Nov 2026. Base: `main` 5aad4ae.
Critical (adds golden files, D-69), so no code or tests before the coordinator approves.

## 1. What happens today (measured on main)

`build_document` runs the PDF rules on every document. Lines without a box each become a
PARAGRAPH, pictures without a box become FIGUREs **at the end of their page**, and then the
font rules for headings, captions, lists and footnotes run over them. On the Markdown sample
that gives: the three table header cells "Group", "Listeners", "Minutes" as chapter headings
(bold, short), "1.1 Questions" not a heading, both pictures after the notes at the end, each
list item, code line and table cell a paragraph of its own, and the notes as plain paragraphs.
The EPUB gets one paragraph per line and headings only where the bold-line rule happens to fire.

What extraction hands over (D-306 to D-311, D-340 to D-344), all three formats alike: pages
without positions; one `TextLine` per block element, a line after a `<br>` (or a wrapped line
of a text file) tagged `br`; runs carry their markup as tags (`h2`, `li`, `table`/`td`,
`pre`, `figcaption`, `#id`, `epub:…`, `role:…`, `link:<item>`, `hidden`, …); `Page.order`
keeps where pictures stand between lines; EPUB nav fills `Content.outline` with `item` anchors.

Corpus: EPUB 368 lines (27 continue after `br`), 3 pictures, 18 spine pages; Markdown 37 lines
(2 `br`), 2 pictures; text 20 lines (12 `br`).

## 2. Design

### 2.1 Routing (q1)

A document **none of whose items has a box** is read from its tags by a new module
`layout/tagged.py`; every other document takes today's path unchanged. EPUB, Markdown and
text never have boxes, PDF pages always do, so the seven papers cannot change. Hand-made mixed
content keeps today's behaviour (the existing test for loose items in a PDF stays as is).

### 2.2 Elements

Walk each page's `Page.order` (lines then pictures if it is empty). A line whose runs carry
`br` continues the element before it when the item before it is a line; otherwise it starts a
new element. An element's **context** is the common prefix of its first line's run tags
(without `br`), so an `em` or inline maths inside a paragraph does not change its kind.
Lines of one element are joined with `\n`, as PDF blocks are (text-at-offset invariant holds).

### 2.3 Kinds, in order of precedence

| Context holds | Block |
|---|---|
| `hidden` or `aria-hidden` (whole line) | FURNITURE, role None (q7) |
| `nav` with `epub:toc` / `role:doc-toc` | FURNITURE `contents` |
| `epub:pagebreak` / `role:doc-pagebreak` (whole line) | FURNITURE `page-number` |
| a note: `role:doc-endnote`, `role:doc-footnote`, `epub:endnote`, `epub:footnote`, `epub:rearnote`, `epub:note`, or an `li` inside `role:doc-endnotes` / `epub:endnotes` / `epub:footnotes` / `epub:rearnotes` | FOOTNOTE, one block per note (lines grouped by the note's `#id`; a note of several `<p>` is one block) |
| `table` | TABLE: one block for a run of consecutive table lines; a `caption` line inside it is cut out as a CAPTION placed before it that `describes` it (q8) |
| `svg` (SVG `text`) | FIGURE holding those lines' text |
| `h1`–`h6` | HEADING (levels in 2.4) |
| `figcaption` | CAPTION; `describes` the placeholder right before it, else right after it, else none |
| `role:math` or `math` as the whole line | FORMULA; label = "1" from Markdown's `… (1)` |
| `li` | LIST_ITEM, one per line (q11) |
| anything else (`p`, `blockquote`, `pre`, `div`, `dd`, untagged) | PARAGRAPH; a `pre` keeps its lines (q6) |
| a picture | FIGURE of its own, text "" (q9) |

Labels follow the PDF rules and the core rule that a label is printed in the block's text: a
heading's printed number via the same `_printed_number` ("1.1"), a caption's label via the same
caption pattern ("Table 2"), a note's mark only if the note's text starts with it (q2), list
markers "" (HTML numbering is not in the text).

Notes stay **where the file puts them** (endnotes chapter, end of the Markdown file, an
`aside` after its paragraph): layout does not move text (q10).

### 2.4 Headings, levels and the section tree (q3, q4)

- Levels are counted **per page** (an EPUB spine document; the whole of a Markdown file):
  a page's highest heading rank (`h1` before `h2`) gets the page's base level, each lower rank
  one more, gaps closed (`h1`, `h3` → 1, 2). The base level is the level of the first outline
  entry that points at the page (after the PDF rule 3: a single top entry with entries under
  it, or one titled as the document, is skipped), else the base of the page before, else 1.
  A heading an outline entry points at by `item` takes that entry's level.
- **Where a page has no heading**, each outline entry that points at it makes the section:
  the block holding `entry.item` (or the page's first block) becomes a HEADING if its text is
  the entry's title (compared as in #24), else the section starts at that block without a
  heading block, titled as the entry.
- The tree is built by the existing `_sections`; section titles by the existing `title`.

Corpus result: Time Machine 18 level-1 sections (title page, Imprint, I–XII, Epilogue,
Endnotes, Colophon, Uncopyright); Markdown "Listening to Papers" (1) holding 1 Introduction
(2, holding 1.1 Questions at 3), 2 Method (2), 3 Results (2), exactly the truth; text none.

### 2.5 Output contract

Same `Document` as the PDF path: the same `BlockKind`s, labels, `describes`, `Section`s,
`page_labels` ("" per page), every item in exactly one block. **No core change, no new
setting, no change to other stages.** textprep sees the same shapes it sees from PDF.

## 3. Expected golden-file changes

- **Seven papers: byte-identical** (routing in 2.1; all existing layout, textprep, app and CLI
  goldens unchanged, checked before opening the PR).
- **New** golden of every block, same format as the papers' (kind, label, describes, page,
  graphics, text, then the section tree), in a new `test_layout_tagged_corpus.py` with its own
  `.ambr`, so the papers' snapshot file is not touched:
  - Markdown: 29 blocks from 39 items: 5 HEADING, 13 PARAGRAPH (the fenced code one block
    of 2 lines), 4 LIST_ITEM, 1 TABLE (9 cells), 2 FIGURE (in place, after the table),
    1 FORMULA (display maths), 2 FOOTNOTE; inline maths stays in its sentence.
  - EPUB: 344 blocks from 371 items: 18 HEADING, 3 FIGURE (title page image, two logos),
    1 FOOTNOTE (the endnote, back-link arrow kept as text), 322 PARAGRAPH (colophon lines and
    the uncopyright verse joined at their `br`s).
  - Text: 8 PARAGRAPH blocks (the 8 runs of non-blank lines), no headings, as its truth says.
- Scripts change for the three samples (headings become chapters, table cells one notice, notes
  introduced as notes); no stored golden holds them. `test_app_job.py`'s "Until #75" docstring
  is updated; its asserted sentences still appear.

## 4. Tests

- `test_layout_tagged.py`: one test per row of 2.3 and per rule of 2.4 on hand-made content
  (tables merging, caption cut-out and `describes`, `br` continuation across a picture, note of
  two paragraphs, nested lists, outline base levels, nested nav, outline-only sections,
  single-top-entry skip), plus Hypothesis (`ci`, `nightly`): on any tagged content (random tag
  vocabulary, `br`, pictures, order, outline with items) layout never fails, every item is in
  exactly one block, every HEADING comes from an `h` tag or an outline entry, and the PDF
  strategy's documents with a box anywhere give the same document as before.
- `test_layout_tagged_corpus.py`: truth tests. EPUB: the 13 truth chapters are level-1
  sections in order, the other five sections named in the test; the one endnote is a FOOTNOTE
  whose text is the truth text (U+FEFF and back-link run left out of the comparison) and the
  noteref's `link:` points into it. Markdown: headings with levels and labels; footnotes by
  text, each mark run's link pointing into its FOOTNOTE; 1 TABLE; FIGUREs = the truth alts in
  order; display formula = FORMULA with the truth TeX; inline formula inside its sentence;
  verbatim sentences inside one block. Text: no headings; verbatim sentences (incl. the
  hyphenated one across a line break) inside one block. Plus the three goldens.
- Mutation pass on the new rules (each rule removed in turn makes a test fail), the
  text-at-offset invariant, and a timing check on the EPUB ×100.

Size: about 350 lines in `layout/tagged.py`, 10 in `build.py`, about 600 lines of tests. One PR
(q14): the rules only make sense together and the golden shows them together.

## 5. Alternatives weighed

- **Run the PDF rules on tagged content and add tag checks inside each** (headings.py,
  captions.py, …): touches every PDF module, so the seven goldens are at risk with every rule,
  and the font heuristics keep misfiring on tags (table header cells as headings today).
- **Route by `Source.format`** instead of "no boxes": the same on real files, but hand-made
  content with boxes and format EPUB would fail the boxed rules' assumptions in the opposite
  way; "no positions" is what the issue names.
- **Raw `hN` numbers as levels**: The Time Machine's title page `h1` would hold all twelve
  chapters (`h2`) as children, so the book becomes one chapter.
- **Outline only for EPUB levels**: Markdown has no outline (D-343) and nav often stops at
  chapters, so sub-headings would get no level.

## 6. Questions (my recommendation first)

1. **Routing.** Read a document from its tags when none of its items has a box. Alt: by
   source format.
2. **Note labels.** The mark of a Markdown or EPUB note is not printed in the note's text
   (the `<ol>` numbers it), and core requires a label to be printed, so the label stays "" and
   the noteref's `link:` tag ties mark and note. Consequence: textprep's footnote step (which
   matches labels on the same page and needs `sup`) will still read the marks ("that1") and
   say "Footnote." without number on these files. **File a textprep issue** (use `link:` and
   `role:doc-noteref`/`epub:noteref`, notes on another page, the back-link arrow) and put it in
   v1.0. Alt: relax `Block.label` for notes (core change; helps Markdown only, the EPUB
   endnote is on another page and its mark has no `sup`).
3. **Heading levels** per page from rank, with the outline's level as the page's base (2.4).
4. **Outline only where a page has no heading** (2.4), section start at the entry's block.
5. **Front and back matter** (Standard Ebooks title page, imprint, colophon, uncopyright) is
   read as text under its own headings, each its own chapter. File a v1.1 issue to deselect
   such chapters by default from their `epub:type` (as the reference list is, TP-06). Alt:
   furniture (needs a new `FurnitureRole`, a core change) or leaving them out (not faithful).
6. **Code blocks** (`pre`) are PARAGRAPHs keeping their lines, as code in a PDF is today.
   Alt: a placeholder (not in D-55's list; would need a decision on what is "not read").
7. **Hidden text**: a whole line tagged `hidden` or `aria-hidden` is FURNITURE (role None, so
   a text step leaves it out with a marked edit); a `nav` table of contents in the spine is
   FURNITURE `contents`; a whole-line page-break marker is `page-number`.
8. **Tables**: one TABLE per run of table lines; two tables with nothing between them merge,
   because the tags carry no table identity (accepted; noted in the docstring).
9. **Figures**: each picture its own FIGURE with text "" (the alt text stays on the
   `Picture`); a `figcaption` describes the adjacent placeholder. Should textprep name an
   uncaptioned figure by its alt text? Recommend a v1.1 issue, not part of #75.
10. **Notes stay where the file places them**; nothing moves next to its mark.
11. **Lists**: one LIST_ITEM per line inside an `li`; a multi-paragraph `li` gives several
    items (tags cannot tell one `li` from the next); label "".
12. **Plain text** stays paragraphs only (D-344 and its truth: "1. Introduction" is text).
13. **Goldens** in a new test file with its own snapshot; no truth-file change (the EPUB's
    five non-chapter headings are named in the test).
14. **One PR**, `Closes #75`, label risk:high, lane:layout.
