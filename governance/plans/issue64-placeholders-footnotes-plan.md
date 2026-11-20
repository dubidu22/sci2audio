# Plan: Issue #64, placeholders, footnotes and the reference list as marked edits

Thread "Add placeholder and footnote text rules", 12 Nov 2026. Lane textprep. **Critical**: new English regression cases and a changed corpus snapshot (golden files, D-69), and, in the recommended option of decision 1, one more text-step category (the text-step interface, D-108). Label `risk:high`. Binding inputs: Q2, Q3, Q15 (plan `v1-remaining-plan.md` §4), D-55, D-57, D-61, D-83, D-105, D-108 to D-113, D-128, issue #64. Built on PR #83 (a57d135). No core change, no new dependency.

## 0. What the corpus shows (prototype run on all 7 papers, scratch code only)

- Placeholders: 10 table blocks, 17 figure blocks (with 14 Figure and 5 Algorithm captions; one Nowak block holds Algorithms 1 and 2 and Figure 1), 45 numbered and 6 unnumbered formulas (the truth counts of D-81). Every table and figure block has at least one caption linked by `describes`; formulas carry their own number as `label`.
- Footnotes: 41 footnote blocks, 39 with a mark. The mark rule below finds the mark of **all 39** in the running text, on the same page, with **no false hit**. Nowak's abstract has 7 maths exponents (`O(N |N |3 + …)`) that look like marks 2, 3 and 4 on the same page, and the rule rejects all of them.
- Reference lists: 6 papers have a "References" section. Liu (PRL style) prints no "References" heading, so a title rule cannot find its list (see 6).

## 1. Decision for the coordinator: how one switch leaves all footnotes out

Q2 says one category switch leaves all footnotes out. D-110 says a switched-off category gives the same script as leaving its steps out. With one Footnotes category these two clash: the Footnotes steps remove the marks and add the "Footnote 1." intro, so switching the category off reads the marks and the notes as printed. It cannot leave the notes out. Leaving them out takes a removal edit that applies only when the user asks for it.

- **A (recommended): an 11th category, "Footnote texts" (`footnote-texts`), off by default.** Its one block step removes every footnote block. "Footnotes" (on) keeps the mark removal and the intro. Turning "Footnote texts" on removes the notes; by D-128 those removals claim the blocks, so the intros are set aside and show in the report with the winner. The marks stay removed either way. Interface change: `Category.on_by_default`, `DEFAULT_SWITCHED_OFF` (exported from `textprep`), and `run_steps(switched_off=DEFAULT_SWITCHED_OFF)` as the default, so #70's job settings start from it. Every left-out note stays a marked edit with a reason (D-57).
- B: a per-step switch (a `default_on` step attribute, `switched_off` takes step ids too). This is a larger change to the interface and the runner, and #77 would have to show switches below the category level.
- C: no textprep change. #70 gets a "read footnotes" job setting that drops footnote blocks when utterances are cut, like a deselected chapter (Q6). Footnote logic is then split over two layers, the left-out notes are not edits, and Q2's "category switch" becomes a job setting.

The other categories all switch on by default, so `DEFAULT_SWITCHED_OFF = {footnote-texts}`.

## 2. Modules (all in `src/sci2audio/textprep/`, importing only `core`)

**`wording.py`: every spoken word of #64 in one table (Q3).** `WORDING = {"en": Wording(...)}`: "{} is skipped." / "{} are skipped.", the list join (", " and " and "), the unnamed notices "A table is skipped.", "A figure is skipped.", "A formula is skipped.", the formula name "Formula {}", the intros "Footnote {}." and "Footnote.", and the label abbreviations read in full: Fig. → Figure, Figs. → Figures, Tab. → Table, Eq. → Equation, Alg. → Algorithm. English only (D-50). German adds a row later.

**`placeholders.py`: two block steps, one per category (D-108).**
- `formula-notices` (Formulas) and `table-figure-notices` (Tables and figures), both `("en",)`. One `replace` per placeholder block over its whole text (an empty block gets a replace on its empty span, which inserts the notice).
- Names: the labels of every caption whose `describes` points at the block, in document order, as printed (abbreviations as in the table). Otherwise a formula's own number gives "Formula 16a". With no name: "A table/figure/formula is skipped." Several names are joined: "Algorithm 1, Algorithm 2 and Figure 1 are skipped." (Nowak). The caption is never repeated and reads as printed in its own place.
- Reason: "formula 4 is not read; a short notice is read instead (D-55)".

**`references.py`: block step `reference-list` (Reference list), `("en",)`.**
- Matches a section at any level whose title, after an optional printed number ("7 References"), is one of the D-83 names for a reference list: References or Bibliography, compared case-insensitively. Names live in a tuple in the module, as layout's own list lives in its settings (textprep cannot import layout).
- One `remove` per block with text in that section's range, the heading included. Footnote blocks are skipped, because their marks stand in the body (Arsiwalla's note 19 sits inside the References range). Furniture is skipped too, because the furniture step already removes it.

