# Review PR #735, round 1 (ruleset 1.10.0, batch 004)

Thread: review-735 (Opus 5.5 medium). Author: layout-b-l3. Head reviewed: 401c78f824a721a5146db2d9ac419c38ce022fcc. Base: `main` at 880b170 (the PR is up to date with it). Date: 2026-11-22.

**Critical: no** (CRIT-01, CRIT-03, decided from the diff). The diff touches only `src/sci2audio/layout/order.py` (+6 −3) and `tests/unit/test_layout.py` (+33). No golden file, snapshot, regression case, layer contract, core dataclass, CI or packaging file, and nothing on `project_profile.critical_paths`. Labels: `lane:layout`, `risk:low`.

**Verdict: approved** (0 must-fix, 0 should-fix, 1 note). Nothing needs a commit. The dispatcher may give the merge go, pinned to 401c78f.

## Verified

- **The rule matches the split the gutter was found with.** `gutters.splits` (order.py:350) accepts a gutter `(start, end)` only if its left column is `x0 >= after and x1 <= end` and its right column is `x0 >= end`. The new `_column` counts a gutter as passed when `x1 > end`. For an element that `_spans` does not exclude:
  - it starts left of the strip and ends inside it: left, as before;
  - it starts inside or right of the strip and ends past `end`: right, as before;
  - it lies wholly inside the strip (`start <= x0`, `x1 <= end`): this case moves from right to left. That is the #679 heading `c0r0` (105.3–176.0 inside the strip 105.3–227.3).
  - With several gutters, an element wholly inside the second strip still passes the first (`x1 > end₁`), so it lands in the middle column. The sum stays monotone.
- **The cause is named in the PR** (acceptance criterion 2). The issue guessed a running head. The real cause is the reading order: the 10 % crossing allowance opens the strip at the short lines' ends, and the old `x0 >= start` rule then put the heading in column 1. I followed the numbers through `_strips` and `splits`: 5 of 50 crossings, and the strip opens at 105.3.
- **The `@example` is the issue's page** (acceptance criterion 1). `found_679()` rebuilds all 50 lines: the full widths, the short and centred lines per column, the row pitch 14 and y 80, in stored order. I checked these against the box list in #679.
- **VER-02: the new tests fail on the wrong code.** I put main's `order.py` back into the worktree, and both `test_a_centred_heading_atop_a_short_column_is_read_in_its_column` and `test_any_clean_column_page_reads_column_by_column` fail. With the PR's file restored, both pass.
- **Corpus unchanged (INV-07).** `uv run pytest tests/unit -k "layout or corpus or truth or blocks" -m "not slow and not benchmark and not browser"` gives 1152 passed and 63 snapshots passed, with none updated. `tests/unit/test_layout.py` gives 70 passed. `ruff check` and `ruff format --check` are clean.
- **Promised tests.** Both tests named under "Tests promised in the plan" exist in the diff under those exact names.
- **Size and scope (PR-06).** One rule line and its docstring, one unit test and one `@example`, as the plan says. No new dependency, file or option.
- **Comments (PR-05).** The new `_column` docstring says why the rule is what it is (the split `gutters` checked). The `(#679)` tag follows the module's existing habit of linking the case (order.py already had 3, layout/ has dozens). It does not narrate a change.
- **CI on 401c78f.** `CI passed` (success, 18:13:42Z), `tests (ubuntu-latest)`, both Chromium shards, lint and layers, licences, security, web paths and CodeQL are green. `governance pr checks` is green on its latest run (18:06:14Z); the earlier failing runs of that check predate it. A non-critical PR needs no three-system run.
- **Form.** The title follows `<area>: <outcome> (#N)`. The body has `Closes #679`, IN-01, a test summary, the licence note, the risk and the out-of-scope section.

## Findings

- **N1 (note, no action).** `_columns`' docstring (order.py:442) still says the elements go "by the column their middle stands in". Neither the old rule (`x0 >= start`) nor the new one (`x1 > end`) looks at the middle. The wording comes from before this PR, so it is not this PR's finding. A later layout PR that touches `order.py` can correct it in passing.
