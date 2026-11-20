# Textprep batch B5: German readings (#536, #557, #483, #527)

Status: **APPROVED (D-774, 19 Nov 01:25Z)** (critical: regression rows in `german.toml` and `english.toml`, and a corpus script change, see 4).
Author: textprep lane thread "Fix German number and citation readings", 19 Nov 2026 ~01:50Z. Base: main ad6b94f (B2 merged, #585).
Read: `next-batches-2026-11-18.md` (rows 536/483/527, B5), issues #536 #557 #483 #527 (all four have acceptance criteria, PLAN-04 met),
CLAUDE.md, `.claude/rules/tests.md`, rules 1.4.7, REVIEW LESSONS in `memory/MEMORY-archive-2026-11-18.md`.

All four reproduce on ad6b94f (probe: `run_steps` twice via `rebuilt_from_script`, de and en):

| issue | input | run 1 | run 2 |
|---|---|---|---|
| #536 | `im Jahr 1998. Jahr` | `im Jahr 19 hundert 98. Jahr` | `… 19 hundert achtundneunzigstes Jahr` |
| #536 (same cause) | `seit 1850. Jahr`, `im Jahr 1998. Auflage` | `18 hundert 50. Jahr`, `19 hundert 98. Auflage` | `fünfzigstes Jahr`, `achtundneunzigste Auflage` |
| #557 | `um 13:30 Uhr 3. Mai` | `um 13 Uhr 30 3. Mai` | `um 13 Uhr 30 dritter Mai` |
| #483 | `(Sommer 2019)`, `(Wintersemester 2019)`, `(Herbst 2020)`, `(Ausgabe 2018)`, `(Stand 2020)` | removed | removed |
| #527 en | `β(0, S, 0) ←− 0 and P′ ←− (I − P)−1 and S −→ ε` | `←minus 0`, `(I − P)minus 1` | same |
| #527 de | same text | as printed (German has no minus rule) | same |

## PR split

**One PR**, `textprep/german-readings-b5`, labels `lane:textprep`, `risk:high`. Closes #536 #557 #483 #527.
Why one: all four are small (each ~5–40 lines of rule code), all in textprep, all add rows to `german.toml`; two PRs would
conflict on `german.toml` and need two review set-ups. Files: `textprep/numbers_de.py`, `textprep/numbers.py`,
`textprep/notation.py`, `textprep/citations.py`, `tests/regression/german.toml`, `tests/regression/english.toml`,
`tests/unit/test_textprep_numbers_statistics_de.py`, `tests/unit/test_textprep_numbers*.py` (en minus tests),
the citations unit test file, `CHANGELOG.md` (one Unreleased line per user-visible fix, D-768). Not touched: `utterances.py` (B6), anything in `web/`, `extraction/` (B8).

Earlier PRs in this batch that built on a model this PR changes: none (first PR of B5). Earlier rules this PR revisits: the
`_AFTER_UHR` ordinal guard (#253) and the `_YEAR_LIKE` ending fallback (#265, D-646), both kept, see 1 and 2.

## 1. #536 a year read in hundreds before ". Noun"

**Cause.** `_years` reads `1998` as `19 hundert 98` and leaves the full stop. On run 1 `_ordinals` refuses `1998.` (a four-digit
year with no word that sets the ending ends its sentence, `_YEAR_LIKE`, #265). On run 2 the text is `19 hundert 98. Jahr`:
`98` is not year-like, so the noun fallback (`_NOUN_ENDINGS["Jahr"]`) reads `achtundneunzigstes`.

**Change.** `_ordinals` skips a number right after a year read in hundreds: new guard `_AFTER_HUNDRED = (?<![\d.,])1[1-9] hundert \Z`
(the shape `year_words` writes, same as `_HUNDRED_BEFORE`), beside `_AFTER_UHR`, `_AFTER_HOCH`, `_AFTER_PUNKT`. Both runs then
read `im Jahr 19 hundert 98. Jahr` (the year, then a sentence end), the reading run 1 already gives and the one #265 chose
for `Das war 2019. Kapitel 3`.

**Not changed.** Real ordinals: `das 98. Jahr` → `das achtundneunzigste Jahr`, `am 3. Mai` → `am dritten Mai`,
`das 1998. Jahr` → `das tausendneunhundertachtundneunzigste Jahr` (no `hundert` before; unchanged, pinned).

## 2. #557 a time with "Uhr" before a date

**Cause.** `_AFTER_UHR` (#253) skips an ordinal right after `Uhr `; it exists for run 2 of `13:30. Jahr`, which reads
`13 Uhr 30. Jahr`, where the number after `Uhr` is the minutes. On run 1 of `13:30 Uhr 3. Mai` the printed `Uhr` is the
time's own word and `3.` is a day, but the guard skips it too. Run 2 sees `13 Uhr 30 3. Mai`, no `Uhr` right before `3.`,
and reads `dritter Mai`.

**Reading chosen: `dritter Mai`** on both runs. AC 3 asks for the reading the date rule gives without the time before it:
`3. Mai` → `dritter Mai`, `13:30 Uhr, 3. Mai` → `13 Uhr 30, dritter Mai`, `um 13 Uhr 30 3. Mai` (printed) → `… dritter Mai`.
Measured on the German front end (misaki `EspeakG2P("de")`): `3. Mai` as printed is spoken "drei. Mai", so reading it is the better choice too.

**Change.** `_AFTER_UHR` no longer applies when that `Uhr` closes a clock time: `Uhr` preceded by `\d{1,2}[:.]\d\d\s+` (the
`_TIME` shape with `uhr`). The `#253` case `13 Uhr 30. Jahr` (no clock before `Uhr`) keeps the guard. Consequence for other
nouns, same on both runs: `um 13:30 Uhr 3. Kapitel` → `um 13 Uhr 30 drittes Kapitel` (run 2 sees `30 3. Kapitel`, which the
noun fallback already reads `drittes`). `um 13 Uhr 3. Mai` (printed, no minutes) stays as printed, as today.

## 3. #483 a season, term or common noun plus a year in brackets

**Cause.** `CitationStep._names_ok` accepts any capitalised word as an author; German capitalises every noun, so
`(Sommer 2019)` passes as author plus year. Only months are refused (`CitationWords.months`).

**Change.** New `CitationWords` field `periods: frozenset[str]` (lower case; empty for English): words that, standing **alone**
as the author of a bracket's only part, make it a date, not a citation. German: `numbers_de.YEAR_WORDS` (made public; seasons,
`Frühjahr`, `Wintersemester`, `Sommersemester`, `WS`, `SS`, `WiSe`, `SoSe`, months, `Jahr…`) plus common nouns before a year:
`Ausgabe`, `Auflage`, `Stand`, `Fassung`, `Version`, `Jahrgang`, `Semester`, `Quartal`, `Saison`, `Spielzeit`, `Welle`,
`Erhebung`, `Erhebungswelle`, `Zensus`, `Mikrozensus`, `Haushaltsjahr`, `Geschäftsjahr`, `Berichtsjahr`, `Kalenderjahr`,
`Schuljahr`, `Studienjahr`. (Words that are also common surnames beyond the seasons, such as `Wahl`, are left out.)
The bracket stays as printed only when the part is that single word plus the year: no second author, no `et al.`/`u. a.`,
no lead word (`vgl. Sommer 2019` is a citation), no locator (`Sommer 2019, S. 3` is a citation), and no other citation part
in the bracket (`Sommer 2019; Koch 2020` is a citation list). Each of these is a case in the unit tests.
This is a word list as the issue proposes; the structural cues above keep a surname like `Sommer` a citation as soon as
anything else shows one.

**Not changed (AC 2).** `(Koch 2019)`, `(Wagner 2020)`, `(Sommer et al. 2019)`, `(Sommer und Koch 2019)` are removed as today; a test pins each.
English `(Summer 2019)` is also removed today: out of scope (AC names German), follow-up issue F1.

## 4. #527 two-glyph arrows and a raised "−1"

**Measured** (Kokoro `KPipeline("a")` g2p, and misaki `EspeakG2P("de")`):
`←−` is spoken "left minus" (en and de), `−→` "minus right", `←` "left arrow" / "Linkspfeil", `→` "right arrow" / "Rechtspfeil".
`(I − P)−1` as printed is spoken "minus one" by both front ends.

**Change, shape 1.** New rule `arrows(text)` in `notation.py` (shared by `find_numbers` and `find_numbers_de`, first in both
`pick` lists): `←−→` → `↔`, `←−` → `←`, `−→` → `→` (U+2212 only, also glued: `X−→α`, `(α−→β)`, lesson #478), reason
`arrow printed as two glyphs "−→" read as one arrow`. So both languages say "right arrow" / "Rechtspfeil", never "minus".
The N1 `_MINUS` look-behind also refuses an arrow glyph before the sign (belt and braces; the arrow candidate already wins `pick`).

**Change, shape 2.** `_MINUS` refuses a sign glued after `)`, `]` or `}`: `(I − P)−1` stays as printed (AC 2 allows this).
Why not "to the power of minus 1": without the raise we cannot tell `(I − P)−1` (inverse) from `f(x)−1` (f of x minus one).
The row pins our script (as printed), and its `goal` says plainly that the voice still says "minus one" here, so the row does
not present that as right (lesson "rows must not lock in wrong readings"). Reading a raised `−1` from its `sup` tag as a power is follow-up F2.
A spaced `(a) − 1` and `x −1` keep "minus" as today (pinned).

**Corpus.** `−→` occurs in read text of acl2023-nowak (list item 26 `X −→\nα`, paragraph 28 `X−→α∈R`) and in its formula
blocks and algorithm figures (notice on by default, not read). So nowak's script changes in those two blocks ("minus right"
→ "right arrow"); nowak has no golden script (`test_app_corpus.GOLDEN`), but I will diff every corpus document's script
(8 papers, 2 text, 2 Markdown, 1 EPUB) main vs branch, with "Tables and figures" on and off, and list every difference in the PR.
No other corpus file holds `←−`/`−→`.

## 5. Regression rows (written first, failing on main, then the rule)

`german.toml` (each with `read_twice` passing; none listed in `SECOND_RUN_EXCEPTIONS`):
- `de-year-hundreds-full-stop-noun` (#536): `Die Studie begann im Jahr 1998. Jahr für Jahr kamen neue Daten.` →
  `Die Studie begann im Jahr 19 hundert 98. Jahr für Jahr kamen neue Daten.`
- `de-time-before-date` (#557): `Die Sitzung beginnt um 13:30 Uhr 3. Mai im Hörsaal.` → `Die Sitzung beginnt um 13 Uhr 30 dritter Mai im Hörsaal.`
- `de-period-bracket-kept` (#483): `Die Daten (Sommer 2019) und die Kurse (Wintersemester 2019) zeigen es, ebenso der Bericht (Ausgabe 2018).` → as printed.
- `de-noun-surname-citation-removed` (#483): `Das zeigen frühere Arbeiten (Koch 2019; Wagner 2020).` → `Das zeigen frühere Arbeiten.`
- `de-two-glyph-arrow` (#527): `Dann gilt β(0, S, 0) ←− 0, P′ ←− (I − P)−1 und S −→ ε.` → `Dann gilt β(0, S, 0) ← 0, P′ ← (I − P)−1 und S → ε.`

`english.toml`:
- `two-glyph-arrow-and-raised-minus` (#527): `Then β(0, S, 0) ←− 0 and P′ ←− (I − P)−1 and S −→ ε hold.` →
  `Then β(0, S, 0) ← 0 and P′ ← (I − P)−1 and S → ε hold.` (goal notes the voice's "minus one" for the raised −1, F2)

## 6. Test-harness changes (all of them)

- `test_a_german_job_reads_the_same_on_a_second_run`: two `@example`s (`im Jahr 1998. Jahr`, `um 13:30 Uhr 3. Mai`), built with
  `make_document(..., language="de")`. `hypothesis.example` import added. The property itself is unchanged.
- `test_a_second_run_reads_nothing_new` / `test_german_numbers_read_as_said` parametrize lists: new cases for 1 and 2
  (incl. `das 98. Jahr`, `am 3. Mai`, `das 1998. Jahr`, `seit 1850. Jahr`, `13 Uhr 30. Jahr`, `um 13:30 Uhr 3. Kapitel`, `um 13 Uhr 3. Mai`).
- Citations unit test: parametrized kept/removed cases for 3 (the nine shapes named above), de and en (`(Summer 2019)` pinned as today's, removed).
- English numbers unit test: arrow and minus cases for 4 (`X−→α`, `←−→`, `(a) − 1`, `x −1`, `f(x)−1` as printed).
- `notation_texts.german_notation_documents` (Hypothesis strategy): add `←−`, `−→`, `Uhr`, `hundert` to its vocabulary so the
  property tests reach the new rules. No strategy is narrowed.
No regression loader, `read_twice` or `SECOND_RUN_EXCEPTIONS` change.

## 7. Checks before hand-off

Fast suite (`not slow and not benchmark and not browser`), ruff, format, lint-imports, deptry; Hypothesis `dev` profile on the
German and English property tests with fresh `.hypothesis` (lesson), plus 3 extra seeds; my own grid fuzz for 1 and 2
(lead word × number × `.`/none × noun × month, both runs, PR vs main) and for 3 (noun × lead × second author × locator);
corpus script diff (4); then `ci:full` (critical) and the Linux CI green before hand-off. Ledger line per PR.

## 8. Follow-up issues to file (proposed milestone v1.2.x)

- F1 (#588): English `(Summer 2019)`, `(Spring 2020)`, `(Fall 2018)` are removed as citations (same cause as #483, English list).
- F2 (#589): a raised `−1` after a bracket (`(I − P)⁻¹` printed as `(I − P)−1`) could be read as a power from its `sup` tag; today as printed, the voice says "minus one".
- F3 (#590): `=⇒` / `⇐=` (a long double arrow printed as two glyphs, common in PDF text) is spoken "equals" and loses the arrow (en measured); same rule shape as 4. Not in the corpus.

Size: ~120 lines of rule code, ~150 lines of tests and rows. Review: Opus high (critical).
