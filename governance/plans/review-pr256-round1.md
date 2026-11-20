# Review of PR #256 (#101 German links and citations), round 1

Head 478a485 (main 3b9ac6d merged in). Reviewer: review thread "Review German references PR", 14 Nov 2026.

## What I checked

- CI on 478a485: all jobs green (Linux, macOS, Windows, browser, lint and layers, licences, security, CodeQL).
- Fast suite locally: 4120 passed, 1 skipped. Two `test_core_properties` health-check failures ("input generation is slow") came from my own corpus runs loading the machine; the file passes alone (10 passed).
- Nightly profile, German module (`-k "second_run or contract"`), seeds 1, 7, 42, 99, 1234, 4242: all clean (29 passed each). English links, citations and statistics modules, nightly, seeds 5 and 77: see the end of this file.
- Corpus, `sci2audio script --chapters all` on all 13 corpus files, main 3b9ac6d vs PR:
  - English scripts byte-identical except the Markdown sample's one line ("project page and; see" → "project page; see"). Liu report: four "[17]"-style reference-list removals take the space after instead of the one before; script identical.
  - German text and Markdown samples: scripts identical (no links or citations in them); reports lose the "links/citations not run" problems.
  - German paper (maass-privacyscore): the three e-mail addresses go, ten link-only footnotes go whole, "ein Prototyp ist unter https://privacyscore.org/ abrufbar" reads "ein Prototyp ist abrufbar", "(vgl. Suchmaschinen und z. B. https://archive.org/)" reads "(vergleiche Suchmaschinen)". All right against the printed text. Its citations are alphanumeric keys ([MH17]): #254.
- Conformance sample: the German document's two new paragraphs sit before "Literatur"; the section bounds (0–12, 12–14) point at the right headings. Both steps now run on it. Coherent.
- About 120 hand probes (German and English), each through the whole chain twice; English on main vs PR.

## The English change (asked by the coordinator)

English is not byte-identical on hand-made text, but every difference is one of the three rules the PR body names and pins in `english.toml`:
- dangling join: "We compare X and https://y.org." main "X and.", PR "X." Correct, and the Markdown sample line follows from it. **Accepted.**
- said sign: "less than [4]", "greater than [12]", "equals [5]" now keep the bracket (main read "reference 4", and "x = [12]" changed on a second run). Prose like "greater than [12]" is rare, and the second-run fix needs it. **Accepted.**
- citation after a removed link sentence: main "[12] It holds." on the first run, PR "It holds." **Accepted.**

## Findings

### M1 (must fix): a link after an abbreviation's full stop eats the sentence's full stop

`links._starts_sentence` reads every "." plus a space as a sentence end, so a link after "z. B.", "u. a.", "bzw.", "ggf." counts as a sentence of its own, and `_whole_sentence` takes the full stop after it:

| printed | PR reads |
|---|---|
| Die Daten liegen z. B. unter https://x.org. Dann mehr. | Die Daten liegen zum Beispiel Dann mehr. |
| Daten finden sich u. a. unter https://x.org. Dann mehr. | Daten finden sich unter anderem Dann mehr. |
| Code liegt bei GitHub bzw. https://x.org. Dann mehr. | Code liegt bei GitHub beziehungsweise Dann mehr. |
| Mehr bei https://a.org bzw. https://b.org. | Mehr beziehungsweise |

Two sentences run together with no full stop and the cutter makes one utterance of them. German writes these abbreviations before links all the time. Fix: a full stop that ends one of the language's abbreviations (the German `CitationWords.abbreviations`, or `utterances.ABBREVIATIONS`) is no sentence end for `_starts_sentence` (and for `_SENTENCE_END` in `only_links_before`). Add German regression cases. English has the same mechanism on main ("The data are online, e.g. https://x.org. Then more." reads "for example Then more."). Either fix it for both, with an English regression case and the English corpus still byte-identical, or keep English as it is and file an issue for it.

### M2 (must fix, small): "bzw." is no German link join

"Die Daten bzw. https://x.org sind neu." reads "Die Daten beziehungsweise sind neu.", and "https://a.org bzw. https://b.org" is not one run. Add "bzw." (and "bzw") to the German `joins`. `_dangling_join` keeps only all-letter joins, so make sure a dangling "bzw." goes too.

### S1 (should fix): access notes

- "(Abruf: 3.5.2017)" is not an access note: the list has "abruf am" and "abrufdatum" but not "abruf". It now reads "(Abruf: dritter Mai 2017)".
- "Die Seite https://x.org/r, abgerufen am 3.5.2017, zeigt es." reads "Die Seite, zeigt es.": a note set off by commas mid-sentence should take its closing comma (or the opening one) too.

### D1 (defer: issue, v1.1 with #253 or a new one): rare second-run cases from a wider fuzz

My own fuzz (3000 German blocks with "bzw.", "u. a.", "ggf.", "Kap.", "S.", "gleich", "(ebd., S. 3)", "[3, S. 4]" added to the PR's vocabulary) found 12 second-run differences out of 3000. They come down to two shapes:
- "Siehe Kap. https://x.org/a (ebd., S. 3)." reads "Kap." on the first run and "Kapitel" on the second (the abbreviations step reads "Kap." before a bracket, not before a link).
- "Die 12. (Müller & Schmidt, 2019). Dann mehr." reads "12." on the first run and "zwölfte" on the second (a removed citation after an ordinal-looking "12."). The same family is on main: "Daten zeigt 12. Kap. (Müller, o. J.). Dann mehr." fails on main too.
Both are rare in real text. Not blocking. Add them to #253 or file a new v1.1 issue.

### Observations (no change asked)

- Affiliation lines keep a trailing comma after the e-mail goes ("Darmstadt, Deutschland,"). English does the same on main.
- Shared English behaviour on main that German now inherits: "Zwischen [1] und [3]" reads "Zwischen und Quelle 3" (English "Between and reference 3"); "Wir danken https://x.org und Müller" reads "Wir danken und Müller"; "[12, S. 3]" is not read as a source. Filed by the reviewer as #257 (v1.2).
- "Werte in [1,5, 3,5]" reads "Quellen 1, 5, 3 und 5". The ";" guard is right for German intervals; a comma-separated pair of decimal commas is ambiguous with "[1,2]" citations, so I leave it.
- "Die Ärztekammer (2019)", "des Statistischen Bundesamtes (2019)" stay as printed (an article before them); "Laut WHO (2019)" keeps the name. Conservative and fine.

## Verdict

Changes requested: M1 and M2 must be fixed; S1 should be fixed in this round; D1 goes to an issue. Everything else is approved, including the English changes.

## Nightly, English modules

`test_textprep_links.py`, `test_textprep_citations.py`, `test_textprep_statistics.py` with `HYPOTHESIS_PROFILE=nightly`, seeds 5 and 77: 325 passed each.

PR review posted: https://github.com/dubidu22/sci2audio/pull/256#pullrequestreview-5903262790
