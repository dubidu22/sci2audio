# PR #689 review, round 1 (head 13ec9c2)

Reviewer: review-web-b-w2, Opus. 20 Nov 2026. Plan: plans/web-b-w2-plan.md §2 (PR B), approved as D-847. Issues #667, #669.
Critical: **yes** (CRIT-01: the CLI help golden `tests/unit/__snapshots__/test_cli_golden.ambr` changes; `risk:high` set; plan approved).
Verdict: **changes requested** (0 must-fix, 2 should-fix, 5 notes).

## Checked and fine

- **(1) Plan and scope.** 16 files: `app/{settings,runner,job,report,audio}.py`, `cli.py`, their tests, `tests/unit/cli_helpers.py` (a test helper, part of "their tests"), the CLI help snapshot, CHANGELOG, and `docs/plugins.md` (N1). No web file, no `core`, no `.importlinter`/`pyproject.toml` change. Labels `lane:app`, `lane:cli`, `lane:docs` (needed for `CHANGELOG.md` anyway), `risk:high`.
- **(2) Goldens.** The only golden diff is the CLI help snapshot: `script` and `convert` usage lines rewrap for `[--no-plugins]`, and each gains the two help lines. No report, `job.json` or `audio.json` golden changes; the snapshot suite passes unchanged (7 snapshots in the plan-test run, all goldens in the fast suite).
- **(3) Settings and runner.** `JobSettings.plugins: bool = True`, refused unless a bool (`settings.py:79`); not in `KEPT`, and `load_settings` drops an unknown `plugins` key with a warning. `steps_for` (`runner.py:33-38`) returns `self.steps` when on and otherwise drops exactly the steps whose `plugin` the loader set (`textprep/plugins.py:121`); built-ins have none, and a runner made with other steps keeps them (T3). The web path builds `JobSettings` without `plugins`, so the server always runs with plugins on, as planned (follow-up #688). The audio job recomputes the script on each run (the resume reuses chunks by text), so switching plugins between a paused run and its resume cannot reuse a script made the other way.
- **(4) Record.** `audio.json` gets `plugins` only when `result.run.plugins` is non-empty, `"version": 1` unchanged; `read_audio_record` (`web/player.py:342-356`) reads named fields only, so the 1.4.0 player loads records with and without the key (T10). Plugins off: `settings.plugins` false and no list, because `steps_for` returns a plain tuple without `InstalledSteps.plugins`.
- **(5) Report and CLI.** Markdown and CLI line "Text-step plugins: switched off for this job." only when `report.settings["plugins"] is False`; JSON report `settings.plugins` false only then. `convert --with-script` writes the report with the same settings.
- **(6) Plan tests.** T1 to T11 exist under the promised node IDs and pass; T2 (`convert`, fake voice, real ffmpeg) takes 0.71 s; T1 0.18 s; T8 to T10 under 0.8 s each. The one changed existing test (`test_the_file_keeps_every_setting_but_the_chosen_chapters`) now also excludes `plugins`; correct by the plan, and T7 pins it.
- **(7) Local run** (worktree at 13ec9c2, macOS): ruff, ruff format (384 files), lint-imports (3 kept, 0 broken), deptry green; `pytest -m "not slow and not benchmark and not browser" -k "not espeak"`: 8597 passed, 6 skipped, 6 xfailed, 0 failed (570 s).
- **(8) Layers.** No new import in `app` (the runner reads the `plugin` attribute); `cli_helpers.py` imports `TextStep` from `sci2audio.textprep`; no stage imports `app`.
- **CI.** Linux PR run: everything required green, `CI passed` green. Three-system `ci:full` run 44791741669 on 13ec9c2: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, Chromium shards, lint and layers, licences, security all success.
- **Comments.** The two new code comments (`audio.py:878`, `job.py:168`) say why; no narrating comment.

## Should fix

**S1. `--no-plugins` still imports every installed plugin and runs its factory.** `cli.py:141` makes the runner with `field(default_factory=JobRunner)` when `CliEnv.real()` is built, before the arguments are read, and `JobRunner.__init__` calls `installed_steps()`, which runs `point.load()` and the plugin's factory (`textprep/plugins.py:197-206`), without a time limit. Probe (real `CliEnv`, one counted entry point): `sci2audio script --no-plugins` exits 0 with the built-in reading ("Salt & pepper"), and the counter shows the entry point loaded once. Failure scenario: a person suspects a plugin whose import hangs, calls `os._exit` or segfaults, or reaches the network or the disk at import; `--no-plugins` cannot rule it out, because that code still runs on every command. PR A's privacy page (D-847) is to name this switch beside "plugins run unsandboxed"; as built, the switch keeps plugin steps out of the job but not plugin code out of the process. Fix at the root: let the CLI make its runner lazily and, under `--no-plugins`, from the built-in steps only (e.g. `CliEnv` holds a runner factory, or `None` and the command builds `JobRunner(BUILT_IN_STEPS)` when `--no-plugins` is given and no runner was injected); keep `steps_for` for the server's long-lived runner. Test: with `--no-plugins` an injected entry point's `load` is never called, and without the flag it is. If the coordinator prefers to defer, an Issue (v1.4, lane:app, risk:high) before PR A's privacy text is written, and that text must then say the plugins are still loaded.

**S2. The `KEPT` comment is now wrong.** `src/sci2audio/app/config.py:27` says "every JobSettings field but the chosen chapters"; `plugins` is now a field that is not kept either. Change it to name both (one line, lane:app).

## Notes

- **N1.** `docs/plugins.md` is outside plan §2's file list. The one added bullet is true for the code (the record lists the plugins when at least one ran) and lives in the lane CHANGELOG already needs; accepted.
- **N2.** `run_script`/`run_audio` with explicit `steps=` and `settings.plugins` false run the given steps unfiltered, while the report and record say plugins were off (and `audio.json` could then hold both `settings.plugins: false` and a `plugins` list). No caller passes `steps=` today; PR A's read-along must not pass plugin steps with plugins-off settings.
- **N3.** `convert --no-plugins` prints no confirmation line; `convert` prints no plugin line when on either (pre-existing), and the choice is in `audio.json` and, with `--with-script`, in the report. The plan's "the CLI prints one line" is met for `script`; accepted.
- **N4. Firefox failure judged unrelated.** `browser (Linux, firefox, 2/2, reported only)` failed once: `test_flow.py::test_resume_of_a_paused_replace_never_asks_to_replace_again[firefox]`, `hold.reached.wait(30)` at line 305 (the third chunk of the replace run never reached the fake voice within 30 s); 96 other tests of the shard passed, and the test passed in Chromium and WebKit on the same head. The flow goes through `JobRunner.run_audio`, which the PR touches, but with plugins on (the server never sets `plugins`, and no plugin is installed in CI) `steps_for` returns `self.steps` unchanged and the record and settings carry no new key, so the code path is the same as on `main`. No earlier failure of this test in the last 30 CI runs and no Issue for it: first occurrence, so no quarantine yet; if it fails again without a code cause, D-374 applies.
- **N5.** Before merge: the round-2 fix commit needs Linux CI green; as a critical PR, a three-system run on the final head (CRIT-02, D-580), checking `tests (macos-latest)` and `tests (windows-latest)`; merge `main` in if behind (no rebase).

## Handoff (THR-07)

- Goal: PR #689 (B-W2 PR B) to merge, then PR A.
- Done: round 1 at 13ec9c2, changes requested (S1, S2).
- Next: round 2 on the author's fix commit; check S1's test (no plugin load under `--no-plugins`) and S2.
