# Textprep v1.2 second batch, PR 5: plan

Thread "Build textprep PRs 4 and 5 for v1.2", 16 Nov 2026. Base: main e107f64. Batch plan: `plans/textprep-v12-second-batch-plan.md` (D-646), PR 5 section, plus #428 folded in (D-691).

Issues: #193, #93, #191 and #428.

The PR is **critical**. It adds two text steps, changes a notice, changes corpus snapshots and a `sci2audio.testing` helper, and adds English and German regression cases. It waits for the coordinator's approval before code or tests.

I prototyped every rule below in a scratch copy of e107f64 and ran it over the 13 corpus documents and the textprep tests. The corpus changes listed here are the prototype's, and so are the tests that change. The second-run check passed on all 13 documents once the testing change in section C was in.

## A. #193: hidden runs and inline page-break markers

**New step `hidden-runs`** (`HiddenRunStep` in `textprep/furniture.py`).
- Category: Page furniture, so the "Page furniture" switch brings these runs back.
- Stage: INLINE. A block-stage edit claims its whole block (D-105), so the existing furniture step cannot hold the rule.
- Languages: all.

**What is removed.** A run whose tags include `hidden`, `aria-hidden`, `epub:pagebreak` or `role:doc-pagebreak`, inside a block of any kind except FURNITURE and the placeholders.
- FURNITURE blocks already go whole. Placeholders get their notice.
- A run's tags are the whole element stack above it (D-306), so a run nested inside a hidden span counts too.
- Tagged runs next to each other make one edit.
- A run of white space only gets no edit.

**White space.** The edit covers the run's text without the white space at its ends. When the run is followed by the end of the block or by `, ; : . ! ? ) ]`, the white space before it goes too. So "text <span hidden>x</span>." reads "text.", not "text .".

**Reasons:**
- `hidden text "SECRET" is not read (hidden in the file)` for `hidden` and `aria-hidden`.
- `page-break marker "13" is not read` for the two page-break tags.

**Order.** The step is the first inline step, before `links`. If it ran later, a citation or link inside a hidden run would win the overlap, the hidden edit would be set aside, and the rest of the hidden text would be read. `test_links_run_right_after_the_block_steps_and_before_citations` changes from `inline[:2] == ["links", "citations"]` to `inline[:3] == ["hidden-runs", "links", "citations"]`. D-167 still holds: links before citations and before footnote marks.

| printed (tags) | e107f64 | PR |
|---|---|---|
| `Visible <span hidden>SECRET</span> text` | Visible SECRET text | Visible text |
| `after <span epub:type="pagebreak">13</span> mid` | after 13 mid | after mid |
| `a <span aria-hidden="true">x</span> b`, `a <span role="doc-pagebreak">7</span> b` | read | removed |
| `text <span hidden>x</span>.` | text x. | text. |
| `<span hidden>a <em>b</em></span> c` | a b c | c (one edit) |
| hidden run in a heading, list item or footnote | read | removed |
| `<span>shown</span>` with `lang:` or `role:` other than the four | read | read |
| PDF (no tags) | | unchanged |

**Corpus.** No document changes: the Time Machine EPUB and the Markdown samples hold no hidden run inside a shown line.

**Second run.** The rebuilt text no longer holds the run, so it reads the same.

## B. #93: affiliation marks in the title block

**New step `affiliation-marks`** (`AffiliationMarkStep` in `textprep/footnotes.py`).
- Category: Footnotes (decision 4 of D-646).
- Stage: INLINE, placed right after `footnotes`.
- Languages: all.

**Title block.**
- These are the blocks of the document's first page, in reading order, up to the first HEADING block ("Abstract", "1 Introduction"). Only PARAGRAPH blocks count.
- The first page is the page of the first block that has parts.

