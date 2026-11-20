# Review PR #242 round 3 (#130), head f0e4fd4

Verdict: **approved; merge** (base main a475be4, the PR is up to date and mergeable "clean").

## Round-2 items: verified
- R2-1 quadratic units step is fixed: a single pointer walk over the sorted file-number spans. `UnitStep().find` at 80k characters now takes 0.06 to 0.20 s (it was 4.6 s). Linear-time test added.
- R2-2 "Kapitel I %CI" is fixed: the Roman rule leaves a numeral before " %" as printed, and the case is pinned.
- The author's 11 extra second-run fixes from 40 more seeds were read line by line: `_STOP` after "1x.", `_POINT_DECIMAL` not after ×/"1x", `_LEADING_POINT`, dashes inside label runs read "bis", ordinals not after a yearless date or after "hoch", ISO/numeric dates let `_year_left_alone` decide on a trailing letter, `_CARET` after "1x", `=` at the block start in German only (word_stop), and the English `_LETTER_X` chain after a spaced x.
- The one English change ("11 x1x1" → "11 times 1 times 1" on the first run) is right: main read "11 times 1x1" and changed it on a second run. I probed "2 x 3x faster", "3 x 4x4 grid", "5 x 2x + 1" and "1 x86 CPU"; all read the same as main.

## Checks
- Fast suite, run locally on its own: 4012 passed, 3 skipped. CI on f0e4fd4: all green.
- Nightly German properties with 8 new seeds (2121 2323 2525 2727 2929 3131 3333 3535): 56/56 each, clean.
- All probe files from rounds 1 and 2 (about 120 German sentences): no second-run differences and no exceptions.
- English corpus: byte-identical to main a475be4 (all 13 files through `run_script_job`; only the German paper and the two German samples differ).

## Deferred
- #243 is closed by this PR (units step and file numbers). #247 was a duplicate (closed). #250 (v1.2) covers "pro Quadratsekunde".
- Nothing else is deferred. "1 x86 CPU" → "1 times 86" is the same on main and in English only, so it is outside this PR.
