# PR #90, review round 1: answers

Pushed as **516546c** on `app/issue70-script-job` (no force-push). The branch is up to date with `main` (061e4e3). Fast suite: **965 passed** (11 new). `ruff check`, `ruff format --check`, `lint-imports` (2 contracts kept) and `deptry src` are clean. Nightly Hypothesis on `test_app_script.py`, `test_app_chapters.py`, `test_app_settings.py` and `test_app_report.py`: **88 passed**. Before applying the fixes I checked the new tests against the old code: 8 of them failed there, and all of them pass with the fixes.

## Findings

**F1: fixed.** `files.write_texts`: without `overwrite`, if a rename fails (a target appeared during the run), the targets this call already renamed are removed again. They did not exist before, because the hard link or rename refuses an existing file, so nothing of the person's is deleted. Without `overwrite`, the outputs therefore go in place all or none. With `overwrite`, I chose the docstring over backups. It now says that a rename failing after earlier ones succeeded cannot be undone. Reason: that happens only after every file was written in full on one file system, and backups would add a third name per file for a case we do not expect. Tests:
- `test_an_output_that_appears_during_the_run_is_not_replaced` now asserts that only `note.pdf` and the foreign `note.report.json` remain.
- New `test_without_overwrite_the_outputs_are_put_in_place_all_or_none`, for each of the three outputs appearing. Only the source and the foreign file remain, and a second run is not refused afterwards.

**F2: fixed.** `load_settings` also catches `RecursionError`, and `ValueError` in general (`JSONDecodeError` is one). It falls back to the defaults with "the settings file is damaged (nested too deeply); using the defaults". New test `test_a_deeply_nested_file_gives_the_defaults_and_a_warning` uses 100,000 `[` followed by `]`.

**F3: fixed.** The property draws its cases from a new strategy, `chaptered`:
- 2 to 12 blocks with two to five top-level sections. Front text exists whenever the first section doesn't start at block 0.
- The choice comes from the document's own chapter indices. A per-chapter coin is drawn, and an all-or-nothing draw is mostly turned into a partial one. Sometimes the choice includes an index the document doesn't have, and sometimes it is the default.
- 2 to 8 edits per case: removals, replacements and pauses. The built-in furniture step also runs, so set-aside outcomes occur.

The old generic case (`documents()` with any choice) is kept as `test_the_chapter_choice_holds_on_any_document`. Both share one check function.

Density, measured with a throwaway probe over 500 examples on the same derandomised settings as the `ci` profile (the probe is not committed):

| | before | now |
|---|---|---|
| more than one chapter | 146 | 500 |
| partial choice | 2 | **466** (93 %) |
| accepted edits in both a chosen and an unchosen chapter | 1 | **243** (49 %) |
| an accepted edit in an unchosen chapter | 21 | **365** (73 %) |
| default choice (None) | | 23 |
| an unknown index | | 34 |

**F4: fixed.** `run_script_job` refuses an output or working folder that is a file, or lies under a file, **before any work**, with `JobError("outfile is not a folder; choose another output folder")`. A folder that becomes a file during the run gets the same message from the `mkdir` step, which now has its own error handling ahead of the `FileExistsError` branch. Neither case is an `OutputExistsError`. New tests:
- `test_an_output_folder_that_is_a_file_is_refused_before_any_work`: the output folder is a file, the output folder lies under a file, and the working folder lies under a file. No progress phase runs in any of them.
- `test_an_output_folder_that_becomes_a_file_during_the_run_is_named`.

## Nits

**N1: fixed.** The `script_text` docstring now says the script is for people: an utterance reading "[pause]" or starting with "# " looks like a pause or a heading there, and programs read the report JSON and the job's data.

**N2: declined for now.** "Applied" stays. No built-in v1.0 step may propose `ask` (D-105), so in v1.0 every accepted edit changes what is heard. When UC-04 brings `ask` edits (v1.1), the count should split. I did not file an issue because UC-04's own issue will change the report anyway. I can file one if you'd rather track it.

**N3: fixed.** Only the integer 1 counts as version 1 (`type(version) is int`). New test `test_only_the_number_1_is_version_1` covers true, 1.0, "1" and null; each gives the version warning.

## Out of scope

#91 (the cutter splits inside `(2022)[p. 8]`) needs nothing in this PR, as the review says.
