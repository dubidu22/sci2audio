# Light batch audit: extraction batch B14 (19 Nov 2026)

Scope: the merged diff of #609 (squash 805da4e on main), the only PR of batch B14 (#175, #328, #329, #602; plan plans/extraction-batch-b14-plan.md, D-777, D-783), read for cross-PR inconsistencies and contract touches only. Auditor: B14 review thread. Verdict: **0 blocking.** 1 new issue (#633, infra).

## Files touched

`extraction/htmlparser.py` (new, CPython 3.13.18 copy), `extraction/markup.py`, `extraction/epub.py`, `extraction/markdown.py`, `THIRD_PARTY_LICENSES.md`, `CHANGELOG.md`, `tests/unit/test_extraction_markup_parser.py` (new), `test_extraction_epub.py`, `test_extraction_markdown.py`. No golden, regression case, core, layer or CI file.

## Cross-PR and cross-lane consistency

- **One batch PR, three rounds,** so no intra-batch conflict. Merges that landed beside it on main: #601/#610 (web), #611 (web player, B12), #616 (textprep B6), #630 (tests), #512 (dev tools: ruff 0.17.5, syrupy 7.0.1). None touches an extraction file; the branch was updated with main before merge (8ec6515) and its own files were unchanged by that merge; ruff 0.17.5 is clean on them; three-system CI green on 8ec6515.
- **#328 and layout (B12/B13, D-756):** no golden moved, and the corpus EPUB's `Content.order` is identical, so layout's snapshots and B13's plan inputs are unchanged.
- **#602 and textprep's figure notice:** alt text now holds no HTML tags or line breaks; no textprep regression case depended on the old text (none changed, suite green).

## Contract touches

- **Core:** none. `TextLine`, `Page`, `Picture` unchanged; no new invariant (the #574 lesson does not apply).
- **Layer contract:** `htmlparser` imports only `re`, `html`, `html.entities` (pinned by a test); lint-imports green.
- **Extraction-internal API:** `TooMuchText` gains `kind` and `message()`; new `TagLimitedParser`, `check_line`, `MAX_MARKUP`, `MAX_LINE`, `MAX_TAG` (markup.py) and `MAX_BLOCK`, `longest_block` (markdown.py). Nothing outside `extraction/` imports them (grep of src/ on 805da4e); `TooMuchText` is caught only in epub.py and markdown.py and becomes an `ExtractionError`, which the CLI reports with exit code 5 (checked) and the app handles as before.
- **Stdlib parser left in the repo:** only `tests/integration/test_voice_kokoro.py` uses `html.parser`, on its own fixture text, not on reader input; fine.

## Licence

PSF-2.0 notice, licence agreement and change summary at the top of the copy; THIRD_PARTY_LICENSES.md row present. Hand/docs items already recorded: `.claude/rules/licences.md` to name PSF-2.0 (D-777, next docs PR).

## Observations and issues

- **#633 (new, infra):** mutmut's `source_paths` include the vendored parser, so a whole-project mutation run spends time on CPython's code; leave it out with `do_not_mutate`.
- **#632 (filed in round 3):** two test gaps in new code (an SVG title in several pieces; `Budget` constructor parameters unused) and older nav / front-matter survivors. Behaviour verified correct by probe.
- **#607, #608** (filed by the author): plain-text long paragraph, NCX parsed whole by xml.etree; still open, v1.2.x proposed.
- The whole-module mutation runner for markup.py (run 44461833213, runner 1) was still running at merge time; the targeted runs covered every function #609 changed in markup.py.

## Lessons for the review archive

- The HTML parser's tag regex (`locatetagend`) keeps backtracking state per attribute: one 8 MB tag cost 1.27 GB before any handler ran. A limit on a parser's input must be checked against the parser's own internal regexes, not only the callbacks.
- In a review venv that is an editable install, mutants in another worktree need `PYTHONPATH=<worktree>/src`, or every mutant survives silently.
- mutation.yml dispatch fails at start-up (no jobs) when the mutants input is long (11 and 6 long globs failed, 3 and 4 worked); split long glob lists over several runs.
