# Plan: batch B-W2, the interface and the jobs know the text-step plugins (#666, #668, #685, #667, #669)

Thread: web/app lane implementation, Opus 5.5 high. Status: **proposal, waits for the coordinator's approval** (both PRs are critical, see §3). No code or tests before approval (PLAN-01).

Sources read: main caecf7a: `app/runner.py`, `app/job.py` (`settings_data`), `app/audio.py` (`_record`), `app/report.py` (plugins in the report), `cli.py` (COMMANDS: `script`, `convert`, ...), `textprep/plugins.py` (`InstalledSteps`, `PluginInfo`, `installed_steps`), `web/player.py` (`build_view`, `joined_hyphens`, `player_for`, `read_audio_record`), `web/pages.py` (listen route), `templates/document.html`, `templates/privacy.html`, `strings/en.toml`, `tests/unit/example_text_plugin.py`, `tests/unit/test_textprep_plugins.py`, `tests/unit/__snapshots__/` (file list); issues #666, #668, #685, #667, #669; audit `plans/audit-batch-2026-11-20.md` F2 (and its META-03 proposal: plan tests carry node IDs, as below). No text-step plugin is installed in the dev environment (`entry_points(group="sci2audio.text_steps") == []`), so no corpus golden can move.

## 1. Order and who owns what

**The runner already exposes its steps:** `JobRunner.steps` is public. It is an `InstalledSteps` (built-in steps plus loaded plugins, with `.plugins` and `.problems`). #666 therefore needs **no app change**: `web` reads `state.runner.steps`.

**Recommended order: PR B (app) first, then PR A (web)**, branched from main after PR B merges. Two reasons:

