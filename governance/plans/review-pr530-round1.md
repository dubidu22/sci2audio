# Review of PR #530, round 1

PR: https://github.com/dubidu22/sci2audio/pull/530 "layout: running heads of small journal pages, note numbers in the notes' size, heading "I" (#457, #459)"
Branch: layout/german-pdf-456-459. Reviewed head: 91d0b79 (1 commit). Base: 96de4a3 (main is now 2979dce, CLAUDE.md only; branch is behind, merge main at merge time).
Criticality: non-critical (lane:layout). Opus medium depth, at most two rounds. No mutation run or three-system run required; a few hand mutations were run to check the "each new rule has its own test" lesson.
Plan: plans/layout-batch-german-pdf-plan.md items L1 to L7 (D-755).

## Verdict: CHANGES REQUESTED, 2 must-fix (F1, F2), 4 test gaps (T1 to T4), 2 nits

The approach is sound and the main claims hold. Two regressions against main come from L4 (`_Page._notes`): it takes any smaller line under the notes with less than 1 em of white as a note line, so a small footer or a small page number set tight under the notes is now read inside the last footnote.

## Checks

| Check | Result |
|---|---|
| Golden, regression case, corpus snapshot moved? | **No.** The diff touches 7 files: `layout/footnotes.py`, `layout/furniture.py`, `layout/headings.py`, `layout/settings.py` and 3 unit test files. No file under `tests/corpus`, no `.ambr`, no regression case. PR stays non-critical. |
| Corpus blocks unchanged | Own run: `build_document` on all 8 corpus papers, main 96de4a3 vs 91d0b79, same extracted `Content`: every block (kind, role, label, text, parts), every section and the page labels are identical on all 8. |
| Layout tests | `pytest -n auto tests/unit -k "layout or furniture or footnote or heading or corpus"` on the head: 1,216 passed, 63 snapshots passed. Full fast suite: 7,017 passed, 3 skipped. |
| New tests fail on main | Copied the 3 test files onto main: the 7 new tests named in the PR body fail, the 3 guards pass. Matches the PR body. |
| Kehren claims (measuring only, nothing quoted in tests) | Confirmed with both extractions. With main's extraction: 14 heads `Bildung und Nachhaltigkeit ∙ 59` to `70 ∙ Pädagogische Korrespondenz ∙ 55/17` become running heads, notes get labels 1 to 5 with 2/3 and 4/5 separate, sections gain "I" (main has only II and III). With PR B's extraction (032ab4a): same heads, labels and sections; the peDOCS sidebar of the other sheet half is gone. |
| #459 guessed cause re-checked (lesson) | Yes. The PR shows the cause is `heading_letters = 2`, not `printed_number`; main finds II and III but not I on Kehren, the PR finds I. The rule is narrow: same style as a heading that is only a Roman numeral. |
| Running-head detection must not eat a real first line (lesson) | The wide band (L1) applies only to text lines in `_apart` and to `_body_heads`; a body-size line still needs the D-322 repeat and coverage rules, and L3 needs the same offset to the page number on each page (`Algorithm 3`/`Algorithm 4` guard passes). Graphics, page numbers, small-line heads and footers keep the strict band. No problem found. |
| Join rules vs. real indents, numbered lists, font-style changes (lesson) | Not touched by this PR (no join rule changed). The note split (L5) needs the mark printed smaller in the text above, a line of its own and 1 em of gap: a note starting "1999 …" is not cut (tested). |
| CI on 91d0b79 | Linux CI green: tests (ubuntu-latest), browser (Linux, Chromium), lint and layers, licences, security, CodeQL, CI passed. |

## Must fix

