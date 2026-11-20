# Review of PR #128, round 2 (head de04e09)

**Verdict: approved.** No must-fix or should-fix left. Merge after updating the branch with main
(#124) and green CI on all three systems.

## Round 1 items

- **M1 (wrapped line loses word spaces): fixed.** `_Line.stacks` now needs the char after the
  line's first letter and at most `STACK` = 2 em back (STACK approved as D-320). My wrapped-line
  probes (Times 10 pt on 10.5/11/11.5/12 pt leading; 12–14 pt with a subscript above) all read
  "Then the word1 is next.". On the corpus `stacks` now fires 60 times, all inside maths in Nowak
  and Liu, at most 1.94 em back (it was 459, many of them line wraps up to 63 em back).
- **M2 (stacked fractions as wrong numbers): fixed.** Liu reads "1 2{Lˆ", "3 2at", "1 22σtot".
  The golden diff has no removed digit-to-digit space left.
- **S1: deferred** to #141 (open). **S2: done** (main #121 merged; main has since moved to #124,
  updated through the API below). **N1: done.**

## Checks on de04e09 merged with main 1064e18

- Golden character diff against 1064e18: layout 556, extraction 481 spaces removed, nothing
  else; textprep rules 11 and links 2 contexts spaces only; furniture counts 63→62, 6→4.
- Text-at-offset invariant on all 7 papers: 0 failures.
- Spoken scripts against main: Chi, Hardt and Waskom unchanged. Arsiwalla 15, Biggs 7 and Liu 184
  removed spaces. Nowak 170 removed spaces, plus the sentence cuts of #141.
- ruff, format, lint-imports (3 kept), deptry clean; fast suite 2139 passed; nightly Hypothesis on
  `test_layout*.py` and `test_extraction*.py` 429 passed; CI on de04e09 green on all systems.
- Mutations of the new guards: the extraction digit guard, the STACK bound and the `separators`
  digit guard are each caught by unit tests.

## Nits (no action needed for merge)

- Two mutants survive. One changes `chars[0].u0 < char.u0` to `<=` (a char starting exactly
  at the line's first letter). The other drops `gap < 0` in the `separators` digit guard. No test
  pins a digit piece after a digit piece with a small positive gap. That case does not happen
  on the corpus.
- An exponent set close ("3 × 10" + raised "8") reads "108" on main too: PDFium adds no
  space there, so this PR does not cause it. It belongs to #67 (N5 exponents).
