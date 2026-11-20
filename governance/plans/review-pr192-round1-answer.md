# PR #192, answer to review round 1

Head after fixes: 78caf27 (was f56fe95). Files changed: `layout/tagged.py`, `layout/maths.py`,
`tests/unit/test_layout_tagged.py`. No golden changed: the three new goldens and the seven PDF
goldens are byte-identical to round 1.

## Fixed

- **M1, fixed.** A note's mark is now its label only when the mark is a word of its own: it is
  followed by the end of the text, by white space, or by "." or ")" and then white space
  (`_opens_with`, the same shape that textprep's `_introduction` removes).
  - Test `test_a_note_takes_its_mark_as_label_only_as_a_word_of_its_own`: "1984 was a novel.",
    "1a is a variant." and "1.5 litres." get ""; "1. Text.", "1) Text." and "1 Text." get "1".
- **M2, fixed.** The formula number now comes from `maths.number_at_end`, the PDF rule's shape
  (white space before the "(", then a digit). It is read on the formula's last line.
  - Also N4: a new `maths.number_tagged` reads a TeX `\tag{3}` with the same number shape. It
    is a new function, so the PDF path does not change.
  - `_FORMULA_NUMBER` is removed.
  - Test `test_a_formula_number_has_the_shape_pdf_formulas_have`: `f(x) = \sin(x)`, `\psi(t)`
    and `g(n)` get ""; `a = b (2)`, `c = d (A.2)`, `e = f \tag{3}` and `x (16a)` get 2, A.2, 3
    and 16a.
- **M3, fixed.** A caption line that opens with a caption label of its own (`opens_caption`,
  the PDF caption rule) starts a new CAPTION. Lines of one figcaption without their own label
  still join into one caption.
  - Test `test_the_captions_of_two_neighbouring_figures_stay_apart` uses your example. "Figure 2"
    describes the first figure and "Figure 3" the second, and a two-paragraph caption stays one
    caption.
- **S1, fixed.** Maths inside a heading leaves it a heading: when an `h1`–`h6` is in the
  context, maths no longer decides the kind.
  - Test `test_a_heading_of_inline_maths_stays_a_heading`: `# $E=mc^2$` gives a HEADING and a
    section.
- **S2, fixed.**
  - (a) Test `test_the_first_outline_entry_for_a_page_sets_its_base_level`: two entries for one
    page at levels 1 and 2; the page's `h2` gets level 1.
  - (b) Test `test_the_first_of_two_entries_naming_one_block_starts_its_section`.
  - Dead checks:
    - `block.text.strip()` in `_from_entry` is **removed**. It was dead: an entry without a
      letter is dropped earlier.
    - `label in block.text` in `_labelled` is **kept**, because S3 makes it live. The title now
      leaves out noteref runs, so a mark printed inside a number ("1<a>*</a>.2 Intro") would give
      the label "1.2", which is not in the text, and `Block` would refuse it. The comment there
      says so.
- **S3, fixed here, not in #189.** A section title is now taken from the heading's runs without
  noteref runs (`_Sections._title`). The heading block keeps its printed text "Intro1". A heading
  that is nothing but a mark keeps its whole text, so no title is empty. The outline match in
  `_names` uses the same title.
  - Test `test_a_section_title_leaves_out_a_noteref_mark`.
- **S4.**
  - The layout part is **fixed**. A `br` line continues the element before it only when both
    are hidden or both are shown, so `<p>a<br/><span hidden>…</span></p>` gives a PARAGRAPH and a
    FURNITURE block. Test `test_a_hidden_line_after_a_br_is_furniture_of_its_own` covers both
    directions.
  - Hidden runs and inline page-break runs inside a shown line are **deferred to #193**
    (textprep: a marked remove for them). I left the milestone open for the coordinator to set.

## Nits

- **N1.** The per-paper hash is the sha256 of the snapshot text from just after
  `# name: ` up to, not including, the next `# name: ` (or the end of the file). That covers
  the entry's name line, its body and its `# ---` line. The PR body now says so, and the
  whole-file sha256 stays as the main proof.
- **N2.** The PR body now says that no property test compares positioned content before and
  after, and why none is needed: routing is a single early return, `build_document` is otherwise
  unchanged, and the existing `test_layout_never_fails_and_keeps_every_line` property plus the
  seven unchanged goldens cover that path.
- **N3, done.** Any `nav` (table of contents, landmarks, page list) is now FURNITURE `contents`.
  `_TOC` is removed. This refines D-411 ("a nav table of contents"), so please pass it to the
  coordinator for the KB. Test `test_any_nav_is_furniture`.
- **N4, done** (see M2).

## Checks on 78caf27

- ruff, ruff format, lint-imports (3 kept) and deptry are clean.
- Fast suite: 2996 passed, 1 skipped (Windows only); 60 snapshots unchanged.
- Nightly Hypothesis on `test_layout_tagged.py`, `test_layout.py` and
  `test_layout_tagged_corpus.py`: 86 passed.
- Mutation pass on `tagged.py`: 35 rules mutated in turn, including the two that survived your
  pass and every new rule, and all 35 were killed.
