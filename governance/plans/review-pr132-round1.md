# Review of PR #132 (#67 numbers, dates and statistics), round 1

Reviewer thread "Review operators and exponents PR 132", 13 Nov 2026. Head reviewed: `1c037a1`
(contains main `1064e18`). Decisions checked against D-176 to D-191 (plan
`plans/issue67-numbers-dates-plan.md` section 5 A to P) and D-230, D-236, D-242 (#68).

## What was checked

- The whole diff (15 files): `notation.py`, `numbers.py`, `statistics.py`, the `characters.py`
  stray-accent change, registry order, tests, regression cases, both snapshot files, the slow
  ASR test.
- `ruff check`, `ruff format --check`, `lint-imports` (3 contracts kept), `deptry src`: clean.
- Fast suite: 2283 passed, 54 snapshots passed.
- Nightly Hypothesis profile (2000 examples) over every `textprep` unit test: all #67, runner,
  steps, characters and units tests pass. One failure, in `test_textprep_citations.py`, is
  pre-existing on main and not touched by this PR (see item 6).
- CI on `1c037a1`: all 12 checks green (tests on Linux, macOS, Windows, browser, lint and
  layers, licences, security, CodeQL).
- Corpus: the script of all 7 papers, main against this PR, diffed sentence by sentence (84 changed
  lines). Every change follows a decision: "=", "≤", "≥", "≫", "±" in maths prose (Nowak, Liu),
  "lines 11 to 18", "Rows 2 to 9", "1 to 2 days", "1 tenth the size", "CC BY-NC-SA 4 point 0",
  "(minus 1)", "equals" in the seaborn code. Nothing lost, nothing doubled.
- About 200 hand-made inputs through all built-in steps, each run twice to check idempotence.
- Long blocks (the S2 check from the #103 review).

## Must fix

### 1. Both steps take quadratic time on long blocks

Several rules look back by searching the whole text before each match:
- numbers: `_JOINED_BEFORE.search(text, 0, c.start)` in `_unjoined` and `_powers`, `text[:start]`
  in `_range_reason`, `text[: match.start()]` in `_counts` (then `_AFTER_OPERATOR.search` and
  `_PREVIOUS_WORD.search` over it), `_TIME_BEFORE.search(text, 0, ...)` in `_is_time`, and
  `_UNIT_CHAIN.search(plain, 0, ...)` in `_powers`.
- statistics: `plain[:start].rstrip()` for every operator, `_AFTER_PERCENT.search(plain, 0, start)`
  for every "CI", and the list of every tag scanned again for every operator.

Measured on this machine (one block each):

| Text (about 100,000 characters) | numbers | statistics |
|---|---|---|
| the PR's own `test_a_long_block_is_quick` text | **17.9 s** | 0.1 s |
| reference-like lines ("Journal 8:64–77, pp. 123–145.") | **11.7 s** | 0.0 s |
| results prose ("t(34) = 2.45, p = .021, F(2, 57) = 4.31, p < .001, 95% CI [1.2, 3.4].") | 0.1 s | **3.3 s** |
| maths prose ("0 ≤ i ≤ k ≤ N and w = w1 · · · wN with G = (N, Σ, S, R, p).") | 0.1 s | 2.1 s |
| "1–" × 50,000 | **110 s** | |
| "Phase " + "I/" × 30,000 | **111 s** | |
| "2^" × 50,000 | **108 s** | |
| "a = " × 25,000 | | **19 s** |
| "95% CI [" × 12,000 | | **15.5 s** |
| "<i>" × 30,000 | | **41 s** |

`test_a_long_block_is_quick` passes only because it has no time limit: it took 17.6 s in the
fast suite. The other text steps assert a bound (`test_textprep_units_abbreviations.py`: under
3 s with `@pytest.mark.timeout(60)`; citations and links: under 5 s).

Fix: bound every look-back to a short window before the match (a slice of the last few dozen
characters, or a fixed-width lookbehind in the pattern), find the left operand of an operator
without copying the text before it, and test tags with a single pass (for example a set of
positions inside tags, or `bisect`). Then assert a time bound in `test_a_long_block_is_quick`
(under 3 s, with a timeout mark) and add the same test for `statistics`, plus a parametrized
pathological test with at least "1–" × 50,000, "2^" × 50,000, "a = " × 25,000 and "<i>" × 30,000.

### 2. A glued "CI" and its bracket run into the words around them

`95%CI[1.2,3.4]` is read `95%confidence interval1.2 to 3.4`. The "CI" replacement is not padded and
removing the "[" glues "interval" to "1.2". Pad the "CI" words (as `padded` does for operators) and
keep a space where the removed opening bracket stood between a word and a number. Add the case
to the unit tests.

## Should fix (or an issue)

### 3. A Roman numeral after an abbreviated keyword is read only on a second run

`Fig. II` reads `Figure II`; running the steps again on that script gives `Figure 2`. The same
for `Exp. II`. The abbreviations step (#68) writes "Figure" after R1 has already run. This is
the only case I found where the built-in steps together are not idempotent. Add the abbreviated
forms of R1's keywords that the abbreviations step expands (Fig., Figs., Tab., Tabs., Sec., Secs.,
Sect., Sects., Ch., Chap., Exp., App.) with their full stop. Small and in the spirit of D-185, so I would fix it here.

### 4. "=" next to some maths symbols is left while the rest of the sentence is read

Liu: `vF equals 3.6 electronvolt angstroms and ∆ = 0.883 electronvolts` ("∆" is U+2206
INCREMENT, a symbol, not a letter); Nowak: `W = ⟨A, ⊕, ⊗, 0, 1⟩` and `⟨ρˆ⟩ = ρ0` stay. The voice reads
"=" through espeak-ng, so what is heard barely changes, but the script is inconsistent. Add ∆, ∇,
∞ and the angle brackets ⟨ ⟩ to the operand character sets, or file an issue.

### 5. Trailing zeros in a label or a version number

`Section 3.10`, `Figure 2.10`, `Table 3.10`, `Eq. 2.10`, `Python 3.10` read "3 point 1 0".
misaki alone says "three point one", which names another section, so D-184 is still an
improvement, but a label number is no decimal. No change needed now: please file a follow-up
issue (milestone v1.1 unless you see it often in the corpus).

## Pre-existing, not this PR

### 6. Nightly property of the citation step fails on main

`test_no_citation_is_left_and_no_word_is_lost` (`tests/unit/test_textprep_citations.py`) fails
under the nightly profile with `[12]. [12]. [12]. ( see Smith (2019))`: the citation step alone
reads it as nothing. The same on main (`1064e18`). "It holds. (see Smith (2019))" reads "It holds.".
Either the bracket rule (D-172) or the property is wrong. Filed as #145; it does not block this PR.

## Nits (no change required)

- `t (34) = 2.1` (a space before the df parenthesis) is not read "of 34"; `X2(1) = 3.84` reads
  "X2 of 1" while S3 reads `χ2` as "chi-square". Could go in the issue of item 5.
- `Call 555-1234 now.` reads "555 to 1234": a phone number taken for a range. Rare in papers.
- 178 set-aside numbers edits on the corpus, almost all page ranges inside reference lists. That
  is how every inline step behaves next to the reference-list step today.

## Checked and fine

D-177 operator readings and the arrow and doubled-sign exclusions; S2 with one, two numbers and
"N = 120"; S3 partial eta in both orders and math-italic letters; S4 intervals with "−", ";" and
round brackets; S5 only before an operator ("the OR operator" stays); N1 including "(−1)" and
"−40°"; N2 with line breaks, years and "COVID-19", "3-1", ISBNs, "1-2-3" left; N3 year words,
round hundreds, "In 1984 people"; N5 caret, braces and parentheses, "x²+1"; N6 skips units
and "mc²"; N7 times with "at", "am", "h", "6:00 to 7:00", "O157:H7"; N8 halves to tenths and
"out of"; N9 invalid dates left; N10 thin and no-break spaces, one plain group left; R1 with
"Henry VIII", "the part I think", "IIa", "Type-I", ranges and lists. Every edit is `replace` or
`remove`, never `ask`; every reason quotes the printed text. The registry order matches D-190 and
the `characters.py` widening keeps every #65 test.
