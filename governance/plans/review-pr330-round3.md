# Review of PR #330, round 3

Head **ece9296**: fix commit a810803, then main 795c2d2 merged in, which brings #332 and #333. Main is still at 795c2d2. Answer: plans/review-pr330-round2-answer.md. Decisions: D-577, D-588, D-599.
Verdict: **approvable at ece9296**. Linux, macOS and Windows are green on this head.

## Round 2, item by item

| item | result |
|---|---|
| R2-1(a) "see/cf./vgl." year nests in one look | held. The four shapes go whole at any depth, in at most 3 looks |
| R2-1(b) work budget (D-599) | held. `_LOOK_WORK = 8` × (length + 300); past it, the unsettled outermost brackets stay as printed |
| R2-1(c) tests | held. The four shapes are in `test_a_deep_citation_nest_takes_linear_time` (ratio, result, look count), plus en and de regression rows at depth 4 |
| R2-1(d) budget test | held. A stand-in with the inner-first reading turned off stays linear, and its nest stays as printed |
| R2-2 shells-pair, sep-behind, toolong-none, read-cap | held. The author killed each one with a new row or test |
| R2-2 shells-balanced, read-longer: code removed | **confirmed unreachable**. I put both checks back into a copy and ran 20,000 seeded nest-heavy texts through the citations step on both. The edits are byte-identical and nothing raised. |

## Deep-nest timing, my own runs

I counted looks per block over 5,280 shapes: 11 lead words × 24 tails × 10 inner brackets × en/de, at depths 4 and 12. Seventeen shapes still need one look per level. Examples are "see"/"cf."/"vgl." with a tail of two year brackets (" (2019a) (2019b)"), and German "siehe" with " (2019)" or " [12] (2019)". The budget now caps them at 10 to 15 looks, so the cost stays linear. All of them still read right ("It holds found it.") and the same on a second run, up to depth 20 at least.

Citations step alone, CPU time, 800 levels:

| shape | PR | main 795c2d2 |
|---|---|---|
| en `see` with tail " (2019a) (2019b)" (17.6 kB) | 1.85 s | 0.20 s |
| de `siehe` with tail " (2019)" (12 kB) | 1.33 s | 0.12 s |
| de `siehe` with tail " [12] (2019)" (16 kB) | 1.86 s | 0.12 s |
| the four shapes the PR resolves in one look | 0.40 to 0.75 s (author) | 0.15 s |

From 100 to 800 levels the time grows 3.5 to 6.6×, which is linear. Round 2 took 88 s at 800 levels. The worst case is now about 10× main on texts of 12 to 18 kB, all inside one bracket nest. I accept that: it is the budget D-599 decided, and no real paper nests 800 levels deep.

## Checks on ece9296

- Fast suite, ci profile: 5177 passed, 1 skipped, 6 xfailed (#320, #321, #324), 76 snapshots passed.
- Nightly profile with fresh seeds 2468, 13579 and 31337, over citations, German citations, links and both regression files: 1033 passed, 6 xfailed for each seed. Seeds 555 and 8080 are covered by the regression rows and by the author's runs, and 41/555/8080/1234/4711/9001 passed on 1c6f75c.
- Corpus: all 13 documents through `run_script_job` are byte-identical to main 795c2d2 (39 files).
- Whole-chain fuzz, seed 999, 8000 texts: 27 second-run breaks against 137 on main, none of them new.
- 90 hand probe shapes from rounds 1 and 2: no second-run break.

## Follow-ups (all on milestone v1.2)
#320, #321, #324 (the known exceptions), #326 (a link glued to the next bracket), #337, #338, #339, and #278 (subject row).

## CI on ece9296 with ci:full
- tests (ubuntu-latest), tests (macos-latest): success
- tests (windows-latest): success. All three ran in one suite with CI passed: success, started 22:32Z. The earlier "CI passed: failure" belongs to the Linux run that was cancelled when the label was added.
