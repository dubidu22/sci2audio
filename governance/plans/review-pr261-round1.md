# Review: PR #261, round 1 (R3 of #80: tests for mutation survivors, D-531)

14 Nov 2026 ~09:22 UTC on head 969c391, base release/1.0 87ba1f5 (up to date).

**Verdict: approved, no fixes.** Merge by squash when CI is green, then cherry-pick forward to main as a PR (as #234 → #244), per the coordinator.

- Tests only: 4 files, +31 lines (characters, numbers, statistics, units). No source, golden file, snapshot or regression-case change.
- Each new case pins current behaviour that changes what the listener hears: non-length units read "cubed"; time bounds (24:00, 10:59 and "pm" after are times; 25:00, 10:60 and 10:5 are ratios); "x <-2 y" is a comparison with minus two, "x <- y" an arrow; a circumflex read across a soft hyphen and line end, with or without a zero-width space.
- Ran here: the four files, 426 passed. Hand mutants in `numbers._is_time`: `hours > 25`, `minutes >= 59`, and `or` → `and` for the time word are each killed by `test_the_bounds_of_a_time` (1, 1 and 3 failures).
- The remaining survivors and unchecked mutants are #260 (v1.0.1). The CI mutation workflow's speed is #246.

**Merged** into release/1.0 by squash pinned to 969c391 (all CI green): ca52ab3 (~09:22 UTC). Forward cherry-pick PR #262 into main opened (head 52cf291).
Forward PR #262 merged into main by squash pinned to 52cf291 (all CI green): 7174f46 (~09:26 UTC). Nothing deferred.
