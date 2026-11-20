# Review PR #366, round 2 (PDF page progress #343, cancel stops the reader #344)

Head reviewed: 4108d81. Answer: plans/answer-pr366-round1.md (D-628).

**Verdict: approvable at 4108d81.** The residual is filed as #367 (v1.2).

- **B1, fixed on POSIX.** SIGINT is held back in the starting thread around `child.start()`, and the child sets `SIG_IGN` and then unblocks it. I re-ran my round-1 probe with a real SIGINT to the child at 0, 0.05, 0.2 and 1.5 s, with `cancel` set 0 or 0.05 s after. Every page-step case now gives `Stopped("cancelled", …)`; before, they gave KeyboardInterrupt or "ended". At the most adversarial timing, a SIGINT within about 1 ms of the child's creation with `cancel` set at once, 1 of 20 tries still gave `Stopped("ended", "starting")`, with no KeyboardInterrupt traceback, so the cause is unknown. Together with the Windows gap (no signal mask, so the child ignores Ctrl-C only from `_child`'s first line), this is filed as **#367**: "Ctrl-C in the reader child's first moments can still read as an unreadable file". The suggested fix is to map a child that ends while `cancel` is set, or is set within a short grace period, to "cancelled". I accept both gaps for this PR. The worst case is an unreadable-file message on a read the user cancelled. Nothing is lost, and a rerun works.
- **S1, fixed.** The timing is taken when `_wait` returns, which is the decision point, so the 1.0–1.5 s bound no longer includes the join.
- **Checks:**
  - Fast suite: 5301 passed, 1 skipped, 2 xfailed.
  - The SIGINT, Ctrl-C, time-limit and cancel tests ran 3 times in a row: 14 passed each time.
  - ruff, format and lint-imports are clean.
  - Commit 4108d81 carries no closing keywords.
  - `ci:full` was added. On 4108d81, tests (ubuntu-latest), (macos-latest) and (windows-latest) and the browser tests are green.

Fix list: none. Deferred: #367.
