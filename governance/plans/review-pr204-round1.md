# Review PR #204, round 1 (issue #163, inline marks in `rows_of`)

Reviewed head afe9eb9 (main b09f18f merged in, PR #200). Earlier head 767c7cf gave the same results.

## Verdict

Approve after two should-fixes, both tests only. No must-fix.

## What I checked myself

- **Fast suite** (ci profile, Python 3.12.13): 3169 passed, 1 skipped, 62 snapshots passed (on 767c7cf). ruff, format and lint-imports clean.
- **Nightly layout properties** (`HYPOTHESIS_PROFILE=nightly pytest tests/unit/test_layout*.py -k "not corpus"`): 257 passed. The #199 failure in the PR body did not come up.
- **Goldens.** The snapshots match the code (62 passed, so regenerating gives no diff). I also rebuilt all 7 papers on main and on the PR and compared the blocks. chi, hardt, nowak, arsiwalla and waskom are identical: kind, text, parts, offsets, labels and sections. The text at each line part's offset is intact, and every item is in exactly one block. In liu (146 → 134) and biggs (82 → 78), each changed hunk replaces a run of PARAGRAPH blocks with fewer PARAGRAPH blocks holding exactly the same parts. Only the paragraph cuts move. Three graphics (liu p2-d121, p2-d135, p3-d200) now stand just after their host line instead of at the end of a cut block. Every other graphic keeps the same anchor as on main.
- **Spoken script** (`sci2audio script --chapters all --ignore-settings`, main b09f18f against afe9eb9): five papers byte-identical. In liu and biggs, with all whitespace stripped, the only difference is liu's "⟩ = i∂δ" → "⟩ equals i∂δ". This is the furniture snapshot's 85 → 86. With whitespace kept, every hunk removes a mid-sentence paragraph pause. The rest is the stacked-fraction glue accepted in D-442 (#202): "eℏ2me", "∂Emq∂q", "∂qδm,m′", "iRmm′q[f(0)", "∂Eq." (12 pauses in liu, 4 in biggs).
- **Textprep snapshots.** The citations corpus snapshot is identical once its numbers are masked. Furniture changes in one line, 85 → 86.
- **Nowak after merging main.** In the layout golden, PR vs main b09f18f touches only liu and biggs. The nowak change between 767c7cf and afe9eb9 is exactly #200's hunk.
- **D-439 inline flag.** Mutant "drop the `unit.inline` branch in `_hold`" is killed by `test_a_mark_in_a_line_is_no_float_before_a_line_that_opens_like_a_caption`. Mutant "`_inline` without its `holds` check" is killed by two tests (footnote, chi verbatim sentence).
- **D-440 shared test.** `graphics._minor` and `paragraphs.inline_mark` both call `geometry.minor`. The old `_is_line` held only drawings, so the refactor is equivalent. Dropping the mark branch or the line branch of `minor` each fails the corpus truth tests.
- **Union-of-pieces rule (D-438).** The following mutants are killed: "latest piece only" (bar-across test), "next piece only" (fraction-bar test), "no `holds`" (liu golden), "flush the marks after the new row" (liu golden), and "`holds` as overlap" (liu golden).

## Should-fix

**S1. The plan's negative case "a picture taller than `mark_height` still cuts as today" has no test.** Mutant "drop `inline_mark(element, size, settings)` from the deferral in `rows_of`" survives every layout test. The difference only shows on a printed line taller than 2 em. On a made-up page with "A Big" and "Title" set at 30 pt as two pieces of one line, and a 26 pt tall `Picture` between them inside the two pieces:
- the PR gives "A Big\nTitle", so the row ends (D-438: only a loose line or mark is read past);
- the mutant gives "A Big Title".

Please add this test, or one like it, to `test_layout_graphics.py`.

**S2. A mark in the last printed line of a page is untested, and dropping the final flush crashes.** Mutant "drop the last `found += [[mark] for mark in after]` in `rows_of`" survives the suite. On a made-up page whose last printed line has a fraction bar between its two pieces (`running(count=2)`, then "the share is 1" at y 128 and "2 of the whole." at y 129, with the bar Box(185, 132, 193, 132.6) read between them), the mutant raises KeyError. The PR gives one paragraph with the bar just after its line. Please add this as a test.

## Nit

**N1.** The PR body says the biggs ORCID icons "stay after their host lines". Only p1-d5 and p1-d6 lie inside a line ("2, Stuart Swerdloff 3, Phillip"). The other 20 drawings lie between pieces and stand at the block's end, as they did on main (#58 rule unchanged). Please correct the wording; no code change is needed.

## Survivors I accept as equivalent

- Dropping `_one_line(latest, ahead)` from the deferral. A deferred mark whose next piece is not on the same line is flushed before that piece's new row, which is today's output.
- `_inline` without `inline_mark`. Nothing inside a body-size line is too big to be a mark. S1's large-type case would distinguish it, but covering it is optional.
- `if unit.inline:` without `self.open` in `_hold`. No layout test distinguishes it, and the guard is clearly right.
