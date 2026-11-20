# Extraction batch B1: unreadable fonts and page frames (plan)

Status: **PROPOSED**. PR 1 (critical) waits for the coordinator's approval; PRs 2 and 3 start on
this plan (D-761). Author: implementation thread "Fix unreadable fonts and page frames",
18 Nov 2026. Base: main 1797ceb. Batch plan: `next-batches-2026-11-18.md` (B1, C1).
Item and question numbers are pinned (PLAN-03).

Earlier PRs in this batch that built on a model a later PR changes: none (PR 1 and PR 2 both
edit `extraction/pdf.py` and `tests/unit/pdf_maker.py`, in different functions; the second to
merge merges main, D-718).

## 0. What was measured first (scratch scripts, nothing committed)

PDFium has no public call for a font's `/ToUnicode` or `/Encoding`, but it marks every
character whose code it could not map to Unicode: `FPDFText_HasUnicodeMapError` (PDFium then
uses the code itself as the character, which is exactly the "glyph ID read as a letter" bug).

| file | font | map errors | embedded program |
|---|---|---|---|
| Stoevesand (Colin's #442 file, project uploads, measure only) | TimesNewRoman, Calibri x3, Symbol (CID, Identity-H) | 7845/7845, 85/85, 13/13, 10/10, 3/3 | TrueType, **no cmap, no post** |
| Kehren (German, uploads, measure only) | all | 0 | |
| chi, hardt | MSAM10 (TeX symbols) | 22/22 | Type 1 |
| nowak, liu | CMEX10, CMEX9 (TeX big operators) | 4 to 69 | Type 1 |
| seaborn | ArialMT (matplotlib Type 3) | 96/96, **reads correctly** | none returned |
| maass, arsiwalla, biggs | | 0 | |

Generated fixture (a TrueType program written in the test helper: rectangles as glyphs, no
real font, so no licence question): CID Identity-H with GID = code point minus 29 reads
`'DV %XFK *HPHLQZHVHQDUEHLW` as in the issue. Without `/ToUnicode` every character has a map
error, **also when the program has a cmap or a post table** (PDFium does not use them for
Identity CID fonts); with `/ToUnicode` the text is right and there are 0 map errors.

Letter-bigram check, leave-one-out over the corpus (8 papers, EPUB, Markdown and text samples
in both languages, plus Kehren): pages with at least 100 letter pairs hold at most **0.93 %**
rare pairs; the same pages shifted by 29 hold at least **12.7 %**; Stoevesand's three pages
22 to 24 %. Off-script letters (Calibri GIDs read as Latin Extended-B and others): corpus
pages at most 1.5 %.

## 1. PR 1: #442 part A, fonts with no Unicode source (critical: core dataclass, lane:infra)

Branch `extraction/442-unmapped-fonts`. Labels: lane:extraction, lane:infra, risk:high.
Closes nothing (part B stays open in #442); body says "Part A of #442".

### 1.1 The font rule (AC-442.1)

A character counts as **from a font with no Unicode source** when
(a) PDFium reports a Unicode map error for it, and
(b) its font's embedded program is TrueType or OpenType (an sfnt) holding neither a `cmap`
nor a `post` table.

That is the AC's CID case, measured through PDFium: no ToUnicode (otherwise no map error, (a)),
Identity-style codes (the map error itself), program without cmap and post (b). The font is
looked up only for a character that has a map error (`FPDFText_GetTextObject`,
`FPDFTextObj_GetFont`, `FPDFFont_GetFontData`), once per font per file (cache by font handle),
and only the sfnt table directory is read (bounded: numTables checked against the data size;
anything that is not a plain sfnt counts as "has a source"). Cost on a normal page: one extra
PDFium call per character.

**Q1 (needs the coordinator's ruling): narrow AC-442.1's "(or a simple font with unknown glyph
names)".** The corpus's TeX math fonts (MSAM10, CMEX) and seaborn's matplotlib Type 3 font
are exactly simple fonts with unknown glyph names (table in section 0): counting them marks
4 of 8 corpus papers, moves their extraction goldens (AC-442.4 and condition C1 both fail),
and seaborn's 96 characters read correctly. Recommended: those fonts are not counted in the
new field; garbled text from them is caught by the text check (1.3), which does not depend on
the font kind. Option B (not recommended): a second field for them, which moves 4 goldens and
makes PR 1 wait for B3.

### 1.2 The Content field (C1: additive, empty default, no golden move)

`core.Page` gets one field:

```python
unmapped: int = 0  # characters in `lines` from a font with no Unicode source (#442)
```

Docstring: their text is the font's glyph numbers, not letters; PDF only, 0 for other
formats. `__post_init__` checks `0 <= unmapped <=` the page's characters (line text without
the spaces extraction puts between words; the count is only made when `unmapped > 0`).
Only characters kept in `lines` count (not those the crop box cuts off).
The per-page share is `unmapped / chars`, given by 1.3. `to_data` leaves a field at its
default out, so every golden stays byte-identical (every corpus page has 0), and `from_data`
reads saved jobs from before the field. No other core type changes.

### 1.3 The text check (AC-442.2) and the page verdict, for B7

New module `extraction/legibility.py`, exported from `sci2audio.extraction`:

```python
@dataclass(frozen=True)
class PageLegibility:
    number: int
    chars: int       # characters in the page's lines, spaces not counted
    unmapped: int    # Page.unmapped
    pairs: int       # letter pairs inside words, case-folded, a to z
    rare: int        # of those, pairs in RARE_PAIRS
    letters: int     # letters, U+FFFD and private-use characters
    foreign: int     # of those, outside Basic Latin, Latin-1, Latin Extended-A and Greek,
                     # or U+FFFD, or private use
    @property
    def unreadable(self) -> bool: ...

def legibility(content: Content) -> tuple[PageLegibility, ...]: ...
```

`unreadable` is true when any of these holds (constants in the module, values from section 0):
- `unmapped / chars > UNMAPPED_SHARE = 0.5`
- `pairs >= MIN_PAIRS = 100` and `rare / pairs >= RARE_SHARE = 0.05` (corpus at most 0.0093,
  shifted text at least 0.127)
- `letters >= MIN_LETTERS = 50` and `foreign / letters >= FOREIGN_SHARE = 0.2` (corpus at most
  0.015)

`RARE_PAIRS`: letter pairs that never occur in the corpus and that cannot form at a German
compound joint (first letter j, q, v, w or x, or second letter q or x), 72 pairs, written out in
the module with how they were found: `bq bx cx dq dx fx gq gx hq hx jb jd jg jq jr jv jx kq kx
lq lx mx pq px qb qc qd qe qg qh qj qk ql qm qo qp qq qr qt qv qw qz sx uq vb vc vd vh vj vn vq
vv vw vx vz wj wq wx wz xb xd xg xk xl xn xr xv xw xx xz zq zx` (the measured list without
`xy`, which "oxygen" and "hexyl" hold). A statistic, not text: no licence question.

The check runs on any `Content` (EPUB, Markdown and text too). Extraction still decides nothing
(D-63): `legibility` measures; stopping or warning is the app's decision (B7).

**For B7 (part B, pinned here so B7 reuses it, AC-442.3):** preparing stops before voices when
unreadable pages hold **more than half** of the document's characters (`sum(chars)` of
unreadable pages `* 2 > sum(chars)` of all pages); a document with at least one unreadable page
below that share gets the #187 report warning naming those pages. B7 writes the notices (EN, DE)
and the report; it calls `legibility(content)` and changes nothing in extraction.

