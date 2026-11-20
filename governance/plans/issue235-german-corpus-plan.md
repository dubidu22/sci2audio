# Issues #235 and #237: a real German paper in the corpus, and stated language tags (plan)

Thread "Add a real German paper to the corpus", 14 Nov 2026, main 0bb973f. Lane: layout (and
extraction for #237). Two PRs, #235 first. **Both critical** (new corpus file, truth file and
goldens; layout furniture, caption and footnote rules), so no code or tests before the
coordinator's approval. Everything below was measured on main 0bb973f with throw-away prototypes
on a scratch branch (never pushed).

## 0. Corrections to the issue

- The arXiv file today is **v2 (30 Jun 2017), 13 pages**, not 6: v2 adds the legal sections.
  367,160 bytes, sha256 `a501d499…4be4`, no `/Lang`. `https://arxiv.org/pdf/1705.08889` and
  `…v2` give the same bytes. Licence on https://arxiv.org/abs/1705.08889: CC BY 4.0.
- Single column on every page, 29 numbered footnotes plus one `∗` note, one figure ("Abb. 1",
  page 3, a vector diagram full of text), no tables, no formulas, a PDF outline of 7 entries.
- The guess (#219) already reads it as German: `de`, source text, 1,587 German and 21 English
  common words in 5,053.

## 1. What layout gets wrong today (three things, not one)

Adding the paper with a drafted truth file and running the fast suite on main: 23 failures, all
on the new paper or on lists that name every paper. The layout ones:

1. **Running heads (the issue).** The LNI heads ("2 Max Maass, Anne Laubach, Dominik Herrmann" /
   "PrivacyScore 3") stand at y = 134.7 pt on a 792 pt page, 17 % down: LNI sets a small type
   area on Letter paper. The top edge band is the top 10 % of the **paper** (79 pt), so the heads
   are never candidates and are read as 12 paragraphs. They are 9 pt against a 10 pt body, so
   once in the band the existing tier-1 shape rule (D-326) takes them.
2. **German caption labels.** "Abb. 1: Anwendungsfälle und Datenstrukturen" is not a caption
   (`captions._NAMES` knows Figure, Fig., Table, Algorithm only). So no figure block takes the
   diagram, its 21 text lines are read as paragraphs, and page 3 counts 3 columns.
3. **Footnote marks at full font size.** From page 2 on, the marks are superior-figure glyphs:
   PDFium reports 7.97 pt, the same as the note's text, but the glyph box is 3.2 pt high and its
   bottom stands 2.2 pt above the baseline. `footnotes._mark` needs a smaller size, so the notes
   of each page become one footnote block without a label (page 1's marks are 6.2 pt and work).

All three prototyped together: the new paper passes every layout truth test (furniture both
ways and roles, headings, footnotes with marks, captions, verbatim sentences) except columns on
page 3 (Q7), and **all 68 existing snapshots pass unchanged**; the only snapshot failures are the
new paper's missing ones. Furniture roles of the 7 English papers: 0 lines change.

## 2. Proposal for #235

### 2.1 Running heads in a small type area (Q1 to Q4)

In `layout/furniture.py`, one function decides the document's top band, used by every
furniture rule and by `build.py`'s placement of top furniture (which reads `edge_band` itself
today, line 171), so the head block also comes first on its page:

- **As today**: a line ending in the top `edge_band` (10 %) of the paper is in the top band.
- **New**: when **nothing is printed in that 10 % on any page** of the document (no text line
  apart from side stamps, no picture, no drawing), a line **starting within `head_drift`
  (0.5 em) of the document's highest text line** is in the top band too. That is the type
  area's first row: where LNI, and books set on bigger paper, print their heads.
- Nothing else changes: same size tiers, same repeat counts, same page-number rules, bottom
  band and footer band untouched. No new setting (it reuses `edge_band` and `head_drift`).

Measured: the English corpus is never touched (the ACL, arXiv and Liu papers print text inside
the 10 %; both JOSS papers have their logo picture there); on the new paper exactly the 12 heads
become running heads and nothing else changes. A first prototype that moved the whole 10 %
band down to the printing failed `test_two_rows_under_one_number_are_one_formula` (a lone "(4)"
on a one-page test document became a page number), which is why the band only reaches the
first row.

### 2.2 German caption names (Q5)

`captions._NAMES` gains `Abbildung|Abb\.|Tabelle|Tab\.|Algorithmus` (and the upper-case forms
the English names have); `graphics._TABLE` gains `Tabelle` and `Tab.`, so such a caption names a
TABLE block. Labels stay as printed ("Abb. 1"). One list for every language, as the reference
names already do (D-132). English corpus unchanged (measured).

### 2.3 Raised footnote marks (Q6)

`footnotes._mark` also accepts a mark whose box **ends at least `footnote_mark_rise` (0.1 em)
above the bottom of the run after it** (a superior figure at full size), besides today's
smaller size. New `LayoutSettings.footnote_mark_rise: float = 0.1` with a comment. Still only a
number or note symbols, still the row's first run. English corpus unchanged (measured).

### 2.4 The corpus file and truth

- `tests/corpus/papers/arxiv2017-maass-privacyscore.pdf`, stored exactly as downloaded, and its
  row in `tests/corpus/LICENSES.md` (CC-BY-4.0, Maass, Laubach, Herrmann, abs page as source,
  Covers: footnotes, figures, citations, URLs, hyphenation, running heads). Corpus: 8 papers.
- `tests/corpus/truth/arxiv2017-maass-privacyscore.toml`, drafted from the PDF and checked
  against the arXiv LaTeX source (only a check, never added): 13 pages, 1 column each, 8
  headings (1 to 7 and "Literaturverzeichnis"; "Abstract:", "Implementation" and
  "Anschaulichkeit und Handlungsempfehlungen" are run-in heads, not headings), the side stamp
  and 12 running heads as furniture, footnotes by page with marks (1, 2, 3, ∗ on page 1; 4 to
  29 after), figure "Abb. 1" on page 3, verbatim sentences: plain, page-break (pages 1 to 2,
  across the new head), hyphenation, footnote-mark; no inline maths (said in a comment).

### 2.5 Tests

Written first, failing on main where they should:

- Unit (`test_layout.py`): a 4-page document on Letter paper with nothing in the top 10 %,
  alternating 9 pt heads at 17 %: all running heads (fails on main); the same with one page
  printing a line in the top 10 %: unchanged rule, heads stay text; a one-page document starting
  at 17 % with a lone "(4)" a row below the first: no page number; a document with a picture in
  the top 10 %: no new band (JOSS shape).
- Unit (`test_layout_captions.py`): "Abb. 1: …", "Abbildung 2. …", "Tabelle 3: …" (TABLE),
  "Tab. 1: …" are captions; "Abb. 1 zeigt …" stays a paragraph.
- Unit (`test_layout_footnotes.py`): a note row whose mark is the text's size but raised 0.2 em
  splits; one raised by 0.05 em does not; a number at the baseline does not.
- Hypothesis: the existing "never fails, every item in one block" properties cover the code;
  one new property: with something in the paper's top 10 % on some page, the furniture is the
  same as with the old band.
- Corpus: the new paper runs through every parametrised corpus test (section 3).
- Before the PR: fast suite, nightly Hypothesis profile on `test_layout*.py`, ruff, lint-imports,
  deptry, and a mutation check of the three rules (each removed in turn must fail a test).

## 3. Goldens and truth files (added or changed)

**Unchanged, byte for byte:** every existing snapshot (68), every English listening script and
report, every existing truth file, `line-end-hyphens-en.toml`, the English and German regression
cases. The PR body will show the snapshot count and `git diff --stat` of `__snapshots__` with
additions only.

**Added:**
- the PDF, its LICENSES row, its truth file;
- new entries for the paper in `test_extraction_corpus.ambr` (golden, outline),
  `test_layout_corpus.ambr`, `test_textprep_furniture.ambr`, `test_textprep_rules_corpus.ambr`
  (footnote marks), and in `test_app_corpus.ambr` the paper's script and report (Q9);
- `tests/regression/line-end-hyphens-de.toml`: the paper's 38 line-end hyphens, read by hand
  (the German hyphen rule of #96 is merged), and `test_textprep_hyphens.py` reads the file of
  each paper's language.

**Lists and counts in tests that name the corpus** (not goldens): the outline table and
CHAPTERS in `test_extraction_corpus.py` / `test_app_corpus.py`, "six papers have a hyphenation
sentence" becomes seven, the footnote-mark count, and `test_layout_language.py` moves the paper
from ENGLISH_CORPUS to GERMAN_CORPUS (its guess with the tag removed: "de").

## 4. Proposal for #237 (second PR)

- One private helper in extraction, `extraction/language.py`: `stated_language(raw: str) -> str`,
  used by the PDF (`/Lang`), EPUB (`dc:language`) and Markdown (`lang`) extractors.
- Rule: surrounding white space removed; `_` becomes `-`; a tag that is not BCP 47 shaped
  (`[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*`, so also `x-default`, `i-…`, "German", "") becomes "";
  a primary subtag `und`, `zxx`, `mul` or `mis` becomes "" (nothing stated, so layout guesses);
  `eng` becomes `en`, `deu` and `ger` become `de` (Q14); letter case kept as written.
- Tests: unit cases for each kind; through `choose_language`: a German text tagged `en_US` →
  `de`, TEXT, with the D-496 warning; tagged `und` → `de`, TEXT, no warning; tagged `ger` → `de`,
  FILE; a generated PDF with `/Lang (en_US)` and German text end to end; Hypothesis: the helper
  never fails, its result is "" or shaped, and it is idempotent.
- Goldens: none change (the corpus tags are "en-GB" twice and none otherwise; shown in the PR).
  Not critical by the rules (no golden, no core, no contract change), but kept on the full
  process as asked.

## 5. Questions (recommendation first)

- **Q1 How heads in a small type area are found.** Recommended: when nothing is printed in the
  paper's top 10 % on any page, lines starting within 0.5 em of the document's highest text
  line are in the top band too (2.1). Not chosen: move the whole 10 % band down to the printing
  (made a lone equation number a page number on a one-page document, measured); raise
  `edge_band` to 0.2 (would make body lines of every corpus paper candidates); per page instead
  of per document (heads are a document's habit, and one empty page would be enough to shift).
  This extends the #33 rules (D-322 to D-328) in one place only: where the top band is.
- **Q2 The bottom edge.** Recommended: unchanged. The bottom of a type area holds footnotes,
  small and, in legal papers like this one, of very regular shape ("BGH v. …, Az. VI ZR …"),
  and the footer rule takes small lines there; no file in hand prints a running foot inside a
  small type area. A symmetric bottom rule changed nothing on the corpus, but it has no case to
  test. No issue.
- **Q3 One band for all furniture rules.** Recommended: the band function also serves the page
  number rules and `build.py`'s top-furniture placement, so all agree. No new setting.
- **Q4 A head that holds its page number in the same line.** Recommended: the whole line is a
  running head (as the truth lists it); the page label stays "" for these pages, so the player
  and report fall back to the physical page number, which here is the same. Splitting the number
  out is not needed for this file; no issue.
- **Q5 German caption names.** Recommended: Abbildung, Abb., Tabelle, Tab., Algorithmus for every
  document, whatever its language (one list, like D-132's reference names; a German paper read as
  English by the fallback still gets its captions). Not chosen: a list per language chosen by the
  document's language (more plumbing, misses mis-tagged files). The spoken notice for "Abb. 1"
  stays with #212 (the notices step is English only, D-147).
- **Q6 Raised footnote marks.** Recommended: a mark is also found when it is raised by at least
  0.1 em over the run after it, new setting `footnote_mark_rise`. Not chosen: a mark by
  numbering alone (next number in sequence: breaks on notes that start with a year or a count).
- **Q7 Page 3 counts three columns.** The diagram's labels stand in three columns above the
  caption, and columns are counted before captions are known. Recommended: the truth says 1 (the
  reading result), and `test_columns_per_page` gets one listed exception for this page with a
  new v1.2 issue (layout: text inside a figure counted as text columns). Not chosen: count
  columns after the figures are found (reorders the layout steps, a much larger change); writing
  3 in the truth (wrong by the README).
- **Q8 Text steps that are English only.** Links and citations (#101), footnote introductions
  and mark removal, and placeholder notices (#212, D-147) don't run on German, so three corpus
  tests fail on the paper by design. Recommended: one table in each of those test modules,
  `GERMAN_LATER = {test: issue}`, skips German papers with the issue named; #101 and #212 each
  get an acceptance line "remove the corpus exception for arxiv2017-maass-privacyscore". Not
  chosen: run those checks with English steps on German text (meaningless); hold the paper back
  until #101 and #212 land (blocks this issue). Note for the coordinator: on main today the
  German paper's figure text and footnote marks are read aloud, because the placeholder and
  footnote steps are English only; the script golden will show it until #212.
- **Q9 Script golden.** Recommended: add the paper to `test_app_corpus.py`'s GOLDEN (script and
  report), recorded as main reads it at PR time. It changes with #130, #101 and #212; whichever
  merges later re-records it, as with the German samples of #219. The report shows language
  `de`, guessed from the text.
- **Q10 File name and version.** Recommended: `arxiv2017-maass-privacyscore.pdf`, the v2 bytes.
- **Q11 Checking the truth.** Recommended: drafted from the PDF, checked against the arXiv LaTeX
  source (`drafted_from = ["pdf", "latex"]`), and checked page by page against rendered page
  images in the review thread.
- **Q12 Where #237's rule lives.** Recommended: one helper in extraction (2 lines in each of 3
  extractors). Not chosen: a helper in core (core holds data objects; no core change needed);
  in layout's `choose_language` only (the report and saved document would still show "en_US").
- **Q13 What counts as no tag.** Recommended: und, zxx, mul, mis and anything not BCP 47 shaped.
- **Q14 Three-letter codes.** Recommended: map eng, deu and ger (the two languages sci2audio
  reads) to en and de, so the D-496 override and the voice choice see them; other codes are left
  as written. Not chosen: leave them (a German PDF tagged "ger" would get the English voice).
- **Q15 Order.** Recommended: #235 first, then #237, each after merging main (the German text
  rules thread's PR 3, #130, changes German scripts and possibly the new paper's script golden).

## 6. Size

PR 1: about 45 lines in layout (furniture, build, captions, graphics, footnotes, settings),
about 200 lines of tests, the truth file (about 110 lines), the hyphen readings (38 rows), the
PDF. PR 2: about 30 lines in extraction, about 100 lines of tests.

## 7. Decisions (coordinator, 14 Nov 2026 02:46 UTC)

Approved as recommended, Q1 to Q15: D-502 (Q1), D-503 (Q2), D-504 (Q3), D-505 (Q4), D-506 (Q5),
D-507 (Q6), D-508 (Q7; the v1.2 issue is #238), D-509 (Q8; acceptance lines added to #101 and
#212), D-510 (Q9), D-511 (Q10), D-512 (Q11), D-513 (Q12), D-514 (Q13), D-515 (Q14), D-516 (Q15).
Issue #235's text corrected to 13 pages, v2.
