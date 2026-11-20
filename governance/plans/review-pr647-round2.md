# Review of PR #647, round 2 (final): approved

Reviewer: B13 review thread, 19 Nov 2026. Reviewed head **29fbfbc**: one fix commit on merge b4bc615, which brings in main fac140c with both CHANGELOG lines kept. Author's answer: `plans/review-pr647-round1-answer.md`.

## Fix list check

| Item | Result |
|---|---|
| T1 | new test; kills `x__denominator__mutmut_3` |
| T2 | direct test of `_denominator` with a mark, and a reason that holds: `rows_of` calls it only in the `elif` branch (`element.line` set) and only with `latest` not None, so `texts` is never empty. `_4` killed |
| T3 | bottom edge: new test with exact coordinates. Top edge (`_17`): equivalent, as stated. `fraction_bar` needs the numerator's letters above the bar, and every piece lies inside the line's union, so a bar at `line.y0` is refused anyway |
| T4 | new test; kills `x__fractions_in_order__mutmut_13` |
| T5 | new test; kills `_21` |
| T6 | a denominator in two pieces reads its numerator once; kills `_24`. `_42`/`_43` targeted a dead line, `placed.add(id(lower))`. A lower is never looked at again, because numerators are sought only to its right. The line is removed, with no behaviour change |
| T7 | direct test of `_over` with a mark, and a reason that holds: a group of more than one element holds only text pieces, and `_fractions_in_order` returns a one-element group before it looks at bars. `_over_1`/`_4` killed |
| T8 | inclusive at exactly 1 pt (`fraction_inside` × 10 pt) on both ends, refused at 0.25 pt more; kills `_over_12`/`_13` |

## Final-round evidence on 29fbfbc

- CI: `CI passed`, `tests (ubuntu/macos/windows-latest)` success (ci:full).
- mutmut (mutation.yml run 44508798245, same globs and tests as round 1): 195 killed, 4 survived. Those are `x__denominator__mutmut_17` (equivalent, T3), `x__fractions_in_order__mutmut_9`/`_12` (equivalent, round 1) and `x_rows_of__mutmut_24` (pre-existing, #163).
- Nightly property tests (run 44508800999): success.
- Local: test_layout_paragraphs, test_layout_corpus, the two textprep corpus tests and the figure-speed tests pass on 29fbfbc (338 tests).
- Base move check: `git diff 9f2cbaa 05d76f9` equals `git diff fac140c 29fbfbc` outside CHANGELOG.md, paragraphs.py and test_layout_paragraphs.py; the last two differ only by the fix commit. The CHANGELOG diff is the single #322 line. Goldens are unchanged since round 1, where only liu's two planned sites moved.

## Verdict

Approved. Squash-merge pinned on 29fbfbc onto main fac140c (green on all three systems).
