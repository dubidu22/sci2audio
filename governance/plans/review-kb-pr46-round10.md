# Review of KB PR #46, round 10 (fix of round 9 M1)

Head reviewed: `e54cce9`. It adds one commit on top of `8313334`. The commit changes D-380, D-382 and D-383 and nothing else.

- **M1 fixed.** The coordinator confirmed that both figures are right but come from different data sets. D-380 and D-382 now limit the 21 % to "the four runs recorded at plan time" and point to D-383 for the later run. D-383 now says the 24 % comes from "a later fifth run, `scripts/speed.py` with the new code on pymedphys (after the four runs of D-380)": 46 % with the old estimator and 24 % with the new one, live and in replay, and 14 % with the first chapter skipped. The rows no longer read against each other.
- The coordinator's "6/6/3 %" was left out. That is right, because the log names no runs it could refer to, and nothing the decision needs is lost.
- D-382's "at 500 characters … 24 %" is about the plan-time runs and is unchanged from the coordinator's first note. Its row now says which runs it means, so it doesn't clash with D-383.
- All three rows still have 6 cells, and the decision texts and statuses are otherwise unchanged.

**Approved at e54cce9.** It merges after KB PR #45 has merged, main has been merged into this branch, and a final check passes.
