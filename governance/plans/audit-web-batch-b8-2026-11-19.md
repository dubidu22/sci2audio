# Light audit: web batch B8 (figures in the player), 19 Nov 2026

Scope: the batch's one PR, #582, merged as **678fe3c** (squash, pinned to ba33026; rounds at b146eea, 065d22c,
bbbf45c). Issues: #293 and #534 closed, #541 closed as met. Follow-ups: #579, #580, #581. Auditor: the B8 review
thread (one PR, so the cross-PR check is against the follow-ups and the contract touches). Opus medium scope.

## Contract touches

- **Layers (lint-imports):** unchanged. `web/figures.py` imports `core` and `extraction` only through
  `sci2audio.extraction`'s public names, and `web` may do so. 3 contracts kept on every run.
- **Core dataclasses:** none changed. `Region` is a new extraction dataclass that holds a `core.Box`.
- **Extraction (cross-lane, D-756):** additive only. The new pieces are `extract_pdf_regions`, `_regions_of_file`,
  `_region`, `region_scale`, `Region`, `REGION_*` and `extract_epub_picture`. `_isolated` gained an optional
  `extra=()`, and `_LIMITS` gained two names that every child receives (harmless for `extract_pdf` and the cover).
  No golden file or regression case moved.
- **readalong-format.md / audio.json / document.json:** unchanged. The route reads `document.json` and applies the
  D-295-style id check.
- **HTTP API:** one new route, `GET /api/v1/documents/{id}/figures/{block}/{image}` (integers only). It is in the
  OpenAPI schema and Schemathesis covers it. ZAP calls it (404 for a heading). The repo has no route list document to
  update.
- **Files written:** `<project data folder>/figures/*.png`. Writes happen under `store.unchanged`, never with
  `parents=True`, and the folder is removed with the project (#470/#569 path, tested).
- **CHANGELOG (D-768):** one Unreleased/Added line. It survived two main merges (#572, #585) unchanged.

## Follow-up issues: checked against the merged code

- **#579 (Markdown pictures):** matches. `Catalog.images` returns nothing for `SourceFormat.MARKDOWN`, and the AC's
  copy-at-open-time design does not need the route to change, since the record carries the `ref`. Milestone unset
  (Colin's step).
- **#580 (`sci2audio listen` jobs):** matches. `pages.listen` passes `figures=not found.outside`, and the route
  answers 404 for `cli-` ids because `DocumentStore.get` checks `ID`. The AC says crops are never written into the
  job's folders, which fits `Figures.image` taking the folder from the store. Milestone unset.
- **#581 (GIF/WebP):** matches. `extract_epub_picture` uses `media_type` and `small_enough` from `cover.py`, so the
  AC's header readers belong there, and SVG stays refused, with a test that already exists. Milestone unset.

## New findings (issues filed)

- **A1 → #596:** the privacy page's "Project folders" text (`privacy.work`, en and de) lists what a project folder
  holds but not the new figure pictures. It is a string-only follow-up, and was left out of #582 on purpose because
  B7 owned `web/strings` during the batch.
- **Seen in review, not this batch's:** #587, a Python 3.13-only failure of
  `test_a_declared_codec_that_is_not_for_text_reads_as_utf_8[punycode]` that is pre-existing on main.

## Lessons for the ledger

- Mutation claims in a PR body need running. 2 of the 13 claims at b146eea did not hold: the EPUB `ref` guard (exact
  zip names make it reachable only through a member literally named `../x`), and `S_ISREG` beside `O_NOFOLLOW`
  (redundant on Linux, the only guard on Windows). Both now have tests. This is the third time
  (`sci2audio-mutation-claims`).
- A `loading="lazy"` image plus a "hide when `complete && naturalWidth === 0`" start check needs a below-the-fold test
  in all three engines. It was added as F2 and passed in Chromium, Firefox and WebKit.
- A whole-file read per request (an EPUB of up to 200 MB) needs a concurrency bound. A browser sends 6 requests at
  once per host.

Thread verdict: the review took 3 rounds (round 1 three fixes, round 2 five test-only fixes, round 3 clean). No defect
after the merge so far. Main CI on 678fe3c: see the ledger line.
