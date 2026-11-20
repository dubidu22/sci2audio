# Review of sci2audio PR #142 (#79), round 2

Heads reviewed: 26f6271 (fixes), 0065d48 and 5926014 (test-only settle waits), 7c46994 (main #146 merged
in by this review via update-branch). KB PR sci2audio-design #42 at 37edfe1.

## Round 1 findings

- **M1 fixed.** `.stack` is now `minmax(0, 1fr)`, form controls get `max-width: 100%; min-width: 0`,
  long paths and words break. New `tests/browser/test_reflow.py` checks nine page states at 320 px in
  English and German. Mutation check: with round 1's `app.css` the test fails at once (the English start
  page was 375 px wide at 320 px too, so the fix covers more than the German select).
- **S1 fixed.** `security._unauthorised` takes the page language from the switch cookie, else
  Accept-Language (`i18n.language_from`), and the sentence from `error.no-token`; the API's 401 JSON is
  unchanged. Five unit cases. The cookie value goes through `known_language`, so nothing from the
  request reaches the page.
- **N1 fixed.** `Strings.t` raises `KeyError(key)`; tested.
- Also: the voice licence names are marked `lang="en"`.
- **K1 fixed** in KB #42: D-321 says 2026-11-13T13:06:20Z.

## New since round 1

- `settled(page)` (now in `tests/browser/conftest.py`): German, reflow and both English keyboard tests wait
  until the document page has no `data-events` before pressing keys. Cause: a page drawn while the report
  is on disk but the analysis job still runs reloads itself when the job ends. Test-only; the cause is
  recorded on #138. Flaky launch test filed as #147.

## Runs

- 5926014: fast suite (`ci`) 2246 passed; browser 29 passed twice; lint-imports 3 kept; ruff, deptry clean.
- 26f6271: nightly Hypothesis on `tests/unit/test_web_*.py` 244 passed.
- CI green on 5926014 on all three systems, browser job and CodeQL.

## Verdict

Passes. Merge pinned to the head CI passes on after the update-branch. KB #42 passes; it merges after KB
#38, #39, #40, once the author has merged main and kept numeric order.
