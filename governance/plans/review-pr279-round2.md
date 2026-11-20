# Review of PR #279, round 2 (#271 nested citations)

Reviewed head 7a512ff (round-2 fixes in 2f87878, main 4cfff38 with #277 merged in), 14 Nov 2026. Round 1: review-pr279-round1.md.

## Verdict

Not ready to merge. The round-1 items are all done and verified. But a wider probe found that a nest in subject or noun position comes out broken when its inner citation keeps its names (M1). I missed this in round 1; it is in ad62290 too. One more regression comes from the M1 fix of round 1 (M2).

## Round-1 items, verified

- **M1 (square children):** fixed. All three shapes read the same on both runs. So do `([1, 2] Jones, 2020)`, `([1] [2] Jones, 2020)`, `([1-3] (Smith, 2019) Jones, 2020)`, `([3] Jones, 2020) found it.` and de `([3] Schmidt, 2020) zeigt das.`. Intervals and label numbers stay as before: `(CI [1, 3] Jones, 2020)`, `(Eq. [3] Jones, 2020)`, de `([1,2; 3,4] Schmidt, 2020)`, `(KI [1; 3] Schmidt, 2020)`, `(x = [12] Jones, 2020)`.
- **S1:** the clamp is removed. I put back an assertion `node.open < start <= end <= node.close` in its place and ran 9,000 random nests (seeds 7, 11 and 13) plus about 120 hand shapes. It never fired, so the author's reasoning holds. The length guard is pinned with `([3] found it)`, and the non-empty write-in with `(see (Smith, 2019; Lee, 2020), 2020)`. The ljust-or-blanks mutant: I accept the argument that it is equivalent.
- **S2, S3:** pinned. S3 is added to #278.
- **S4:** I ran the `shift = 0` mutant against `test_a_long_block_takes_linear_time[nests]`, and it fails: "8 times the text took 35.4 times as long ... the limit 32". The margin is slim (35 to 38 against 32), but the test catches it.
- **D1:** #291 is filed and linked.
- **Corpus:** the 13 scripts and 26 reports are byte-identical to main 4cfff38.
- **Fast suite:** 4,331 passed, 1 skipped. ruff, lint-imports and deptry are clean.

## Findings

### M1 (blocker): a subject or noun-position nest whose inner citation keeps its names reads broken

When the inner citation follows "see", "cf.", "vgl." and the like, its names stay (TP-04). If the outer bracket is then a subject, the outer's kept name span runs over the inner bracket. The inner bracket is not inside an outer removal, so it is still visited, and its edits overlap the outer's. `_settled` then drops one edit. The reading keeps a stray ")", the year, or the inner citation as printed. Whole chain, first run → second run:

| printed | main | PR 7a512ff |
|---|---|---|
| `(see (Smith, 2019) 2020) found it.` | `(see Smith 2020) found it.` → `Smith found it.` | `Smith 2020) found it.` (both runs) |
| `(see (Smith, 2019; Lee, 2020) 2021) found it.` | `(see Smith and Lee 2021)` → `Smith and Lee found it.` | `Smith and Lee 2021) found it.` (both runs) |
| `(cf. (Smith, 2020) 2020) is cited.` | `(compare Smith 2020) is cited.` → `Smith is cited.` | `Smith 2020) is cited.` |
| `(cf. (Smith, 2020) (Lee, 2019) 2020) is cited.` | `(compare Smith 2020) is cited.` → `Smith is cited.` | `Smith (Lee, 2019) 2020) is cited.` → `Smith 2020) is cited.` |
| `(see (Smith, 2020) [1] 2020) is cited.` | `(see Smith 2020)` → `Smith is cited.` | `Smith [1] 2020) is cited.` → `Smith 2020) is cited.` |
| `It holds ((cf. (Smith, 2020) [1] 2020) the) here.` | `((compare Smith 2020) the)` → `(Smith the)` | `It holds (Smith [1] 2020) the) here.` → `It holds the) here.` |
| de `(vgl. (Müller, 2019) 2020) zeigt das.` | `(vergleiche Müller 2020) zeigt das.` (stable) | `Müller 2020) zeigt das.` |
| de `wie (vgl. (Müller, 2019) 2020) zeigt` | `wie (vergleiche Müller 2020) zeigt` (stable) | `wie Müller 2020) zeigt` |
| de `Es gilt ((vgl. (Weber, 2020) [1] 2020) das) hier.` | `((vergleiche Weber 2020) das)` (stable) | `Es gilt (Weber [1] 2020) das) hier.` → `Es gilt das) hier.` |

Edits for `It holds ((cf. (Smith, 2020) [1] 2020) the) here.`: only `10-16 '(cf. ('` (outer, "is the subject") and `21-28 ', 2020)'` (the inner, "is part of the sentence") survive. The outer's closing removal is lost.

These shapes read well and stay correct: `(see (Smith, 2019) and Lee, 2020) found it.`, `(cf. (Smith, 2019), Lee, 2020) found it.`, `such as (see (Smith, 2019) Lee, 2020) could` and `(Brown and (Smith, 2019) Jones, 2020) found it.`. Each reads its names on both runs. What breaks a shape is a residual whose names span runs over an inner bracket that keeps names.

Required:

1. The edits for a nest never overlap. Two ways to get there:
   - Build the outer's subject edits from the read itself: carry over the inner edits that fall inside a kept name span, and do not visit those children again.
   - Or decline the re-judgement (`return None`) when a kept name span overlaps an inner bracket, and keep today's reading. Then say which shapes still take two runs, and add them to #291.
2. Pin every shape in the table on both runs, in English and German, with brackets balanced in the reading.
3. Add a guard against this kind of bug: a unit or property test that, for nested input, the citations step's own decisions before `_settled` do not overlap. A nested-subject Hypothesis strategy asserting a stable second run and balanced brackets would also do.

### M2 (regression from round 1's M1 fix): a page bracket glued inside a nest

`It holds ((Smith, 2019)[p. 4] Jones, 2020) here.` read `It holds here.` on both runs at ad62290. Now it reads `It holds ( Jones, 2020) here.` and then `It holds here.`, as on main.

The cause: `[p. 4]` is now an inner child. Its own decision is None, because its removal already belongs to the sibling citation, so `if not handled: return None` gives up. A child that lies inside a sibling's written-in edit should be skipped, not counted as kept. Pin the shape on both runs.

### N1 (no fix in this PR; add to #291): an emptied nest before a bare year

`Jones (((Smith, 2019)) 2020) found it.` read `Jones (() 2020) found it.` on main, stable but with an empty bracket. The PR now removes the empty bracket, which leaves the #291 bare-year residual: `Jones ( 2020) found it.`, then `Jones found it.`. This is the D1 shape reached another way. Please add it to #291.

## Fuzz numbers, main 4cfff38 against 7a512ff (3,000 texts per seed, both runs)

- seed 7: 60 unstable on main are fixed; 1 newly unstable (the de M1 shape above).
- seed 11: 51 fixed; 2 newly unstable (one M1, one N1).

## Merge conditions

1. M1 and M2 fixed and pinned. N1 added to #291.
2. Corpus byte check, fast suite and CI green on the new head.
