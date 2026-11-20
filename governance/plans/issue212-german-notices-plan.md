# Issue #212: notices in German, and the language control in the web — plan

Thread "Read notices in German", 14 Nov 2026, on main 5a254e4. One PR, branch
`textprep/german-notices-212`, base `main` (never release/1.0). **Critical** (it changes golden
files and the conformance samples in `sci2audio.testing`), so `risk:high`; waits for the
coordinator's approval. Status: measured on a local prototype (not pushed), numbers below.

## 1. What is English-only today, measured

The issue's three steps are the only ones that put words of their own into the script:
`formula-notices`, `table-figure-notices` (textprep/placeholders.py) and `footnotes`
(textprep/footnotes.py) declare `languages = ("en",)`; their words come from one table,
`textprep/wording.py` (D-145). Nothing else speaks app-made words: chapter titles are the
document's own, reasons in the report stay English by D-291. The citations step's "reference 12"
words live in the same table but belong to #101.

With a German `Wording` row and the three steps opened to "de", the German paper
`arxiv2017-maass-privacyscore` reads its figure as "Abbildung 1 wird übersprungen." instead of
the diagram's 5 lines, and every note starts "Fußnote 1." — but only **3 of its 30 footnote marks**
are found, so the corpus test the issue names would still fail. The 27 missing marks:

- 26 are "superior figures": set in the text's own size (10.0 pt, like the text) but raised.
  Layout learned this for the notes themselves in #235 (D-507, `footnote_mark_rise` 0.1 em), the
  footnotes step only knows "tagged sup" or "set smaller".
- 1 ("Alexa Top 1 Million“9") stands after the German closing quote “ (U+201C), which the step's
  list of closing punctuation lacks (it has ” and ’).
- 1 is the title's "*" while the note's label is "∗" (U+2217).

With three small changes in `footnotes.py` (section 2, item 3) all **30 of 30** are found.

**English stays byte-identical**, measured: every corpus file (8 PDFs, the EPUB, both English
Markdown and text samples) run through `run_script_job` on main and on the prototype gives the
same script bytes for all 11 English files; only the German paper and the German Markdown sample
change. The fast suite shows no English golden change.

