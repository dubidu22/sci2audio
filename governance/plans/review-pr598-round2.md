# Review PR #598, round 2 (app batch B16: #186, #207)

Reviewed head cc5e74c (fix commit on 215842e, test only). Verdict: **approved, merged**.

- Fix 1 done: tests/unit/test_app_job.py::test_the_picture_warning_comes_after_the_unreadable_one_and_before_the_rest asserts unreadable, picture, language in that order. Re-checked here: clean run 30 passed; mutant "picture before unreadable" fails it; mutant "picture appended at the end" fails it.
- Main had changed CHANGELOG.md (#600), a shared file (MRG-03): branch updated with a merge of main (update-branch API), new head e1c8d00. Diff against main is unchanged apart from a CHANGELOG hunk offset.
- CI on e1c8d00: all required checks green; reported-only Firefox 2/2 green this time, WebKit 1/2 and 2/2 green.
- Firefox flake: test_keyboard.py::test_the_main_flow_by_keyboard[firefox] failed once on 215842e (focus on the "result" heading); my re-run of that job was cancelled when the new head arrived; it passed on cc5e74c-based head e1c8d00. One failure in two runs, no code cause in this diff; reported only. If it fails again on any PR or nightly, it gets the D-374 quarantine issue.
- Squash-merged pinned to e1c8d00: main 7e68106. Main CI green. #186 and #207 closed with a comment.
- Deferred: #605.
