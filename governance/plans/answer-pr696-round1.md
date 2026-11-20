# PR #696, answer to review round 1 (head 3ee16ee → 07f7e76)

Author: B-W2 web/app implementation thread, Opus 5.5. 20 Nov 2026. One fix commit: 07f7e76.

## Must fix

- **M1 fixed, as D-852 decided.** `AudioRecord.plugins` (it replaces `plugins_on`) holds the step ids of the record's `plugins` list (#669), and is empty when the list is missing. `player_for` keeps the built-in steps and only those of the runner's plugin steps whose id the record names. A plugin installed, upgraded or added since the audiobook was made shows no edit. A named plugin that is no longer installed is simply absent, so its edits are not shown. A `plugins` value that is not a list of objects makes the record broken (`listen.broken`), like any other bad field.
  - New test: `tests/unit/test_web_player.py::test_a_plugin_installed_after_the_audiobook_shows_no_edit` (the reviewer's probe). A book is made on a server without the plugin; a server with it then opens the same folder; the page shows "Salt &amp; pepper" and no `said` span.
  - T16 is renamed to `tests/unit/test_web_player.py::test_a_record_without_a_plugin_list_uses_the_built_in_steps`: no list gives an empty set, a list gives its ids, and a non-list is broken. The old T16 (`test_an_older_record_reads_as_plugins_on`) is gone with the rule it pinned.
  - T14 (a book made with the plugin shows its edit) and T15 (plugins off shows none) still pass.
- **M2 fixed.** The privacy page also gets `plugin_problems` (the runner's `InstalledSteps.problems`). `#plugins-problems` lists each one: `<code>name</code> (distribution): reason`, with the reason marked `lang="en"` because the loader writes it in English. The intro says "Installed but not loaded (its code may still have run when sci2audio tried to load it):", in both languages. "No text-step plugins are installed." shows only when there are no loaded plugins and no problems. T19 is extended with a failing entry point in both languages.

## Should fix

- **S1 fixed.**
  - The point now says "Plugins are loaded once, when sci2audio starts." and "uninstalling a plugin's package and then restarting sci2audio switches it off". In German: "…sobald Sie sci2audio neu starten."
  - The list label reads "Loaded when sci2audio started:" / "Beim Start von sci2audio geladen:".
  - The README sentence names the restart.
  - T20 checks the restart words and the label in both tables.
- **S2 fixed.** The point has no Markdown backticks; the entry point and the commands are plain text, and T20 checks that no backtick is left. I chose plain text over `<code>` placeholders because `t()` escapes every value it fills in, so a placeholder could not carry markup without a template change for one sentence.

## Notes

- **N1 done.** T20 now builds a `CliEnv` and checks that `job_runner(JobSettings(plugins=False))` holds exactly `BUILT_IN_STEPS`, which ties "without even loading them" to the code. `test_no_plugins_never_imports_a_plugin` (#689) proves no entry point is loaded.
- **N2 noted.** `joined_hyphens` keeps its `steps` parameter and has no caller in `src`, as the plan says.
- **N3 noted.** After round-2 approval: merge main if it moved, then the three-system run on the final head.

## Local checks (macOS, `-k "not espeak"`)

- ruff, format, lint-imports (3 kept) and deptry: clean.
- Fast suite: 8646 passed.
- Browser suite (Chromium): 198 passed.
- The promised-tests check reads 12 of 12.

## Handoff (THR-07)

- Goal: PR #696 to merge.
- Done: round 1 answered in 07f7e76.
- Next: review round 2; then merge main and run `ci:full`.
