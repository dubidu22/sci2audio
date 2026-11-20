# Light batch audit: textprep v1.2 follow-ups (D-605), 15 Nov 2026

Scope: the five squash commits on main, #353 bd3be17, #359 739f69c, #361 eb28274, #368 82d9e0d, #371 342a8f5 (tip 342a8f5). Read-only, one pass, Opus medium (D-627 item 6). No mutation or nightly runs.

Method: read the review reports (rounds 1–3 of each PR) and both ledgers first, then the src diff of each commit, looking at the files that more than one PR touched (`numbers.py` #359 + #361, `units.py` #359 + #361, `numbers_de.py` #359 + #368) and at how #353's label rebuild meets #368's notice labels. About 90 shapes ran through the whole chain twice (`rebuilt_from_script`) on tip 342a8f5 and on the pre-batch base 87c6503, with paragraphs and with figure + caption pairs. I also grepped the test diffs for removed or weakened tests. The KB repo itself was not reachable from this session (private, read-only clone refused), so I checked the KB against the pending KB batches in `/mnt/project-files/kb/` (D-605, D-610, D-614, D-615, D-630, D-636).

## Verdict

**The batch is sound.** I found no bug (B) in the merged code. Every PR's listed second-run fix holds on tip, and every first-run change I probed is one the PR tables list. Cross-PR: #361's `_MINUS` and #359's fraction chain work together ("−↵3/4 s⁻¹" reads "minus 3 quarters s⁻¹" on both runs). #368's notice reading uses #353's caption-only label mapping as intended. No test was weakened. The removed items are the six `SECOND_RUN_EXCEPTIONS` the batch fixed, `test_liu_reads_the_same_on_a_second_run` (replaced by the 13-document test), and the `assume` for #326 in the citations sibling property (#371 fixed #326, so the property now draws that shape too). The one golden-file expectation that changed ("3.4.2019 - 5.4.2019" now reads "bis") is listed in #368 round 1 N1. Nothing contradicts D-57: every new reading is a marked edit with a reason, and the label rebuild is test code (`sci2audio.testing`). Nothing contradicts the KB entries.

**Missed findings: B 0, S 2, N 2.** S1 is a gap the reviews could have caught. The batch made it visible: #353 made the shape testable and #368 fixed only its German side. S2 is older than the batch and sits next to #339. Neither is a regression against main before the batch. So the batched workflow did not lower review quality in any way I can measure: the review thread found 2 B, 9 S and 9 N over 13 rounds, and each of its fixes holds on tip.

## Findings

### Should fix

**S1. English caption ranges and powers: notice and caption disagree, so a second run differs.** `src/sci2audio/textprep/placeholders.py:48` reads label numbers for German only (D-615 says "English unchanged"). Since #353 maps a caption label through the script (`src/sci2audio/testing/documents.py` `_rebuilt_label`), the second run's notice names the figure as the caption reads it. A first run reads it as printed. #368 fixed exactly this for German (round 1 S3: "Abbildung 1.2-1.4" → "bis"), but the English twin stayed:

| caption (en) | run 1 notice | run 2 notice | caption reads |
|---|---|---|---|
| `Figs. 1–3: Values.` | `Figures 1–3 is skipped.` | `Figures 1 to 3 is skipped.` | `Figures 1 to 3: …` |
| `Table 1–2: Means.` | `Table 1–2 is skipped.` | `Table 1 to 2 is skipped.` | `Table 1 to 2: …` |
| `Figures 2–4. Values.` | `Figures 2–4 …` | `Figures 2 to 4 …` | `Figures 2 to 4. …` |
| `Fig. 1/2 shows x.` | `Figure 1/2 …` | `Figure 1 half …` | `Figure 1 half …` |
| `Fig. 10⁶ shows x.` | `Figure 10⁶ …` | `Figure 10 to the power of 6 …` | (same) |
| `Fig. 3x: Values.` | `Figure 3x …` | `Figure 3 times …` | (same) |

"Figs. 1–3" is a common caption shape in real papers. On base 87c6503 every labelled notice differed on run 2 (it fell back to "A figure is skipped"), so this is no regression. But no regression case or issue covers it: #370 is the German "Tab. 3x", and #362 covers formula labels. Suggested: one v1.2 issue, "English notices read caption label numbers as the caption does (en twin of #249 captions)", with a `label_numbers_read` counterpart over `find_numbers` (English). The `3x` row can join #370.

**S2. A year shell holding two inner citations leaves a stub "(; 2021)" (older than the batch, next to #339).** `src/sci2audio/textprep/citations.py:1545`: `_shells` takes the year shell only when it holds one removal and then a year. With two inner citations listed, the shell keeps the separator:

| printed | tip and base |
|---|---|
| `Data ((Smith, 2019); (Lee, 2020) 2021) here.` | `Data (; 2021) here.` |
| `((Smith, 2019); (Lee, 2020) 2021) is cited.` | `(; 2021) is cited.` |
| `Daten ((Müller, 2019); (Lee, 2020) 2021) hier.` | `Daten (; 2021) hier.` |

It reads the same on both runs, so no second-run test sees it, but "(; 2021)" reaches the voice. It is a different shape from #372 (subject nest losing names). Suggested: add it to #372, or file a separate v1.2 lane:textprep issue.

### Nits

**N1. `return bool(rest)` is always True** (`src/sci2audio/textprep/abbreviations.py:275-276`): `rest in _CLOSING_QUOTES` already means `rest` is not empty. `return True` says the same thing more plainly. (The `in` here is a tuple test, so the "empty string is in every string" trap of #371 round 2 does not apply.)

**N2. A dotted section range reads only its first half** (older than the batch, in `numbers_de.py` near #349's `_AFTER_PUNKT`, line 837 and following): `Kapitel 1.2. – 1.3. lief es.` reads `Kapitel 1 Punkt 2. – 1.3. lief es.` on both runs, tip and base. It is stable and rare. Mention it on #370 or ignore it.

## Not findings (checked, fine)

- English "N out of M unit" (#335) has no German twin: German leaves "17/20 kg", "12/13 mg" and "3/4 s⁻¹" as printed on both runs.
- `equals` / `less than or equal to` before "2x" (#320) read the same on both runs, and "≤2x" now agrees on run 2 (base differed).
- Grouped caret exponents (#210): "10^1 000" with one group stays printed, "10^1 000 000" and "x^1 000 000" read whole, both runs.
- German closing-quote stop (#342): „usw.“ mid-sentence keeps no stop, while »usw.« Dann and ‚usw.‘ at the block's end keep it. English is not affected (`any_capital` is False for "en").
- #368's `_PAIR_DASH` and a three-date chain read "bis" for each dash on both runs.
- Layering: `placeholders.py` imports `numbers_de` inside `textprep`, which the layer contract allows (lint-imports passed on every PR).

## Workflow verdict (D-627 item 6)

| | B | S | N |
|---|---|---|---|
| Found by the batch review (13 rounds, 5 PRs) | 2 (#353 r1 B1, #359 r2 B1) | 9 | 9 |
| Missed, found by this audit | 0 | 2 (1 the reviews could have caught, S1; 1 older than the batch, S2) | 2 (1 older than the batch) |

One review thread over seven planned PRs, with heavy checks only on the approving round, did not lower quality in a way I can see. The one real miss (S1) is a language-twin gap. The plan itself scoped it out ("English unchanged"), and the reviews followed the plan. Lesson for later plans: when a plan makes one language's side agree on a second run, it should say what happens to the other language's side, or file the twin issue at plan time. The ledgers show no CI reruns caused by the batch, and the merged PRs have no post-merge defects.