espeak-ng German (through misaki, the #211 front end) reads the proposed wording right:
"Fußnote 1. Der Text" → "fusnote eins. der text" (no ordinal, the cut after "1." is a real
sentence end), "Formel 16a" → "sechzehn a", "Formel IV" → "römisch vier", "Tabelle A.1" → "a
punkt eins", "Abbildung 1 und Tabelle 2 werden übersprungen." fine.

## 2. The change

1. **`textprep/wording.py`**: a `GERMAN` row, `WORDING = {"en": ENGLISH, "de": GERMAN}`:
   "{} wird übersprungen." / "{} werden übersprungen.", ", " and " und ", unnamed "Eine Tabelle
   wird übersprungen.", "Eine Abbildung wird übersprungen.", "Eine Formel wird übersprungen.",
   "Formel {}", "Fußnote {}." / "Fußnote.", label words "Abb." → "Abbildung", "Tab." → "Tabelle",
   "Gl." → "Gleichung", "Alg." → "Algorithmus" (the same readings as the German abbreviation table
   of #113), and the reference words "Quelle", "Quellen", "bis" (#101's issue wording; unused
   until #101 opens the citations step to German, Q4). English row unchanged.
2. **Steps**: `formula-notices`, `table-figure-notices` and `footnotes` declare `("en", "de")`.
   The footnote step's "already introduced" check (`_INTRODUCED = "Footnote\b"`) comes from the
   job's wording ("Fußnote\b" for German) so the step stays still on a second run.
3. **Footnote marks** (Q3): a mark is also found when its run is raised `RISE = 0.1` em above a
   run next to it on the same line (mirrors layout's `footnote_mark_rise`, D-507); “ counts as
   closing punctuation before a mark; "*" in the text matches a note labelled "∗". The other
   conditions stay (label of a note on the same page, after a word, no maths operator after it,
   each label once per page). These apply to every language; English output unchanged (above).
4. **Web** (Q5, Q6): the document page's check form gets "Language of the text" (a select:
   "Automatic: as the file states, else guessed", "English", "German"), next to the switches.
   Changing it marks the form as changed, like a switch, so "Update" runs the check again with
   it; the existing note ("Language of the text: German (your setting)") moves with it. The audio
   job uses the language the report on screen was made with (`shown.language`), not the saved
   settings. Not remembered between documents. Strings in `en.toml` and `de.toml` (`check.language*`).
5. **CLI**: `--language` exists (#211, #219); its help text gains "also the language of the
   spoken notices". Nothing else.
6. **Docs**: CHANGELOG "Unreleased" line; README's "short spoken notice" sentence says "in the
   text's language (English or German)".

## 3. Tests

- **Regression** (`tests/regression/german.toml`, new section "#212 notices", golden): table
  named by its caption, "Abb. 3" read "Abbildung 3 wird übersprungen.", two captions joined with
  "und" → "werden übersprungen.", formula with number "Formel 4 wird übersprungen.", formula
  without, figure without caption "Eine Abbildung …", footnote with number "Fußnote 1." and
  mark removed, footnote with a symbol "Fußnote.", German closing quote before a mark.
- **Unit**: `test_textprep_placeholders.py` / `test_textprep_footnotes.py`: the two tests that pin
  "English only" become "English and German, other languages not run" (a French job is still not
  run); raised mark found / not found when not raised or on another line; "*" ↔ "∗"; second run
  of the footnote step on a German script adds nothing; `wording_for("de-AT")` is German.
- **Conformance** (`sci2audio.testing`, critical): the German sample document gets a table with
  caption "Tabelle 1: …", a numbered formula, a figure and a footnote with its mark, so the three
  steps are checked on German too (edits valid, idempotent).
- **Corpus**: remove the two #212 entries from `GERMAN_LATER` (rules corpus) and the three from
  `GERMAN_LATER_STEPS` (app corpus); the notice and footnote checks read their words from
  `wording_for(document.language)` instead of the English literals. Golden re-recorded, German
  only: the German paper's script and report (D-510), its footnote-marks snapshot (30 marks, new),
  the German Markdown sample's script (`test_layout_language`). English goldens untouched.
- **Web**: TestClient: a script job with `language: "de"` gives German notices; the page renders
  the select with the report's language chosen. **Browser** (`tests/browser`): choose German,
  Update, the changes table shows "… wird übersprungen."; axe-core clean.
- Full gates: ruff, format, lint-imports, deptry, fast suite, browser suite.

## 4. Lanes and other threads

The issue is labelled lane:textprep, and the notice table lives in textprep. My textprep edits are
limited to `wording.py`, `placeholders.py` (one line), `footnotes.py` (the three mark checks and
the introduced check) and the German regression file. The German text rules thread works in
numbers/statistics (#130) and later links/citations (#101); the overlap is `german.toml` (own
section, a plain merge) and `wording.py` (#101 then uses the reference words already there
instead of adding a row). I will tell that thread when the plan is approved. Nothing on
release/1.0.

## 5. Out of scope (new issues at PR time)

- German units read "W" in court file numbers as "Watt": "Az. 2 W 12/07" → "2 Watt 12/07"
  (seen in the German paper's notes 19, 20). For #113's follow-ups (v1.2).

## 6. Open questions, with my recommendation

- **Q1 Wording.** Recommended: "… wird/werden übersprungen.", "Eine Tabelle/Abbildung/Formel wird
  übersprungen.", "Formel 4", "Fußnote 1." / "Fußnote." — the issue's own example, parallel to the
  English row, and the interface already says "mit einem kurzen Hinweis übersprungen". Not chosen:
  "ausgelassen" (no gain, breaks the parallel with the interface); "Anmerkung" for notes.
- **Q2 Label words.** Recommended: German short labels only (Abb., Tab., Gl., Alg.); an English
  "Fig. 3" in a German job is named as printed. Not chosen: mapping "Fig." to "Abbildung" too
  (rewrites a printed name across languages).
- **Q3 Finding the German paper's marks here.** Recommended: yes, the three checks of section 2.3
  (about 25 lines in footnotes.py), since the issue's acceptance line needs the marks test on the
  German paper and English output is unchanged on the whole corpus. Not chosen: keep a corpus
  exception for the marks test with a new issue (the German paper would read "Qualys5 und
  Mozilla.6" aloud in v1.1).
- **Q4 Reference words in the German row.** Recommended: "Quelle", "Quellen", "bis" set here from
  #101's issue text, so the row is complete once; #101 only opens its step. Not chosen: leaving
  them to #101 (the dataclass needs every field; a placeholder value would be worse).
- **Q5 Where the web control lives and whether it is remembered.** Recommended: in the check
  form, applied by "Update", per document, not saved in the settings (a remembered "German" would
  read the next English paper with German rules). The audio job takes the report's language.
  Not chosen: a saved setting on the settings page; a control next to the voice (the language
  changes the script, so it must re-run the check).
- **Q6 Choices offered.** Recommended: Automatic, English, German; if the report was made with
  another tag (e.g. "en-GB" from the config file or CLI), that tag is a fourth option, selected,
  so nothing changes silently. Not chosen: a free text field (BCP 47 is not for everyone).
- **Q7 Conformance sample.** Recommended: extend the German sample document (critical, the
  conformance suite every plugin runs). Not chosen: a separate German-only check (the samples are
  where every step is checked).
- **Q8 One PR.** Recommended: one PR (about 80 lines of code, 300 of tests, goldens); the web part
  is small and the issue is one acceptance list. Not chosen: splitting web from textprep.

## 7. Size

Code about 80 lines (wording 25, footnotes 30, placeholders 1, web 25), strings 8 keys per
language, tests about 300 lines, goldens German only.
