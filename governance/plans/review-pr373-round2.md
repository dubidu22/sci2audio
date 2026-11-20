# Review PR #373, round 2 (v1.1 player wins, PR A: #152 speed, #153 position, #190 publisher pages)

Head reviewed: 7a7acb1 (base main 342a8f5, `mergeable_state` clean). Round 1: plans/review-pr373-round1.md. Non-critical, last round.

**Verdict: the review is done and S1 and N1 are fixed, but 7a7acb1 cannot merge. Two new tests fail on Windows (`tests (windows-latest)` is red), so the three-system rule (D-580) blocks the merge. Nothing is merged.**

## Round 1 items

- **S1, fixed.** `player-data` carries the page's stamp. player.js sends `audiobook` with each POST and skips saving without one. `PositionIn.audiobook` must be 16 hex digits, and `save_position` answers 409 `other-audiobook` and writes nothing when the stamp differs from the current read-along file's. The new TestClient test covers both cases: the old stamp gets 409 and no record, and the current stamp gets 204.
- **N1, fixed.** `resume-continue` and `resume-start` are drawn `disabled` and are enabled once their listeners are added.

## Checks on 7a7acb1

- Fast suite (local, Linux): 5589 passed, 1 skipped.
- Browser suite (local, Chromium): 65 passed, 1 skipped (the quarantined #365 test).
- CI with `ci:full`: Linux, macOS, browser, lint and layers, licences, security, CodeQL and ZAP are green. **`tests (windows-latest)` failed** with 2 failed and 5581 passed (run 43737236425, job 132882425139).

## Fix list (Windows only)

**W1. `test_the_stamp_is_the_read_along_files_hash` fails on Windows, and the code it tests is at fault.** `audiobook_stamp` caches the hash under `(st_mtime_ns, st_size)`. On Windows the two writes in the test ("one", then "two") land in the same clock tick and have the same size, so the cache returns the old stamp (`'7692c3ad3540bb80' != '7692c3ad3540bb80'`). In real use this would need a rewrite of the same size within one tick, so the risk is small. Still, the stamp is now the S1 guard, so it must not depend on timestamp resolution.
Fix: drop the `lru_cache` on `_stamp` and hash the file on each call. Only the page draw and the POST (at most every 5 s) call it, and the POST already reads the read-along file. If you keep a cache, also key it on `st_ino` and `st_ctime_ns`. The test stays as it is and must pass on all three systems.

**W2. `test_no_record_and_a_folder_in_its_place_are_ignored` expects the wrong message on Windows.** `os.replace` onto a folder raises `PermissionError: [WinError 5] Access is denied` there, not a message containing "directory". The behaviour is right: the write fails, and the route answers 503. Fix the test only, for example `pytest.raises(OSError)` without `match`, or `match="directory|Access is denied"`.

These need no new review round. The next check is three-system CI (`ci:full` is already on the PR, so the push tests all three) and the fast suite on the fix head.

## Fix head e31eb40 (approved and merged)

- W1 is fixed: the stamp cache key now includes `st_ino`. The audio job replaces the read-along file whole (`write_texts` renames a partial file), so a new audiobook always gets a new file identity. The test now replaces the file with the same time and size. With `st_ino` taken out of the key, it fails on Linux too.
- W2 is fixed: the test accepts `directory|denied`.
- `test_web_position.py`: 36 passed locally. Three-system CI on e31eb40: everything is green, including `tests (windows-latest)` and `tests (macos-latest)`.
- Squash-merged pinned to e31eb40 as **514dc2f**. #152, #153 and #190 are closed. #376 stays open for PR B.
