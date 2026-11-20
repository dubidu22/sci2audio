# Review of sci2audio PR #139, round 1 (Issue #11, speed script; D-281 to D-287)

Reviewed head `78de509` (the author's merge of main at 1064e18), 13 Nov 2026. Reviewer: review thread "Review speed script PR 139".

## What I checked

- Whole diff (6 files: `scripts/speed.py`, `tests/unit/test_speed_script.py`, `docs/baseline.md`, `docs/release-checklist.md`, `CONTRIBUTING.md`, `.github/workflows/nightly.yml`) against plan `plans/issue11-speed-plan.md` choices 1 to 7. All seven decisions are implemented as decided: script in `scripts/` (D-281), every torch device named, `auto` = the engine's own order (D-282), hardt default and `--quick` pymedphys (D-283), estimate error first / 25 / 50 / 75 % / median / largest with the 10 s cut (D-284; compared against the start of encoding, which matches `_Speech.seconds_left`, a speaking-only estimate), JSON `sci2audio-speed` v1 plus rows, nothing committed, no host name (D-285), budget section with one enforced rule and three reported targets (D-286), nightly `--quick --device cpu` step using the cached voice files (D-287). No `src/` change, so no layer, core, voice-contract or golden-file change.
- `uv run ruff check`, `ruff format --check`, `lint-imports`, `deptry src`: clean. `zizmor --offline .github/workflows`: no findings.
- Fast suite: 2114 passed, 54 snapshots (52 s).
- Nightly Hypothesis profile (`HYPOTHESIS_PROFILE=nightly`) on the fast suite: 2114 passed (5 min 53 s).
- Real voice: downloaded the Kokoro files and ran exactly the nightly line (`--quick --device cpu --models-folder … --json …`) on this container: exit 0, no network attempts, 131 s whole job, 41.7 characters per second, RTF 3.14 while speaking, estimate first +24 %, largest +26 % with a minute left (so #136 reproduces: [NOT met]).
- Arithmetic of the committed baseline rows (RTF 1548.9 / 352.92 = 4.39; 19,167 / 352.92 = 54.3; encoding 62× and 57×): correct.
- CI on 78de509: every job green on Linux, macOS and Windows, plus browser, lint and layers, licences, security, CodeQL.

## Findings

1. **Should fix: `--json` into a folder that does not exist loses the whole run.** `main` writes the JSON only after `measure` finished and before printing the summary, so `--json results/speed.json` without a `results/` folder ends in a `FileNotFoundError` traceback after the full measurement (about 10 minutes on the M4 release run), with no summary and no rows on screen. Probed with the fake voice: `RAISED FileNotFoundError … nope/x.json` after part A ran. Fix: check (or create) the target's folder before any work and stop with exit 1 and a clear message if it cannot be written; a test for it.

2. **Should fix: a job error ends in a traceback after part A, nothing written.** `resolve_paper` accepts any existing file, but the job reads only PDF today: `--paper notes.md` measured part A, then died with `UnsupportedFileError: p.md: sci2audio can read .pdf files only` as a traceback. Any other `JobError` from `run_audio_job` does the same. Plan §2 promises "exit code 1 with a clear message" for an unknown paper. Fix: catch `JobError` in `main` and say it as `speed: …` with exit 1 (better also refuse a paper the job cannot read before any work, without hard-coding `.pdf` so #73's EPUB keeps working); a test for it.

3. **Minor: `--quick` silently drops `--voice`.** `measure` uses `[DEFAULT_VOICE]` whenever `--quick` is set without `--all-voices`, so `--quick --voice bf_lily` measures af_heart, and `--quick --voice xx_nobody` exits 0 without the unknown-voice message. Fix: under `--quick`, honour `--voice` (quick then only means the short paper and, by default, one voice) and validate it as usual; a test for it.

4. **Minor: the speech budget is judged on devices it does not apply to.** D-286 sets "faster than real time" for the reference machine with the device the app picks by itself, but `budget()` marks every device met or NOT met; on the M4 a slow CPU row would print `[NOT met]` for a target that is not about the CPU. The `reference` field is computed but the summary never uses it. Fix: `met = None` (not judged) for devices other than the app's own, or print "(the app's device)" in the line; update the budget test.

No other findings. Once 1 to 4 are fixed (or 3 and 4 filed as issues, with links), this PR is ready to merge.
