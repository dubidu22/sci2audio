# Plan: Issue #24, outline field and PDF bookmarks as a heading hint

Thread "Add outline field and PDF bookmark headings", 13 Nov 2026. Item 15 of the approved v1.0 plan
(`plans/v1-remaining-plan.md`). Critical: changes the core dataclasses (`sci2audio.core`) and the
extraction golden files. No code or tests before the coordinator approves. D-numbers: the
coordinator assigns them; the questions below are numbered q1 to q12.

## 1. What the corpus shows (measured on main a0d363a, pypdfium2 5.15.2)

| Paper | Outline as stored (level 1 = top, page from 1) | Truth headings | Font rules today |
|---|---|---|---|
| arsiwalla | 5 entries, level 1: "Introduction" p2, "Subjective Meaning in Phenomenology of Experience" p4, "Do Raw Feels Have Subjective Meaning? " p9, "The Formal Structure of Meaning" p11, "Discussion " p18. No numbers, two trailing spaces; Abstract, Acknowledgments, References missing | 8 | 8/8 |
| liu | 3 entries: the paper title (level 1, p1) with "Abstract" (level 2, p1) and "References" (level 2, p4) under it | none (PRL style, nothing printed as a heading) | 0, correct |
| waskom | 6 entries, level 1: Summary, Statement of need, Example, Overview, Acknowledgements, References | 6 | 6/6 |
| biggs | 4 entries, level 1: Summary, Statement of need, Acknowledgements, References | 4 | 4/4 |
| chi, hardt, nowak (ACL) | no outline | | 73/75 overall, the two misses (#48) are in ACL papers |

What follows from it:

- On the corpus the outline would add no heading the font rules miss: all 15 entries that name a
  printed heading already match a HEADING block on their page. The layout use is for PDFs the font
  rules handle worse; on the corpus it must change nothing (layout golden files unchanged).
- Outlines are **partial** (arsiwalla lists 5 of 8 headings), so an entry's absence says nothing:
  the outline may add or confirm, never remove.
- Outline **levels are not reliable as given**: liu's single root is the paper's title, which pushes
  Abstract and References to level 2. Its title is printed on page 1, so matching it naively would
  make the title a heading (the truth says no headings).
- Outline titles **omit printed numbers** ("Introduction" for "1 Introduction") and keep stray
  spaces; matching needs the number off and white space folded.
- A running head can carry the same text ("Introduction" is also furniture on arsiwalla p2), so
  only text blocks may match, never furniture.
- Destination **positions are unreliable**: in waskom and biggs, "Acknowledgements" and
  "References" point at the same spot. Page numbers were right in all 18 entries.
- The KB audit of the old app found "chapters cut by page from the PDF outline; several headings on
  one page become duplicates" (`audit-english-rules-vs-spacy-2026-11-09.md`). So the outline must
  never cut text by page; it can only mark blocks that layout has already built.

## 2. PR split (q1)

**Recommendation: three PRs, one per lane, each merged before the next opens.**

1. **Core** (lane:core, critical): the field.
2. **Extraction** (lane:extraction, critical: changes the extraction golden files): PDF records the outline.
3. **Layout** (lane:layout): headings use it.

The v1.0 plan said two PRs (core, then extraction/layout). `.github/lanes.yml` says a PR changes the
files of its own lane only, and #36 is working in the layout lane now; a separate extraction PR can
land while #36 holds the layout lane, and the layout PR stays small and reviewable on its own.
Alternative not chosen: extraction and layout in one PR (one review fewer, but crosses two lanes and
waits for the layout lane).

## 3. PR 1: core field

```python
@dataclass(frozen=True)
class OutlineEntry:
    """One entry of the file's own outline (PDF bookmarks, later an EPUB's table of contents):
    a hint for the layout stage, not a decision."""
    title: str              # as the file stores it, spaces and all; may be ""
    level: int              # 1 = top; an entry under another is one level deeper
    page: int | None = None # the page it points at (Page.number); None if it points nowhere we have

@dataclass(frozen=True)
class Content:
    source: Source
    pages: tuple[Page, ...]
    metadata: Metadata = field(default_factory=Metadata)
    outline: tuple[OutlineEntry, ...] = ()   # in the file's order; empty when it has none
```

Validation (in `__post_init__`, raising ValueError as the other core objects do): `level >= 1`;
the first entry is at level 1 and each entry is at most one level deeper than the one before (so
the tree is always rebuildable from the flat list); `page` is None or a number of one of
`Content.pages`.

Design questions:

- **q2. Flat tuple with levels, or a nested tree?** Recommend **flat**, in the file's order, with
  the level rule above. Order and nesting are both kept (the tree is the levels), export stays one
  short list, layout matches entry by entry, and EPUB nav (#73) maps onto it directly. Alternative:
  nested entries with `children` like `Section` (mirrors the document tree, but every reader has
  to walk it, and validation of a tree adds no information the level rule doesn't have).
- **q3. Name.** Recommend `OutlineEntry` and `Content.outline`: neutral between PDF bookmarks and
  EPUB's table of contents, and "outline" is the glossary's word. Alternative: `Bookmark` (PDF only).
- **q4. Which fields.** Recommend exactly title, level, page, as the issue's criteria say.
  Not recorded: the destination's position on the page (wrong in 2 of 4 corpus outlines, and no
  stage would read it), colour, bold or italic style, open or closed state. Because the export
  leaves out fields at their default, a field added later (say an EPUB anchor's item id in #73)
  changes no golden file. Alternative: record `top` as well (D-63 says extraction records what the
  file holds; but nothing would use it and it is often wrong).
- **q5. Empty titles and odd characters.** Recommend: keep the title exactly as stored, also `""`
  and trailing spaces (D-64, identifiers and text as printed); layout ignores an entry with no
  letters. Alternative: drop empty entries in extraction (would lose an entry that has children).

Files: `core/content.py` (+ `__init__` export), `tests/unit/test_core_content.py` (examples:
the made-up PAPER gets a two-level outline, EPUB a one-level one; refused values: level 0, first
entry at level 2, a jump of two levels, page 0, page past the last; round trip), the Hypothesis
strategy `core_strategies.contents` draws outlines too (round trip and sorted, repeatable export
already run on it), core golden file `test_core_content.ambr` gains the outline lists (diff
explained in the PR). `CHANGELOG.md` line. Size: about 40 lines of code, 80 of tests.
Nothing else changes: `document.json` in the audio job and the CLI goldens use corpus content,
which has no outline until PR 2.

## 4. PR 2: PDF extraction records the outline

In `extraction/pdf.py`, inside the existing `_PDFIUM` lock, after the pages: walk the bookmark tree
with `PdfDocument.get_toc()` (pypdfium2 5.15.2, already a dependency; it keeps the file's order,
gives the nesting level, and stops at a circular reference with a logged warning).

- **Title**: read with `FPDFBookmark_GetTitle` and decoded from UTF-16 with `errors="replace"`
  (U+FFFD, as extraction already records an unmappable glyph), so a damaged title cannot stop the
  file. Not stripped.
- **Page**: from `FPDFBookmark_GetDest`; if the entry has no `/Dest`, from its action
  (`FPDFBookmark_GetAction` → `FPDFAction_GetDest`, the `/A /GoTo` form many generators write).
  A page index outside the document, a URI or launch action, or no destination gives `None`.
- **Depth (q6)**: recommend keeping pypdfium2's default of 15 levels; deeper entries are left out
  (a real document stops well before; this bounds a hostile file). No count limit: the walk is
  linear in what the file holds, like its pages.
- **Damage never fails the file (q7)**: an outline is a hint, so a broken outline gives what could
  be read and the pages are still recorded. Recommend this over raising `ExtractionError`.

Tests:

- Corpus (`test_extraction_corpus.py`): the expected outline of each of the 4 papers written out in
  the test, entry by entry as stored (titles, levels, pages, as in section 1), and the 3 ACL papers
  give an empty one. Cross-check with the truth files: in arsiwalla, waskom and biggs every outline
  title, with white space folded, is a truth heading with its printed number taken off; liu's three
  entries are named in the test with the reason they are not truth headings (title root, and
  "Abstract" and "References" are bookmarks only, not printed). This is the issue's criterion
  "outline titles match their truth headings, allowing for the printed number"; liu cannot meet it
  literally, so the test says why instead (q8).
- Golden files: `describe()` prints an `outline:` section (one line per entry: level, page, title
  in repr so spaces show) after the metadata line; the 4 papers gain lines, the 3 ACL papers gain
  nothing (the section is left out when empty). Checked against the truth headings above, never
  against old output.
- Made-up PDFs: pypdfium2 cannot write bookmarks, so `pdf_maker.py` gets a small writer for raw PDF
  objects (catalogue, pages with one Helvetica line each, an `/Outlines` tree), with no new
  dependency. Cases: nested entries in order with levels; `/A /GoTo` destination; no destination;
  a destination past the last page; a circular `/Next` (finishes, records the entries once); a
  title in PDFDocEncoding and one in UTF-16 with a byte-order mark; an empty title; no outline at
  all (empty). Alternative not chosen: `pypdf` (BSD-3) as a test dependency to write outlines
  (one more dependency and licence row for about 40 lines of test helper).

Size: about 50 lines of code, 200 of tests. `CHANGELOG.md` line.

## 5. PR 3: layout uses the outline as a heading hint

In `layout/headings.py`, after the font rules have decided (`_Headings.levels()`), one more step
`_outline_headings()`. The rule, written in the module docstring and tested:

1. **The font rules go first and are never undone.** Every heading they find stays, with its level
   and printed number, whatever the outline says. Outlines are often partial (arsiwalla lists 5 of 8
   headings), and the font rules are the ones measured against the truth (73/75).
2. **An outline entry can add a heading the font rules missed**: when, on the entry's page, exactly
   one PARAGRAPH block (never furniture, a caption, a footnote, a list item or a placeholder) has
   the entry's title as its whole text. Compared after NFKC, case folding and folding white space,
   with a printed number ("2.1", "A.3", under the font rules' own rule for letters) taken off the
   front of the block's text; the block's heading lines are joined with the existing `title()`.
   No match, or two matches, and the entry is ignored.
3. **A title root is not a heading**: when the outline has a single top entry with entries under it
   (liu), that entry names the document; it is skipped and the entries under it move up one level.
   An entry whose text is the file's own title (`Metadata.title`) is skipped too.
4. **Level of an added heading**: from its printed number when it has one (depth of "2.1" = 2, as
   for the font rules); otherwise the entry's level after rule 3.
5. **Disagreement on the level** of a heading both found: the font rules' level stands (rule 1).
   The outline's level only decides for headings that only it found.
6. The section tree is then built as today from all headings.

Design questions:

- **q9. Confirm only, or also add?** Recommend **add, never remove** (above). Alternative A: confirm
  only (outline changes nothing at all, so it would have no effect anywhere; the issue asks for a
  second signal). Alternative B: outline wins wherever it exists (would make liu's title a heading
  and drop arsiwalla's Abstract, Acknowledgments and References: 4 truth regressions on the corpus).
- **q10. Which level wins when they disagree?** Recommend the font rules (printed number, then
  style), for the reason in rule 1 and because the printed number is what the page shows (D-64).
  Alternative: the outline's level (wrong on liu as stored).
- **q11. Page tolerance.** Recommend the entry's own page only. All 18 corpus pages are right; a
  miss only means the font rules decide alone. Alternative: also the next page (catches anchors set
  just before a page break, but doubles the chance of a wrong match).
- **q12. A heading joined into a paragraph.** When paragraph building has joined a body-size heading
  with the text after it, no block's whole text matches, and the outline cannot help. Splitting a
  block is a paragraph-stage change, out of scope here (none of the corpus papers has such a case).
  Follow-up filed as Issue #122.

No new setting: a test compares a document with and without its outline by
`dataclasses.replace(content, outline=())`.

Tests:

- Made-up `Content` (core objects, no PDF): an outline adds a body-size, non-bold heading the font
  rules miss, with its level; a numbered one gets its number's level and label; a title root is
  skipped and its children move up; the file's own title is skipped; furniture with the same text is
  not matched; two matching blocks on the page: ignored; a match on another page: ignored; a font
  heading missing from the outline stays; a level disagreement keeps the font level; no outline:
  same document as before.
- Hypothesis (CI and nightly profiles): for any `Content` with an outline drawn from its own line
  texts, random levels and pages, layout never fails, every item is in exactly one block, sections
  nest, and every heading found without the outline is still a heading, with the same level and
  label, with it.
- Corpus: layout golden files unchanged (the expected result, see section 1); a new test that every
  outline entry naming a printed heading in arsiwalla, waskom and biggs falls on a HEADING block,
  and liu still has no headings.
- Nightly Hypothesis profile and `lint-imports` run before the PR opens (layout imports only core).

Size: about 60 lines of code, 150 of tests. `CHANGELOG.md` line. If a layout golden file changes
after all, the PR stops, explains each changed line against the truth files, and becomes critical.

## 6. Order, process, risks

- PR 1 opens after approval; PR 2 after PR 1 merges; PR 3 after PR 2 merges, merging main for #36
  first. Each PR: fast suite, ruff, `lint-imports`, `deptry`, PR body with the attribution lines,
  `Closes #24` only on PR 3 (PRs 1 and 2 say "Part of #24"), feature IDs IN-01 and TP-16, risk
  label `risk:high` on PRs 1 and 2. No merging here; a review thread merges each.
- #73 (EPUB) can start on the field as soon as PR 1 merges.
- Risks: a PDF whose outline repeats a body sentence as a title would turn that one block into a
  heading (rule 2 needs the whole block's text to match, so a sentence inside a paragraph never
  does); outlines in other languages need nothing special (no word lists).
- Licences: no new dependency, no copied code, no new sample text.

## 7. Decisions (coordinator, 13 Nov 2026 07:16 UTC, under D-80; all twelve as recommended)

| D | Question | Decision |
|---|---|---|
| D-262 | q1 | Three PRs, one per lane: core, extraction, layout |
| D-263 | q2 | `Content.outline` is a flat tuple in the file's order with levels; first entry at level 1, each entry at most one level deeper than the one before |
| D-264 | q3 | Names `OutlineEntry` and `Content.outline` |
| D-265 | q4 | Fields title, level, page only |
| D-266 | q5 | Titles kept exactly as stored (also "" and trailing spaces); layout ignores entries with no letters |
| D-267 | q6 | pypdfium2's default depth of 15 levels, no count limit |
| D-268 | q7 | A damaged outline never fails the file |
| D-269 | q8 | liu's outline entries are named in the extraction test with the reason they are not truth headings |
| D-270 | q9 | The outline adds headings, never removes one |
| D-271 | q10 | When font rules and outline disagree on a level, the font rules' level wins |
| D-272 | q11 | An entry matches on its own page only |
| D-273 | q12 | A heading joined into a paragraph is out of scope; follow-up Issue #122 |
