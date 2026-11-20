# Plan: issue #68, abbreviations, symbols and units in English (TP-08, TP-10, K8)

Thread "Read abbreviations, symbols and units", 13 Nov 2026. Lane textprep. Builds on the
text-step interface (PR #83, a57d135), the cutter (PR #86, 006c964) and the Kokoro voice
(PR #88, 061e4e3). Written while #65 (PR #98), #66 (PR #103) and #91 (PR #105) are in review
and #67 is being coded; binding split with #67: D-178.

**Critical: yes.** The PR changes golden files: `tests/regression/english.toml` (the
`expected` of two audit cases and of two #64 caption cases changes, about 30 cases are
added), the per-category corpus snapshot and #70's script snapshot
(`test_app_corpus.ambr`). **No change to core dataclasses, the layer contract or the
text-step interface.** Label `risk:high`. No new dependency (standard library `re`,
`tomllib`, `importlib.resources`). The two word lists are written for the project (no list
is copied, so the licence gate has nothing to add; GPL-3.0-or-later like the code).

## 1. What the voice already reads (measured, not assumed)

I ran the voice's real front end as #18 uses it: Kokoro's `KPipeline(lang_code="a",
model=False)`, which is misaki with spaCy `en_core_web_sm` plus the espeak-ng fallback,
on about 150 cases, and read the phonemes. Every replacement proposed below was put through
the same front end and reads as intended ("milligrams per kilogram", "37 degrees Celsius",
"metres per second squared", "1.42 angstroms", "441 thousand", "for example", "Equation 8").

**Abbreviations**

| Printed | The voice says | Right? |
|---|---|---|
| Dr. · Mr. · Mrs. · Ms. · vs. · No. 5 · etc. · Ltd. · a.m. · p.m. · U.S. · U.K. | doctor · mister · ... · versus · number five · etcetera | yes |
| et al. | "et al" | yes (how researchers say it) |
| i.i.d. · a.k.a. | "I I D" · "A K A" | yes (said as letters) |
| **i.e. · e.g. · cf.** | "I E" · "E G" · "C F" | **no** |
| **w.r.t. · s.t. · w.l.o.g.** | spelled letter by letter | **no** |
| **Fig. · Figs. · Eq. · Eqs. · Sec. · Secs. · Sect. · Tab. · Alg. · Ref. · Ch. · Chap.** | "fig" · "figs" · "eck" · "sec" · "tab" · "C H" ... | **no** |
| **Thm. · Def. · Prop. · Cor. · Lem. · App. · Suppl. · Nos.** | "T H M" · "def" · "prop" · "nose" ... | **no** |
| **Approx. · approx. · ca. · resp. · incl. · esp. · viz. · avg.** | "approx" · "ka" · "resp" · "inkl" · "esp" · "viz" · "A V G" | **no** |
| **Prof.** | "prof" | **no** |
| p. 8 · pp. 3 · vol. 2 · ed. · eds. · edn. | "P eight" · "P P" · "vol" ... | no, but see 3.1 (G) |

**Units, after a number**

| Printed | The voice says | Right? |
|---|---|---|
| 12% · 12 % · MHz · GHz · mol · bar · Torr | percent · megahertz · gigahertz · ... | yes |
| 45° · 45 ° | "forty-five degrees" | yes, but "1°" reads "one degrees" |
| **37 °C · 98 °F · 37°C** | "degrees C" · "degrees F" | **no** |
| **3.5 mg/kg · 5 km/h** | "M G slash K G" · "K M slash H" | **no** |
| **m · cm · mm · km · nm · µm · μm** | "M" · "C M" · "m" (one sound) · ... · "micro M" · "myoom" | **no** |
| **g · mg · µg · kg · L · mL · µL · s · ms · ps · h · min · Hz · kHz** | letters ("K G", "M L", "P S", "H Z"), "min" | **no** |
| **V · W · kW · A · mA · Ω · kΩ · J · kJ · N · Pa · kPa · eV · meV · keV · MeV** | "vee" · "double-u" · "omega" · "pa" · "E V" · "mev" | **no** |
| **K (kelvin) · Å · 1.42˚A (PDF form) · dB · mM · µM · nM · kcal · KB · MB · GB · Gy · cGy · Sv · Bq · psi · atm** | "kay" · "A ring" · "D B" · "M M" · ... · "sigh" (psi) | **no** |
| **m² · cm³ · m^2 · m/s² · m s⁻¹ · km h⁻¹ · W m⁻² · kg/m³** | "M two" · "M S" (the −1 dropped) · "M slash ..." | **no** |
| **441K apps · 332M words · 100k steps · 15M parameters · 175B tokens** | "four hundred forty-one K" · "M" · "B" | **no** |
| rpm · fps · dpi · ppm · FLOPs · mph | "R P M" ... | yes (said as letters) |

**Symbols**

| Printed | The voice says | Right? |
|---|---|---|
| ≈ 5 · x ≈ 3 | "approximately" (espeak-ng) | yes |
| 3 × 4 · 2× faster · ×10 | "times" (espeak-ng) | yes |
| **~5 · ~ 10 · τ ∼ 0.1 ps** | "tilde five" · nothing · nothing | **no** |
| **3 x 4 · 10x speedup · 3.5x** | "ex" | **no** |
| **‰** | nothing | **no** |
| **µ = 3 · µB** (micro sign U+00B5 used as the Greek letter) | "micro" | **no** (μ U+03BC reads "mu") |
| **1 °C** | "one degrees" | no |

Spelled-out forms read right in every case tried, in British and American spelling alike
("metre" and "meter" both "meeter"), including "square", "cubic", "squared", "per".

## 2. What the corpus holds (layout output of main, 7 papers, outside furniture and placeholders)

- **Abbreviations in running text:** "e.g." 33, "Eq." 17 and "eq." 14 (Arsiwalla writes
  "eq.(1)", glued), "Alg." 12, "i.e." 11, "etc." 10, "Fig." 4 ("Fig. 2a"), "vs." 4, "Ref." 3
  (all before a citation bracket, #66's), "Lem." 2, "App. B" 2, "Proof." 5 (a word, no edit).
  "et al." 123, almost all inside citations (#66). "pp.", "vol.", "eds.", "edn.", "Phys. Rev."
  live only in reference lists, which are not read (#64).
- **Units:** few, as the papers are CS and physics theory: "9kg of carbon", "25 meV",
  "τ ∼ 0.1ps", "3.6eV˚A", "1.42˚A", and glued magnitudes "441K", "332M words", "100k
  steps", "15M more parameters". So, like #67, the unit rules are tested with written cases.
- **Symbols:** "%" 6, "×" 6 (all in inline maths: "d × d matrices"), "≈" 3 ("≈ 95%"),
  "µ" 3 (all "µB", the Bohr magneton), "∼" 1.

## 3. Design

Two inline steps, English only (`languages = ("en",)`), one per category (D-108):

| Step id | Module | Category | What it proposes |
|---|---|---|---|
| `units` | `textprep/units.py` | Numbers, symbols, units and statistics | units after a number, °, magnitudes, ≈ ~ × x ‰, the micro sign |
| `abbreviations` | `textprep/abbreviations.py` | Abbreviations | abbreviations read in full |

Both skip furniture blocks and the placeholder kinds (table, formula, figure), as #66 and #67
do. Every change is a `replace` edit (never `ask`), whose reason quotes the printed text, so
the report names exactly what changed: `unit "mg/kg" read as "milligrams per kilogram"`,
`"°C" read as "degrees Celsius"`, `abbreviation "e.g." read as "for example"`. Edits cover
only the symbol, unit or abbreviation, never the number, so they never overlap #67's edits on
the number itself. Replacement texts carry their own spaces where the printed text has none
("9kg" → "9 kilograms"), since `spoken_text` collapses white space.

**Word lists as data (TP-08):** two TOML files shipped in the package,
`src/sci2audio/textprep/data/en/abbreviations.toml` and `.../en/units.toml`, read once with
`tomllib` through `importlib.resources` and checked on load (every entry has its fields, no
duplicate). A German table is one more folder later; nothing in the code is English except
the folder name chosen by the job's language. A test builds the wheel's file list (hatchling
includes package data by default) and checks both files are in it.

### 3.1 `abbreviations` (TP-08)

Three kinds of entry, each with the printed form(s) and the reading:

- **Anywhere** (word boundary before, not part of a longer dotted chain):
  i.e. → "that is", e.g. → "for example", cf. → "compare", viz. → "namely",
  w.r.t. → "with respect to", s.t. → "such that", w.l.o.g. → "without loss of generality",
  approx. → "approximately", resp. → "respectively", incl. → "including",
  esp. → "especially", avg. → "average", Prof. → "Professor". The spaced forms "i. e." and
  "e. g." count too.
- **Before a number only:** ca. → "circa" ("ca. 1900"), Nos. → "Numbers".
- **Before a label only** (a digit, "(", a capital letter on its own such as "App. B" or
  "Sec. A.2", or a Roman numeral; glued or spaced): Fig./Figs. → Figure(s), Eq./Eqs. and
  Eqn./Eqns. → Equation(s), Sec./Secs./Sect./Sects. → Section(s), Tab./Tabs. → Table(s),
  Alg./Algs. → Algorithm(s), Thm. → Theorem, Def. → Definition, Prop. → Proposition,
  Cor. → Corollary, Lem. → Lemma, App. → Appendix, Ch./Chap. → Chapter, Ref./Refs. →
  Reference(s), Ex. → Example, Exp. → Experiment, and Suppl. → Supplementary before a label
  word ("Suppl. Fig. 3" → "Supplementary Figure 3"). Glued forms get a space:
  "eq.(1)" → "equation (1)", "Fig.4" → "Figure 4".

**Case:** the reading keeps the printed case of the first letter ("E.g., the" → "For
example, the"; "fig. 2" → "figure 2"); a form printed in capitals reads capitalised
("FIG. 3" → "Figure 3"), as #64's label words do.

**Sentence ends:** an entry marked `can_end_sentence` (approx., resp., incl., esp., avg.)
that stands at the end of the block or before white space and a capital letter is replaced
without its full stop, so the full stop stays as printed and the cutter still ends the
sentence there ("..., resp. The next" → "..., respectively. The next"). Entries that
introduce something (e.g., i.e., cf., viz., the label words) never end a sentence.

**Left as printed** (the voice reads them right, section 1): Dr., Mr., Mrs., Ms., vs., No.,
etc., et al., i.i.d., a.k.a., a.m., p.m., U.S., U.K., Ltd. The cutter's abbreviation list
(`utterances.py`) is unchanged: it still protects these, and expanded ones no longer end in a
full stop.

### 3.2 `units` (TP-10, K8)

**What counts as "after a number":** a number as printed (digits with "," or "." groups, a
sign "-", "−" or "+", a leading point ".5", a range "1–2" or "5-10", superscript or "^"
exponents "10⁸"), then nothing, a space, a no-break or a thin space, then a unit from the
table, then a boundary (not a letter, digit or combining mark). Not after a label word
(Figure, Fig., Table, Section, Experiment, Study, Group, Condition, Phase, Type, Model,
Panel, Chapter, Appendix, Lemma, Theorem, Equation, Line, Row, Step) when the "unit" is a
single capital letter ("Figure 2 A", "Table 3 C" get no edit).

**Single-letter units need a space** ("5 m", "3 h", "10 s", "4 V", "300 K"); glued, a single
letter is something else ("1990s", "2D", "5G", "2a"). Multi-letter units may be glued
("9kg", "0.1ps", "25meV").

**The unit table** (`units.toml`) lists every unit explicitly, with singular and plural
reading, rather than combining prefixes with base units, so collisions are decided one by
one: length (m, km, cm, mm, µm/μm, nm, pm is **not** in, Å/˚A), mass (g, kg, mg, µg, ng),
volume (L, l, mL, ml, µL, dL), time (s, ms, µs, ns, ps, fs, min, h, hr, d, wk, mo, yr),
frequency (Hz, kHz, MHz, GHz, rpm stays as printed), electricity (V, mV, kV, A, mA, µA, W,
mW, kW, MW, Ω, kΩ, MΩ), energy (J, kJ, eV, meV, keV, MeV, GeV, cal, kcal, Wh, kWh), force and
pressure (N, Pa, kPa, MPa, mbar, atm, psi), temperature (K kelvin, °C, °F), amount (mol,
mmol, M is **not** in, mM, µM, nM), sound (dB), data (KB, MB, GB, TB), dose (Gy, cGy, mGy,
Sv, mSv, Bq), imperial (ft, lb, oz, mi). Left out because they collide with words or other
readings: in (inch), pm (time), a, y, pt, M (molar or million), kb and Mb (kilobase or
kilobit), um. Units the voice already reads right (MHz, GHz, mol, bar) are still in the
table, so plural agreement and the report are the same for every unit.

**Readings:**

- **Plural agreement (K8):** singular when the number is exactly "1" as printed (signed
  allowed: "−1 °C" → "minus 1 degree Celsius"); plural otherwise, "1.0", "0.5" and ranges
  included. Singular also when the number and unit are joined by a hyphen ("a 5-km race" →
  "a 5-kilometre race", "10-mg dose"), and after "a" or "an" ("a 1 m pole"). Names that do
  not change (hertz, kelvin, Celsius, lux) are listed so in the table.
- **Spelling:** British, as the issue writes it ("metre", "litre", "kilometres"); the voice
  reads "metre" and "meter" the same.
- **"/" reads "per"**, each denominator singular: "mg/kg" → "milligrams per kilogram",
  "mg/kg/day" → "milligrams per kilogram per day", "J/(kg·K)" → "joules per kilogram per
  kelvin". Day, week and the like are unit words in a denominator only ("per day").
- **Negative exponents** ("s⁻¹", "s^-1", "s-1", "s−1" after another unit) read "per":
  "m s⁻¹" → "metres per second", "km h⁻¹" → "kilometres per hour", "W m⁻²" → "watts per
  square metre", "mg kg⁻¹ day⁻¹" → "milligrams per kilogram per day".
- **Powers:** ² and ³ (also "^2", and a plain "2"/"3" glued to a unit after a number and a
  space, as PDFs give superscripts: "5 m2") on a length read "square" / "cubic" before the
  unit ("5 m²" → "5 square metres", "4 cm³" → "4 cubic centimetres"); on any other unit
  "squared" / "cubed" after it ("m/s²" → "metres per second squared").
- **Products:** units joined by a space, "·" or "⋅" are one compound when every part is in
  the table: "N m" → "newton metres", "kW h" → "kilowatt hours"; the plural goes on the last
  unit before "per".
- **Degrees:** "°" after a number → "degree(s)" (an edit even where the voice says
  "degrees" already, so "1°" reads "1 degree"); °C, ℃, ˚C, ºC → "degree(s) Celsius"; °F,
  ℉ → "degree(s) Fahrenheit"; "K" with a space → "kelvin".
- **Magnitudes:** a glued "K" or "k" → " thousand", a glued "M" → " million", a glued "B" or
  "bn" → " billion" ("441K apps" → "441 thousand apps", "15M parameters"), when a space,
  punctuation or the end follows. A spaced "K" is kelvin, a spaced "M" is left as printed.
  Known collision: a glued kelvin ("300K") reads "300 thousand"; SI style and the corpus
  always space it.

### 3.3 Symbols (in `units`)

- **"%"** is left to the voice (misaki reads it right, spaced or not).
- **"‰"** after a number → " per mille".
- **"≈"** → " approximately " wherever it stands between two operands or before a number,
  made explicit although espeak-ng says the same (as D-177 does for "≥": the script, the
  report and read-along show what is said, and the regression cases can pin it).
- **"~" and "∼"** right before a number (spaced or not) → "about " ("~5", "τ ∼ 0.1 ps" →
  "τ about 0.1 picoseconds"); between operands where the right one is not a number
  ("X ~ N(0, 1)") they are left as printed.
- **"×"** → " times " between two operands or right after a number ("3 × 4", "2× faster",
  "d × d"), explicit for the same reason as "≈". A letter "x" or "X" reads "times" only
  between two numbers ("3 x 4") or glued after a number with no letter or digit after it
  ("10x speedup", "3.5x."); never in "0x1F", "x86" or "2 x n".
- **"µ" (micro sign, U+00B5)** that is not a unit prefix (#65 leaves it alone) becomes the
  Greek letter "μ", which the voice reads "mu" ("µ = 3", "µB"). Greek letters themselves
  stay with the voice (D-178).

### 3.4 Registry

`units` then `abbreviations`, after #67's `statistics` and `numbers` and before #65's
characters and hyphenation steps, which stay last (D-150, D-190). Two lines in
`BUILT_IN_STEPS` plus the docstring, merged with whichever of #98, #103 and #67 land first.
No overlap is expected with #67: its N5 exponent edit covers "10⁻⁴" but not the "×" (D-178),
its N6 power edit does not apply after a number and a space ("5 m²"), its N8 fractions are
digits only. #66's earlier edits win over "Ref. [1]" and "(e.g., [3])" (the citation or the
whole bracket goes), as intended.

## 4. Decisions for the coordinator (please assign D-numbers)

- **A. Scope principle** as D-176: edit only where the voice's real front end reads wrong
  (section 1), with two kinds of exception: symbols the voice reads only through espeak-ng
  (≈, ×) are made explicit as D-177 does, and every unit in the table gets an edit even if
  the voice reads it right, so plurals and the report are uniform. Alternative: expand every
  abbreviation and symbol (against D-54; "Dr.", "vs." and "%" are read right by misaki).
- **B. Two steps, two modules, two categories** (`units` in Numbers, symbols, units and
  statistics; `abbreviations` in Abbreviations), registry order as 3.4. Alternative: one step
  (one switch for two different things, against D-108).
- **C. Word lists as data**: two project-written TOML files in the package, loaded with
  `tomllib`; no third-party list. Alternative: Python dictionaries in the modules (less
  "kept as data"), or a copied list (a licence question for little gain: the lists are short).
- **D. The abbreviation list** of 3.1 (three kinds: anywhere, before a number, before a
  label) and the readings "that is", "for example", "compare" (cf.), "namely" (viz.),
  "circa" (ca.). Alternative for cf.: "see" (shorter, but not what it means).
- **E. "et al." left as printed**: the voice says "et al", which is how researchers read it;
  the cutter already knows it. Alternative: "and colleagues" (the old app's reading; longer,
  and it changes the author's words).
- **F. Left as printed: Dr., Mr., Mrs., Ms., vs., No., etc.** (read right by misaki).
  The `abbreviations` audit case therefore keeps "Dr." and "vs." in its script; its goal
  ("read in full") is met by the voice. Alternative: expand them too for a uniform script.
- **G. Reference-list abbreviations (p., pp., vol., ed., eds., edn.) are not in v1.0**: they
  occur only in reference lists (not read) and in citation locators (#66's). Adding them
  would put hundreds of set-aside edits into the report. Follow-up issue for "p. 8" in
  running text if a paper shows it.
- **H. Sentence ends**: the full stop of an abbreviation that ends a sentence stays as
  printed (3.1). Alternative: replace it with the abbreviation and leave sentence ends to the
  cutter (it would merge two sentences after "resp.").
- **I. #64's label words**: `wording.label_words` (D-145) stays where it is; a test checks
  that each of its entries reads the same as the abbreviation table, so the two cannot drift.
  Alternative: make `wording.py` read the TOML file (touches #64's module for no change in
  behaviour).
- **J. Units only after a number**; single-letter units only with a space; not after a label
  word; the explicit table of 3.2 with its exclusions. Alternative: prefixes combined with
  base units (larger, but brings in "pm", "Ms", "ks" collisions).
- **K. Plural agreement** singular only for exactly "1", plus the hyphen and "a/an" rule for
  attributive use. Alternative: plural for everything but "1" without the attributive rule
  ("a 5 kilometres race").
- **L. British spelling** ("metre", "litre") as in the issue. Alternative: American spelling,
  or by the job's language tag (en-US / en-GB) later; the voice reads both the same.
- **M. Compound units**: "/" and negative exponents read "per"; ²/³ read "square"/"cubic"
  on lengths and "squared"/"cubed" otherwise; products joined by space or "·".
- **N. Degrees and kelvin** as in 3.2, including an edit on "45°" for uniform plurals.
- **O. Magnitude suffixes** (441K, 15M, 175B) are #68's (letters after a number; not named in
  D-178), glued only, read "thousand", "million", "billion"; the "300K" collision accepted.
  Alternative: leave them to #67 (it has not planned them) or to v1.1.
- **P. Symbols** as 3.3: "%" left; "‰" per mille; "≈" approximately and "×" times made
  explicit; "~" about before a number only; "x" times between or glued after numbers; the
  micro sign as a letter becomes "μ".
- **Q. Speech-recognition round trip**: one slow, nightly test speaks the `units` regression
  case and checks with faster-whisper that "milligrams per kilogram" and "degrees Celsius"
  are heard, in the same test file and with the same helper as #67's statistics check (P of
  #67, D-191); if #67's helper has not merged yet, a small copy that the later PR folds in.

## 5. Tests (test-first)

1. **Regression cases first** (`tests/regression/english.toml`): change `expected` of
   `units` ("Doses of 3.5 milligrams per kilogram were given at 37 degrees Celsius.") and
   `abbreviations` ("... included, that is, preschoolers and toddlers, for example, in
   day-care (Figure 1). Dr. Smith compared them vs. controls (see Table 2). Approximately
   half were girls.", same three utterances; its "0–6" follows #67's range rule whichever
   lands first). `symbols` moves to `issue = 67` if #67 has not done it (D-178). #64's
   `figure-abbreviated-label` and `figure-label-in-capitals` now read their captions
   "Figure 3. Response over time." and "Figure 4 Response at rest." (the caption is read in
   its place, and its label word is now read in full). Add about 30 cases (`audit = 0,
   issue = 68`): each abbreviation kind, a sentence-final "resp.", capitals and glued forms,
   "et al." and "Dr." left (no edit); units with plural and singular, "per", negative
   exponents, powers, products, degrees, kelvin, angstroms in both printed forms, the
   attributive hyphen, magnitudes; and the "no edit" families: "1990s", "2D", "Figure 2 A",
   "at 5 pm", "0x1F", "X ~ N(0, 1)", "12%".
2. **Unit tests** per rule with exact spans, kinds, replacement texts and reasons, including
   every exclusion named in section 3, NBSP and thin space before a unit, line breaks inside
   "e.g.\n" and between number and unit, and both data files' load checks (a broken entry
   fails with a clear message).
3. **Conformance:** both steps pass `check_text_step(step, allow_ask=False)` through
   `test_textprep_conformance.py` automatically.
4. **Hypothesis** (ci and nightly profiles, both run), with text strategies weighted toward
   digits, unit letters, "/", "·", superscripts, degree signs, dotted abbreviations and the
   label words (density checked with a probe and a Counter): no crash; valid, non-overlapping
   edits; idempotent (running a step on its own output proposes nothing); neither step adds,
   removes or reorders a digit; `abbreviations` changes only letters and full stops.
   A 30k-example random fuzz of unit, number and abbreviation tokens through
   `core.check_edits` (the check that found #103's overlaps), and pathological length: a
   100k-character block of units and abbreviations runs in under a second (no per-match
   look-back over the text before it).
5. **Corpus:** the per-category corpus snapshot gains the `units` and `abbreviations` rows
   per paper; #70's script snapshot shows the new readings ("Equation (8)", "Algorithm 1",
   "for example", "9 kilograms", "25 millielectronvolts", "441 thousand"), diff explained in
   the PR.
6. **ASR round trip** as in Q (slow, nightly). I run it here once if the model download works
   in this session, otherwise the PR says it waits for the nightly run.

## 6. Size and order of work

About 500 lines of code in two modules, two data files (about 60 abbreviation and 120 unit
entries), about 800 lines of tests, the regression cases. One PR, branch
`textprep/issue68-abbreviations-units`, `Closes #68`, merged with main as #98, #103, #105
and #67 land. Then a KB PR with the decisions under the numbers you give. Follow-up issues:
German abbreviations and units (v1.1); spelling by language tag en-US/en-GB (v1.1);
reference-list abbreviations in running text (G, only if a paper shows them).
