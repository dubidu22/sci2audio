# PR #671 review, round 1 (head 933cdf4)

Reviewer: B-L1 layout review thread, Opus. 20 Nov 2026. Plan: plans/layout-b-l1-plan.md (D-835).
Critical: **yes** (CRIT-01: golden files under `tests/unit/__snapshots__`, `risk:high` set; plan approved as D-835).
Verdict: **changes requested** (1 must-fix, 1 should-fix, 2 notes).

## Checked and fine

- **Rules against plan and issues.** #125 lives in `extraction/pdf.py` (`_accents_onto_letters`, `_under`, `_across`) as D-835 Q1 to Q3 decide: only lone-accent lines are composed, NFC, ids not renumbered, `ACCENT_LINES` = 8 bounds the search. #126 (`layout/paragraphs.py` `_on_row`, `_band`) measures the row's band from the largest-size runs over the row as a whole, and only adds a condition to the old join, so it can split but never join more. The denominator (#322) and inline-mark (#163) paths are untouched.
- **Tests (a) to (g).** All present: after-word, before-word (before the line above), no letter under it, inside a line, ids, Chi's "Doug" case on `_accents_onto_letters`; braces (e), tall piece between two lines on `rows_of` (f), Liu stacked scripts (g). Run against main's `pdf.py` and `paragraphs.py`: 7 new tests fail, the 3 guards (c, d, g) pass, as the PR says.
- **Hypothesis property.** `test_an_accent_stored_apart_is_never_a_line_of_its_own`: my 150-example probe hits both branches (composed 76, left inline for #65 74), so the composed branch is really exercised.
- **Golden diff, line by line.** Exactly as the PR body says. `test_extraction_corpus.ambr`: Chi p6-l61 / -l63, Hardt p6-l11 / -l12, Liu p6-l37 / -l38, p6-l47 / -l48 and the three line counts; nothing else. `test_layout_corpus.ambr`: Chi blocks 74 and 76 differ in one character each (" " → "\n" before "321–340." / "531–548."), Chi 75, Hardt 80, Liu 113 and 116 lose the accent and one part. `test_app_corpus.ambr`: Hardt only (set-aside 15 → 14, the removed accent edit, block 80 offsets 2 back, report counts 84 → 83). `test_textprep_furniture.ambr` (63 → 62, 15 → 14, 32 → 30) and `test_textprep_citations_links_corpus.ambr` (Liu [66] "Želez…") follow from the same four lines (N1). No truth file or regression case changed.
- **Layout invariants.** `test_layout_never_fails_and_keeps_every_line` (its strategy draws run boxes and `None`), every item in one block and `test_each_line_stands_in_its_block_as_found` are green; `_band` cannot see an empty row, since `rows_of` only calls `_on_row` when the row's last element and the piece are text lines.
- **Layers.** `extraction/pdf.py` adds only `unicodedata`; the combining table is extraction's own copy, nothing from textprep. `lint-imports` 3 kept, `deptry` clean.
- **Licence.** No dependency, file, model, voice or text added; the PR's licence note says so.
- **No unrelated change.** 9 files: the two modules, two test files, five goldens.
- **Local run** (temporary worktree at 933cdf4, macOS): ruff, ruff format, lint-imports, deptry green; `pytest -m "not slow and not benchmark and not browser" -k "not espeak"`: 8368 passed, 6 skipped, 6 xfailed, 0 failed.

## Must fix

**M1. A second lone accent over the same letter is lost.** `src/sci2audio/extraction/pdf.py:880-886` takes candidate letters from every line in reach, including other lone-accent lines and ones already placed, and `_under` (line 902) accepts any one-character `isalpha()` text. "ˆ" (U+02C6) and "ˇ" (U+02C7) are category Lm, so `isalpha()` is true for them. Two accents drawn as glyphs of their own over one letter (a stacked "ế" in a Vietnamese name, set as "ˆ" plus "´") stand at the same height, so the second overlaps the first accent across more than it overlaps the letter and is put onto the first accent's character. Probe on `_accents_onto_letters` ("Nguyen", "ˆ" then "´" over the "e"): placed {1, 2}, the page reads "Nguyên", and the acute is gone without a trace (the first accent's line is already left out). With the order reversed, the result is a line "ˆ́" of its own, not composed. This breaks the plan's §6 "no character is lost" and D-57 (nothing changes text silently). Fix at the root: a character of a lone-accent line (or any `_COMBINING` key) is never a letter for `_under`; then both accents go onto the "e" (NFC "ế"). Add a made-up test with two stacked accents in both stored orders, and let the Hypothesis property draw a second accent over the same letter now and then.

## Should fix

**S1. The planned corpus check is missing.** Plan §4 ("Corpus") promises a check that Chi p6 reads "Marasović" and that the two references end "pages" with "321–340." / "531–548." on lines of their own. No truth file mentions these lines (`grep` over `tests/corpus` finds none), so the verbatim-sentence test does not cover them, and only the snapshots pin the result. Add a small corpus test with direct assertions on those Chi p6 blocks (and Hardt / Liu names), so a later `--snapshot-update` cannot silently undo #125 or #126 (`tests/unit/test_layout_corpus.py` or `test_extraction_corpus.py`).

## Notes

- **N1.** Plan §5 said the textprep goldens would not change; they do, for the reason the PR body gives (each lone accent was a set-aside "not read" characters edit). Accepted as explained.
- **N2.** `src/sci2audio/layout/paragraphs.py:233`: `for r in runs if r.box` repeats the filter of line 231; drop it with the fix commit if convenient.

## Handoff (THR-07)

- Goal: PR #671 (B-L1) to merge.
- Done: round 1 at 933cdf4, changes requested (M1, S1).
- Next: round 2 on the author's fix commit; check the stacked-accent test and the corpus assertions, then the three-system run on the final head (CRIT-02).
