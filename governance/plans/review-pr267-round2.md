# Review PR #267, round 2 (head 1354f40)

Author's answer: https://github.com/dubidu22/sci2audio/pull/267#issuecomment-6876825521

- R1 fixed: `_NEXT_WORD` ends with `\b(?![-‐‑])`; backtracking cannot split a word
  (no `\b` inside it). Probed: "Der 2. In-vitro-Versuch", "Vor-Ort-Termin", "Nach-Untersuchung",
  "Seit-Ansicht", U+2011 compounds all read the ordinal as on main; "2 Std. Ein-Euro-Jobs" one
  sentence as on main.
- R2 fixed by correcting the PR body and #264 (acceptance criterion: no cut after "i. V. m.",
  three corpus joins). Accepted.
- R3 fixed: Laut, Ich, Sein, Nichts, Etwas, Ja, Nein removed; trade-off in the list comment;
  test pins them as non-openers. "Der 3. Laut", "Das 2. Ich" read as on main. Cost: "Platz 3.
  Sein Bruder", "2 Std. Etwas später" stay one sentence, as on main (no regression).
- R4 fixed: "»" in `_OPENING`, "«" in `_CLOSING`. "Er sagte: »Es kam.« Dann" now cut (main
  not); English "»It was.« Then" also now cut (correct; English corpus unchanged).
- Corpus: all 13 outputs byte-identical to round 1 (so 11 identical to main).
- Fast suite 4,260 passed; ruff, format, lint-imports clean. Nightly seeds 555 and 31415 on the
  five textprep files: 860 passed each.
- CI: macOS failed `test_the_link_look_ahead_of_the_abbreviations_step_takes_linear_time[dense]`
  (#263's test), 1.687 s vs limit 8 x 0.2096 = 1.677 s. It times `AbbreviationStep.find`
  only, which this PR does not change (it adds a separate `reads_full_stop`). Passes 3/3
  locally. One re-run of the job requested.

Verdict: approve once CI is green.

## Outcome

- #274 test fix: PR #275 reviewed (count test fails on the old quadratic loop: 2,001,000 > 2,000;
  timing test now 8x text vs limit 32, gc off). macOS hit an unrelated English timing test
  (test_textprep_numbers pathological [dashes], 3.2 s vs 3 s) once; one re-run green. Branch
  updated with main 89a80d3 (#270), CI green, squash-merged aa71172 at 12:28:05Z. Closes #274.
- #267: main (aa71172) merged into the branch (2cb7a7c). #270 touched citations.py too; fast
  suite 4,275 passed, corpus and 80 probes identical to round 2, nightly seed 777 874 passed.
  CI green on all jobs. Squash-merged fea9874 at 12:33:47Z. #227 closed by keyword; #229 closed
  by hand with a note (not auto-closed).
- Filed in this review: #268 (v1.0.1, D-536), #274 (v1.1, D-539, now closed).
