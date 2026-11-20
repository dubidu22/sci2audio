# Review of sci2audio PR #108, round 3

Reviewed head `d60f0dc` (7980a2a answers round 2; 8f340b9 merges main d30e6e7 with #66; d60f0dc fixes the snapshot).

- R2-1 fixed (7980a2a): both Ctrl-C tests wait with `wait_for_stopping` until the "stopping after the current sentence" line is on stderr (10 s limit) before going on, so they no longer depend on how fast a loaded machine handles `interrupt_main`. Locally 10 of 10 runs passed; the author reports 25 of 25 under CPU load.
- R2-2 done (7980a2a): `worker.start()` is inside the `try`; a Ctrl-C before the thread exists re-raises (nothing to stop politely), otherwise it is a first Ctrl-C. The author found the old order failing 1 in 20 under load, so this was real.
- Snapshot after #66 (d60f0dc): #66 changed seaborn chapter 5 from 45 to 44 sentences. The chapter-list snapshot now replaces the counts with `N sentences` and the test checks six positive counts outside it. The snapshot diff is exactly those six fields; numbers, marks, titles and the reference-list note stay pinned. Later text-step PRs won't touch it.

Local on `d60f0dc`: ruff, format, lint-imports (2 kept), deptry clean; fast suite with the ci profile 1576 passed, 53 snapshots passed; `test_cli_properties.py` and `test_cli_convert.py` with the nightly profile passed.

No decision of D-210 to D-226 changes in substance. Open follow-ups: #104, #112, #115, the checkbox on #73.

Verdict: approve once CI is green on Linux, macOS and Windows, including the smoke step.

## Merge of main after #76 (head `b207ce7`)

#76 (PR #107, 7767174) merged first, so #108 conflicted. The author merged main (no rebase or force-push). In cli.py, #76's `ui` is one more `Command` row with `add_ui` (`--no-browser`, #76's help text) and `run_ui_command`, which imports `sci2audio.web` lazily inside the command (D-207). `web.run` returns 0, wrapped in `Exit`. The help snapshots gain the two-line `ui` entry and a new `ui` command help. The property test samples `ui` and `--no-browser` and stubs `sci2audio.web.run` for the module. Nothing else of #108 changed. Local: ruff, format, lint-imports (3 contracts kept), deptry clean, fast suite with the ci profile 1729 passed.

CI on `b207ce7` was green on Linux, macOS and Windows, with the smoke step on all three. Squash-merged pinned to `b207ce7` as `b82eb66` (13 Nov 2026).
