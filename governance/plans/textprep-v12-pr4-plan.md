# Textprep v1.2 second batch, PR 4: plan

Thread "Build textprep PR 4 for v1.2", 16 Nov 2026. Base: main ffdd2f9. Batch plan: `plans/textprep-v12-second-batch-plan.md` (D-646), PR 4 section.

Issues: #240 and #223. Both are German only, in `sci2audio.textprep.hyphens` (step `line-end-hyphens`, TP-02).

The PR is **critical**: it changes a hand-checked truth file (`line-end-hyphens-de.toml`), one German regression case and the maass corpus script. It waits for the coordinator's approval before code or tests.

Every row below was probed on ffdd2f9 and on a scratch prototype of this plan, through the whole chain run twice. Every row reads the same on both runs, on main and on the prototype.

## #240: a hyphenated word split again at a line end

Today rule 4 keeps a line-end hyphen whenever the word before it already holds a hyphen. That is right for "state-of-the-/art" and wrong for "Datenschutz-Grundverord-/nung", where TeX split the second part again.

**Rule (German only).** When the word before holds a hyphen and the word after starts with a lower-case letter, the "hyphen already in the word" signal counts only if the last part before the line-end hyphen is a chain word. Otherwise the step goes on to the rest of the rule, as for a word without a hyphen. The rest is: one letter, a capital at the end, a capital after (keep), then the #223 rule, then join.

- Chain words, lower case only, compared as printed: `zu an in um auf bei für vor von aus mit nach über und oder bis im am zum zur` and the English words used in German compounds `to of the and on at by for or it`.
- The lower-case test matters. A capital fragment such as "Online-An-/gebote" joins, because a noun part after a hyphen is written with a capital, while "Ende-zu-" and "Peer-to-" are lower case.
- The capital-after rule is unchanged. "Ende-zu-/Ende" and "Ad-hoc-/Analyse" keep their hyphen because of it.
- English is unchanged. The English corpus has no line-end hyphen after a hyphenated word, and "state-of-the-/art" is pinned there. "the non-differen-/tiable loss" still reads "non-differen-tiable" in English. I file that as a new issue (English split-again), not part of this PR.

| printed (de) | ffdd2f9 | PR |
|---|---|---|
| `Die Datenschutz-Grundverord-↵nung gilt.` | `Datenschutz-Grundverord-nung` | `Datenschutz-Grundverordnung` |
| `Die Datenschutz-Ver-↵ordnung gilt.` | `Datenschutz-Ver-ordnung` | `Datenschutz-Verordnung` |
| `Die deutsch-franzö-↵sischen Beziehungen.` | `deutsch-franzö-sischen` | `deutsch-französischen` |
| `Die PDF-Daten-↵bank läuft.` | `PDF-Daten-bank` | `PDF-Datenbank` |
| `Eine Ende-zu-↵Ende-Verschlüsselung fehlt.` | kept | kept (capital after) |
| `Ein Peer-to-↵peer-Netz läuft.` | kept | kept (chain word "to") |
| `Ein State-of-the-↵art-Verfahren läuft.` | kept | kept (chain word "the") |
| `Eine Ad-hoc-↵Analyse folgte.` | kept | kept (capital after) |
| `Ein E-Mail-↵basiertes Verfahren läuft.` | `E-Mail-basiertes` | `E-Mailbasiertes` (accepted, see below) |
| `Eine Ad-hoc-↵analyse folgte.` | `Ad-hoc-analyse` | `Ad-hocanalyse` (accepted, see below) |

**Accepted cost.** A real hyphen before a lower-case word part, after a hyphenated word, now joins. Examples are "E-Mail-/basiertes" and the misspelt "Ad-hoc-/analyse". The cost is lopsided. A wrong join still reads one whole word ("E-Mailbasiertes" sounds like "E-Mail-basiertes"). A wrong keep breaks a word in two ("Grundverord" and "nung"). That is why the default is to join.

**Changed golden.** The #96 regression case `de-hyphen-inside-word-kept` prints "Eine Ad-hoc-↵analyse folgte." with a lower-case "analyse" and expects the hyphen kept. German writes "Ad-hoc-Analyse". I change the case's text to `Eine Ad-hoc-\nAnalyse und ein Peer-to-\npeer-Netz folgten.` with expected `Eine Ad-hoc-Analyse und ein Peer-to-peer-Netz folgten.`, and its goal to "A hyphen already inside the first part keeps the one at the line end before a capital or after a chain word (#96, #240)." The old shape gets its own row in the unit tests with the new reading.

