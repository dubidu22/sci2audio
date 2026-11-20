# PR #359, answer to review round 2

New head: f876880. It holds the fix commit 91f9324 on ff55995, then merges of main bd3be17 and 0af10d0, with no force-push. The label ci:full is set.

- **B1, fixed:** `numbers_de._fractions` leaves a fraction as printed before a unit chain only when the power after it is left too. `_power_left_after` now takes a lone letter power (not a statistics square) or a chain whose last base passes `_unit_chain`, so the power is read as a unit power on both runs. The six B1 shapes read as on main again ("3 Viertel kg x Quadrat", "3 Viertel m x hoch minus 1", "3 Viertel m s x Quadrat", "ein halb kg R Quadrat", "ein Fünftel m R Quadrat", "2 Drittel s t Quadrat"). They are pinned as rows in `de-numbers-a-unit-power-after-a-fraction`.
- **Merge of main bd3be17:** `SECOND_RUN_EXCEPTIONS` is now empty in both regression test files. The #324 entries went with main, and the #320 and #321 entries went with this PR.

Checks on f876880:
- Fast suite: 5316 passed, 1 skipped, 0 xfailed.
- ruff, ruff format and lint-imports are clean.
- All 13 corpus documents are byte-identical to main.
- Nightly seeds 7, 555 and 8080 on numbers, units and runner: 555 is clean. Seeds 7 (`310^250 000 000`, #210) and 8080 (`3 × 10−410^2`, #340) break the numbers contract on main 0af10d0 too, and both read the same on both runs on the #361 branch.
- The macOS failure on 670eeba was the reader start-up timing that main 0af10d0 fixes.
- The PR body has the round 2 notes and these numbers.
