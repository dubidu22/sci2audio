## Review of PR #85, round 2 (fixes in 452c158)

**Verdict: passes.** All eight items are answered: seven fixed, one deferred to #89 (open, `risk:high`, `lane:core`). That deferral is right, since core is its own lane.

Checked on 452c158 merged locally with current main (df76ad6):
- ruff, format, lint-imports, deptry: clean.
- Fast suite with the ci profile: 621 passed, 18 snapshots.
- Nightly profile on `test_output_parts.py` and `test_output_faults.py`: 67 passed.
- slow and benchmark: 2 passed.

Each fix, checked:
1. **Byte cap on names.** `names.cut` caps names at 120 characters and 200 bytes, so the longest partial name is 224 bytes. My round 1 reproductions (130 × "Ü", 60 × "量子") now write. The property test checks UTF-8 bytes and UTF-16 units of every derived name.
2. **ffmpeg on an interrupted wait.** `process.wait()` now sits inside the kill path, and there is a test for it.
3. **Order of the ffmpeg check.** `find_ffmpeg()` runs before mkdir and before any delete. A test confirms the folder is unchanged when ffmpeg is missing.
4. **Read-along property test.** A Hypothesis round trip over generated timelines and spans, with `None` names.
5. **No-overwrite race.** `_commit` uses link-then-unlink on POSIX and `os.rename` on Windows, with a recheck where hard links aren't available. Mutation check: putting back `os.replace` makes `test_a_file_appearing_during_the_run_is_not_replaced` fail.
6. **AI label.** It now carries `__version__`. lint-imports still passes, and the root package imports nothing.
7. **Core docstring.** Deferred to #89.
8. **Key order.** Pinned on the raw text.

The `%` checks from round 1 still pass on the new head. Next: update the branch from main, wait for CI, then merge pinned to the head.
