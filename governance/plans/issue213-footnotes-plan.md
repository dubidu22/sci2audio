# Plan: read a footnote next to its mark (#213, TP-05, D-457)

Thread "Read footnotes at their mark", 14 Nov 2026. Lane: layout lane slot (the work is core + textprep + app + web; labels on the issue: lane:core, lane:textprep). Base: main 12944c8.

**Critical: yes.** It changes the core dataclasses (`EditKind`, `Edit`, `check_edits`, `apply_edits`), the text-step interface (a new stage) and golden files (English and German regression cases, app corpus snapshots, tagged-footnote snapshot). The plan waits for the coordinator's approval before any code or tests.

## 1. What I measured (main 12944c8, all corpus files)

Script: run every corpus file through extraction, layout and `run_steps`; for each footnote mark the footnotes step removes, find its note, the chapter of both, and the end of the utterance (sentence) holding the mark.

| | Count |
|---|---|
| PDF marks found (all labelled notes on the 8 papers: chi 6, hardt 1, nowak 12, maass 30 German, arsiwalla 20; liu, seaborn, pymedphys none) | 69 of 69 |
| ... in a paragraph / in a list item | 68 / 1 |
| ... whose sentence ends inside the mark's block / runs to the block's end | 60 / 9 |
| ... mark printed right after a full stop, "?" or "!" ("environment.³ A") | 27 |
| ... note in **another chapter** than its mark | **21** (title-page and author notes placed after the Abstract heading; notes at the foot of a column where a new section began) |
| ... note standing before its mark in reading order | 0 |
| Sentence ends holding two or three marks (author lines "Maass¹, Laubach², Herrmann³"; "Qualys⁵ und Mozilla.⁶") | 6 places |
| Notes with no mark (ACL "Responsible NLP Checklist" notes in chi and hardt) | 2: they stay where printed |
| Notes printed over two pages | 0 |
| Longest distance mark → sentence end | 471 characters (maass p.7, one legal sentence) |
| Markdown samples (en, de): linked marks | 3 each; note "2" is marked twice (list item and a later paragraph) |
| The Time Machine: linked mark in chapter 10 → endnote in chapter 16 | 1 (another chapter) |

Consequences: (a) a third of the notes would land in another chapter, so chapters must follow where a note is read, not where it is printed (Q6); (b) several notes often share one sentence end, so moves to the same position must be allowed and ordered (Q2); (c) a note whose mark is after the full stop must still land after that mark (Q4).

## 2. Decisions to approve (recommendation first)

**Q1. How the edit model moves text (D-61 (1)).** Recommend: a new `EditKind.MOVE` and an optional field `Edit.to: Span | None = None`. A move edit's span covers a whole block; `to` is an empty span (a position) in another block. `apply_edits` builds the block's script as today (its own edits applied: the "Footnote 1." introduction, back-links, numbers) and reads it at `to` instead of where the block stands. `ScriptPiece` does not change: the moved pieces keep their own spans, so read-along and the report still point at the note on its page.
Alternatives not chosen: (b) a separate placement list next to the edits: outside the edit model, so the switches, the report and set-aside logic would need a second path; (c) layout moves the note block: layout cannot place a block inside a paragraph, does not know sentences, and D-414 says layout does not move text.

**Q2. When a move is valid (core `check_edits`).** Recommend: the span is the whole, non-empty block; `to` lies in another block, inside its text; at most one move per block; no chains (a block that is moved is not a target, and a target block is not moved); `to` may not lie strictly inside another edit's span, nor share its position with an empty non-move edit (an insertion or pause: their order would be a guess, D-61 (2)). Several moves to the same position are allowed and read in block order (the notes' reading order). A move does not overlap the edits inside its own block. Invalid moves raise `OverlappingEditsError`/`SpanError` as today.

**Q3. Moves run last, in a stage of their own.** Recommend: a third `Stage.MOVE` after every inline step (`check_registry` enforces block → inline → move). A move-stage step may propose only moves, and only a move-stage step may propose them (the runner raises `StepError` otherwise). So a move never blocks a rule about the text; a move that conflicts is set aside, with the edit that won, and the note is read where it is printed. The runner sets a move aside when its block or its target block is claimed by a block-stage edit (D-128: "Footnote texts" on, reference list, furniture), when `to` lies strictly inside an accepted edit, or when Q2 forbids it. `TEXT_STEP_API` stays 1: only additions, every existing step keeps working; the public plugin interface is still v1.3 (D-459).
Alternative not chosen: the footnotes step proposes the move itself (it runs before numbers, units and abbreviations, so its move would block their edits at the sentence end).

**Q4. Where the note is read: after the sentence that holds its mark.** Recommend: a new step `footnote-places` (category Footnotes, stage move) finds the sentence end with the utterance cutter's own sentence rule (abbreviations, initials, the German ordinal rule; factored out of `utterances._sentences` into a helper both use), run on the block's text with the footnote marks left out. The note goes where the white space after the sentence starts, so after closing quotes, brackets and a mark printed after the full stop. When the sentence does not end inside the block (9 of 69), the note goes at the block's end. Notes sharing a sentence end are read in their marks' order.
Alternative not chosen: after the paragraph (block end): simpler, but notes would drift up to a whole paragraph away (471 characters measured), which the issue's criterion rules out.