**F1. A small footer set tight under the notes is read inside the last footnote** (`furniture.py`, `_Page._notes` and `furniture()` line `if line.id in found or line.id in self.notes`).
Probe: 4 pages of 600 x 800, notes in 8 pt under a footnote rule ending at y 712 (above the bottom band), then a repeated footer "Journal of Tests, volume 55" in 7 pt at the column's left edge at y 720 (in the band, 8 pt of white under the last note, less than `apart` = 1 em).
- main 96de4a3: the footer is a running head on all 4 pages; the notes end with "… row 4, in small letters."
- 91d0b79: no furniture at all; every page's note text ends "… in small letters.\nJournal of Tests, volume 55", so the footer is read aloud as part of a footnote.
The same happens with notes reaching into the band (journal fixture with notes plus a 7 pt footer at y 747 or 748).
Wanted: a row under the notes that is furniture by its own repeat ends the notes stack and is not taken as a note line. One way: a row with nothing beside it whose text repeats word for word at its height on `repeat_pages` pages (D-323, numbers kept); the design is yours, say which rule you chose. A note number alone ("1", "3" at the same height on two pages, the case L4 fixes) must still stay a note: the rule must keep `test_footnotes_in_the_bottom_band_are_neither_footers_nor_running_heads` green. Add a test with the probe above (footer stays furniture, notes keep their text) that fails on 91d0b79.

**F2. A small page number set tight under the notes is read inside the last footnote** (same place).
Probe: the PR's `journal_page(n, notes=True)` without the head, plus the page number `str(n + 54)` in 8 pt at the left edge at y 747 (8 pt of white under the notes).
- main 96de4a3: page numbers found on all 4 pages, `page_labels` ("55", "56", "57", "58").
- 91d0b79: no page number, `page_labels` empty, the last note ends "… down to the paper's foot. | 58".
At y 760 (white over 1 em) the PR finds them, so only the tight case breaks. The docstring's promise "a page number set apart below them still is" holds only for body-size or well-spaced numbers.
Wanted: a row under the notes that is a lone number alone on its row (`_PAGE_NUMBER` shape, nothing beside it) ends the notes stack. A note mark is never alone on its row (its text stands beside it), so Kehren's hanging marks are not affected. Add a test with the probe above (labels 55 to 58, note text without the number) that fails on 91d0b79.

## Test gaps (each new rule needs its own test; found by hand mutations on the full fast suite, 7,017 tests)

Mutants killed: `_rule_under` thickness check removed (1 failure), the `apart` white check in `_notes` removed (3 failures). Mutants that survived:

- **T1.** `_notes`: `and abs(boxed(li).x0 - box.x0) <= reach` removed: all tests pass. Add a test where smaller lines below the rule but far from its left end (for example a small line at the foot of the other column, or a right-aligned small footer) are not taken as notes.
- **T2.** `footnotes._mark`: `and row[0].text.strip() == text` removed (the mark must be a line of its own): all tests pass. Add a test where a note line whose first run is "1" followed by more text in the same line, with another piece 1 em or more to its right, is not cut, while the body prints the mark "1".
- **T3.** `_notes`: `or box.y0 < settings.footnote_band * (page.height or 0.0)` removed (the rule must be in the lower half): all tests pass. Add a test where a short thin rule in the upper half (for example under a head or above a table) with smaller lines under it does not shield those lines from the furniture rules.
- **T4.** `headings._numeral_one`: `and (text.style.bold or self._larger(text))` removed: all tests pass. As far as I can see it is redundant, because `levels` only holds styles of found headings, and those are bold or larger. Either remove it, or add a test showing a case it guards (a numeral-only heading found in body style). Say which in the answer.

## Nits (no action needed beyond answering)

- **N1.** On Kehren the page labels stay empty: the page number printed inside the head line ("∙ 61") is not used as the page's label. Not asked by #457/#458/#459; file a follow-up issue (lane:layout, v1.2.x) if you agree it is wanted, or say why not.
- **N2.** `_texts` also makes an offset variant of a number at the end of an even head ("55/17" → "55/#-…#"). Harmless (it never repeats), mention only.

## Fix list for the author (round 1)

One fix commit on layout/german-pdf-456-459, no other pushes:
1. F1: fix plus its test (fails on 91d0b79).
2. F2: fix plus its test (fails on 91d0b79).
3. T1: test.
4. T2: test.
5. T3: test.
6. T4: remove the check or add its test; state which.
7. N1: file the issue or say why not; N2 needs no action.
8. Re-run the corpus check: every block of the 8 papers identical to main, `test_app_corpus.ambr` unchanged; report the Kehren result again (14 heads, labels 1 to 5, sections I to III).
Answer item by item in plans/answer-pr530-round1.md, then tell me the new head once Linux CI is green.
