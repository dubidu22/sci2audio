# Plan: issue #67, numbers, dates and statistics in English (TP-09, TP-11, TP-13)

Thread "Read numbers, dates and statistics", 13 Nov 2026. Builds on the text-step interface
(PR #83, a57d135), the cutter (PR #86, 006c964) and the Kokoro voice (PR #88, 061e4e3).
Written alongside PRs #94 (#64) and #98 (#65), which are in review, and the #66 plan.

**Critical: yes.** The PR changes golden files: `tests/regression/english.toml` (the
`expected` of three audit cases changes, one case changes owner, about 20 cases are added),
the per-category corpus snapshot and #70's script snapshot (`test_app_corpus.ambr`). **No
change to core dataclasses, the layer contract or the text-step interface.** Label
`risk:high`. No new dependency (standard library `re` and `unicodedata`).

## 1. What the voice already reads (measured, not assumed)

D-54 leaves ordinary numbers to misaki. I ran the voice's real front end as #18 uses it:
Kokoro's `KPipeline(lang_code="a")`, which is misaki with spaCy `en_core_web_sm` **plus the
espeak-ng fallback** for words misaki does not know (no model needed for phonemes). misaki
alone gets much more wrong than the full pipeline, so the fallback matters: it reads "=",
"≤", "≥", "≠", "±", "−3" and Greek letters. The table lists what the voice gets right and
what it gets wrong; the "rule" column is what this plan proposes.

| Input | The voice says | Right? | Rule |
|---|---|---|---|
| 1,234 · 10,000 · 12,345.67 · 0.001 · .05 · 4.2 | as written, in words | yes | none |
| 1st, 21st, 100th · 12% · 1-2% (the % part) | first, twenty-first, ... percent | yes | none |
| 2019 · 1990s · '90s · mid-1990s · 21st century | twenty nineteen, nineteen nineties, ... | yes | none |
| 12 March 2019 · March 12, 2019 | as written | yes | none |
| 1000, 5000 examples · 1100 cells · 1200 ms | one thousand · eleven hundred · twelve hundred | yes | none |
| GTX 1080 Ti · In 1892 · 2000 | ten eighty · eighteen ninety-two · two thousand | yes | none |
| n = 35 · β = .3 · ±12 · −3 · ≥ 18 · ≠ | equals · beta · plus or minus · minus three · "greater or equal to" | mostly (no "than") | S1 (explicit) |
| p **<** .05 · x **>** 3 | **nothing**: "p point zero five" | **no** | S1 |
| t(34) = 2.45 | "t ... equals two point four five" (**34 is dropped**) | **no** | S2 |
| F(2, 57) · χ2(1) | "F two fifty-seven" · "chi two one" | no | S2, S3 |
| R2 · η2 · R² · η² | "R two" · "eta two" | no | S3 |
| 95% CI [1.2, 3.4] | "ninety-five percent C I one point two, three point four" | partly | S4 |
| OR = 1.5 (odds ratio) | "**or** equals one point five" | no | S5 |
| 1234 · 1999 · 1905 · 2050 · 3615 participants | twelve thirty-four · nineteen oh five · ... (**every bare 4-digit number is a year**) | no | N3 |
| **−.32** (minus sign U+2212, no leading zero) | "minus [pause] thirty-two" (**point lost**) | **no** | N1 |
| 3–5 · 3 – 5 · 18-25 · 2010–2015 · 1-2 days | "three five" · "eighteen twenty-five" | no | N2 |
| **1.2–3.4** | "one [pause] two three [pause] four" (**both points lost**) | **no** | N2 |
| 2.50 · 1.00 · 3.0 | "two point five" · "one" · "three" (**trailing zeros dropped**) | no | N4 |
| **10⁶** · **10⁻⁴** · 10^6 | "**one hundred six**" · "ten" · "ten six" | **no** | N5 |
| x² · m² | "x two" · "m two" | no | N6 (x²), #68 (m²) |
| 3:1 ratio · 1:100 dilution | "three [colon] one" | partly | N7 |
| 1/2 · 2/3 · 1/10 the size · 17/20 | "one two" · "one ten the size" | no | N8 |
| World War II · Phase III · Type II error · Henry VIII | "World War I I" · "Phase I I I" | no | R1 |
| 2019-03-12 | "twenty nineteen zero three twelve" | no | N9 |
| 12/03/2019 · 10:30 · 0,5 (decimal comma) | digits as written | partly | none (section 4) |
| 50 000 (space as thousands separator) | "fifty zero zero zero" | no | N10 |

Every replacement text proposed below was checked through the same front end and reads as
intended ("t of 34 equals 2.45", "1.2 to 3.4", "minus .32", "1,234 participants",
"10 to the power of minus 4", "1 tenth", "World War 2", "chi-square", "R squared").

## 2. What the corpus holds (layout output of main, 1,224 blocks)

The seven corpus papers are computer science and physics; they have **no p values, no df
parentheses and no CI**. What they do have, outside furniture, formula and table blocks:
130 comparison operators (nearly all inline maths: "0 ≤ i ≤ k ≤ N", "G = (N, Σ, ...)", one
"< 5%", "Y, Z ̸= S" with the combining stroke PDFs give for ≠), 183 number ranges with an
en dash (almost all page ranges in reference lists), 11 with a hyphen ("Rows 2-9",
"1-2 days"), 1 fraction ("roughly 1/10 the size"), 0 superscript characters (PDFium gives
them as plain digits), 38 four-digit numbers that are not years (page numbers in references,
"select 1000 examples", "GTX 1080 Ti"). So the statistics rules are tested with written
cases (the audit sample's style), and the corpus snapshot mostly shows the operator and
range rules.

## 3. Design

Two inline steps in the category **Numbers, symbols, units and statistics** (D-108), one
module each, English only (`languages = ("en",)`):

| Step id | Module | What it proposes |
|---|---|---|
| `statistics` | `textprep/statistics.py` | operators, df parentheses, squared statistics, CI, OR (S1 to S5) |
| `numbers` | `textprep/numbers.py` | minus, ranges, four-digit counts, trailing zeros, exponents, ratios, fractions, ISO dates, grouped digits, Roman numerals (N1 to N10, R1) |

Both skip furniture blocks and the placeholder kinds (table, formula, figure), which other
steps claim whole. Every change is a `replace` edit (never `ask`, never `remove` of
something spoken) whose reason quotes the printed text, so the report names exactly what
changed (design principle: everything referenceable), e.g. `"<" read as "less than"`,
`range "3–5" read as "3 to 5"`, `"1234" read as a number, not a year`,
`Roman numeral "III" after "Phase" read as "3"`. Digits stay digits wherever misaki reads
them correctly (D-54): the edits change the symbols around numbers, not the numbers.
Replacement texts carry their own spaces (" less than "), since `spoken_text` collapses
white space. Patterns compare letters after NFKC per character, so math-italic letters
("𝑝 < .05", "𝜂2") are matched too; #65's math-letter fix runs later and loses the overlap
to these edits, which already contain the plain letter.

### 3.1 `statistics` (TP-11)

- **S1 Operators.** `=` equals, `<` less than, `>` greater than, `≤ ⩽ ≦` less than or equal
  to, `≥ ⩾ ≧` greater than or equal to, `≠` and `̸=` not equal to, `±` plus or minus, `∓`
  minus or plus, `≪` much less than, `≫` much greater than. Applies where the symbol stands
  between two operands or before one ("p<.05", "± 12%", "≥ 18"); not inside an arrow or a
  doubled sign ("->", "<-", "=>", "<=>", "<<", "=="), which are left as printed. In
  inline maths this reads "0 less than or equal to i", which is what the voice already
  says minus the missing "than".
- **S2 Degrees of freedom.** A test statistic (t, F, r, H, U, W, z, χ2/χ², G) directly
  followed by a parenthesis of one or two whole numbers and then an operator: "(34)" becomes
  " of 34", "(2, 57)" becomes " of 2 and 57". One edit over the parenthesis.
- **S3 Squared statistics.** R², r², η², ηp²/η²p, ω², and χ²; with a plain 2 (as PDFs give
  them: "R2", "η2", "χ2") only when an operator or a df parenthesis follows: "R squared",
  "eta squared", "partial eta squared", "omega squared", "chi-square". One edit over the
  name and its 2.
- **S4 Confidence intervals.** "CI"/"CIs" after a percentage ("95% CI") or before "[", "(",
  "=" or ":" becomes "confidence interval(s)"; a bracketed pair of numbers right after it
  ("[1.2, 3.4]", "(−0.5, 1.1)") becomes "1.2 to 3.4" (brackets removed, the comma read
  "to"). Elsewhere "CI" is left to the voice, which spells it.
- **S5 OR.** "OR" before an operator becomes "odds ratio" (the voice reads it as the word
  "or"). Other statistic letters (M, SD, SE, HR, RR, IQR, df, AUC, n, N, p) are left as
  printed: the voice spells them correctly (criterion 1).

### 3.2 `numbers` (TP-09, TP-13)

- **N1 Minus sign.** U+2212 "−" (and U+2012 figure dash) right before a number or a decimal
  point, with nothing or a space after it, becomes "minus "; not before an arrow ("−→").
  The ASCII hyphen-minus is left to the voice, which reads "-3" and "-.32" correctly.
- **N2 Ranges.** Number, then an en dash, figure dash or an unspaced em dash (spaces
  around the en dash allowed), then a number: the dash becomes " to " ("3–5", "1.2–3.4",
  "2010–15", "−3–3"). With a hyphen-minus only between plain numbers that are not part of a
  longer chain ("18-25", "Rows 2-9", "1-2%"; not "2019-03-12", "978-0-201", "COVID-19").
  A dash followed by a line break is included in the edit, so #65's hyphen step (later)
  loses the overlap and does not keep a hyphen there.
- **N3 Four-digit counts.** misaki reads every bare four-digit whole number as a year. The
  step writes it with a thousands comma ("1234" → "1,234", read "one thousand two hundred
  thirty-four") when the context says it is a count: (a) after an operator ("n = 1234"), or
  (b) followed by a lowercase plural word ("participants", "pages", "cells", "people",
  "children", "data") and not preceded by a year word ("in", "since", "from", "until",
  "by", "during", "of", "the", "this", "that", "these", "early", "mid", "late", a month,
  a season). Round hundreds (1000, 1200, 5000) are left alone, since both readings are
  right ("select 1000 examples" gets no edit).
- **N4 Trailing zeros.** A decimal number whose fraction ends in 0 with a digit before the
  point ("2.50", "1.00", "3.0") loses the zeros in misaki; it becomes "2 point 5 0". A
  leading-point number (".050") is already read digit by digit.
- **N5 Exponents.** A number followed by superscript digits ("10⁶", "10⁻⁴"), or by "^"
  ("10^6", "10^-4", "2^{10}"), becomes "10 to the power of 6" / "... of minus 4". With
  plain digits, as PDFs give it, only right after "×" or "x" between numbers and with an
  explicit minus ("3 × 10−4"), since "104" alone could be a number. The "×" itself is #68's.
- **N6 Powers of a letter.** A single letter or Greek letter standing alone, followed by
  "²" or "³" ("x²", "σ²"), becomes "x squared" / "cubed"; other superscript digits "to the
  power of n". Not after a number and a space ("5 m²"): that is a unit, #68's.
- **N7 Ratios.** Number colon number that is not a time ("3:1", "1:100", "2:3") becomes
  "3 to 1". A time is H:MM with MM 00 to 59 after "at", "from", "until", "by", "before",
  "after", or before am/pm/h: left alone (the voice reads "ten thirty").
- **N8 Fractions.** Whole numbers N/M, not part of a date, path or longer chain, and not
  both of four digits ("2019/2020"): with M from 2 to 10 and N < M, the slash and M become
  a fraction word ("1/2" → "1 half", "2/3" → "2 thirds", "3/4" → "3 quarters", "1/10" →
  "1 tenth"); other N ≤ M become "N out of M" ("17/20" → "17 out of 20"); N > M is left.
- **N9 ISO dates.** YYYY-MM-DD with a valid month and day becomes "12 March 2019".
- **N10 Grouped digits.** Groups of three digits separated by a thin, narrow no-break or
  no-break space ("50 000") become one number with commas ("50,000"); with a plain space
  only when there are at least two groups ("1 000 000"), since "Table 2 000" style
  collisions are possible with one.
- **R1 Roman numerals (TP-13).** An uppercase Roman numeral I to XXXIX after one of these
  words (any case): War, Phase, Type, Class, Stage, Grade, Level, Tier, Part, Chapter,
  Volume, Book, Section, Appendix, Study, Experiment, Trial, Table, Figure; becomes its
  number in digits ("World War 2", "Phase 3", "Type 1 error"). Regnal names ("Henry VIII")
  and bare numerals are left alone.

## 4. Left to the voice or out of scope (no edit)

Ordinary numbers, decimals, percentages, ordinals, years, decades and written dates (all
read right, criterion 1). Slash dates ("12/03/2019": day or month first is unknowable),
times ("10:30"), decimal commas ("0,5", rare in English text), Greek letters on their own
(the voice says "alpha", "beta"), units and m², s⁻¹, %, ≈, ~, ×, °, µ (all #68).

## 5. Decisions for the coordinator (please assign D-numbers)

- **A. Scope principle.** Edit only where the voice's real front end (misaki plus the
  espeak-ng fallback, measured in section 1) reads wrong, plus S1. Alternative not chosen:
  writing every number as words (against D-54; misaki reads them better than a rule).
- **B. S1 for all operators, not only the silent "<" and ">".** The issue asks for them
  "read as words"; an explicit script does not depend on espeak-ng's wording ("greater or
  equal to", no "than") or on its being installed, the regression cases can pin it, and
  read-along and the report show what is said. Alternative: edit "<" and ">" only.
- **C. Split with #68.** #67 takes the comparison operators including ± (TP-11), the minus
  sign, exponents and powers of a single letter; #68 keeps %, ≈, ~, ×, °, µ/μ and units
  with their powers (m², s⁻¹). Greek letters stay with the voice except inside S3. The
  `symbols` regression case (≥ 18, ± 12%) moves from `issue = 68` to `issue = 67`; its "vs."
  is covered by #68's `abbreviations` case. I tell the #68 thread when it starts.
- **D. Degrees of freedom read "t of 34"** (and "F of 2 and 57"). Alternative: "t with 34
  degrees of freedom" (clearer to a newcomer, but three times as long in a results section).
- **E. CI** as in S4, including the bracketed interval read "1.2 to 3.4". Alternative:
  expand "CI" only and leave the brackets (the voice reads "one point two, three point four").
- **F. OR** becomes "odds ratio" only before an operator; no other statistic letter is
  expanded (the voice spells them). Alternative: expand M, SD, SE as words (not what
  researchers say aloud, and a matter for #68's abbreviation list if wanted).
- **G. N3 four-digit counts** with the context rule as written; round hundreds untouched.
  Alternative: every non-year-context four-digit number as a cardinal (wrong for "the 2019
  guidelines", "GTX 1080").
- **H. N2 ranges read "to"**, hyphen ranges only between plain numbers. Alternative: en
  dash only (misses "18-25", "Rows 2-9", common in prose).
- **I. N4 trailing zeros** kept ("2 point 5 0"): the printed precision is part of the value
  (D-57, faithful text). Alternative: leave to misaki.
- **J. Roman numerals in v1.0** (TP-13 is a Should; D-113 left it to #67) with the keyword
  list of R1. It is small, it is audit case 11, and "Type I/II error" is common in
  statistics. Alternative: defer to v1.1 (case stays as it is).
- **K. N7 ratios and N8 fractions** as written. Alternative: leave both to the voice (only
  one fraction in the corpus, but "one two" for "1/2" is wrong).
- **L. N5 and N6 exponents and powers** as written. Alternative: leave superscripts to #64
  (formula notices only cover formula blocks, not inline maths).
- **M. N9 ISO dates only** become words; slash dates, times and decimal commas are left
  (section 4).
- **N. N10 grouped digits** as written. Alternative: thin and no-break spaces only.
- **O. Two steps, registry order.** `statistics` then `numbers`, placed after the footnote
  marks (#64) and the citations and links (#66), before abbreviations (#68), and before
  characters and hyphenation, which stay last (D-150). The registry change is two lines in
  `BUILT_IN_STEPS` plus the docstring line, merged with whichever of #94, #98 and #66 land
  first. Alternative: one step (one id in the report for two quite different kinds of
  rule; the report reads better with two).
- **P. Speech-recognition round trip** (criterion 4, #9): one slow test speaks the script of
  the `statistics` regression case through Kokoro and checks with faster-whisper that
  "less than", "equals" and "confidence interval" are heard and that the WER on that
  sentence is under 0.25, after turning symbols and digits in both texts into words (with
  `num2words`, already installed through misaki; test-only use, so no new dependency).
  Runs nightly with the existing ASR test.

## 6. Tests (test-first)

1. **Regression cases first** (`tests/regression/english.toml`): change `expected` of
   `statistics` ("n equals 35", "M equals 4.2 (SD equals 1.1)", "p less than .05, 95%
   confidence interval 1.2 to 3.4"), `symbols` (now issue 67: "(plus or minus 12%) ...
   greater than or equal to 18 years") and `roman-numerals` ("World War 2", "Phase 3");
   `large-number` stays unchanged (misaki reads "1,234"; it pins "no edit"). Add about 20
   cases (`audit = 0, issue = 67`), one per rule and one per "left alone" family: df
   parentheses, squared statistics, OR, minus sign with a leading point, en-dash, hyphen
   and decimal ranges, "1234 participants" and "the 2019 guidelines" (no edit), "select
   1000 examples" (no edit), trailing zeros, exponents, ratio, fraction, ISO date, grouped
   digits, Type II error, ordinary numbers, years and written dates (no edit).
2. **Unit tests** per rule with exact spans, kinds, replacement texts and reasons,
   including the edge cases named in section 3 (arrows, chains, times, regnal names,
   math-italic letters, line break after a range dash).
3. **Conformance:** both steps pass `check_text_step(step, allow_ask=False)` through
   `test_textprep_conformance.py` automatically.
4. **Hypothesis** (ci and nightly profiles, run both), with text strategies weighted
   toward digits, operators, dashes, minus signs, superscripts, colons, slashes and Roman
   numerals (density checked with a probe): no crash; valid, non-overlapping, idempotent
   edits; `statistics` never adds or removes a digit; `numbers` keeps every digit in order
   except the denominator of a simple fraction (N8) and adds digits only for Roman numerals.
5. **Corpus:** the per-category corpus snapshot gains the "numbers-and-units" rows per
   paper; #70's script snapshot shows the new readings (diff explained in the PR).
6. **ASR round trip** as in P (slow, nightly). I run it here once if the model download
   works in this session, otherwise the PR says it waits for the nightly run.

## 7. Size and order of work

About 450 lines of code in two modules, about 700 lines of tests, the regression cases.
One PR, branch `textprep/issue67-numbers-statistics`, `Closes #67`, merged with main as
#94, #98 and #66 land. Then a KB PR with the decisions under the numbers you give.
Follow-up issues: German numbers and statistics (v1.1); slash dates by document locale
(v1.1).
