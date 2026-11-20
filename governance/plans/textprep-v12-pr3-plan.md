# Textprep v1.2 second batch, PR 3: plan

Thread "Implement second textprep plan", 15 Nov 2026. Base: main a9e0e2d. Batch plan: `plans/textprep-v12-second-batch-plan.md` (D-646), PR 3 section.

Issues: #257, #258, #372, #375, and the test pins #383 and #384.

The PR is **critical**: it adds English and German regression cases and may change corpus golden files. It waits for the coordinator's approval before code. It will not be merged until the v1.1 release tag is cut.

Every row below was probed on a9e0e2d through the whole chain run twice. All of them read the same on both runs today; the problem is what they read.

## #257: a word left without its partner

| printed | a9e0e2d | wanted |
|---|---|---|
| `Between [1] and [3] it lies.` | `Between and reference 3 it lies.` | `Between references 1 and 3 it lies.` |
| `Zwischen [1] und [3] liegt es.` | `Zwischen und Quelle 3 liegt es.` | `Zwischen Quellen 1 und 3 liegt es.` |
| `We thank https://x.org and Smith (2019).` | `We thank and Smith.` | `We thank Smith.` |
| `Wir danken https://x.org und Müller (2019).` | `Wir danken und Müller.` | `Wir danken Müller.` |
| `In [12, p. 3] it is.` | as printed | `In reference 12, page 3 it is.` |
| `In [12, S. 3] steht es.` | `In [12, Seite 3] steht es.` | `In Quelle 12, Seite 3 steht es.` |

**Pairs (in `citations._numeric`).**
- Take a numeric or key bracket that would go as an aside, followed directly by "and" / "und" and a second bracket that the rule reads as needed.
- The two become one needed reading, over both brackets and the join word: `_spoken` of both lists, "references 1 and 3".
- The reason names both brackets.
- Only "and" / "und". "or" / "oder" keeps today's reading, and a case pins that.
- Two brackets that are both needed already ("in [1] and [3]") keep today's reading ("in reference 1 and reference 3"), so the corpus does not change there.

**A join word after a removed link (in `links`).**
- The join word goes with the link when all of these hold:
  - the link was removed without a lead word ("at", "unter" and the like keep their own rule);
  - the word before the link is a word, not punctuation and not a join word;
  - a word follows the join word.
- Join words: "and", "or", "und", "oder". This mirrors #256, where a join word with nothing after it goes.
- Kept: "We downloaded it from https://x.org and ran it." stays "We downloaded it and ran it.", because "from" went with the link.
- I measure this on the 13 corpus documents first. Any corpus change gets listed, or the rule narrows.

**A page in a numeric bracket.**
- The bracket's contents may end in ", p. N", ", pp. N–M", ", S. N" or ", Seite N", after one number or one key.
- Where the citation is needed, it reads "reference 12, page 3" / "Quelle 12, Seite 3", and "pages 3 to 5" for a range.
- As an aside it goes whole: "This holds [12, p. 3]." reads "This holds."
- Several sources with pages ("[12, p. 3; 14]") stay as printed, and a case pins it.

**Tests.** The six rows above as en/de regression cases, plus the "or", "both needed", "from … and" and multi-source rows. Both runs. The #330 token fuzz gets pairs, page brackets and links before join words.

## #258: ".." after an abbreviation before a removed link

| printed | a9e0e2d | wanted |
|---|---|---|
| `Smith et al. https://x.org. Then more.` | `Smith et al.. Then more.` | `Smith et al. Then more.` |
| `The answer is in Fig. https://x.org. Then.` | `… in Fig.. Then.` | `… in Fig. Then.` |
| `Wir zeigen das in Abb. https://x.org. Dann mehr.` | `… in Abb.. Dann mehr.` | `… in Abb. Dann mehr.` |
| `Daten finden sich u. a. unter https://x.org. Dann mehr.` | `… unter anderem. Dann mehr.` | unchanged |