**Truth file.** The one `[[miss]]` in `line-end-hyphens-de.toml` goes. The test's limit for German drops from 1 to 0 misses, and the test reads a file with no `[[miss]]` table. All 38 German and 495 English hand-checked readings stay as checked. The prototype passes `test_every_corpus_line_end_hyphen_reads_as_checked_by_hand` for every paper.

## #223: hyphenated adjective pairs at a line end

**Rule (German only, after rules 1 to 5 and the #240 change, before the final join).** Keep the hyphen when both of these hold:
- **The part before** (its last part, if it holds a hyphen) starts with a lower-case letter. It ends in one of `sch lich ig al iv iell uell rell nell mell är`, with at least 3 letters before that ending.
- **The whole word after** starts with a lower-case letter. It ends in one of those endings followed by one of `e en er es em`, with at least 4 letters before the ending and its inflection.

The reason reads `hyphen at a line end kept, read as one word: "deutsch-französischen" (an adjective pair)`.

**Changes from the issue's idea, and why.**
- "sch" replaces "isch". "isch" misses the issue's own first row, "deutsch", and "sch" also covers "isch".
- "ell" is narrowed to `iell uell rell nell mell` ("materiell", "aktuell", "kulturell", "traditionell", "formell"). A plain "ell" kept "fertig-/stellen" and "gesell-/schaftlichen".
- The stem minimums (3 before, 4 after) remove "al-/ternative", "mittelal-/terlichen" and "einzig-/artigen".
- The lower-case test leaves noun fragments alone ("Wirtschaftlich-/keit", "Persönlich-/keitsmerkmale").

Rule 3 still comes first. A document that prints "deutschfranzösischen" closed elsewhere joins the line-end form too, as it does today.

**Measured (D-227).**
- **False keeps.** I took every word of a German frequency list and split it at every point a German hyphenation dictionary allows (pyphen 0.17, de_DE). The list and the dictionary were used only for measuring and do not enter the repo. Then I counted the splits the rule keeps. Each of those is a word that a line end split and the rule would read with a hyphen.
  - 50,000 most frequent words: 82,153 split points, **0 kept**.
  - Every word printed 3 or more times (355,551 words): 701,565 split points, **87 kept**. That is 542 of 80.8 million word tokens, or 0.0007%. Most of the 87 are compound joints, where the hyphen reads the same: "englisch-/sprachigen", "dreißig-/jährigen", "national-/sozialistischen", "spiral-/förmigen". Some are nouns, which a capital keeps out in real text: "Persönlich-/keitsmerkmale", "Moral-/prediger". Two in the top 40 really break a word: "gemisch-/trassige" and "mannig-/faltige".
- **Pairs found.** I wrote 35 adjective pairs typical of scientific German. The rule keeps 31 of them, for example "deutsch-französischen", "sozial-emotionale", "technisch-organisatorischen", "physikalisch-chemischen", "materiell-rechtlichen", "kognitiv-emotionalen" and "räumlich-zeitlichen". It misses 4: "rot-grüne", "schwarz-weiße", "süß-saure" and "digital-analoge". None of these has an adjective ending, and catching them would need a word list (D-149). They stay joined, the PR says so, and I file one issue for them.
- **Corpus.** All 38 hand-checked German readings stay as they are. The maass paper has no adjective pair at a line end.

| printed (de) | ffdd2f9 | PR |
|---|---|---|
| `Die deutsch-↵französischen Beziehungen sind gut.` | `deutschfranzösischen` | `deutsch-französischen` |
| `Die sozial-↵emotionale Entwicklung.` | `sozialemotionale` | `sozial-emotionale` |
| `Die technisch-↵organisatorischen Maßnahmen.` | joined | kept |
| `Die physikalisch-↵chemischen Eigenschaften.` | joined | kept |
| `Die materiell-↵rechtlichen Fragen.` | joined | kept |
| `Die deutsch-↵französischen und deutsch-↵polnischen Beziehungen.` | both joined | both kept |
| `Die rot-↵grüne Koalition.` | `rotgrüne` | `rotgrüne` (left out) |
| `Die Wirtschaftlich-↵keit sinkt.` | joined | joined |
| `Das ist natür-↵lich gut.` | joined | joined |
| `Die tech-↵nischen Maßnahmen.` | joined | joined |
| `Die gesell-↵schaftlichen Fragen.` | joined | joined |
| `Die mittelal-↵terlichen Städte.` | joined | joined |
| `Die einzig-↵artigen Funde.` | joined | joined |
| `… deutsch-↵französischen … und die deutschfranzösischen Verträge.` | joined | joined (rule 3) |
| `The deutsch-↵französischen case.` (en) | joined | joined (English unchanged) |

## Corpus change (13 documents, ffdd2f9 against the prototype)

Every file is byte-identical except one, the maass paper (`arxiv2017-maass-privacyscore`):
- **script.txt, line 326:** "Datenschutz-Grundverord-nung" becomes "Datenschutz-Grundverordnung".
- **report.json and report.md:** that one edit becomes a join, with original "-↵" instead of "↵", start 360 instead of 361, and the reason `word split at a line end joined: "Datenschutz-Grundverordnung"`.

The two maass snapshots in `test_app_corpus.ambr` change by exactly that, through `--snapshot-update`.

## Code

- `HyphenWords` gets three fields, empty for English:
  - `chain_words: frozenset[str]`, the list above;
  - `split_again: bool`, which turns the #240 rule on;
  - `adjective_pairs: bool`, which turns the #223 rule on.
- New module constants `ADJECTIVE_ENDINGS` and `INFLECTIONS`, and a function `_adjective_pair(before, after)`.
- The rule list in the module docstring gets the two additions.
- No change to step ids, categories, switches, the text-step interface or `core`.

## Tests (written first, failing before the rule)

- **`german.toml`:**
  - `de-hyphen-split-again-joined` (#240): "Die Datenschutz-Grundverord-↵nung und die PDF-Daten-↵bank."
  - `de-hyphen-chain-kept` (#240): "Ende-zu-↵Ende-Verschlüsselung", "Peer-to-↵peer-Netz", "State-of-the-↵art-Verfahren".
  - `de-hyphen-adjective-pair-kept` (#223): "deutsch-↵französischen", "technisch-↵organisatorischen", "sozial-↵emotionale".
  - `de-hyphen-adjective-ending-split-joined` (#223): "Wirtschaftlich-↵keit", "natür-↵lich", "tech-↵nischen", "gesell-↵schaftlichen", "einzig-↵artigen".
  - `de-hyphen-adjective-pair-printed-closed` (#223, rule 3 first).
  - `de-hyphen-adjective-pair-not-covered` (#223, "rot-↵grüne" pinned as joined).
  - The changed `de-hyphen-inside-word-kept`.
  - Every case is checked on both runs.
- **Unit tests** (`test_textprep_hyphens.py`):
  - one test per row of both tables;
  - each chain word kept, and the same word with a capital joined;
  - each ending, and each ending with one letter too few;
  - English left alone for both rules;
  - the reason texts.
- **Hypothesis:**
  - German property: a hyphenated word with a lower-case non-chain last part, a line-end hyphen and a lower-case rest is joined.
  - German property: a pair built from generated stems and the endings is kept.
  - The existing properties (no crash, spans valid, every letter kept, idempotent) also run with `DE`.
- **Corpus:** the truth-file test without the miss, and the maass snapshots.

## Checks before review

- The second-run check over all regression cases and the 13 corpus documents.
- Corpus scripts against ffdd2f9: byte-identical except the maass change above.
- Fast suite, ruff, format, lint-imports and deptry.
- Mutants of every new guard, with `mut3.py` from a clean worktree of the PR head and a passing baseline run first. The PR body names the command, ROOT, the test glob and the baseline result (D-676):
  - each chain word dropped;
  - the lower-case tests removed;
  - each ending dropped;
  - stems 3→2 and 4→3;
  - `split_again` and `adjective_pairs` forced on for English.
- A token fuzz in German: hyphenated words, line-end hyphens, adjective endings and chain words, the whole chain twice, against ffdd2f9. Only differences that appear on the PR alone are reported.

Size: small.

## Left out (said in the PR, issues filed)

- English split-again ("non-differen-/tiable"): a new issue.
- Adjective pairs without an adjective ending ("rot-/grüne", "schwarz-/weiße", "süß-/saure", "digital-/analoge"): a new issue, probably for Later, since a fix needs a word list.
- A pair at a sentence start ("Deutsch-/französische …") joins, because of the lower-case test. This is named in the PR, with no issue.

## Decision asked for

Approve the readings above. In particular:
- #240 joins by default after a hyphenated word before a lower-case rest. The accepted cost is "E-Mail-/basiertes" reading "E-Mailbasiertes".
- The #96 case `de-hyphen-inside-word-kept` changes its text to a capital "Analyse".
- #223 uses the narrowed endings and stems above. The pairs without an adjective ending are left out.
