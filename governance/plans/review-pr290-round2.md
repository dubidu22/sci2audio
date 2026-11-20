# Review of PR #290, round 2 (issue #286)

Reviewed head: 9fde5d2 (main 407f5bd merged in as 7f646b7, fix commit 9fde5d2).

## Round 1 findings

| Item | Status |
|---|---|
| M1: view showed set-aside joins | Fixed. `joined_hyphens` now runs `run_steps(document, StepContext(language), BUILT_IN_STEPS, record's categories)` and keeps only ACCEPTED `line-end-hyphens` edits of length 2 (unknown category strings are dropped). Tests: `test_a_hyphen_in_a_link_at_a_line_end_shows_as_printed` (the three URL cases) and `test_a_join_inside_a_removed_reference_list_is_not_shown_as_joined`. |
| N1 | No change needed (as stated). |
| Merge main (#288) | Done, 7f646b7; the merged `_notices`/`_block_view` code-block changes from #288 are intact. |

## Corpus re-check (same scratchpad script)

View joins now equal the runner's accepted joins on all 8 papers (chi-plue 80/80, hardt 58/58, nowak 38/38, maass 34/34, arsiwalla 53/53, liu 77/77, seaborn 9/9, pymedphys 0/0).

## Runs at 9fde5d2 (local)

ruff, format, lint-imports (3 kept), deptry clean; fast suite 4,301 passed, 1 skipped; browser suite 51 passed. GitHub CI on 9fde5d2: every check green, PR mergeable (clean), base main 407f5bd.

## Verdict

Approved. Merge by squash pinned to 9fde5d2.
