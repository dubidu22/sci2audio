# Review of PR #277, round 1 (issue #276, D-540): textprep timing tests against a base run

Head reviewed: 8d4a19a. Reviewer thread: "Review robust timing tests PR". Date: 14 Nov 2026.

## Verdict

One must-fix. Everything else holds. Not ready to merge until F1 is fixed.

## What was checked

- **No production code changed.** `git diff origin/main...HEAD` touches only `tests/unit/` (11 files, +195/−90).
- **Helper (`tests/unit/linear_time.py`).** Logic is right: best of 3 with gc collected then off, base at `size // 8`, limit 32 × max(base, 2 ms), result of the large run returned.
- **Fake-clock tests are real.** Each of these helper mutations makes one of `tests/unit/test_linear_time.py` fail: `LIMIT = 65`; `FLOOR = 0.0`; dropping the floor from the assert; timing the base at full size.
- **The 2 ms floor.** It never applies on today's cases: the smallest base run measured is 3.9 ms (statistics long-space). It can only hide a slow-down whose large run stays under 64 ms, which is not a blow-up worth catching. No action.
- **Per-case ratios (4 cores, serial).** 30 of 31 cases: base 3.9–114 ms, large 30–871 ms, ratio 6.7–9.4. The one exception is F1.
- **Mutations (slow versions applied to the source, converted test run):**

| slow version | test | result |
|---|---|---|
| sentence cutter counts the whole rest each cut (`width = end - start + 1`) | `test_a_long_text_without_a_full_stop_is_cut_in_linear_time` | fails, ratio 72.9 (0.104 s → 7.574 s) |
| footnotes: each note scans every block's mark list | `test_many_marks_and_notes_take_linear_time` (absolute `large < 2.0` dropped) | fails on its ratio check (4.94 s vs 40 × 0.065 s) |
| citations look-back unbounded (`_LOOK_BACK = 10**9`, the S2 slow version) | citations `test_a_long_block_takes_linear_time` and German links/citations | fails, ratios 67.0 and 63.4 |
| #263 look-ahead scans the removals instead of bisecting | `test_the_link_look_ahead_looks_at_one_removal_per_abbreviation` (unchanged by this PR) | fails (2,001,000 looks > 2,000) |
| citations bracket cap ×2 / ×4 (`_MAX_BRACKET = 8000` / `16000`) | German `test_long_german_blocks_take_linear_time[deep-brackets]` | **passes** (see F1) |

- **Suite runs.** Fast suite with `HYPOTHESIS_PROFILE=ci`: `-n 24` on 4 cores 4290 passed, 1 skipped (178 s); `-n auto` 4290 passed (127 s) against main's 4287 passed (110 s): +17 s on 4 cores. GitHub CI on 8d4a19a: all green, test-job times within ±25 s of main's last run. Acceptable. (A `-n 24` run with the default `dev` profile had 10 Hypothesis `too_slow` health-check failures in core, app and runner property tests. That is overload against the dev profile, which CI does not use; no timing test failed.)
- ruff check, ruff format --check: clean on CI.

## F1 (must-fix): the deep-brackets case no longer catches anything short of 17 s

`tests/unit/test_textprep_links_citations_de.py::test_long_german_blocks_take_linear_time[deep-brackets]`, text `"(" * n + "Müller 2019" + ")" * n`, size 20,000.

The citations step parses every bracket whose inside is at most `_MAX_BRACKET` (4,000) characters, at quadratic cost in the depth, and skips longer ones. Time against depth: 500 → 32 ms, 1,000 → 126 ms, 2,500 → 555 ms, 5,000 → 510 ms, 20,000 → 607 ms. The base run (depth 2,500) is already at the cap, so base and large take the same time: measured 542 ms and 561 ms, ratio 1.0. The limit becomes 32 × 0.54 s ≈ 17 s.

Measured consequence: with `_MAX_BRACKET = 16000` the large run takes 8.3–9.0 s. The converted test passes; the old test (`< 3 s`) failed it.

Fix wanted: give this case a check that does not grow with the cap. Acceptance: fails with `_MAX_BRACKET = 16000`; passes on today's code under `-n 24` on 4 cores.

One way that works (measured): time the deep nest against a reference text of the same length through the same two steps, e.g. `("(Müller 2019) " * 3000)[: len(deep)]`, both with `best_seconds`. Ratio today 6.0; with cap ×2 23.5; with cap ×4 88.0. A limit of 16 catches both raised caps with 2.7 times headroom. Any other check that meets the acceptance is fine.

## N1 (nit, optional)

`test_a_long_block_takes_linear_time` in `test_textprep_citations.py` has no `ids`, so its case names contain the raw text (`[[1] -25000]`, `[Smith (2019) shows it [3]. -4000]`). Give it ids like the others.

## Side finding (production, not this PR): issue #287

A block made of many deep nests costs about 0.14 ms per character in the citations step (20 nests of depth 1,990: 79,820 characters, 10.9 s). Robustness on hostile input only. Filed as #287 (no milestone; coordinator to assign).

## Observation (no action)

The #274 counted test counts reads of `_Removals._spans` only. A slow version that scans `_starts` linearly instead of bisecting is caught by neither the counted test nor the timing test (both pass with that mutation). It is a different slow version from the one on record in #263, which the counted test does catch. Not part of this PR's diff.
