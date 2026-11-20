# Review of PR #248, round 2

Reviewed head f43c550 (round 1 fixes on 62eb832), 14 Nov 2026. Verdict: **approved, ready to
merge** once CI on f43c550 is green.

## Round 1 findings, checked

- **M1 fixed.** `_marks` zips each run with its neighbours inside its own `TextLine` (new `_lines`
  helper, `zip(..., strict=True)` keeps runs and neighbours aligned); `_raised` gets only those.
  Re-measured on the corpus: runs that pass every mark condition except the label match only via
  a neighbour on another line went from 279 to 0. New two-line overlap test (de, en).
- **S1 fixed.** `_raised` skips neighbours set small. Same-line candidates went from nowak 15 to 0
  and liu 36 to 3; German paper still 26 + 4 (30/30). New subscript test (de, en).
- **S2 fixed.** `_CLOSING` has ‘ « » too; regression case
  `de-footnote-mark-after-guillemets-and-single-quote` covers »…«, ‚…‘, «…».

## Checks after the fixes

- English byte-identity rerun by me: main vs f43c550, every corpus file, automatic and "en",
  default switches and all on: every English script and report identical; only the German paper,
  the German note and the German text sample's report differ, as in round 1.
- German paper script identical to round 1 (30/30 marks, no golden change); forced-"de" outputs of
  every corpus file identical to round 1.
- Fast suite (ci profile, -n 8): 3798 passed, 3 skipped. Browser suite passed in round 1 (51); no
  web change since.

## Deferred

Nothing from this review. #249 (v1.2, "Formel 3.2" read "drei.zwei") is out of scope.

## Merged

Squash-merged as a475be4 on 14 Nov 2026 (CI on f43c550 all green, main was 98eb92a).
