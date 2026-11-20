# Review of PR #132, round 3 (head e4535ae)

Round 2 answer: https://github.com/dubidu22/sci2audio/pull/132#issuecomment-6856186262

## Round 2 items: checked

- (a) "00±¸C" reads "00 plus or minus Ç" on both runs; "x = ¸C" and "¨o = 3" too. "C¸ = 3"
  (accent after the letter) stays as printed on both runs, since the Unicode step does not join
  it either.
- (b) "00×=0" and "3 ×= 2" read "times equals" on both runs.
- CI on e4535ae: tests green on Linux, macOS and Windows; the browser job failed once on the known
  keyboard flake (#138, no web change in this PR) and passed on its re-run.
- Fast suite here: 2610 passed, 55 snapshots. All earlier hand-made inputs: no second-run change.

## New: one more second-run case (nightly profile, fresh database)

`test_the_step_keeps_the_contract_on_any_document` (`tests/unit/test_textprep_numbers.py`):
block `"3 × 10−4⁻⁴"`. Run 1 reads "4⁻⁴" as a signed power (`_SIGNED_POWER`: the "−" before the
base is not in its lookbehind, and `_JOINED_BEFORE` knows "-" but not "−"), giving
"3 × 10−4 to the power of minus 4". Run 2 then reads "10−4" as a times-ten power:
"3 × 10 to the power of minus 4 to the power of minus 4".

Suggested fix: a base right after a number and a minus sign is joined (add U+2212 to
`_JOINED_BEFORE`'s dash class, or to the bases' lookbehinds), so "10−4⁻⁴" is left as printed,
like "10-4⁻⁴". Add the case as a unit test that runs the step twice.

Everything else is clean. After this fix, CI green and one nightly round of runner, numbers and
statistics, I merge #132 and then KB #38.