1. **The privacy text in PR A (#685) can then be complete and true in one go.** It can say that a command-line job can run without plugins (`--no-plugins`, #667), and that uninstalling is the off switch for the interface. PR A cannot change that wording later without another web PR. With the other order, the page would first say "uninstall only" and need a fix right after.
2. **The read-along (#666) can then use the steps the audiobook was made with.** It reads the record's choice (#669 and #667 put it in the record): built-in steps only when the record says plugins were off, else the runner's steps. With the other order, an audiobook made with `--no-plugins` and opened in `sci2audio listen` would show plugin edits that were never spoken.

PR B is small, so the delay is short. **Alternative not chosen:** PR A first with "uninstall" wording only and the runner's steps unconditionally. It is possible (the files are disjoint), but it leaves both gaps above as follow-ups.

**File lists, disjoint:**

- **PR B:** `src/sci2audio/app/{settings,runner,job,report,audio}.py`, `src/sci2audio/cli.py`, `tests/unit/test_app_*.py`, `tests/unit/test_cli_*.py`, the CLI help snapshot `tests/unit/__snapshots__/test_cli_golden.ambr`, CHANGELOG.
- **PR A:** `src/sci2audio/web/{player,pages}.py`, `src/sci2audio/web/templates/{document,privacy}.html`, `src/sci2audio/web/strings/{en,de}.toml`, `tests/unit/test_web_*.py`, `tests/browser/test_plugins.py` (new), README privacy list, CHANGELOG.

## 2. PR B: `app: a job can run without text-step plugins and the audiobook names its plugins (#667)`

Closes #667 and #669. Labels `lane:app`, `lane:cli`, `risk:high`.

### #667: the switch

- **`JobSettings.plugins: bool = True`** (app/settings.py), checked like `subtitles`. It is not kept in `settings.json` (not in `KEPT`), like the chapters: it belongs to one job.
- **`JobRunner.run_script` and `run_audio`:** with `settings.plugins` false and no `steps` given, the job runs `self.steps` minus the steps a plugin added (those whose `plugin` attribute is set by the loader). A runner made with other steps keeps its own built-ins.
- **`settings_data()` writes `"plugins": false` only when off**, so every existing report, `job.json` and `audio.json` golden stays byte-identical. The JSON report's `settings` then holds the choice. The Markdown report and the CLI print one line: "Text-step plugins: switched off for this job."
- **`--no-plugins` on `script` and `convert`.** The issue says "audio"; the command is `convert`. Help text: "run only the built-in text steps, without installed text-step plugins".

### #669: the record

- **`audio.json` gets `"plugins": [{"step", "distribution", "version"}]`** when the job ran with at least one plugin, taken from `result.run.plugins`. With none, the key is left out, so the golden is unchanged. With plugins switched off, `settings.plugins` is false and no list is written.
- **Format version stays 1:** the key is an addition, and the 1.4.0 player ignores unknown keys (`read_audio_record` reads named fields only).

### Tests (PR B), written first

- T1: `--no-plugins` on `script` runs only the built-in steps and the report says so  -> `tests/unit/test_cli_script.py::test_no_plugins_runs_only_the_built_in_steps`
- T2: `--no-plugins` on `convert` (fake voice, real ffmpeg, a few seconds)  -> `tests/unit/test_cli_convert.py::test_no_plugins_makes_the_audiobook_without_plugins`
- T3: the runner drops only plugin steps  -> `tests/unit/test_app_job.py::test_plugins_off_drops_only_the_plugin_steps`
- T4: the report JSON and Markdown name the switch only when off  -> `tests/unit/test_app_report.py::test_the_report_says_when_plugins_were_switched_off`
- T5: `settings_data` leaves the key out when on (goldens unchanged)  -> `tests/unit/test_app_job.py::test_settings_data_names_plugins_only_when_off`
- T6: `JobSettings(plugins="no")` raises  -> `tests/unit/test_app_settings.py::test_plugins_must_be_true_or_false`
- T7: the switch is not kept in `settings.json`  -> `tests/unit/test_app_settings.py::test_the_plugin_switch_is_not_kept`
- T8: `audio.json` lists the plugins used  -> `tests/unit/test_app_audio_job.py::test_the_record_names_the_plugins_that_made_it`
- T9: without plugins the record has no `plugins` key  -> `tests/unit/test_app_audio_job.py::test_a_record_without_plugins_has_no_plugin_key`
- T10: the player reads a record with and without the key  -> `tests/unit/test_app_audio_job.py::test_records_with_and_without_plugins_load_in_the_player`
- T11: the CLI help golden gains the two `--no-plugins` lines  -> `tests/unit/test_cli_golden.py::test_command_help_text` (snapshot update, diff explained in the PR)

The plugin in tests is `tests/unit/example_text_plugin.py:AmpersandStep`, loaded through `installed_steps(entry_points=[EntryPoint(...)])`. No network; no real installed package.

### Rough size

About 60 lines of code and 250 of tests.

## 3. PR A: `web: the read-along, the document page and the privacy page know the text-step plugins (#666)`

Closes #666, #668 and #685. Labels `lane:web`, `lane:docs` (README), `risk:high` (#685).

### #666: the read-along

- **`player_for(..., steps=...)` passes the steps to `build_view`; `joined_hyphens(document, switched_off, steps=BUILT_IN_STEPS)` gets a `steps` parameter.** The listen route passes `state.runner.steps`. When the record says `settings.plugins` is false, it passes the runner's built-in steps only (`AudioRecord` gains `plugins_on: bool`, read from the record, default true for older records).
- No read-along golden changes: no plugin is installed, so `runner.steps` equals the built-in steps.

### #668: the document page

- **The page lists the plugins from the report's `plugins`:** a callout "Text-step plugins this analysis ran with:" with one item per plugin, `id (distribution version)`. When the report says plugins were off: "Text-step plugins were switched off for this analysis." Nothing when the report has neither, as today.
- The plugin ids and distributions are shown as `lang="en"` code text, escaped by Jinja.

### #685: the privacy page

A new point, "Text-step plugins", in English and German:

- An installed Python package can add a text step through the `sci2audio.text_steps` entry point.
- A plugin runs inside sci2audio with the program's rights. It reads the text of each document and proposes edits, which the report lists. Like any installed Python package, it could use the network or read files.
- sci2audio does not sandbox plugins or check what they do. Each job's report and the document page name every plugin it ran with.
- A command-line job can run without them (`--no-plugins`). For the interface, uninstalling the package switches a plugin off.

Then the live part, from `state.runner.steps.plugins`: "Installed now: id (distribution version), …" or "No text-step plugins are installed." The `local` point gains "…; installed text-step plugins are other people's code, see below." The README privacy list gets the same sentence.

### Tests (PR A), written first

- T12: `build_view` with the plugin step marks the plugin's accepted edit  -> `tests/unit/test_web_player.py::test_the_read_along_uses_the_plugin_steps_it_is_given`
- T13: `joined_hyphens` uses the steps it is given  -> `tests/unit/test_web_player.py::test_joined_hyphens_takes_the_steps_it_is_given`
- T14: the Listen page uses the server runner's plugin steps (fake voice, real ffmpeg)  -> `tests/unit/test_web_player.py::test_the_listen_page_uses_the_servers_plugin_steps`
- T15: an audiobook recorded with plugins off shows only built-in edits  -> `tests/unit/test_web_player.py::test_an_audiobook_made_without_plugins_shows_no_plugin_edits`
- T16: an older record without the key reads as plugins on  -> `tests/unit/test_web_player.py::test_an_older_record_reads_as_plugins_on`
- T17: the document page lists id, distribution and version  -> `tests/unit/test_web_pages.py::test_the_document_page_lists_the_plugins_that_ran`
- T18: the document page says when plugins were off, and says nothing without plugins  -> `tests/unit/test_web_pages.py::test_the_document_page_says_when_plugins_were_off`
- T19: the privacy page lists the installed plugins from the runner, or says none  -> `tests/unit/test_web_languages.py::test_the_privacy_page_names_the_installed_plugins`
- T20: D-293 check-against-code: the plugin point is in both tables and names the entry-point group from `PLUGIN_GROUP`, the switch's flag from `cli.py`, "network" and "sandbox"  -> `tests/unit/test_web_languages.py::test_what_the_privacy_page_says_is_what_the_code_does`
- T21: the document page with a plugin, in a browser, passes axe  -> `tests/browser/test_plugins.py::test_the_document_page_lists_its_plugins_and_passes_axe`
- T22: the privacy page with a plugin installed passes axe, in English and German  -> `tests/browser/test_plugins.py::test_the_privacy_page_names_the_plugin_and_passes_axe`
- Existing coverage: `test_web_languages.py::test_every_page_in_german` and `::test_every_string_used_is_in_both_tables_and_every_string_is_used` cover the new strings; no `--snapshot-update` in PR A.

### Rough size

About 70 lines of code, 40 of templates, 30 of strings, and 300 of tests.

## 4. Criticality and checks

- **PR B is critical** (CRIT-01, golden file): the CLI help snapshot changes. That is the only golden it touches.
- **PR A is critical** because of #685 (`risk:high`, privacy text about the network).
- **Both get:** Linux CI green, then main merged in (merge commit), then `ci:full` three-system green, reported, label removed, then review.
- **Before each PR:** the fast checks from `CLAUDE.md` locally with `-k "not espeak"`. PR A also runs `uv run pytest -m browser`.

## 5. Follow-ups (issues only if the coordinator wants them)

- A "run without plugins" switch in the interface's check form (web), mirroring `--no-plugins`.
- The privacy page could link each plugin to its package's metadata page.

## Handoff (THR-07)

- Goal: B-W2 as two PRs, B then A.
- Done: plan.
- Next: the coordinator's approval and the order; then PR B, tests first.
