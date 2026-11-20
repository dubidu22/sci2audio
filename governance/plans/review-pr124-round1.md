# Review of PR #124, round 1 (core: Content.outline, #24 part 1)

Reviewed head: aec74e7 (up to date with main a0d363a). Plan: plans/issue24-outline-plan.md section 3; decisions D-262 to D-273 (section 7).

## Result

No must-fix. One should-fix (a missing refusal test), no nits on the code. Ready to merge once S1 is answered (fixed, or deferred with an issue).

## What I checked

- **Dataclass and validation against section 3, D-263 to D-266:** `OutlineEntry(title, level, page=None)`, frozen, only these three fields. `level >= 1` in `OutlineEntry.__post_init__`; in `Content.__post_init__` the first entry must be at level 1 (start level 0, at most one deeper), each entry at most one level deeper than the one before, any number of levels back up, and `page` None or 1..len(pages), which equals "an existing Page.number" because pages are checked to be 1, 2, 3, ... just before. Titles are not touched (D-266).
- **Oracle check:** 5000 random outlines (levels -1..5, pages None or -1..5, 0 to 3 pages) built through `Content`: accepted exactly when the rule in section 3 holds, refused with ValueError otherwise. No mismatch.
- **Export:** `outline` defaults to `()`, so `to_data` leaves it out when empty and no other golden file changes (fast suite: 54 snapshots pass, only `test_core_content.ambr` changed). `page=None` is left out too, `title=""` is kept. Old saved data without `outline` loads with the default.
- **Golden diff:** only the two made-up examples gain outlines: PAPER with Introduction (1, p1), "Motivation " (2, p1, trailing space), Results (1, p2), "" (1, no page); EPUB with Chapter One (1, p1). Each line matches the PR's explanation.
- **Strategy:** `contents()` now draws outlines through `outlines(count)`. Measured on 2000 draws: 59% have an outline, 31% go to level 2, 8% to level 3, 52% have an entry with no page, 33% have an empty title or one with outer spaces (`words` is `st.text(max_size=12)`). Round trip, JSON round trip and the sorted, repeatable export run on them.
- **Callers:** the only `Content(...)` in src outside core are `extraction/pdf.py` and `testing/documents.py`, both by keyword or with the new field at its default; nothing rebuilds a `Content` field by field and could drop the outline.
- **CHANGELOG** line present, names D-262 to D-266. Feature IDs IN-01, TP-16 match the issue. "Part of #24" (not Closes) is right for PR 1 of 3.
- **Local runs:** ruff check and format, lint-imports (3 contracts kept), deptry: clean. Fast suite with the ci profile: 1924 passed, 17 subtests. PR CI: green on Linux, macOS and Windows, lint and layers, licences, security, CodeQL.
- **Hand mutations of the new checks (7):** 6 killed, 1 survives, see S1.

## #123 and the nightly profile

- The smallest case in #123 raises `ValueError: items in more than one block: ['d']` on main a0d363a and on the PR head alike. The PR changes no layout code. Independent of this PR: confirmed.
- How often the nightly profile reaches it: `test_layout_headings.py` plus `test_layout.py` with `HYPOTHESIS_PROFILE=nightly`, a fresh example database each time, seeds 1 to 8: 43 passed every time, on main and on the PR. The failing test alone, seeds 101 to 124: passed every time on both. 30,000 generated `contents()` examples straight through `build_document` (generation only, no shrinking): 0 crashes on main, 0 on the PR.
- So the crash is rare in both trees and this PR does not make the nightly job fail. **No skip and no `@example` change now**: skipping would weaken a test, and the nightly job is not required for merging. If a nightly run does go red on it, #123 (P1) already holds the cause.

## Must-fix

None.

## Should-fix

- **S1. No test pins "back up, then two levels deeper".** Replacing `level = entry.level` with `level = max(level, entry.level)` in `_check_outline` keeps every test green, so an outline like levels 1, 2, 3, 1, 3 (back up to 1, then a jump to 3) would be accepted by that broken version without any test noticing. Add one refused case to `test_invalid_values_are_refused`, for example `outline=(OutlineEntry("A", 1, 1), OutlineEntry("A.1", 2, 1), OutlineEntry("B", 1, 1), OutlineEntry("B.1.1", 3, 1))`.

## Nits

None on the code.

## For the coordinator

- #123 has no milestone. Layout must never fail on any `Content` (D-76), so it probably belongs in v1.0; it is layout-lane work after #36.

## Round 2 and merge (13 Nov 2026)

- S1 fixed in 58df7e2: the new refused case (A 1, A.1 2, B 1, B.1.1 3) kills the `max(level, entry.level)` mutant (checked: 1 failed with the mutant, all pass without). Nothing deferred.
- Branch updated with main twice by merge commit (#116, then #121); merged head 94879dc: 2103 fast tests pass locally, CI green on Linux, macOS, Windows, browser, lint and layers, licences, security, CodeQL.
- Squash-merged as 1064e18; CI on main green. #24 stays open for PR 2 (extraction) and PR 3 (layout). #123 is in milestone v1.0.
