# Light batch audit: textprep batch B6 (#616), 19 Nov 2026

Auditor: the B6 review thread (Opus high; the batch is one critical PR). Merged diff b6355cc~1..b6355cc (squash of #616, pinned 8655836), 13 files, +646 / −33.

## Contract touches
- No layer contract, core dataclass, text-step interface, snapshot, golden script or corpus truth file changes.
- Regression cases added (english.toml 1, german.toml 2) and the sentence gate's stress set grows by 5 own lines (CC0); `known-errors.toml` and floors unchanged. Critical, reviewed in 3 rounds.
- Harness: `sci2audio.testing.regression` gains `second_run` (factored from `read_twice`, same behaviour) and `cut_twice`; the D-577 script check is unchanged. New second-run cut check with 6 strict-xfail exceptions, each with its reason.

## Cross-file consistency
- `utterances._readings` now reads tables from four other textprep modules (`numbers.OUT_OF`, `numbers_de.FRACTIONS_OF_ONE`, `statistics.SYMBOL_READINGS`, `statistics_de.SYMBOL_READINGS_DE`); those modules only gained named constants, readings unchanged (fast suite and corpus identical). Imports are inside the cached function because of the import cycle through footnotes/links; lint-imports green (same layer).
- Minor (not blocking, no issue): `units.py` keeps its own `_OUT_OF` pattern with the literal "out of"; it could read `numbers.OUT_OF` too. Note for the next textprep batch that touches units.
- Module docstring of `utterances.py` matches the rules (same-word rule, rank 5, its limit #613). CHANGELOG has one Unreleased line (D-768); #533 is tests only, no line.

## Follow-ups (all open, v1.2.x, lane:textprep)
#613 rank-5 residue, #614 German "10⁻³ d. h." script break (widened), #615 glued bracket, #617 unit after a label range (script break), #619 eight pre-existing `_cut_point` mutmut survivors.

## Findings for thread length
3 review rounds, 0 post-merge defects at writing. Round 1 found a coverage gap the plan's own list could not show (cover.py over every multi-word replacement) and a quadratic constant; round 2's mutation found one real edge (label at the paragraph start). Lesson for the ledger: check rule coverage against what the steps actually produce, and time punctuation-dense input. No reason to shorten or lengthen threads.