**A mark** is a run, or several next to each other, that meets all of these:
- **Its text** is only digits, `,`, `∗`, `*`, `†`, `‡`, `§` and `¶`, apart from white space at the ends.
- **Set small:** tagged `sup`, or set more than 8% smaller than the block's main size (the footnotes step's `SMALLER`).
- **Superscript:** tagged `sup`, or its box ends at least 0.1 em above the box of a run in the main size on the same line (the footnotes step's `RISE`).
- **Not a footnote mark:** it does not overlap a mark that the footnotes step removes (`found_marks`). So "∗" with its note stays with the footnotes step, and the maass marks 1, 2 and 3, which mark notes, stay there too.
- **Shape**, one of two:
  - **After a name:** the text before it, without white space, ends in a capitalised word of two letters or more. After it comes the block's end, white space, `,`, `;` or a note mark ("Chi¹˒²", "Biggs↵¹, Matthew", "Ahmad³∗").
  - **Before an affiliation:** it stands at the block's start or after white space or a comma, and a capital follows, after at most one space ("¹Meta AI", "², University").

The shape test keeps maths and sentence marks out of the title block: "x²", "N³", "size³ + 1", "small.¹" and a "⁵ is first" list number all stay.

White space is handled as in section A: "Biggs↵¹, Matthew" reads "Biggs, Matthew".

**Reason:** `affiliation mark "1,2" is not read`.

**Corpus** (8 papers; prototype against e107f64):

| paper | e107f64 | PR |
|---|---|---|
| chi | `Jianfeng Chi1,2 Wasi Uddin Ahmad3 Yuan Tian3 Kai-Wei Chang3` / `1Meta AI, 2University of Virginia, 3University of California, Los Angeles` | `Jianfeng Chi Wasi Uddin Ahmad Yuan Tian Kai-Wei Chang` / `Meta AI, University of Virginia, University of California, Los Angeles` |
| arsiwalla | `Xerxes D. Arsiwalla1,2,` / `1Pompeu Fabra …` / `2Wolfram Institute …` | `Xerxes D. Arsiwalla` / `Pompeu Fabra …` / `Wolfram Institute …` |
| liu | `Hong Liu1 and Dimitrie Culcer1` / `1School of Physics …` | `Hong Liu and Dimitrie Culcer` / `School of Physics …` |
| waskom | `Michael L. Waskom1` | `Michael L. Waskom` |
| biggs | `Simon Biggs 1, Matthew Jennings 2, … Cody Crewson14, and Matthew Sobolewski8,15` | `Simon Biggs, Matthew Jennings, … Cody Crewson, and Matthew Sobolewski` |
| nowak, hardt | no marks | unchanged |
| maass | marks 1–3 mark notes | unchanged (footnotes step) |

**Left out.**
- The JOSS affiliation lines print their numbers in the text's own size, not raised: waskom "1 Center for Neural Science", and biggs "1 Radiotherapy AI, … 2 The Royal Adelaide Hospital …". They keep their numbers, because there is no size or position cue to tell them from a number in the text. I file an issue for them.
- EPUB and Markdown count a `sup` tag as small and raised, so the rule works there too. No corpus sample has such a title block.

**Test helper.** In `test_textprep_footnote_places_corpus.py`, `cutter_end` skips past removed marks that start where the sentence ends. Today it counts only edits of step `footnotes`; it now also counts `affiliation-marks`. The chi note "∗" now lands after the removed "3" at the end of the author block, at 60 instead of 59. The spoken text is the same.

## C. #191: an uncaptioned figure read by its alt text

**Rule (`TableFigureNoticeStep`, `textprep/placeholders.py`).** A FIGURE block that no caption names, whose pictures (`Picture` parts) carry alt text, gets the notice:
- English: `A figure is skipped. It shows: <alt text>.`
- German: `Eine Abbildung wird übersprungen. Sie zeigt: <alt text>.`

These are new `Wording` fields: `shows = "It shows: {}"` and `"Sie zeigt: {}"`.

**The alt text:**
- White space is folded to single spaces and trimmed.
- Several pictures with alt text are joined in order with "; ".
- A full stop is added unless the text already ends in `.`, `!`, `?` or `…`.

**Unchanged:**
- An empty or white-space alt text keeps today's notice ("A figure is skipped.").
- A captioned figure keeps today's notice ("Figure 3 is skipped.").
- PDF pictures carry no alt text, so PDF does not change.

**Reason:** `this figure is not read; a short notice with its alt text is read instead (D-55)`.

The alt text is part of the notice, so the inline steps (numbers, abbreviations) do not read it again, as for any notice. I'll say so in the PR.

**Testing change (needed for the second run).**
- **The problem:** `rebuilt_from_script` builds the second-run document with `make_document`, which has no pictures. Its FIGURE block would lose its alt text, and the notice on the second run would be "A figure is skipped.". The prototype failed `test_every_corpus_document_reads_the_same_on_a_second_run` for the two Markdown samples and the EPUB.
- **The fix:**
  - `make_document` gets `pictures: Mapping[int, Sequence[str]]`, the alt texts of each block's pictures. They become `Picture` items on the block's page, with parts at the end of its text.
  - `rebuilt_from_script` passes each block's pictures on, as it already keeps kinds, `describes`, roles and sections.
  - The regression-case loader gets a block key `pictures = ["…"]`.
- **Why it's safe:** the oracle still compares spoken text only. It now keeps one more thing the script cannot carry.

**Corpus.**
- `sci2audio-sample-note.md` script: `A figure is skipped.` becomes `A figure is skipped. It shows: A bar chart of minutes per group.` The second image (`![](figures/decoration.png)`, empty alt text) keeps "A figure is skipped.".
- `sci2audio-beispiel-notiz.md` script: `Eine Abbildung wird übersprungen.` becomes `Eine Abbildung wird übersprungen. Sie zeigt: Ein Balkendiagramm der Minuten pro Gruppe.`
- `wells-the-time-machine.epub`: report only. Two rows in chapters that are not chosen now read "A figure is skipped. It shows: The Standard Ebooks logo.". The script is unchanged.

## D. #428: `link_removals` passes the language on

`link_removals` (`textprep/links.py:935`) calls `LinkStep()._block_edits(0, text, kind, label, words)` without the language. It becomes `…, words, language)`, and `_block_edits` loses its `"en"` default, so no caller can leave the language out again.

The test: `link_removals("Daten finden sich u. a. https://x.org. Dann mehr.", PARAGRAPH, "", "de")` equals the spans `LinkStep` removes on the same German document, (23, 37), as does the English row. It fails on e107f64, which gives (23, 38).

There is no reading change. The 11 audit probes stay as they read today.

## Other changes the prototype showed

- **`test_textprep_steps.py::test_the_built_in_registry_is_valid`:** the id list gets `hidden-runs` (first inline) and `affiliation-marks` (after `footnotes`).
- **`test_textprep_runner.py::test_the_default_steps_are_the_built_in_ones`:** its every-step document gets a hidden run and an affiliation mark.
- **`sci2audio.testing` conformance samples:** `test_the_sample_documents_give_every_built_in_step_work` needs a sample with a hidden run and a title block with a raised affiliation mark. Both are added to the sample documents.
- **Snapshots** (`--snapshot-update`; each diff only as listed above):
  - `test_textprep_furniture.ambr`: the category summary counts of chi, arsiwalla, liu, waskom and biggs (new accepted footnotes edits);
  - `test_app_corpus.ambr`: waskom script and both reports;
  - any other corpus snapshot that holds these five title blocks or the two Markdown figures. The PR body lists each one.
- **Report step list:** two new step ids appear in reports.

## Tests (written first, failing on e107f64)

- **`english.toml` and `german.toml`:**
  - hidden runs: the six rows of A, en and de;
  - affiliation marks with `sup` runs: chi's shape and arsiwalla's "1,2,∗" shape with its note, biggs' line-start mark, and controls "x²" and "small.¹" in a title block, plus a mark after the first heading, which stays;
  - the figure notice: with alt text, empty alt text, captioned, two pictures, alt text ending in "?";
  - the Markdown sample's two images as one case (#191's criterion).
  - Every case is checked on both runs.
