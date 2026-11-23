# Plan: impl-744, espeak-ng on Windows with a non-ASCII data folder (#744)

Thread: `impl-744`, implementation, lane:voices, batch 005 slot B item 1, Opus 5.5 high. Status: **non-critical, started at once** (D-72): `src/sci2audio/voices/espeak.py` and its unit tests only; no layer contract, no core dataclass, no golden file, no `.github/**`, no `pyproject.toml`, no new dependency.

## 1. Expected cause (to be measured on Windows CI)

phonemizer passes the data folder to `espeak_Initialize` as UTF-8 bytes (`phonemizer/backend/espeak/api.py:49`). espeak-ng's `espeak_ng_InitializePath` checks the folder with the narrow C API (`stat` through `GetFileLength`) before `espeak_ng_Initialize` sets a UTF-8 `LC_CTYPE`. The Windows CRT turns narrow paths into file names through the ANSI code page unless the locale is UTF-8, so `ü` (UTF-8 `C3 BC`) is read as `Ã¼` in cp1252: the folder is not found, espeak-ng falls back to its build-time folder, finds no `phontab` and calls `exit(1)` (#663). Python sets `LC_CTYPE` to the user's locale (`.1252` on the GitHub runner), not UTF-8. So the folder works only where its UTF-8 bytes are the same in the ANSI code page: an ASCII path, or a system whose ANSI code page is UTF-8 (65001, the Windows "Beta: UTF-8" option).

This is a prediction. The characterisation test (4.1) measures it on `windows-latest` in the PR's `ci:full` run; if Windows speaks instead, the check (section 2) is dropped, the test pins speaking, and the PR says so (the third acceptance criterion).

## 2. Change, if Windows exits

`src/sci2audio/voices/espeak.py`:

- `windows_ansi_encoding() -> str | None`: the ANSI code page (`locale.getencoding()`) on Windows, `None` elsewhere, where espeak-ng opens the UTF-8 bytes as they are.
- `check_espeak_data`: after the length check (unchanged) and before the `phontab` check, raise `ModelLoadError` when the ANSI encoding is set and the path's UTF-8 bytes differ from its bytes in that encoding (any non-ASCII character unless the code page is UTF-8). The message names the folder, the code page and #744, and asks for a folder whose path holds only ASCII characters. This is stricter than "not encodable in the ANSI code page", the Issue's example: `ü` is encodable in cp1252, but espeak-ng gets the UTF-8 bytes, which are not cp1252's.
- The module docstring gets one sentence on why.

No retry, no fallback copy of the data folder (REV-06): the check stops the job with an error before espeak-ng can end the process.

## 3. Not changed

POSIX: `windows_ansi_encoding()` is `None`, so nothing new is checked. The length limit and its tests from #739 stay as they are. The fast suite stays offline (the test copies the wheel's own data).

## 4. Tests (first)

1. `tests/unit/test_voices_espeak.py::test_espeak_on_a_non_ascii_data_folder`: copies (Windows) or links (POSIX) the wheel's data into `tmp_path / "Jürgen" / "data"` and runs the test's `SPEAK` script on it. POSIX, and Windows with a UTF-8 ANSI code page: speaks `bɾˈʏkə` from that folder. Windows with any other code page: exits 1, `phontab` in stderr, nothing spoken. Red before the check exists only in the sense that it pins espeak-ng's own behaviour; the Windows outcome is measured in CI.
2. `tests/unit/test_voices_espeak.py::test_a_non_ascii_data_folder_is_refused_under_an_ansi_code_page`: with `windows_ansi_encoding` patched to `cp1252`, a folder `Jürgen` holding a `phontab` raises `ModelLoadError` naming the folder and `#744`. Fails before the change (no error). Runs on all three systems.
3. `tests/unit/test_voices_espeak.py::test_a_non_ascii_data_folder_passes_where_espeak_reads_utf8`: with `windows_ansi_encoding` patched to `None` and to `utf-8`, the same folder passes; an ASCII folder passes under `cp1252`.
4. `tests/unit/test_voices_espeak.py::test_windows_ansi_encoding_is_set_on_windows_only`: `None` off Windows, a code page name on Windows.
5. Unchanged and still green: the five tests of #739 in the same file.

## 5. Size

About 25 lines in `espeak.py`, about 70 lines of tests. One PR `voices: refuse a non-ASCII espeak-ng data folder on Windows (#744)`, `Closes #744`, lane:voices, risk:low, label `ci:full` (the fault is Windows-only).

## 6. Results
