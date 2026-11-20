# Review: sci2audio-design PR #36 (D-262 to D-273, #24 outline and PDF bookmarks)

Reviewer thread: "Review KB PR 36 outline decisions", 13 Nov 2026. PR head 0c468b2, base main ab673e1; code PR #124 head aec74e7.

## Round 1 (13 Nov 2026, ~07:35 UTC)

### Format: all pass
- 12 rows D-273 down to D-262, directly above D-261; the whole log is strictly descending, no duplicate IDs, 240 rows (gaps only D-176–191 and D-227–243, both in other open PRs).
- Every row has exactly six columns (no unescaped pipe).
- All 12 rows are **Decided (Claude)** (coordinator, 13 Nov 07:16 UTC, under D-80; plan approved as written; Colin informed 2026-11-13T07:16:04Z). The chat post cmsg_…MCCt9EMujhpDc4hAxJ3nut has created_at 2026-11-13T07:16:04Z (checked with read_messages_by_id). Plan section 7 says "all twelve as recommended", so "approved as written" is right.
- D-66's change only appends "; #24 plan: D-262 to D-273" to the record cell; the rest of the row is byte-identical.
- main ab673e1 is the parent of the PR head; mergeable_state clean. No closing keyword in the PR body; code PR #124 is a plain link. Issue #122 exists ("Layout: split off a heading the outline names when it was joined into a paragraph", open).

### Against plan sections 2 to 5 and 7 (q1–q12) and the chat post
q1 = D-262 … q12 = D-273 in order; each row gives the decision, question, alternative and reason as the plan says. Facts checked:
- D-263, D-264, D-265: match PR #124 (`OutlineEntry(title, level, page=None)`, level ≥ 1, first entry at level 1 and at most one level deeper, page None or 1..len(pages), checked in `Content.__post_init__`).
- D-265 "wrong in 2 of the 4 corpus outlines" and D-272 "all 18 corpus entries" match plan section 1 (5 + 3 + 6 + 4 = 18).
- D-270 "4 truth regressions" = liu title + arsiwalla Abstract, Acknowledgments, References (plan q9). D-271 "73 of 75" matches plan section 1.
- D-262 "revises the v1.0 plan's two PRs" matches v1-remaining-plan.md item 15 ("core PR, then extraction/layout PR").
- D-264 "outline is the glossary's word": glossary-de-en.md line 39 (Gliederung → Outline). Matches.
- D-269 and D-273 add alternatives the plan did not spell out (changing the truth file; splitting in the #24 layout PR); both are fair statements of what was rejected. No change needed.

### Findings

- **F1 (must fix): D-270 says "exactly one text block".** Plan section 5 rule 2 and the chat post Colin read say "exactly one **paragraph** block". "Text block" is wider (a HEADING block is a text block too and is not in the excluded list), so the row does not say what was decided. Fix: change "exactly one text block (never furniture, …)" to "exactly one paragraph block (never furniture, …)".
- **S1 (should fix): every row's record cell links PR #124 without saying which part it is.** #124 is PR 1 of 3 (core) and implements only D-263 to D-265 (and the title rule of D-266); D-267 to D-273 belong to the extraction and layout PRs, which do not exist yet. A reader following the link for D-272 finds no page matching. Suggested: "sci2audio Issue #24 (PR 1 of 3: [#124](…))" in each row, or the same text as now with "(PR 1 of 3)" after the link.

Note for the code review of PR #124, not the KB: none.

KB PR #36 merges once F1 is fixed (and S1 fixed or answered), and after merging main if KB PR #34 lands first (numeric order D-273…D-262, D-261…D-244, D-243…D-227).

## Round 2 (13 Nov 2026, ~07:30 UTC)

Author's fix 8678c3c (new commit, no force-push) changes exactly 13 words in the log:
- F1 fixed: D-270 now says "exactly one paragraph block (never furniture, …)", as plan rule 2 and the decision post say.
- S1 fixed: all twelve record cells now read "PR #124 (PR 1 of 3, core)".
Log still strictly descending, 240 rows, six columns each; mergeable_state clean; KB PR #34 still open, so #36 merged first. Approved and squash-merged pinned to 8678c3c: main 5ed350b.
