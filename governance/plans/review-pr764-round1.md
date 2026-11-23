# Review PR #764, round 1

- PR: https://github.com/dubidu22/sci2audio/pull/764 (#724, LW-02, lane:web + lane:app; plan `plans/impl-724-plan.md`, approved as D-902)
- Head: `9d38cece0abf8689732cfc78c8fc0fdd5435eb2e`, base `9f622af` (= main)
- Thread: review-b005 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (CRIT-03, D-902 ruling 2): `app/audio.py` now writes `document.json` into the job folder before the first chapter, under the D-895 rule; risk:high.
- **Verdict: approved.** 0 must-fix, 0 should-fix, 0 deferred, 3 notes.

## Verified checks

- Run 45184320620 on 9d38cec: `tests (ubuntu|macos|windows-latest)`, both Chromium shards, `lint and layers`, `licences`, `security`, `web paths`, `CI passed` success; ZAP baseline scan and CodeQL success. `ci:full` removed.
- Locally: `test_web_listen_growing.py`, `test_web_audio.py`, `test_app_audio_chapters.py`, `test_app_audio_faults.py`, `test_web_player.py`, `test_web_library.py`: 250 passed, 1 skipped. Chromium browser tests `test_listen_growing.py`, `test_joined.py` and `test_flow.py::test_the_removal_button_waits_for_the_script`: 12 passed. ruff check and format clean; lint-imports 3 contracts kept.
- All 27 node IDs of the plan's test list exist. The one rename (`..._is_spoken` to `..._is_playable`) is covered by D-904.

### D-902 kill fault test

`test_a_kill_after_the_document_is_written_resumes_without_overwrite`: a subprocess job is SIGKILLed right after `_write_document` (wrapped in `STOPPED_JOB`, hang then kill). It asserts `document.json` is there, `audio.json` is not, and the output folder is empty; then `resumed_like_an_uninterrupted_run` resumes without `overwrite` and checks no partial, every file byte-equal to an uninterrupted run, a complete record with nothing pending, and only the 6 chunks not yet spoken are spoken. Order in `_Chapters._writer`: `_remove_old_records`, then `_write_document`, then the record, then the first file, so an old `audio.json` never sits beside the new document (pinned by `test_audio_json_is_still_written_only_at_the_end`). The one changed existing assertion (`test_a_rerun_that_fails_while_encoding_leaves_no_old_record`: `document.json` is no longer absent after the failed rerun) now plants an old document and asserts it is replaced by this rerun's, so it checks more, not less.

### WebKit (reported only)

Attempt 1 of `browser (Linux, webkit, 2/2, reported only)` failed `test_flow.py::test_the_removal_button_waits_for_the_script[webkit-library]` (locator not visible) and `test_joined.py::test_the_mark_and_the_bar_stay_on_the_sentence_through_its_pieces[webkit]` (no highlight at piece 2). The rerun (attempt 2, job 137779261646) on the same head passed all 102. The last nightly on main (45160266582, 8965914) passed. The author's "neither touches the new code" holds for the removal button; `test_joined` runs on the Listen page, whose `player.js` this PR changes, but it passes on Chromium locally and in CI and on WebKit in the rerun. One failure each, so D-374's "twice" is not met; see N1.

## Findings

- **N1** (note). If either WebKit test fails again, on this PR's branch or on main, D-374 applies the same day (the coordinator's note): quarantine with an Issue, then the 40-run check. `test_joined` is the one to watch, since this PR changes the script it exercises.
- **N2** (note, for #726 PR 4). `book_key` hashes the settings key and `planned`; impl-725's plan 2.4 drops `planned` from it so a kept position survives added chapters.
- **N3** (note, ledger). `prs/pr-764.yaml` names `fixes_kinds: zap-walk`, a kind no round recorded, so `ledger_tool.py check` flags it. The entry's writer should clear it or name a recorded kind.

## Handoff (THR-07)

- Goal: critical review round 1 of #764 at 9d38cec.
- Done: kill test and the record order verified; tests green locally (unit and Chromium) and in CI on three systems; WebKit failures did not repeat.
- Next: the coordinator's go `ledger/gos/pr-764.yaml` for 9d38cec; then `ledger_tool.py gate 764`, rerun `governance pr checks` if still red, squash-merge pinned to 9d38cec, record the merge and main's three-system run.
