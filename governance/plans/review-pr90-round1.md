# Review of sci2audio PR #90, round 1 (script job, #70)

Reviewed head: ffb37de (a2b2453 + merge of main 450d6a6 + the Windows test fix). Reviewer thread "Review script job PR", 12 Nov 2026.

**Verdict: changes needed.** Three must-fix items and one should-fix. The design matches the approved plan and all 12 decisions; nothing below changes D-129 to D-140 in substance (F1 tightens how D-136 is implemented, F2 makes the code meet D-139 as written).

## What I ran

- `uv sync`, then `uv run pytest -m "not slow and not benchmark"`: **954 passed, 31 snapshots passed** (26 s, xdist).
- `ruff check`, `ruff format --check`, `lint-imports` (2 contracts kept), `deptry src`: all clean.
- Nightly Hypothesis profile on `test_app_script.py`, `test_app_chapters.py`, `test_app_settings.py`, `test_app_report.py`: **82 passed** (64 s).
- Planted imports: `import sci2audio.testing` in `app/job.py`, `cli.py`, `web/__init__.py`, and `import sci2audio.app` in `textprep/runner.py`. Every plant gives BROKEN. Files restored.
- CI on ffb37de: green on Linux, macOS and Windows, plus lint, licences, security, CodeQL. (The first run on 450d6a6 failed on Windows: the fault test built folder keys with `\`. ffb37de switches to `as_posix()`. That is a correct test fix and weakens nothing.)
- Licence: platformdirs 4.14.5 metadata says `License-Expression: MIT`, with no Requires-Dist. It already sat in `uv.lock` as an indirect dependency; the lock diff only adds it as a direct one. The `THIRD_PARTY_LICENSES.md` row is present.
- PR body: `Closes #70` is meant to close the issue. The KB PR is referenced with "see" and a plain link, with no closing keyword near any PR link.

## Plan and decisions: checked against the code

| Decision | Where | OK |
|---|---|---|
| D-129 steps on the whole document, chapter filter at cutting, unchosen edits `spoken: false` | `script.prepare_script`, `report._edit` | yes |
| D-130 chapter = top-level section, runs to the next one; deeper top-level sections count | `chapters.find_chapters` (uses `Document.sections`, the top level of the tree) | yes |
| D-131 front chapter title from metadata, else file stem | `chapters.document_title` | yes ("Untitled" as a last fallback when neither has text: fine) |
| D-132 references by title, one `REFERENCE_NAMES` table, EN + DE, appendices never | `chapters.REFERENCE_NAMES`, `is_reference_title` | yes (DE adds Quellen and Quellenverzeichnis to the plan's list: fine) |
| D-133 selection by index, unknown ignored with a warning | `chapters.selected`, `report.build_report` warnings | yes |
| D-134 report JSON `sci2audio-report` v1 + Markdown | `report.report_data`, `report_markdown` | yes |
| D-135 script one utterance per line | `report.script_text` | yes. Checked on all 7 papers: body lines = utterance count, and no utterance has a line break (the cutter collapses white space). The heading is `# n. title`, not the plan's `# title`; the PR body says so. Not a change in substance. |
| D-136 `<stem>.script.txt/.report.json/.report.md`, overwrite only with `overwrite=True`, checked first | `job.script_files`, `run_script_job` | yes, but see **F1** |
| D-137 `job.json` `sci2audio-job` v1 in the working folder | `job._record` | yes; no machine paths |
| D-138 one job per `JobRunner`, `JobBusyError`, phase callbacks | `job.JobRunner` | yes. The phases are reading, layout, text-steps, writing and done; the plan's separate "cutting" phase is part of text-steps. Not a change in substance. |
| D-139 platformdirs settings.json, chapters not saved, broken file never stops start-up | `config.py` | **no, see F2** |
| D-140 JobError only when it cannot go on | `run_script_job` | yes |

## Golden snapshots: spot-checked against the PDFs

- Chapter lists for all 7 papers equal plan §3 (the corpus test pins them).
- hardt: the title, "We test a series of GPT-3 models…" (p. 1), "8 Limitations" (p. 5) and "A.1 Sample Instantiations" (p. 6) are all found on those pages with pypdfium2. Printed page labels 39 to 47 match the footer "pages 39–47". The References chapter is deselected and its page-5 page number is reported as "not spoken (chapter not chosen)".
- seaborn: the front chapter is titled "seaborn: statistical data visualization", which is the PDF's metadata Title. "seaborn is a library…" (p. 1) and "Unlike many graphical libraries…" (p. 3) match. The sidebar furniture (DOI, Review, Repository…) is left out.
- Remaining "lan- guage" style hyphens and figure-inside text are #65 and #64 and are expected to change these snapshots.
- One cutter defect is visible in the hardt snapshot: `Kocijan et al. (2022)[p.` / `8], “Solving…` is cut inside the citation. The cause is in the #63 cutter, not in this PR, so it is **filed as #91** (https://github.com/dubidu22/sci2audio/issues/91). No change is needed in this PR.

## Findings

### F1 (must fix): an output that appears during the run leaves a half set of outputs

`files.write_texts` renames the partial files one by one. With `overwrite=False`, if the 2nd or 3rd target appeared during the run, the 1st is already renamed into place. Reproduced: a `note.report.json` created during WRITING gives `OutputExistsError`, and the folder then holds a **new `note.script.txt` with no reports from this run**. A second run without overwrite then refuses because of that script file. The test `test_an_output_that_appears_during_the_run_is_not_replaced` only checks the report file and the absence of `.partial` files, so it misses this.

Fix: when `overwrite` is false and a commit fails, remove the targets this call already committed. They did not exist before (the link or rename refused an existing file), so removing them deletes nothing of the person's. Extend the test to assert that only `note.pdf`, the foreign `note.report.json` and no other output remain. With `overwrite=True`, a rename that fails half-way cannot be undone without backups; say that in the `write_texts` docstring, or keep the old files under a backup name until all renames succeed (author's choice; say which).

### F2 (must fix): a deeply nested settings file stops start-up

`load_settings` catches `JSONDecodeError` only. A file of 100,000 `[` followed by `]` raises `RecursionError` out of `json.loads` (reproduced). D-139 says a broken file never stops start-up. Fix: also catch `RecursionError` (and `ValueError` in general) and fall back to the defaults with the "damaged" warning. Add a test.

### F3 (must fix): the main Q6 property hardly tests what it claims

`test_cutting_the_chosen_chapters_equals_cutting_all_and_dropping_the_rest` draws the choice as `st.frozensets(st.integers(0, 8))` and the document from `documents()`, independently. I counted 500 examples under the `ci` profile with a throwaway probe:

- 146 had more than one chapter.
- **2** had a partial choice (some chapters chosen, some not).
- **1** had edits in both a chosen and an unchosen chapter.
- 21 had an edit in an unchosen chapter.

So the claim "they equal cutting the whole script and dropping the other chapters", and the `spoken` rule, are exercised in well under 1% of runs. Fix: build the document first, then draw the choice from its real chapter indices (`st.sets(st.sampled_from(range(n)))`, plus some unknown indices). Bias toward two or more top-level sections, for example a strategy that adds a section tree to the drawn blocks. Report the new density in the reply (aim for most examples having a partial choice).

### F4 (should fix): an output folder that is a file gives a misleading message

With `output_folder` pointing at an existing file, `mkdir(parents=True, exist_ok=True)` raises `FileExistsError`, and `_write` turns it into `OutputExistsError("outfile appeared during the run; choose to replace it")` (reproduced). Choosing to replace cannot help. Fix: make the folders before the `FileExistsError` branch, or handle their errors on their own, as `JobError("<name> is not a folder")`. Add a test.

### Nits (no change required)

- N1: a script line that starts with `# ` or reads `[pause]` cannot be told apart from a chapter heading or a pause in `script.txt`. The JSON is the format for machines, so this is fine; one sentence in the `script_text` docstring saying that the script is for people would settle it.
- N2: `CategoryCount.applied` also counts accepted `ask` edits, which are read as printed. The Markdown says "Applied". Consider "Accepted" later. No change needed now.
- N3: `{"version": true}` in settings.json passes as version 1 (`True == 1`). Harmless.

## Out of scope, filed

- #91: the cutter splits after an abbreviation glued to a bracket (`(2022)[p. 8]`), code from #63.

## Next round

Answer each of F1 to F4 as fixed (and how), deferred (with an issue) or declined (with a reason), and N1 to N3 the same way, item by item. I will re-run the fast suite, the nightly profile and the probes for F1 to F3.
