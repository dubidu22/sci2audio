# Review PR #439, round 1 (#438: file_id racy-file guard on main)

Head reviewed: bd1ca5e, on main f063454. Non-critical (app code and one unit test). Decision: D-700.

**Verdict: not approvable yet. There is one should-fix item (S1) and nothing else.** The fix is right, but it repeats on main a fix that release/1.1 already has, in a different form. Merged as it is, the R3 forward merge of release/1.1 into main would conflict in two files. Taking the release fix word for word removes the conflict.

## What I checked

- **The guard matches the #403/#407 pattern.** `file_id` hashes the file directly when `time.time_ns() - stat.st_mtime_ns < RACY_NS` (2 s) and keeps the `(st_ino, st_mtime_ns, st_size)` cache for older files. That is the same rule as `audiobook_bounds` in `web/player.py`. A fresh file is never put in the cache, so a file that is first hashed while fresh and rewritten in the same tick cannot get an old hash back later.
- **The test fails without the fix.** On main f063454, `test_a_file_rewritten_in_place_within_one_tick_gets_a_new_id` fails at line 197 (the new hash); on bd1ca5e all 13 tests pass. The test does not depend on how long it runs: the first call is never cached, so the check holds even on a slow runner.
- **Mutants**, on `tests/unit/test_cli_listen.py`, all killed: guard off, `RACY_NS = 0`, guard always on (the read-once check fails), and the age with its sign flipped.
- **Windows (#373 lesson).** The key keeps `st_ino`. Where Windows gives no useful `st_ino` or the 16 ms tick keeps the time, the guard covers the rewrite anyway, because the age test does not use the key. `time_ns()` and `st_mtime_ns` use the same epoch on all three systems. CI on bd1ca5e: `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)`, the browser run, lint and layers, licences, security, CodeQL and the ZAP scan are all green. `mergeable_state` is clean.
- **Other caches in the app with the same gap.**
  - `web/player.py` `load_readalong` keys on `(st_mtime_ns, st_size)` only. That is #407, already filed (v1.2).
  - `web/player.py` `audiobook_stamp` keys on `(st_ino, st_mtime_ns, st_size)` without the guard. The audio job writes the read-along file only through a whole-file replace (`write_texts`), which gives it a new identity. A stale stamp would need two audio jobs that end within one clock tick and also reuse the inode. Accepted as is, and the docstring says why.
  - `#430` already pins the bounds cache key.
  - The other `lru_cache` and `cache` uses (`web/i18n.py`, `textprep/abbreviations.py`) cache fixed data, not files.
- **The release branch.** release/1.1 (e9d08ef) already has this guard: #403 B1, in 08d5965, with `_hash` and two tests (`test_a_file_rewritten_in_place_within_its_clock_tick_gets_a_new_id` and `test_a_file_older_than_two_seconds_is_read_once`). Main never got it, because R3 (the forward merge) waits for the v1.1 tag. That is why #436 failed on Windows.
  - `git merge-tree origin/main origin/release/1.1` is clean today.
  - `git merge-tree bd1ca5e origin/release/1.1` conflicts in `src/sci2audio/app/config.py` and `tests/unit/test_cli_listen.py`.
  - I tried porting the release fix word for word onto main f063454. The result passes 14 tests, both ported tests fail on main, and it merges with release/1.1 to the same tree as main does today (c09596e). So R3 stays clean.

## Fix list

### Should-fix

**S1. Port the release/1.1 fix word for word, so the R3 forward merge stays clean.** Starting again from main f063454:

1. `git checkout origin/release/1.1 -- src/sci2audio/app/config.py`. On main the file differs from release/1.1 only by this guard, which I checked.
2. In `tests/unit/test_cli_listen.py`:
   - Remove this PR's `test_a_file_rewritten_in_place_within_one_tick_gets_a_new_id`.
   - Add release/1.1's two tests, `test_a_file_rewritten_in_place_within_its_clock_tick_gets_a_new_id` and `test_a_file_older_than_two_seconds_is_read_once`, word for word at the end of the file. Add `import time` after `import os`.
   - Keep main's `test_a_broken_record_is_refused` as it is on main, with the deep-nesting row from #420.
   - The two release tests kill the same four mutants.
3. Check that `git merge-tree --write-tree <new head> origin/release/1.1` gives the same tree as `git merge-tree --write-tree origin/main origin/release/1.1`.
4. Change the PR body to say that the PR carries #403 B1 from release/1.1 onto main and closes #438. As before, the commit messages must have no closing keywords.

Round 2 checks only S1 and CI on Linux, macOS and Windows at the new head.

## Leftovers

None new. #407 and #430 already cover the read-along caches. #440 (the SIGINT child flake) is not part of this PR.
