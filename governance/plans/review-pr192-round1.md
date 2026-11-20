# Review PR #192, round 1 (layout for documents without positions, #75)

Reviewed head f56fe95 (base main 5aad4ae), 13 Nov 2026. Critical (risk:high, new goldens).
Plan: plans/issue75-tagged-layout-plan.md; decisions D-405 to D-418.

## Verified

- **PDF path untouched.** `build.py` adds only the early `if not positioned(content): return build_tagged(...)`.
  `headings.py` and `captions.py` are pure renames (`printed_number`, `outline_entries`, `title_key`,
  `section_tree`, `caption_label`); no other line changed under `layout/`.
- **Seven PDF goldens byte-identical.** I deleted both layout `.ambr` files in a clean worktree and
  regenerated them with `--snapshot-update` from the PR's code: `test_layout_corpus.ambr` came out
  byte-identical to main's (sha256 `cc276ec4…8b94da`, as the PR says).
- **Three new goldens reproduce.** The regenerated `test_layout_tagged_corpus.ambr` is byte-identical
  to the committed one (sha256 `75336e9a…4f4341`).
- **EPUB sections against the book's own table of contents.** toc.xhtml has 18 flat entries
  (Titlepage, Imprint, I to XII, Epilogue, Endnotes, Colophon, Uncopyright), one per spine document,
  and the golden has 18 level-1 sections in the same order. The titlepage section is titled by its `h1`
  "The Time Machine"; every other section by its `h2`.
- **Markdown sections against the truth file.** Exactly the truth's 5 headings and levels (1, 2, 3, 2, 2).
- Fast suite 2987 passed, 1 skipped (Windows only), 60 snapshots. ruff, ruff format, lint-imports
  (3 kept) and deptry are clean.
- Nightly Hypothesis on `test_layout_tagged.py`, `test_layout.py` and `test_layout_tagged_corpus.py`:
  77 passed.
- Browser suite (Chromium 1243): 46 passed.
- **Linear time.** The Time Machine took 0.0035 s once, 0.033 s at ×10 and 0.48 s at ×100 (34,400
  blocks, ids and `link:` targets renamed per copy). The Markdown body on one page took 0.003 s at
  ×10 and 0.031 s at ×100.
- PR CI on f56fe95: all checks green.

## Must-fix

**M1. A note whose text starts with a longer number takes the mark as its label, and textprep
then cuts the number.**
`_marked` sets the label when `block.text.lstrip().startswith(mark)`. Take a noteref "1" linking to
`<aside epub:type="footnote"><p>1984 was a novel.</p></aside>`: the note gets label "1", and
`sci2audio script` writes "Footnote 1.\n984 was a novel." (I ran it.) That is silent text damage.
Fix: take the mark as the label only when what follows it is the end of the text, white space, or a
"." or ")" followed by white space. That is the same shape textprep's `_introduction` removes. Add a
test with "1984 …", "1a …" and "1. Text".

**M2. The display formula number accepts any bracketed letters at the end, so `f(x)` gets the
label "x".**
`_FORMULA_NUMBER` is `\((alnum{1,6}…)\)\s*\Z` with no white space required before it. So
`$$ f(x) = \sin(x) $$` gets the label "x", and the notice step would say "Formula x is skipped."
Any formula ending in `(t)`, `(n)` or `(x)` does the same, which is common in physics.
Fix: use the PDF rule's number shape (`layout/maths.py` `_NUMBER`: white space before the "(", a
digit required, as in "(12)", "(16a)" and "(A.2)"). Share it with `maths.py` rather than copying a
looser one. Add tests: `f(x)`, `\psi(t)` and `g(n)` get no label; `a = b (2)` and `(A.2)` do.

**M3. The figcaptions of two neighbouring figures merge into one CAPTION.**
Figcaption units share the key `("figcaption",)`, so two figcaptions with no picture between them
are joined. Example: `<figure><img/><figcaption>Figure 2: bee</figcaption></figure><figure>
<figcaption>Figure 3: cee above</figcaption><img/></figure>`. This gives one CAPTION, "Figure 2:
bee\nFigure 3: cee above", which describes figure 2. Figure 3 gets no caption, and the script reads
"Figure 2 is skipped. / Figure 2: bee Figure 3: cee above / A figure is skipped."
Fix: a figcaption line that opens with its own caption label (`caption_label`) starts a new CAPTION.
Keeping lines of one figcaption together is still right. Any other rule that keeps two figures'
captions apart is fine too. Add the test above.

