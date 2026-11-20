# Review of PR #228, round 1 (German abbreviations, symbols and units, #113)

Reviewed 14 Nov 2026 at head b0e1fb4 (base main 9af111e, main has not moved). Critical (adds cases to the German golden `tests/regression/german.toml`). PR 2 of 4 of the v1.1 German text rules (plan `plans/v11-german-textprep-plan.md`, D-474 to D-482).

**Verdict: changes requested.** Ten fixes; three items deferred to new issues (#229 v1.1, #230 and #231 v1.2). Merge is also held on the coordinator's word until the release/1.0 branch exists.

## What I checked

- Plan section 2 PR 2 and D-476, D-480: matches. German tables inside the existing `abbreviations` and `units` steps (same ids, categories, switches); two optional abbreviation keys (`exact_case`, `before_year`; the plan's `after_name` became `before_year`, same meaning); German number pattern, joined powers, "1" by gender as a separate edit on the number. No change to the core dataclasses, the layer contract or the text-step interface.
- CI: all 12 checks green on b0e1fb4.
- Locally: ruff, format, lint-imports (3 kept), deptry clean; fast suite 3509 passed, 1 skipped (`HYPOTHESIS_PROFILE=ci`, `-n 8`). Changed and related test files under the nightly profile: 491 passed.
- **English byte-identity:** `sci2audio script --ignore-settings` on all 10 corpus documents (7 PDFs, EPUB, Markdown, text) on main (PYTHONPATH to a main worktree) and on the PR: script, report.json and report.md byte-identical. With `--language de` they differ as expected (German lists now run).
- English code paths read line by line: `hyphen_singular` defaults True, `joined_powers` False, the "block-end full stop" branch needs a printed unit with a full stop (no English unit has one), `by_form` holds one entry per form for English. Same behaviour.
- Loader refusals for every new key are tested (gender, decimal, one table, dative without one, exact_case clash).
- Every new German golden case read and judged as spoken German: all right, with the limits below.
- Front-end readings measured with misaki `EspeakG2P("de")` (the #211 voice's front end).

## Hand probes (German job) that read wrong

1. Case after "über", "auf", "ab": "über 1 kg" reads "über einem Kilogramm", "über 1 Mio. Euro" "über einer Million Euro" (right: "über ein Kilogramm", "über eine Million"); "auf 1 m erhöht" reads "auf einem Meter" (right: "auf einen Meter"); "ab 1 kg" reads "ab ein Kilogramm" (right: "ab einem Kilogramm").
2. Capitals with umlauts are not seen: "Dr. Özdemir", "Prof. Ünal" stay as printed (and the cutter splits "Laut Dr." | "Özdemir ..."); "Katzen usw. Über die Studie" and "usw. Ältere Studien" drop the full stop, so two sentences run together. `_WORD` and `_NEXT_SENTENCE` use `[A-Z]`.
3. "o. ä." and "u. ä." (lower-case ä, very common) stay as printed, and the cutter splits after them.
4. "5 ‰" is silent in German (front end reads only "fünf"); English lists "‰", German does not. "1 %" and "1 €" read "eins Prozent", "eins Euro" (measured), where German says "ein Prozent", "ein Euro".
5. German label lists: "Bedingungen 1 bzw. 2 V" reads "2 Volt", "Gruppen 1 und 2 K" reads "2 Kelvin". `_LABEL_JOIN` knows only "and"/"or".
6. "eine 1-kg-Packung" reads "1-Kilogramm-Packung", which the front end says "einskilogrammpackung" (measured); right is "Ein-Kilogramm-Packung".
7. "u. a." before an unbracketed year after a lower-case word: "Das gilt u. a. 2019 und 2020" reads "und andere 2019".
8. "S. 12 ff." leaves "ff.", read "eff eff" (measured).
9. "nach 12 min. Pause" reads "12 Minuten. Pause" and is cut there: "min." is not a printed unit form ("Min." is).

## Fix list

1. **Case of "1" after prepositions** (`data/de/units.toml`): move "über" and "auf" from `dative` to `accusative` (with a number they mean "more than" / a target, so "über ein Kilogramm", "über eine Million", "auf einen Meter"); add "ab" to `dative`. Golden case for "über 1 Mio. Euro" and "auf 1 m"; unit parameter for "ab 1 kg".
2. **Capitals with umlauts in German jobs** (`abbreviations.py`): a capital after a German abbreviation is any upper-case letter (`str.isupper()` or `[^\W\d_]` checked upper), in `_WORD` (before-word entries), `_NEXT_SENTENCE` (can-end entries) and `_LABEL` for German. Keep English's `[A-Z]` exactly as it is, so English stays byte-identical. Golden cases: "Prof. Dr. Özdemir" reads "Professor Doktor Özdemir" (with `utterances`), "Katzen usw. Über die Studie" keeps the cut.
3. **"o. ä." and "u. ä."** (`data/de/abbreviations.toml`): read the lower-case forms too ("o. ä.", "o.ä.", "u. ä.", "u.ä."), for example by making both entries `exact_case` and listing all forms. Golden or unit case for each spelling.
4. **"‰", "%" and "€" in German** (`data/de/units.toml`): add "‰" as "Promille" (n). Add "%" ("Prozent", n) and "€" ("Euro", m) so a "1" before them reads "ein Prozent", "ein Euro". If you keep "%" and "€" out of the unit list, give the "1" edit another way; either way update `de-units-percent-and-euro-left-to-the-voice` and show "10%" glued still reads right.
5. **German label joins** (`units.py` `_LABEL_JOIN`, by language): "und", "oder", "bzw.", "sowie" and "bis" join labels in German, so "Bedingungen 1 bzw. 2 V" and "Gruppen 1 und 2 K" stay as printed. Golden case. English pattern unchanged.
6. **"1" in a hyphenated compound** (`units.py`): "1-kg-Packung" reads "Ein-Kilogramm-Packung" (the uninflected "Ein", capital as it starts the compound); "1,5-l-Behälter" stays a number. Golden case.
7. **`before_year` only after a name** (`abbreviations.py`): read `before_year` only when the word right before the abbreviation starts with a capital letter (an author); "gilt u. a. 2019" reads "unter anderem 2019". Golden case next to `de-abbreviations-u-a-before-a-year`.
8. **"ff."** (`data/de/abbreviations.toml`): "ff." reads "folgende" (lower case, `exact_case`, `can_end_sentence`). Unit case "S. 12 ff." reads "Seite 12 folgende". The bare "f." is deferred to #231.
9. **"min." as a printed unit form** (`data/de/units.toml`): add "min." next to "min" and "Min." so "nach 12 min. Pause" reads "nach 12 Minuten Pause" and is not cut. Check that "max. 5, min. 3" (the abbreviation before a number) still reads "minimal 3".
10. **Dangling path in both data files**: `data/de/abbreviations.toml` and `data/de/units.toml` cite `plans/v11-german-measure-misaki.txt`, which is not in the repository (same as PR #222 round 1 fix 3). Point to #113 or #211 instead.


As before: write the golden cases first so the PR shows the before/after, and rerun the English corpus byte-identity check after the fixes.

## Deferred (issues filed)

- #229 (v1.1): sentence end lost after a unit printed with a full stop mid-block ("2 Std. Danach", "2 Mio. Die Firma"). Needs a measured rule, because "2 Mio. Euro" must stay one sentence. Same area as #227.
- #230 (v1.2): a unit symbol after "pro"/"per" with no number ("pro m²"), English and German.
- #231 (v1.2): German "f." after a page number.

## Accepted as is (no change)

- `can_end_sentence` on "o. Ä.", "Jh.", "n. Chr." etc. cuts before a capitalised noun ("Hunde o. Ä. Tiere"). The file header names this limit; these mostly end a clause.
- "−1 °C" reads "minus 1 Grad Celsius" (the front end says "minus eins"); plan keeps signed numbers as printed.
- "um 1 °C" reads "um einen Grad Celsius": correct for masculine "der Grad".
- "1 Woche" (a per-only unit word) stays "1 Woche": plan Q7 limit.
- "Das war im 20. Jh. Die Kunst" is cut after "20.": that is #227.
- "(Müller, S. 2019)" reads "Seite 2019": an initial before a bare year is rare in running text; reference lists are not read.
