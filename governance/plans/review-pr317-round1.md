# Review of PR #317, round 1 (#313, deep German nest timing after #300; D-568)

Heads: a194614 (on main 405c2b6); then I merged main 57f9fd2 in with update-branch, giving efd24b6.
Result: **approved**. Merge once CI is green on Linux, macOS and Windows.

## What it does

`_identifiers_only` keeps the leaf-bracket check as printed. A bracket with inner brackets is rebuilt (`_read_inside`) only when its own text, outside the inner brackets, holds a run of five digits, which every identifier needs. The check for lead words left after a cut (`_cut_inside`) now runs before `_only_lead_left`, which is the cheaper order.

## Correctness

- The five-digit test is a necessary condition, so it never skips a bracket that could be identifiers. A digit run split by an inner bracket ("(527(x)794)") cannot be an identifier after the rebuild either, because the rebuild writes blanks in place of the inner bracket. Gluing the own-text segments together without a separator can only give false positives, which cost time but never change a reading.
- Before #317, the raw-inside identifier match on a bracket with inner brackets always failed, because "(" is not an identifier character. Dropping it changes nothing.
- Readings are identical to main 405c2b6. I compared the two-run output of 20,000 seeded random token texts (en and de, 30% wrapped in up to 6 extra brackets) byte for byte, plus my 300+ hand probes from the #300 review.

## Cost (Linux, best of 3, CPU time, links + citations, de)

| head | plain deep nest ratio | deep nest around identifier |
|---|---|---|
| 1cbed9b (before #300) | 6.4 | 5.3 |
| 405c2b6 (main with #300) | 11.3 | 11.6 |
| a194614 / efd24b6 (#317) | 5.7 / 6.0 | 5.9 / 5.8 |

A nest with five digits at every level, or with an identifier and citation at every level, is linear: 0.10 → 0.23 s and 0.06 → 0.32 s from 2k to 16k levels, against 0.04 → 0.33 s for plain citations. The new test (`…around_an_identifier…`, limit 16) passed 3 of 3 times under -n 8.

## Runs

- Fast suite on a194614: 4630 passed. On efd24b6: 4672 passed, 1 skipped.
- CI: see the merge message.

## Lesson for my own #300 review

In round 3 I measured the deep identifier nest at 2× main and judged it sublinear, so acceptable. With limit 16 and a baseline ratio of about 6, 2× is enough to cross the limit on slower runners. A new cost on a capped shape should be compared with the test's limit, not only checked for linearity.
