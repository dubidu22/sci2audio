# Light batch audit: extraction batch B1 (18 Nov 2026)

Scope: the merged diff of #556 (d2ffcac), #559 (56d937f), #562 (215405c) and #568 (d44cf5d), read together on main d44cf5d for cross-PR inconsistencies and contract touches only (plan plans/extraction-batch-b1-plan.md, D-762, D-766). Auditor: B1 review thread.

## Files touched by the batch

- `extraction/isolate.py`: #556 moves `_wait`'s poll into the try; #568 adds `_out_of_memory` in `_child`.
- `extraction/pdf.py`: #559 adds `_Frame` turning, `_media_box`, circular angle compare; #562 adds `_SourcelessFonts` and returns the `unmapped` count from `_lines`.
- `extraction/legibility.py`, `extraction/__init__.py`: #562.
- `core/content.py`: #562.
- `docs/unreadable-pdf-text.md`: #562.
- Tests: `pdf_maker.py` (#559 `turned`, `spread`; #562 `glyph_number_pdf` and sfnt writer), `test_extraction_pdf.py`, `test_extraction_legibility.py`, `test_extraction_pdf_process.py`, `test_core_content.py`.

## Cross-PR consistency

- **#559 × #562 in `_chars`:** both edit the same loop (angle via `frame.angle`; `unmapped` from `_SourcelessFonts.has`). They are independent, and the branch was merged with main before #562 merged (MRG-03). On that merged tree, a glyph-number page shown through `/Rotate 90` reads the same text and counts 34 of 34 characters, as upright. `unmapped` counts only characters `frame.shows` keeps, which matches the docs ("only characters kept in lines").
- **#556 × #568 in isolate.py:** the two paths agree. The parent reads an OSError from poll/recv as "the child ended" and takes the reason from the exit code. The child turns PDFium's out-of-memory OSError into MEMORY_EXIT, so the parent sees "memory". The parent never sees a raw 0xE0000008 any more.
- **`Page.unmapped` producers and consumers: DEFECT A1 (post-merge, from #562).** Only `extraction/pdf.py` sets the field; text, EPUB, markup and `testing/documents.py` construct `Page` without it (default 0). One consumer filters a PDF page, though: `textprep/placeholders.py` `_read_in_place` builds a small document with `replace(page, lines=<used lines only>)` and keeps `unmapped`. On a page with glyph-number text and a captioned table, figure or formula, the kept lines hold fewer characters than `unmapped`, so `Page.__post_init__` raises. The step `table-figure-notices` then fails: StepError under strict, and outside strict the step is reported as not run and the document loses its notices. Reproduced on main d44cf5d with `make_document` + `replace(page, unmapped=34)`. Filed **#574** (bug, P2, v1.2.x, critical: core). Recommended fix: core checks only `unmapped >= 0`, and extraction's tests keep the bound. Why the reviews missed it: round 1 checked that extraction itself cannot produce `unmapped > characters`, but no review read the field's consumers outside extraction (lesson: for a new core invariant, grep every `replace(<dataclass>` in src/).
- **Naming:** `Page.characters` and `PageLegibility.characters` mean the same thing (non-space characters of the lines). `legibility` takes the first from the second.

## Contract touches

- `core.Page` gains `unmapped: int = 0` (last field) and the read-only property `characters`. This is additive, the default is left out of exports, and old data loads (tested). No other core, layer or plugin contract changes; lint-imports passes on main.
- New public API: `sci2audio.extraction.legibility` and `PageLegibility`, documented in `docs/unreadable-pdf-text.md` together with the policy pinned for B7 (#442 part B).
- The coordinate convention changed for turned pages only: positions are now on the page as shown. The `pdf.py` module docstring says so. No other doc describes PDF coordinates; `core.Box` already says "top left".

## Out of scope, and issues

- #442 part B (the app's stop and warning): #442 stays open (B7).
- Defect A1 above: **#574**.
- isolate.yml cannot run a unit test alone on Windows, so both #485 proofs used scratch branches against TST-08: filed **#573** (lane:infra, risk:high, milestone v1.2.x, proposed criteria).
- Notes that need no issue: `child.join()` without a timeout after an OSError (not reachable: only the child holds the write end, #556 N1); the font cache keyed by name, not handle (#562 N1); the two surviving mutants judged equivalent (#562 N3).
- CHANGELOG: none of the four PRs adds an Unreleased line. #559 (turned pages read as shown) and #556/#568 (a too-large PDF on a busy Windows machine now gets the size message) are user-visible fixes. This is not batch-specific: the last CHANGELOG change on main is 1e461a7 (#507), and later lane PRs (#552, #558, #561) add none either. Left to the coordinator as a cross-lane point; no issue filed.
- Scratch branches for Colin's delete list: `ci/isolate-485`, `ci/isolate-568`.

## Ledger reading

4 PRs, 6 review rounds in all (#556 1, #559 2, #562 2, #568 1), 3 must-fix findings (#559 M1, #562 M1 and M2). 1 post-merge defect (A1, #574, from #562). One defect found between merges and fixed the same evening: the 0xE0000008 path, which #556's un-quarantine exposed and #568 fixed. One allowed CI re-run (pip-audit PyPI timeout). Main is green on all three systems after each merge (d2ffcac, 56d937f, 215405c; d44cf5d pending at the time of writing).
