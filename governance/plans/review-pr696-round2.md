# PR #696 review, round 2 (head 07f7e76)

Reviewer: review-web-b-w2, Opus. 20 Nov 2026. Plan: plans/web-b-w2-plan.md §3 (D-847), changed by D-852. Author's answer: plans/answer-pr696-round1.md (governance d5c100b).
Critical: **yes** (unchanged).
Verdict: **approved** (0 must-fix, 0 should-fix, 3 notes). Merge needs `main` (9066c3d or later) merged in, a green three-system run on that head, and the coordinator's go.

## Round 1 findings

- **M1 fixed per D-852.** `AudioRecord.plugins` (`player.py:317-319`) holds the step ids of the record's `plugins` list, empty without one; `player_for` (`player.py:1136-1138`) keeps the built-in steps (no loader `plugin` mark) and only the plugin steps whose id the record names. A malformed `plugins` value reads as a broken record (`PlayerError`). Tests: `test_a_plugin_installed_after_the_audiobook_shows_no_edit` (my probe: book made without the plugin, opened by a server with it → "Salt &amp; pepper", no `said` span); `test_a_record_without_a_plugin_list_uses_the_built_in_steps` (none → empty, a list → its ids, a non-list → broken); T14 and T15 still pass. Mutation: keeping every plugin step makes the new test fail.
- **M2 fixed.** `pages.py:1352` passes `plugin_problems` (the runner's `InstalledSteps.problems`); `privacy.html:29-33` lists each as `<code>name</code> (distribution): <span lang="en">reason</span>` under "Installed but not loaded (its code may still have run when sci2audio tried to load it):" / German equivalent; "No text-step plugins are installed." only when neither list has an entry. T19 extended with a failing entry point in both languages. Mutation: showing `plugins_none` whenever nothing loaded makes T19 fail.
- **S1 fixed.** Both tables: "Plugins are loaded once, when sci2audio starts." / "Plugins werden einmal geladen, wenn sci2audio startet.", the uninstall sentence names the restart ("and then restarting sci2audio" / "sobald Sie sci2audio neu starten"), the label is "Loaded when sci2audio started:" / "Beim Start von sci2audio geladen:"; README names the restart. T20 checks the restart words and the label.
- **S2 fixed.** No backtick left in `privacy.plugins` (both tables); T20 asserts it.
- **N1 done.** T20 builds a `CliEnv` and asserts `job_runner(JobSettings(plugins=False)).steps` is exactly `BUILT_IN_STEPS`. **N2, N3 noted**: accepted.

## Checks

- **Fix-commit diff 3ee16ee..07f7e76**: 8 files (README, `web/pages.py`, `web/player.py`, both string tables, `privacy.html`, `test_web_languages.py`, `test_web_player.py`), only the answers above; no app, stage or golden file.
- **Promised tests**: the PR body's section lists 12 node IDs (T12 to T22 with T16 renamed, plus the probe test); the 10 unit ones pass by node ID, the 2 browser ones in the browser run.
- **Local run** (fresh worktree /tmp/review-696 at 07f7e76, macOS): ruff, ruff format (387 files), lint-imports (3 kept, 0 broken), deptry green; fast suite `-k "not espeak"`: 8646 passed, 6 skipped, 6 xfailed, 0 failed; `pytest -m browser --browser chromium`: 198 passed, 5 skipped, 0 failed (axe on both plugin pages, English and German; request fence held).
- **CI on 07f7e76 (Linux)**: `CI passed`, governance pr checks, `tests (ubuntu-latest)`, lint and layers, licences, security, ZAP, CodeQL, both Chromium shards green; all four report-only Firefox and WebKit shards pass.

## Notes

- **N4.** `player_for`'s docstring (`player.py:1130-1132`) and the answer say a plugin "upgraded ... since shows no edit", but the match is by id only (as D-852 decided), so an upgraded plugin with the same id that now edits differently is still used. Either trim "upgraded" from the docstring when `main` is merged in, or open a follow-up Issue to match on id, distribution and version (the record holds all three). Not blocking: D-852 chose ids.
- **N5.** The template comment `{# ... (#696 M2) #}` and the test comments "(#696 S1)", "(#696 S2)" cite review findings; the sentences say why, so not a narrating-comment finding; "(#685)" would do.
- **N6.** `test_web_languages.py` imports `BUILT_IN_STEPS` twice (module level as `BUILT_IN`, again inside T20); harmless.

## Handoff (THR-07)

- Goal: PR #696 (B-W2 PR A) to merge.
- Done: round 2 at 07f7e76, approved.
- Next: author merges `main` in and runs `ci:full`; on the coordinator's go, verify the merge commit holds no conflict resolution, gate, check `tests (macos-latest)` and `tests (windows-latest)`, squash-merge pinned to that head.