**`footnotes.py`: two steps.**
- `footnote-texts` (Footnote texts, block, `("*",)`, off by default): one `remove` per footnote block with text. Present only in option A.
- `footnotes` (Footnotes, inline, `("en",)`):
  - **Intro:** a footnote block whose text (after leading white space) starts with its label gets a `replace` of the label: "Footnote 1." for a number or letter, "Footnote." for a symbol (∗ † ‡ §: the listener cannot match a symbol, and the marks are gone from the text). A space is added when no white space follows. A note without a mark gets "Footnote. " inserted. A note that already starts with the word "Footnote" gets nothing, which keeps the step idempotent.
  - **Marks:** a `remove` of a mark in a paragraph, heading, caption or list item when all of these hold:
    1. the run is tagged `sup` (EPUB and Markdown later) or set smaller than the block's main size (by layout's 8 %);
    2. its text is the label of a footnote on the same page;
    3. the word before it ends in at least two letters (optionally followed by digits, as in "Ahmad3∗") or in closing punctuation (`. , ; : ! ? ) ]` and quotes);
    4. the next character that is not white space is not a maths operator (`+ = − × · | < > ≤ ≥ ∈ / ^ _`).

    Each label is removed at most once per page, at its first match in reading order. If no mark matches, the note is still read with its intro.
  - Reasons: "footnote mark 1 is not read; the note is read at the foot of the column (Q2)" and "footnote 1 is introduced". A line whose text does not equal its slice of the block text is skipped, so a span never lands on wrong text.
  - Clean marks also depend on #36 (no space before a superscript). Without it a removed mark can leave "sets. ." at worst. Read-aloud white space is collapsed by `spoken_text` anyway.

**`registry.py`:** blocks `page-furniture`, `reference-list`, `formula-notices`, `table-figure-notices`, `footnote-texts`; inline `footnotes`. #66's inline steps go in before `footnotes`, as the docstring plans. This keeps my registry change to a few lines, because #65 edits the same file.

## 3. Test infrastructure (`sci2audio.testing`, lane textprep)

- `make_document` gains two keyword arguments. `tags` takes character ranges per block that become separate runs with `tags=("sup",)`. `sections` takes a section tree.
- The regression format gains two optional keys:
  - a block may give `runs = ["The effect", { sup = "1" }, " held."]` in place of `text`;
  - a case may give `sections = [{ title, level, start, end }]`.

  The loader's error messages name the case as before.
- `SAMPLE_DOCUMENTS`: the English paper gets its References section and a `sup` footnote mark, so the conformance suite exercises the new steps on every check, idempotence included.

## 4. Tests

- **Regression cases (golden, `tests/regression/english.toml`, issue 64), added first:**
  - table with its caption above it;
  - figure without a caption;
  - numbered and unnumbered formulas;
  - "Fig. 3" read as "Figure 3";
  - a figure with two captions;
  - footnote with a superscript mark: "Footnote 1.";
  - symbol note "Footnote.";
  - note without a mark;
  - maths exponent "N3" kept;
  - References and "7 Bibliography" sections removed with an appendix after them kept.

  None of the 14 audit cases changes (none belongs to #64).
- **Unit tests:** each rule above, each mark condition (accepted and refused), every switch state (Footnotes off, Footnote texts on and the intros set aside with their winner), and empty and white-space-only blocks.
- **Hypothesis:** on `documents()` with `sup` and size runs added, each new step passes `check_text_step(step, [doc], allow_ask=False)`. That covers no crash, valid spans, whole-block edits, determinism and idempotence. The existing built-in-steps idempotence property covers them together. Both run in the nightly profile. A density probe confirms that a fair share of examples propose edits (the #83 lesson).
- **Conformance:** automatic through `test_textprep_conformance` once the steps are registered.
- **Corpus (fast, on `apply_edits` output until #70):**
  - every placeholder block reads exactly its notice, so no formula or table text is left;
  - the notices' names equal the truth labels of tables, figures and algorithms and the truth formula numbers (or the layout counts where #21 named a gap);
  - every block of a References section, except notes, reads nothing;
  - every footnote reads from "Footnote";
  - every accepted mark is a footnote label on its page, and all 39 marks are removed;
  - a syrupy snapshot of each paper's removed marks with ten characters on each side, so a reviewer can check them against the PDFs.
- **Snapshot change:** the per-paper outcome summary of #83 gains the new categories. The furniture corpus test is narrowed to the furniture category's edits, because it asserted that only furniture changes. The PR explains both diffs.

## 5. Out of scope, with issues to file

- A reference list without a heading (Liu, PRL style): needs a list detector.
- Author-affiliation marks ("Chi1,2"), which are not footnotes.
- Reading a note next to its mark (v1.1, needs core, D-61 (1)).
- A German wording row (with #79).

## 6. Decisions for the KB (numbers from the coordinator)

1. Option A, B or C above. With A: the 11th category, `on_by_default`, `DEFAULT_SWITCHED_OFF`, and the runner default. This refines D-108 and D-110.
2. Mark detection: the four conditions, at most one mark per label per page.
3. Intro wording: "Footnote 1.", "Footnote." for symbols and notes without a mark; no second intro.
4. Notice names: every linked caption label, printed abbreviations read in full, the formula's own number, a list joined with "and"; one wording table keyed by language.
5. Reference list: References or Bibliography at any level after an optional number; heading and blocks removed, notes and furniture skipped; unheaded lists deferred.
6. All #64 steps are English only except `footnote-texts` (any language: it says nothing).
7. Regression format: `runs` with `sup` and `sections`.

## 7. Size

About 380 lines of source, 600 of tests and data, 1 PR.
