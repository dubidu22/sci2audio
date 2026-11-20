# Plan: Issue #11, the speed script and baseline numbers (lane voices; item 28, wave 5)

Status: **approved by the coordinator 13 Nov 2026 07:52 UTC (D-281 to D-287); work started** (not critical: no layer contract, core dataclass, KB or golden file is touched; the open choices below each have a clear recommendation). Thread "Add speed script and baseline numbers". Written on `main` at 088abee (after #116). Feature IDs: VA-02 (PyTorch speed check on the M4), AQ-06, WI-04 (measured time estimate).

Sources read: Issue #11; `CLAUDE.md`, `.claude/rules/tests.md`, `.github/lanes.yml`, `.github/workflows/nightly.yml`; `docs/baseline.md`, `docs/release-checklist.md`; `plans/v1-remaining-plan.md` (item 28, Q13), `plans/issue18-kokoro-plan.md`, `plans/issue71-audio-job-plan.md` (section 4, D-159); code on `main`: `app/audio.py` (`run_audio_job`, `AudioProgress`, `_Speech.seconds_left`), `app/voice.py` (`VoiceSource`, `kokoro_voice`), `voices/kokoro_engine.py` (`EngineConfig.device`, device order mps, cuda, cpu), `tests/integration/test_voice_kokoro.py`, `tests/integration/test_audio_job.py`, `tests/unit/audio_fakes.py`.

## 1. What of #11 is still open

| Acceptance criterion | State on `main` |
|---|---|
| Speed script measures characters per second per voice and device; results in `docs/baseline.md` | **open**: only pytest benchmarks exist (`test_kokoro_speed_on_cpu` from #18, `test_benchmark_the_audio_job_on_a_short_paper` from #71), CPU only, one voice, no device choice, no script, no estimate check |
| pytest-benchmark tests for the text pipeline, run nightly | **done**: cutting (#63/#86), script job on arsiwalla (#70, fails above 30 s), output encoding (#69), all in the nightly `benchmarks` job |
| A written performance budget | **half**: "under 30 s for a 20-page paper" is written only inside the script-job section of `docs/baseline.md`; `docs/release-checklist.md` already says "run the speed script on the MacBook Pro M4 ... compare with the performance budget" |

So this PR adds the script, a budget section, and the measured rows; it closes #11. Colin's M4 row stays his release step (Q13).

## 2. The script

`uv run python scripts/speed.py` (after `sci2audio voices download`). One command, no arguments needed. It runs offline: everything after start-up runs inside `sci2audio.testing.no_network()`, so the numbers also prove VA-04.

**Part A, the voice alone, per voice and device.** A fixed English paragraph of our own writing (about 700 characters, 6 sentences; no third-party text) spoken sentence by sentence, as the job does, with `speak_to_wav` into a temp folder. Per device: model load seconds (once). Per voice and device: one warm-up sentence not counted, then characters per second (characters / wall time of synthesis plus WAV write) and real-time factor (seconds of audio / seconds of work; above 1 is faster than real time).

**Part B, the audio job on a corpus paper, per device.** `run_audio_job` on the paper in a fresh temp work and output folder (cold cache), default settings, voice `af_heart`, with a progress callback that time-stamps every event. Reported: whole job seconds; reading + layout + text steps seconds; voice load seconds; speaking seconds; encoding seconds; characters spoken; the job's own measured characters per second (`AudioJob.characters_per_second`, the number the estimate uses); audio seconds; real-time factor of speaking and of the whole job.

**Estimate accuracy (WI-04, D-159).** For every speaking event with `seconds_left` set: actual = time the encoding phase started − time of the event; error = (estimate − actual) / actual. Reported: when the first estimate appeared (characters done, %), its error; the error at 25 %, 50 % and 75 % of the characters; median and largest absolute error over all events with at least 10 s still to go (the last seconds divide by almost nothing). All samples go into the JSON file.

**Machine and versions** in every result: OS and version, machine model where the OS tells it (macOS `sysctl hw.model` and `machdep.cpu.brand_string`, Linux `/proc/cpuinfo`, Windows `platform.processor()`), CPU cores, memory, Python, torch, kokoro, misaki, sci2audio version, git commit of the checkout (if any), device, date (UTC).

**Options:** `--models-folder` (default: the app's `default_models_folder()`), `--device` (repeatable: `auto`, `cpu`, `mps`, `cuda`; default every device torch has here, so on the M4 both MPS and CPU), `--voice` (repeatable, default `af_heart`) and `--all-voices` (the 28 English voices, part A only), `--paper` (a corpus name such as `joss2022-biggs-pymedphys`, or a file; default `acl2023-hardt-ellipsis`), `--quick` (pymedphys, part A with one voice), `--skip-job`, `--json PATH`.

**Output:** a readable summary on screen, and always a JSON file (default `speed-<UTC date and time>-<host>.json` in the current folder, format `sci2audio-speed` version 1) holding everything above, plus ready-to-paste Markdown rows for `docs/baseline.md`, so a run is both referenceable and exportable. Exit code 0, or 1 with a clear message (voice files missing: "run `sci2audio voices download`"; unknown device or paper).

## 3. Files

| File | What | Size |
|---|---|---|
| `scripts/speed.py` | the script; small pure functions (estimate accuracy, rows, machine info) plus the runner; the voice is passed in, so tests use the fake voice | ~350 |
| `tests/unit/test_speed_script.py` | fast tests with `audio_fakes.FakeVoice` and a fake clock: accuracy maths (exact numbers on a made-up event list), the job part end to end on the pymedphys paper with the fake voice (JSON written, format/version, rows), argument errors, missing voice files message, no network attempt | ~200 |
| `docs/baseline.md` | new section "Speed script (#11)" with this container's rows; new section "Performance budget"; the M4 row left for Colin | |
| `docs/release-checklist.md` | the speed line names the command | 1 line |
| `.github/workflows/nightly.yml` | the `benchmarks` job also runs `scripts/speed.py --quick --device cpu` so the script cannot rot against the real voice (about 3 min) | 4 lines |
| `README.md` or `CONTRIBUTING.md` | one line on the speed script | 1 line |

No change to `src/`, so no layer, core, voice-contract or golden-file change. `scripts/` is outside the package (not in the wheel); ruff checks it, lint-imports and deptry do not need to.

## 4. Design questions (recommendation first; the coordinator assigns D-numbers)

Decided by the coordinator 13 Nov 07:52 UTC, all seven as recommended:
- D-281: script in the repo, no CLI command (Q1).
- D-282: every torch device, named (Q2).
- D-283: hardt default, `--quick` pymedphys (Q3).
- D-284: estimate error as first, 25/50/75 %, median and largest (Q4).
- D-285: JSON file plus pasteable rows, no result files committed (Q5).
- D-286: budget section: 30 s rule enforced, three reported targets (faster than real time on M4, estimate within ±25 %, encoding ≥ 50× real time) (Q6).
- D-287: nightly `--quick --device cpu` (Q7).


1. **Where the script lives.** (a, recommended) `scripts/speed.py` in the repository, run from a checkout with `uv run python scripts/speed.py`: the corpus papers are in `tests/corpus/` anyway, nothing new ships to users, and the release step is Colin's on a checkout. (b) A `sci2audio speed` command: ships a developer tool to every user, needs help texts, cli tests and later translation (#79), and still needs a paper. (c) Only pytest benchmarks: not one readable command, no device choice, results buried in pytest-benchmark JSON.
2. **Devices.** Recommended: every device torch reports (`mps`, `cuda`, `cpu`), each named explicitly (never "auto"), and the summary marks which one the app picks by itself (order mps, cuda, cpu, as `kokoro_engine`). Alternative: only the app's own device; but the issue asks per device, and CPU on the M4 is the fallback users without MPS get.
3. **Default paper.** Recommended `acl2023-hardt-ellipsis` (8-page two-column conference paper, about 20,700 spoken characters: enough chunks after the first estimate to judge it; about 8 minutes on this container's CPU, likely 2 to 4 on the M4). `--quick` uses pymedphys (5,800 characters). Alternatives: pymedphys as default (too few chunks after the first estimate to judge accuracy), arsiwalla (60,300 characters, about 23 minutes on CPU, too long for a routine run).
4. **Estimate accuracy measure.** As in section 2: signed error per event against the real remaining speaking time; summary at first estimate, 25/50/75 %, median and largest absolute error with at least 10 s to go. Alternative: only the first estimate's error (one number hides drift).
5. **Results format.** Recommended: always write the JSON file (`sci2audio-speed` v1) and print paste-ready Markdown rows; `docs/baseline.md` keeps the rows. Alternative: commit result JSON files under `docs/`: grows the repo with machine noise; the dated rows are the record.
6. **Performance budget** (new section in `docs/baseline.md`; the script prints each line as met or not). Recommended:
   - Script job: a 20-page paper prepared in under 30 s (exists; enforced by the nightly benchmark).
   - Speech on the reference machine (MacBook Pro M4, the app's own device): faster than real time, real-time factor at least 1 (informational; Colin's run decides it; CPU containers are not held to it).
   - Time estimate: once shown, within ±25 % of the real remaining speaking time while at least a minute is left (informational, checked by the script on every machine).
   - Encoding: at least 50 × faster than real time (today 340 × in #69's benchmark; informational).
   Alternative: enforce speech speed in CI: CI runners vary ("compare trends, not single runs", #11), so only the script job budget is enforced.
7. **Nightly.** Recommended: run `--quick --device cpu` in the nightly `benchmarks` job (the script then runs against the real voice every night; its numbers in the log give the trend). Alternative: fast tests only (the fake voice cannot catch a broken device path or a renamed engine attribute).

## 5. Tests

- `test_speed_script.py` (fast, no marker): the accuracy function on a hand-made event list (first estimate, 25/50/75 %, median and max with the 10 s cut-off, no estimate at all → "never shown"); the job part on pymedphys with `FakeVoice` and real ffmpeg (a few seconds of audio, allowed in the fast suite by D-118): JSON file written with format, version, machine, every phase time, at least one estimate sample, Markdown rows; network attempts list empty; `--paper` with an unknown name fails with exit code 1 and the list of corpus names; a missing models folder fails with the download hint, before any work.
- The real voice: the nightly step (Q7) and my own runs for the baseline rows.

## 6. Baseline numbers I record

On this Linux cloud container (4 vCPU Intel Xeon @ 2.10 GHz, CPU torch): part A for `af_heart` (and all 28 voices once, to see whether voices differ in speed), part B on hardt and pymedphys, with the estimate accuracy. Labelled with the hardware, date and commit. The M4 row stays empty with "Colin measures before v1.0 (VA-02)".

## 7. Out of scope

- Remembering the measured speed between jobs for an earlier estimate (noted in #71's plan; an issue if #77 wants it).
- Parallel synthesis or GPU tuning: an issue if the M4 run misses the budget.
- A `sci2audio speed` command (Q1 b): an issue later if users ask for it.

## 8. Outcome (13 Nov 2026)

- Code PR: dubidu22/sci2audio#139 (branch `issue11-speed-script`, commits 79db1fc and the docs commit). KB PR: dubidu22/sci2audio-design#39 (D-281 to D-287).
- Measured: hardt is 9 pages in `Content` (19,167 spoken characters), 380 s whole job on this container's CPU (not 8 minutes); pymedphys 123 s. The fixed paragraph is 517 characters (not 700).
- Found: the estimate misses the ±25 % target early on the short pymedphys paper (first estimates +32 % and +51 % in two runs); filed as dubidu22/sci2audio#136 (lane app).
