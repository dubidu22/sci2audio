# Review PR #486, round 1 (quarantine of the Windows flate-bomb test, D-725)

Head reviewed: de2f777, one commit on main cfeb084. The PR is non-critical (lane:extraction) and its Linux CI is green. One pinned round, per the coordinator's D-725 ruling.

**Verdict: approvable, and merged.** Squash-merged and pinned to de2f777. The new main is **6525212**.

## What I checked
- **The diff.** It is one `@pytest.mark.quarantined(issue=485, reason=…, platform="win32")` marker on `test_a_flate_bomb_is_stopped_at_the_memory_limit_and_this_process_stays_small`, and nothing else.
- **The marker.** `tests/conftest.py` accepts `platform=`, and it skips the test only when `sys.platform == "win32"`.
- **Locally on Linux:**
  - the test still runs and passes (`-k flate_bomb`: 1 passed);
  - `-m quarantined --collect-only` lists it as "#485 … (on win32)".
- **#485** is open, lane:extraction, milestone v1.2.x, and holds the 0-of-40 isolation result (run 44006516928, `plans/flate-bomb-isolation-d725.md`). The PR body says "Refs #485" without a closing keyword, so the issue stays open until the test is fixed.
- **CI on de2f777:** `CI passed`, `tests (ubuntu-latest)`, browser, lint and layers, licences, security and CodeQL are all green. It is a non-critical PR, so Linux CI is the merge gate.

## Next
The #484 author merges main 6525212 into #484. That three-system run is the base move that counts as #484's round 3 run (D-725).
