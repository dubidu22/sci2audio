# Review: PR #769, round 2

- PR: #769 (PR 4 of #725/#726, web: generate the remaining chapters later), non-critical.
- Head reviewed: e2f635876d80b1ccc94760920dccb8c5a884d8aa (one fix commit, e2f6358, tests only).
- Thread: review-b005. Date: 2026-11-23.
- **Verdict: approved.** 0 must-fix, 0 should-fix, 0 deferred.

## Round 1 findings

Only `tests/unit/test_web_add_chapters.py` changed (+49 lines). This review re-applied both round 1 mutations on the new head:

- **S1** is fixed. With the vouch removed from `chapter_states`, `test_a_chapter_file_changed_after_it_was_made_reads_as_not_generated` fails. The test changes one byte of the MP3 and keeps its size, so only the vouch can tell; a deleted MP3 stops `current_audiobook` before the vouch is reached.
- **S2** is fixed. With `made_with = settings`, `test_generate_notes_the_projects_settings_not_the_forms` fails. That test checks `made` in `audiobook.json` while the job runs, and `audio.json` after it. The round 1 report said `audio.json` for the record written while the job runs; the test checks both.
- **N1 and N2** stay as they are, for the author's reasons. A second click can't start a second job (409 busy). Sharing `_kept` would change the app's API, which is outside this lane. Both were optional.

## Checks

- Locally, `test_web_add_chapters.py` passes (14 passed), and ruff and format are clean on it.
- CI on the head is green: tests on ubuntu, both Chromium shards, ZAP, governance, CodeQL, lint and licences. The report-only Firefox and WebKit jobs are green too.

## Notes

- **N3.** A chapter MP3 that was deleted makes `current_audiobook` fail as a whole, so the page lists no chapter states. That is #724's behaviour and not changed here. If a deleted chapter should come back as "not generated", that would need a new Issue.

## Summary

- Done: S1 and S2 verified fixed by mutation; CI green.
- Not done: none.
