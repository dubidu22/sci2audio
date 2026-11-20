# Review of PR #345, round 1: read PDFs in a separate process (#185, #28, D-581)

Review thread "Review PDF subprocess PR 345", 15 Nov 2026. Reviewed head **8611d18** (on main 99b8166). Plan: `plans/pdf-subprocess-plan.md` (D-581, Q1 to Q9 plus three required additions).

**Verdict: changes needed.** The design matches the plan and works: every hostile file I tried is stopped or refused, the parent stays small, all 8 corpus papers read identically in the child and in-process, and CI is green on all three systems. One blocker: the two memory tests do not tell the watch and the hard limit apart, so nothing proves the Windows job object (or Linux `RLIMIT_AS`) works. Five should-fix items, two nits, three deferred issues.

## What I ran

| Check | Result |
|---|---|
| CI with `ci:full` on 8611d18 (run 43692046806) | all green: tests (ubuntu-latest) 5196 passed; **tests (windows-latest) 5194 passed, 3 unrelated skips, all 18 process tests ran**; tests (macos-latest) 5195 passed, only the hard-limit test skipped (as designed); browser, lint and layers, licences, security green |
| Fast suite locally, `-n auto`, 4 cores | branch 5196 passed, 1 skipped, 6 xfailed in 146.8 s; main 99b8166 5177 passed in 138.0 s: **+8.8 s**, under the 15 s rule |
| Fast suite on CI, branch vs main 99b8166 | Linux 206 vs 191 s (+15), Windows 311 vs 295 s (+16), macOS 223 vs 236 s (−13). Borderline but acceptable; the conftest read cache stands (see notes) |
| Slow + benchmark (`-m "slow or benchmark"`) | 6 passed, 24 skipped (voice models not downloaded; none read PDFs) |
| Browser (`-m browser`, Chromium) | 54 passed |
| Corpus: `extract_pdf(p) == read_pdf(bytes)` | **equal for all 8 papers**; child costs 0.04 to 0.35 s more per paper; all 8 covers render |

### Hostile files (`extract_pdf`, then `extract_pdf_cover`)

| File | Size | Result | Time | Cover |
|---|---|---|---|---|
| Flate bomb, 3 GB of spaces | 3.2 MB | memory message (1 GB) | 1.0 s | None |
| Flate bomb, 8 GB of spaces | 8.5 MB | memory message | 0.8 s | None |
| 1,000,000 filled rectangles on one page | 2.4 MB | "page 1 holds more than 100,000 drawings and pictures" | 4.1 s | rendered, 1.6 s |
| 5,000,000 unpainted paths (`re n`) | 12.1 MB | reads (not counted, nothing kept) | 2.9 s | rendered |
| forms nested 8 deep (10⁸ rectangles) | 4 KB | memory message | 2.1 s | None |
| a form that draws itself (cycle) | 1 KB | reads, 8 drawings (walk depth cap holds) | 0.1 s | rendered |
| one 40,000 × 40,000 px image (1.6 GB decoded) | 1.6 MB | reads | 0.2 s | rendered, 1.3 s, under the limit |
| page tree whose Kids contain itself | 1 KB | "page 2 cannot be read" | 0.2 s | rendered |
| 10,000 pages (at `MAX_PAGES`) | 1.6 MB | reads | 2.7 s | rendered |
| 5 pages × 100,000 rectangles (the most the limits allow) | 0.2 MB | reads, 500,000 drawings | 11.5 s | rendered; **parent grows by 497 MB; layout then takes 198 s** (D1, D2) |

Parent peak growth stayed at 0 MB for every refused or stopped file.

### Hand mutants (13, run against the process, broken-file, CLI and web-refusal tests)

Killed (8): no watch thread (by the Flate-bomb tests, *not* by the watch test), no `__main__` swap, no reader cap, no page report, page-graphics off by one, file count ignoring earlier pages, limits not passed to the read child (by `test_web_refused_pdfs`), every end reported as memory.

Survived (5):
1. **No hard limit** (`_hard_limit` call removed): every test passes on Linux; the watch catches the "hard limit" test → B1.
2. **No watch thread**: `test_the_watch_stops_a_child_that_grows_past_the_limit` still passes on Linux, because `RLIMIT_AS` at 200 MB stops the 300 MB allocation → B1.
3. **`report("outline")` removed** → S3.
4. **`_READERS = isolate.Readers(3)`** (the production cap) → S4.
5. **`freeze_support()` removed** from `cli.main` → N2.
(Limits not passed to the cover child survives too, but no test patches `COVER_SIZE`; no action.)

### Other probes

- An exception raised in the child that pickles but does not unpickle (`__init__(self, a, b)` calling `super().__init__(f"{a}/{b}")`) reaches the caller as `TypeError: __init__() missing 1 required positional argument` → S1. `PdfiumError` itself round-trips (checked), so this is robustness, not a live bug.
- Parent killed with SIGKILL while the child is in a step: the child kept running until its own work ended (checked with a 40 s step; it was still alive 20 s after the parent died). Q9 of the plan says the child ends "at its step limit", but the step limit lives only in the parent → S2.

## Fix list

### Blocker

