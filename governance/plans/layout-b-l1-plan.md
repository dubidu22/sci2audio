# Layout batch B-L1: #125 (accent glyphs onto their letter) and #126 (tall pieces chain rows) (plan)

Thread layout-b-l1 (implementation, Opus 5.5 high), 20 Nov 2026. **Critical**: both issues
change golden files (CRIT-01), and #125 as recommended touches `src/sci2audio/extraction/`
(Q1). The plan waits for the coordinator's approval; no test or code is written before it.
The numbers below come from read-only probes on the corpus (scratch scripts, no product code).

## 1. What is wrong, measured

**#125.** The corpus has 4 spacing accents that extraction puts into a line of their own (a
`TextLine` holding only "´" or "ˇ"), all over a letter of a name in the references:

| Paper, line | Accent stands over | Stored after | Read today |
|---|---|---|---|
| Chi p6-l63 "´" | "c" of "Marasovic," (p6-l61) | "Swabha" (p6-l62) | "Ana Marasovic,´ Swabha" |
| Hardt p6-l12 "´" | "c" of "Marasovic" (p6-l11) | the end of p6-l11 | "Ana Marasovic, Noah A ´\nSmith" |
| Liu p6-l38 "ˇ" | "Z" of "Zelezn´y" (p6-l37) | the end of p6-l37 | accent apart, "J. Zelezn´y" |
| Liu p6-l48 "ˇ" | "S" of "Smejkal," (p6-l47) | the end of p6-l47 | "L. Smejkal, ˇ" |

They are split off because the accent's x jumps back from where it is stored (`_Line.accepts`).
The other 43 spacing accents in the corpus (all in Liu) sit inside a line, in reading order:
TeX accents before their letter ("Nov´ak", "Zelezn´y", "G¨obel") and maths hats ("ρˆ",
"Hˆ0", "ˆj", "eV˚A"). Those are the #65 text step's (`textprep/characters.py`), which joins
a TeX accent onto a vowel as a marked edit and leaves a maths hat alone (review M1 of #98).

**#126.** The tall piece is not an accent. Chi p6-l56 "able Privacy and Security ({SOUPS}
2016), pages" has the braces "{" "}" in CMSY10, whose boxes reach 7 pt below the baseline
(752.38 to 769.62; the text runs 750.87 to 762.88). The line's box is 18.75 pt tall and
overlaps the next printed line "321–340." (761.83 to 773.84) by 7.79 pt, more than
`row_overlap` × 12.0 pt, so `rows_of` takes "321–340." into the row and the paragraph reads
"… 2016), pages 321–340." on one line. Same for p6-l75 "({USENIX} Security 18), pages" and
"531–548.". So the issue's AC ("shares the row's baseline band with the row as a whole")
is right in kind but must measure the band from the letters, not from the boxes: a single
tall piece already chains with no third piece in between.

## 2. #125: design (recommended: in extraction)

Layout cannot do this: the accent is a `TextLine` of its own, and a block keeps every line's
text verbatim at its part's offset (`test_each_line_stands_in_its_block_as_found`, the never-fails
property, D-57). Composing "c" + "´" in the block text would change "Marasovic,"'s text
there and drop the accent line's text. Extraction sees each character's box and builds the
line text, so the fix is one rule there, and every layout invariant holds untouched.

