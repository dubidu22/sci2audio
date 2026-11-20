# Review of PR #539, round 1

PR: https://github.com/dubidu22/sci2audio/pull/539 "layout, core, app: front matter named by the outline is the publisher's chapter (#456)"
Branch: layout/front-matter-456. Reviewed head: 3f93b7e (merge of main 94a4353 on fdc27a0). Main has moved since (#519, #524 and more); it gets merged in at merge time.
Criticality: **critical** (core dataclass `Section.publisher`; labels risk:high, lane:core, lane:infra, lane:layout, lane:app). Opus high, full depth, up to 4 rounds. Plan items C1 to C3, D-755 option 1 with conditions.

## Verdict: CHANGES REQUESTED, 2 must-fix (F1, F2), 2 test gaps (T1, T2), 2 nits

The design matches D-755 and the conditions are met. Two edge cases of the C1 rule give wrong results, and two parts of `front_matter`/`_publisher` have no test (hand mutants survive).

## D-755 conditions

| Condition | Result |
|---|---|
| `Section.publisher` named in the PR body as a core dataclass change, with the reason no old-reader test applies | Yes ("C2 core (critical)"). Reason checked: `Section` is written to no file. The readalong format and caches hold chapters; extraction's child process pickles `Content`, not `Document`; no snapshot holds a `Section`; `grep` for `asdict`/`pickle`/JSON writers finds no `Section`. `layout/code.py` rebuilds sections with `replace`, so the flag survives `find_code`. |
| Corpus-truth exception worded as in the plan, in the test and in the docstring | Yes: "a publisher section from the outline starts at its page's first block" in `test_each_section_starts_at_its_heading_with_its_printed_number` and in rule 5 of the `headings.py` docstring. The test checks that publisher sections start at a page's first block (or block 0) before leaving them out of the heading check. |
| A front-matter chapter is deselected by default and can still be chosen | `test_front_matter_is_deselected_by_default_and_can_still_be_chosen`: `default_selection` leaves out chapters 0 and 1, `selected(chapters, (0, 3))` keeps 0. |
| Cover sheet found only through the outline; a PDF without an outline gets no front matter | `test_without_an_outline_nothing_is_front_matter` (same pages, no outline: no publisher section). The code has no shape rule. |
| Linux CI and the author's ci:full green before review | Yes, on 3f93b7e: tests (ubuntu-latest), tests (macos-latest) (one re-run after a runner cancel with no log, allowed), tests (windows-latest), browser (Linux, Chromium), ZAP baseline, lint and layers, licences, security, CodeQL, CI passed. |

## Checks

| Check | Result |
|---|---|
| Corpus unchanged | Own run on all 8 corpus papers, main 94a4353 vs 3f93b7e: every block, section and chapter and the default selection are identical. No corpus outline names front matter. No golden or snapshot in the diff. |
| German paper (measuring only) | Chapters: Cover (blocks 0 to 33, pages 1 to 2), Impressum, Inhaltsverzeichnis (all three publisher, deselected), the title chapter (blocks 91 to 94), "Zur Aktualität …", I, II, III, Literatur (references), Internetquellen. Default selection: the title chapter, "Zur Aktualität …", I, II, III, Internetquellen. As the PR body says; #456 criteria 1, 3, 4 met. |
| Hand mutations (subset: layout headings, layout, layout corpus, app chapters, core tests) | Killed: entry page check removed (M3), title chapter `<` to `<=` (M5), end bound by front-matter entries only (M7), start-at-0 for every section (M8). Survived: M2 `end > start` removed, M4 lifted children dropped, M9 "no heading before" check removed; see T1, T2, N1. M4 and M9 also survive the full fast suite (7,036 passed each, clean worktree of 3f93b7e, `pytest -n 8 -m "not slow and not benchmark and not browser" tests`). |

## Must fix

**F1. An outline that names only front matter can deselect the whole document** (`headings.front_matter`, the end bound).
Probe: a 3-page file whose layout finds no heading (cover sheet, a cover page, then body text) and whose outline is one entry, "Cover" on page 2.
- 3f93b7e: one publisher section "Cover" from block 0 to the end; `find_chapters` gives one chapter `("Cover", 0, 6, publisher=True)`; `default_selection` is empty, so a default script or audiobook job reads nothing.
The rule as approved ("ends at the next heading or at the next outline page") has no bound when neither exists. Wanted: a front-matter section never runs to the document's end when nothing bounds it. Choose one and say which: (a) it is then no front matter at all (no publisher section), or (b) it ends at the first block of the page after its own. Either way add a test with this probe that fails on 3f93b7e (the document keeps a selected chapter holding its body text). `test_front_matter_with_no_entry_after_it_ends_at_the_next_heading` stays as it is.

**F2. Front-matter starts are taken in outline order, not page order** (`front_matter`, the loop over `starts`).
Probe: `journal_issue(OutlineEntry("Impressum", 1, 3), OutlineEntry("Cover", 1, 2), OutlineEntry("Article", 1, 4))` from the PR's test helper.
- 3f93b7e: one publisher section "Impressum" from block 0 (pages 1 to 3). The "Cover" entry is dropped as overlapping, so the cover sheet and journal cover are listed under "Impressum".
- Wanted (the same as with the entries in page order): "Cover" (pages 1 to 2) and "Impressum" (page 3). The plan's end rule is already "by page, not outline order"; the start rule ("the first such section starts at block 0") should be too. Fix: walk the starts sorted by block. Add this probe as a test that fails on 3f93b7e.

## Test gaps (hand mutants that no test kills)

- **T1.** `_publisher`: `out += section.children` removed. No test fails. A front-matter section's children are the deeper headings `section_tree` put under it after its cut-off end; dropping them loses sections and chapters. Probe: page 1 the imprint (outline "Impressum" p1), page 2 headings "1.1 Background" and "1.2 Aims" (12 pt), then "2 Results" (14 pt) and "2.1 More". 3f93b7e: sections Impressum (publisher), 1.1 Background, 1.2 Aims, 2 Results; chapters Impressum, 1.1 Background, 1.2 Aims, 2 Results. Mutant: the two level-2 sections are gone and their blocks become a chapter titled like the document. Add this as a test.
- **T2.** `front_matter`: `and not any(h < start for h in heads)` removed (start at block 0 only when no heading stands before it). No test fails. Probe: page 1 a title heading the outline names ("A Study of Tests" p1), page 2 a contents list without a printed title (outline "Inhalt" p2), page 3 "Einleitung" and "Methode". 3f93b7e: sections A Study of Tests (0 to 2), Inhalt (2 to 4, publisher), Einleitung, Methode. Mutant: `build_document` raises `ValueError: document: section 'Inhalt' overlaps or lies outside`, so the file cannot be read at all. Add this as a test.

## Nits

- **N1.** `if end > start and …`: `end` is the least of indexes greater than the original `start`, and `start` only ever moves down to 0, so `end > start` always holds. The mutant M2 is equivalent: I searched for a counterexample and found none. Remove the check or say why it stays.
- **N2.** When an outline entry that is not front matter points at a page between two front-matter pages (say "Editorial" on page 3, with no printed heading), the blocks of that page become a chapter titled like the document. It is selected, so nothing is lost, but its title is wrong. No change asked. Mention it under "Out of scope" in the PR body, or file an issue if you think it is worth one.

## Fix list for the author (round 1)

One fix commit on layout/front-matter-456, no other pushes:
1. F1: the bound (choose (a) or (b) and say which), plus the test with the probe (fails on 3f93b7e).
2. F2: walk front-matter starts in page order, plus the test with the probe (fails on 3f93b7e).
3. T1: test.
4. T2: test.
5. N1: remove `end > start` or give the reason.
6. N2: one line in the PR body, or an issue.
7. Hand-check that each new test kills its mutant: M4 for T1, M9 for T2, and for F1/F2 the old line back.
8. Corpus again: every block, section and chapter of the 8 papers identical to main. Give the German paper's chapter list again.
Do not merge main. CI: Linux only on the fix commit (ci:full label stays off). The final round needs a three-system run on the head I merge: I will add `ci:full` after merging main at merge time, unless you prefer to do it.
Answer item by item in plans/answer-pr539-round1.md and send me the new head once Linux CI is green.
