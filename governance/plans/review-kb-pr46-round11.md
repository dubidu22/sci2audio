# Review of KB PR #46, round 11 (references for D-380 to D-383)

Head reviewed: `d21799f`. It adds one commit on top of `e54cce9`, which was approved in round 10. The commit changes four Record cells and one phrase in D-383. No decision text or status changed.

- **D-383:** "goes to a v1.1 issue, filed by the #136 thread" now reads "goes to v1.1 as sci2audio Issue [#178](…)". Issue #178 is open, milestone v1.1, titled "app: leave the first chapter out of the time estimate's measurement? (WI-04)".
- **D-380 to D-383:** each Record cell now reads "sci2audio Issue [#136](…), PR [#179](…); …", and D-383 also names Issue #178. PR #179 ("app: the time estimate fits a cost per chunk (#136)") is open and in review. Linking it is fine, because nothing in the PR body or the new cells puts a closing keyword next to it.
- All four rows still have 6 cells.

**Approved at d21799f.** It merges after KB PR #45 has merged, main has been merged into this branch, and a final check passes.
