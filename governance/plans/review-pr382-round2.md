# Review PR #382, round 2 (textprep batch 2 PR 2: German readings and units #230 #231 #233 #250 #265 #358, legal forms #264)

Head reviewed: 51abd44. It is fix 51abd44 on merge ea7a71c of main 8a8f863. Answer: plans/answer-pr382-round1.md. Critical, final round.

**Verdict: approvable at 51abd44.** It closes #230 #231 #233 #250 #265 #358 #264. Three unpinned guards are filed as #384 (test-only). Nothing is merged.

## Main merge

`mergeable_state` is clean. The maass script's change set against main 8a8f863 is identical to round 1's against c841f3d: the same 91 diff pieces, which are the 51 legal readings. The other 12 corpus documents are byte-identical to main.

## Round 1 items

All rows below were probed through the whole chain twice, against main 8a8f863.

- **B1, fixed.** `_ending` and `_after_preposition` now take the reading of an abbreviation that ends right before the number. Every row of round 1 now reads the same on both runs:
  - "i. S. d. 3. Abschnitts", "i.S.d. 3. Abschnitts" and "i. S. d. 2019. Kapitel 3" stay as printed (because of S1).
  - "i. S. v. 3. Abschnitt" reads "im Sinne von 3. Abschnitt".
  - "i. V. m. 2. Alternative" reads "in Verbindung mit 2. Alternative".
  - "Urteil v. 3. Mai 2019" reads "vom dritten Mai 2019".
- **The side effect, accepted.** "gem. 3. Abschnitt" and "lt. 3. Abschnitt" now read "gemäß 3. Abschnitt" and "laut 3. Abschnitt". Main read "gemäß dritter Abschnitt", which is stable but in the wrong case ("gemäß" takes the dative). The new reading is what the printed-out "gemäß 3. Abschnitt" reads on main, it leaves the number as printed rather than speaking a wrong ending, and no corpus document has the shape. The same holds for "i. V. m. 1. Satz", which was "erster Satz" on main.
  - Unchanged from main: "z. B. 3. Mal", "usw. 3. Kapitel", "Kap. 3. Abschnitt", "inkl. 2. Auflage", "zzgl. 3. Rate" and "bzgl. 3. Abschnitts".
- **S1, fixed.** The new `before` kind "law" matches "§", "Art." and "Abs.". "§§" is covered, because the pattern matches its first "§": "i. S. d. §§ 3 und 4 BDSG" reads "im Sinne des §§ 3 und 4 BDSG".
  - These read in full: "i. S. d. § 3 BDSG", "i. S. d. Art. 4 DSGVO" and "i. S. d. Abs. 2".
  - These stay as printed: "i. S. d. DSGVO", "i.S.d. DSGVO", "i. S. d. Richtlinie" and "i. S. d. Nr. 2".
- **S2, fixed.** These are now one utterance each: "§ 28 a. F. BDSG", "Art. 7 a. F. EGBGB", "BDSG a. F. Abs. 2", "Art. 7 n. F. Satz 2", "a. F. EU-Recht", "a. F. S. 2" and "a. F. AB Test".
  - These still end their sentence: "a. F. Die Norm", "a. F. Dr. Müller", "a. F. Im Jahr 2020" and "a. F. Satz und Absatz." (no number).
- **N1, fixed.** "Hs." reads "Halbsatz" only after a sentence number. "S. 1 Hs. 2" and "Satz 1 Hs. 2" read "Satz 1 Halbsatz 2"; "die Hs. B", "in Hs. 12" and "S. 12 und Hs. 2" stay. "S. 12 Hs. 2" now reads "Satz 12 Halbsatz 2", which is right in a law citation and rare elsewhere. Accepted.

## Checks on 51abd44

- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 5877 passed, 1 skipped.
- **Corpus:** see "Main merge".
- **Token fuzz:** 9,000 texts (seeds 7–9, de and en) from 72 tokens, which add "i. S. d.", "n.F.", "gem.", "lt.", "Abschnitts", "DSGVO", "S. 1", "Hs. 2", "des", "§§", "Nr.", "EU-Recht" and "Dr. Müller" to round 1's set. The whole chain ran twice against main 8a8f863. There were no crashes, and no text differs on a second run on the PR that does not also differ on main.
- **Mutants:** 19 of the round 2 guards. 13 are caught: `_LAW` without "Abs." and without "Art.", "i. S. d." with `before = "anything"`, `_ending` and `_after_preposition` on the printed text, `after_sentence` off, the "S. n Hs." reading off, `inside_citation` off, the capitals word, the label word, its number, the listed-form check, and "Satz" in `_SENTENCE_BEFORE`. One of mine did not apply; the author's "`read_before` always None" covers it. Five survive:
  - Three change a reading in rare shapes and are filed as **#384**:
    - the capitals look-ahead: "a. F. CDs" becomes one utterance;
    - the number-kind forms in `_citation_goes_on`: "a. F. S. 2 gilt" is cut;
    - the look-behind of `_SENTENCE_BEFORE`: "BGS. 1 Hs. 2" reads "Halbsatz".
  - Two are defensive and change nothing in about 30 shapes: `read_before` allowing text between, and "§" in `_CITATION_GOES_ON`, which never starts a sentence because it is no capital.
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`; units and German readings, abbreviations, utterances, conformance, runner): seeds 2024 and 123456, 672 passed each.
- **CI with `ci:full`** on 51abd44: tests on ubuntu, macOS and Windows, browser, lint and layers, licences, security and CodeQL are all green.
- Commit messages carry no closing keywords. The PR body closes all seven issues.

## Fix list

None. Deferred: #384 (test pins, v1.2, lane:textprep).

## Merged

Squash-merged pinned to 51abd44 as **a9e0e2d**. All seven issues are closed. The v1.1 milestone shows 0 open and 46 closed issues.
