# Review of PR #528 (#487), round 2 (final)

Reviewed: fix commit **d5f9c01** (on 161f854). Tests only: `tests/regression/english.toml`, `tests/regression/german.toml`.

**Verdict: APPROVED, 0 new findings.** It merges after #524. Before the merge I merge main into the branch, confirm the PR diff is unchanged, and run `ci:full` on that head.

## Round 1 findings
- **S1 fixed.** Both "read as a paragraph" rows (en and de) carry a link in all three blocks. The links step removes it, and the expected text is updated ("…, data." / "…, Daten."). I re-ran the mutant on d5f9c01: the links step's old skip now fails `a-table-and-a-figure-read-as-a-paragraph-when-their-notice-is-off`.
- **S2 fixed.** New row `furniture-stays-as-printed-when-page-furniture-is-off`: with page furniture switched off, a running head holding a unit, an abbreviation, a citation and a link is read exactly as printed, and the paragraph beside it is read as usual. I re-ran the mutant on d5f9c01: disabling the furniture branch of `read_as_prose` now fails that row.
- **N1 fixed.** The body names both plan changes, P3.4 (8 PDFs, with my run on the other 5) and P3.1 (the notice-on corpus assertion), each with its reason.

## Final-round checks
- **Mutation:** 12 of 12 hand mutants killed on d5f9c01. That is the 10 killed in round 1 plus S1's and S2's.
- **Nightly seeds** (HYPOTHESIS_PROFILE=nightly) on `test_textprep_conformance.py`, `test_textprep_placeholders.py` and both regression files: seeds 555, 8080 and 31337, 1200 passed each.
- **Differential fuzz** (round 1): 2,700 texts, table and figure read alike with the paragraph; second-run changes are only ones the paragraph also has (#540, older).
- **Linux CI** on d5f9c01 is green.
- **Three-system run:** 161f854 was green. The final head after merging main gets `ci:full` before the squash.

## Merge
After #524 is merged:
1. Merge main into `textprep/notice-off-reading`. Regenerate the corpus snapshot if it conflicts; never hand-resolve it.
2. Check that `git diff origin/main HEAD` equals `git diff 96de4a3 d5f9c01`, and run the fast suite.
3. Push, run `ci:full`, and squash-merge pinned to that head with the message closing #487 only.
