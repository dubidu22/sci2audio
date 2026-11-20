# Review of PR #300, round 3 (#285, bracketed grant numbers)

Head reviewed: c202b9b (main 1cbed9b already merged in; main has not moved since).
Result: **approved, merged by squash.**

## Round 2 fixes checked

- R2-1 fixed: `_decide` runs the identifier test a second time on `_read_inside` (the inside after the inner brackets' edits). `(527794 (Smith, 2019))`, `(grant 527794 (Smith, 2019))`, `( 527794 (Smith, 2019) )`, `(527794 [3])`, `(527794 (Smith, 2019) (Lee, 2020))`, `Smith (527794 (Lee, 2019))` and the German forms all go on run 1 and stay gone on run 2. The keeps stay: `(527794 (2019))`, `(527794 (OPP-115))`, `(527794 (3))`, `(12,345 (Smith, 2019))` → `(12,345)`, and `(n = 12345 (Smith, 2019))`.
- The author's own find, de `(Projekt 12.345 (Müller, 2019))`, is fixed. `_in_round_bracket` now skips closed inner brackets and reads `(Projekt 12 345)` on both runs. I probed `(a) 12.345 (b)`, `(a (b) 12.345)`, `((a) 12.345)` and `12.345 (b)`; each reads as expected.
- R2-2: the stubs are added to #305 as a comment. `( (527794))` now goes under the round 1 lead-only rule.

## Probes and fuzz

- 300+ hand shapes from rounds 1–3: none changes on the second run, except the link shapes below.
- Fuzz on c202b9b: 80,000 random token texts (en and de, whole chain twice) with new seeds 5–8.
  - 358 texts read differently on the second run; 300 of those also do on main 1cbed9b.
  - The other 58 are main's sibling class #308 with an identifier in between, link shapes (below), or URLs glued to brackets.
  - No R2-1-like class remains.
- Links: `(527794, https://example.org)` → `(527794)` → gone on run 2. Main has the same break for citations: `(Smith, 2019, https://example.org)`. Filed as #309 (v1.2). This is not a #300 regression: run 1 reads the number as main does.

## Runs

- Fast suite: 4562 passed, 1 skipped.
- Own nightly seeds 99 and 31337 on the citation, German links/citations, German numbers, both regression files and runner: 870 passed each.
- CI on c202b9b: all 12 checks green, including tests on macOS, Windows and Ubuntu and the Chromium browser job. The PR is mergeable (clean).
- Golden diff against main 1cbed9b: still exactly the two seaborn grant brackets (3 snapshot files, +41 −5).
- Timing (8× the text): id+citation 7.6×, wide children 8.3×, German thousands 7.3–8.3×. A deep nest (capped) costs 0.41 s vs 0.21 s on main at 10k characters, sublinear.

## Deferred, all with issues

#305 (separator and lead-word stubs), #306 (nests on main), #308 (sibling year class on main), #309 (link inside a bracket), #304 (English numbers second run on main), #303 (German date on main).
