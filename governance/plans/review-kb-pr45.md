# Review of KB PR #45 (sci2audio-design, D-329 to D-336)

Head reviewed: d5c76d0, 13 Nov 2026. Reviewer thread "Review loose rule joins PR 164".

**Verdict: approved, merge in its turn** (after KB #38 to #44; the author merges main into the
branch if it conflicts, keeping numeric order, no force-push).

- Only `docs/kb/00-index/decision-log.md` changes: eight rows D-336 down to D-329, newest
  first, directly above D-320; D-90's status gains "refined by D-329 to D-333 (13 Nov)".
- Each row matches the approved plan (`plans/issue58-loose-rule-plan.md` §6, Q1 to Q8, and §9)
  and PR #164's code: one line's box, smallest box, tie by read order; no slack; per group;
  right after the line; any block kind; golden format commit; `split_at` order; `formulas._flush`
  keeps D-90, follow-up #163.
- Facts checked against the corpus run in the PR #164 review: 5 of 158 joining graphics move
  (nowak p1-d7/p1-d8, liu p1-d97, biggs p1-d5/p1-d6), no text change.
- Status "Decided (Claude)", 13 Nov 14:15 UTC under D-80, Colin informed 2026-11-13 14:15:16 UTC,
  as the coordinator gave it. Cross-references (D-90, D-92, D-276, D-60) exist and fit.
- The PR body links code PR #164 with "see there", no closing keyword before it.
- If round 1 of PR #164 (M1 speed, S1/S2 tests) changes no behaviour, no KB change is needed.
