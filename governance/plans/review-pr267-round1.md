# Review PR #267, round 1 (German sentence ends, #227 #229, D-530)

Reviewed head 626f147 (main 2c9adac merged in), 14 Nov 2026 ~12:00 UTC. Plan:
plans/issue227-229-german-sentence-ends-plan.md.

## Checked and fine

- Every changed golden line read. `test_app_corpus.ambr`: 18 cuts inside "i. S. v.", "i. V. m."
  and "LG Ulm v." gone (182 → 164 utterances); each join is one a German listener wants.
  `test_layout_language.ambr`: "1. Einleitung" one utterance (wanted). No other golden moves.
- All 13 corpus scripts and reports rebuilt main vs PR (`run_script_job`, own output folder):
  11 byte-identical incl. every English one; only the two German scripts differ, as claimed.
- ~80 hand shapes, main vs PR, whole chain twice: no second-run change anywhere on the PR
  (main's "Die 12. … Dann" second-run break is fixed). All plan rows behave as planned.
  English citation rule: "See e.g./i.e./Fig. (Smith, 2019). Then" now keep the full stop;
  "et al." unchanged.
- Fast suite 4,245 passed; 2 linear-time tests failed only while my corpus/timing runs loaded
  the machine and passed alone (12/12). Nightly seeds 7, 4242, 90210 on the utterance, units,
  German numbers/citations and citation test files: see the PR review.

## Findings

R1 (must fix). `opens_sentence` counts the first part of a hyphenated compound as an
opener. Regressions against main (main read the ordinal):
- "Der 2. In-vitro-Versuch lief gut." main "Der zweite In-vitro-Versuch", PR "Der 2." / "In-vitro-Versuch lief gut."
- "Es folgte der 2. Vor-Ort-Termin.", "Die 3. Nach-Untersuchung kam.", "Die 2. Seit-Ansicht fehlt." same.
- units: "Es dauerte 2 Std. Ein-Euro-Jobs kamen später." now cut (debatable).
Fix: a word followed by a hyphen (- U+2010 U+2011) is no opener; tests for these rows.

R2 (must fix, accuracy). "i. V. m." is still cut after "m." before a capital: three corpus
utterances end in "… GG i. V. m." / "… in dem i. V. m." and the next starts "Artikel …"
(snapshot lines ~12290, 12318, 12320). Hand shape: "Gemäß Art. 2 Abs. 1 i. V. m. Art. 1 Abs. 1
GG gilt das." → cut before "Artikel 1". The PR body ("GG i. V. m." whole) and #264 ("The
#227/#229 PR fixes the cut; this issue is only the reading") say otherwise. Either fix it here,
or correct the PR body and #264 (acceptance criterion: no cut after "i. V. m."; the three
corpus lines join). Reviewer leans to the second: once #264 lists "i. V. m." it is a
replacement the cutter never cuts inside, and its tokens join ABBREVIATIONS["de"] by themselves.

R3 (should fix). The opener list breaks its own rule ("nor a word that is also a noun after
a number"): Laut, Ich, Sein, Nichts, Etwas, Ja, Nein. Measured: "Der 3. Laut des Wortes ist
stumm." main "Der dritte Laut …", PR "Der 3." / "Laut des Wortes …"; "Das 2. Ich ist stark."
the same. Remove the twins that seldom open a sentence right after a number, or keep them and
name the trade-off in the list comment and the cutter docstring. Say which.

R4 (fix or issue). "»" opens a sentence for `opens_sentence` but not for the cutter's
`_OPENING`: "Es dauerte 2 Std. »Danach« kam er." keeps "Stunden." but is not cut; "Es waren
3. »Die Studie« lief." not cut (main the same). Add "»" to `_OPENING` with a test, or file an
issue.

## Side finding (on main, filed by the reviewer)

#268: `_sentences` looks up the word before each full stop with `_LAST_WORD.search(text, 0,
…)`, quadratic: main cutter alone 3.98 s / 15.25 s / 60.81 s on 48k / 96k / 192k characters
of short English sentences. The PR adds more checked sentence ends, so German shapes get
~1.5–2x slower, but the cause is on main. No milestone set; coordinator to place it.
