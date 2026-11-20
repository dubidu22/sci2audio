# Review PR #481, round 3 (sentence-boundary batch PR 4, #460 + #455)

Head reviewed: 7393b60, one fix commit on 260d5f3. Main was 7d866bf, the merge base, so the branch was up to date. Earlier rounds: plans/review-pr481-round1.md and plans/review-pr481-round2.md.

**Verdict: approvable, and merged.**

## The fix commit
- It changes only `tests/unit/test_textprep_utterances.py` (+38). The source diff against 260d5f3 is empty.
- **S1 of round 2, fixed.** `test_a_closing_mark_of_an_inline_list_opens_no_bracket_for_cutting` has an en and a de case.
  - It kills mutant 27 (`depth -= 1`): 2 failed.
  - The baseline on 7393b60 passes: 1552 passed (`/home/user/probe/m481/run.py 0 27`, the same test files as round 2).
- The utterance tests on 7393b60 pass: 201 passed.

## CI on 7393b60
- **Three systems green:** `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser, lint and layers, licences, security, CodeQL and `CI passed`. This covers both the pull_request run and the author's ci:full dispatch run.
- **The Windows flate-bomb test** passed on both runs. The round 1 failure stays a one-off.
- **A new note.** The dispatch run's Windows job first failed `tests/unit/test_web_jobs.py::test_events_keep_the_stream_alive_and_end_when_the_server_stops`: no keep-alive came within 0.5 s.
  - One re-run passed, and the pull_request run's Windows job passed on the same head.
  - This PR does not touch web.
  - It is reported to the coordinator. If it fails again, it is quarantined with an Issue in the web lane the same day.

## Merge
- **Squash-merged** at 00:59Z (17 Nov), pinned to 7393b60. The new main is **cfeb084**.
- **The merged tree is identical** to the reviewed head's tree, so the three-system run covers the merged code.
- **Closed:** #455 and #460 (its textprep part; the pause and highlight are in #480).
- **Follow-ups:** #480 (app/web), #482 (second-run cut beside a reading) and #483 ("(Sommer 2019)"). All three are open.
- **Main cfeb084 three-system run:** `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)` are green. The flate-bomb test and the web keep-alive test both passed, so no quarantine is needed.
