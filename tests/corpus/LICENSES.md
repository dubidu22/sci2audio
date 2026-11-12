# Sample corpus: sources and licences

Only texts we may share: our own writing, public domain, CC0 or CC BY (with attribution). Never add copyrighted papers or books, not even for a quick test.

Rules, checked by `tests/unit/test_corpus.py` on every PR:

- Every file in `tests/corpus/` has exactly one row below, and every row names a file that exists.
- `Licence` is one of `CC0-1.0`, `CC-BY-2.0`, `CC-BY-2.5`, `CC-BY-3.0`, `CC-BY-4.0` or `public domain`, as stated at the source.
- No file over 1 MB; the whole corpus under 10 MB; 5 to 10 papers (`papers/*.pdf`) and at least one EPUB (`epub/*.epub`).
- Files are stored exactly as downloaded, so their content matches the source.

`Covers` names the layout and text features a file is meant to exercise, so tests can pick the right sample: two-column, footnotes, tables, formulas, citations, URLs, code, pseudocode, examples, chapters.

| File | Title | Authors | Source | Licence | Covers | Added in |
|---|---|---|---|---|---|---|
