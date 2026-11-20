# Review of sci2audio PR #94 (issue #64), round 2

Reviewed head b76826e, 13 Nov 2026. That head is main (660d21f) merged in as f357011, plus the fixes in 639fdc5 and b76826e. The author's item-by-item answer is https://github.com/dubidu22/sci2audio/pull/94#issuecomment-6841568702.

**Verdict: passes. Every round-1 item is fixed.**

| Item | Status | Checked |
|---|---|---|
| M1 default job left notes out | fixed | `JobSettings.switched_off` defaults to `DEFAULT_SWITCHED_OFF`, and a settings file without the key gets it too. The hardt app report now shows Footnote texts "0 applied, 2 switched off"; its note reads "Footnote 1." and its mark is removed. There are new tests for the default job and for the settings file. |
| M2 five fast tests failed on the merge | fixed | `test_app_corpus.ambr` is regenerated and the diff is explained in the PR body. Every placeholder reads its notice, and the reference-list removals fall only in the deselected References chapters. The app property test now asserts that every edit comes from a built-in step and that no footnote-texts edit is accepted by default. That is a fair narrowing, not a weakening. |
| M3 titles matched two ways | fixed | `app.chapters.REFERENCE_NAMES["en"] is textprep.REFERENCE_TITLES`. `textprep.is_reference_title` uses the app's number pattern, case rule and closing-punctuation rule. An agreement test runs both on 28 titles. My probes: "References:" and "A.1 References" are now removed by the step, while "References and notes" is read (it is not one of D-132's names). |
| S1 "1." or "1)" after the note's mark | fixed | My probe now gives "Footnote 1. Measured." for both. "1.5 mm" is untouched, because "." is absorbed only when white space or the end of the note follows. There is a new regression case. |
| S2 "FIG. 3" and "Fig.3" | fixed | My probes now give "Figure 3 is skipped." for both. There is a new regression case. |
| N1 corpus test matcher | fixed | `test_no_reference_list_is_read` now finds sections at any level with `is_reference_title`. |

## Checks on b76826e

- ruff, ruff format, lint-imports (2 kept) and deptry are clean.
- Fast suite: 1146 passed, 38 snapshots passed.
- Nightly Hypothesis profile on the textprep, regression, conformance, documents, app script, chapters and settings tests: 427 passed, 14 snapshots passed.
- GitHub CI is green on Linux, macOS and Windows, and the branch is 0 commits behind main.

## Effect on the decisions

None of D-142 to D-148 changes in substance.

There is one detail of D-146 matching. Titles now match exactly as the app's chapter choice matches them:
- a trailing "." or ":" is ignored;
- a printed number has at most two digits;
- "A.1"-style numbers are accepted.

This carries out the D-146 line "treated the same way by both". The set of names and the rules (any level, notes and furniture kept) are unchanged. It also does the English part of issue #95.
