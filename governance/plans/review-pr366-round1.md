# Review PR #366, round 1 (PDF page progress #343, cancel stops the reader #344)

Head reviewed: 766d56a (base main 0af10d0). Plan: plans/issue343-344-pdf-progress-cancel-plan.md (D-623). Non-critical, lane:app.

**Verdict: not approvable yet. One blocker (B1), one should-fix (S1).**

## What I checked

- Change against the plan: it matches in extraction (`on_step`, `cancel`, `Readers.take/give`, `ReadCancelled` not an `ExtractionError`), app, web and cli.
- Fast suite: 5298 passed, 1 skipped, 2 xfailed. CI on 766d56a: Linux tests, browser, lint, licences, security, ZAP and CodeQL are green. No `ci:full` run yet; it belongs to the approving round.
- Commit messages carry no closing keywords.
- Cancel through the API (web) and through `cancel` in the audio job: these become `JobCancelledError`, and `test_web_pdf_progress` checks that no "damaged" text appears. That is right.
- **Per-step deadline:** `test_with_a_cancel_to_watch_a_step_is_stopped_at_its_own_time_limit` pins it from both sides. It must not be shorter than 1.0 s, and it must not be stretched, which fails at 30 s. See S1 for its upper bound.

## Fix list

### Blockers

**B1. Ctrl-C in the CLI during the reader child's start fails the job as an unreadable file.** On a terminal, Ctrl-C sends SIGINT to the whole process group, so the reader child gets it too.

I probed this on Linux with `isolate.run(page_then_hang, …, cancel=event)`, sending `os.kill(child.pid, SIGINT)` at several delays and then setting `cancel`, as `convert` does:
- SIGINT 0 to 0.05 s after the start, with `cancel` set 0 or 0.05 s later, gives `Stopped("ended", "starting")`. The child dies inside the spawn bootstrap, as its KeyboardInterrupt traceback shows. `extract_pdf` turns that into `paper.pdf: cannot be read: sci2audio could not start its PDF reader (it ended while starting)`, an `UnreadableFileError` with the unreadable exit code, not 130 and not "cancelled".
- SIGINT during a page step: the child catches KeyboardInterrupt and sends it back, and the parent raises it in the reading thread. `convert` then exits 130 with "stopped; run the same command again to continue". That is not "damaged", but the PR's own "cancelled while the file was read" path is skipped.

The child's start lasts up to seconds on macOS (D-616), so pressing Ctrl-C right after `convert paper.pdf` hits this window.

The existing test `test_ctrl_c_while_the_pdf_is_read_stops_the_reader_at_once` uses `_thread.interrupt_main()`, which reaches only the parent, so it cannot see this.

Fix: a SIGINT to the child must never become a damaged or unreadable file. Two ways, both suggested:
- (a) Keep SIGINT away from the child. On POSIX, block SIGINT in the starting thread around `child.start()` (`signal.pthread_sigmask`, which is inherited across spawn's exec), then set `SIG_IGN` first thing in `_child`.
- (b) In `_wait`, treat a child that ended by SIGINT, or that sent KeyboardInterrupt back, as `Stopped("cancelled", step)`. Then `extract_pdf` raises `ReadCancelled`, even when the parent's own `cancel` is set a moment later.

Test: send a real `os.kill(child.pid, signal.SIGINT)` once during the start and once during a page step (POSIX; skip on Windows, or use `CTRL_C_EVENT` if you can make it reliable). Assert the read ends as `ReadCancelled` or `KeyboardInterrupt`, and never as `ExtractionError`. Then add a CLI-level check that `convert` exits 130 with the cancelled message.

### Should-fix

**S1. The deadline test's upper bound includes the child's kill and join.** `took` is measured after `isolate.run` returns, so `took < 1.5` also counts killing, joining and closing the child. On slow macOS or Windows runners that can eat the 0.5 s of slack: the #345 timing test failed there for a similar cause (D-616). Either measure until `_wait` decides, by recording the time in `on_step`/`Stopped` or patching `child.kill`, or raise the bound to `< 2.0`. The 2.0 bound still fails a stretched deadline, which runs 30 s, and a slice-reset one.

### Nits, deferred

None.

## Next

Round 2 is the approving round: the B1 test must fail on 766d56a, then the fast suite, the browser suite and `ci:full` on all three systems.
