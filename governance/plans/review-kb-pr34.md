# Review: sci2audio-design PR #34 (D-227 to D-243, #68 units and abbreviations)

Reviewer thread: "Review KB PR 34 units decisions", 13 Nov 2026. PR head 991fcb4; code PR #116 head ec0d1aa.

## Round 1 (13 Nov 2026, ~06:45 UTC)

### Format: all pass
- 17 rows D-243 down to D-227, directly above D-226; the whole log is strictly descending with no duplicate IDs.
- Every row has exactly six columns (no unescaped pipe in any cell).
- All 17 rows are **Decided (Claude)** (coordinator, 13 Nov 02:37 UTC, under D-80; Colin informed 2026-11-13T02:37:00Z). The chat post cmsg_…8MrsEoUWSD69Kvfz9CUMfH has created_at 2026-11-13T02:37:00Z (checked with read_messages_by_id).
- main (d87cede, holding D-1–175 and D-192–226) is an ancestor of the PR head; mergeable_state clean. No closing keyword before a PR link.

### Against plan section 4 (A–Q): all match
A = D-227 … Q = D-243 in order. Each row gives the plan's decision, question, alternative and reason. Notes, none needing a change:
- D-230 says "four kinds", plan D says "three kinds"; plan 3.1 itself lists Suppl. separately ("before a label word"), and the code has four `before` values (anything, number, label, word). The row matches the code.
- D-233 "an issue follows only if a paper shows them in running text" vs the chat line "wait for v1.1": compatible.
- D-236 "no unit is read after a label word" is broader than plan 3.2's wording (single capital letter only), but plan J says "not after a label word" without a limit and the code blocks every unit after a label word ("Figure 2 mg", "Step 5 ms" stay). The row matches the code.
- D-243 says #67's check "can share its helpers once it lands" where plan Q says "a small copy that the later PR folds in": same intent.

### Against the code (PR #116, ec0d1aa)
Checked counts: 37 abbreviation entries, 93 units, magnitudes K/k, M, B/bn, label words and articles in units.toml; the excluded forms (in, pm, a, y, pt, M, kb, Mb, um) are absent. D-243's test `test_units_are_heard_as_words` exists, `@pytest.mark.slow`, WER limit 0.25, symbol mapping before comparing.

Probed about 120 inputs through `run_steps(..., steps=(step,), strict=True)`. Every example in D-230 to D-242 reads as the row says (e.g. "mg/kg/day", "5 J/(kg·K)", "5 m s⁻¹", "5 s⁻¹", "5 m²", "9.8 m/s²", "5 N m", "5 m A", "5 day", "5 mg kg⁻¹ day⁻¹", "3.6eV˚A", "−1 °C", "1.0 m", "0–1 h", "a 5-km race", "a 1 m pole", "5 K", "1°", "441K apps", "5K/s", "5 M", "5‰", "××", "~5", "τ ∼ 0.1 ps", "X ~ N(0, 1)", "5~10", "1920x1080", "2x3x4", "10x speedup", "0x1F", "x86", "2 x n", "0003-066X", "µ = 3", "1990s", "2D", "5G", "5m", "9kg", "Figure 2 A", "COVID-19 m", "10:30 h", "1/2 h", "1 A note.", NBSP/thin/narrow space/line break, "E.g.", "fig. 2", "FIG. 3", "S.T.", "eq.(1)", "App.B", "resp. The next", "Suppl. Fig. 3", Dr./vs./No./etc./et al. left, caption "Fig. 3. Response over time.").

**One mismatch (code, not KB):**

- **F1 (must fix in PR #116): a glued magnitude letter at the end of a block is never read.** D-241 and plan 3.2 say the magnitude reads "when a space, punctuation or the end follows". In the code, "300K", "2bn", "100k", "1M", "the 441K", "about 15M" as the last characters of a block stay as printed, while "300K." reads "300 thousand.". Cause: `src/sci2audio/textprep/units.py:248`, `text[magnitude.end() : magnitude.end() + 1] not in _UNIT_JOINTS`: at the end of the text the slice is `""`, and `"" in "/^·⋅⁻²³"` is True, so the check fails. Fix: test the character only when there is one (e.g. `text[pos:pos + 1] not in _UNIT_JOINTS or pos >= len(text)`, or compare against a frozenset of joint characters), plus a unit test with the magnitude at the very end of the block ("trained on 15M", "300K"). Real case: a heading or caption ending "on 441K".
  Other `in` checks on one-character slices were checked: line 293 (`before[-1:] in _DASHES`) is guarded by `isdigit()` on the next slice, line 406 has an explicit `!= ""`.

No KB row needs changing. KB PR #34 merges once F1 is pushed to PR #116 and re-checked, so that D-241 describes the code that lands.

## Round 2 (13 Nov 2026, ~07:40 UTC): merged

- F1 fixed in PR #116 (head 62f5e89): "300K", "2bn", "100k", "trained on 15M", "the 441K" at the end of a block now read thousand/million/billion; "5K/s" still stays. Unit test (line 357) and regression case `units-magnitude-at-the-end` added.
- Three rows refined after the review of PR #116 round 1, each marked so in its Record column, all checked against 62f5e89:
  - D-230: a label may start with "[": "Eq. [3]" reads "Equation [3]" (matches D-171).
  - D-236: no unit or magnitude letter after a plural label word or in a list of labels after one: "Figs. 2A and 3B", "panels A and 3B", "Tables 1A, 1B, and 2C", "Figures 2B" stay; "Our 7B model" reads "7 billion".
  - D-242: a glued x next to an operator is the variable: "y = 2x + 1", "3x^2", "f(x) = 4x." stay; "10x speedup", "3 x 4", "1920x1080", "3.5x." still read "times".
- Main (#35 D-244–261, #36 D-262–273) merged into the branch at 94f6070: the diff against main is exactly the 17 rows; the log reads D-273 … D-227, D-226 … strictly descending, no duplicates, six columns everywhere; only gap D-176–191 (#67, still to come).
- Squash-merged as 31755a6.
- Note for the coordinator: the three refinements post-date the 02:37:00Z chat post; Colin has not had a line on them yet (D-80).
