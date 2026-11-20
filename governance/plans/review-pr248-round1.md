# Review of PR #248 (#212 German notices + "Language of the text"), round 1

Reviewed head 62eb832 (8f605c7 + merge of main 98eb92a), 14 Nov 2026. Verdict: **changes requested**
(one must-fix, two should-fixes). Everything else checked and fine.

## What I verified

- Gates locally: ruff, format, lint-imports, deptry clean; fast suite (ci profile, -n 8) 3793 passed,
  3 skipped (2 wait for #101, 1 Windows-only). CI on 62eb832 all green (3 OS, browser, ZAP, CodeQL).
- **English byte-identity**, run_script_job on main (PYTHONPATH main worktree) vs PR, every corpus
  file (8 PDFs, EPUB, 2 Markdown, 2 text), languages automatic / "en" / "de", default switches and
  all switches on (Footnote texts too): with automatic and "en", every English file's script,
  report.json and report.md are byte-identical. Only the German paper, the German Markdown note
  (script + report) and the German text sample (report only: not_run list) change. Forcing "en" on
  the German paper changes it too (expected: the three mark checks apply to every language).
- German paper: 30/30 marks left out (new snapshot), every note introduced "Fußnote N." /
  "Fußnote.", "Abbildung 1 wird übersprungen." replaces the diagram text. Script diff read in full.
- footnotes.py: the change is the three checks of plan 2.3 (RISE, “ in _CLOSING, "*"→"∗" via _same)
  plus the wording-driven introduced check. No other behaviour change.
- Wording: correct German; three-item list "Abbildung 1, Abbildung 2 und Tabelle 1 werden
  übersprungen.", "Formel IV", de-AT → German, English "Fig. 2" in a German job named as printed
  (D-518). espeak-ng de readings fine ("Fußnote eins.", "Fußnote a.").
- Web: select in the check form, changing it shows "changed" and Update re-runs the check with the
  language; audio job takes shown.language; the PUT of remembered settings keeps the saved language
  (not persisted, D-521); browser test covers all of it including "next document starts automatic".
  Strings en/de read well. Option for another tag (D-522) present.
- Conformance sample: German document extended with mark+note, table+caption (describes=6 points at
  the table), numbered formula, empty figure; section ranges moved 0-10 / 10-end correctly. Same
  block kinds the English sample already has, so coherent for plugins.
- GERMAN_LATER: both #212 entries gone from the rules corpus table (now empty), the three steps gone
  from GERMAN_LATER_STEPS. The rewritten notice corpus test is not weaker (StopIteration fails it if
  a notice has no known ending; unnamed formulas still counted against the truth).

## Must fix

**M1. A run counts as "raised" against a run on the next or previous line.** `_runs` yields the
runs of all lines of a block in one list, and `_raised` compares a run with list neighbours
`number ± 1`, which at a line start or end is the last/first run of the adjacent line. The "same
line" test is only box overlap, and font boxes of adjacent lines overlap with normal leading, so the
upper line's run looks raised by about 1 em. Measured on the corpus (runs not set small, passing
`_raised`, `_after_word` and `_not_maths`, i.e. only the label match missing): 279 such runs come
only from a neighbour on another line (chi-plue 158, biggs-pymedphys 72, hardt 40, nowak 4, liu 5),
e.g. chi-plue p.1 "information is handled. Natural language un-". They are harmless today only
because none equals a note label on its page. A label-like run at a line start/end in its own style
(an italic "a" variable before "in", a bold "2" at the line end) would be removed silently whenever a
note with that label is on the page. The German paper's 26 superior figures all compare with a run
on their own line, so restricting the comparison to runs of the same TextLine keeps 30/30.
Fix: compare only with the neighbour runs of the same line; add a unit test with two overlapping
lines (line 1 ending in a label-only run, line 2 below with an overlapping box) that keeps the run.

## Should fix (or defer with an issue)

**S1. The reference run should be in the block's main size.** Same-line, a normal run next to a
subscript counts as raised (liu: " for" after "j" + subscript "zy"; nowak "X" before subscript
"j"). Requiring the neighbour that the rise is measured against not to be set small
(`not _set_small(neighbour, main)`) removes that class and keeps the German paper's 26 (their
neighbours are TeXGyreTermes at 10 pt).

**S2. The other German closing quotes.** “ was added, but German print also closes with ‘ (U+2018,
„…“ / ‚…‘) and with « (»…«, common in German books) or » (Swiss «…»). Probed with sup marks:
"die »Top 1 Million«9", "es ‚klein‘8", "es «gross»7" all keep the mark ("…Million«9 jeden Monat").
This is the same check (closing punctuation before a mark), so adding ‘ « » to `_CLOSING` stays
inside D-519; please add a regression case in german.toml and rerun the English corpus comparison.

## Observation, out of scope (issue filed)

"Formel 3.2 wird übersprungen." is read by espeak-ng de as "drei.zwei" (dotted number), where the
English row gets "three point two". Notices with dotted labels need the German number reading of
#130/#242 or a notice-specific reading. Filed as #249 (v1.2).

## Overlap with PR #242

#242 (German numbers, in review) also re-records the German paper's goldens. Whichever merges
second merges main and re-records; I'll recheck the goldens after that.
