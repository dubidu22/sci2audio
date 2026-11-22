# Voices B-V1: #663, real-espeak tests exit pytest on macOS (plan)

Thread voices-b-v1 (implementation, Opus 5.5 high), batch 004 slot B, 22 Nov 2026. Base: main 204c188.

**Critical: no.** lane:voices, risk:low. No `pyproject.toml`, `conftest.py` marker, `.github`, golden file, core type or plugin-contract change.

## 1. Cause (measured)

espeak-ng copies its data folder into a fixed buffer, `char path_home[N_PATH_HOME]`: 160 bytes on POSIX, 230 on Windows (espeak-ng 1.52.0, `src/libespeak-ng/speech.h`; `check_data_path` in `speech.c` uses `snprintf(path_home, sizeof(path_home), ...)`). A longer path gets truncated, the cut path is not a folder, and espeak-ng falls back to the folder baked in when the wheel was built (`/Users/runner/work/espeakng-loader/...`). There it finds no `phontab` and calls `exit(1)`, which ends the whole process: pytest with no summary, or the app's server in the middle of a job.

Evidence, each a fresh `python -I` subprocess on this Mac, with misaki's `EspeakG2P("de")` on a copy of the wheel's `espeak-ng-data`:

- data path 159 characters: `bɾˈʏkə`, exit 0. 160 characters: `Error processing file '/Users/runner/work/espeakng-loader/.../phontab': No such file or directory.`, exit 1. That is the issue's exact message.
- No data path at all (`set_data_path(None)`): the same message, exit 1. A missing or unreadable `phontab` in a short folder: exit 1 naming that folder. The macOS hidden flag (iCloud) on the data: works.
- Today on this Mac the wheel's data path is 140 characters in a worktree and 85 in `~/Projekte/sci2audio`. The three tests pass alone (`-p no:cacheprovider -x`, faulthandler, exit 0) and in the full fast suite (8797 passed, no deselect, 14 min with the `dev` profile). The failing runs came from the old `~/Documents/...` iCloud checkout (moved 20 Nov 2026), which no longer exists, so its path can't be measured. The only way a readable folder from espeakng-loader yields the baked-in path is this buffer limit. Worktree paths here leave 19 characters of headroom.
- So the cause is not macOS itself: it is path length, and it hits the English voice too (kokoro's `KPipeline` builds misaki's `EspeakFallback` on espeak-ng).

## 2. Fix

New module `src/sci2audio/voices/espeak.py`:

- `ESPEAK_PATH_LIMIT`: 229 bytes on Windows, 159 elsewhere (the buffer minus its terminating zero byte).
- `check_espeak_data(path=None)`: takes the folder phonemizer will pass (default: espeakng-loader's, read through `misaki.espeak.espeakng_loader`, because espeakng-loader is not a direct dependency and deptry would refuse an import), resolves it as phonemizer does, and measures it in UTF-8 bytes. It raises `ModelLoadError` naming the path, its length, the limit and #663 when the path is too long, or when the folder has no readable `phontab`. espeak-ng would exit the process in both cases.
- `espeak_g2p(language)`: calls `check_espeak_data()`, then returns misaki's `EspeakG2P(language=...)`.

Callers: `kokoro_german.german_pipeline` builds its G2P with `espeak_g2p("de")`. `kokoro_engine`'s pipeline factory calls `check_espeak_data()` before it builds a `KPipeline` (English), so the error reaches the job runner as a typed engine error instead of killing the process. The test helpers (`test_voices_german.py`, `espeak_german()` in `test_voices_letters.py`) use `espeak_g2p`, so a too-long path fails those tests with the message instead of ending pytest.

Alternatives rejected:
- Skipping on macOS: the cause is path length, not macOS (macOS CI passes), and a skip hides it on Linux too.
- Making long paths work: phonemizer resolves symlinks, so a short link does not help. Copying the 19 MB folder to a short cache path is file writing (fault-injection tests, D-58) for a case only deep developer checkouts reach. Installed apps sit well inside the limit. Not planned. The error names the remedy (a shorter folder).

## 3. Tests (first)

1. `tests/unit/test_voices_espeak.py::test_espeak_exits_on_a_data_path_past_its_buffer`: characterisation of the upstream behaviour, so the limit stays honest. A subprocess runs misaki's `EspeakG2P("de")` on a folder of links to the wheel's data, at exactly `ESPEAK_PATH_LIMIT` bytes (speaks, exit 0) and at one byte more (exit 1, `phontab` in stderr). It passes on main, because it pins espeak-ng's behaviour, not ours.
2. `tests/unit/test_voices_espeak.py::test_a_data_path_past_the_limit_is_refused_before_espeak_loads`: `check_espeak_data` on a path one byte over the limit raises `ModelLoadError` naming #663 and the limit, and one at the limit passes. Fails on main (no module).
3. `tests/unit/test_voices_espeak.py::test_a_data_folder_without_phontab_is_refused`, and `::test_a_non_ascii_path_is_measured_in_bytes` (espeak-ng counts bytes, not characters): fail on main.
4. `tests/unit/test_voices_espeak.py::test_the_wheels_data_folder_passes_the_check`: the real default path passes. Fails on main.
5. `tests/unit/test_voices_kokoro.py::test_a_too_long_espeak_path_fails_the_pipeline_with_a_model_load_error`: the factory raises `ModelLoadError` for English and German before any pipeline is built (fake pipelines, `check_espeak_data` patched to a long path). Fails on main.

The three tests of the issue keep their names and run unchanged in the fast suite, with no deselect.

Then the fast checks without deselecting anything, the PR, and a `ci:full` run (acceptance: the three pass on macOS). The author removes the label once it is green.

Size: about 50 lines in `src/sci2audio/voices`, 90 in tests.

## Tests promised in the plan

- `tests/unit/test_voices_espeak.py::test_espeak_exits_on_a_data_path_past_its_buffer`
- `tests/unit/test_voices_espeak.py::test_a_data_path_past_the_limit_is_refused_before_espeak_loads`
- `tests/unit/test_voices_espeak.py::test_a_data_folder_without_phontab_is_refused`
- `tests/unit/test_voices_espeak.py::test_a_non_ascii_path_is_measured_in_bytes`
- `tests/unit/test_voices_espeak.py::test_the_wheels_data_folder_passes_the_check`
- `tests/unit/test_voices_kokoro.py::test_a_too_long_espeak_path_fails_the_pipeline_with_a_model_load_error`
- `tests/unit/test_voices_german.py::test_real_espeak_german_gives_only_kokoro_symbols`
- `tests/unit/test_voices_letters.py::test_german_spans_are_spelled_words_found_in_the_sentence`
- `tests/unit/test_voices_letters.py::test_the_german_pipeline_slows_spelled_letters`