**Fix (links step).**
- When the link ends the sentence and the text before it ends in an abbreviation's full stop that the abbreviations step leaves as printed, the removal takes the link's own full stop too. So there is no "..".
- To keep the sentence end for the listener, the step adds an empty PAUSE edit right after the abbreviation, with the reason "sentence end after an abbreviation". The cutter makes a pause an utterance boundary, so the two utterances that a9e0e2d gives stay two.
- Where the abbreviations step reads the abbreviation with its own full stop ("u. a." → "unter anderem"), the link's full stop stays, as today. The check is `abbreviations.reads_full_stop`.
- `abbreviations` imports `links`, so I either import it inside the function or move the check into a small helper both modules can import. I'll take the helper if it stays small, and say which in the PR.
- A second run sees "Smith et al. Then more." with no pause. Its spoken text is the same, which is what the second-run check compares; the cut may differ, as for any pause.

**Tests.** The four rows as regression cases in en and de, with `utterances`.

## #372: subject nests that lose names

| printed | a9e0e2d | wanted (as the flat form) |
|---|---|---|
| `((Smith, 2019); (Lee, 2018); Jones, 2020) is cited.` | `is cited.` | `Smith, Lee and Jones is cited.` |
| `((Smith, 2019); (Lee, 2018)) is cited.` | `is cited.` | `Smith and Lee is cited.` |
| `(Jones, 2020; (Smith, 2019)) is cited.` | `Jones is cited.` | `Jones and Smith is cited.` |
| `((Müller, 2019); (Lee, 2018); Schmidt, 2020) wird zitiert.` | `wird zitiert.` | `Müller, Lee und Schmidt wird zitiert.` |

**Fix (`citations`).**
- A subject bracket whose items are inner citation brackets or flat "Name, year" items, joined by ";", is read as its flat form.
- The names of every item are listed in order, through the path `_listed_inner_names` already uses for one inner bracket (#278).
- It stays inside the D-599 work cap. Any nest the cap stops keeps today's reading, and a case pins one nest deeper than the look cap.

**Tests.** The four rows in en and de, both runs. The nest and sibling second-run properties get these shapes. A timing check uses the #317 ratios.

## #375: a year shell around two inner citations

| printed | a9e0e2d | wanted |
|---|---|---|
| `Data ((Smith, 2019); (Lee, 2020) 2021) here.` | `Data (; 2021) here.` | `Data here.` |
| `((Smith, 2019); (Lee, 2020) 2021) is cited.` | `(; 2021) is cited.` | `Smith and Lee is cited.` |
| `Daten ((Müller, 2019); (Lee, 2020) 2021) hier.` | `Daten (; 2021) hier.` | `Daten hier.` |

**Fix.**
- `_shells` takes a year shell that holds a list of removals, joined by ";" or ",", and then a year. Today it takes one removal only.
- The whole shell goes with them.
- The subject row reads its names as #372's flat form does.

**Tests.** The three rows in en and de, both runs.

## #383 and #384: test pins (no reading changes)

Each shape from the issues becomes a unit or regression row, with `utterances` where a cut is the point. Each row must fail with its mutant applied, and I check that in the mutation run.

- **#383:**
  - `_KEY_ENTRY` `^`: "The tool of [Mn12] A. Bee works.", en and de.
  - `_ENTRY_AUTHOR` look-behind: six body items "[N] In 2011 we went to the USA." after "Results".
  - `unheaded_list` `headed` reset: "Notes", "[3] A stray note.", then [1]–[6].
- **#384:**
  - `_CITATION_GOES_ON` look-ahead: "Nach § 28 a. F. CDs gilt das." gives two utterances.
  - Number-kind forms: "Nach § 28 a. F. S. 2 gilt das." stays one utterance.
  - `_SENTENCE_BEFORE` look-behind: "Nach BGS. 1 Hs. 2 gilt das." keeps "Hs.".

## Checks before review

- The second-run check over all regression cases and the 13 corpus documents.
- Corpus scripts against a9e0e2d, byte-identical except the listed changes.
- Fast suite, ruff, format, lint-imports and deptry.
- Mutants of every new guard.
- The #330 token fuzz (en and de) against a9e0e2d: no differences that appear only on the PR.

Size: medium.

## Left out (say in the PR)

- `We thank Smith and https://x.org here.` reads `We thank Smith and here.`. This is a join word with a word after it but nothing between. It is a different shape, and I'll file it if it is not covered.
- "or" pairs and multi-source page brackets stay as they read today.

## Decision asked for

Approve the readings above. In particular:
- "Between [1] and [3]" reads "between references 1 and 3".
- "[12, p. 3]" reads "reference 12, page 3" where needed and goes whole as an aside.
- #258 keeps the sentence end with a pause rather than a second full stop.
