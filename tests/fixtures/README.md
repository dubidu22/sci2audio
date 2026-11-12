# Stored PDFs for extraction tests

Files the tests can't make themselves: most test PDFs are made inside the tests with
`tests/unit/pdf_maker.py`, and the other broken cases (empty, truncated, not a PDF) are cut from
the corpus. All files here are our own work, made for these tests, CC0-1.0.

| File | What it is | Made with |
|---|---|---|
| `broken/password-protected.pdf` | A blank 200 × 200 pt page, encrypted (AES-256, user password `sci2audio`); extraction must refuse it with a clear message (Issue #23, testing issue #5) | pikepdf, once |
| `metadata.pdf` | A blank 200 × 200 pt page with Title, Author (`Lovelace, Ada; Babbage, Charles`), CreationDate (5 March 2024) and `/Lang` `en-GB`, which PDFium can't write | pikepdf, once |

pikepdf (MPL-2.0) is not a dependency; it was only used to make these files.
