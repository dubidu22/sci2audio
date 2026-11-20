# Review of sci2audio PR #94 (issue #64), round 1

Reviewed head a9d10f3, 13 Nov 2026. Plan: `plans/issue64-placeholders-footnotes-plan.md`; decisions D-142 to D-148 (coordinator post 12 Nov 23:35:34Z), with D-146 widened to the five D-132 names.

**Verdict: changes needed (3 must-fix, 2 should-fix, 1 nit).** The textprep work itself matches the plan and the decisions. The problems come from main having moved: PR #90 (the script job, 660d21f) landed after the branch was cut, and the merge with it breaks the default behaviour of D-142 and five fast tests.

## What I checked and found right

- **Plan conformance:** six steps, registry order furniture → reference-list → formula-notices → table-figure-notices → footnote-texts → footnotes (Q15 coarse to fine). Categories, `on_by_default`, `DEFAULT_SWITCHED_OFF`, the runner default, one wording table, the reasons, and English-only steps except `footnote-texts` (D-147) all match.
- **Regression cases (golden):** the 12 new cases are the plan's list. The 14 audit cases are unchanged.
- **Corpus against the PDFs:** I rendered Nowak p. 4 (marks 7 and 8) and p. 10 (marks 9 to 12, the ones after "W.", "P," and "term:"). All are real footnote marks, and the `N³|N|³` exponents on p. 4 stay. The counts match the truth files: 51 formula notices (34 + 9 + 8), 27 table and figure notices, 39 marks for 39 labelled notes, and 41 introductions.
- **Layer check:** I planted `import sci2audio.layout` in each of footnotes.py, placeholders.py, references.py and wording.py, and `lint-imports` reported BROKEN each time. ruff, ruff format and deptry are clean.
- **Hypothesis:** the nightly profile on the textprep, regression, conformance and documents tests (branch merged with main) gave 293 passed. A density probe over 500 `rule_documents()` examples gave footnotes edits in 100%, footnote-texts 100%, table-figure-notices 47%, formula-notices 35%, reference-list 32% and page-furniture 38%.
- **CI on a9d10f3:** green on Linux, macOS and Windows. The branch is behind main, though, and see M1 and M2.

## Must fix

**M1. With main merged, the app leaves every footnote out by default (against Q2 and D-142).**
`app.settings.JobSettings.switched_off` defaults to `frozenset()`, and `app.script.prepare_script` passes it to `run_steps`. The runner's new default `DEFAULT_SWITCHED_OFF` is therefore never used by a job, and "Footnote texts" is on in every job. Evidence: on the merge, the hardt app report shows `Footnote texts | 2 | 0 | 0 | 0` (2 applied), and both introductions are set aside ("the remove edit of step footnote-texts ... won").
Fix: make `JobSettings.switched_off` default to `DEFAULT_SWITCHED_OFF`. A settings file without the key then gets the same default. Add a test that a default job reads each note with "Footnote 1." and that turning Footnote texts on (switched_off without it) leaves the notes out.

**M2. The fast suite fails on the merge with main: 5 failures.**
- `test_app_corpus.py::test_the_script_is_as_recorded` and `test_the_report_is_as_recorded`, for hardt and seaborn (4 snapshots). This is expected now that #64's steps run in the job. Regenerate `tests/unit/__snapshots__/test_app_corpus.ambr` after M1, and explain the diff in the PR, since it is a golden file (D-69).
- `test_app_script.py::test_the_built_in_steps_always_prepare_a_script` asserts that every edit is on a furniture block. Falsifying example: one footnote block whose text is `'\xa0'`, removed by `footnote-texts`. After M1 that step is off, but other #64 steps still edit non-furniture blocks. Narrow the test the way you narrowed the furniture corpus test, and say why in the PR.

Merge main into the branch (no force-push), then fix.

**M3. The reference-list step and the app's chapter choice disagree on titles (D-146 says both treat them the same way).**
This was also raised in the KB review of D-146. There are two tuples, `textprep.REFERENCE_TITLES` and `app.chapters.REFERENCE_NAMES["en"]`, with no test that keeps them equal. They also match differently. Probes on the merge:
- `"References:"`: the step reads the section, while `is_reference_title` deselects the chapter (it strips a trailing "." or ":").
- `"A.1 References"`: the step reads it, while the app accepts "A.1" as a number.
- The number patterns differ as well: `\d{1,3}` against `\d{1,2}`, `[IVXL]{1,6}` against `[IVX]{1,5}`, and letter-plus-subnumbers only in the app.

Fix: give the English names one source (the app may import textprep, but textprep may not import app), use the same matching in both (number prefix, case, trailing "." or ":"), and add a test that runs both on one shared list of titles. At least these: "References", "REFERENCES", "References:", "7 References", "7. References", "A.1 References", "IV. Bibliography", "Works Cited", "Results", "Notes".

## Should fix

**S1. A note printed "1. Text" or "1) Text" gets a stray mark.** Label "1" with text "1. Measured." reads "Footnote 1. . Measured."; "1) Measured." reads "Footnote 1. ) Measured." (probe on the merge). The corpus PDFs don't print notes this way, but EPUB and Markdown notes, and other PDFs, often do. Fix: when "." or ")" follows the label at once, take it into the replaced span. Add a unit test and a regression case.

**S2. Short caption labels are only expanded in one exact spelling.** "FIG. 3" (APS and PRL style) reads "FIG. 3 is skipped.", and "Fig.3" (no space) reads "Fig.3 is skipped.". D-145 says abbreviations are read in full. Fix: look up the label word without regard to case, and split a label word that a number follows without a space. Add unit tests. D-145 itself does not change.

## Nit

**N1.** `test_no_reference_list_is_read` finds sections with `s.title.strip() in REFERENCE_TITLES`: exact case, top-level sections only. After M3 there is one matcher, so use it there too. Otherwise the corpus test and the step can drift apart.

## Effect on the decisions

None of D-142 to D-148 changes in substance. M1 restores D-142 as written ("off by default"). M3 carries out D-146's "treated the same way". S1 and S2 implement D-144 and D-145 as worded.
