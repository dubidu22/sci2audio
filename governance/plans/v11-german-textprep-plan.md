# Plan: German text reading rules for v1.1 (#96, #101, #113, #130)

Thread "Add German text reading rules", 13 Nov 2026, main 31b6d16. Lane: textprep. Roadmap:
`plans/roadmap-after-v1.md` (v1.1 German reading, D-454).

**Critical: yes** (risk:high). Every PR adds to a new golden file, the German regression cases
`tests/regression/german.toml`, and PR 4 adds a German script snapshot. It also extends the German
sample document that the conformance suite (`sci2audio.testing`) checks every step on. **No change
to the core dataclasses, the layer contract or the text-step interface** (`TextStep`,
`StepContext`, `run_steps` stay as they are). **No English golden changes**: every English
regression case, the English line-end hyphen cases and all corpus snapshots must stay byte-identical,
and each PR shows that. No new dependency.

## 0. How the language reaches the steps (nothing to build)

The contract already carries it. `Document.language` is set by layout as
`settings.language or content.metadata.language or "en"` (`layout/build.py:73`, `tagged.py:117`);
the user sets it with `--language de` or the web setting, and EPUB, Markdown front matter and PDF
`/Lang` fill it from the file. The app passes `StepContext(language=document.language)`; the runner
runs only steps whose `languages` match (`"de-AT"` matches `"de"`) and lists the rest in the
report as not run. So each German rule is: the step adds `"de"` to `languages` and picks its German
table or German rules by `context.language`.

**Gap outside this thread (recommend a new v1.1 issue, app or layout lane):** most PDFs declare no
`/Lang`, so a German PDF without one is read as English unless the user sets the language. An
offline guess when the file declares nothing (count of German function words such as "und", "der",
"die", "nicht", "ist" against English ones over the body text; the report says the language was
guessed) would make German work without a setting. Not part of these PRs.

## 1. What the German front end reads wrong (measured, not assumed)

The German voice is still being chosen (#211; candidates Kokoro with a German fine-tune, Piper
thorsten/kerstin). Both main candidates speak through **espeak-ng's German front end**: Kokoro's
non-English path is misaki's espeak backend (phonemizer, `preserve_punctuation=True`), Piper uses
espeak-ng directly. I ran espeak-ng `de` (the copy in the project's own `espeakng-loader` 0.2.4,
through phonemizer, both with and without punctuation kept). Readings below are the IPA turned back
into words. **I re-run the whole table on the chosen voice's real front end before the first PR**
(D-227: measure first); a rule whose input the voice already reads right is dropped then.

