# Review of PR #273 (#269), round 1

Head reviewed: c4e2855 (base main 2c9adac). Reviewer: review thread "Review German percent second-run fix PR", 14 Nov 2026.

## What I checked

- Regression: the 4 new `test_a_second_run_reads_nothing_new` rows and the new `german.toml` case fail on main's code (PYTHONPATH=main/src), pass on the PR. Confirmed.
- "%ige" family ("%ige", "%igen", "%iger", "%igem", "%iges", "%ig", "‰ige", "°ige", " %ige"): unchanged from main, read as decimal. Confirmed.
- English: only `numbers_de` and `statistics_de` call `unit_follows` / `unit_starts_at`; no English path reaches the change.
- Corpus: all 13 corpus files, language auto and forced "de" (26 script jobs), byte-identical main vs PR.
- Fast suite on the PR: 4203 passed, 1 skipped.
- Nightly profile, seeds 13001 and 48271 (new), on the five German/statistics/units/citations test files: 841 passed each.
- A probe file of 76 shapes through the whole German chain, two runs each, main vs PR (harness: whole chain via `run_steps`, flags any second-run change). Main has 5 second-run breaks in it (the 3 of #269, plus "0,05°12.03.2019", "0,05€12.03.2019", "0,05°1/2"); the PR has none.

## Findings

### F1 (must fix): coordinates lose their reading, glued or after a space

The "°" sign now counts as a unit before any letter, so a compass letter after it turns the decimal off:

| printed | main | PR |
|---|---|---|
| `Bei 52,5°N und 13,4°O.` | `52 Komma 5°N und 13 Komma 4°O` | `52,5°N und 13,4°O` |
| `Bei 52,5 °N gemessen.` (space before) | `52 Komma 5 °N` | `52,5 °N` |
| `Bei 52,5°N, 13,4°E und 2,5°S sowie 7,5°W.` | all read | all as printed |

The spaced one goes through the token path (`_unit_base.match("°N")`). espeak-ng de (misaki) reads "52,5°N" as "zweiundfünfzig, fünf Grad N": the comma becomes a pause and "Komma" is lost. Coordinates are a normal spelling in geography, climate and field-study papers, not an odd glued shape, so this goes beyond D-537's accepted change.

Fix asked: keep main's rule for "°" followed by one to three compass capitals (N, S, O, W, E) and no further letter, e.g. a lookahead `(?!(?<=°)[NSOWE]{1,3}(?![^\W\d_]))` on the sign branch. That is stable: no step's reading produces a lone compass capital right after a sign ("°η²" becomes "°Eta", "°Nr.3" becomes "°Nummer 3", both still letters after the capital). I tried exactly this in a scratch copy: all coordinate rows read as on main, no second-run break in the 76 shapes. Add test rows (glued, spaced, NNE) to `test_a_second_run_reads_nothing_new`.

### F2 (must fix): dotted unit forms moved into the sign group; the PR body says they did not

`f[-1:].isalpha()` is False for "Tsd.", "Std.", "Min.", "Sek.", "Mrd.", "sek.", "Mio.", "min.", so they now follow the sign rule. The body says "A form that ends in a letter ("m", "Std.") keeps its old rule". Effect:

| printed | main | PR |
|---|---|---|
| `Es waren 2,5 Mio.Einwohner.` | `2 Komma 5 Mio.Einwohner` | `2,5 Mio.Einwohner` |
| `Es dauerte 1,5 Min.Pause.` | `1 Komma 5 Min.Pause` | `1,5 Min.Pause` |

Main has no second-run break for them ("2,5 Mio.12.03.2019" and "2,5 Std.3. Platz" are stable on main), so they need no change. Fix asked: classify by the last character before a final dot (`f.rstrip(".")[-1:].isalpha()`) so dotted forms keep the old rule, and add one row ("2,5 Mio.Einwohner"). Tried in the same scratch copy: back to main's reading, still stable.

## Not findings (inside D-537, noted only)

- "%IGE" in capitals is not caught by the "-ig" exception: now as printed. Very rare; no action.
- "12,5°Celsius", "2,50€pro Stück", "1.234%abc", "0,05%η²": now as printed. Odd glued shapes, the class D-537 accepted.

## Result

Round 1: changes requested (F1, F2). Everything else as claimed in the PR body.
