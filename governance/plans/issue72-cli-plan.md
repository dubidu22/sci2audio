# Plan: Issue #72, the command line (`script`, `convert`, `voices`) and the smoke test on three systems

Thread "Build the command line", 13 Nov 2026. Feature IDs WI-03 (command line), PE-02 (CI on three systems with a smoke test), VA-03 (voice download with licence and consent). Lane cli, plus infra (one step in `ci.yml`), docs (README section, CHANGELOG) and, if question 14 is decided as recommended, two lines in lane app.

Sources read: Issue #72; `CLAUDE.md`, `.claude/rules/tests.md`, `.claude/rules/licences.md`, `.github/lanes.yml`, `pyproject.toml` (layers, D-114 forbidden contract), `.github/workflows/ci.yml` and `nightly.yml`; KB D-47, D-104, D-114, D-121, D-122, D-138 to D-141; `plans/v1-remaining-plan.md` §2, §3 and Q5, Q6, Q12, Q13; `plans/issue70-script-job-plan.md`; `plans/issue71-audio-job-plan.md` with D-154 to D-166; `plans/issue76-server-plan.md` §8 (the `ui` subcommand); code on `main` 395e4c9 and on the PR #99 branch `app/issue71-audio-job` (`JobRunner.run_audio`, `AudioProgress`, `AudioJob`, `VoiceSource`, `kokoro_voice`, `clean_work_folder`, `default_models_folder`, `default_work_folder`, `work_folder_lock`); `voices.download` (`download_plan`, `download_voice_files`, `missing_files`, `KOKORO_LICENCE`, `SPACY_LICENCE`); the current `cli.py` stub and its three test files.

## 1. What the person can do

```text
sci2audio script FILE [options]        listening script + report, no voice needed
sci2audio convert FILE [options]       the audiobook (MP3 per chapter, M4B, read-along); resumes
sci2audio voices                       the voices, and whether the voice files are installed
sci2audio voices download [--yes]      shows files, sizes, licences, hosts; downloads after "yes"
sci2audio clean FILE                   removes the speech cache of FILE (question 1)
sci2audio ui [--no-browser]            added by #76, through the same command table (question 2)
```

Options shared by `script` and `convert`:

| Option | Meaning | Default |
|---|---|---|
| `-o, --output FOLDER` | where the files go | the settings file's folder, else next to FILE |
| `--chapters LIST` | chapter numbers as printed by `script`, e.g. `1,3-5`, or `all` | every chapter but the reference list (Q6) |
| `--off CATEGORY` / `--on CATEGORY` | switch a text-step category off (read as printed) or on; repeatable or comma-separated | the settings file, else the defaults (D-142) |
| `--language TAG` | `en`, `en-GB`, ... | the file's own, else `en` |
| `--overwrite` | replace existing output files | refuse (exit 7) |
| `--work-folder FOLDER` | the job's working folder | `default_work_folder(FILE)` (D-164) |
| `--ignore-settings` | don't read the settings file | read it |
| `-q, --quiet` | no progress lines (errors and the summary still print) | progress on stderr |

`convert` adds: `--voice ID` (from `sci2audio voices`), `--speed X` (0.5 to 2.0), `--format both|m4b|mp3`, `--with-script` (question 8), `--models-folder FOLDER` (default `default_models_folder()`). `voices` takes `--models-folder` too.

What `script` prints (stdout): the chapter table with the numbers `--chapters` takes, chosen or not and sentences per chapter; edits per category; problems (failed steps, `ask` edits, ignored chapter numbers); the three files written. What `convert` prints: progress on stderr, then the files written, chunks spoken and reused, skipped sentences, the length of the book, and the size of the speech cache with the hint `sci2audio clean FILE`.

## 2. Modules and sizes

| File | What | Size |
|---|---|---|
| `src/sci2audio/cli.py` | parser, command table, the four commands, exit codes, progress printer, Ctrl-C handling | ~550 lines |
| `src/sci2audio/app/job.py` | `UnreadableFileError(JobError)` raised by `read_document` (question 14) | +4 |
| `.github/workflows/ci.yml` | smoke step in the `tests` matrix job (question 15) | +15 |
| `README.md` | "Command line" section: the commands, exit codes, where files go | ~60 |
| `CHANGELOG.md` | one entry | +3 |
| tests (section 4) | | ~1,000 |

