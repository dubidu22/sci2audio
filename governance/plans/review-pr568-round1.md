# Review PR #568 round 1 (#485 reopened, critical: extraction/isolate.py, D-766)

Head reviewed: 5c05c14 (on main 56d937f). ci:full run 44402440923 green on ubuntu, macOS, Windows; on Windows the new job-limit test ran and passed (not skipped).
Reviewer: B1 review thread (Opus high), 18 Nov 2026.

## Verdict: APPROVED in code; merge waits for the AC-485.2 proof below

## Verified

- Cause matches the failing log (run 44399793442, job 135139368488): the child raised `OSError: [WinError -536870904] Windows Error 0xe0000008`, sent it as "raised", and isolate.py re-raised it in the parent. 0xE0000008 is PartitionAlloc's out-of-memory exception code. ctypes turns the SEH exception into an OSError whose `winerror` is the signed value.
- Fix: in `_child`, an exception that `_out_of_memory` matches ends the child with MEMORY_EXIT, the same as MemoryError. The match is exactly the OSError whose `winerror` equals 0xE0000008 - 2^32. Other OSErrors and errnos are still raised as themselves (5 unit cases).
- Hand mutants, run on Linux on 5c05c14 (`test_extraction_pdf_process.py`, clean run 41 passed, 1 skipped):
  - With the check removed (`if False:`), the stand-in test fails.
  - With `_out_of_memory` matching any `winerror`, the table test fails.
- `read_unwatched` parks the watch by raising `_WATCH_SECONDS` after its last look. Only the job object can then stop PDFium, so a pass on Windows exercises the real path.
- The commit message has no closing keyword; the PR body says Closes #485.

## Merge condition (AC-485.2, since #485 is reopened)

1. 40 isolated Windows runs, each run alone, of `test_the_job_limit_stopping_pdfium_is_the_memory_limit` and of `test_a_flate_bomb_is_stopped_at_the_memory_limit_and_this_process_stays_small`, with the fix. The loop must fail on any failed iteration (as in ci/isolate-485). isolate.yml runs browser tests only, so a scratch workflow branch is needed again (N1). The counts go into #485.
   Reason: after PDFium's allocator raises, ctypes unwinds through PDFium's frames. The `finally` blocks in `_pages` (`textpage.close()`, `page.close()`) then call PDFium again before the child exits. If that ever crashes, the child ends as "ended", not "memory", and the size message is lost again. One green run does not show this; 40 do.
2. Three full fast-suite Windows runs: ci:full 44402440923 (green), plus two dispatches I started, 44404125316 and 44404138127.

## Notes (no change asked)

- N1 isolate.yml covers only browser tests on Linux and WebKit on macOS. A unit test on Windows needs a scratch workflow, which TST-08 forbids. Filing an issue to let isolate.yml run unit tests on Windows (lane:infra) would close that gap.

## Merge (18 Nov 22:20Z)

Proof met: scratch run 44404389214 reproduces OSError 0xe0000008 on Windows with main's isolate.py (no load); with the fix the flate-bomb test passed 40/40 and the job-limit test 40/40, in a loop that fails on any failed iteration. Full Windows runs 44402440923, 44404125316, 44404138127 green. Main since 56d937f touched neither file of this PR, so the branch was not updated (MRG-03). Merged d44cf5d (squash, pinned 5c05c14); #485 closed.
