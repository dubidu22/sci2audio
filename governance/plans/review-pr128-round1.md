# Review of PR #128, round 1 (issue #36: a space only where the page prints one)

Reviewed head e9ec24c, also merged locally with current main (8f0aee6, #121). Plan:
`plans/issue36-line-joins-plan.md`, decisions D-274 to D-280.

**Verdict: changes needed (2 must-fix).** The design is right and the golden work is clean;
both must-fixes are narrow guards with a test each.

## What I checked, and what held

- **Golden files, character diff of base 088abee against the head:** layout 561 spaces
  removed, extraction 486 spaces removed, nothing else changed (same line counts, every
  opcode a deletion of " "). Textprep rules 11 and citations/links 2 contexts: spaces only
  (the rest is the fixed-width context window shifting). Furniture: 63→62 and 6→4
  set-aside counts, as the PR says.
- **Page crops:** "qualia1." (Arsiwalla p3), "language 5." (p9, space before the mark, none
  after), "5https://…" (Chi p11), "sets. 1" (Hardt p3) all match the page.
- **Text-at-offset invariant** on all 7 papers (every line part of every block,
  `block.text[start:start+len(line.text)] == line.text`): 0 failures. No extracted line starts
  or ends with white space.
- **Real space characters** from the file are always kept (code path and the mutation below).
- **Spoken script, main vs PR, all 7 papers, all chapters (`sci2audio script`):** Chi, Hardt,
  Waskom unchanged; Arsiwalla 15, Biggs 7, Liu 189, Nowak 170 removed spaces. Beyond spaces,
  only Nowak's sentence cuts move (S1). #127: nothing spoken changes (Chi script identical;
  Liu formulas (2), (3) are notices).
- **Links regression case** `link-only-footnote-mark-set-close` fails when the D-278 rule is
  removed. `NOT_YET_ONE_BLOCK` is empty and the corpus truth tests pass.
- ruff, ruff format, lint-imports (3 kept), deptry: clean. Fast suite after merging main:
  2121 passed. Nightly Hypothesis profile on `test_layout*.py` and `test_extraction*.py`:
  419 passed. CI on e9ec24c green on all three systems.
- **Mutations** (each rule removed once, layout/extraction/links tests): every new rule is
  caught by at least one non-golden test (touch, shift, SPACE threshold, `before`, `stacks`,
  real space, `separators` word_space/stack_reach/reach, paragraph, footnote and `read_rows`
  joins, `_before`, `part_ends`, `kept` joins, links label), except the `size > 0` guard (N1).

## Must-fix

**M1. A wrapped line can lose every real word space after a script (`extraction/pdf.py`,
`_Line.stacks`).** `stacks` only asks that the new char starts between the line's first letter
and its reach, with any vertical overlap. The next printed line of a paragraph satisfies that
whenever loose boxes overlap (tight leading, or a subscript in the line above). Then `before`
is the right end of the line above, and `_white` measures every baseline-change space of the
whole new line from there, so all are dropped. On the corpus `stacks` fires 459 times, many of
them line wraps up to 63 em back (Biggs, Chi); it changes no corpus text only by luck.
Reproduction with `pdf_maker` (Times-Roman 10 pt, superscript "1" then 4 pt of white before
"is next."): leading 10.5 and 11 pt give `"Then the word1is next."`; 11.5 pt and more, or main,
give `"Then the word1 is next."`. 10 on 11 pt is common. Also with 12 pt leading when the
line above ends in a subscript. Fix: a stacked script starts close to the reach, e.g.
`reach - char.u0` at most a small em bound (the layout's `stack_reach` is 2 em), and add the
wrapped-line test above.

**M2. Stacked fractions turn into different numbers in the spoken script.** The touching rule
(D-276) drops the generated space whenever the next char starts before the last one ends,
also across a baseline change, so a numerator and a denominator stacked under it are glued;
`separators` does the same for pieces. Spoken in Liu (main → PR):
- "ˆj = 1 2 {Lˆ, vˆ}" → "ˆj = 12{Lˆ, vˆ}" (printed ½)
- "vF = 3 2 at" → "vF = 32at" (printed 3/2 at, crop checked)
- "σ int OH = 1 22σ tot" → "σintOH = 122σtot" (printed 1/22)

Neither reading is good, but the PR's reads a wrong number (twelve, thirty-two, one hundred
twenty-two), against D-57. D-276 measured only same-baseline touching letters. Fix: never join
two digits on different baselines when the second starts back under the first (keep PDFium's
space in extraction, keep " " in `separators`); a test for a stacked ½ in extraction and in
layout; Liu's three sentences keep a space between the digits. (A real fraction reading is out
of scope.)

## Should-fix

**S1. Nowak's sentence cuts move.** With "N ." now "N.", the cutter reads a single capital
before a full stop as an initial, so four sentence ends after "∈ N." are no longer cuts and one
utterance is cut at a comma instead ("X, Y,⏎Z ∈ N. This yields"). Words are unchanged, pauses
move. Fine to defer: file an issue (cutter: a single capital after a maths symbol is not an
initial) and note it in the PR.

**S2. The branch is behind main (#121).** Merge main (no force-push); the merged tree passes
the fast suite locally.

## Nits

**N1.** `separators`: `and size > 0` is dead (an equivalent mutant): with size 0 the interval
`-stack_reach*0 <= gap < word_space*0` is empty. Drop it or say why it stays.

## Round 2 notes (paused 13 Nov 08:19 UTC, at Colin's request)

Head de04e09 (fixes M1, M2, N1; S1 deferred to #141; main merged). Read the source diff: M1
bound (STACK = 2 em, after the line's first letter) and M2 digit guard look right. Checked an
exponent set close ("3 x 10" + raised "8"): reads "108" on main too (PDFium adds no space
there), so not a regression of this PR. Not yet done: wrapped-line and fraction re-probes,
golden diff 556/481, fast suite, nightly, mutation of the two new guards, CI check. Main has
moved again (#124), so the branch needs main merged before the merge.
