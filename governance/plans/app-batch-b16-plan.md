# App batch B16 plan (#186 + #207), D-776

Thread "Fix report warnings and quotes", 19 Nov 2026. Base main 678fe3c. Branch `app/b16-picture-pages-and-quotes`. One PR, non-critical (no contract, core dataclass, golden or regression change; the report JSON gains an optional key only when there is something to say, as `unreadable` did in #577). Review Opus medium, at most 2 rounds. C3 kept: no change to `web/static/app.js`, `web/player.py`, `tests/unit/test_web_outside.py`, `web/api.py`; nothing in `layout/`.

## #186 Pages that hold only pictures

**Cause.** Extraction records a scanned page as a `Page` with pictures and no text lines; layout turns each picture into "A figure is skipped." and nothing anywhere says the page's text was never there. A wholly scanned PDF is already refused (D-393), so this is about partly scanned PDFs.

**Change.**
- `app/readability.py` (the module that already judges whether a PDF's pages can be read, #187): `picture_pages(content) -> tuple[int, ...]`, the PDF pages with at least one picture and no line with visible text (a line of white space only counts as no text). PDF only, as D-772 for `unreadable`: an EPUB "page" is a spine file, and a cover or a plate file holding one image is normal there, not a scan. Drawings (vector graphics) do not count: a scan is a picture. And `picture_warning(pages) -> str`: "Page 7 holds no text, only pictures (a scanned page?), so nothing on it is read." / "Pages 12–18 hold no text, only pictures (scanned pages?), so nothing on them is read." (ranges with `page_ranges`, en dash).
- `app/report.py`: `Report.picture_pages: tuple[int, ...] = ()`; `build_report` puts the warning right after the unreadable warning (before the language and encoding warnings), so it is in `report.md` (Problems section) and `report.json` `warnings`. `report_data` adds `"picture_pages": {"pages": [...], "ranges": "12–18"}` at the end, only when there is one, so every other report (the corpus golden files included) is byte for byte as before.
- `web/templates/document.html`: a `callout warn` with `id="picture-pages"` under the unreadable callout, text from `document.picture_pages.one/.other` in `web/strings/en.toml` and `de.toml` (German: "Seite 7 enthält keinen Text, nur Bilder (eingescannt?); darauf wird nichts gelesen." / "Die {n} Seiten {pages} enthalten keinen Text, nur Bilder (eingescannt?); darauf wird nichts gelesen."). The English warning also stays in the page's "Notes:" list, as the unreadable one does today.
- `cli.py`: `_guessed_encoding` (renamed `_document_warnings`) also prints `sci2audio: warning: <picture warning>` for `script` and `convert`.

**Tests.** `test_app_readability.py`: a text page + an image-only page names the image page; a blank page (no text, no picture) is not named; a white-space-only line counts as no text; an image page with invisible OCR text is not named; EPUB and text inputs never named; `picture_warning` one page / a range; a Hypothesis property over `contents()` (named pages are exactly those with pictures and no visible text, PDF only). `test_app_job.py`: `joined_pdf(plain, image_only_pdf(), blank, plain)` gives the warning naming page 2 only in `report.json`, `report.md` and the `picture_pages` key; a text-only PDF has no `picture_pages` key. `test_web_pages.py`: callout in English and German. `test_cli.py`: the warning on stderr. Corpus: checked on main, none of the 8 corpus papers has such a page (all 0); the corpus snapshots stay unchanged, which pins "the corpus papers get no warning".

## #207 Invisible characters in an edit's quote

**Cause.** `app.report.shown_original` (report.py:485) makes only "\n" visible ("↵"). A removed zero-width space quotes as "“” → left out", and a soft hyphen at a line end as "“↵”", the soft hyphen showing as nothing.

**Change.** `shown_original` also shows every format character (Unicode category Cf: soft hyphen, zero-width space, joiners, word joiner, byte order mark, bidirectional marks) as its code point in angle brackets, "⟨U+200B⟩", wherever it stands in the quote. Code points read the same in English and German, need no new string, and the brackets are not Markdown specials, so `_md` leaves them alone. It applies in running text too (rare: an edit whose span holds a soft hyphen, "Ft⟨U+00AD⟩t (1998)"), because there the character is just as invisible and the quote should show what the edit covers. The JSON `original` stays the raw text. The document page's check table calls the same function (pages.py:541), so it follows.

**Tests.** `test_app_report.py`: `shown_original` on "​", "­\n", "a­b", "﻿", existing "\n" cases unchanged; an end-to-end report with `UnicodeStep` on "ab​ text" and a soft hyphen at a line end pins "“⟨U+200B⟩” → left out" and "“⟨U+00AD⟩↵”" in `report.md`; `test_web_pages.py` pins the check table cell.

## CHANGELOG (Unreleased, D-768)

- Added: "Pages that hold only pictures are named (#186): when some pages of a PDF are scans without text, the report, the document page (in English or German) and the command line name them ("Pages 12–18 hold no text, only pictures (scanned pages?), so nothing on them is read."), instead of only saying a figure is skipped."
- Fixed: "An edit that removes an invisible character no longer quotes as empty (#207): the report and the document page show a zero-width space, soft hyphen or other invisible character as its code point, "⟨U+200B⟩"."

Files: `app/readability.py`, `app/report.py`, `cli.py`, `web/templates/document.html`, `web/strings/en.toml`, `web/strings/de.toml`, `CHANGELOG.md`, tests in `tests/unit/`. Size about 150 lines of code and tests.
