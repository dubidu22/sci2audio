# Review PR #739, round 1

Thread review-b004-b (review, Opus 5.5 medium), batch 004 slot B, 22 Nov 2026. Author voices-b-v1.
PR: `voices: an espeak-ng data path espeak-ng would exit on is refused with an error (#663)`.
Head reviewed: 744cc83e654fecce770a27ee1d3930a70c46cb05. Plan: `plans/voices-b-v1-plan.md`.

**Critical: no** (CRIT-03, from the diff). Files: `src/sci2audio/voices/{espeak,kokoro_engine,kokoro_german}.py` and four `tests/unit/test_voices_*.py`. No core type, layer contract, voice plugin contract (the factory raises the contract's existing `ModelLoadError`), golden file, `.github`, `pyproject.toml`/`uv.lock`, licence, file writing outside `tmp_path` or network call. The check is an input validation that turns a process exit into a typed error, not a safety mechanism of CRIT-01.

**Verdict: changes requested** (no must-fix; one should-fix, two notes).

## Verified

- Buffer sizes against espeak-ng 1.52.0 source (`gh api`, tag `1.52.0`): `speech.h:59/66` `N_PATH_HOME_DEF` 230 on Windows, 160 elsewhere; `speech.c:247-260` `check_data_path`; `src/include/compat/stdio.h:33-36` maps `snprintf` to `_snprintf` under `_MSC_VER`. The POSIX limit 159 matches, and is the same on Linux and macOS.
- Bytes, not characters: phonemizer resolves the folder (`wrapper.py:218`) and passes `str(data_path).encode('utf-8')` (`api.py:49`); the check resolves the same way and measures `os.fsencode` (UTF-8 on all three systems). `test_a_non_ascii_path_is_measured_in_bytes` kills a characters mutant (chars <= limit < bytes, `phontab` present).
- VER-02 on the limit: mutants `else 160` and `else 158` each fail `test_voices_espeak.py` locally (1 failed, 4 passed both times), so the characterisation test pins the boundary from both sides. File restored.
- Local run on this head: the four touched test files, 100 passed (macOS, worktree data path 140 bytes).
- CI on 744cc83: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, `CI passed`, `governance pr checks`, lint and layers, licences, browser green. Issue acceptance: the three tests run in the macOS fast suite with no deselect.
- Nothing skipped: no `skip`, `xfail`, `importorskip` or deselect in the diff. On Windows the characterisation test still runs the at-limit case; only the over-limit exit is POSIX-only, and the over-limit refusal is still tested on Windows by `test_a_data_path_past_the_limit_is_refused_before_espeak_loads`.
- Windows copy instead of links: test scaffolding only; installed apps and checkouts do not symlink the wheel's data, so it hides no user path. Not a finding.
- Lane: all source files under `src/sci2audio/voices/**` (lane:voices), tests under `tests/unit/`. OK.
- Error text: names the folder, its size, the limit, the remedy (a shorter folder, or reinstall) and #663. Clear enough for a user; it reaches the job as `ModelLoadError` before any model loads (the factory check runs before `german_pipeline` loads weights).
- Order in the factory: `_check_pack`, then `check_espeak_data()`, then the pipeline; English (`a`, `b`) and German (`d`) are all covered by the parametrised test.

## Findings

### S1 (should-fix) The Windows limit 229 still runs espeak-ng's undefined first copy

`src/sci2audio/voices/espeak.py:27` (and the module docstring at `:9-11`, the test docstring at `tests/unit/test_voices_espeak.py:55-57`, the PR body "Test summary").

`check_data_path` (`speech.c:251`) first copies `"%s/espeak-ng-data"`, 15 bytes longer than the folder, into the same 230-byte buffer, and only then (`:258`) the folder alone. With MSVC's `_snprintf` a copy that does not fit leaves `path_home` without its zero byte, and `GetFileLength(path_home)` reads past the buffer. So every Windows folder of 215 to 229 bytes already runs the undefined read the PR names as its reason for stopping at 229; it passes on the runner for the same reason 230 did (a zero byte happens to follow). POSIX is unaffected: its `snprintf` always terminates, and at 159 bytes the cut first copy is the folder itself.

Fix: on Windows keep both copies inside the buffer:

```python
# espeak-ng copies the folder plus "/espeak-ng-data" first, then the folder alone, into
# path_home[N_PATH_HOME]; MSVC's _snprintf leaves a copy that does not fit unterminated
ESPEAK_PATH_LIMIT = 230 - 1 - len("/espeak-ng-data") if sys.platform == "win32" else 159
```

(214 on Windows.) Correct the module docstring and the test docstring to match (undefined from 215 bytes on Windows, not from 230), and the PR body. The existing tests then pin the Windows at-limit case at 214 with no other change.

### N1 (note) Non-ASCII data folders on Windows are not measured

phonemizer hands espeak-ng UTF-8 bytes (`api.py:49`), and espeak-ng opens its files with the narrow C API, which Windows reads in the ANSI code page. A folder such as `C:\Users\Jürgen\...` may then not be found, and espeak-ng would fall back and `exit(1)` exactly as in #663. Not measured here (no Windows machine) and outside #663's acceptance. Recommended: a follow-up Issue (lane:voices, risk:low) with a Windows characterisation test that runs the test's `SPEAK` script on a copy of the data in a non-ASCII folder and, if it exits, a refusal in `check_espeak_data` for folders not encodable in the ANSI code page. No change in this PR.

### N2 (note, narrating-comment) A docstring line says what, not why

`src/sci2audio/voices/espeak.py:14`: "misaki is imported only inside the functions that need it." describes the code (PR-05). Fix: delete the line, or replace it with the reason for the lazy import if there is one.

## Next

Author: one fix commit for S1 and N2; answer N1 (Issue link, or decline with a reason). Round 2 checks S1 and N2 on Linux CI (non-critical).
