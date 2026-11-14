# Stored PDFs for extraction tests

The one file the tests can't make themselves. Every other test PDF is made inside the tests
with `tests/unit/pdf_maker.py`: through PDFium (`make_pdf`) or written object by object
(`raw_pdf`), which is how the metadata file, the files locked by an owner password (RC4,
`owner_locked_pdf`), DRM and certificate encryption, page-tree bombs, dense pages and damaged
cross-reference tables are made (#5, D-393 to D-398). The cut-short files are cut from the
corpus. The refused files and their exact messages are listed in `tests/unit/broken_pdfs.py`.
The file here is our own work, made for these tests, CC0-1.0.

| File | What it is | Made with |
|---|---|---|
| `broken/password-protected.pdf` | A blank 200 × 200 pt page, encrypted (AES-256, user password `sci2audio`); extraction must refuse it with a clear message (Issue #23, testing issue #5) | pikepdf, once |

pikepdf (MPL-2.0) is not a dependency; it was only used to make this file. The metadata file
(`metadata.pdf`, made with pikepdf by #23) was removed by #5: it held a blank page, which is now
refused (D-393), so its test writes the same Info dictionary and `/Lang` with `raw_pdf`.

EPUBs for tests are never stored here: every made-up and broken EPUB (password, DRM, missing
container, zip bombs, entity declarations, ...) is built inside the tests by
`tests/unit/epub_maker.py` (#73, D-316). The one real EPUB is the corpus file
`tests/corpus/epub/wells-the-time-machine.epub`.

Markdown and text files for tests are never stored here either: the made-up and broken ones
(empty, only white space, NUL bytes, a PDF or zip named `.txt`, every byte order mark,
Windows-1252, nesting past the limit, CommonMark's pathological inputs) are built inside the
tests (#74, D-347, D-348). The two real samples are the own corpus files
`tests/corpus/markdown/sci2audio-sample-note.md` and `tests/corpus/text/sci2audio-sample-plain.txt`.

## Kokoro's symbol table

`kokoro-vocab.json` is the `vocab` table of Kokoro-82M's `config.json` (revision
`f3ff3571791e39611d31c381e3a41a3af07b4987`, [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M),
Apache-2.0; the German model's `config.json` has the same bytes). The German voice tests
check espeak-ng's German phonemes against it without the 327 MB model (#211).
