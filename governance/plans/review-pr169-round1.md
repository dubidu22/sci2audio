# Review of PR #169 (extraction: Markdown, plain text and their broken files, #74 part 2), round 1

Head reviewed: 779e211 (up to date with main d79eb25). Plan: plans/issue74-text-input-plan.md, D-337 to D-352.

## What I checked

- **Move commit bc38d46**: the moved block of the old `epub.py` (limits, `_BLOCKS` … `_WHITE`, `_clean`, `_resolve`, `_fold`, `_Anchors`, `_Element`, `_Reader`, `_runs`, `_resolve_links`) with the renames applied by sed, diffed against `markup.py` ignoring white space: only comments and blank lines differ. `epub.py` only gains the imports and the renamed calls. `test_extraction_epub_corpus.ambr` is not touched by either commit and passes: the EPUB golden is byte-identical.
- **Plan**: dialect, render rules, roles, Pandoc dollar rules, front matter reader, empty outline, text lines and tags, encoding order, the broken-file table and both limits all match D-339 to D-351.
- **Licences**: markdown-it-py 4.2.0, mdit-py-plugins 0.6.1, mdurl 0.1.2 are MIT by their installed metadata; rows in THIRD_PARTY_LICENSES.md. Both samples are own text, CC0-1.0, with rows in tests/corpus/LICENSES.md; I read both in full: no third-party text, made-up names (A. Example, B. Sample), example.org links, a 10.0000 DOI.
- **Goldens and truth (D-60)**: read both golden entries line by line against the sources (hard break kept by `.gitattributes`, notes numbered by first use, `#method` stays `href:` as anchors are off, `#fn1` resolves, comment and `***` give no line). Truth files agree with the sources.
- **Runs**: ruff, format, lint-imports (3 kept), deptry: pass. Fast suite: 2799 passed, 20 subtests, 57 snapshots. Nightly Hypothesis on the new tests plus EPUB and corpus tests: 266 passed. CI on 779e211: all green on Linux, macOS, Windows, browser, licences, CodeQL.
- **Fail-not-lose fuzz**: 3,000 random documents mixing quotes, bullet and ordered lists, indentation and footnote definitions, depth 1 to 120, each word unique: every file either failed with the nesting message or kept every word. No loss found.
- **Probes** (all read or failed cleanly, no crash): `http://[x` in Markdown links, images and raw HTML; inline notes `^[...]`; notes inside notes; maths in tables; labelled display maths; U+2028, VT, NEL; unclosed front matter; bad dates; lone CR.
- **Hand mutants**: limit off by one, `allow_digits`, gzip signature, UTF-32 LE mark: all killed. `typographer: True` survives, but it is an equivalent mutant (the commonmark preset has the replacements and smartquotes rules off, so the option does nothing).

## Must-fix

None.

## Should-fix

S1. **Memory and time per block are high enough that the 64 MB limit does not bound them.** Measured on this branch: Markdown of short paragraphs (`"w\n\n" * n`) costs about 70 µs and about 2 KB of peak memory per paragraph (400,000 paragraphs, 1.2 MB of file: 28 s, 0.82 GB); plain text of short lines about 440 bytes per line (2,000,000 lines, 4 MB: 12 s, 0.88 GB). Linear, but a 64 MB file of one-character lines would need about 14 GB (text) or about 45 GB (Markdown) and many minutes. Real files are far from this (a 1 MB book is under a second), and the EPUB reader has the same per-member shape, so a new limit is a new decision, not a fix for this PR. Suggested: file a GitHub issue ("limit lines or blocks per document, Markdown/text/EPUB") and link it in the reply.

S2. **Pin three CommonMark behaviours that drop text from the file on purpose**, so they are decided, not accidental: (a) a footnote definition that is never referenced is not read (`Body.\n\n[^1]: A note nobody cites.` gives one line); (b) of two definitions with the same label only one is read; (c) a `<!--` that is never closed hides the rest of the file (`<!-- hello\n\nworld` fails as "holds no text"; with text before it, the rest is silently gone). All three match GitHub, Pandoc and a browser, so I don't ask to change them, but add a unit test for each and one sentence in the `markdown.py` docstring, so #75 and a later reviewer know.

## Notes (no action needed)

- `typographer` is set to False but has no effect in the commonmark preset; fine as documentation.
- Front matter splits a value on a vertical tab (`str.splitlines`); harmless.

## Next

Merge after the author's reply to S1 and S2 (fix or linked issue for each) and green CI on the new head.

## Round 1 answer (3b9f656)

- S1: deferred to issue #174 ("extraction: limit lines or blocks per document (Markdown, text, EPUB)"), which needs its own decision.
- S2: fixed in 3b9f656: three unit tests (uncited note not read; of two notes with one label the LAST is read; unclosed `<!--` hides the rest, alone it fails as "holds no text") and a docstring paragraph in markdown.py. Checked locally: the new tests and the Markdown/text suites pass, ruff clean.
