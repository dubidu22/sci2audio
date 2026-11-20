# Review PR #630, round 1 (final): #525 keep-alive test, quarantine lifted

Reviewer: installers release review thread (Opus high), 19 Nov 2026. Reviewed head 699af2c, base b6355cc (= main, green on three systems).

Verdict: **approved, merged in round 1.** Findings: none.

## Checked

1. **Race removed, not a wait widened.** Old test: a 0.5 s Timer set `stopping` before the stream was read; if opening the stream took longer, the generator saw `stopping` right after the snapshot and returned (only the snapshot seen). New test sets `stopping` only after reading the first keep-alive line, so the order is causal. The 30 s timer and the 100-line cap only bound a broken stream. Local run: 0.25 s on Linux; Windows log 1.1 s per run, so the 30 s bound is never what passes it.
   Reproduced the race: `await asyncio.sleep(1.0)` at the top of `job_events.stream()` (simulated load) turns main's test red (keep-alive missing) and leaves #630's test green (1.25 s).
2. **No false failure from the 100-line cap.** Starlette 1.10 TestClient streams through a memory object stream of size 0, so the server is at most one chunk ahead of the reader; it cannot queue keep-alives ahead of the stop.
3. **Hand mutants in `web/api.py` (clean baseline green first, test run alone, `-p no:randomly`):** stop ignored → red (100-line cap); `end` sent on stop → red (`'end' not in`); no keep-alive → red (keep-alive missing after the 30 s bound); 1 s slow stream start → green (intended). 3/3 killed. Baseline 20/20 green.
4. **Quarantine gone:** marker removed; `pytest -m quarantined --collect-only -q` collects none on the head. #525 linked by `Closes #525`.
5. **Repeat evidence on the head:** run 44477978745 on `ci/isolate-525-fix` (b47f390); `git diff 699af2c b47f390` touches `.github/workflows/ci.yml` only, so the test file is the PR head's. Log: the test alone 40/40 passed; whole fast suite `-n auto` 4/4 runs with 7879 passed and the same 6 failures, all `test_ci_workflows.py` reading the replaced ci.yml (expected on the scratch branch); the keep-alive test is in no FAILED line. The job is red because of those 6, which is the honest outcome (lesson 18 Nov: a repeat job must fail on any failed iteration).
6. **Three-system CI on 699af2c:** tests ubuntu/macos/windows success, CI passed success, browser shards, lint, licences, security, CodeQL success.
7. Commit message has no closing keyword besides the PR body's `Closes #525`.

Nightly seeds: not applicable (no Hypothesis test touched).