## Should-fix

**S1. A heading that is only inline maths becomes a FORMULA, and its section is lost.**
`# $E=mc^2$` gives a FORMULA and no section. The "innermost decides" loop lets the `role:math` span
inside the `h1` win. Fix: an `h1`–`h6` in the context wins over maths inside it. The list-item and
paragraph cases ("a whole line of maths is a formula") stay as planned.

**S2. Two rules survive mutation, so they are untested.** I mutated 13 lines of `tagged.py`.
- (a) `firsts = {e.page: e.level for e in reversed(self.entries)}` → without `reversed` (the last
  entry for a page sets its base, not the first, which D-407 asks for): all tests pass.
- (b) `_from_entry` guard `k not in heads` removed (two entries pointing at one block: the later one
  overwrites the first): all tests pass.
Add one test for each. Two more survivors are equivalent mutants, so those checks are dead code:
`label in block.text` in `_labelled` (the label always comes from the text) and `block.text.strip()`
in `_from_entry` (outline entries without a letter are already dropped). Remove them or keep them,
and say which.

**S3. A noteref mark inside a heading stays in the section title.** Both
`<h2>Intro<a epub:type="noteref">1</a></h2>` and Markdown `# Intro[^a]` give the section title
"Intro1", which becomes the chapter name in the script and the M4B. #189 only removes marks from
running text. Fix: either leave noteref runs out of the title in `tagged.py`, or add an acceptance
criterion for section titles to #189. Say which.

**S4. Hidden text inside a visible line is read aloud.**
- `<p>Visible <span hidden>SECRET</span> text</p>` gives the PARAGRAPH "Visible SECRET text". D-411
  covers only whole lines, so layout follows the decision here, but the text is not shown and would
  be spoken. The same happens to an inline page-break span that holds text ("after 13 mid").
  File an issue (textprep: a marked remove for runs tagged `hidden`/`aria-hidden` and for inline
  page-break markers). The coordinator sets the milestone.
- In layout itself: a whole-line hidden line after a `<br>` (`<p>a<br/><span hidden>…</span></p>`)
  joins the visible paragraph, because `br` continuation runs before the hidden check. Fix in
  `_units`: a `br` line whose own context is hidden starts its own FURNITURE element.

## Nits (no change needed to merge; say what you did)

- N1. I could not reproduce the per-paper hashes in the PR body's table. I tried sha256 of the
  snapshot entry body, of the whole entry, and of `golden_text`. The whole-file sha256 is right and
  my regeneration is byte-identical, so the table adds nothing. State how it was computed, or drop it.
- N2. Plan §4 promised a Hypothesis property: content with a box anywhere gives the same document as
  before. It isn't there. By inspection it holds, because routing is a single early return. Say so
  in the PR body.
- N3. A `nav` in the spine that is not the toc (landmarks, page-list) and not hidden is read as list
  items. Consider treating any `nav` as FURNITURE `contents`.
- N4. A Markdown display formula numbered with `\tag{3}` gets no label. Optional.

## Checked and fine

- Nested lists (D-415): one LIST_ITEM per line, and a multi-paragraph `li` gives several items.
- A table right after a table merges (D-412). A caption between two tables splits them, and the
  caption describes the table after it.
- An `h1` in a chapter file whose outline level is 2 gets level 2, and its `h2` gets level 3.
- A figure without a figcaption is a FIGURE with text "" and no caption.
- A picture inside a table cell joins the TABLE. A picture between two notes with different ids
  stays its own FIGURE.
- Outline-only sections: an entry whose printed text matches becomes a HEADING. One that doesn't
  match starts a section with no heading block (`app.chapters` handles a section without a heading
  block; no text is lost).
- A page-break `div` is FURNITURE page-number. A nav toc in the spine is FURNITURE contents.