**Q2:** `legibility` lives in extraction (lane of this batch, AC-442.2 is part A). Alternative:
textprep, as #187 once suggested. Recommended: extraction, next to the reader that knows why
text can be unreadable; app imports it like the readers.

### 1.4 Tests (all in the extraction lane's test files, plus core's)

Test-harness changes (listed for the review): `tests/unit/pdf_maker.py` gets
`glyph_number_pdf(text, *, order="shifted"|"far", cmap=False, post=False, to_unicode=False)`
and the sfnt writer it needs (about 60 lines).

- AC-442.1: the fixture page has `unmapped == chars`; with `to_unicode=True` it reads the real
  text and `unmapped == 0`; with `cmap=True` or `post=True` (and no ToUnicode) `unmapped == 0`
  (rule (b)), and the text check still flags it; a page mixing a Helvetica line and a fixture
  line gives the exact count; a fixture line outside the crop box is not counted; a Helvetica
  with unknown `/Differences` names (#187's example) has `unmapped == 0` (Q1 boundary).
- AC-442.2: `legibility` flags the fixture page by its letters alone (`rare` share, with the
  `unmapped` count set to 0 in a copy of the content); the "far" order is flagged by `foreign`;
  every corpus page shifted by 29 (with at least 100 pairs) is flagged.
- AC-442.4: `extract_pdf` of every corpus paper gives `unmapped == 0` on every page and no page
  is unreadable; the same for the EPUB, Markdown and text samples; all existing goldens pass
  untouched (no `--snapshot-update` in this PR).
- core: the field's check (negative, more than the page's characters), `to_data` leaves 0 out,
  `from_data` round trip with a value.
- Hypothesis: `legibility` never fails on any `Content` from the core strategies, and its counts
  stay within the page's characters.
- Speed: the existing `benchmark` extraction test shows the cost; the plan's bound is under
  5 % on arsiwalla.

### 1.5 Docs

New `docs/unreadable-pdf-text.md`: `Page.unmapped` and the font rule, `legibility` and its
constants with the measured margins, the B7 policy above, and what is out (glyph-ID recovery,
#442 part 3, Colin's call). The KB thread records the decision (D-number from the
coordinator).

