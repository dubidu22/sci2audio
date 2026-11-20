# Review of PR #547 (#488 German "et al.", #477 English initials and "U.S."), round 2 (final)

Reviewed: fix commit **78fc5d0** (on d761e40). Merge head after my merge of main c3b79c2 (#528): **08061b5**.

**Verdict: APPROVED, 0 new findings.** The merge waits for the three-system run on 08061b5.

## Round 1 findings
- **B1 fixed.** The 9 words ("He", "Her", "An", "So", "To", "On", "Or", "Still", "Even") are gone from `data/en/sentence_openers.toml`, exactly those and nothing else, and the header says why. New row `an-initial-before-a-surname-that-is-also-a-function-word-ends-no-sentence` reads two utterances, one per sentence. The list test asserts none of the 9 is in the list. The body states the D-744 gate re-run: no unlisted error, known errors unchanged, floors held, every row and all corpus snapshots unchanged.
- **N1 fixed.** The body names prepositions and question words as beyond P2.3, with the reason ("the U.K. In both", "in the U.S. In 2019").

## Final-round checks
- **Shapes (my battery, main c3b79c2 → 78fc5d0).** All 8 surname sentences read exactly as on main (whole). The 41 shapes: every round 1 gain is kept ("U.S. Census Bureau", "U.S. (n = 12)", "U.S. FDA", "U.S. Army", "H.R. 1234 the U.S. Congress" whole; "called A. | Then", "vitamin A. | However", "Vitamin C. | As", "letter E. | Its", "J. A. | In:", "N. | The" cut; German "et al." whole). No shape lost a cut that round 1 gained.
- **Mutation.** 12 of 12 killed: the 8 round 1 mutants of `utterances.py`, and 4 that put a removed word back ("He", "An" killed by the new row; "Still", "On" killed by the list assertion).
- **Nightly seeds** (HYPOTHESIS_PROFILE=nightly) on utterances, sentence boundaries, units/abbreviations and both regression files: seeds 555, 8080 and 31337, 1473 passed each.
- **Merge of main.** Clean, no snapshot conflict. `git diff origin/main 08061b5` and `git diff 712ec4c 78fc5d0` differ only in index and hunk-header lines; every changed line is the same. Ruff clean; fast suite on 08061b5: 7076 passed, 3 skipped.
- **Linux CI** on 78fc5d0 is green. **Three-system run:** `ci:full` added on 08061b5.

## Note, no action (from round 1)
German second run of "Das zeigen Müller et al. (2019). Die Studie ist neu." loses its cut; the words are the same (D-577). Same class as #482.

## Merge
Squash-merge pinned to 08061b5 once `CI passed`, `tests (macos-latest)` and `tests (windows-latest)` are green on it, after grepping commit messages for closing keywords. The squash message closes #488 and #477.
