# Light audit: textprep batch B5 (#593), 19 Nov 2026

Auditor: B5 review thread (Opus high). Scope: the merged diff of #593 (b32612d, which closes #536, #557, #483 and #527) on main, read against what merged in the same window: #582 (web), #598 (app), #600 (layout) and the dependency bumps #513 to #515. I checked contract and core touches, cross-PR and cross-lane effects, regression rows, the corpus and the CHANGELOG (D-768). B5 had one PR, so there is no cross-PR issue inside the batch.
**Result: clean, 0 defects.**

## Contract and core
- The batch changes `src/sci2audio/textprep/` only: `citations.py`, `notation.py`, `numbers.py` and `numbers_de.py`. There is no change to `sci2audio.core`, the text-step interface, `sci2audio.testing`, a `lint-imports` layer, the regression loader, `read_twice` or `SECOND_RUN_EXCEPTIONS`.
- There is one new import inside textprep: `citations` reads `numbers_de.YEAR_WORDS`, made public from `_YEAR_WORDS`. `numbers.py` already imported `numbers_de`, so this adds no import cycle, and `lint-imports` is green. `YEAR_WORDS` has two readers: `_is_year` (unchanged) and `CitationWords.periods`. A word added for years now also keeps a German bracket as a date, which is the intended coupling. It is named in the field's comment.
- `as_one_arrow` and `arrows` are shared in `notation.py`. Only `find_numbers_de` masks, while English reads the unmasked text, and the grid needs no mask there. I accept this asymmetry: it is named in the round-2 answer. If an English rule ever refuses a number after `−`, it will need the same mask.

## Cross-lane (same window)
- **#600 (layout, "Listing" captions and code blocks across a page break) and #598 (app report quoting):** I compared the corpus scripts on 7e68106 (main before B5) and b32612d (after), 13 sources × default / figures off / figures and formulas off. Only acl2023-nowak changes, with 6, 17 and 17 lines. These are the exact lines #593 listed against ad6b94f, so #600's new code blocks and #593's arrows do not meet in the corpus.
- **#582 (web player figures):** it shares no file except CHANGELOG.md. The review thread resolved that conflict by merging main into the branch, and the src and tests diff was checked unchanged before the merge.
- **Dependency bumps (#513 fastapi, #514 mdit-py-plugins, #515 markdown-it-py):** none touches textprep.

## Second-run contract on main b32612d
- Arrow grid (840 texts, 5 arrows × 42 number shapes, en and de): 0 unstable.
- A wider grid with statistics, units, citations, abbreviations, dates and clock times after the arrows, with a second arrow later in the text: 1,806 texts, 0 unstable on b32612d and 0 on 7e68106.
- The review's probe files (s1 to s6, 74 shapes): 0 second-run differences.

## Regression rows and goldens
- Added: 5 German rows (47 lines) and 1 English row (8 lines). No line of an earlier row changed (numstat: 0 deleted).
- The goals are honest: both arrow rows say that the voice still says "minus one" for the raised `−1` (#589), and the #557 row names the as-printed alternative ("drei. Mai").
- The only golden change is `test_textprep_furniture.ambr`: nowak `numbers-and-units: accepted` goes from 59 to 65, the six arrow joins in read blocks. `test_app_corpus` goldens are unchanged.

## CHANGELOG (D-768)
- There are three Unreleased "Fixed" lines covering #483, #536 with #557, and #527, beside #598's line after the conflict merge. One nit, no change needed: the #527 line names only "←−" and "−→". The longer "−−→" and "←−−" forms (round-1 F1) are covered by the same sentence's "a long arrow".

## Follow-ups (all filed, proposed v1.2.x)
- From the author: #588, #589, #590, #591 and #592.
- From the review: #594 ("Uhr" twice when it stands on the next line), #595 (two-word German dating brackets), #597 (German line-end "-" before "=" on a second run) and #606 (40 old `_ordinals` mutants).

## Ledger
The review line is in `ledger/review.md` (3 rounds, 0 compressions, 0 CI reruns, 0 post-merge defects so far).
Lesson for thread sizing: two of round 1's findings came from tools outside the plan's checks (a neighbour-shape grid and nightly seed 31337), not from the PR's own fuzz. Future textprep plans that replace a glyph should name a neighbour grid in their checks.
