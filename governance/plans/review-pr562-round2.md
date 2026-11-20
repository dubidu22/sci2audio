# Review PR #562 round 2 (final round, critical)

Fix commit reviewed: 38b7717cd7d4c1b5733c1799b03a0bd3ded589ab (Linux CI green). Answer: plans/answer-pr562-round1.md.

## Verdict: APPROVED, merge after the three-system run on b88c7e2

- M1 fixed as given: map error asked first; docstring says so; new test `test_a_page_whose_characters_pdfium_maps_never_looks_at_a_font_program` kills the order mutant (checked).
- M2 fixed: the three test groups as listed (10 + 9 + 2 cases).
- Hand mutants again (plans/b1-review-mut562.py plus the order mutant; ROOT = PR worktree at 38b7717; tests `test_extraction_legibility.py test_core_content.py`; clean baseline 92 passed): 11 of 13 killed. Survivors: the embedded check and `bool(needed)`, both judged equivalent in practice in round 1 (N3).
- N2 wording changed to "hardly ever". N1, N3 no change.
- **Branch update (MRG-03):** main moved under this PR with #559 (56d937f), which changed `extraction/pdf.py` and `tests/unit/pdf_maker.py`, files this PR touches. Updated with update-branch (merge, no force-push): new head b88c7e2, identical in content to my local merge ccb303d. PR diff against main still the same 8 files (+787 −6). On the merged tree: legibility, pdf, core and pdf-process tests 213 passed; corpus, golden and snapshot tests 566 passed; #559's skew and inherited-rotate probes unchanged; a glyph-number page turned by /Rotate 90 still counts 34 of 34 characters.
- Final round (REV-03): `ci:full` added for the three-system run on b88c7e2. Merge pinned to b88c7e2 once "CI passed", tests (ubuntu, macos, windows) are green. A Windows failure of the flate-bomb test with WinError 0xE0000008 is the known bug fixed by #568, not this PR (REV-09).
