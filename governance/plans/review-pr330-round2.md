# Review of PR #330, round 2

Head eb7615b (round-1 fixes in 1c6f75c, then main 8f530a4 merged in, which brings in #332). Answer: plans/review-pr330-round1-answer.md.
Verdict: **changes needed**. R2-1 is a blocker, a quadratic cost. R2-2 lists tests to add for code no test needs.

## Round 1, item by item

| item | result |
|---|---|
| R1-1 nests of any depth | **held for the shapes named in round 1**. The comma, semicolon, "e.g.", "vgl." and "und" nests go whole on the first run and read the same on the second. The seed 555 and 8080 rows are regression cases (`citations-a-nest-of-any-depth`, `de-citations-a-nest-of-any-depth`). **Not held** for a lead word nest with a year tail: see R2-1 |
| R1-2 seed 41 | held. The oracle takes "." and the edge separators, and the row is in the #272/#259 case |
| R1-3 #324 | held. The four reasons name #324, and #324 has the new criterion |
| R1-4 mutants | held for the six from round 1. I checked the replacements; removing the crossing check in `_merged` is fine (16,000 fuzz texts in strict mode raised no overlap) |
| R1-5 German rows | held |
| R1-6 issues | #337, #338 and #339 were filed. I put them on milestone v1.2 (D-598) |

## Checks I ran

- Fast suite on eb7615b: 5112 passed, 1 skipped, 6 xfailed (#320, #321, #324), 76 snapshots passed. On 1c6f75c: 5068 passed.
- Nightly profile on 1c6f75c, over the citations, German citations, links and both regression files: seeds 41, 555, 8080, 1234, 4711 and 9001 all pass (1007 passed each).
- Corpus: all 13 documents are byte-identical to main, for 1c6f75c against fbc6de8 and for eb7615b against 8f530a4.
- Fuzz, seed 777, 8000 texts, against main fbc6de8: 36 second-run breaks here against 150 on main. One break shows up only here, `. doi:10.5281/zenodo.592845( (Müller, 2019) (Smith, 2019); (527794) ) Lee see`. Its minimal form, `doi:10.5281/zenodo.592845( (Müller, 2019); (527794) ) Lee`, breaks on main too: a link glued to "(" swallows it, which is #326's class. Not this PR's.
- 90 hand shapes (round 1's and new ones, including subjects, separators and mismatched brackets): no second-run break. `((Smith, 2019); Jones, 2020) is cited.` now reads `Jones is cited.`. That is D-541's rule, the same as main's `((Smith, 2019) Jones, 2020)` → `Jones`; keeping Smith too stays #278's job.

## Fix list (all required)

**R2-1. One look per level: quadratic time.** I counted the looks per block over every combination of 7 lead words, 15 tails and 7 inner brackets, at depths 4 and 12. Six combinations need one look per level: a lead word ("see", "cf.", "vgl.") with a year tail " (2019)", around "(Smith, 2019)" or "(Smith, 2019, https://x.org)". Example: `It holds (see (see (see (see (Smith, 2019) (2019)) (2019)) (2019)) (2019)) found it.` Each look removes one level, and the bound of one look per bracket lets the looks keep going. Citations step alone, CPU time:

| depth | characters | looks | PR | main |
|---|---|---|---|---|
| 100 | 1,332 | 102 | 0.84 s | 0.02 s |
| 200 | 2,632 | 202 | 4.5 s | 0.06 s |
| 400 | 5,232 | 402 | 26.6 s | 0.15 s |
| 800 | 10,432 | 802 | 87.8 s | 0.15 s |

German "vgl." behaves the same: 82 s at 800 levels. A 10 kB paragraph holds the job for a minute and a half, which breaks the linear-time rule (#274, D-539). Two mutants of round 2 point the same way: without `_separators_left`'s start rule, the suite runs past 300 s instead of failing.

Wanted:
- (a) Decide this shape inner first in one look, as you did for the comma nests: once the inner citation goes, the year bracket after it is judged on the names before it, inside the nest.
- (b) Make the look loop linear whatever the shape. Keep "until a look changes nothing", but stop as well once the looks have read a fixed multiple of the block's length (a work budget). The bound then still depends on the input (D-588), but no shape can cost quadratic time.
- (c) Add this shape (en "see" and "cf.", de "vgl.", with and without the link inside) to `test_a_deep_citation_nest_takes_linear_time`, and as en and de regression rows at depth 4.
- (d) Add a test that runs a shape needing one look per level (a stand-in, if (a) leaves none) and checks the budget keeps it linear.

If (a) and (b) cannot both hold for some shape, linear time wins. The second-run difference on that shape then gets an issue, and the coordinator decides.

**R2-2. New code that no test needs.** I made 13 one-line mutants of the round-2 code. Seven were killed (two of them by running past the timeout). These six survived:
- `shells-pair`: in `_shells`, any opening and closing bracket counted as a pair. Kill it with `Text ( [12] ] more.` → `Text ( ] more.` (the mutant reads `Text more.`, dropping brackets that do not match). Add that row.
- `shells-balanced`: `if kind is EditKind.REMOVE:` without `_balanced(...)`.
- `sep-behind`: the end separator blank in `_separators_left` (`if hung := self.hung_behind.search(...)` → `if False:`).
- `toolong-none`: `_decide` returning None for a bracket longer than the cap, in place of `_cited_once_inner_citations_go`.
- `read-cap`: dropping the cap check at the end of `_Read.of`.
- `read-longer`: dropping `len(replacement) > end - start` in `_Read.of`.

`test_a_deep_citation_nest_takes_linear_time` only times the run, so `toolong-none` and `read-cap` pass it with the nest unread. Make it also check the result (the whole nest goes: `It holds found.`), and confirm that this kills both. For `shells-balanced`, `sep-behind` and `read-longer`, add a test that fails without the code, or remove the code if it cannot be reached. Say which, for each.

## For the coordinator
- R2-1(b) puts a work budget on top of D-588's input-tied bound. It keeps D-588's intent (no fixed count of passes) and adds a linear-time guarantee. If you want it recorded, it is a refinement of D-588.
- CI on eb7615b: I add "ci:full" once round 3 passes, before I recommend the merge.

## Probes (container-local, /home/user/probe/)
looks.py and growth.py (looks per block, growth search), quad.py (the R2-1 table), mutate2.py (round-2 mutants), probe.py with all.txt, subj.txt, s7.txt and s9.txt, fuzz.py (seed 777).
