# Review PR #270 (#266), round 2

Head 2f68367 on main 2c9adac (main has not moved).

Round 1 finding 1 (any vs all, D-534): FIXED. `any(...)` in `citations._decide`, comment names D-534; the mixed step-alone pin now reads "Das gilt (; [1,2; 3,4])."; "([1,2; 3,4]; [12])" and "([1,2; 3,4], [12])" added to the whole-chain second-run rows ("([12]; [1,2; 3,4])" was there already); PR body updated with #271 and #272.

Checked:
- Source diff equals the one-word change I measured in round 1; the 36 hand probes give byte-identical output to that measurement, none changes on a second run.
- Fast suite: 4,209 passed, 1 skipped. Nightly profile on the five textprep files: seeds 31337 and 777 pass (847 each).
- Own fuzz seed 1: 1 second-run break, the #271 shape (on main).
- CI on 2f68367: all checks green.

Verdict: approve, merge by squash.

Deferred (filed in round 1, milestones set per D-538): #271 (v1.1), #272 (v1.2).
