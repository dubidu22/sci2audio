# Answer to the review of PR #582, round 2

Fix commit: **bbbf45c**, one test-only commit on top of 065d22c (your merge of main). There is no change under `src/`. The branch is frozen after it.

For each test I removed the guard it pins locally, ran the test, saw it fail, and restored the guard.

| finding | test | the mutant it kills |
|---|---|---|
| R2-1 a zip member literally named outside the book | `tests/unit/test_extraction_figures.py::test_a_member_named_outside_the_book_is_never_read`, with two cases: `../images/fig1.png` and `/images/fig1.png`. `make_epub(extra_files=...)` writes each member under that exact name, and zipfile keeps both, including the leading `/`. The test asserts the name is in `namelist()` before it asserts `extract_epub_picture` gives None. | Dropping `clean_path(ref) != ref` from `extract_epub_picture` makes both cases fail. |
| R2-2 the link check where the system has no O_NOFOLLOW | `tests/unit/test_web_figures.py::test_a_link_is_not_read_where_the_system_has_no_o_nofollow` removes `os.O_NOFOLLOW` with monkeypatch, puts a link `figures/a.png` pointing to a PNG outside, and asserts `read_cached` gives None. | Dropping the `S_ISREG` check in `read_cached` makes it fail. |
| R2-3 the batch pinned at 12 | `test_one_child_renders_at_most_twelve_crops` builds a PDF with 14 figures on 14 pages and asks for the first one with nothing kept. It asserts there is exactly one `extract_pdf_regions` call, with exactly 12 regions, which are the first 12 in reading order. | Changing `>= BATCH - 1` to `>= BATCH` makes it fail. |
| R2-4 an EPUB table holding a picture | `test_an_epub_table_holding_a_picture_shows_none` checks first that the test can't pass vacuously. It takes `figure_epub()`'s first figure block (it shows its picture as a figure) and turns it into a TABLE. It then asserts the block is a TABLE placeholder whose parts include the picture `p1-i1`, and that `images()` gives `[]`. On the route, the figure is served (200), then `document.json` gets that block's kind changed to `table`, and the same address gives 404. I first tried a real `<table><td><img/></td></table>`, but layout keeps the cell's `<img>` out of the table's parts (they were only the text lines), so that markup could never test the guard. | Dropping `and block.kind is not BlockKind.TABLE` in `Catalog.images` makes it fail. |
| R2-5 the player.js early hide | `tests/browser/test_player_figures.py::test_an_image_that_failed_before_the_script_ran_is_hidden_too` holds `**/static/player.js`, answers `**/figures/**` with 404, and reloads with `wait_until="commit"`. It waits until the image is `complete` with `naturalWidth === 0`, asserts it is not yet hidden, then lets player.js through. After `at_rest` the figure is hidden and the notice text stays. | Deleting `if (figure.complete && figure.naturalWidth === 0) hide();` makes it fail (Chromium). |

Local runs on bbbf45c:
- ruff check, ruff format --check, lint-imports (3 contracts kept) and deptry are clean.
- `tests/unit/test_web_figures.py` and `test_extraction_figures.py`: 85 passed.
- `tests/browser/test_player_figures.py`: 6 passed in Chromium.
- Fast suite: 7,571 passed, 8 skipped, 1 failed. The failure was `tests/unit/test_web_pdf_progress.py::test_an_audio_job_reports_each_page_it_reads` under `-n auto`. This commit doesn't touch that file, and it passed 3 of 3 runs on its own.

On your note that two mutation claims in the PR body did not hold (clean_path and S_ISREG): R2-1 and R2-2 now pin both, as the table shows.

CI on bbbf45c: run [44437266438](https://github.com/dubidu22/sci2audio/actions/runs/44437266438) is green in every job: Linux tests, Chromium 1/2 and 2/2, Firefox 1/2 and 2/2, WebKit 1/2 and 2/2 (all six browser legs), lint and layers, licences, security, web paths and CI passed. ZAP baseline is green too. No re-runs.
