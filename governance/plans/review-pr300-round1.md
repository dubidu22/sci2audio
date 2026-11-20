# Review of PR #300, round 1 (#285, bracketed grant numbers)

Heads reviewed: b7ecf3e (main 12944c8 merged in; my own local merge and `--snapshot-update` gave a byte-identical tree), then rechecked on 2d77a51 (main 34303e1, #279, merged in). Findings below are as they stand on 2d77a51.
Result: **changes requested**, two blockers (R1-1, R1-2), one finding to fix or defer with an issue (R1-3).

## What holds

- Golden diff against main 12944c8 is exactly the two seaborn grant brackets (block 51, page 4): script line, two report entries, Citations 8 → 10 in the report table and in `test_textprep_furniture.ambr`, two lines in `test_textprep_citations_links_corpus.ambr`, count 328 → 330. Nothing else.
- The D-557 reading is right: misaki/espeak-ng German reads "(12 345)", "(12345)" and "(1 234 567; 12 345)" as whole numbers (zwölftausenddreihundertfünfundvierzig).
- Timing: citations step on 10k vs 40k characters of alphanumeric runs, dash-joined segments, many identifiers with a failing end, funding words, many brackets, long spaces: ratios 3.8–5.0, 160k characters in 0.03 s. `_in_number_bracket` on German thousands: ratio 3.8–4.1, same as main.
- Keeps from the plan hold on both runs: (2019), (12,345), (n = 12345), (OPP-115), (COVID-19), (GPT-3), (ISO 9001), (ISBN …), (doi:…), (arXiv:2101.12345), (PMID 12345678), (p = 0.00001), (12:34:56), (12345.6).
- Removals that look right: (R01MH123456), (5R01MH123456-03), (NCT01234567), (GSE12345), (grant agreement no. 757432), (Grant No. 12345 and Award No. 67890).

## R1-1 (blocker): German thousands after a funding word, or before "-mal"/"-fach", change on the second run

Citations runs before numbers. Run 1: citations sees "12.345" (not an identifier), then N-de-2 reads it "12345". Run 2: citations drops the bracket.

| printed (de) | run 1 | run 2 |
|---|---|---|
| `Gefördert (Projekt 12.345) und mehr.` | `(Projekt 12345)` | `Gefördert und mehr.` |
| `Gefördert (FKZ 12.345) und mehr.` | `(FKZ 12345)` | dropped |
| `Es lief (Projektnummer 12.345) gut.` | `(Projektnummer 12345)` | dropped |
| `Es lief (Grant 12.345) gut.` | `(Grant 12345)` | dropped |
| `Es stieg (12.345-mal) an.` | `(12345-mal)` | dropped |
| `Es lief (12.345-fach) gut.` | `(12345-fach)` | dropped |

On main all six are stable. D-557's `_in_number_bracket` covers only brackets of bare numbers. Whatever the fix (spaces for every thousands number inside a round bracket, or citations taking a grouped German number after a funding word as an identifier on run 1, etc.), these six must be stable on both runs and pinned as tests. "(12.345-mal)" should stay read.

## R1-2 (blocker): a removal next to or inside another bracket changes how that bracket is judged on the second run

| printed (en/de) | run 1 | run 2 |
|---|---|---|
| `As shown by Smith (527794) (2019), it grew.` | `Smith (2019), it grew.` | `Smith, it grew.` |
| `Text (527794) (2019) mehr.` (de) | `Text (2019) mehr.` | `Text mehr.` |
| `Text (Smith, 2019; 527794) more.` | `Text (527794) more.` (the existing partial citation removal leaves the identifier) | `Text more.` |

All three are stable on main 34303e1. (On b7ecf3e a fourth, `(Smith, 2019 (527794))`, also broke; #279 fixed it on 2d77a51.) The PR's Hypothesis properties did not hit these shapes. Fix so that run 1 already gives the run-2 result (or both runs keep the bracket), and add these three as second-run tests in both languages. A Hypothesis strategy that mixes identifier brackets with year and author-year brackets, adjacent and nested, would guard the class.

## R1-3 (fix or defer with an issue): an inner identifier leaves a stub outer bracket

| printed | run 1 |
|---|---|
| `Text (see (527794)) more.` | `Text (see) more.` |
| `Text (cf. (527794)) more.` | `Text (compare) more.` |
| `Text (e.g., (527794)) more.` | `Text (for example,) more.` |
| `Text ((527794); 2019) more.` | `Text (; 2019) more.` |

Stable on both runs, but the listener hears "see", "compare", "for example" with nothing after it. Either remove the outer bracket when nothing but identifiers and pointer words would remain, or defer to a v1.2 issue and link it.

## Judgment calls (no change asked)

- `(12345-12350)` (hyphen range of two five-digit numbers) and `(1e12345)` are dropped. Rare; covered by D-547's accepted edge.

## Runs

- Golden diff on 2d77a51 vs main 34303e1: still exactly the two seaborn grant brackets.
- Fast suite (ci profile, -n 8) on b7ecf3e: 4407 passed, 1 skipped (the author reports 4446 on 2d77a51).
- Own nightly seeds 7 and 2026 on all textprep test files (`-k "not corpus"`): 2058/2057 pass; the failures are not #300's: `3–33–3 −3/3` (numbers step, reproduces on main) and `0:~-↵0` (English, no bracket) → #304 (v1.2); `10^250 000 000` is #210.
- Probe harness: /home/user/probe (shapes through the whole chain twice, PR vs main via PYTHONPATH).
