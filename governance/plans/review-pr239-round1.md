# Review of PR #239, round 1 (head 8d45e56, base main 0bb973f)

PR: layout: a real German paper in the corpus, its LNI running heads found (#235). Critical
(new corpus file, truth file, goldens, three layout rule changes). Plan
`plans/issue235-german-corpus-plan.md`, decisions D-502 to D-516.

## Verdict

Correct and close to mergeable. Two small fixes (F1, F2), then merge. No blocking finding in
the layout code.

## What I checked, and how

- **CI on 8d45e56**: every check green (tests on Linux, macOS, Windows; lint and layers;
  licences; browser; security; CodeQL; "CI passed").
- **Fast suite locally**: see the end of this file.
- **Corpus against main** (`run_script_job` on all 13 corpus files, main's code via
  PYTHONPATH vs the branch): the scripts and reports of the 12 other files (7 English papers,
  the EPUB, both Markdown and both text files, German samples included) are **byte-identical**.
  Only the new paper differs, and only where intended: its 12 running heads are left out (report:
  page furniture 1 → 13), its 30 notes are footnote blocks (0 → 30 labelled), and its diagram text
  sits in one FIGURE block named "Abb. 1". The top-band extension does not fire on any English
  file (each prints something in the paper's top 10 %).
- **Truth file vs page images** (`pdftoppm -r 80`, all 13 pages viewed): 13 pages, one text
  column each; headings 1 to 7 and "Literaturverzeichnis", all level 1; run-in heads
  ("Abstract:", "Keywords:", "Flexibilität durch Nutzerorientierung", "Offene Daten und
  Vertraulichkeit", "Implementation", "Anschaulichkeit und Handlungsempfehlungen", "Zulässigkeit
  der automatisierten Untersuchung von Webseiten", "Rechtliche Bewertung der
  Untersuchungsergebnisse", "Rechtliche Herausforderungen hinsichtlich der Veröffentlichung der
  Ergebnisse", "Danksagung") correctly not headings; side stamp on page 1; 12 alternating running
  heads, page number in the line, none on page 1; footnote marks per page exactly as printed
  (1, 2, 3, ∗ | 4–8 | 9, 10 | none on 4 | 11, 12 | 13 | 14–18 | 19, 20 | 21–23 | 24, 25 | 26, 27 |
  28, 29 | none on 13); one figure "Abb. 1" on page 3; no tables, formulas or algorithms; page 3's
  three-column diagram labels (D-508, #238). The six verbatim sentences are on the pages named
  (page breaks 1→2 "(etwa Google / Analytics)" and 12→13 "herzustellen / und Öffentlichkeit",
  "ins-/besondere" on page 2, mark 7 after "überprüfen."). No error found.
- **Licence**: PDF sha256 a501d499…4be4 as stated; LICENSES.md row names title, the three
  authors, arXiv source and abs page, CC-BY-4.0, Covers, #235. Corpus 8 papers (limit 10).
- **German hyphens**: all 38 readings checked against the page images. Every "join" is a
  TeX split ("imple-mentieren", "Zusammenhangs-analysen", "Lö-schungsanspruch" …), every "keep"
  is a hyphen of the word ("Datenschutz-Aufsichtsbehörden" twice, "PrivacyScore-Plattform").
  Right German. The one listed miss ("Datenschutz-Grundverord-/nung", rule keeps) is real; filed
  as **#240 (v1.2)**.
- **Top band (D-502 to D-505)**: `edges()` gives a first-row band only when no non-stamp line,
  picture or drawing starts in the paper's top `edge_band` on any page; `first_row` is
  min(top of every line) + `head_drift` em, so only the first row joins. The bottom band is
  unchanged. `build.py` placement and every furniture rule use the same `Edges` (D-504). The
  tests cover all four cases, plus a Hypothesis property; nightly profile on the new tests: 5
  passed. Fails safe: a page-filling background drawing makes the document fall back to today's
  band.
- **Caption names (D-506)**: one list, not language-gated; `Algorithmus` matches after the
  `Algorithm` branch backtracks; `startswith(_TABLE)` cannot confuse Tabelle/Table
  (T-a-b-e vs T-a-b-l). "Abb. 1 zeigt …" stays a paragraph (test).
- **footnote_mark_rise (D-507)**: applies only to the first run of a row in the notes area,
  number or note symbols only. Measured on the corpus, the rise of a full-size number run over
  the next run, all lines of all papers: German marks 0.345 em; the highest elsewhere is 0.054 em
  (Liu's reference list, bold volume numbers), then 0.021 and 0.01 (JOSS affiliations). So no
  superscript citation or exponent in the English papers comes near 0.1 em, and English
  snapshots are unchanged.
- **Skip tables (D-509)**: `GERMAN_LATER` names exactly 2 tests for #101 and 2 for #212; both
  issues carry the acceptance line. `GERMAN_LATER_STEPS` in test_app_corpus.py also names
  #130 for "numbers" and "statistics" (correct: those steps are English only); #130 lacked the
  acceptance line, added in this review. The German paper's report lists exactly these 7 steps
  as not run (measured).
- **Corpus test edits**: the outline test now accepts a heading with or without its printed
  number (needed for LNI, not a weakening); hyphen tests read each paper by its language;
  footnote count split 39 English / 30 German; NOT_YET_COLUMNS lists page 3 with #238.

## Fix list

- **F1** `tests/unit/test_app_corpus.py`, `test_every_paper_runs_with_its_chapters_and_no_problem`:
  assert `set(done.report.not_run) == set(GERMAN_LATER_STEPS)` instead of `<=`. Today the
  German paper's not-run steps are exactly the 7 keys (measured), and with `<=` an Issue that
  lands (#130, #101, #212) can leave its entry behind unnoticed; with `==` the table must shrink
  as the comment says ("An Issue that lands takes its steps out").
- **F2** `tests/regression/line-end-hyphens-de.toml`: name #240 in the `why` of the one
  `[[miss]]` (e.g. "…; #240"), and say "One miss is listed (#240)" in the PR body.

## Not required, noted

- #156 (v1.2, smaller lines repeated at the page edge taken for running heads) now also
  applies to the first row of a small type area; commented there.
- The German paper's script golden speaks the diagram labels and footnote marks: by design until
  #212 (D-510).

## Local fast suite (8d45e56)

`pytest -m "not slow and not benchmark and not browser"`: 3,713 passed, 5 skipped (4 German
paper skips named #101/#212, 1 Windows-only), 74 snapshots passed. Matches the PR body.
