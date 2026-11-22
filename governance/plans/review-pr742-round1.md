# Review PR #742, round 1 (#709: the regression goal strings name no review rounds)

Thread: review-b004-a (Opus 5.5 high), batch 004 slot A. Author: infra-b-i5. Head reviewed: 85dd31209b113b32063f4cf1c6c756112e29ec99. Base: 1bebb96 (main is now 3fb4d1b, #741; GitHub says CLEAN). Date: 2026-11-22.
**Critical: yes** (CRIT-01: `tests/regression/english.toml` and `german.toml` are golden files; `risk:high`, `lane:textprep`). Plan: `plans/infra-b-i5-plan.md` §5, approved as D-878. No file in common with #740, so the two merge in either order.

**Verdict: approved** (0 must-fix, 0 should-fix, 2 notes).

## Verified

- **Only `goal` strings change.** I parsed both files with `tomllib` at 1bebb96 and at 85dd312 and compared every top-level key and every case key by key. English: 259 cases, 24 goals differ. German: 206 cases, 39 goals differ. Every other value is equal (`id`, `audit`, `issue`, `language`, `blocks`, `sections`, `expected`, `utterances`), the case count and order are the same, and no key was added or dropped. In the text diff, every changed line is a `goal = ` line.
- **Each goal only loses its review tag.** A character diff of the 63 goals shows deletions only ("review of ", "review round 2 of ", ", F1", "Review von ", ", Runde 2", " review round 1, B2" and the like), with the issue, PR and D-numbers kept. The one exception is N1.
- **Goals are not compared to output.** `sci2audio.testing.regression` (`regression.py:150`) only checks that `goal` is a non-empty string; the two regression tests check `case.goal` is truthy. So no snapshot or regression result can change. Locally on 85dd312: `test_review_tags.py`, `test_textprep_regression.py`, `test_textprep_regression_german.py`, `test_textprep_hyphens.py`, `test_textprep_units_abbreviations.py`: 1685 passed, 6 xfailed (the known D-719 second-run cases).
- **The new test is red on the old goals (VER-02).** With the base's `tests/regression/*.toml` put back on the head, `test_no_regression_goal_carries_a_review_tag` fails and lists the tagged goals; with the head's files it passes.
- **`REVIEW_TAG`.** The added branch `\b(?i:review)\s+von\s+(?:PR\s+)?#\d+` matches "(Review von PR #377, Runde 2)" and leaves "ein Review von Fachleuten" and "in der zweiten Runde 2019" alone; the three new known forms and the two plain German phrases are cases of the existing parametrized tests. The wider pattern still passes the comment and docstring scan (`test_no_comment_or_docstring_carries_a_review_tag` green). No goal left on the head holds "review", "Runde" or a finding name (the only hit of a search, 'S3.1' in `de-notice-dotted-caption-labels`, is a caption label of the case's subject).
- **Lane.** Files: `tests/regression/*.toml` and `tests/unit/test_review_tags.py`; `governance pr checks` green.
- **CI on 85dd312.** `CI passed`, `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, lint and layers, `governance pr checks`: green. The `ci:full` label is off.
- **Form.** Title `textprep: ... (#709)`; body has `Closes #709`, the plan, the golden-file diff statement (INV-06) with the parse check, the promised node ID, test summary, licence (none), risk.

## Findings

### Notes

- **N1.** `tests/regression/german.toml`, case `de-numbers-date-after-a-dash-without-bis`: the bare finding name "(F2)" was replaced by "(PR #263)", which is a small addition rather than a deletion, since `REVIEW_TAG` does not match a bare finding name. It names the same source as the "(PR #263)" earlier in the goal and the body discloses it; accepted.
- **N2.** `tests/unit/test_review_tags.py:46-47`: the German branch covers "Review von PR #N" only, not a "Runde 2 von PR #N" order, as the English "round 2 of #450" branch does. No goal or comment uses that order today; if one appears, the comment scan or this test is the place to add it.

## Merge

Gate: no open B/M finding. A critical PR needs all three systems green on the merged head (MRG-01, D-580): they are green on 85dd312. If the branch is updated to main first (merge commit), re-check the diff and CI on the new head.
