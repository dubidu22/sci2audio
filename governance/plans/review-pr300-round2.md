# Review of PR #300, round 2 (#285, bracketed grant numbers)

Heads reviewed: 997f2bb (round 1 fixes), then 7dc7589 (main 1cbed9b, PR #302, merged in; my local merge gives the same tree).
Result: **changes requested**, one blocker (R2-1); three cosmetic stubs to add to #305 (R2-2).

## Round 1 fixes checked

- R1-1 fixed: `(Projekt/FKZ/Projektnummer/Grant 12.345)`, `(12.345-mal)`, `(12.345-fach)` read `(… 12 345 …)` and are stable on both runs. `_in_round_bracket` puts spaces in every German thousands number inside a round bracket: "(12 345 Fälle)", "(N gleich 12 345)", "(EUR 12 345)". The voice reads it the same as "12345" (D-557 measurement), and the German corpus is byte-identical.
- R1-2 fixed: `Smith (527794) (2019)`, de `Text (527794) (2019)` and `(Smith, 2019; 527794)` are stable on both runs, and so are 40 more neighbour and nest shapes I probed (subject position, `[12]`, links, glued brackets, German `Laut Müller …`).
- R1-3 fixed for lead words: `(see/cf./e.g./siehe/vgl./z. B. (527794))` go whole. Deferred to #305: `(; 2019)` and `(see and Lee, 2019)`. That deferral is accepted.
- The fix list on the PR names each fix, and the deferral has issue #305.

## R2-1 (blocker): an outer bracket that holds only an identifier once its inner citation goes

Main reads both of these the same on both runs.

| printed | run 1 | run 2 |
|---|---|---|
| `Text (527794 (Smith, 2019)) more.` | `Text (527794) more.` | `Text more.` |
| `Text (grant 527794 (Smith, 2019)) more.` | `Text (grant 527794) more.` | `Text more.` |
| `( 527794 (Smith, 2019) )` | `( 527794 )` | (gone) |

This is the reverse of R1-2. The identifier test (`self.identifiers.match(inside)`) reads the outer bracket as printed, but the inner citation has already been decided (`decided`) and goes. Judge the outer bracket's inside without the inner removals, as `_cited_once_inner_citations_go` does for citations. Pin the three shapes in both languages, and extend `test_identifier_brackets_add_no_second_run_change` so that citations also go inside identifier text.

## R2-2 (no change in this PR; add to #305): stubs that stay stable

| printed | both runs |
|---|---|
| `Text ( (527794)) more.` | `Text () more.` |
| `Text (see (see (527794))) more.` | `Text (see) more.` |
| `Text (527794, (Smith, 2019)) more.` | `Text (527794,) more.` (may change with the R2-1 fix) |

## Fuzz (80,000 random token texts, en and de, whole chain twice)

- 369 texts read differently on the second run on 997f2bb.
- 300 of those also read differently on main 34303e1.
- The other 69 come down to R2-1 above, or to main's sibling class with an identifier in between. Main's sibling class means a removed citation, numeric citation or year leaves a year bracket beside a name, and the second run then removes it: `Lee (Smith, 2019) (2019)`, `Text [12] (2019)`, `Lee (2019a) (2019)`, and de `. .(Müller, 2019)12.345`. Each identifier-free form breaks on main, so these are filed as **#308** (v1.2) and are not a #300 finding.
- Harness: /home/user/probe/fuzz.py (seeded token generator), fuzz_pronly.txt.

## Runs

- Fast suite on 7dc7589: 4552 passed, 1 skipped.
- Nightly seeds 11 and 4242 on the citations, German links/citations, German numbers, both regression files and runner: 860 passed each.
- Golden diff against main 1cbed9b: still exactly the two seaborn grant brackets (3 snapshot files, +41 −5).
- Timing (citations step alone, 10k vs 80k characters): identifier and year pairs 5.8×, lead-word nests 8.1×, identifiers inside citations 9.1×. All linear.
