# Review of PR #593, round 2 (textprep batch B5)

Reviewed head: **5b6c114** (fix commit on 6b75aa1). Answer: `plans/answer-pr593-round1.md`.
**Verdict: CHANGES REQUESTED, tests only.** Two test items (T1, T2), no code change. Round 3 is then a short final check before the merge.

## Round 1 items: all fixed

| item | check |
|---|---|
| F1 long arrows | `−−→`, `←−−` and `←−−→` give one arrow on both runs, en and de. My probe files s1, s2, s4 and s5 now have 0 unstable lines (6b75aa1 had 8, one of them also on main). |
| F2 German neighbours | `arrowgrid.py`: **0 unstable** (6b75aa1: 562). `↔` is in `_MATHS_SIGNS`. The seed-31337 `@example` is pinned. |
| F3 clock exception | two spaces, tab and newline before `Uhr` are stable. `13 Uhr 30. Jahr` (#253) is unchanged. |
| F4 survivors | `←`/`↔` were dropped from `_MINUS`, and the `]`/`}` fraction cases and `211 hundert`/`5 hundert` cases were added. My hand mutants for these are now killed. |

## Final-round checks on 5b6c114

- **Three systems:** CI run 44447392863 (workflow_dispatch on the head) is green on `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)`. `CI passed` is green.
- **Nightly seeds** (nightly profile, the number and citation test files en and de): 2024 and 8080 are green (1,008 passed each). The author ran 31337 on the German second-run test.
- **Corpus:** all 39 scripts (13 sources × 3 settings) are identical to 6b75aa1. The round-1 diff against main still holds: nowak only, 6/17/17 lines.
- **Probes:** 0 second-run differences over my 70 probe lines and the 840-text arrow grid.
- **Mutation workflow** (each run with its baseline passed):
  - `notation.x_arrows*` and `x__one_arrow*` (run 44447812433): 25 of 25 killed.
  - `citations.xǁ_Rulesǁ_dated_period*` (run 44447903076): 32 of 32 killed.
  - `notation.x_as_one_arrow*` (run 44449290059, German tests): 9 killed, 2 survived (see T1 and the accepted list).
  - `numbers_de.x__ordinals*` (run 44447870680): 169 killed, 44 survived. Four of those are on lines this PR touches (T2 and the accepted list). The other 40 are on lines main already has, filed as **#606**.
- **My hand mutants** on the new code (25, targeted unit and regression tests, ci profile): 22 killed. Two survivors are real: `mask-first-only` (T1) and `uhr-window-12` (accepted below). The third, `mask-space`, is equivalent on the grid (accepted below).

## Findings

### T1 (required): no German test has a right arrow, or two arrows, before a number rule
Two mutants of `as_one_arrow` survive, and each gives wrong text:
- Masking with the arrow's first glyph (`−→` becomes `−−`): `x −→1:1` reads `→1:1` on run 1 and `→1 zu 1` on run 2. That is a second-run break, with 24 unstable texts on the grid.
- `pieces = [...]` for `pieces += [...]` (mutmut 7): with two arrows in a block the masked text gets shorter, and other rules' spans land in the wrong place. `x −→1:1 und y −−→3/4 und z −→3-5` reads `x →1:1 und y bis →3/4 …`.

Every F2 test has one left arrow, so neither mutant is noticed.
**Add** to the German `test_a_second_run_reads_nothing_new`: `("x −→1:1 und y −−→3/4 und z −→3-5", "x →1 zu 1 und y →3 Viertel und z →3 bis 5")`. I checked that this is the head's reading on both runs and that it kills both mutants.

### T2 (required): a guard's `continue` turned into `break` survives on the two guards this PR adds or changes
`_ordinals` mutmut 60 (the `_AFTER_UHR`/`_CLOCK_UHR` guard) and mutmut 74 (`_AFTER_HUNDRED`) stop reading every later ordinal in the block, and no test notices.
**Add** to the same list:
- `("13 Uhr 30. Jahr und am 3. Mai", "13 Uhr 30. Jahr und am dritten Mai")`
- `("im Jahr 19 hundert 98. Jahr und am 3. Mai", "im Jahr 19 hundert 98. Jahr und am dritten Mai")`

These are the head's readings, fixed points, and they kill 60 and 74 respectively. I checked both.

### Accepted, no change
- `as_one_arrow` mutmut 2 (`at = None`): `text[None:i]` is `text[:i]`, so it is equivalent.
- `mask-space` (pad with spaces, not the arrow glyph): 0 unstable on the 840-text grid. No German rule looks at `←`/`→` before a number. It is equivalent for today's rules.
- `_UHR_WINDOW` 24 → 12 (hand mutant): it differs only when 8 or more whitespace characters stand between the clock and the number. I accept that.
- `_ordinals` mutmut 71 (`_AFTER_HUNDRED` window start `max(1, …)`): it only matters for a printed `19 hundert 98.` at block start, which a year reading never writes. Mutmut 73 (`- 17`): the pattern is at most 11 characters. Both are equivalent in practice.
- English `b ←−−1` reads `←1`, and `←`/`↔` are dropped from the minus look-behind: both choices agreed.
- `um 13:30\nUhr 3. Mai` is pinned as a fixed point in the step-level test. Through the whole chain it still reads `Uhr` twice, so #594 stays open.

## For round 3
Push one fix commit with T1 and T2 only (tests). I will run the three-system CI on that head, check the two mutants again, and merge pinned to it if all is green. No `ci:full` label is needed. Main has moved by #582 (CHANGELOG.md only). MRG-03 needs no update unless GitHub shows a conflict.
