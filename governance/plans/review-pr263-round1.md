# Review of PR #263, round 1 (issue #253, German numbers read the same on a second run)

Reviewed head 2cb7768 (main 7174f46 merged in), 14 Nov 2026. Reviewer: review thread "Review German second-run number fixes PR".

## What I checked

- **Pins are real second-run cases.** Ran the PR's new unit pins and regression cases against main's code (PYTHONPATH to a main 7174f46 worktree): 33 pins fail on main; the three stated guards (`um 13:30 m² Fläche`, `im 1500-1998 m`, `1-2,5 m`) pass on main, as the body says. Of the 7 new regression cases, 6 fail on main; `symbols-x-before-a-times-sign` passes on main (first run only, second run pinned in the unit test), as the body says.
- **Corpus unchanged.** `sci2audio script` on all 13 corpus files (English and the two German ones, read as "de"), main vs PR: all 39 output files (script, report.json, report.md) byte-identical.
- **Fast suite** on the head: 4,183 passed, 1 skipped (76 snapshots). CI green on 2cb7768 (all three systems, browser, lint, security, licences, CodeQL).
- **Nightly profile, own seeds** (the five textprep files the body lists): seed 31337: 822 passed, 1 failed (D2 below, on main too, not caused by this PR); seed 4242: 823 passed.
- **Hand probes, both runs, main vs PR**, about 120 German and English shapes around each fix (date ranges with and without years, hyphen/em-dash year ranges, ordinals before abbreviated nouns, labels, links after abbreviations, x after powers, `<CI`, `5x×`, soft hyphens in names). Every shape in the PR's tables is stable on the head.
- **Speed**: long blocks for each changed rule, main vs PR.

## Findings

### F1 (must fix): a dated range after "1.–" or "1.3.–" is now half read, with the wrong ending

`_NUMERIC_DATE` no longer refuses an en dash right before the day, and the new skip covers only a date without a year. So a date with a year after a day and a dash is now read, while the day before the dash is not:

| printed | main (stable) | PR (stable) |
|---|---|---|
| `vom 1.–3.4.2020 im Labor` | as printed | `vom 1.–dritter April 2020 im Labor` |
| `vom 1.3.–11.3.2020 im Labor` | `vom ersten März–11.3.2020 im Labor` | `vom ersten März–elfter März 2020 im Labor` |

Both are common German date-range spellings. "dritter"/"elfter" is the wrong case after "vom … bis", and the dash is not read "bis". The `_RANGE_DASH_BEFORE` ending rule needs a digit right before the dash, so it does not fire here.

Wanted: either keep main's reading for these (do not read a date after `<day>.–` or `<day>.<month>.–`), or read both sides ("vom ersten bis dritten April 2020", "vom ersten März bis elften März 2020"). Pin both shapes on both runs, plus a German regression case.

### F2 (should fix, small): em dash date range gets the nominative ending

`vom 1.3.2020—11.3.2020` reads "vom ersten März 2020 bis elfter März 2020" (the same on main). This PR teaches the em dash to `_JOINED_YEAR`/`_JOINED_NEXT`, but `_RANGE_DASH_BEFORE` knows only the en dash. Add `—` there and pin it.

### F3 (must fix): `_Removals.past` makes the abbreviations step quadratic on link-dense text

`past()` walks every link removal in the block for each abbreviation whose place does not fit. The abbreviations step alone on `"Kap. https://x.org/a dazu " * n`:

| characters | main | PR |
|---|---|---|
| 52k | 0.05 s | 0.34 s |
| 104k | 0.05 s | 0.76 s |
| 208k | 0.10 s | 1.88 s |
| 416k | 0.24 s | 5.15 s |

The whole German chain on 104k characters goes from 1.8 s to 2.7 s, and English (`"Fig. https://x.org/a then "`) from 1.8 s to 2.4 s. Use `bisect` on the removal starts (or a forward cursor, since matches come in order), and add a timing test in the style of the existing ones (best of 3, gc off, a ratio well below quadratic).

## Noted, no change asked in this PR

- **D1, the ordinal before an abbreviated noun after a sentence-ending number.** `Das war 2019. Kap. 3 zeigt mehr.` now reads "Das war zweitausendneunzehntes Kapitel 3 zeigt mehr." on the first run. Main read the first run right ("2019. Kapitel 3") but changed it on the second run. The full word already does this on main (`… 2019. Kapitel 3 …` reads "zweitausendneunzehntes Kapitel" on the first run). So the PR is consistent with the existing #130 rule and with D-530, which does not cut a sentence before a non-opener. The fix belongs to both forms: no ordinal from a year-like number before a noun with no article or preposition. Filed as #265 (v1.2).
- **D2, nightly seed 31337**, `test_both_steps_keep_the_contract_on_any_german_document`: the citations step alone turns `( (Müller & Schmidt, 2019) [1,2; 3,4])` into `( [1,2; 3,4])` and then into `""` on a second run. Same on main 7174f46. The whole German chain is stable ("( [1 Komma 2; 3 Komma 4])"), because the numbers step reads the commas. Not this PR's; filed as #266 (v1.1, since a nightly run can go red on it).
- `1-m Abstand` now reads "ein-Meter Abstand" (main "Ein-Meter Abstand"). Only the capital changes, and the voice reads it the same. Fine.
- `<CI=` now keeps "<" glued ("<confidence interval ="), and `U.S.Figure 5 mg` / `i.e.Table 5 mg` now leave "mg" as a label's number. These are rare shapes and the readings are consistent. Fine.
- German pointer phrases (`z. B. https://… im Netz` → "Daten gibt es im Netz.") are #256's design (pointer chains), and the same on main. Not touched.
