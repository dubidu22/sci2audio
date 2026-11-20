# Review PR #270 (#266), round 1

Reviewed head a1296e1 on main 2c9adac. Non-critical (German only, no golden file).

## Checked and fine

- Regression case `de-citations-decimal-interval-in-round-brackets` fails on main (2c9adac source, PR tests) and passes on the PR. Five new unit rows fail on main too.
- `all([])` cannot hit: `numeric_aside` needs at least one square bracket, so an aside always has one.
- English untouched: 7 English hand probes give identical output on main and PR (citations step and whole chain); the PR's English guard `It holds ([1,2; 3,4])` -> `It holds.` holds.
- True German source lists still go: `([1; 3])`, `([1; 3], [5])`, `([1, 3])`, `([12])`, `(vgl. [1; 3])`, `([1,2])`, `([1,2, 3,4])` -> removed, as on main.
- Idempotent: all 36 hand probes stable on a second run (citations step alone and whole chain). New intervals kept on both runs: `(vgl. ...)`, `(siehe ...)`, `([1,2;3,4])`, `([1,2 ; 3,4])`, `(([1,2; 3,4]))`, `KI ([1,2; 3,4])`, `95 %-KI (...)`.
- Gates: ruff check, ruff format --check, lint-imports, deptry clean. Fast suite 4,207 passed, 1 skipped.
- Nightly profile on the five textprep files: seeds 31337, 4242, 90210 pass (845 each). Main fails 31337 (6 with the PR's tests).
- Own fuzz, 2 x 4,000 random German shapes of brackets and citations through the step and the whole chain twice: main 4 second-run breaks, PR 3; the one fixed is a #266 shape. The 3 left are also on main: filed as #271.

## Finding 1 (fix): the PR keeps the aside only if ALL inner brackets are intervals; D-534 says ANY

The approved plan (D-534): "If any inner bracket is an interval, the round bracket stays and each inner bracket is judged on its own." The PR uses `all(...)`, so a mixed aside is still removed whole and the interval goes with it:

| printed | PR (`all`) | with `any` |
|---|---|---|
| `Das gilt ([12]; [1,2; 3,4]).` | `Das gilt.` | `Das gilt (; [1 Komma 2; 3 Komma 4]).` |
| `Das gilt ([1,2; 3,4]; [12]).` | `Das gilt.` | `Das gilt ([1 Komma 2; 3 Komma 4];).` |
| `Das gilt ([1,2; 3,4], [12]).` | `Das gilt.` | `Das gilt ([1 Komma 2; 3 Komma 4],).` |

Why `any`: the interval is measured content, not a source (D-57, faithful text); and the same aside with an author-year citation in front, `( (Müller, 2019) [12]; [1,2; 3,4])`, already keeps the interval on main and the PR (`(; [1 Komma 2; 3 Komma 4])`), so `all` makes two near-identical printed shapes read differently. The stray ";" is the cost; it is already on main for that shape and is not spoken. Filed #272 for the separators.

Measured with `any` (one-word change): all 36 hand probes stable on both runs; nightly seed 31337 on the citations, links/citations-de and both regression files passes except the one row that pins the old mixed reading (`test_the_citations_step_alone_decides_an_aside_the_same_on_a_second_run[Das gilt ([12]; [1,2; 3,4]).-Das gilt.]`); fuzz identical to the PR.

Wanted: `any(...)`; change that row to the kept interval; add the mixed shapes to the second-run (whole chain) rows; update the comment, the PR body table and its "An aside that mixes ..." paragraph.

## Filed (not asked of this PR)

- #271: `((Müller, 2019) Schmidt, 2020)` (and English `((Smith, 2019) Jones, 2020)`) reads the rest on run 1, removes it on run 2; whole chain too. On main. Suggest v1.1 (same class as #266).
- #272: separators left inside a round bracket after an inner citation is removed (`(; [1,2; 3,4])`, `(; )`). On main. Suggest v1.2 with #259.
