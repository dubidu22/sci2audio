# Review PR #359, round 2 (textprep follow-ups PR 2, units #320 #321 #335)

Head reviewed: ff55995 (9d6a8e7 and efb2eee on 9fc815f, then a merge of main 87c6503). Answer: plans/review-pr359-round1-answer.md.

**Verdict: not approvable yet. One blocker (B1), caused by the S1 fix.**

## Round 1 items

- **S1:** the issue rows are fixed. "2/3 m s⁻²", "3/4 m s⁻¹", "3/4 kg m²", "1/2 m · s⁻¹", "1/2 W m⁻² K⁻¹", "3/4 min s²", the line-broken forms and "Am 3.4. 1/2 m s⁻¹" now read the same on both runs. "1/4 cm²", "3/4 und x²" and "1/5 m⁶" stay as on main. But the new chain lets in shapes that main read the same on both runs (B1).
- **N1, fixed.** Both look-behinds are pinned. "1,017 out of 20 kg", "2.5 out of 20 kg", "2.5 quarters s⁻¹" and "1,003 halves s⁻¹" read the same on both runs, and the extra "," in `(?<![\w^.,])` is right.

## Fix list

### Blockers

**B1. The German chain ends in any letter power, so it now breaks shapes main read the same twice.** `_letter_power_after()` takes any letter with a power at the chain's end (`[^\W\d_][⁺⁻]?[⁰…⁹]`), and skips `_STATISTICS_SQUARE` only right after the fraction. When the first run then reads that last power ("x Quadrat", "R Quadrat"), the fraction stays printed on run 1, and run 2 reads it as words. Whole chain twice; every row below reads the same twice on main 87c6503:

| printed (de) | first run (ff55995) | second run (ff55995) |
|---|---|---|
| `Es ist 3/4 kg x² hier.` | `3/4 kg x Quadrat` | `3 Viertel kg x Quadrat` |
| `Es ist 3/4 m x⁻¹ hier.` | `3/4 m x hoch minus 1` | `3 Viertel m x hoch minus 1` |
| `Es ist 3/4 m s x² hier.` | `3/4 m s x Quadrat` | `3 Viertel m s x Quadrat` |
| `Es ist 1/2 kg R² hier.` | `1/2 kg R Quadrat` | `ein halb kg R Quadrat` |
| `Es ist 1/5 m R² hier.` | `1/5 m R Quadrat` | `ein Fünftel m R Quadrat` |
| `Es ist 2/3 s t² hier.` | `2/3 s t Quadrat` | `2 Drittel s t Quadrat` |

The last row shows that requiring a listed unit symbol at the end is not enough either: "t" is a listed form, yet run 1 reads "t²" after "s ".

Fix: leave the fraction as printed only when run 1 leaves that last power as printed too. Ask the same question the powers rule asks: `numbers_de._powers` skips a letter power when `_unit_chain(plain, base)` or `_NUMBER_BEFORE` holds, and the statistics step reads `R²`. A separate symbol list will drift from that rule. Add the six rows to `de-numbers-a-unit-power-after-a-fraction` (or the unit test), reading as main reads them ("3 Viertel kg x Quadrat", …). They must fail the second-run check on ff55995. Keep the issue rows as they are now.

### Should-fix, nits, deferred

None.

## Checks on ff55995

- Fast suite (`HYPOTHESIS_PROFILE=ci`): 5287 passed, 1 skipped, 4 xfailed (#324).
- Branch commits 9d6a8e7, efb2eee and ff55995 carry no closing keywords. The "Closes #214" in the log range comes from main's 87c6503.
- CI on ff55995: tests (ubuntu-latest), (macos-latest) and (windows-latest) are all green. The next head needs its own green run.
- I'll run the 13 sample documents, mutants and nightly seeds again on the B1 fix head.
