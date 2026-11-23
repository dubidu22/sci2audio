# Review PR #761, round 2

- PR: https://github.com/dubidu22/sci2audio/pull/761 (PR B of #723, closes #723)
- Head: `a83995537dd542c5834ccd3211b002e7a045cb5e` (one fix commit on round 1's `492eb06`); base `f1a9c1f`
- Thread: review-b005 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (as round 1).
- **Verdict: approved.** 0 must-fix, 0 should-fix, 0 deferred.

## Verified checks

- Fix commit: `app/audio.py` (+17/−6), `app/playable.py` (+24/−13), `tests/unit/test_app_audio_faults.py` (+27/−3); nothing else changed since round 1.
- Three-system run 45172191271 on a839955: `tests (ubuntu|macos|windows-latest)` and `CI passed` success; `ci:full` removed (labels `risk:high, lane:app, lane:web`).
- Locally: the eight test files of round 1, 220 passed (216 plus the four new cases); ruff check and format clean; lint-imports 3 contracts kept.
- `prs/pr-761.yaml` now has `handback: done`; `ledger_tool.py check` is clean.

## Round 1 finding

- **B1 fixed.** `_vouch` now always adds the new entry to `pending` and leaves any entry of the same name in place (`with_pending` no longer drops it), so `owned` accepts the file on disk whichever version it is. A read-along, M4B or subtitle file is only moved from `pending` to `book` by `_placed`, which runs when the step that wrote it has finished (after the chapter's `add`, and in `complete`). A chapter's files take the newest `pending` entry of each name (`newest_pending`), and `with_chapter` drops all older ones. Reuse still requires the same fingerprint and the recorded size and SHA-256.
- VER-02, checked by this review: the new `test_a_kill_while_the_readalong_file_is_replaced_resumes_cleanly` (SIGKILL before or after the 2nd and 3rd read-along renames, then a resume compared byte for byte with an uninterrupted run) fails twice with round 1's `src` (the two before-rename cases; after the rename the old code's record already matched) and passes on a839955. This review's own round 1 probe (in-process stop at the 2nd and 3rd read-along rename, then resume without overwrite) now passes too.
- Notes N1 to N3 of round 1 stand; no change asked.

## Handoff (THR-07)

- Goal: critical review round 2 of #761.
- Done: fix verified against round 1's reproduction and shown to fail without the fix; three-system run green on a839955.
- Next: the coordinator's go `ledger/gos/pr-761.yaml` for a839955; then `ledger_tool.py gate 761`, rerun `governance pr checks` if still red, squash-merge pinned to a839955, record the merge and main's three-system run.
