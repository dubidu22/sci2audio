# Plan: issue #65, Unicode clean-up and line-end hyphens (IN-04, TP-02, FX-04)

Thread "Add Unicode and hyphen text rules", 12 Nov 2026. Builds on the text-step interface
(PR #83, a57d135) and the utterance cutter (PR #86, 006c964).

**Critical: yes.** The PR changes golden files: `tests/regression/english.toml` (two
`expected` lines change, about ten cases are added) and the corpus summary snapshot of
`test_textprep_furniture.py` (new "characters" rows). It also adds one new hand-checked
truth file for line-end hyphens. **No change to core dataclasses, the layer contract or the
text-step interface.** Label `risk:high`. No new dependency (only `unicodedata` from the
standard library).

## 1. What the corpus holds (survey of the 7 papers, layout output of main)

- **497 hyphens at a line end** inside blocks. For 382 of them the same paper prints the word
  elsewhere, joined (343) or hyphenated (39), so the paper itself says which is right
  ("Pri-/vacy" appears 98 times as "privacy"; "pre-/training" 35 times hyphenated, 3 joined).
  For the other 115 the paper gives no evidence; by hand, about 104 of them are words split
  in two ("bet-/ter", "conclu-/sions") and 11 are real compounds ("fine-/grained",
  "language-/based", "self-/energy", "Wei-/Hung", "2023-/01-10").
- **No ligatures, no math letters, no soft hyphens, no no-break or thin spaces** in the
  corpus PDFs (PDFium already splits ligatures for these fonts). Those cases come from other
  PDFs, EPUB and Markdown, so they are tested with written cases, not the corpus.
- **TeX accents set apart:** 20 places where the accent is a separate spacing character
  before the letter: "Garc´ıa", "G¨obel", "˚Akerman", "Hovanˇc´ık", "Kl¨aui"; and a few where
  it drifted off the word ("Marasovic, ´ Swabha"). A voice stumbles on these. Not named in the
  issue, but it is the same kind of Unicode clean-up, so I propose to include it (U5).
- Math hats ("ˆρ", "Lˆ"), minus signs, primes, Greek letters and arrows are formula and
  symbol territory (#64, #68), not this issue.

## 2. Design

Two inline steps in category **Characters and hyphenation** (D-108), in a new module each:

| Step id | Module | Languages | What it proposes |
|---|---|---|---|
| `unicode-clean-up` | `textprep/characters.py` | any (`*`) | ligatures, math letters, soft hyphens, invisible characters, TeX accents |
| `line-end-hyphens` | `textprep/hyphens.py` | `en` | the TP-02 rule below |

Both run on every block kind except formula and table blocks for the hyphen step (a "-" at a
line end there is usually a minus or an empty cell; those blocks get notices from #64 anyway).
Every change is a `replace` or `remove` edit with a reason naming the characters; the block
text never changes (D-57). One edit per run of neighbouring characters of the same kind, so
"𝐀𝐱" is one edit, not two. Nothing proposes `ask`.

### 2.1 `unicode-clean-up` (IN-04, FX-04)

| Kind | Characters | Edit | Example reason |
|---|---|---|---|
| Ligatures | U+FB00 to U+FB06 (ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ) | replace by the letters (NFKC) | `ligature "ﬀ" read as "ff"` |
| Math letters (FX-04) | U+1D400 to U+1D7FF (𝑥 𝐀 𝛼 𝟏), and letterlike symbols whose NFKC form is one plain letter (ℓ ℎ ℝ ℕ ...) | replace by the plain letter or digit (NFKC; Greek stays Greek, 𝛼 → α) | `mathematical letters "𝐀𝐱" read as "Ax"` |
| Soft hyphens | U+00AD | inside a line: remove it; before a line break: remove the soft hyphen and the line break, which joins the word | `soft hyphen at a line end: word joined` |
| Invisible characters | U+200B, U+2060, U+FEFF, U+2061 to U+2064, U+200E, U+200F, U+202A to U+202E, U+2066 to U+2069, U+180E | remove | `invisible character U+200B (ZERO WIDTH SPACE) not read` |
| TeX accents | a spacing accent (´ ¨ ˚ ˇ ˜ ¯ ˘ ˙ ¸ ˛ ˝, and ˆ only inside a word) right before a Latin letter (ı and ȷ count as i and j), where letter plus accent compose to one character | replace both by the composed letter | `accent set apart: "´ı" read as "í"` |
| Stray accents | one of those accents standing alone between white space | remove | `accent mark without its letter not read` |

ZWJ and ZWNJ (U+200C, U+200D) stay: they carry meaning in emoji and in some scripts.
U+FFFD (a glyph the PDF could not map) stays: removing it would hide a gap the report should
show; that belongs to the extraction report.

### 2.2 `line-end-hyphens` (TP-02): the written rule

For a hyphen (- or U+2010) directly followed by a line break inside a block, let *before* be
the word ending in the hyphen and *after* the word starting the next line. The first rule
that applies decides:

1. **Not letters on both sides.** A digit or other character next to the hyphen
   ("2019-/2020", "COVID-/19", "J.-/P."): keep the hyphen. If nothing readable follows, no edit.
2. **Suspended hyphen.** *after* is "and", "or" or "nor" ("pre-/and post-test"): no edit; the
   line break is read as a space, as printed: "pre- and post-test".
3. **The document's own spelling.** Count, in the same document and case-insensitively, how
   often the whole word is printed joined ("development") and hyphenated ("pre-training")
   outside line ends. The form printed more often wins; a tie keeps the hyphen.
4. **Clearly a compound.** *before* is a single letter ("x-/axis", "t-/test"), ends in a
   capital ("PP-/RoBERTa", "OH-/conductance"), already holds a hyphen ("state-of-the-/art"),
   or *after* starts with a capital ("Wei-/Hung", "non-/English"): keep the hyphen.
5. **Short lists.** *before* is "self", or *after* is one of: based, related, specific,
   dependent, independent, driven, oriented, aware, grained, level, free, scale, wide, sized,
   term, order: keep the hyphen.
6. **Otherwise join.**

"Join" is one `remove` edit over the hyphen and the line break ("develop-\nment" reads
"development"). "Keep" is one `remove` edit over the line break only ("state-of-the-\nart"
reads "state-of-the-art", not "state-of-the- art"). This is the "hyphen at a line end is an
edit" of Q4/D-98; ordinary line breaks stay with the cutter.

Measured on the corpus with a prototype: of the 495 line-end hyphens outside formula and
table blocks, rules 1 to 6 decide 487 as a careful reader would (98.4%). The 8 misses go into
the truth file as known misses: 5 real compounds joined ("domainadaptive", "domainadapted",
"contentaddressable", "sidejump", "passedthrough"), "self-hood" kept though "selfhood" is one
word, and the model names "SciB-ERT" and "Span-BERT" kept by the capital-letter rule. Each
miss is still read understandably.

## 3. Decisions for the coordinator

- **U1: no word list.** The old app used wordfreq (data licence CC BY-SA 4.0, about 20 MB of
  dependencies). A dictionary would fix most of the 8 misses, but it adds a licence-gate
  question and size for a gain of about 1.6% on the corpus. Proposal: no dictionary in v1.0;
  the document's own spelling does most of the work. Alternative not chosen: vendoring a
  SCOWL-derived word list (permissive but non-SPDX licence, ~500 KB).
- **U2: characters and hyphenation run last among the inline steps** (the registry docstring
  today plans them before numbers, units and abbreviations). Steps all see the original
  text and the earlier step wins an overlap, so a one-character fix placed early would block
  a later rule covering the same text: a ligature fix in "ﬁg." would block the abbreviation
  step's "figure", a math-letter fix in "𝑝 < .05" would block the statistics step, a thin
  space in "3.5 mg" would block the units step. Placed last, these fixes only apply where no
  other rule rewrote the text, and every other rule writes clean text. The registry change is
  the two steps appended at the end of `BUILT_IN_STEPS` and one docstring line.
- **U3: no edits for white space.** No-break, thin and other Unicode spaces are already read
  as one plain space by `spoken_text` and the cutter (D-98: edits that change nothing a
  listener hears only fill the report). The acceptance criterion "odd spaces become plain
  text" is met by that rule and pinned by a regression case. Only invisible characters that
  are not white space (zero-width space and similar) get `remove` edits.
- **U4: the hyphen step is English only in v1.0**; German needs its own conjunction list
  ("und", "oder", "bis") and capital-letter rule (German nouns). The Unicode step runs for
  every language. A follow-up issue for German hyphens, milestone v1.1.
- **U5: TeX accents** are included as described in 2.1.

Each decision gets a row in the KB decision log (a KB PR from this thread, reviewed in its
own thread, D-78).

## 4. Tests (test-first)

1. **Regression cases first** (`tests/regression/english.toml`): change `expected` of
   `line-end-hyphens` ("development", "difficulties", "processing") and `ligature`
   ("Androff"); add cases with `audit = 0, issue = 65`: ligatures, soft hyphens (inside and at
   a line end), zero-width characters, odd spaces (no edit, reads plain), math letters,
   TeX accents, suspended hyphen, compound kept ("state-of-the-art"), capital after the
   hyphen, the document's own spelling ("pre-training" printed hyphenated elsewhere), digits.
2. **Unit tests** per kind and per rule, including the exact edit spans, kinds and reasons.
3. **Conformance**: both steps pass `check_text_step(step, allow_ask=False)` automatically
   through `test_textprep_conformance.py`.
4. **Hypothesis properties** (ci and nightly profiles), with text strategies weighted
   toward the characters in question so most examples exercise the rule (I count it with a
   probe): no crash on any text; edits valid and idempotent (`check_text_step` on generated
   documents); after the Unicode step no ligature, math letter, soft hyphen or listed invisible
   character is left in the spoken text; the hyphen step only ever removes "-", "‐" and line
   breaks, and keeps every letter in order.
5. **Corpus**: a new truth file `tests/regression/line-end-hyphens-en.toml` listing all 497
   corpus line-end hyphens (paper, word before, word after, join or keep, labelled from the
   paper's own spelling where it has one and by hand otherwise; known misses marked with a
   reason). The test asserts every decision and that the known misses still miss, so a better
   rule shows up as a diff. Also: every `where = "hyphenation"` truth sentence of the 7 papers
   appears word for word in the spoken text after the two steps.
6. `test_textprep_furniture.py`: its "everything but furniture reads as printed" check runs
   the furniture step alone (it now fails as soon as any rule step exists); the per-category
   corpus snapshot keeps running all built-in steps, so the PR shows the new "characters"
   counts per paper as a snapshot diff. Issue #64 needs the same change; I tell its thread.

## 5. Size and order of work

About 300 lines of code in two modules, 500 lines of tests, the truth file. One PR, branch
`textprep/issue65-unicode-hyphens`, `Closes #65`. Then a KB PR with U1 to U5. Follow-ups as
issues: German line-end hyphens (U4); hyphens split across two blocks (an edit cannot span
blocks; layout keeps a split paragraph in one block in all corpus cases).
