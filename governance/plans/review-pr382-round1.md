# Review PR #382, round 1 (textprep batch 2 PR 2: German readings and units #230 #231 #233 #250 #265 #358, legal forms #264)

Head reviewed: 7189d6a (main c841f3d merged in). Plan: plans/textprep-v12-second-batch-plan.md PR 2 (D-646), with #264 added by D-650. Critical.

**Verdict: not approvable yet. There is one blocker (B1), two should-fix items (S1, S2) and one nit (N1).** The PR now also conflicts with main 8a8f863 (#377) in `tests/regression/english.toml`, `tests/regression/german.toml` and `tests/unit/__snapshots__/test_app_corpus.ambr`, so main must be merged in first.

## What I checked

- **Plan.** The change follows the plan for all seven issues. The PR body closes all seven, and the commit messages carry no closing keywords.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 5739 passed, 1 skipped.
- **Corpus.** 13 documents against main c841f3d. Twelve are byte-identical. In the maass script, every change is one of the 51 legal readings: "v." → "vom" 28, "i. S. v." 13, "lit." 6, and "i. V. m." 4, three of them joining the next line. Nothing else changes.
- **Probes.** About 75 hand rows (en and de) ran through the whole chain twice, against main.
  - These read as the plan asks, the same on both runs:
    - #230: "pro m²", "je m²", "pro Std.", "per m²"; "pro A-Gruppe" and "pro t" stay.
    - #231: "S. 12 f.", "Seiten 12–13 f."; "f. d." and "Der Wert f." stay.
    - #233: "p. a.", "p.a.", "1 %-Hürde", "1 kg-Packung".
    - #250: "m/s²" and "m s⁻²" read "Quadratsekunde"; English is unchanged.
    - #265: "Das war 2019. Kapitel 3".
    - #358: "y < 2x" now agrees on both runs; "less than 2x slower" is unchanged.
    - #264: "i. S. v." and "i.S.v.", "i. V. m." and "i.V.m.", "lit. f", "Rn.", "Hs.", "v." before "12.03.2015", "12. März 2015", "1.2.2010" and "12.03."; "Abs. 1 S. 2" and "Absatz 2 S. 3" read "Satz"; "v. Chr." and "v. Goethe" are unchanged.
  - The #264 cut after "i. V. m." is gone: "Gemäß Art. 2 Abs. 1 i. V. m. Art. 1 Abs. 1 GG gilt das." is one utterance.
- **Token fuzz.** 6,000 texts (de and en, seeds 1 and 2) from 57 tokens (legal forms, per words, units, dates, ordinals, comparisons) ran through the whole chain twice against main. There were no crashes. Seven texts differ on a second run on the PR but not on main, and all seven are B1.
- **Judgement calls in the PR body:**
  - **"i. S. d." as "des":** not accepted, see S1.
  - **"lit." as "Buchstabe":** accepted. German statute text writes it so.
  - **"p. a.", "a. F." and "n. F." end a sentence before any capital:** accepted for "p. a." and for "a. F. Die …". Not accepted where the next word is a law's short name or a label, see S2.
- **#265's narrowing:** accepted. With an article before the number, the ordinal stays ("das 2019. Kapitel", "zum 1250. Jubiläum" style). The code comment says so, and the plan's row ("Das war 2019. Kapitel 3") has no article.
- Mutants, nightly seeds and `ci:full` are left for the approving round.

## Fix list

### Blockers

**B1. After "i. S. d.", an ordinal number reads differently on the second run (D-577).** Run 1 checks the ordinal's left context in the printed "i. S. d.". Run 2 sees "im Sinne des", and "des" sets the ending:

| printed (de) | run 1 | run 2 |
|---|---|---|
| `Das gilt i. S. d. 3. Abschnitts.` | `… im Sinne des 3. Abschnitts.` | `… im Sinne des dritten Abschnitts.` |
| `Das gilt i.S.d. 3. Abschnitts.` | same | same |
| `Das gilt i. S. d. 2019. Kapitel 3 beginnt.` | `… im Sinne des 2019. Kapitel 3 …` | `… im Sinne des zweitausendneunzehnten Kapitel 3 …` |

The fuzz found the same with "3.", "1.2." and "2019." after "i.S.d.". The run 2 reading is the right one ("im Sinne des dritten Abschnitts").

Fix: the ordinal and date rules must take a listed abbreviation's reading as their left context, so that run 1 reads what run 2 reads. One way is to let `_ending` and `_after_preposition` see the last word of the reading of an abbreviation that ends right before the number ("i. S. d." → "des", "i. S. v." → "von", "i. V. m." → "mit"). If S1 keeps "i. S. d." as printed before a number, its rows must still read the same on both runs.

Tests: the three rows above plus "i. S. v. 3. Abschnitt" and "i. V. m. 2. Alternative", in German, on both runs. They must fail on 7189d6a. Add the legal forms to the PR's second-run property, which now leaves them out.

### Should-fix

**S1. "i. S. d." reads "des" before a feminine noun, so the wrong word is spoken.** "i. S. d. DSGVO" reads "im Sinne des DSGVO", and "i. S. d. Richtlinie" reads "im Sinne des Richtlinie". "i. S. d. DSGVO" is one of the most common shapes in German data-protection texts. A wrong article goes against faithful text (D-57). The corpus has no "i. S. d.", so this costs nothing there.

Fix: read "im Sinne des" only right before "§", "§§", "Art." or "Abs." (or before a word list you choose that takes "des"). Anywhere else, leave "i. S. d." as printed. Rows: "i. S. d. § 3 BDSG" and "i. S. d. Art. 4 DSGVO" read in full; "i. S. d. DSGVO" and "i. S. d. Richtlinie" stay as printed. Both spellings, both runs.

**S2. "a. F." and "n. F." end a sentence before a law's short name or a label, so the script gets a full stop and a cut inside a sentence.** Main keeps each of these as one utterance:

| printed (de) | utterances on the PR |
|---|---|
| `Nach § 28 a. F. BDSG gilt das.` | `Nach § 28 alte Fassung.` / `BDSG gilt das.` |
| `Nach Art. 7 a. F. EGBGB gilt das.` | `Nach Artikel 7 alte Fassung.` / `EGBGB gilt das.` |
| `Nach § 28 BDSG a. F. Abs. 2 gilt das.` | `Nach § 28 BDSG alte Fassung.` / `Absatz 2 gilt das.` |
| `Nach Art. 7 n. F. Satz 2 gilt das.` | `Nach Artikel 7 neue Fassung.` / `Satz 2 gilt das.` |

German capitalises every noun, so "before a capital" is a weak sign of a sentence end for a form that mostly stands inside one. "usw." is different because it mostly ends its sentence.

Fix: "a. F." and "n. F." do not end a sentence before an all-capitals word ("BDSG", "GG"), "§", a listed label abbreviation ("Abs.", "Art.", "S.", "Nr.") or "Satz", "Absatz", "Artikel" or "Nummer" followed by a number. "a. F. Die Norm ist alt." still ends its sentence. Add the four rows above as regression rows with `utterances`. They must fail on 7189d6a. "p. a." may keep its rule, since "3 % p. a. Rendite" is rare.

### Nits

**N1. "Hs." reads "Halbsatz" anywhere.** In the humanities, "Hs." is "Handschrift" ("die Hs. B", "Hs. 12"). Either read it only after a sentence number ("S. 1 Hs. 2", "Satz 1 Hs. 2"), or say in the list's comment why "anywhere" is enough.

### Deferred

None new. #379 (the "2x m²" second run) was filed by the author.

## Next

Round 2 re-checks B1, S1, S2 and N1 on a head with main 8a8f863 merged in. If it is expected to approve, it also runs the 13 samples, mutants, nightly seeds, the token fuzz and `ci:full`.
