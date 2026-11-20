# Review of PR #311, round 2 (#303, German glued dates; D-562, D-567)

Heads: 28b85a4 (fix), 4434849 (main 57f9fd2 merged in), then fe305aa (I merged main e9167e3 in with update-branch).
Result: **approved, merged by squash.**

## R1-1 fixed

A hyphen between two full dotted dates reads as a range, and the second date takes "-en" as after an en dash. Every shape below reads the same on a second run.

| printed | PR |
|---|---|
| `Laufzeit 1.1.2020-31.12.2020` | `erster Januar 2020 bis einunddreißigsten Dezember 2020` |
| `Vom 3.4.2019-5.4.2019` | `dritten April 2019 bis fünften April 2019` |
| `Vom 03.04.2019-05.04.2019` | same |
| `Vom 3.4.2019-5.4.2019-7.4.2019` | three dates joined by "bis" |
| `(1.1.2020-31.12.2020)`, `…, dann`, `…. Dann`, `…-Projekt` | range read |
| `…-5.4.2019-06`, `…-31.2.2020`, `…-5.4.2019 kg`, `…-5.4.2019x` | the first date is read, the rest stays as printed, as on main |

The D-562 shapes (`3.4.2019-03-12`, `-2020`, `-03`) still stay as printed. The D-567 shapes are unchanged from round 1.

## Accepted with an issue

- `Vom 3.4.2019-5.4.` (yearless end) now reads nothing; main read the first date. It is a rare shape and stable. Filed as **#318** (v1.2) together with `3.4.-5.4.2019`, which main already reads only in half.
- `Am 3.4. 1/2 Tag` is #310, the same on main.

## Runs on fe305aa

- Fast suite: 4687 passed, 1 skipped. No snapshot change against main, so the corpus is byte-identical.
- Own nightly seeds 2 (the issue's seed), 77 and 4242 on the German numbers file and the German regression file: 361 passed each.
- CI: all 12 checks green, including the Ubuntu, macOS and Windows tests. Main e9167e3 is green after #317.
- 47 hand-made date shapes, PR against main: the only second-run change is #310.
