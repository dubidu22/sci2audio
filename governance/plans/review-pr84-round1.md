# Review of PR #84, round 1: build overlapping spans instead of filtering (#47)

PR: https://github.com/dubidu22/sci2audio/pull/84, head `a7772b0`, base `af78e0b`.
Reviewer: separate review thread, 12 Nov 2026. Test-only, non-critical.

## Verdict

Pass. No must-fix and no should-fix findings. One optional note (no action needed).

## What I checked

1. **Core's rule equals the test's independent rule.** Brute force over every pair of spans
   in blocks of 0 to 5 characters (two blocks, both argument orders): `check_edits` refuses a
   pair exactly when `overlaps()` in `core_strategies.py` says they overlap. So covering
   `overlaps()` means covering core's rule (shared character, a position strictly inside a
   span, two marks at one position, and no overlap across blocks or at an edge).
2. **The strategy produces every overlapping span, and only those.** Analysis of
   `overlapping_spans`, case by case:
   - empty span at an edge (0 or block length): only the equal empty span overlaps, and that is what it returns;
   - empty span at an inner position p: the equal span, or any `(s, e)` with `s < p < e` (both ranges are complete);
   - non-empty span: an empty span at any position strictly inside it (when its length is 2 or more), or any non-empty `(s, e)` with `s < end` and `e > max(s, start)`, which is exactly the set of non-empty spans sharing a character.
   Confirmed empirically: a scratch Hypothesis run collected the strategy's output for every
   span in blocks of 0 to 5 characters; all 350 overlapping pairs appeared and every output
   satisfied `overlaps()`. So the test proves the same property as before over the same set of
   pairs; nothing is narrowed. The second span always lies in the first one's block, which is
   correct: spans in different blocks never overlap.
3. **Argument order.** `st.permutations([first, second])` restores both orders, which the old
   symmetric draw had. The `{first, second}` check of the error still holds when the two edits
   are equal.
4. **Mutation check** on `check_edits` with `HYPOTHESIS_PROFILE=ci`: 5 of 6 mutants fail the
   test (dropping the two-marks-at-one-position clause, `b.start < a.end - 1`, ignoring empty
   second spans, requiring `b.end <= a.end`, requiring `b.start > a.start`). The surviving one
   (ignoring an empty *first* span unless the spans are equal) is equivalent: after sorting,
   an empty first span can only overlap an equal one.
5. **No health check suppressed, no profile changed.** The diff touches only
   `tests/unit/core_strategies.py` and `tests/unit/test_core_properties.py`;
   `tests/conftest.py` is unchanged. The remaining `assume` in the file belongs to
   `test_a_document_that_loses_an_item_is_refused` and is out of #47's scope.
6. **Runs on the PR head:**
   - ruff check, ruff format --check, lint-imports, deptry: clean.
   - The test under the `dev` profile with `--hypothesis-seed=1..100`: 0 of 100 fail (the PR ran 1..60).
   - The issue's nightly seed `259931665419182006590228805532880943070` under `nightly`: passes (25 s).
   - The whole fast suite under `HYPOTHESIS_PROFILE=nightly` on `a7772b0`: 548 passed, 17 snapshots passed, in 6 min 36 s.
   - CI on `a7772b0`: all green on Linux, macOS and Windows.
   - Main had moved by one commit (df76ad6, PR #81, truth files and two corpus tests only, no overlap with this PR). Branch updated with a merge commit to `5679af8`; CI on `5679af8`: all green on Linux, macOS and Windows.

## Optional note (no action)

- About 44% of the PR's own 3000 samples were the equal empty case, because an empty first
  span at an inner position returns the equal span half of the time. That is fine for a test
  that must prove refusal; it only spends examples on the cheapest case. Not worth a change.

## Merge

Review passed; merged on the coordinator's instruction, pinned to `5679af8`.
