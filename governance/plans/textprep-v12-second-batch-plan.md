# Textprep v1.2 second batch: plan

Thread "Implement second textprep plan" (textprep lane), 15 Nov 2026. Base: main 342a8f5.
Follows the D-605 batch (PRs #353 #359 #361 #368 #371, all merged). Workflow D-626/D-627.
Every PR below adds English or German regression cases or changes a golden file, so every PR is
**critical** (`risk:high`, `ci:full` on the final round) and this plan waits for the
coordinator's approval before code or tests.

Every PR: regression cases first (failing), unit tests that fail with the fix reverted, the
second-run check over all regression cases and all 13 corpus documents green, the 13 corpus
scripts byte-identical except the listed changes, fast suite, ruff, lint-imports, deptry clean.
Closing keywords only in the PR body. One PR at a time, branched from the newest main.

## PR 1: references and alphanumeric keys (#92, #254)

One PR, because both decide what of a paper's sources is read, both change the same corpus
goldens (`test_app_corpus.ambr`, the citations/rules corpus snapshots) and the review checks
the same thing (no body text lost).

### #254 alphanumeric keys ("[MH17]", "[Fa14]", "[GKL+19]", "[Knu84]")

Probed on main 342a8f5: all maass shapes are read as printed today; numeric citations in the
same places read "Quelle 12" / "reference 12" and are stable on a second run, and so is
"in Quelle MH17" (whole chain twice).

- **Key shape:** a capital letter, then 1 to 3 letters, an optional "+", two digits, an optional
  lower-case letter (`[A-Z][A-Za-z]{1,3}\+?\d{2}[a-z]?`). At least two letters, so "[C60]",
  "[CO2]", "[H2O]", "[GPT4]" never match. A bracket of one or more keys joined by "," or ";"
  (no ranges, no mix with numbers) is a key citation.
- **Same rules as numeric citations** (the `_numeric` path): an aside goes ("haben gezeigt
  [Fa14], dass" → "haben gezeigt, dass"); never glued to a word, never after a maths sign or
  word, a label word, an interval; a bracket of lead words and keys goes whole ("(vgl. [MH17])").
- **Needed key (decision 1):** read with the reference word and the key as printed:
  "erstmalig in [MH17] vorgestellt" → "erstmalig in Quelle MH17 vorgestellt", "[Ho16, Ma16]"
  needed → "Quellen Ho16 und Ma16"; English "reference MH17". The key is what the list prints,
  so it stays as printed (D-57); how the voice says it is the voice's. Spelling it out is the
  alternative, not recommended.
- **False friends (written list):** "PM10", "PM25", "SO42", "Win10", "Win11", "COVID19"
  stay as printed even where the shape matches; the list lives in `CitationWords` beside the
  maths words so review can extend it.
- Tests: en/de regression cases (aside, needed after "in", subject "[MH17] zeigen", two keys,
  "vgl." bracket, false friend "[PM10]", "[CO2]"); `test_german_brackets_that_are_no_citation_stay`
  loses its "[Fa14]" row (it becomes a citation case, said in the PR); the corpus count test
  counts maass's 17 keys; linear-time and second-run properties take key brackets in their
  token sets; the #330 token fuzz (en and de) with keys added, PR-only differences none.

### #92 a reference list printed without a heading (Liu, PRL/revtex)

Liu's blocks 53 to 133 are entries "[1] …" to "[81] …", with page numbers (furniture) between,
two blocks that hold two entries each ("[16] … [17] …"), two short continuation blocks
("Europhysics Letters 135, 37001 (2021).", "(2020).") and the note "[59] The limit of ∆ → 0 …"
(revtex footinbib). The document has no sections.

- Same step (`reference-list`, category Reference list), second rule, used **only when the
  document has no section with a reference-list title** (so the 7 headed papers cannot change).
- The list is the last run of blocks of the document (furniture, footnotes and placeholders
  skipped) or the last run before a heading block (an appendix after it is read), where:
  the first entry is "[1]"; every "[N]" at a line start in the run counts up (a step of 1 to 3,
  so a block that layout merged or split does not break it); a block without "[N]" at its start
  is a continuation only if it is shorter than 120 characters and an entry follows it;
  at least 5 entries; at least half of the entries hold a year (1500 to 2099).
- Each block of the run is removed with reason "the reference list is not read (printed without
  a heading)".
- **Decision 2:** a note printed as an entry of the list (Liu's "[59]") goes with the list. Its
  mark in the body is a numeric citation that goes too, so the note would be read at the end
  with nothing pointing to it. The alternative (keep entries without a year) is not recommended.
- Tests: English regression case for an unheaded list (body, then six entries), plus "left
  alone" cases: a numbered "[1] [2] [3]" list in the body followed by a paragraph; a list that
  starts at "[3]"; entries without years. Corpus: Liu's blocks 53 to 133 read nothing, block 52
  ("Acknowledgments.") is still read, no other corpus document changes. The truth file's
  comment already says the list has no heading; no truth data changes.
- Size: medium (both parts).

## PR 2: German readings and units (#230, #231, #233, #250, #265, #358)

- **#230:** a listed unit symbol right after "per" / "pro" / "je" with no number reads as the
  singular unit word: "pro m²" → "pro Quadratmeter", "per m²" → "per square metre". Only listed
  symbols, only directly after the word; "pro A-Gruppe" and variables stay.
- **#231:** "f." reads "folgende" only after a page number that follows "S." / "Seite" /
  "Seiten" (or a page range), lower case only; "f. d.", a variable "f." at a sentence end and
  "F." stay.
- **#233:** "p. a." reads "pro Jahr" (exact case, can end a sentence); "1 %-Hürde" and
  "1 kg-Packung" read "Ein-Prozent-Hürde", "Ein-Kilogramm-Packung"; other numbers unchanged.
- **#250:** German "m s⁻²" and "m/s²" read "Meter pro Quadratsekunde"; likewise power 2 and 3
  of length and time units after "pro" ("Quadratmeter", "Kubikzentimeter"). English unchanged.
- **#265 (decision 3):** a four-digit number from 1100 to 2099 ending a German sentence is never
  an ordinal before a noun the ordinal rule knows ("Das war 2019. Kapitel 3 …" keeps "2019."
  and the sentence end), full word and abbreviation alike. The two-digit case ("umfasste 12.
  Kapitel 3") stays as today (ordinal), since D-530's sentence-end rules have no better
  signal; a case pins it.
- **#358:** a bare "less than" / "greater than" counts as the sign before a glued "2x" only
  after a single-letter variable or a closing bracket ("y < 2x" reads the same on both runs);
  "less than 2x slower" keeps "2 times".
- Probes: the #359 lesson (ask the other rule, probe the German twin and the controls).
  Size: medium.

## PR 3: citations and links that lose a word (#257, #258, #372, #375)

- **#257:** "Between [1] and [3]" reads "between references 1 and 3" (both brackets needed
  once one is); a join word left with nothing before it after a removed link goes ("We thank
  Smith"); "[12, p. 3]" / "[12, S. 3]" reads "reference 12, page 3" / "Quelle 12, Seite 3"
  where needed and goes as an aside.
- **#258:** no ".." in the script after an abbreviation's full stop when a link that ends the
  sentence goes; the abbreviation's own reading ("u. a." → "unter anderem.") keeps one stop.
  Fixed in the links step by keeping the sentence's stop only where the abbreviation step will
  not read the abbreviation's stop as its own; rows of the issue in en and de.
- **#372:** subject nests keep every name, as the flat form does
  ("((Smith, 2019); (Lee, 2018); Jones, 2020) is cited." → "Smith, Lee and Jones is cited."),
  inside the D-599 work cap.
- **#375 (audit S2, D-645):** a year shell around a list of inner citations that go, goes
  with them: `Data ((Smith, 2019); (Lee, 2020) 2021) here.` → `Data here.` (not `Data (; 2021)
  here.`); the subject row keeps its names. en and de.
- Probes: #330 token fuzz, nests one deeper than any look cap, timing-test ratios (#317).
  Size: medium.

## PR 4: German line-end hyphens (#240, #223)

- **#240:** a German compound split again at a line end ("Datenschutz-Grundverord-↵nung") joins
  the second split when the part after is lower case and the part before the line-end hyphen
  holds a hyphen already; "Ende-zu-↵Ende" style (capital or a short function word after) keeps
  it. The `[[miss]]` leaves `line-end-hyphens-de.toml`.
- **#223:** keep the hyphen of an adjective pair: the part before ends in an adjective ending
  (-isch, -lich, -ig, -al, -iv, -ell, -är) and the whole part after is an inflected adjective;
  measured first on the 38 hand-checked German line ends and the maass paper (D-227). If the
  rule breaks any hand-checked reading, it is dropped and #223 moves to Later (said in the PR).
- Size: small to medium.

## PR 5: what a listener should not hear, and alt text (#193, #93, #191)

- **#193:** a run tagged `hidden`, `aria-hidden`, `epub:pagebreak` or `role:doc-pagebreak`
  inside a block is removed with a reason (furniture step, category Furniture). PDF unchanged.
- **#93 (decision 4):** affiliation marks after author names and before affiliation lines on
  the first page's title block (superscript digits, "∗", "†" and the commas between them, above
  the first body heading or the abstract) are removed in the Footnotes category, reason
  "affiliation mark". Corpus snapshot of what goes on the chi, arsiwalla and nowak title pages.
- **#191:** an uncaptioned FIGURE whose pictures carry alt text gets the notice
  "A figure is skipped. It shows: <alt text>." / "Eine Abbildung wird übersprungen. Sie zeigt:
  <alt text>." (wording fixed in the PR); empty alt text and captioned figures keep today's
  notice. Regression case for the Markdown sample's two images.
- Size: medium.

## PR 6: placeholder labels on a second run (#362, #370, #374; finishes #249)

- `rebuilt_from_script` gets a placeholder rule: a placeholder whose notice reads the label
  (the label is in the block's text, the notice names it) keeps its label on the rebuild when
  the notice's label reading is the one the label step gives it. Then German formula notices
  read "Formel 3 Punkt 2 wird übersprungen." (#249's formula part) and a caption label reads
  through the whole chain's caption reading, so "Tab. 3x" reads as the caption does (#370).
- **#374 (audit S1, D-645):** English figure and table notices read label numbers as the caption
  does: "Figs. 1–3" → "Figures 1 to 3 is skipped.", fractions and powers likewise, on both runs
  (the English twin of #368's German caption labels).
- Touches `sci2audio.testing` (plugin conformance, #203): critical. Size: small to medium.

## Later or next batch (recommend)

- **#292** (code lines with a pause when Code blocks is off): stays v1.2, next textprep batch;
  it needs its own plan for reading symbols in code.
- **Later:** #97 (no case found in the corpus), #114 (spelling shows only in the script),
  #131 (needs a locale setting), #100 (needs a reference-list match), #287 (hostile input only;
  the D-599 cap bounds the worst case), as in the D-605 plan section 4.

## Decisions asked for

1. Approve the six-PR split and order (all critical), PR 1 = #92 + #254 as one PR; audit items
   #374 (PR 6) and #375 (PR 3) added per D-645.
2. #254: a needed key reads "Quelle MH17" / "reference MH17", key as printed; the false-friend list.
3. #92: a note printed inside an unheaded list goes with it (Liu "[59]").
4. #265: only four-digit years lose the ordinal; the two-digit case stays.
5. #93: affiliation marks go in the Footnotes category.
6. #292 to the next batch; #97 #114 #131 #100 #287 to Later.
