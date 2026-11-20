# Review of sci2audio PR #81, round 1 (issue #39, truth sentences with footnote marks and inline maths)

Reviewed head: 33343c9ac2b0b4bc16dda8d4237a1fbbb5b45427 (base af78e0b, main unchanged since).
Governing decision: KB D-106 (sci2audio-design f8b6461). Standing autonomy rule D-80.

**Verdict: approve. No must-fix.** Two small nits, deferred to an issue (see below).

## 1. Every new sentence against the rendered page

I rendered each page myself with pypdfium2 (scale 3), cropped the passage and read it, and measured
the gap between the last glyph and the mark or script with `get_charbox` to decide each space. I
also checked each sentence against pdfium's text of the page with spaces and hyphens removed (all
8 found once soft hyphens U+FFFE were accounted for).

| Paper | Page | where | Word for word | Space at the mark or script |
|---|---|---|---|---|
| chi-plue | 3 | inline-maths | ✓ | "RoBERTa" → "BASE": gap 0.32 pt, none. "pre-train" broken after "pre-" is a real hyphen: the paper writes "pre-train" mid-line elsewhere (p3 "We continually pre-train only", p1 "to pre-train BERT") ✓ |
| chi-plue | 5 | footnote-mark | ✓ | "." → "3": gap 1.11 pt, none ✓ |
| hardt-ellipsis | 3 | footnote-mark | ✓ | "." → "1": gap 5.02 pt, wider than this line's word space (". The" is 4.34 pt). The PDF also has a space character there. The space in "sets. 1" is right ✓ |
| nowak | 1 | footnote-mark (fragment) | ✓ ("liter-ature" joined) | "CNF," → "4": 0.71 pt, none; "4" → "matching": 3.97 pt, space; ")." → "5": 1.02 pt, none ✓ |
| nowak | 3 | inline-maths (fragment) | ✓ | "i" → "th": 0.67 pt, none (pdfium itself emits a line break between them, which is the #36 symptom) ✓ |
| arsiwalla | 3 | footnote-mark | ✓ | "qualia" → "1": 1.43 pt; "1" → ".": 2.20 pt, both well under a word space ✓ |
| arsiwalla | 14 | inline-maths | ✓ ("both," ends a line) | "Obj" → "P": 0.58 pt, none ✓ |
| liu | 2 | inline-maths | ✓ ("contribution" ends a line before "nE") | "n" → "E": 0.77 pt; "S" → "E": 0.16 pt; "E" → ".": 1.70 pt, none ✓ |

The fragments (Nowak p1, p3) are at least six words and each has a comment saying why, as the README asks.

## 2. Papers left without one

- Hardt has no inline maths: a scan of every small glyph that sits off the baseline of a body-size glyph found only line-break artefacts on the checklist pages 8–9 ✓.
- Liu has no footnotes: its raised small glyphs are affiliation marks and formulas; `footnotes = []` already ✓.
- Waskom and Biggs: only author affiliation marks ✓.

## 3. Existing truth unchanged

Loaded every truth file at af78e0b and at the PR head with `tomllib`: every key other than
`verbatim` is identical, and the old verbatim entries are all still there, unchanged and in the
same order. The diff only adds entries and comments ✓.

## 4. README and D-106

The README text matches D-106: marks and maths in line as printed, Unicode symbols, a space only
where the page shows one, superscript first when stacked, the two new `where` values, 3 to 7
sentences, "say in a comment when it has none". Text stays exactly as printed (no trimming) ✓.

## 5. Tests

- `VERBATIM_PLACES` gains the two values; `MAX_VERBATIM` 7 ✓.
- New check: a `footnote-mark` sentence must hold one of its page's marks. Tried by hand: removing the mark from a sentence makes it fail ✓.
- `NOT_YET_ONE_BLOCK` is compared with `==`, so #36 must remove both entries once fixed ✓.
- Mutation check of the corpus layout test: I changed four truth strings in a scratch worktree ("environment. 3", "RoBERTa BASE", "CNF, 4", "sets.1"). `test_verbatim_sentences_are_inside_one_block` failed for all three papers. So the new sentences really guard the spacing that D-106 cares about ✓.

## 6. Runs

- `ruff check`, `ruff format --check`, `lint-imports`, `deptry src`, `pytest -m "not slow and not benchmark"`: 548 passed, 17 snapshots passed.
- `HYPOTHESIS_PROFILE=nightly pytest -m "not benchmark"` (whole suite incl. slow): 548 passed, 17 snapshots passed, 7 min 45 s.
- CI on 33343c9: tests on ubuntu, macOS and Windows, lint and layers, licences, security, CodeQL all green.

## Nits (not blocking; deferred to issue #82)

- **N1.** `footnote_marks` check uses a plain substring test, so a mark "1" would also be found inside "2019" or "[124]". It passes today because every entry holds its mark. A digit boundary (`(?<!\d)mark(?!\d)`) would make it exact; all four current entries pass that stricter form (Nowak p1 matches 4 and 5).
- **N2.** README: the fragment rule names "a stacked formula" as something that cannot be written in line, while the next paragraph says a superscript stacked above a subscript is written in line, superscript first. Saying "a fraction or a formula built over several levels" would avoid the clash. The README could also cite D-106 next to #39.