**Q5. Which notes move.** Recommend: every note whose mark the footnotes step removes from running text (paragraph, heading, caption, list item): printed-label marks (PDF, D-143) and linked marks (EPUB, Markdown, D-428), the latter at the **first** mark that links to the note (later marks are still left out, D-421). A note whose mark is not found stays where printed (the 2 checklist notes). A linked mark inside another note does not move its note (no chains, Q2). EPUB endnotes move too (The Time Machine's endnote moves into chapter 10). D-414 stays true: layout still does not move notes; the text step does.

**Q6. Chapters follow where a note is read.** Recommend: `StepRun.read_at(block)` gives the block whose place a block is read in (its move's target block, else itself). The app uses it when it picks a chapter's pieces (`prepare_script`), for a report row's chapter and "spoken" flag, and the player uses it too. So a note read in chapter 2 belongs to chapter 2 even when printed in chapter 3 (21 of 69 notes); a note whose mark's chapter is not chosen is not read. Without this, those notes would be dropped or read out of order.

**Q7. Switches.** Recommend: no new switch or category. The move belongs to "Footnotes" (on by default): switched off, marks are read and notes stay unintroduced where printed (as today). "Footnote texts" switched on still leaves every note out: its block removal claims the note, so the move is set aside. A switch "read notes where printed" can become an issue if Colin asks for it.

**Q8. Player.** Recommend: the player shows a moved note right after the block holding its mark, with its page label, so the view follows the voice instead of jumping to the page foot and back while it scrolls along (D-301). Alternative: show it where printed (the highlight jumps; a note printed in a chapter that is not chosen would not show at all).

**Q9. Report.** Recommend: a move is a report row in "Footnotes": kind `move`, said "read after the sentence with its mark" (German "wird nach dem Satz mit seinem Zeichen gelesen"), JSON with a `to` object (block, start, end, page, printed page) beside the usual `where`; Markdown "read after its mark on page N". The mark-removal reason changes from "the note is read at the foot of the column (Q2)" to "the note is read after the sentence that holds it".

**Q10. Pauses and the script file.** Recommend: no new pause kind. A note is another block, so it gets the paragraph pause before it and the paragraph pause back into the sentence after it (D-116); in the script text it stands on its own lines with a blank line around it.

## 3. Tests first

PR A (core, runner, app, web; no built-in step moves anything yet):
- core: `Edit` checks for a move (needs `to`, `to` empty, no replacement, non-empty span); `check_edits` for each Q2 rule; `apply_edits` order (kept text split exactly at `to`, moved pieces keep their spans and their block's own edits, the block is not read at its own place, several moves at one position in block order, a move at a block's start and end). Core Hypothesis property: random documents and valid edit sets with moves never raise, every kept character is read exactly once, spans of one block stay in order.
- runner: stage order in `check_registry`; a move from an inline step and a non-move from a move step are `StepError`; each set-aside case of Q3; "Footnote texts" on sets the move aside; switched-off category.
- conformance suite (`sci2audio.testing.text_steps`): a fake move step passes it; the suite's rendering and idempotence checks handle moves.
- utterances: a moved block between two halves of a paragraph gives utterances of three runs, no utterance spans two blocks.
- app: with a fake move step, a note printed in chapter 3 is read in chapter 2; report rows (kind, `to`, chapter, spoken); audio plan pauses; script text.
- web: report row text (English, German strings); `build_view` puts a moved note after its target block; one browser test that the highlight follows a moved note (existing fake-voice player fixture).
- regression renderer: lines follow the script order (a new line at each block change); no existing case changes.

PR B (the step, then the golden files):
- English and German regression cases first (they fail on main): mark mid-sentence; mark after the full stop; sentence running to the block's end; two marks in one sentence; a note without a mark stays; "Footnote texts" on; "Footnotes" off; a linked mark used twice (first use wins); a linked mark inside a note (stays); abbreviation and German ordinal before the mark ("e.g.", "3. Sieger"); a move whose target lies inside another step's edit (set aside, note stays).
- sentence-end helper: unit tests and a Hypothesis property (the end lies at or after the mark, inside the block, at the start of white space or the block's end).
- corpus: every one of the 69 PDF notes and the 3 tagged notes moves (or each set-aside one is listed in the test with its reason), and lands at the end of the cutter's utterance that holds its mark.

## 4. Golden files that change (PR B only)

- `tests/regression/english.toml`, `tests/regression/german.toml`: the footnote cases' expected lines change order (note after the sentence instead of after the paragraph or at the end); new cases added.
- `tests/unit/__snapshots__/test_app_corpus.ambr`: scripts and reports of chi, hardt, nowak, maass and arsiwalla (notes move; reports gain move rows; mark reasons change). liu, seaborn and pymedphys unchanged.
- `tests/unit/__snapshots__/test_textprep_footnotes_tagged_corpus.ambr`: the move edits of the Markdown sample and The Time Machine.
- Any CLI or audio-job snapshot that holds a footnote (checked when running; each listed in the PR).
PR A changes no golden file.

## 5. PR split

Two PRs, both `risk:high`, one review thread for both:
- **PR A** "core: an edit can move a block's script (#213)": `EditKind.MOVE`, `Edit.to`, `check_edits`, `apply_edits`, `Stage.MOVE`, runner settling, `StepRun.read_at`, conformance suite, app chapters/report/audio, player and report strings. Reviewable alone: everything is driven by a fake move step in tests.
- **PR B** "textprep: read a footnote after the sentence holding its mark (#213)", stacked on A: the sentence-end helper, `FootnotePlaceStep`, registry, regression cases, golden files. Retargeted to main after A merges.

Rough size: A about 350 lines of code and 600 of tests; B about 200 lines of code, 300 of tests and cases, plus golden diffs.

## 6. Not in scope (issues to file if wanted)

- A setting to read notes where printed (Q7).
- Chains: a note marked inside another note is read where printed.
