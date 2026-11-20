# Plan: issue #189, footnote marks and notes tied by link tags (EPUB, Markdown)

Thread "Read footnote marks in EPUB and Markdown", 13 Nov 2026. Lane textprep, milestone v1.0,
critical (adds English regression cases and a golden file, extends the regression format).
Base: PR #192 (`layout/tagged-75`, f56fe95). Branch from main once #192 merges; the PR opens
only after that, rebased by merge, no force-push.

Measured on #192's head with the real job (`run_script_job`), and the "after" with a throwaway
prototype of the rule below patched in at run time (not committed).

## 1. What happens today

Layout (D-406) gives each EPUB/Markdown note a FOOTNOTE block with label "" (its mark is not
printed in its text). The mark in the running text is a run tagged `role:doc-noteref` or
`epub:noteref` plus `link:<item id>` of the note's first line (D-307, D-341):

| file | mark run | tags | its note |
|---|---|---|---|
| Markdown sample, block 1 | "1" | p, sup, a, #fnref1, role:doc-noteref, link:p1-l36 | block 27, page 1 |
| Markdown sample, block 7 (list item) | "2" | ol, li, sup, a, #fnref2, role:doc-noteref, link:p1-l37 | block 28, page 1 |
| Markdown sample, block 26 | "2" | p, sup, a, #fnref2:1, role:doc-noteref, link:p1-l37 | block 28 (second use of `[^fn]`) |
| The Time Machine, block 240 (ch. 8, page 10) | "1" | section, #chapter-8, …, a, #noteref-1, epub:noteref, role:doc-noteref, link:p16-l2 | block 331, page 16 (Endnotes) |

The Time Machine's note ends with a run "↩︎" tagged a, epub:backlink, role:doc-backlink,
link:p10-l8. The Markdown renderer drops the back-link (D-341). PDF runs carry no tags at all
(all 7 papers checked), so nothing below can fire on a PDF.

`FootnoteStep` (D-143) finds a mark only by a note's printed label on the same page, so with
label "" it finds nothing: marks stay, notes are introduced "Footnote." (D-144), the arrow is
read.

## 2. The rule

In `textprep/footnotes.py`, `FootnoteStep.find` (same step, same category "Footnotes", on by
default) gains a **linked-mark pass** that runs before the printed-label pass:

1. **Notes by item:** map every item id of every FOOTNOTE block to that block's index.
2. **Linked marks:** in every block that can hold a mark (MARKED_KINDS, plus FOOTNOTE, see
   q1), a run tagged `role:doc-noteref` or `epub:noteref` whose `link:` target is an item of a
   FOOTNOTE block is a mark. Consecutive runs with the same noteref and the same `link:` tag
   are one mark (`<a><b>1</b>a</a>`). Its text without surrounding white space is removed with
   one `remove` edit: reason "footnote mark 1 is not read; the note is read where the file
   places it (Q2, D-414)". No page, size, word-before or maths condition: the tag says what the
   run is. **Every** linked mark is removed (q2), wherever its note stands (another page, the
   Endnotes chapter). A noteref whose link does not reach a FOOTNOTE block is not a linked mark
   (q4); a noteref linking to the note it stands in is not one either.
