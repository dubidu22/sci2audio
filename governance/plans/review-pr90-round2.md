# Review of sci2audio PR #90, round 2 (script job, #70)

Reviewed head: 516546c (round 1 fixes on top of ffb37de). It is up to date with main 061e4e3 (0 behind). Answer: /mnt/project-files/plans/review-pr90-round1-answer.md.

**Verdict: passes. Ready to merge.**

## Re-checked

- **F1, fixed.** My round-1 probe (an output appears during WRITING) now leaves only `note.pdf`, the foreign `note.report.json` and the working folder. Before the fix it also left a new `note.script.txt`. Rollback runs only when `overwrite` is false, and only on targets this call committed. The overwrite limit is documented in the `write_texts` docstring. I accept that choice.
- **F2, fixed.** 100,000 nested `[` now give the defaults and "the settings file is damaged (nested too deeply)". Before the fix, a RecursionError escaped.
- **F3, fixed.** I ran my own density probe on the new `chaptered` strategy (500 derandomised examples): 436 have a partial choice and 231 have an edit in an unchosen chapter. Before the fix the counts were 2 and 21. The old generic case is kept as `test_the_chapter_choice_holds_on_any_document`, and the built-in steps now run inside the property too.
- **F4, fixed.** An output folder that is a file now gives `JobError("outfile is not a folder; choose another output folder")` before any work. A folder that becomes a file mid-run gets the same message. Neither is an `OutputExistsError`.
- **N1 and N3, fixed.** N1 is now a sentence in the `script_text` docstring; N3 counts only the integer 1 as version 1.
- **N2, declined.** The reason holds: no v1.0 step may propose `ask` (D-105), and UC-04 will change the report anyway. No issue is needed.

## Ran

- Fast suite: **965 passed, 31 snapshots passed**. Snapshots are unchanged by the fixes.
- `ruff check`, `ruff format --check`, `lint-imports` (2 contracts kept), `deptry src`: all clean.
- Nightly Hypothesis on `test_app_script.py`, `test_app_chapters.py`, `test_app_settings.py`, `test_app_report.py`: **88 passed**.
- CI on 516546c: every job is green on Linux, macOS and Windows, plus lint, licences, security and CodeQL.

No decision D-129 to D-140 changes in substance.
