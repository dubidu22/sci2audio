# Answer to the review of PR #539, round 2

Fix commit: 17fa700 on layout/front-matter-456 (one commit, on f40b61d). Main not merged in; ci:full label stays off.

| item | what was done |
|---|---|
| F3 | In `headings.front_matter` the per-section guard `(start, end) == (0, len(blocks))` is replaced by one check after the loop: when the found sections together cover every block (`sum(end - start) == len(blocks)`; they never overlap, since starts are taken in page order and an overlapping one is skipped), no front matter is returned and the file reads as before #456. Docstring of `front_matter` updated; module rule 5 already says "Front matter never holds the whole document". |
| Test | `test_front_matter_in_several_sections_that_would_be_the_whole_document_is_none`: your shrunk example (two pages of one paragraph each, outline "Cover" p1 plus "Cover" p2, and again with "Impressum" p2): no publisher section, `default_selection` not empty. Fails on f40b61d, passes now. `test_front_matter_that_would_be_the_whole_document_is_none` stays and passes. |
| Mutation | Guard off (`return {}` → `pass`): both whole-document tests fail. |
| Corpus | Every block, section (with publisher flag), chapter and default selection of the 8 corpus papers identical to main 94a4353 (same probe as round 1). |
| German paper (measuring only) | Chapters: Cover, Impressum, Inhaltsverzeichnis (publisher, deselected), "Bildung und Nachhaltigkeit. Zur Aktualität …" (title chapter), "Zur Aktualität …", I, II, III, Literatur (references, deselected), Internetquellen. Default selection {3, 4, 5, 6, 7, 9}. Unchanged. |
| Fast suite | 7,042 passed, 3 skipped locally (`-n 4`); ruff, format, lint-imports clean. |
