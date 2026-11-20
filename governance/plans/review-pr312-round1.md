# Review PR #312, round 1 (#213 PR B: footnote-places step)

Reviewed head 6c65f33. The author then merged main 405c2b6 in as 1a67d4c, which changes no files (the tree of bb84758 equals the tree of 405c2b6). Checked against plans/issue213-footnotes-plan.md (D-558).

Verdict: **approved, no changes requested.** Two older problems found while probing are filed for v1.2 (#315, #316). This PR did not cause either.

## What I checked

- Fast suite, run locally: 4671 passed, 1 skipped. CI on 1a67d4c: all green (3 systems, browser, lint and layers, licences, CodeQL).
- **Corpus, all 13 documents** (PDF, EPUB, Markdown, text): I ran the built-in steps with and without `footnote-places`. Every block reads exactly the same text in both runs, and its spans stay in order. Only the reading order changes. That makes 74 moves in all (69 PDF notes, 1 Time Machine endnote, 2 notes in each Markdown sample), and none is set aside. I printed each of the 69 PDF targets in context. Every note lands after its sentence's stop or after the marks printed there. Author lines ("Maass1, Laubach2, Herrmann3") end the block, so the notes go at the block's end, as the plan expects.
- **21 tricky sentence shapes** (English and German, regression format, whole chain run twice). These work: "et al." mid-sentence, a closing ” after the stop, a mark before the stop, "?", "e.g.,", a citation removed before the stop, "etc.", "(see below).", units, a German ordinal ("3. Mai"), "z. B.". A sentence that the link step removes whole sets the move aside, and the note stays where printed.
- **Golden diffs:** the English and German regression changes touch only the footnote cases (goals and order), and nothing is lost. `test_app_corpus.ambr` holds only hardt, maass and seaborn as golden scripts, so chi, nowak and arsiwalla appear only in the furniture counts (+6/+12/+20). The plan's section 4 list was broader than the golden set; the PR body explains every change. `test_textprep_footnotes_tagged_corpus.ambr` is unchanged because it pins only the footnotes step's edits; the tagged moves are covered by the new corpus test.
- **Changed tests:** the utterance corpus test now checks span order block by block instead of across the whole script. That is needed once notes are read inside another block, and the exact text check per block stays. The hyphens, registry and app-script tests place the move step last. None of these weakens a test.
- N2 from #307: the whole-chain property now asserts that a second run accepts no move.
- CHANGELOG entry present. The PR body has a line on chains.

## Found, not caused by this PR (filed, v1.2)

- **#315:** a German sentence ending in a closing quote (`„ja.“`) is not cut by the utterance cutter, so a note marked there is read at the end of the paragraph. English `.”` works.
- **#316:** a footnote mark glued to "bzw.", "z. B." or "Abschnitt 2." hides it from the abbreviation and number rules. "bzw." is not expanded and "2." is read "2 Punkt". The second run then reads it differently. The same happens on main.

## Merge

Squash merge, pinned to 1a67d4c, which closes #213.
