# Review of PR #323, round 1 (#202 inline fractions, D-575)

Reviewed head e7ad8c5 (main aec6e6a merged in). Verdict: **changes requested**, 6 items. The design follows D-575 and the PR's claims hold; the items are about headroom and the tests the plan promised.

## What I checked and found correct

- **CI**: all jobs green on e7ad8c5 (ubuntu, windows, macos, browser, lint and layers, licences, security, CodeQL).
- **Fast suite locally** (Python 3.12, `HYPOTHESIS_PROFILE=ci`, -n 4): 4697 passed, 1 skipped, 76 snapshots passed.
- **Goldens are liu only.** Extraction hunks all fall inside `test_golden_file[arxiv2024-liu-orbital-hall]` (p2-l89, p2-l122, p2-l123, p3-l65), layout hunks too (blocks 16, 23, 27, 28, 33, 34, 36, 38; block count unchanged). The fourth extraction line, p2-l89 "− i ℏ-V", is i over ℏ in display formula (3): a real fraction, correctly explained.
- **Spoken-script diff over all 8 papers** (`sci2audio script FILE -o <scratch> --chapters all --ignore-settings`, main via PYTHONPATH vs branch): 7 identical, liu differs in exactly the 3 sentences the PR shows ("eℏ 2me", "1 ℏ ∂Emq ∂q … i ℏ", "eE ℏ").
- **Second run on liu**: the new `test_liu_reads_the_same_on_a_second_run` passes; the regression case passes.
- **Layout does not move text**: only separators change; `test_the_parts_of_an_inline_fraction_keep_a_space` checks text at offset.
- **Script stacks without a bar stay glued** (unit test plus corpus: the 3 already-spaced fractions unchanged).
- **Underlines** (my probe, extraction, main vs PR): an underlined word ("word", "x", "A", "f") with a subscript stored right after it and tucked 0.5 or 1.5 pt back under its last letter, subscript 2 to 4 pt below the baseline, underline 0.4 or 0.6 pt: identical on main and PR, all glued. Only a subscript 5 pt (0.5 em) below a 10 pt baseline, tucked back under an underlined letter, gains a space ("word q"). That shape is contrived; I accept it as a known limit (no issue).

## Measured on liu (all matched bars)

| | thickness | numerator gap | denominator gap |
|---|---|---|---|
| extraction (em of the larger letter, 7 pt) | 0.114 em | ≤ 0.19 em | ≤ 0.20 em |
| layout (em of the row size, 10 pt) | 0.080 em | **0.52 em** for "∂Emq" (all runs), else ≤ 0.19 | ≤ 0.20 em |

The 0.52 comes from `fraction_bar` requiring *every* numerator run over the bar to be within reach: the 5 pt superscript "m" of "∂E^m_q" is the farthest. Lifting that superscript by 1 pt (0.1 em) loses the space (probe on `separators` with liu's boxes: 0.0/0.5/0.8 pt lift → " ", 1.0/2.0 pt → ""). Any numerator with a superscript a little taller than liu's (∂²E over ∂q², x² over 2) would read glued again.

## Fix list

- **R1-1 (layout reach from the nearest numerator letter).** In `geometry.fraction_bar`, keep "every overlapping letter has its middle above the bar", but measure `reach` from the numerator letter nearest the bar (the smallest `drawn.y0 - b.y1`), not from every letter. Add a test in `test_layout_split.py` with liu's "∂E^m_q over ∂q" boxes where the "m" run is lifted by 2 pt: it keeps " ". (Extraction looks at the last char only, so it needs no change.)
- **R1-2 (raise the bar thickness to 0.25 em, both places).** Decision: `FRACTION_BAR = 0.25` and `LayoutSettings.fraction_bar = 0.25`; `fraction_reach` / `FRACTION_REACH` stay 0.6 (after R1-1 the largest measured gap is 0.20 em, three times headroom). Why: TeX keeps the rule thickness when a fraction is set smaller, so liu's 0.8 pt bar over 5 pt letters is 0.16 em and is missed at 0.15. My probe: "1 over h" in 5 pt with a 0.8 pt bar reads "1h" at 0.15 and "1 h" at 0.25. Raising thickness costs nothing in false positives, because underlines and table rules are already far below 0.15 em: the geometry (overlap, middles on either side, reach) is what tells them apart, and your sweep shows no change on the corpus up to 1.0. Update both comments to say why 0.25, add an extraction test case for the 5 pt / 0.8 pt fraction to `test_a_fraction_over_its_bar_keeps_its_space`, and rerun the sweep table (bar and reach) after R1-1 and post it in the PR.
- **R1-3 (the underline guard the plan promised).** Plan section 4 item 1 promised "a word with an underline and a subscript right after it stays glued"; the PR has no such test. Add it to the extraction test (underlined word, 0.4 pt rule 1.5 pt under the baseline, a 7 pt subscript stored right after it, tucked 0.5 pt back, 2.5 pt below the baseline: stays "wordq") and the same shape as two pieces to the `separators` test in `test_layout_split.py`.
- **R1-4 (settings point at each other).** `LayoutSettings.fraction_bar` / `fraction_reach` comments name the extraction constants, like `word_space` names "extraction's SPACE": add "(extraction's FRACTION_BAR)" and "(extraction's FRACTION_REACH)".
- **R1-5 (no second copy of the defaults).** `separators(..., bar: float = 0.15, bar_reach: float = 0.6)` repeats the setting values and would drift with R1-2. Take the defaults from `LayoutSettings.fraction_bar` / `LayoutSettings.fraction_reach` (geometry already imports `LayoutSettings`), or make them required.
- **R1-6 (say which em layout uses).** Plan Q3 says "em of the larger of the two letters' sizes"; layout measures in the row's letter size (`size`, 10 pt on liu, so the bar is 0.08 em there but 0.114 em in extraction). Keep it (with 0.25 both are well inside), but say so in the `fraction_bar` docstring and in the settings comment.

Nothing deferred from this round. #322 (liu's line-end fraction, reading order) is already filed.

After the fixes: reply in the PR with the item-by-item list (fixed / how / why), the rerun sweep, and the new head SHA. Golden files should not change again (verify and say so).