- **Unit tests:**
  - the `HiddenRunStep` rows, the reasons and the switch (Page furniture off: read);
  - `AffiliationMarkStep` with sized and boxed runs: the size test, the raise test, each shape, a footnote mark next to an affiliation mark (adjacent edits, no overlap), the first-page and first-heading limits, the Footnotes switch;
  - the figure notice rows;
  - `make_document(pictures=…)` and `rebuilt_from_script` keeping alt text;
  - `link_removals` for the "u. a." row.
- **Hypothesis:**
  - Any text with random hidden ranges reads as the text without them (white space folded).
  - Generated names with `sup` marks lose the marks and keep the names.
  - Marks outside the title block are never touched.
  - Conformance (no crash, valid spans, idempotent) runs for both new steps.

## Checks before review

- The second-run check over all regression cases and the 13 corpus documents.
- Corpus scripts and reports against e107f64: byte-identical except the files listed in B and C.
- Fast suite, ruff, format, lint-imports and deptry.
- Mutants of every new guard, from a clean worktree of the PR head with a passing baseline run first, run with `mut3.py` (D-676). The PR body names the command and test glob.
- A token fuzz with tagged hidden runs and `sup` marks, the whole chain twice, against e107f64. Only differences that appear on the PR alone are reported.

Size: medium.

## Decision asked for

1. **#193:** an inline step `hidden-runs` in Page furniture, the first inline step, with the two reasons above.
2. **#93:** the title-block limit (page 1, up to the first heading), the mark tests (small, raised, the charset, the two shapes), and the corpus readings above. JOSS same-size affiliation numbers are left read, with a new issue.
3. **#191:** the wording "It shows: …" / "Sie zeigt: …", with pictures joined by "; ".
4. **The testing change:** `make_document(pictures=…)`, and `rebuilt_from_script` keeping pictures, so the second-run check sees the alt text.
5. **#428** as section D.