| Input | espeak-ng de says | Right? | Rule |
|---|---|---|---|
| 2,5 · 0,05 · 2,45 | "zwei fünf" · "null null fünf" · "zwei fünfundvierzig" (**Komma lost**) | **no** | N-de-1 |
| 0,001 · 1,234 | "null tausend eins" · "eintausendzweihundert…" (comma read as an English thousands mark) | **no** | N-de-1 |
| 1.234 · 1.000.000 | right without punctuation kept; **"eins. zweihundert…"** with it (Kokoro's way) | depends | N-de-2 |
| 10 000 · 1 000 000 | "zehntausend" · "eine Million" | yes | none |
| 1998 (a year) · 1990er | "eintausend neunhundert achtundneunzig" · "eintausend neunhundert neunziger" | **no** | N-de-3 |
| 2019 · 1066 · 1234 Teilnehmer | "zweitausendneunzehn" · ... · "eintausendzweihundert…" | yes | none |
| 3–5 · 3-5 · 2010–2015 | "drei fünf" · "drei Strich fünf" | **no** | N-de-4 |
| am 3. Mai · der 3. Platz · im 20. Jahrhundert · 1. Auflage | "am drei Mai" · "der drei Platz" · "zwanzig Jahrhundert" · "eins Auflage" | **no** | N-de-5 |
| 12.03.2019 · 1.3.2020 · 2019-03-12 | "zwölf null drei zweitausend…" · "zweitausendneunzehn Strich null drei Strich zwölf" | **no** | N-de-5, N-de-6 |
| 1/2 · 2/3 · 17/20 | "eins zwei" · "zwei drei" | **no** | N-de-7 |
| 3:1 · 1:100 · 13:30 Uhr | "drei eins" · "eintausendeinhundert" · "dreizehn dreißig Uhr" | **no** | N-de-8 |
| 10⁶ · R² · x² | "zehn sechs" · "R zwei" | **no** | N-de-9, S-de-3 |
| Kapitel IV · Phase II | "Kapitel römisch vier" | partly | N-de-10 |
| r = .45 · p < .05 · 2.5 (point in a German text) | "r gleich fünfundvierzig" · "p null fünf" (**sign and point lost**) | **no** | N-de-1, S-de-1 |
| p < 0,05 · x > 3 | **"<" and ">" silent** | **no** | S-de-1 |
| ≥ 18 · ± 12 · = · ≠ | "größer oder gleich" · "plus minus" · "gleich" | yes | S-de-1 (explicit, as D-177) |
| t(34) = 2,45 · F(2, 57) | "t vierunddreißig gleich…" (bracket meaning lost) | **no** | S-de-2 |
| 95 %-KI [1,2; 3,4] | "Prozent Ki eins zwei drei vier" | **no** | S-de-4 |
| z. B. · d. h. · u. a. · bzw. · usw. · ca. · vgl. · S. 12 · Nr. 5 · Abb. 3 · Tab. 2 · Gl. 2 · Kap. 3 · Dr. · Prof. | "zet be" · "de ha" · "u a" · "be zet we" · "usf" · "ka" · "fau ge el" · "es zwölf" · "en er fünf" · "app drei" · ... | **no** (every one) | A-de |
| 5 km · 5 km/h · 3 mm · 1,5 l · 12 min · 3 h · 2 Std. · 5 Mio. | "ka em" · "ka em ha" · "em em" · "el" · "min" · "ha" · "es te de" · "mio" | **no** | U-de |
| 37 °C · 10 % · 5 € · § 5 | "Grad C" · "Prozent" · "Euro" · "Paragraf" | °C partly, rest yes | U-de (°C) |
| 1 kg · 1 Sekunde | "eins Kilogramm" · "eins Sekunde" | **no** | U-de (ein/eine) |
| 3x so schnell | "drei ix so schnell" | **no** | U-de (mal) |

Every proposed replacement below was read back through the same front end and sounds as meant:
"2 Komma 4 5", "19 hundert 98", "3 bis 5", "am dritten Mai", "zwölfter März 2019", "ein halb",
"zwei Drittel", "17 von 20", "3 zu 1", "13 Uhr 30", "10 hoch minus 4", "R Quadrat",
"p kleiner als 0 Komma 0 5", "5 Kilometer pro Stunde", "37 Grad Celsius", "5 Quadratmeter",
"ein Kilogramm", "Quelle 12", "Quellen 3 und 5".

## 2. Rules per issue, with example readings

Readings keep the printed digits wherever the front end reads them right (D-176). Words replace
digits only where it cannot (ordinals, dates). Every edit's reason quotes the printed text (D-175).
Reasons stay English, as the report is English.

### PR 1: #96 line-end hyphens (TP-02)

The rule of #65 (D-149 to D-152) works for German once three word lists are per language
(`HyphenWords`; English values unchanged):

- Suspended hyphen: *after* is "und", "oder", "bis", "sowie", "bzw", "beziehungsweise", "noch" or
  "respektive" → no edit, the line break is read as a space. "Wohnungs-/und Sozialarbeit" reads
  "Wohnungs- und Sozialarbeit".
- The capital test stays and is right for German, which answers the issue's worry: a line-end
  split never capitalises the rest of a word, so "Corona-/Pandemie" (capital after) is a hyphen the
  author wrote and is kept, and "Sozial-/arbeit" (lower case after) joins to "Sozialarbeit". A
  capital *before* the hyphen ("PDF-/Datei"), one letter ("E-/Mail") or a hyphen already inside
  ("Ad-hoc-/Analyse") keeps it, as in English.
- No "self" and no second-word list for German (German writes such compounds closed:
  "kontextabhängig"), so the default is to join. The document's own spelling still wins first.
- Example cases: "Bun-/desregierung" joins; "Corona-/Pandemie", "PDF-/Datei", "E-/Mail",
  "COVID-/19" keep; "Kinder-/und Jugendhilfe", "Ein-/oder Ausgang", "Haus-/noch Gartenarbeit" no
  edit; a document printing "Datenschutz-Grundverordnung" elsewhere keeps "Datenschutz-/Grundverordnung".

Also in PR 1, because it is the smallest PR and sets up the German test structure: the
`german.toml` regression file and its test, the larger German conformance sample, the German
Hypothesis strategy (section 4).

**Proposed extra (Q8):** German reference-list titles. `ReferenceListStep` is English only, so a
German document's "Literatur" section would be read in full. `app.chapters` already lists "Literatur",
"Literaturverzeichnis", "Quellen", "Quellenverzeichnis"; I'd add "Bibliographie", "Bibliografie"
and make the step take the names of the job's language (`REFERENCE_TITLES` by language), with the
existing test that keeps the step and the chapter choice equal. No notice is spoken, so it does not
touch #212. Needs a new v1.1 issue if you agree.

### PR 2: #113 abbreviations, symbols and units (TP-08, TP-10)

`textprep/data/de/abbreviations.toml` and `data/de/units.toml`, project-written, checked by the same
loader; both steps add `"de"`.

Abbreviations (about 60 entries, each with `before` as in D-228): "z. B."/"z.B." zum Beispiel,
"d. h." das heißt, "bzw." beziehungsweise, "usw." und so weiter (may end a sentence), "etc." et
cetera (may end), "ca." circa, "vgl." vergleiche, "ggf." gegebenenfalls, "evtl." eventuell, "inkl."
inklusive, "bspw." beispielsweise, "i. d. R." in der Regel, "o. Ä." oder Ähnliches, "u. U." unter
Umständen, "v. a." vor allem, "z. T." zum Teil, "u. v. m." und vieles mehr, "sog." sogenannte,
"Dr." Doktor, "Prof." Professor (before a word), "Nr." Nummer, "S." Seite (before a number), "s."
siehe, "Abb." Abbildung, "Tab." Tabelle, "Gl." Gleichung, "Kap." Kapitel, "Abschn." Abschnitt,
"Anh." Anhang, "Abs." Absatz, "Bd." Band, "Aufl." Auflage, "Hrsg."/"Hg." Herausgeber, "Jh."
Jahrhundert, "n. Chr."/"v. Chr.", "max."/"min." maximal/minimal (before a number only, so "12 min."
stays the unit's), "vs." versus. "et al." stays as printed (the voice reads it right).

Two loader additions, both optional keys with English untouched:
- `exact_case = true`: the form matches only as printed and the reading keeps its case. Needed
  because "S." (Seite) and "s." (siehe) differ only in case, and noun readings stay capitalised.
- `after_name = "und andere"`: "u. a." reads "und andere" when a year or a bracketed year follows
  ("Müller u. a. (2019) zeigen" reads "Müller und andere zeigen" once the citation bracket goes),
  and "unter anderem" everywhere else.

Units (about 80 entries): km Kilometer, m Meter, cm, mm, µm Mikrometer, nm, kg Kilogramm, g Gramm,
mg, µg, l/L Liter, ml, s Sekunde/Sekunden, ms, min Minute/Minuten, h/Std. Stunde/Stunden, Hz, kHz,
MHz, GHz Hertz, V Volt, W Watt, kW, kWh Kilowattstunde/-stunden, J Joule, N Newton, Pa Pascal, hPa,
bar, mol, mmol, °C Grad Celsius, K Kelvin, Mio. Million/Millionen, Mrd. Milliarde/Milliarden, Tsd.
Tausend; words pro, Quadrat-, Kubik-, hoch 2, hoch 3, ungefähr (≈), etwa (~), mal (×, "3x"). Three
German differences in the unit step, each switched by the language's table, not by new code paths
for English:
- **Numbers as German prints them**: decimal comma and thousands point ("2,5 km", "1.500 m");
  English keeps its pattern.
- **Compounds are one word**: "5 m²" reads "5 Quadratmeter", "3 cm³" "3 Kubikzentimeter" (a
  `joined = true` flag next to `square`/`cubic`). "m/s²" reads "Meter pro Sekunde hoch 2".
- **Number 1 by gender**: each unit has `gender`; "1 kg" reads "ein Kilogramm", "1 s" "eine
  Sekunde", "1 Mio." "eine Million"; after a dative preposition ("mit", "nach", "von", "bei", "aus",
  "seit", "zu", "in", "an", "unter", "vor") "einem"/"einer" ("nach 1 Stunde" reads "nach einer
  Stunde"). A separate edit on the "1", so the unit edit still never covers a number. Plural after
  any other number, also after "1,0".
- Plural forms only where German has them (Sekunden, Minuten, Stunden, Millionen); most units are
  the same in both. A day unit "d" is read only after "pro" (as English "day"), since the dative
  plural "Tagen" would need case.

### PR 3: #130 numbers, dates and statistics (TP-09, TP-11, TP-13)

German rules live in their own module (`textprep/numbers_de.py`, `statistics_de.py`); `NumbersStep`
and `StatisticsStep` add `"de"` and call them when the job is German. Same step ids and category,
so the report and the switches stay as they are, and the English code is not touched.

- N-de-1 decimals: "2,5" reads "2 Komma 5", "2,45" "2 Komma 4 5", "0,05" "0 Komma 0 5" (digits after
  the comma one by one, as German says them; trailing zeros kept, so no N4 twin is needed). A point
  decimal in statistics position (after an operator, or a leading point) reads the same: "r = .45"
  reads "r gleich 0 Komma 4 5", "p < .05" "p kleiner als 0 Komma 0 5". A point after a label word
  ("Abschnitt 2.5", "Version 2.1", "Tabelle 3.1") reads "2 Punkt 5". Any other point between digits
  is left as printed (ambiguous).
- N-de-2 thousands: "1.234" reads "1234", "12.345.678" "12345678" (groups of exactly three).
- N-de-3 years: a number 1100 to 1999 is read as a year, "19 hundert 98", when it follows a year
  word ("Jahr", "im Jahr", a month name, "Anfang", "Mitte", "Ende", a season, "seit", "bis", "ab",
  "um", "von", "zwischen", "WS"/"SS") and no capitalised word follows ("seit 1998 gibt es" is a year;
  "nach 1500 Versuchen" stays a count); "1990er" always reads "19 hundert 90er". Other years are
  read right already ("2019", "1066").
- N-de-4 ranges: "3–5", "3 – 5", "3-5" (plain numbers), "2010–2015", "1,2–3,4" read with "bis":
  "3 bis 5".
- N-de-5 ordinals and dates, with the ending the word before asks for: "der/die/das 3." → "dritte",
  "den/dem/des/am/im/vom/zum/zur/beim 3." → "dritten"; with no article only before a short list of
  nouns whose gender is known ("1. Auflage" → "erste Auflage", "20. Jahrhundert" → "zwanzigstes
  Jahrhundert", "2. Weltkrieg" → "zweiter Weltkrieg"); a day before a month name or a numeric date
  ("12.03.2019", "1.3.2020") → "zwölfter März 2019", after "am"/"vom"/"bis zum" "am zwölften März
  2019". "Es waren 3. Die Studie" is left alone (no article, no listed noun). Ordinals are written
  in words by a small German number-to-words function (1 to 999 999), which is the one place
  digits become words.
- N-de-6 ISO dates: "2019-03-12" reads as a German date, "zwölfter März 2019".
- N-de-7 fractions: "1/2" "ein halb", "1/4" "ein Viertel", "3/4" "drei Viertel", "2/3" "zwei
  Drittel" (denominators 2 to 10), else "17 von 20".
- N-de-8 ratios and times: "3:1" "3 zu 1"; "13:30 Uhr" or "um 13:30" "13 Uhr 30".
- N-de-9 powers: "10⁶" "10 hoch 6", "10⁻⁴" and "× 10−4" "10 hoch minus 4", "x²" "x Quadrat".
- N-de-10 Roman numerals after a keyword (Kapitel, Teil, Band, Phase, Typ, Klasse, Stufe, Studie,
  Experiment, Anhang, Abschnitt, Tabelle, Abbildung, Abb., Tab., Kap.): "Kapitel IV" reads
  "Kapitel 4" (as D-185). A Roman numeral with a full stop ("Ludwig XIV.") is left as printed.
- S-de-1 operators: "<" kleiner als, ">" größer als, "≤" kleiner oder gleich, "≥" größer oder
  gleich, "=" gleich, "≠" ungleich, "±" plus minus, "∓" minus plus, "≪"/"≫" viel kleiner/größer als.
- S-de-2 df brackets (Q4): "t(34)" reads "t mit 34 Freiheitsgraden", "F(2, 57)" "F mit 2 und 57
  Freiheitsgraden", "χ²(1)" "Chi-Quadrat mit 1 Freiheitsgrad".
- S-de-3: "R²" R Quadrat, "η²" Eta-Quadrat, "ηp²" partielles Eta-Quadrat, "ω²" Omega-Quadrat,
  "χ²" Chi-Quadrat (a plain "2" only before an operator or a df bracket, as English S3).
- S-de-4: "KI" and "CI" read "Konfidenzintervall" after a percentage or before a bracket, "=" or
  ":"; the pair inside reads "1 Komma 2 bis 3 Komma 4". German pairs are split by ";" (the comma is
  the decimal sign): "[1,2; 3,4]". The citation step's interval check learns "KI" too, so "KI [1; 3]"
  is never read as citations 1 and 3.
- S-de-5: "OR" before an operator reads "Odds Ratio".

### PR 4: #101 links and citations (TP-03, TP-04, TP-07)

German rows for `LinkWords` and `CitationWords`, as the issue asks, plus the few English words that
sit in module-level patterns today (they move into the rows; the English values stay the same):

- Links: labels ("Kontakt", "E-Mail", "Code", "Quellcode", "Daten", "Datensatz", "URL", "Webseite",
  "Website", "Homepage", "Repository", "verfügbar unter", "abrufbar unter", "online"), words before
  ("unter", "auf", "bei", "über", "via", "siehe", "vgl.", "s.", "hier"), introducers ("verfügbar",
  "abrufbar", "zugänglich", "frei", "öffentlich", "online", "hinterlegt", "veröffentlicht"),
  pointers ("siehe", "siehe auch", "vgl.", "s."), joins ("und", "oder", "sowie", ",", ";", "/", "&"),
  purposes ("für", "zu", "zum", "zur") and the common words that end a URL at a line break ("und",
  "der", "die", "das", "ist", "sind", "wird", "verfügbar", ...). "Die Daten sind unter
  https://x.org/d verfügbar." reads "Die Daten sind verfügbar." "Kontakt: a@b.de." is not read.
  "Siehe https://x.org für Details." goes whole.
- German web citations add a date note after the link: "(abgerufen am 12.03.2020)", "(Zugriff am
  …)", "[letzter Zugriff: …]", "(Stand: …)". A bracket right after a removed link that starts with
  such a word goes with it (German words only; English has no such list today, so English is
  unchanged).
- Citations: "u. a." and "et al." and "und"/"u."/"&" between authors, "im Druck", "o. J." (no year),
  locators "S. 8", "S. 8–10", "S. 8 f.", "Kap. 9", "Abschn. 3"; lead words ("siehe", "siehe auch",
  "vgl.", "vgl. auch", "z. B.", "zum Beispiel", "für einen Überblick siehe", "etwa"); German months
  and articles ("der", "die", "das", "ein", "eine"). "(Müller & Schmidt, 2019)" and "(vgl. Müller u.
  a. 2019, S. 12)" go; "Müller (2019) zeigt" reads "Müller zeigt"; "die Studie (2019)" keeps its
  bracket (article before, D-448).
- Numeric citations the sentence needs read "Quelle 12", "Quellen 3 und 5", "Quellen 2 bis 6" (the
  issue's words). These come from a German `Wording` row (D-145: wording only there). That row also
  needs notice texts; I fill them with a proposal, but they stay unused (the notice steps stay
  English only) and **#212 owns their final wording**.

## 3. Idempotence: how each rule stays still on a second run

Every replacement contains nothing its own rule (or an earlier German rule) matches again, and the
property tests prove it:

- Hyphens: an edit removes the line break, so no hyphen stands at a line end any more.
- Abbreviations and units: readings are plain words with no full stop and no unit symbol; "ein"
  before a unit word is no number. "pro", "Quadratmeter" match no printed unit form.
- Numbers: "2 Komma 4 5" has no digit-comma-digit; "1234" has no group point; "19 hundert 98" has no
  four-digit number; ordinals and dates become words; "3 bis 5", "3 zu 1", "10 hoch 6", "13 Uhr 30"
  have no dash, colon or superscript left. The two rules that could meet on a second run share one
  check: N-de-2 does not remove the point from "1.998" where N-de-3 would then read "1998" as a
  year (same year-word test), so "im Jahr 1.998" stays as printed on both runs.
- Statistics: words only; "Konfidenzintervall 1 Komma 2 bis 3 Komma 4" has no bracket.
- Links and citations: the removed text is gone; "Quelle 12" has no bracket.

## 4. Tests and test data

- `tests/regression/german.toml`, same format and loader as `english.toml` (`language = "de"` per
  case, which the loader already supports), its own test module; every rule above gets at least one
  case and one "left alone" case (about 120 cases over the four PRs). German line-end hyphen cases
  go here as ordinary cases; there is no German corpus paper to count line-end hyphens in.
- Unit tests per rule in the existing test files (German classes next to the English ones), and
  loader tests for the two new abbreviation keys and the German unit keys.
- Hypothesis: a German document strategy (German words with ä, ö, ü, ß, decimal commas, dates,
  ordinals, units, links, brackets) for no crash, valid spans and idempotence, for every step that
  handles "de"; the `ci` and `nightly` profiles as for English.
- Conformance: the German sample document in `sci2audio.testing` grows from three short blocks to
  about ten (a paragraph each for numbers, statistics, units, abbreviations, links, citations, a
  line-end hyphen), so `check_text_step` exercises the German paths of every step.
- German sample text (PR 4): a project-written German sample, about one page, in
  `tests/fixtures/german/` (no third-party text), run through the whole text pipeline with a syrupy
  snapshot of its script by category. A real CC BY German paper for the corpus can follow as its own
  issue, with the licence check.
- Each PR: the full fast suite, `ruff`, `lint-imports`, `deptry`, and proof that every English
  golden (regression cases, line-end hyphen cases, corpus snapshots, app script snapshots) is
  unchanged.

## 5. PRs and size

One PR per issue, each with its own review thread (D-376), in this order, each branched from main
after the one before merges (or stacked on it while it is in review):

1. #96 hyphens + German test structure (+ Q8 reference titles if agreed): about 400 lines.
2. #113 abbreviations and units: about 900 lines, most of it the two data files and cases.
3. #130 numbers and statistics: about 1,200 lines.
4. #101 links and citations, German Wording row, German sample snapshot: about 800 lines.

## 6. Questions (my recommendation first)

- Q1 Language: use the declared job language (document or user setting), no detection here; file
  the detection gap as a new issue (section 0). Recommended.
- Q2 Structure: German tables inside the existing steps (same ids, categories, switches); German
  number and statistics rules in their own modules called by the existing steps. Recommended over
  separate German steps, which would double the report's step list and the switch logic.
- Q3 Measurement: espeak-ng de now; re-measure on #211's chosen front end before PR 1 and drop
  rules it does not need.
- Q4 df brackets: "t mit 34 Freiheitsgraden" (clear when listening) over "t von 34" (mirror of the
  English "t of 34", but not how German is spoken).
- Q5 Decimal digits after the comma one by one ("2 Komma 4 5"), as German reads them.
- Q6 Years: read 1100 to 1999 as years only with a year word before (section 2, N-de-3);
  everything else stays a count, which is what the voice does today.
- Q7 Number 1 before a unit by gender and the dative prepositions; "1 + other nouns" (no gender
  list) stays as the voice reads it, a known limit.
- Q8 German reference-list titles in PR 1 (new issue). Recommended: without it a German paper's
  reference list is read in full.
- Q9 One PR per issue (four PRs), in the order above.