`cli.py` stays one module (lane cli is `src/sci2audio/cli.py`). It imports `sci2audio.app` and `sci2audio.voices` (download plan and function, voice list), never `sci2audio.testing` (D-114) and never `sci2audio.web` at import time (`ui` imports it inside its function, as #76 §8 plans).

## 3. Design questions, each with my recommendation

1. **Commands.** `script`, `convert`, `voices` with a nested `voices download`, and a small `clean FILE` that calls `clean_work_folder` (the #71 plan leaves offering it to the cli and the interface, D-158). Alternatives: `convert --clean-up` (cleaning later would mean converting again); `voices --download` as a flag (reads worse than a verb, and the download is all files at once, D-122, so "download one voice" isn't possible). No command at all prints the help and exits 2 (today it prints "nothing to run yet" and exits 0; `test_cli_runs` changes with it, explained in the PR).

2. **Structure, for #76's `ui` and for tests.** One command table (`name → (add_arguments, run)`), one pair of functions per command, so `ui` is one row plus its function and the merge with #76 touches separate lines. `main(argv)` builds the real `CliEnv` (streams, whether stderr is a terminal, an input function, the voice-source factory `kokoro_voice`, the download `fetch`, a `JobRunner`) and calls `run(argv, env)`; tests call `run` with fakes (the fake voice from `tests/unit/voice_fakes.py`, a fake `fetch`). No module-level state. Alternative: split into a `cli/` package (changes the lane path in `lanes.yml` and conflicts with #76's edit of `cli.py`).

3. **Exit codes**, documented in `--help` and the README, pinned by a test:

   | Code | When |
   |---|---|
   | 0 | done (problems in the report do not change it) |
   | 1 | failed for another reason: a write failed, disk full, ffmpeg failed, the voice failed five times in a row, the download failed, the person said no at the download question |
   | 2 | usage: unknown option, bad chapter list, unknown category or voice id, speed out of range, `voices download` without a terminal and without `--yes`, no command |
   | 3 | FILE not found, or not a file |
   | 4 | file type not supported (`UnsupportedFileError`) |
   | 5 | file damaged or unreadable: password-protected, not a PDF inside, cannot be opened (question 14) |
   | 6 | voice not installed (files missing in the models folder) |
   | 7 | output files exist and `--overwrite` was not given (`OutputExistsError`) |
   | 8 | busy: another sci2audio job is working on this file (`JobBusyError`) |
   | 130 | stopped with Ctrl-C (128 + SIGINT, the shell convention) |

   Messages go to stderr as `sci2audio: <message>`; the app's `JobError` messages are already written for people (D-140), and the cli adds the next step where there is one ("run `sci2audio voices download`", "add `--overwrite`", "run the same command again to continue"). No traceback ever reaches the person; an unexpected exception prints one line, says it is a bug, and exits 1. Alternatives: BSD `sysexits` codes 64 to 78 (unfamiliar to most users, and no code for "voice missing"); one code 1 for every failure (the issue asks for clear codes for the four cases).

4. **The settings file (D-139).** `script` and `convert` read it as defaults (language, switches, voice, speed, output folder), options override it for this run, and the cli **never writes it** (the interface does). Its warnings print to stderr and never stop the run. `--ignore-settings` gives the built-in defaults, for scripts that must not depend on what was set in the interface. Alternative: ignore the file (the voice picked in the interface would not carry over to the command line, against playbook 3.4); write options back (a one-off `--speed` would silently change the interface).

5. **Chapter numbers.** The cli counts chapters **from 1**, as the Markdown report's table and the MP3 file numbers do, and converts to `JobSettings.chapters` (from 0). `LIST` is numbers and ranges (`1,3-5`) or `all`. A number the document doesn't have is reported by the cli in the same 1-based terms (from `ScriptResult.ignored_chapters`) and the run goes on (D-140). Finding while reading: the report's own problem line says "chapter N was chosen, but the document has chapters 0 to M" in 0-based numbers, inside a Markdown report whose table counts from 1; I'll file an issue (lane app) rather than change the report here. Alternative: from 0, as the JSON (people read the table, not the JSON).

6. **Category switches.** `--off citations` and `--on footnote-texts`, by the `Category` values; `--help` lists every value with its label and whether it starts on. "On" means the step works on that category ("Citations": citations are left out; "Footnote texts": the notes are left out, D-142); "off" means the text is read as printed. The same category in `--on` and `--off` is a usage error. Alternative: one `--leave-out` list, as the issue words it (reads wrong for categories whose step replaces rather than removes, such as numbers and abbreviations).

7. **Folders.** Output files next to FILE unless `-o` (or the settings file's folder); the working folder is `default_work_folder(FILE)` for **both** commands, so the script job's `job.json` sits beside the audio job's chunks and records for the same file (D-164); `--work-folder` and `--models-folder` override, which the tests and CI use. Alternative: a temporary working folder for `script` (its `job.json` would be lost).

8. **`convert` writes the audiobook only** (D-154: the script and report are the script job's). `--with-script` runs the script job first with the same settings and the same `--overwrite`, writing the script and the report next to the audiobook. Alternative: always write them (each rerun would need `--overwrite` for the script files too, and `convert` would clutter the folder for people who only want audio).

9. **Resume.** Nothing to ask: running the same `convert` again on the same file uses the same working folder, and the audio job speaks only what is missing (D-156); the summary says "spoke N, reused M". A stopped run leaves nothing in the output folder, so the rerun needs no `--overwrite`. A run with another voice or speed reuses nothing (D-155) and needs `--overwrite` if the earlier book was finished; the message says so.

10. **Ctrl-C.** `convert` runs the job in a worker thread and waits in the main thread. The first Ctrl-C sets the job's cancel event (D-160): the cli prints "stopping after the current sentence; finished sentences are kept" and the job stops at its next cancel point; exit 130 with "run the same command again to continue". A second Ctrl-C exits at once (unfinished `.part` chunks are removed on the next start, D-156). `script` (seconds) and `voices download` stop at once on Ctrl-C (writes are atomic; the download removes its `.part` file, D-122); exit 130. Alternative: no thread, KeyboardInterrupt wherever it lands (could fire inside an ffmpeg call or a chunk write; the cancel event exists for this).

11. **Progress.** On stderr, so stdout carries only the result. On a terminal: one line rewritten in place ("Speaking chapter 2 of 5, Methods: 120 of 455 sentences, about 3 min left"; "measuring speed" until D-159's estimate exists). Not a terminal (CI, a log file): one line per phase and per chapter, no `\r`. `--quiet` turns it off. Alternative: a progress-bar package (a new dependency for one line of text).

12. **Voice download with consent (VA-03, D-122, D-141).** `voices download` first prints, without any network: the destination folder; each source with its file count, size and licence (Kokoro-82M model, config and 28 English voices from huggingface.co, Apache-2.0, 342 MB; spaCy `en_core_web_sm` 3.8.0 from github.com, MIT, 12.8 MB); the total (about 355 MB) and the note that both hosts redirect to their download servers (Hugging Face's CDN and storage, objects.githubusercontent.com) and every file is checked by sha256. Then `Download about 355 MB? [y/N]`; only `y` or `yes` starts it. `--yes` is consent given on the command line (for scripts and CI); without a terminal on stdin and without `--yes` it refuses (exit 2) rather than wait. When everything is in place it says so and fetches nothing (exit 0). Progress in MB on stderr. It calls `voices.download_voice_files(models_dir, progress=...)`, the one download function (Q12, D-122), and nothing else. Alternative: consent through an environment variable (invisible in the command that runs).

13. **Voice checks before any work.** `convert` checks `--voice` against the voice list (unknown id: exit 2 with the hint `sci2audio voices`) and `missing_files(models_dir)` (missing: exit 6 with "the voice files are not installed; run `sci2audio voices download`") before the file is read. `convert` never downloads. `voices` (the list) shows id, name, accent, gender, the default voice and whether the files are installed, without network. Alternative: offer the download from inside `convert` (a network call from a command that is not about downloading; scripts would block on the question).

14. **Telling a damaged file apart.** The app raises a plain `JobError` both for a file it can't read and for a write that fails, so the cli can't tell exit 5 from exit 1. Recommendation: a subclass **`UnreadableFileError(JobError)`** raised by `app.job.read_document` for `ExtractionError` and for `OSError` on opening (4 lines in lane app, named in the PR; the server can map it to its own error code too; existing tests keep passing because it is still a `JobError`). Alternative: the cli inspects `error.__cause__` for `ExtractionError` (works today, but depends on how the app chains its errors).

15. **Smoke test on three systems (PE-02).** Every PR: a step in the `tests` matrix job of `ci.yml`, after the fast tests, that runs the **installed console script** `uv run sci2audio script tests/corpus/papers/joss2021-waskom-seaborn.pdf -o "$RUNNER_TEMP/smoke" --work-folder "$RUNNER_TEMP/smoke-work" --ignore-settings` and checks that the script, `.report.json` and `.report.md` exist and are not empty (bash on all three systems, about 5 s). Also a fast pytest test that runs the same command through `subprocess` (so it runs locally too). Nightly: a `slow` pytest test (the existing nightly job runs `pytest -m slow` with the cached voice files, so `nightly.yml` does not change) that runs `sci2audio convert` as a subprocess on `joss2022-biggs-pymedphys.pdf` (about 5,800 characters, about 2 min of speech) with `--models-folder $SCI2AUDIO_TEST_MODELS`, checks the M4B, the MP3s and the read-along file exist and are not empty; then kills a second run on a fresh work folder after its first chunks appear, runs it again and checks it reused them (the fault-injection rule for resume); then reruns the first with `--overwrite` and checks that nothing was spoken again. The subprocesses get `HTTP_PROXY`/`HTTPS_PROXY` pointing at a closed local port, so any `requests` call would fail. **The EPUB part of the criterion waits for #73** (EPUB extraction is not built yet): I'll add a checkbox to #73 to add `wells-the-time-machine.epub` to this nightly test. Alternative: a separate smoke workflow (another required check on main; the ruleset only requires "CI passed").

16. **Windows consoles.** A redirected stdout on Windows uses the locale code page (cp1252), so printing a title like "García" can raise `UnicodeEncodeError`. `main` reconfigures stdout and stderr with `errors="replace"` (encoding unchanged): a character the console can't show becomes `?` and the run never fails over it. Tested with a cp1252 stream.

17. **`clean` while a job runs.** `clean_work_folder` on the #99 branch removes `chunks/` without taking the work-folder lock, so `sci2audio clean FILE` during a running `convert` (or the server's audio job) would delete chunks under it. Recommendation: `clean_work_folder` holds `work_folder_lock` and raises `JobBusyError` (exit 8) when a job holds it; best fixed in #99 itself (its review can take it as a finding); if #99 merges without it, my PR adds it in `app/chunks.py` with a test.

## 4. Tests

- `tests/unit/test_cli_script.py`: a tiny generated PDF (`pdf_maker`) and the seaborn paper: the three files exist and match `run_script_job`'s; chapter table output (golden); `--chapters 2`, `all`, ranges, an out-of-range number (warned in 1-based terms, exit 0); `--on/--off` reach `JobSettings`; `-o`; `--overwrite`; settings file read, overridden by options, ignored with `--ignore-settings`, broken file only warns, and never written (file unchanged after a run).
- `tests/unit/test_cli_convert.py` (fake voice, real ffmpeg on a few seconds of audio, as #71's tests): files written; summary; second run reuses everything and needs `--overwrite` only when the book exists; `--format m4b`; `--with-script`; `--voice`, `--speed` reach the job; unknown voice exit 2; missing voice files exit 6 before the file is read; Ctrl-C via `_thread.interrupt_main()` while the fake voice speaks: cancel event set, exit 130, chunks kept, rerun continues; busy exit 8 while `work_folder_lock` is held.
- `tests/unit/test_cli_voices.py`: list (no network, `sci2audio.testing` is not used by cli but the tests use its `no_network` guard); download plan text (golden: sizes, licences, hosts, folder); consent `y`, `n`, empty, EOF; no terminal and no `--yes` exit 2 and nothing fetched; `--yes` with a fake `fetch`: files in place, progress lines; already installed: nothing fetched; network error exit 1; Ctrl-C mid-download: exit 130, no `.part` left.
- `tests/unit/test_cli_errors.py`: one test per exit code in the table (missing file, a folder as FILE, `.docx`, the broken fixture `password-protected.pdf`, a PDF that isn't one, output exists, busy, a write into a read-only output folder), each checking code, the stderr line and no traceback; an unexpected exception prints one line and exits 1; the cp1252 stream test.
- `tests/unit/test_cli_golden.py`: help texts of `sci2audio` and of each command pinned (the existing snapshot changes: golden file, so the PR is critical and labelled `risk:high`).
- `tests/unit/test_cli_properties.py`: any arguments end in one of the documented exit codes and never a traceback (today: 0 or 2), run with the work, models and config folders in `tmp_path` and the network blocked.
- `tests/unit/test_smoke.py`: `test_cli_runs` changes to expect the help and exit 2 (question 1); a subprocess test of `sci2audio script` on the seaborn paper.
- `tests/integration/test_cli_convert.py` (`slow`): question 15.
- Layers: `lint-imports` already forbids cli → testing (D-114); a test checks that importing `sci2audio.cli` does not import `sci2audio.web`, fastapi, torch or kokoro (the command line starts fast and `--version` loads nothing heavy).

Fast suite: about 60 new tests, a few seconds (the corpus extraction of one paper is about 0.5 s).

## 5. Sequencing

1. Build on the PR #99 branch (`app/issue71-audio-job`) against its interfaces; merge `main` in when #99 lands; **open the PR only after #99 is merged**.
2. One code PR: `cli: script, convert, voices and clean commands with a smoke test on three systems (#72)`, lanes cli + infra (the `ci.yml` step, named in the PR) + docs + app (question 14), `risk:high` because the help snapshot is a golden file. It references other PRs only with plain links or "see".
3. #76 adds `ui` to `cli.py`: whichever merges second merges `main` in; with the command table the two edits are separate rows.
4. A KB PR in `sci2audio-design` with the decisions as "Decided (Claude)", with the D-numbers and the "Colin informed" time the coordinator gives.
5. Follow-up issues: the 0-based chapter number in the report's problem line (question 5), and the EPUB nightly checkbox on #73 (question 15).

## 6. Out of scope

The `ui` command (#76); the browser interface (#77); EPUB, Markdown and text input (#73, #74: they join through `app.job.EXTRACTORS`, and the cli needs no change); German interface texts (#79 covers the web interface; the cli is English in v1.0); a machine-readable progress stream (`--json`); shell completion.