**Rule (`extraction/pdf.py`, in `_lines`, after the lines of a page are built, before
`_text_line`):** a line made of one spacing accent (´ ` ˇ ˆ ˜ ¨ ¯ ˘ ˙ ¸ ˛ ˚) is put onto the
letter it stands over, in one of the `ACCENT_LINES` (8) lines stored before or after it on
the page (the cost bound: a page of 100,000 lone accents stays linear). The letter is the
alphabetic character whose extent along the line holds the accent's middle and whose line's
extent across overlaps the accent's (widened by 0.5 em, so an accent set above a capital
still counts). Its text becomes NFC(letter + combining accent); the accent line is left out.
No letter under it: the accent stays a line of its own, as today. The spacing-to-combining
table (12 entries) is extraction's own copy: extraction cannot import textprep (layers,
INV-02), and core holds data objects only.

- Ids stay as numbered: the accent's id (p6-l63) is simply missing, so no other line of the
  page is renumbered and the golden diff stays at the four names.
- An accent inside a line (stored in order, before or after its letter) is left as it is,
  for the #65 text step (Q2).
- Real result: "Ana Marasović, Swabha", "Ana Marasović, Noah A\nSmith", "J. Železn´y"
  (then #65 reads "Železný", a marked edit), "L. Šmejkal,".

## 3. #126: design (`layout/paragraphs.py`)

`rows_of` joins a piece to the open row only if (as today) it is in the same column, and
its **letter band** overlaps the **row's letter band** by `row_overlap` of the smaller one
(`same_row` on the two bands; no new setting). A band is the across extent of the base
letters: the runs within `same_size` of the largest letter size among the pieces, taking the
letter-weighted median top and median bottom of those runs; a piece without run boxes
(EPUB, text) or sizes uses its box, as today. The row's band is measured over all its pieces
so far, so a piece compares with the row as a whole, not with the piece before it (the AC).
The denominator path (`_denominator`, #322) and the inline-mark path (#163) stay as they are.

Prototype on the corpus (`rows_of` swapped in a scratch script): only Chi's two references
change ("pages\n321–340.", "pages\n531–548."); every other block of the 8 papers is
identical, and the result is the same for a size share of 0.01, 0.05 and 0.2. A first try
with a plain letter-weighted band (all sizes) broke Liu p2 ("J1st0[n(−1)E]", superscripts
outweigh base letters in a piece), which is why the band takes the largest letters only.

## 4. Tests first (each fails on main before its fix)

- **#125, extraction, made-up PDFs** (`tests/unit/test_extraction_pdf.py`, `pdf_maker`):
  (a) "Marasovic," then "´" drawn over its "c" and stored after the word, then "Swabha"
  → one line "Marasović," and no accent line; (b) the accent stored before its word, out of
  order (drawn over the "c" of a word stored after it) → composed; (c) an accent with no
  letter under it → stays its own line; (d) an accent inside a line in reading order
  ("Garc´ıa") → left as stored. Plus a test that the accent line's id leaves no other id
  renumbered.
- **#126, layout, made-up pages** (`tests/unit/test_layout_paragraphs.py`): (e) a line whose
  brace runs reach a line pitch down, then the next printed line → two rows, in order, the
  paragraph text "pages\n321–340."; (f) a tall accent piece between two printed lines
  (the issue's AC) → two rows; (g) a base line, a superscript piece, a subscript piece, a
  word → still one row (guards Liu's stacked scripts).
- **Corpus**: a truth-file check that Chi p6 reads "Marasović" and the two references end
  "pages" / start "321–340." on lines of their own, via the existing verbatim-sentence test
  (truth files unchanged).

## 5. Golden files expected to change (all explained line by line in the PR)

- `test_extraction_corpus.ambr`: Chi p6-l61, Hardt p6-l11, Liu p6-l37 and p6-l47 gain their
  accent; Chi p6-l63, Hardt p6-l12, Liu p6-l38 and p6-l48 are gone.
- `test_layout_corpus.ambr`: the same four references (text, part counts such as
  "[p6-l58..p6-l70 (13)]" → 12), and Chi's two references with their second line apart.
- `test_app_corpus.ambr`: Hardt's reference "Noah A ´ Smith" → "Noah A Smith", "Marasović".
- Not changed: truth files, English regression cases (the #65 case is made-up text and its
  rule is untouched), textprep goldens (grep finds none of these lines there).
Every other golden line must stay byte-identical (INV-07, checked on a local merge of main).

## 6. Properties that must still hold

Layout never fails on any `Content`; every item in exactly one block; each line's text at
its part's offset with "", " " or "\n" between (`test_layout_never_fails_and_keeps_every_line`);
extraction never fails on random bytes. New Hypothesis property (extraction): for random
words with a spacing accent drawn over one of their letters, stored before, inside or after
them, the extracted text equals the composed word (NFC) and no character is lost.

## 7. Size, files, labels

About 50 lines in `extraction/pdf.py`, 30 in `layout/paragraphs.py`, 150 to 200 lines of
tests, three goldens. One PR, `layout: accent glyphs join their letter and tall pieces stay
on their line (#125, #126)`, labels `lane:layout`, `lane:extraction`, `risk:high`, IN-01.

## 8. Questions (coordinator decides; recommendations given)

- **Q1, where #125 lives.** Recommended: in extraction, in this PR, with `lane:extraction`
  added (no extraction batch is active, so LANE-02 holds; precedent D-278). Alternative:
  hand #125 to the extraction/voices lane and ship #126 alone; that splits one Chi p6 golden
  diff over two PRs that must then wait for each other.
- **Q2, which accents.** Recommended: only accents extraction would split off into a line of
  their own; accents inside a line stay for the #65 text step. Composing those too would
  rewrite Liu's maths hats ("ρˆ", "Hˆ0") silently in extraction, which #65 deliberately
  leaves alone, and turn #65's marked edits into unmarked ones (D-57). This narrows the AC's
  "wherever it is stored" to "wherever it is stored apart from its letter's line"; unit test
  (b) covers an accent stored before its letter.
- **Q3, ids.** Recommended: keep the page's numbering, the accent's id goes missing.

## 9. Handoff (THR-07)

- Goal: B-L1, #125 and #126 in one critical PR.
- Done: issues measured on the corpus, both rules prototyped read-only, this plan.
- Next: on approval, tests (a) to (g) failing first, then the two rules, fast checks,
  `--snapshot-update`, PR, `ci:full`, ledger entry.
