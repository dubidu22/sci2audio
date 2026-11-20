# Review of PR #539, round 2

PR: https://github.com/dubidu22/sci2audio/pull/539. Reviewed head: f40b61d (one fix commit on 3f93b7e). Answer: plans/answer-pr539-round1.md.
Criticality: critical (core `Section.publisher`). Opus high, full depth. This round was meant as the final one, so it also ran the final-round checks: hand mutations on the full fast suite, the Hypothesis nightly profile, and a property probe of the new rule.

## Verdict: CHANGES REQUESTED, 1 must-fix (F3)

All round 1 items are fixed and verified. One gap is left in the F1 fix: the guard against deselecting the whole document looks at one section at a time. Several front-matter sections together can still take every block.

## Round 1 items

| Item | Check |
|---|---|
| F1 (option b + whole-document guard) | My probe (cover sheet, cover page, body text, outline "Cover" p2): Cover (blocks 0 to 4, publisher) plus a selected title chapter with the body; `default_selection` {1}. Test added, fails on 3f93b7e. The "next heading" test is unchanged and green. |
| F2 page order | Probe (Impressum p3, Cover p2, Article p4): Cover pages 1 to 2, Impressum page 3. Sorting is stable, so two entries for one page keep outline order. Test added. |
| T1 | Probe gives sections Impressum, 1.1 Background, 1.2 Aims, 2 Results [2.1 More], and chapters to match. Test added; the author says it kills M4, and my R4 run below confirms it. |
| T2 | Probe gives A Study of Tests (page 1), Inhalt (page 2, publisher), Einleitung, Methode. Test added; kills M9 (R5 below). |
| N1 | `end > start` removed; correct (end is above the original start, and start only moves down to 0). |
| N2 | Line in the PR body under "Out of scope". |
| Corpus | Own run on all 8 papers: blocks, sections, chapters and default selection identical to main 94a4353. |
| German paper (measuring only) | Chapters and default selection identical to round 1 (Cover, Impressum, Inhaltsverzeichnis deselected; title chapter, "Zur Aktualität …", I, II, III, Internetquellen selected; Literatur deselected as references). |
| CI on f40b61d | Linux CI green (tests ubuntu, browser Chromium, ZAP, lint and layers, licences, security, CodeQL, CI passed). |

## Final-round checks

- **Hypothesis nightly profile** (`HYPOTHESIS_PROFILE=nightly`) on test_layout_headings, test_layout, test_layout_footnotes, test_app_chapters and test_core_objects: 293 passed.
- **Property probe** (scratch, not for the repo): `core_strategies.contents()` with up to 6 outline entries drawn from Cover, Impressum, Inhalt, Contents, Titelei, Article and Introduction, on any page, 3,000 examples. `build_document` never raised, and the chapters hold every block exactly once. The same probe found F3.
- **Hand mutations, full fast suite** (clean worktree of f40b61d, `pytest -x -n 8 -m "not slow and not benchmark and not browser" tests`): results in the table at the end.

## Must fix

**F3. Front matter can still be the whole document when it comes in several sections** (`headings.front_matter`, the guard `(start, end) == (0, len(blocks))`).
Found by the property probe and shrunk to: two pages of one paragraph each, outline "Cover" p1 and "Cover" p2 (the same happens with "Cover" p1 and "Impressum" p2). f40b61d gives two publisher chapters, Cover (0 to 1) and Cover (1 to 2), with no other chapter. `default_selection` is empty, so a default job reads nothing, which is what F1 was meant to rule out.
Wanted: front matter never takes every block of the document, however many sections it makes. The simplest fix is to check the union after the loop: if the found sections cover blocks 0 to the end with nothing left over, return no front matter (the file is then read as before #456). Add a test with the shrunk example (two pages, two front-matter entries) that fails on f40b61d. The single-section test `test_front_matter_that_would_be_the_whole_document_is_none` stays.

## Mutation results (full fast suite on f40b61d)

All 10 killed:

| Mutant | Result |
|---|---|
| R1 starts in outline order again (F2) | 2 failed |
| R2 no own-page end, document's end instead (F1) | 1 failed |
| R3 whole-document guard removed | 1 failed |
| R4 lifted children dropped (T1) | 1 failed |
| R5 "no heading before" check removed (T2) | 1 failed |
| R6 headed-page check removed | 1 failed |
| R7 `or section.publisher` removed in chapters.py | 2 failed |
| R8 title chapter after front matter removed | 2 failed |
| R9 trailing ".: " not stripped | 1 failed |
| R10 next heading no longer ends front matter | 1 failed |

## Fix list for the author (round 2)

One fix commit on layout/front-matter-456, Linux CI only, main not merged:
1. F3: the fix plus its test (fails on f40b61d).
2. Re-run the corpus check (blocks, sections, chapters, selection identical to main) and give the German paper's chapters again.
Answer in plans/answer-pr539-round2.md and send me the new head once Linux CI is green. Round 3 then checks F3 only. I merge main at merge time (in the coordinator's D-758 slot) and run ci:full on that head before the pinned squash-merge.
