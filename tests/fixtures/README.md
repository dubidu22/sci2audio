# Stored PDFs for extraction tests

Files the tests can't make themselves: most test PDFs are made inside the tests with
`tests/unit/pdf_maker.py`, and the other broken cases (empty, truncated, not a PDF) are cut from
the corpus. All files here are our own work, made for these tests, CC0-1.0.

| File | What it is | Made with |
|---|---|---|
| `broken/password-protected.pdf` | A blank 200 × 200 pt page, encrypted (AES-256, user password `sci2audio`); extraction must refuse it with a clear message (Issue #23, testing issue #5) | pikepdf, once |
| `metadata.pdf` | A blank 200 × 200 pt page with Title, Author (`Lovelace, Ada; Babbage, Charles`), CreationDate (5 March 2024) and `/Lang` `en-GB`, which PDFium can't write | pikepdf, once |

pikepdf (MPL-2.0) is not a dependency; it was only used to make these files.

EPUBs for tests are never stored here: every made-up and broken EPUB (password, DRM, missing
container, zip bombs, entity declarations, ...) is built inside the tests by
`tests/unit/epub_maker.py` (#73, D-316). The one real EPUB is the corpus file
`tests/corpus/epub/wells-the-time-machine.epub`.

Markdown and text files for tests are never stored here either: the made-up and broken ones
(empty, only white space, NUL bytes, a PDF or zip named `.txt`, every byte order mark,
Windows-1252, nesting past the limit, CommonMark's pathological inputs) are built inside the
tests (#74, D-347, D-348). The two real samples are the own corpus files
`tests/corpus/markdown/sci2audio-sample-note.md` and `tests/corpus/text/sci2audio-sample-plain.txt`.