**B1. Make the two memory tests prove each mechanism on its own.** Today either mechanism satisfies both tests on Linux and Windows (mutants 1 and 2), and `_windows_job` returns silently when any of its three calls fails, so a broken job object would go unnoticed.
- Hard-limit test: the target parks the watch first, then allocates in one go, e.g. `isolate._WATCH_SECONDS = 3600; time.sleep(0.1); data = b"x" * (300 * MB)` at `memory=100 MB`. Stopped with "memory" only if the system's limit refused the allocation.
- Watch test: grow in steps to 1.5 × the limit, below the 2 × hard limit even with the child's own ~113 MB of address space, e.g. sixty 10 MB chunks held 0.3 s at `memory=400 MB`.
- I prototyped both (scratch module, not in the repo): as is, both stop with "memory"; without `_hard_limit` the first returns 314572800; without the watch the second returns 60. Each test must fail under its own mutant on Linux, and the Windows CI job must run both (only the hard-limit one is skipped on macOS).

### Should fix

**S1. An exception from the child that cannot be unpickled.** In `_child`, check `pickle.loads(pickle.dumps(error))` before sending and fall back to `RuntimeError(f"{type(error).__name__}: {error}")` when it fails (the fallback already exists for pickling failures). Test with a two-argument exception class defined at module level in the test file.

**S2. The child ends on its own when the parent is gone.** Plan Q9 promises the child ends at its step limit, but only the parent enforces it. Let the watch thread also end the child (its own exit code, e.g. `TIME_EXIT`) when no step has been reported for twice `step_seconds`; pass `step_seconds` to `_child`. Test: a target that sleeps past twice a 0.5 s step in a child whose parent is killed (a fresh interpreter, as in the Flate-bomb test), and the child's pid is gone within a few seconds.

**S3. The outline step and the "opening" and "outline" time messages are untested.** Add (a) a test that `read_pdf` reports `page 1`, `page 2`, `outline` in that order (monkeypatch `isolate._report` with a list in-process), which kills mutant 3, and (b) message tests for `_stopped(..., Stopped("time", "opening"))` → "opening it took more than 60 seconds" and `"outline"` → "reading its outline took more than 60 seconds".

**S4. The production reader cap is untested.** `test_a_third_read_waits_for_a_free_reader_and_is_read` swaps in its own `Readers(2)`. Add `assert pdf._READERS.limit == pdf.MAX_PDF_READERS` to `test_the_limits_are_the_decided_ones` (kills mutant 4).

**S5. "Could not start its PDF reader" only for a failed start.** `_isolated` turns every `OSError` into that message, including one the child raised and `_wait` re-raised. Convert only failures of `child.start()` (for example, `run` raises its own small error from the start block, which `_isolated` catches), and close both pipe ends when the start fails (today they leak). Test: monkeypatch the spawn context's `Process.start` to raise `OSError` → the message; a child that raises `PermissionError` → that error, not the start message.

### Nits

**N1.** `isolate.Readers.__enter__` returns `None`; fine, but the docstring of `run` could say the slot wait has no limit and is not counted in the step time (a third read waits for one of the two to finish).

**N2.** Pin `freeze_support` with a one-line test that `cli.main([])` calls `multiprocessing.freeze_support` (monkeypatched), so mutant 5 dies; it matters only for the v1.3 frozen builds, where nothing else would catch it.

### Deferred (GitHub issues on milestone v1.2)

**D1. layout: `order.figures` grows faster than linearly with drawings on a page** (lane:layout). One page: 5,000 drawings 0.18 s, 20,000 1.1 s, 50,000 5.6 s; the file of 5 pages × 100,000 that the new limits allow (0.2 MB) takes 198 s of layout in the parent, with no limit. cProfile at 20,000: 1.15 s of 2.1 s is `layout/order.py:44 figures` itself.

**D2. extraction: parent memory at `MAX_GRAPHICS`** (lane:extraction). 500,000 drawings come back as +497 MB in the parent (the plan estimated at most 430 MB); with two readers that is about 1 GB in the parent. Options: a lower `MAX_GRAPHICS` (corpus maximum 1,863 per paper), or a compact encoding of drawings across the pipe. Decide with D1.

**D3. docs: macOS and Windows rows in `docs/baseline.md` and the macOS `RLIMIT_AS` check** (lane:extraction). Plan Q4 and Q9 promised them from the PR's CI runners; the PR has the Linux row only. CI proves the code paths run on both systems, so this need not hold the merge; a `slow` measuring test would give the numbers from the nightly's three-system job.

## Notes (no action)

- Plan addition 3 asked for a once-per-module fixture if the suite grew by more than 15 s. The PR uses an autouse per-worker read cache in `tests/conftest.py` instead, backed by its count of 547 children per run, mostly from app, web and CLI tests where a per-module fixture would not help. Errors and stops are never cached, and the reader's own tests (`every_pdf_read`) and benchmarks always start a child. I accept the deviation.
- Swapping `sys.modules["__main__"]` is process-wide while other threads run. It is held under `_MAIN` only for `child.start()`, which writes the preparation data synchronously on all three systems. Accepted.
- The time message reads "reading page N took more than 60 seconds" where the plan wrote "page N took more than 60 seconds to read"; the PR body states the wording. Accepted.
- Squash-merge check for later: the branch's commit messages hold no "fixes/closes #N" besides the intended `Closes #185` and `Closes #28` in the PR body.
