# Review of PR #239, round 2 (head 71eae11)

Diff since round 1 (8d45e56..71eae11): two lines in two files, nothing else.

- F1 fixed: `tests/unit/test_app_corpus.py` asserts `set(done.report.not_run) ==
  set(GERMAN_LATER_STEPS)` for the German paper.
- F2 fixed: the one `[[miss]]` in `tests/regression/line-end-hyphens-de.toml` ends its `why`
  with "(#240)"; the PR body says "One miss is listed (#240)".

Local: test_app_corpus.py and test_textprep_hyphens.py, 136 passed, 9 snapshots unchanged.
Main still at 0bb973f, so the branch is up to date.

Verdict: review passed. Merge by squash pinned to 71eae11 once CI is green.

Deferred: #240 (v1.2, German compound split again at a line end). Issue edits made in review:
#130 acceptance line (remove "numbers"/"statistics" from GERMAN_LATER_STEPS), note on #156.

Merged: squash c19cb0d (head 71eae11) at 03:22Z, 14 Nov 2026.
