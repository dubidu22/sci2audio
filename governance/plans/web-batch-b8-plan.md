# Web batch B8: figures in the player (#293), preview limit comment (#534), markers axe test (#541)

Status: **WAITING FOR APPROVAL** (#293 is critical).
Author: web-lane implementation thread "Show figures in the player", 18 Nov 2026 ~23:55Z. Base: main 5a605e5.
Read: `plans/next-batches-2026-11-18.md` (B8 row, AC-293.1 to AC-293.5, §4 on #541), `plans/per-project-folders-plan.md`
(L1 to L3, R1 to R5), CLAUDE.md, rules 1.4.7, decisions D-742 to D-769, KB D-295, D-310, D-313, D-340, D-353, D-356,
D-546, D-581, D-608, issues #293, #534, #541 with comments, and the code named below on main 5a605e5.
Earlier PRs in this batch that built on a model this PR changes: none (D-718).

## 0. What exists already (no new dependency, no new mechanism)

- `document.json` (in the project data folder) holds the whole `Content`: every placeholder block's `parts` name its
  lines, pictures and drawings; on a PDF page each has a `box` in points on the page as shown (crop box origin, /Rotate
  applied, #458 #537); an EPUB/Markdown `Picture` has `alt` and `ref` (D-310, D-340).
- `extraction/pdf.py` already renders a page in the isolated child (`extract_pdf_cover`: pypdfium2, `isolate.run`,
  1 GB, 60 s a step, at most 2 readers, PNG written by the standard-library `png()` writer, D-313, D-581).
- `extraction/epub.py` already reads one image from the zip with limits (`extract_epub_cover`: `_Book.read(path,
  limit=20 MB)`, JPEG/PNG sniffed from the bytes, `small_enough` pixel limits, D-579).
- The project data folder `<data>/sci2audio/projects/<id>/` is removed whole by `DocumentStore.remove` (D-355, #569), so
  a cache inside it goes with the project; `store.unchanged(id)` holds off a removal while a write happens (D-356).

## 1. Design (#293)

**D1 Which blocks.** A placeholder block the page shows as a notice box (`BlockView.notice` set) of kind FIGURE, TABLE or
FORMULA (CODE keeps D-546). PDF: one image per page its parts lie on, at most 4 a block. EPUB: one image per `Picture`
part with a `ref`, at most 4; a table or formula there keeps today's text view (AC-293.2). Markdown and plain text: no
image (Q1). A command-line job opened with `sci2audio listen` (#154): no image (Q2).

**D2 Address.** `GET /api/v1/documents/{id}/figures/{block}/{n}`, two integers, no path or name in the address. The server
takes everything else from the project's own records: `document.json` (its `content.source.sha256[:16]` must equal the id,
as D-295 asks of `audio.json`), the block and its n-th image, and the source copy `source/<name>` from the store
(`StoredDocument.source`), whose own hash is the id by construction (D-198). 404 for any id, block or n the rules above do
not give. Answers `image/png` (PDF crop) or the picture's sniffed type (`image/jpeg`, `image/png`), with
`X-Content-Type-Options: nosniff` and `Cache-Control: private, no-cache`. Only `state.listening(id)` documents that are not
`outside`.

**D3 PDF crop (AC-293.1).** New `extract_pdf_regions(path, regions) -> list[bytes | None]` in `extraction/pdf.py`, run in
the isolated child with `extract_pdf`'s limits (same `_isolated`, `_READERS`, `MAX_MEMORY`, `STEP_SECONDS`; one step per
region, reported as "region N of M"). A region is (page number, box in points as shown, scale). The child renders the page
as shown and keeps the box: the union of the block's part boxes on that page, plus a 4 pt margin, clipped to the page.
Scale: 3 pixels a point (216 dpi), lowered so the longer side is at most 2,000 px and the area at most 4 megapixels. A
region off the page, empty, or a page that fails gives None (the image is then not served: 404, the notice stays). The
function is general (a whole page is a region too), so #155 can reuse it.

**D4 EPUB picture (AC-293.2).** New `extract_epub_picture(path, ref) -> Cover | None` in `extraction/epub.py`: `ref` must be
a clean zip path (`markup.clean_path`: no `..`, no absolute path, no scheme) that names a member of the zip; read with
`_Book.read(limit=MAX_COVER)` (zip-bomb safe, 20 MB); kept only if the bytes are JPEG or PNG and `small_enough` (D-579).
The ref comes from `document.json`, never from the request. (Returning `Cover` reuses its checked JPEG/PNG type; the
docstring says it serves both. GIF, WebP and SVG are not shown: Q3.) Not cached: one zip read per request.

**D5 Cache (AC-293.5).** `<project data folder>/figures/<key>.png`, key = first 32 hex of the SHA-256 of a canonical JSON
of {format version, document id, page, box, scale}, so a new analysis that moves a box never meets an old crop. Read only
if `lstat` says a regular file (no link), at most 8 MB, and it starts with the PNG signature; anything else is rendered
again. Written atomically (temp name in `figures/`, then `os.replace`) **inside `store.unchanged(id)`** and only when the
project folder still exists (`figures/` made with `mkdir(exist_ok=True)`, never `parents=True`), so a removal is never
undone by a late write and never meets a half file. Size cap 64 MB a project: after a write, the oldest crops (by mtime)
go until the folder is under the cap. A failed write (disk full, read-only) still serves the image, uncached. Removing the
project deletes `figures/` with the rest (test), and its bytes count in "freed" as today.

**D6 One child per batch.** Crops are rendered on the first request that misses the cache: that request renders the crops
of the asked block and of the next blocks in reading order that are not cached, up to 12 regions, in one child, under a
per-document lock kept in `ServerState` (no global state); a request waiting on that lock then finds its crop cached. So a
page of lazy images costs one child start per 12 figures, not one per image.

**D7 Page (AC-293.3, AC-293.4).** `BlockView` gets `figures: tuple[FigureView, ...]` (n, alt, width, height in CSS px).
`listen.html` draws, inside the notice box, after the notice line and before the folded "found in the file" text:
`<img class="figure" src="…/figures/{block}/{n}" alt="…" width height loading="lazy" decoding="async">`. Alt text: the
picture's `alt`, else the caption block's text (`describes` points at this block), else the notice (AC-293.3, as
approved; where it falls back to the notice a screen reader hears the notice twice, which the AC accepts). Width and
height: PDF crops from the box at 96/72 px a point, shown no wider than the text (`max-width: 100%; height: auto`); EPUB
pictures get no size (unknown until read). The image is not focusable and adds no Tab stop; a click on it acts like a
click on the notice box (plays from there), exactly as the code view (D-546). Light and dark: the crop keeps its white
paper on a thin `--rule` border, never inverted. The CSP already allows `img-src 'self'`.

**D8 Failure is quiet.** A missing image (404, a render the child stopped) shows the browser's empty image with its alt
text; `player.js` hides an image whose `error` event fires, so only the notice and its text stay. Nothing fails the page.

## 2. #534 (rides along in PR 1, one line)

Keep `PREVIEW_LIMIT = 300` (a voice preview is a short sample, and the form, page and browser test already say 300) and
reword the comment so it no longer claims to be the cutter's limit. No value change, so no new test (AC-534 second bullet
does not apply).

## 3. #541

No code: the isolation run on main 1797ceb was 80/80 green (40 WebKit Ubuntu, 40 WebKit macOS), the first criterion is met,
and the others apply only if it fails again. I watch the markers axe test in this PR's Chromium, Firefox and WebKit legs; if
it fails, it is fixed or quarantined the same day per its criteria. I recommend closing #541 as met once this PR's legs are
green (coordinator's call).

## 4. PR split and files

**One PR, critical (risk:high, lane:web; touches extraction, D-756 cross-lane):**
`web: the player shows figures, tables and formulas where their notice is read (#293)`, also closes #534.

| file | change | owner check |
|---|---|---|
| `src/sci2audio/extraction/pdf.py` | `extract_pdf_regions` + child function | extraction lane: B1 is done, no thread open |
| `src/sci2audio/extraction/epub.py` | `extract_epub_picture` | same |
| `src/sci2audio/extraction/__init__.py` | export both | same |
| `src/sci2audio/web/figures.py` | NEW: regions, alt text, cache, batch lock | web |
| `src/sci2audio/web/player.py` | `FigureView`, `BlockView.figures`, built in `_block_view` | web, not B7 |
| `src/sci2audio/web/api.py` | the route | web, not B7 |
| `src/sci2audio/web/state.py` | `ServerState.figures` (the per-document locks) | web, not B7 |
| `src/sci2audio/web/pages.py` | no figures for an outside job | web, not B7 |
| `src/sci2audio/web/templates/listen.html` | the `<img>` | web, not B7 |
| `src/sci2audio/web/static/app.css` | `.notice img.figure` | web, not B7 |
| `src/sci2audio/web/static/player.js` | hide a figure whose image fails | web, not B7 |
| `src/sci2audio/web/models.py` | #534 comment | web, not B7 |
| `CHANGELOG.md` | one Unreleased line (D-768) | docs |
| tests | below | |

**Not touched:** `web/documents.py`, `app/**`, `output/**`, `web/strings/*.toml` (no new string: the alt text is the
file's own words), `core/**` (no dataclass change), goldens and regression cases (no extraction or reading change).
If a B7 change in `web/strings` or `documents.py` merges first, I merge main; no shared file is expected.

## 5. Tests (first-of-kind rules: a route in `web/`, file writing)

- `tests/unit/test_extraction_pdf_regions.py` (new): a generated PDF with a black rectangle at a known place: the crop's
  pixel size is the box times the scale and its middle is black; the same on a page turned 90 and 270 degrees (#537) and
  on a crop box that does not start at the origin (#458, #543); scale lowered at 2,000 px and 4 MP; region off the page →
  None; damaged PDF → all None; the child limit is the one of `extract_pdf` (stopped child → None, monkeypatched step
  limit).
- `tests/unit/test_extraction_epub.py` (added cases): picture read by ref; refused: `../x.png`, `/x.png`, `http://…`, a
  ref that is not a member, a member over the limit (declared and actually unpacked: a small deflate bomb), bytes that
  are not JPEG/PNG (SVG with a script, GIF), a PNG header of 20,000 × 20,000 px.
- `tests/unit/test_web_figures.py` (new): which blocks get images (each kind, each format, outside job none, code none);
  union, margin, clip, page split, cap 4; alt text order; cache hit, miss, a link in place of a cache file is not read,
  a truncated or non-PNG cache file is rendered again, cap removes the oldest, a failed write still serves, a project
  removed during the render is not created again (the write happens under `unchanged`, folder never re-made), a key
  changes when the box changes; batch of 12 in one child (render function counted).
- `tests/unit/test_web_api_figures.py` (new): 200 `image/png` for a PDF figure and a table, `image/jpeg` for an EPUB
  picture; `nosniff`; 404 for unknown id, `cli-` id, text block, code block, out-of-range block and n, negative n, a
  `document.json` naming another id, a Markdown document; a removed project answers 404 and leaves no folder; removal
  deletes `figures/` (through `DocumentStore.remove`). Schemathesis picks the route up from the schema.
- `tests/browser/test_player_figures.py` (new): the listen page of a generated PDF with a figure shows the image inside its
  notice box with its alt text, the image loads (`naturalWidth > 0`); Tab order unchanged (same stops as without
  figures); a click on the image plays from the notice; a failing image is hidden; `check_axe` light, dark and German;
  no request leaves the server (the conftest guard).
- Mutation (final round, scoped): the id check, `clean_path`, member check, the lstat/link check, `unchanged` write,
  `parents=False`, cap pruning, the 4-per-block cap; each has its own failing test (listed in the PR body).

## 6. Size and order

About 450 lines of code and 700 of tests. Order: extraction functions + tests, `web/figures.py` + unit tests, route,
page, browser test, CHANGELOG. Linux CI green, then `ci:full` green (three systems, Firefox/WebKit legs reported), label
removed, branch frozen, PR number and head to the coordinator; ledger line.

## 7. Questions (recommendation first)

- **Q1 Markdown pictures (deviation from AC-293.2's "or Markdown").** sci2audio keeps a copy of the `.md` file only; the
  pictures it names stay beside the original, whose folder the server never learns (an upload carries no path), and a
  `data:` picture has no `ref` (D-340). **Recommend:** no image for Markdown in this PR; the notice and its folded text
  stay; a follow-up issue (v1.2.x) to keep the pictures a Markdown file names when it is opened from a path (CLI) or
  dropped together with them. Alternative: keep `data:` pictures in `ref` (extraction + golden change, out of scope).
- **Q2 Command-line jobs (`sci2audio listen`).** Their folders are read-only to the server (#154), so no cache can be
  written, and the CLI working folder holds no source copy. **Recommend:** no images there; follow-up issue.
- **Q3 EPUB GIF, WebP, SVG.** **Recommend:** JPEG and PNG only (the checked `Cover` types, nearly all EPUB figures); SVG
  never (served from our origin it could run script if opened on its own). Follow-up issue for GIF and WebP with header
  size checks.
- **Q4 Cap.** 64 MB a project, 2,000 px and 4 MP a crop, 4 images a block, 12 regions a child. Recommend as written.
