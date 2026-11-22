# Review PR #739, round 2

Thread review-b004-b (review, Opus 5.5 medium), 22 Nov 2026. Author voices-b-v1.
Head reviewed: 4f675c9849991fd7d4dafe28d0a5ea7f863e7955 (one fix commit on 744cc83). Previous round: `plans/review-pr739-round1.md`.

**Critical: no** (unchanged from round 1; the fix commit touches only `src/sci2audio/voices/espeak.py` and `tests/unit/test_voices_espeak.py`).

**Verdict: approved.** Must-fix 0, should-fix 0. This is the last round for a non-critical PR (REV-01).

## Round 1 findings

- **S1: fixed.** `espeak.py:28` is now `ESPEAK_PATH_LIMIT = 230 - 1 - len("/espeak-ng-data") if sys.platform == "win32" else 159` (214 on Windows), with a why-comment at `:25-27` naming both copies into `path_home` and the difference between POSIX `snprintf` and MSVC `_snprintf`. The module docstring (`:9-13`) and the test docstring (`test_voices_espeak.py:53-59`) now say the read goes undefined from 215 bytes on Windows. The PR body answers the round. POSIX is unchanged at 159, so the limit mutants killed in round 1 still apply.
- **N1: deferred** to #744 ("voices: espeak-ng on Windows with a non-ASCII data folder", open, milestone v1.5, lane:voices, risk:low). Accepted.
- **N2: fixed.** The narrating line "misaki is imported only inside the functions that need it." is removed.

## Verified

- Diff 744cc83..4f675c9 contains only the changes above; the PR's file list is unchanged (lane:voices plus tests).
- CI on 4f675c9: `tests (ubuntu-latest)`, `CI passed`, `governance pr checks`, lint and layers green.
- Local run (macOS): `test_voices_espeak.py` and `test_voices_kokoro.py`, 30 passed.

## Note (no action)

- The changed Windows branch is not run at this head, because non-critical PRs get Linux CI only. The risk is low: 214 is lower than the 229 that passed `tests (windows-latest)` on 744cc83, and at 214 both copies fit inside the buffer. The push to `main` after the merge runs all three systems. The thread that merges checks `tests (windows-latest)` on the merge commit.
