# Review PR #753, round 1

- PR: https://github.com/dubidu22/sci2audio/pull/753 (closes #744, lane:voices, risk:low; plan `plans/impl-744-plan.md`)
- Head: `dae7c19d6ce48457f37ffa562af3bc2eb63a5e47`, base `0994f97`. Main is now at `f1a9c1f` (#751, #754); neither touches `src/sci2audio/voices/` or `tests/unit/test_voices_espeak.py`.
- Thread: review-b005 (Opus 5.5 high), 2026-11-23
- **Critical: no** (CRIT-03): `voices/espeak.py` and its unit test only; no layer contract (the voice plugin interface is unchanged), no core dataclass, no golden file, no `.github/**`, `pyproject.toml` or dependency. The check extends #739's guard, which was also judged non-critical.
- **Verdict: approved.** 0 must-fix, 0 should-fix, 2 notes.

## Verified checks

- Three-system run 45144703459 on dae7c19: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, `CI passed` success; `ci:full` removed (labels now `lane:voices, risk:low`).
- Windows job log (job 137590991426): 8882 passed, 24 skipped; none of the skips is in `test_voices_espeak.py`, so the characterisation test and the three new unit tests ran on Windows.
- Locally (Linux, Python 3.12): `tests/unit/test_voices_espeak.py` 9 passed; ruff check and format clean.
- Acceptance criteria of #744: (1) characterisation test on a copy of the wheel's data under `Jürgen/data`, running `SPEAK`: present; (2) `check_espeak_data` raises `ModelLoadError` naming the folder and #744, with unit tests for refuse and pass: present; (3) not applicable (Windows exits); (4) POSIX: `windows_ansi_encoding()` is `None` off Windows, so nothing new is checked there; the #739 length tests are unchanged and green; no network.
- Code: `locale.getencoding()` is the right call, since it ignores Python's UTF-8 mode and returns the locale code page the CRT uses for narrow paths. The test `test_a_non_ascii_data_folder_is_refused_under_an_ansi_code_page` would fail without the new check (it was green on main only as "no error", which it now refutes). PR-05: the two new comments say why.

## Findings

- **N1** (note, the author's caveat). The Windows runner's code page is not logged. It does not weaken the check: the characterisation test branches on the same predicate as `check_espeak_data` (`windows_ansi_encoding()` not `None` and not UTF-8), so a green Windows run shows that espeak-ng behaves as the check predicts on that runner, whichever code page it has. What stays unproven is only which branch ran; GitHub's `windows-latest` image is en-US with ANSI code page 1252, so the exit branch is the expected one. When #744 is closed, its closing note should say the exit was observed on `windows-latest` (cp1252 assumed, not logged).
- **N2** (note, for the coordinator, product scope). Users whose Windows profile name holds a non-ASCII character (common in German) and who install into their profile now get a clear error instead of a crash, but still cannot use Kokoro until they move the install. A later Issue could pass espeak-ng the folder's 8.3 short name (`GetShortPathNameW`, ASCII where 8.3 names are enabled) or copy the data to an ASCII folder. Not part of #744; no Issue opened from this round, since it is a roadmap choice.

## Handoff (THR-07)

- Goal: review round 1 of #753.
- Done: diff, tests, acceptance criteria and the three-system run checked at dae7c19; approved.
- Next: the merge go (`ledger/gos/pr-753.yaml`, or the dispatcher's go for a non-critical PR per MRG-01); then this thread runs `ledger_tool.py gate 753` and squash-merges pinned to dae7c19.
