# PR #382, answer to review round 1

The new head is **51abd44**. It includes merge ea7a71c of main 8a8f863 (#377) and the fix commit 51abd44. Review report: `plans/review-pr382-round1.md`.

## Main merge (ea7a71c)

- `tests/regression/english.toml` and `german.toml` conflicted only because both sides added cases at the end. Both sides' cases are kept. English has 176 cases: 169 at the merge base, 5 added by main and 2 by the PR. German has 131: 122 at the base, 3 added by main and 6 by the PR. No id appears twice.
- For `test_app_corpus.ambr` I took main's side and regenerated it. Its diff against main is the same 936/72 lines as before the merge: the 51 legal readings in maass, and Abbreviations going from 93 to 144.

## Fixes (51abd44)

**B1 (the word before an ordinal is the abbreviation's reading).**
- New: `abbreviations.read_before(text, start, language)`. It returns the start and the reading of an abbreviation that this step reads, when the abbreviation ends right before `start` with only white space between. It looks only at a window of 96 characters around `start`.
- `numbers_de._before_read` puts that reading in place of the printed form. Both `_ending` and `_after_preposition` now use it, so run 1 decides from the same word that run 2 sees.
- Results:
  - "i. V. m. 2. Alternative" reads "in Verbindung mit 2. Alternative": "mit" is a preposition, so the case is not known, as for "in 3. Auflage".
  - "i. S. v. 3. Abschnitt" reads "im Sinne von 3. Abschnitt".
  - "Urteil v. 3. Mai 2019" still reads "vom dritten Mai".
  - "i. S. d. 3. Abschnitts" stays as printed, because of S1, and reads the same on both runs.
- **First-run change (not in the corpus).** "gem." and "lt." before an ordinal used to read "gemäß dritter Abschnitt". That was stable, but the case was wrong. They now read "gemäß 3. Abschnitt", as the printed-out "gemäß 3. Abschnitt" reads on main. Other abbreviations I probed before an ordinal read as on main: "usw.", "Kap.", "z. B.", "bzw.", "ca.", "bzgl.", "inkl.", "zzgl.", "exkl.", "vgl." and "s.".
- Rows, both runs: the three rows of the report, plus "i. S. v. 3. Abschnitt", "i. V. m. 2. Alternative", "i.V.m. 2. Alternative", "v. 3. Mai 2019" and "gem. 3. Abschnitt". They are in `test_legal_forms_read_the_same_on_both_runs`.
- The second-run property now draws the legal forms as well: "i. S. d.", "i. S. v.", "i.V.m.", "a. F.", "n.F.", "gem.", "S. 1" and "Hs.", before "3. Abschnitt", "2019. Kapitel", "§ 3", "BDSG", "Art. 4", "Abs. 2", "Satz 2", "Hs. 2", "Die Norm" and "12.03.2015". It is green under the nightly profile.

**S1 ("i. S. d." only before a law).**
- New `before` kind `"law"`: only before "§" (so "§§" too), "Art." or "Abs.".
- "i. S. d." now has this kind and reads "im Sinne des". Anywhere else it stays as printed.
- Rows: "i. S. d. § 3 BDSG", "i.S.d. § 3", "i. S. d. §§ 3 und 4", "i. S. d. Art. 4 DSGVO" and "i. S. d. Abs. 2" read in full. "i. S. d. DSGVO", "i.S.d. DSGVO" and "i. S. d. Richtlinie" stay as printed. All on both runs.

**S2 ("a. F." and "n. F." inside a citation).**
- New list field `inside_citation`, set on "a. F." and "n. F.". Their full stop ends no sentence before any of these:
  - a word in capitals ("BDSG", "GG", "EGBGB");
  - "§";
  - a listed abbreviation of the label or number kind ("Abs.", "Art.", "Nr.", "S.", and so on), checked against the list;
  - "Satz", "Absatz", "Artikel", "Nummer" or "Paragraph" followed by a number.
- "a. F. Die Norm ist alt." and "a. F. Dr. Müller …" still end their sentence. "p. a." keeps its rule.
- Regression case `de-abbreviations-legal-forms-inside-a-citation` has `utterances`, with the report's four rows, "a. F. Die Norm ist alt." and the S1 pair. Unit rows add "n.F. § 3", "a. F. Nr. 2" and "a. F. Satz und Absatz." (no number, so the sentence ends).

**N1 ("Hs.").**
- I took the restriction rather than a comment. The new list field `after_sentence` means "Hs." reads "Halbsatz" only right after a sentence's number after "S." or "Satz". So "die Hs. B", "Hs. 12" and "S. 12 und Hs. 2" stay as printed.
- In the same place, "S." before a number and "Hs." reads "Satz" ("S. 1 Hs. 2" is "Satz 1 Halbsatz 2"). Before this, it read "Seite 1 Halbsatz 2". This extends `after_paragraph`, and the list's comment says so.

## Checks

- **Rows fail on 7189d6a.** I ran the PR's tests against 7189d6a's source:
  - 16 of the 30 rows in `test_legal_forms_read_the_same_on_both_runs` fail. They include all of B1's "i. S. d." and "i. S. v." rows, "gem.", all of S1's "stay as printed" rows, all of S2's rows inside a citation, and N1's rows.
  - The new regression case fails as well.
  - The 14 that pass are the ones whose reading did not change, such as "i. S. d. § 3" and "a. F. Die Norm".
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`): 5877 passed, 1 skipped. Ruff, format, lint-imports and deptry are clean. The PR's property file passes under the nightly profile.
- **13 corpus documents against main 8a8f863.** Twelve are identical. maass has exactly the same change set as round 1, the 51 legal readings in 23 blocks; I compared the change sets in code. The corpus has no "i. S. d.", "a. F.", "n. F." or "Hs.".
- **Mutants (round 1 code).** 13 mutants, each caught by a test:
  - `_LAW` without "Abs.", and the `law` kind replaced by `word`;
  - the `after_sentence` guard;
  - "S. n Hs." no longer reading "Satz";
  - the `inside_citation` guard, its capitals word, its lower-case look-ahead, its label word and number, and its number-kind forms;
  - the look-behind of the sentence number;
  - `read_before` always None;
  - `_before_read` taken out of `_ending`, and out of `_after_preposition`.
  - Together with round 0, that makes 43 of 43.
- **Linear time.** `read_before` looks at the text around `start` only; the first version sliced `text[:start]`. The new test `test_ordinals_after_abbreviations_take_linear_time` repeats a line of legal forms and ordinals 2000 times. To be exact: it also passes with the old slice at that size, so it guards the time overall, not that one slice.
- **Token fuzz.** 12,000 texts with seeds 4 to 6, over the earlier tokens plus "i. S. d.", "i.S.d.", "n. F.", "gem.", "BDSG", "Satz", "3.", "Abschnitts", "DSGVO", "S. 1" and "des". The whole chain ran twice, against main 8a8f863. No crashes. No text differs on a second run on the PR that does not also differ on main.

## Not changed

- "Ludwig v. Beethoven" keeps "v." as printed. "v." reads "vom" only before a date.
