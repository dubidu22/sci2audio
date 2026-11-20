# Review: sci2audio-design PR #37 (D-274 to D-280, #36 a space only where printed)

Reviewer thread: "Review KB PR 37 printed-space decisions", 13 Nov 2026. PR head 66c68b4, base main 31755a6; code PR #128 head e9ec24c.

## Round 1 (13 Nov 2026, ~08:05 UTC)

### Format: all pass
- 7 rows D-280 down to D-274, directly above D-273; the whole log is strictly descending, no duplicate IDs, 264 rows.
- Every new row has exactly six columns (the pipes in "\|N\|" are escaped).
- All 7 rows are **Decided (Claude)** (coordinator, 13 Nov 07:27 UTC, under D-80; plan approved as recommended; Colin informed 2026-11-13T07:27:05Z). The chat post cmsg_…XJwfZAd5boTh5nfSvS9Q4a has created_at 2026-11-13T07:27:05Z (checked with read_messages_by_id). Plan section 9 says Q1 to Q7 "as recommended", so the wording is right.
- No existing row edited. main 31755a6 is the parent of the head; mergeable_state clean; no other open KB PR. No closing keyword in the PR body; code PR #128 is a plain link. Issues #125, #126, #127 exist and are open.

### Against plan sections 1 to 5 and 9 (Q1–Q7), the decision post and PR #128
Q1 = D-274 … Q7 = D-280 in order; each row gives decision, question, alternative(s) and reason as the plan does. Facts checked:
- D-274: alternatives A–D match plan section 2; "13 real against 34,070 generated" matches section 1; "no core dataclass changes" matches the post.
- D-275: 0.05 em scriptspace, 0.12 em null delimiter, thin space 1/6 em, 0.20 em cutting "✓ A" and medium maths spaces: all as in plan sections 1 and 5.
- D-276: 161 touching cases, white of 0 or less, any baseline: matches `_Line._white` in PR #128 (`char.u0 - last.u1 <= 0` returns False before the baseline test).
- D-277: matches plan section 3 and Q4.
- D-278: `_after_label` in `textprep/links.py` (FOOTNOTE block, starts with its label after leading white space); regression case id `link-only-footnote-mark-set-close` in `tests/regression/english.toml`: both match.
- D-279: "grammar.1" and "xij" are the expected texts in `test_a_footnote_mark_or_subscripts_do_not_cut_a_paragraph`; the second test's "band off-diagonal"/"terms" gap goes from 0.2 pt to 10 pt (1 em). (The code PR also moves the subscript "E" and "into the" so the gap stays halfway; that is a code detail, the row is right.)
- D-280: `SPACE = 0.15`, `SHIFT = 0.1` beside `LINE_GAP` in `extraction/pdf.py`; `LayoutSettings.word_space = 0.15`, `stack_reach = 2.0`; the pdf.py comment names `LayoutSettings.word_space` and the settings comment names extraction's `SPACE`: all match.

### Findings

- **F1 (must fix): D-278 cites D-128 in its record.** D-128 is "a block step's accepted edit claims its whole block", which is about block steps; `links` is an inline step (D-167), and D-278 has nothing to do with edit claims. The decision D-278 protects is D-168's "a block or footnote holding nothing but links (and its mark) reads nothing", which is exactly what the regression case checks (`expected = []`). Fix: replace "D-128" with "D-168" in the D-278 record cell.
- **N1 (nit, take or answer): D-275 says "0.15 em of the letter size".** Plan section 3 and PR #128 measure it in em of the larger of the two letters (extraction) and of the row's letter size (layout); SHIFT is in em of the smaller letter. Suggested: "white narrower than 0.15 em (of the larger letter in extraction, of the row's letter size in layout) is no space", so the row can be reproduced from the log alone.

Note for the code review of PR #128, not the KB: none.

KB PR #37 merges once F1 is fixed and N1 is fixed or answered.

## Round 2 (13 Nov 2026, ~07:58 UTC)

Author's fix 2a82cdc (new commit, no force-push) changes exactly two cells of the log:
- F1 fixed: D-278's record now cites D-168 instead of D-128.
- N1 fixed: D-275 now reads "white narrower than 0.15 em is no space: in extraction, 0.15 em of the larger of the two letters; in layout, 0.15 em of the row's letter size", as plan section 3 and PR #128 measure it.
Log still strictly descending, 264 rows, six columns in each new row; base main still 31755a6; mergeable_state clean. Approved and squash-merged pinned to 2a82cdc: main b6836fd.
