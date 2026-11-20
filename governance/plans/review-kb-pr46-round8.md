# Review of KB PR #46, round 8 (D-380 to D-382, D-159 note)

Head reviewed: `88fb2d4`. It adds one commit on top of `e736b02`, which was approved in round 7. The commit adds three rows and one status note.

- **D-380, D-381 and D-382 match the coordinator's handoff** to the KB thread (17:00:00 UTC) item by item:
  - the model a + b·characters + q·characters², with non-negative coefficients fitted on the current run and summed over the chunks still to speak;
  - worst error 39/32/27/14 % falling to 21/12/7/6 % (pymedphys three times, hardt);
  - 4 warm-up calls instead of 1, and 1,000 characters instead of 500, with 24 % at 500;
  - every rejected alternative: constant plus per-character only (39 % to 38 %), recency weighting (no effect), 8 calls or 15 s (overfits pymedphys), digit weighting, and phoneme counts from the voice (changes the voice contract).

  They also agree with the chat post of 17:00:04 UTC (39 % to 21 %, 14 % to 6 %, a fixed cost per call plus a per-character term that grows for long chunks). The author's one-line reasons are fair paraphrases of these two sources.
- **The context matches Issue #136** (open). The problem is the early over-estimate on short papers, and the budget is ±25 % (D-286, `docs/baseline.md`), so "24 %, at the budget's edge" is right.
- **Status:** all three are "Decided (Claude)", which is right for the coordinator's own decision. The time Colin was told matches the post's creation time, 17:00:04.
- **D-159's status note** "partly revised by D-380 to D-382 (13 Nov)" sums up the three changes correctly. The rest of D-159 is unchanged.
- **Form:** the three rows sit above D-379 in descending order, each has 6 cells, and D-380 was the next free number. The PR title and body cover D-380 to D-382 and the D-159 note, and there is still no closing keyword before a link.

**Noted only (no change needed):** D-382 refers to "the budget" without naming it. Adding D-286 to its Record cell would make the reference findable, but it isn't required.

**Approved at 88fb2d4.** It merges after KB PR #45 has merged, main has been merged into this branch, and a final check passes.