Size: about 150 lines of source, 250 of tests, 60 of docs. Review: Opus high, critical
process; my own `ci:full` before hand-off.

## 2. PR 2: #537 + #543, page frame positions (non-critical)

Branch `extraction/537-543-page-frames`. Label lane:extraction. Closes #537 #543.
Files: `extraction/pdf.py` (`_Frame`, `_chars` angle), `tests/unit/pdf_maker.py` (a raw spread
helper), `tests/unit/test_extraction_pdf.py`.

**#543 (inherited media box).** `FPDFPage_GetMediaBox` reads only the page's own entry
(crbug.com/pdfium/1786); `FPDF_GetPageBoundingBox` does inherit, and gives crop box ∩ media box.
`_Frame.of` sets the page's crop box to an unbounded box for one call, reads the bounding box
(= the inherited media box), and sets the crop box back, before the text page is loaded (the
document is never saved; text positions do not depend on the crop box). Measured on a
generated spread with `/MediaBox` only on `/Pages`: main reads both halves on each page; the
trick gives the right sheet on both pages.

**#537 (/Rotate).** `_Frame` takes the page's rotation (0, 90, 180, 270) and turns every point
after taking it from the crop box's corner: with W and H the unrotated crop box's width and
height, (x, y) becomes (H − y, x) for 90, (W − x, H − y) for 180, (y, W − x) for 270. A
character's angle becomes `(angle + rotation) mod 2π`, so text that reads left to right when
shown has angle 0 (measured: PDFium gives 3π/2 for 90, π for 180, π/2 for 270 on such text).
Drawings and pictures go through the same `point`, the sheet too.

Tests (#537 criteria): generated pages with `/Rotate 90` and `/Rotate 270` (and 180) whose text
reads left to right when shown: every line inside the page's width and height, lines in reading
order, angle 0 so lines join as on an upright page; a rotated page with a drawing; pages
without `/Rotate` unchanged (existing tests); corpus goldens unchanged (all at 0). The third
criterion (a landscape table page rotated by 90 reads its rows in order, layout's columns per
page as shown) as an end-to-end test in the extraction test file that runs layout on the
extracted content, test only. #543 criteria: the spread reads only its half on each page; text
outside the sheet itself is still kept (as `dense_pdf`); corpus unchanged.

Size: about 60 lines of source, 150 of tests. Review: Opus high batch reviewer, non-critical
process (2 rounds max).

## 3. PR 3: #485, the Windows flate-bomb test (critical: `extraction/isolate.py`)

Branch `extraction/485-windows-pipe`. Labels lane:extraction, risk:high. Closes #485.

**Cause found by reading the code.** On Windows, `multiprocessing`'s `PipeConnection.poll`
calls `PeekNamedPipe` first, and that raises `BrokenPipeError` (WinError 109) when the writer
is gone and the pipe is empty (CPython 3.12 `connection.py:342`). `isolate._wait` calls
`receive.poll(...)` outside its `try`, so when the child ends (here: the memory watch's
`os._exit(MEMORY_EXIT)`) before the parent is back at `poll`, the error escapes `extract_pdf`,
the test's script dies with an uncaught exception and exits 1, stderr unseen. On an idle runner
the parent is already waiting inside `poll` when the child ends, so `recv` gets `EOFError` and
all is well; under `-n auto` load the parent is late, which matches both failures and the
40 green isolated runs. Linux and macOS poll with `select`, which never raises here. In the
app this is a real bug: on a busy Windows machine a too-large PDF can fail with an unhandled
`BrokenPipeError` instead of the size message.

**Fix.** In `_wait`, an `OSError` from `poll` means the child has ended, handled like the
`EOFError` from `recv` (join, reason from the exit code).

**Tests.** AC-485.1: the flate-bomb test runs its script without `check=True` and fails with
the exit status and the child's stderr in its message. A unit test with a stand-in connection
whose `poll` raises `BrokenPipeError` (every system; fails on main). A real-pipe test: the
child reports a step and ends with `MEMORY_EXIT` while the parent's `on_step` handler still
sleeps, so the parent polls an empty, closed pipe (fails on Windows on main, passes elsewhere;
proves the fix on the Windows CI leg). The quarantine marker comes off (AC-485.2).

**Proof (AC-485.2).** `isolate.yml` on the branch: the flate-bomb test alone 40 times on
Windows (mode full), and the full fast suite three times on Windows (`ci:full` run plus two
dispatches); results go into #485. If any run fails, AC-485.3 applies: marker back, evidence in
the issue.

Size: about 10 lines of source, 60 of tests. Review: Opus high, critical process, my own
`ci:full` before hand-off.

## 4. Order

PR 3 first (small, cause known), then PR 2, then PR 1 once approved. Each PR gets Linux CI
green (critical ones also `ci:full`) before I tell the coordinator it is ready for review.
Nothing here touches `app/`, `web/`, `cli.py`, `layout/`, `textprep/` or their tests (PR 2's
end-to-end test only calls layout).
