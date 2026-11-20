# PR #677 review, round 1 (head 1c0bbc2)

Reviewer: layout lane review thread (on the coordinator's request), Opus. 20 Nov 2026. Issue #670.
Critical: **no** (one test file; no golden, contract, product code or CI change).
Verdict: **approve** (0 must-fix, 0 should-fix, 1 note).

## Checked and fine

- **Scope.** One file changed, `tests/unit/test_extraction_pdf_process.py` (+22 −2); `src/sci2audio/extraction/isolate.py` is untouched.
- **No result on the pipe.** Both children (`_exits`: `os._exit(1)`; `_killed`: `SIGKILL` to itself) end before answering, as `os.abort` did.
- **Both death paths.** `isolate.run` maps the exit code with `{MEMORY_EXIT: "memory", TIME_EXIT: "time"}.get(child.exitcode, "ended")` (isolate.py:241). A signal (exit code −9) and a non-zero exit (1) take the same branch, and neither 1 nor −9 is 86 or 87. The PR keeps both cases anyway, so the signal death stays covered. The `SIGKILL` case is skipped only where `signal` has no `SIGKILL` (Windows).
- **`Stopped("ended", "opening")`.** Asserted for both cases, with the same user message as before.
- **No crash report on this Mac.** In a temporary worktree at 1c0bbc2 I ran the whole file (41 passed, 2 skipped) and the two cases alone (both passed). Before and after, `~/Library/Logs/DiagnosticReports` held 45 files, and the newest is from 14:41, before the run.
- **Lint.** ruff check and ruff format clean on the file. The comment above the parametrize says why (PR-05).

## Notes

- **N1.** Since `isolate.run` treats both deaths the same, one case would suffice, as the PR body says. Keeping the second costs about 0.3 s and is accepted.