3. **Introduction:** a note whose own label is "" and that at least one linked mark points at is
   introduced by the first such mark in reading order: "Footnote 1." for digits or letters,
   "Footnote." for a symbol (D-144's wording and rules, `wording.footnote`). A mark printed in
   one pair of brackets, "[1]" or "(1)", is introduced as "Footnote 1." (q3). A note with a
   printed label keeps today's introduction (it replaces the printed mark). A note already
   starting with "Footnote" or empty gets nothing, as today.
4. **Back-links:** inside a FOOTNOTE block, a run tagged `role:doc-backlink` or `epub:backlink`
   is removed together with the white space before it, one `remove` per back-link: reason
   "the back-link of a footnote is not read" (q5). A note that is blank apart from back-links
   gets no introduction.
5. **No double edits:** a run with a noteref tag is decided by the linked-mark pass only; the
   printed-label pass skips it, and a linked mark of a labelled note counts as that label's
   one mark on its page (D-143), so the label pass never removes a second run for it. One step
   never proposes overlapping edits (a non-strict run would drop all of the step's edits).

The module docstring gains the linked-mark rule. Cost: one pass over the runs with dict and set
lookups, linear.

Switching "Footnotes" off reads marks, arrows and notes as printed (D-110); switching
"Footnote texts" on removes every note as a whole block, which claims the introductions and
back-link edits (D-128), and the marks stay out, as today.

## 3. Spoken output, exact before and after

### Markdown sample (`tests/corpus/markdown/sci2audio-sample-note.md`), 5 lines change

| before | after |
|---|---|
| Every sentence here is our own.1 | Every sentence here is our own. |
| Do footnotes2 help or hurt? | Do footnotes help or hurt? |
| Listeners kept up.2 | Listeners kept up. |
| Footnote. / Nothing in this note is taken from anyone else. | Footnote 1. / Nothing in this note is taken from anyone else. |
| Footnote. / A footnote with bold text, continued on a second line. | Footnote 2. / A footnote with bold text, continued on a second line. |

"see also the method and note 1." stays: `[note 1](#fn1)` is an ordinary link, not a noteref.

### The Time Machine (`tests/corpus/epub/wells-the-time-machine.epub`), 2 places change

Before (one utterance):
> Had it not been for her I do not think I should have noticed that the floor of the gallery sloped at all.1 The end I had come in at was quite above ground, and was lit by rare slit-like windows.

After (the cutter now ends the sentence at "all."):
> Had it not been for her I do not think I should have noticed that the floor of the gallery sloped at all.
> The end I had come in at was quite above ground, and was lit by rare slit-like windows.

Before:
> Footnote.
> It may be, of course, that the floor did not slope, but that the museum was built into the side of a hill. —Ed. ↩︎

After:
> Footnote 1.
> It may be, of course, that the floor did not slope, but that the museum was built into the side of a hill. —Ed.

No other line of either script changes. The 7 PDF papers: their runs carry no tags, so their
scripts stay byte-identical; `test_app_corpus.ambr` and `test_textprep_rules_corpus.ambr` must
not change (checked in CI and by a before/after diff of all 7 scripts in the PR).

## 4. Tests (written first)

- **Regression cases** (`tests/regression/english.toml`, issue 189), added with today's output
  as `expected` in a first commit, then changed with the rule, so the PR shows the diff:
  - `linked-marks-markdown`: the sample's three marks (one list item, `[^fn]` used twice) and
    two notes → the 5 lines above.
  - `linked-endnote-on-another-page`: The Time Machine's sentence on page 1, its endnote with
    the back-link on page 2 → the after-text above.
  - `noteref-to-a-paragraph-is-kept`: a noteref whose link reaches a paragraph → read as
    printed.
- **Regression format** (`sci2audio.testing.regression` and `make_document`, q7): a run table
  may be `{ text = "1", tags = ["sup", "role:doc-noteref", "link:b3l0"] }` (several tags, as
  core records them; `make_document`'s line ids are `b<block>l<line>`), and a block may give
  `page = 2` to stand on a later page (pages in order). `{ sup = "1" }` stays as it is.
- **Unit tests** (`test_textprep_footnotes.py`): mark removed when its note is on another page;
  several marks of one note all removed; the first mark introduces the note; symbol mark →
  "Footnote."; "[1]" → "Footnote 1." with the brackets removed from the text; noteref without
  `link:`, with `href:`, or linking to a non-note block → kept; self-link in a note → kept;
  noteref inside a note to another note → removed; mark split over two runs → one edit;
  back-link removed with the space before it, back-link outside a note kept; note of only a
  back-link → no introduction; labelled note + noteref (layout labelled it): one removal, one
  introduction, strict run passes; Footnotes off / Footnote texts on as in §2.
- **Hypothesis** (property, `ci` and `nightly` profiles): documents with random noteref and
  back-link runs linking random items: the step keeps the text-step contract
  (`check_text_step`, no overlaps, spans in blocks), is idempotent on its own output, and
  every remove is a noteref run or a back-link (with white space before it).
- **Pathological size:** 100k noterefs in one block and 100k notes: under 1 s (linear).
- **Corpus golden** (new `tests/unit/test_textprep_footnotes_tagged_corpus.py` and its
  `.ambr`, q8): for the Markdown sample and The Time Machine, every removed mark with 30
  characters around it, every introduction, every removed back-link. Plus assertions: every
  noteref run in both files is removed and every note starts with "Footnote <n>.".
- `uv run ruff check`, `ruff format --check`, `lint-imports`, `deptry src`, fast suite; the
  nightly profile on the new property test; a local diff of the 7 PDF scripts main vs branch.

Rough size: footnotes.py +80 lines, testing +40, tests +250, english.toml +3 cases, one new
golden. One PR, `textprep: footnote marks tied to their notes by link tags (#189)`,
risk:high + lane:textprep, `Closes #189`.

## 5. Questions (each with a recommendation)

1. **Where a linked mark is looked for.** Recommend MARKED_KINDS plus FOOTNOTE (a note citing
   another note), not furniture or placeholders, and never a noteref linking to its own note.
   Alt: MARKED_KINDS only, as D-143 (a mark inside a note would be read).
2. **How many marks per note.** Recommend every linked mark is removed (the Markdown sample
   uses `[^fn]` twice; both must go). Alt: D-143's once per label per page (would read the
   second "2").
3. **Bracketed marks.** Recommend removing the whole mark ("[1]") and introducing the note with
   what is inside one pair of brackets or parentheses ("Footnote 1."); no corpus file has one.
   Alt: "Footnote." for any mark that is not plain digits or letters.
4. **A noteref whose link does not reach a FOOTNOTE block** (unresolved `href:`, or a note
   layout did not recognise). Recommend: kept and read as printed (faithful text; the
   printed-label rule still applies if its four conditions hold). Alt: removed anyway (the
   listener would lose a number that points at text they then hear without an introduction).
5. **Back-links.** Recommend removing them in the Footnotes step (category Footnotes), with the
   white space before them, only inside notes. Alt: a separate step in "Page furniture" (one
   more step for one arrow; switching Footnotes off would still drop the arrow).
6. **Introduction source.** Recommend the text of the first linked mark in reading order. Alt:
   the note's position in its notes list (`<ol>` number), which the tags do not carry.
7. **Regression format.** Recommend run tables `{ text, tags }` mirroring `TextRun.tags` and an
   optional block key `page`, as D-148 extended it for `sup`. Alt: a shorthand
   `{ noteref = "1", note = 3 }` (hides the tags the rule reads, and needs a second shorthand
   for back-links).
8. **Golden file.** Recommend a targeted golden of marks, introductions and back-links for the
   two files. Alt: whole-script goldens of the Markdown sample and The Time Machine in
   `test_app_corpus` (2,300 lines that change with every text step).

## 6. Decisions to record (coordinator assigns D-numbers)

The rule of §2 (linked marks, introductions, back-links, no double edits) and q1-q8 as decided;
the regression-format extension (q7, extends D-148). Refines D-143 and D-144 for tagged files;
follows D-406 and D-414.

## 7. Approval

Approved as written by the coordinator, 13 Nov 2026 20:22 UTC (under D-80): q1-q8 as
recommended = D-420 to D-427 in question order; the rule of §2 = D-428. Branch from main after
#192 merges (the coordinator says when); before/after table in the PR body; do not merge.
