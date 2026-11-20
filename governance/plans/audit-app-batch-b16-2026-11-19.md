# Light batch audit: app batch B16 (19 Nov 2026)

Scope: the merged diff of #598 (7e68106: #186, #207) on main 7e68106, against the plan plans/app-batch-b16-plan.md (D-776). One PR in the batch. Auditor: the B16 review thread.

Result: **no defect found and no new issue needed.** #605 (a page with only a small logo named as a scanned page) is the one leftover, filed in round 1.

## Consistency
- `picture_pages` and `unreadable` (#577) both live in app/readability.py, are PDF only (D-772) and use `page_ranges`. They cannot name the same page: an unreadable page has text (glyph numbers), a picture page has none.
- Warning order in `build_report`: unreadable, picture, language, then encoding; pinned by a test. The CLI (`_document_warnings`) prints the picture warning first among its own warnings; the unreadable case stops earlier (exit 5) in `convert`.
- Report JSON: `picture_pages` is added last and only when non-empty, like `unreadable`; corpus snapshots and test_cli_golden unchanged.
- Web: callout `#picture-pages` uses document.picture_pages.one/.other in en.toml and de.toml with the same placeholders; the English warning also stays in the Notes list, as for `unreadable`.
- #207 `shown_original` feeds report.md and the document page's check table (pages.py); the JSON `original` stays raw.
- CHANGELOG (D-768): the Added (#186) and Fixed (#207) lines are on main beside #600's line.

## Contract touches
- No layer contract, core dataclass, golden or regression change. `Report` (app layer) gains `picture_pages: tuple[int, ...] = ()`. lint-imports on main: 3 kept, 0 broken.
- C3 held: no change to web/static/app.js, web/player.py, web/api.py, tests/unit/test_web_outside.py or layout/.
