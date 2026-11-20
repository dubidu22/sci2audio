# PR #359, answer to review round 1

New head: ff55995. It holds two new commits on 9fc815f, then a merge of main 87c6503, with no force-push. Every item is fixed and nothing is deferred.

- **S1, fixed with option (a):** `numbers_de._fractions` leaves a fraction as printed when a chain of listed German unit symbols ending in a letter power follows it. That covers "2/3 m s⁻²", "3/4 m s⁻¹", "3/4 kg m²", "1/2 m · s⁻¹" and "1/2 W m⁻² K⁻¹"; before, it did this only for a lone letter power ("1/5 m⁶").
  - The chain takes only the letter forms of the German unit list (`units("de")`, cached), each with an optional power.
  - My first version allowed any word of 1 to 3 letters, which changed "3/4 und x²" (it then read differently on a second run). Probing caught it, and "und" is now pinned.
  - First-run changes are listed in the PR body: these fractions stay as printed, where they read "2 Drittel …" / "ein halb …" before.
  - New German regression case `de-numbers-a-unit-power-after-a-fraction`: the three rows, the control "1/4 cm²" (reads "ein Viertel cm²" as before) and "3/4 und x²" (reads as before). It fails on 9fc815f, both the script and the second-run check.
  - New unit test `test_a_german_fraction_before_a_unit_chain_with_a_power` with 6 rows, both runs.
- **N1, fixed with pinning tests:**
  - `_OUT_OF`: "It was 1,017 out of 20 kg." and "It was 2.5 out of 20 kg." keep "20 kilograms".
  - `_UNIT_CHAIN_AFTER_FRACTION`: "2.5 quarters s⁻¹" and "1,003 halves s⁻¹" read the power. The "1,003" row showed the look-behind let a thousands comma through, so it is now `(?<![\w^.,])`, and the comment says why.

Checks on ff55995:
- Fast suite: 5287 passed, 1 skipped, 4 xfailed (#324).
- ruff and lint-imports are clean.
- All 13 corpus documents are byte-identical to main.
- Nightly seeds 7, 555 and 8080 on German numbers, units and runner are clean. Seed 7's `10^250 000 000` shape is #210, fixed in PR 3.
