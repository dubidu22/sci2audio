# Review of PR #167 (core: Source.encoding, Source.encoding_guessed, #74 part 1), round 1

Head reviewed: 90cef45. Plan: plans/issue74-text-input-plan.md, D-337 to D-352 (D-346 for these fields).

## What I checked

- Diff against the plan (q10/D-346, PR 1 test list): two optional fields with defaults "" and False; `Source` refuses `encoding_guessed=True` without an encoding; defaults left out of the export. Matches.
- Golden change: only `tests/unit/__snapshots__/test_core_content.ambr` changes, and only by adding a `text` entry (made-up `notes.txt`, Windows-1252 guessed, `p` then `p`,`br` as D-344). The `pdf` and `epub` entries are byte-identical; no other snapshot, truth or corpus golden file is touched (4 files changed in total).
- Merged with main (47c86fb, #144) locally, since the branch is behind: ruff check, ruff format --check, lint-imports (3 kept, 0 broken), deptry: all pass. Fast suite: 2446 passed, 20 subtests, 55 snapshots.
- Nightly Hypothesis profile (2000 examples) on every test using `contents()`: test_core_content, test_core_objects, test_core_properties, test_layout, test_layout_headings, test_extraction_epub_corpus: 201 passed.
- from_data probes: guessed without encoding, `encoding_guessed: 1`, `encoding: 5` are all refused with ValueError.
- Hand mutations of the new code (drop the check, invert it, flip either default): all 4 killed by test_core_content / test_core_objects.
- CI on 90cef45: all green except macOS still queued at review time.

## Must-fix

None.

## Should-fix

S1. `Source` accepts an encoding on a PDF or EPUB source (`Source("a.pdf", SourceFormat.PDF, encoding="utf-8")` builds, and `from_data` accepts it), although the new docstring says the field is empty for those formats. Core already guards its other invariants in `__post_init__` (bare file name, guessed needs an encoding). Suggested fix: refuse a non-empty `encoding` when `format` is PDF or EPUB, add the case to the refusal list in test_core_content.py, and draw an encoding in `sources()` only for MARKDOWN and TEXT.

## Notes (no action needed)

- The encoding name itself is free text (" UTF 8 " is accepted). Extraction PR 2 is the only writer and its encoding table tests will pin the exact names; a closed set in core is not needed now.

## Outcome

S1 fixed by the author in 7c06f5c (refusal for PDF/EPUB, two refusal cases, `sources()` draws an encoding only for MARKDOWN/TEXT). Branch updated with main twice (#144, then #132 dbbae83) via update-branch merge commits; head 595a0e8: ruff, format, lint-imports (3 kept), deptry pass; fast suite 2664 passed; nightly Hypothesis on every `contents()` user 203 passed; CI all green on all three systems. Squash-merged 13 Nov 2026 as d79eb25.
