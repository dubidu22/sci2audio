# Review PR #556 round 1 (#485, critical: extraction/isolate.py)

Head reviewed: 6ca1f027e0a9ea01e85381b676170b6035d49112 (merged with main f919d81 locally: clean, main changed no extraction file since base 1797ceb).
Reviewer: B1 review thread (Opus high), 18 Nov 2026.

## Verdict: APPROVED (final round)

Merge condition: Windows full fast-suite runs 2 and 3 (44396331896, 44396344573) green on 6ca1f02 (AC-485.2, TST-08). Run 1 is ci:full 44393345271: tests on ubuntu, macos, windows all success.

## Verified

- Cause: `PipeConnection._poll` calls `PeekNamedPipe` (CPython 3.12 connection.py:344), which raises `BrokenPipeError` (WinError 109) on an empty pipe whose writer is gone; main polled outside the `try`. Proven on Windows: scratch run 44393255371 (main's isolate.py swapped in) fails all 4 new tests, the real-pipe test with exactly `[WinError 109]` at connection.py:344.
- Fix: poll inside the same `try` as recv; the exit code still names the reason. Data written before the child ends stays readable (PeekNamedPipe reports bytes while any remain), so a "done" sent just before exit is not lost.
- AC-485.1: flate-bomb test drops `check=True`, asserts returncode 0 with exit status, stdout and stderr in the message.
- AC-485.2: quarantine marker removed (no other reference to #485 in the repo). 40 isolated Windows runs each for the flate-bomb test and the busy-parent test: 40/40 and 40/40; the loop counts every iteration and the step fails on any failed iteration (`! grep " [1-9][0-9]* failed"`), so the 18 Nov repeat-run lesson holds. Full-suite Windows run 1 green; runs 2, 3 pending (merge condition).
- Safety mechanism has a test failing without it (REV-07), Linux locally, branch + main merged, `test_extraction_pdf_process.py` 35 passed:
  - mutant `except EOFError` only: 3 of 3 stand-in cases fail.
  - mutant reason map without TIME_EXIT: `[87-time]` fails.
  - main's poll outside the try: the 4 new tests fail on Windows (run above); the stand-in tests fail on every system.
- Corpus/goldens: no output path touched (isolate only changes which errors mean "ended").
- Commit message: no closing keyword.

## Findings

None to fix.

- N1 `child.join()` after an OSError has no timeout. If an OSError ever came while the child was alive, the parent would wait without its time limit. Not reachable today: only the child holds the write end (the parent closes `send` after start), so the pipe breaks only when the child has ended. Same as the existing recv path; no change asked.
- N2 TST-08 says no scratch branches for isolation. The 40-run proof used scratch branch `ci/isolate-485` because it also had to run main's isolate.py against the new tests, which isolate.yml cannot do. Accepted for this proof; the branch goes on Colin's delete list.
