# PR #148 round 1: what was fixed

New head **1e17652**. It holds fix commit c2b1771 plus a merge of main (a0bb69f, with #139); there was no force-push. Every item from round 1 is fixed. Nothing is deferred, so no issue was opened.

## Must fix

- **M1, malformed URL.** `_resolve` now catches the `ValueError` from `urlsplit` and returns `(None, "")`, the same as for a link that leaves the book. The effects:
  - A manifest item with such an href is skipped.
  - `extract_epub_cover` gives None.
  - A chapter `<a>` is recorded as `href:<as stored>`.
  - An `<img>` keeps its stored source as `ref`.

  Tests:
  - `test_an_address_that_cannot_be_parsed_is_kept_as_stored` covers the manifest item, the link and the picture.
  - `test_a_cover_whose_address_cannot_be_parsed_gives_none`.
  - The markup alphabet now includes `<a href="http://[x">`, `<img src="http://[y"/>` and `<a href="c1.xhtml#x">`.
  - Two new Hypothesis properties check that `extract_epub_cover` never raises: one on any bytes, one on a package file with damage inserted (including a cover href of `http://[x`). The damaged-package property fails on the old code.
- **M2, non-text codec.** `_decode` now falls back to UTF-8 with `errors="replace"` when the declared codec raises `LookupError` or `ValueError` while decoding (`UnicodeError` is a `ValueError`). Test: `test_a_declared_codec_that_is_not_for_text_reads_as_utf_8`, for hex, base64, rot13, zlib, uu, idna and punycode. All seven failed before the fix.
- **M3, damaged nav.** `_NavReader.handle_endtag` sets `labelled[-1]` only while an `<li>` is open. Tests:
  - `test_a_damaged_navigation_document_never_fails_the_file`, with three cases. Your `<li><a>A</li></a>` is one of them, and two of the cases failed before the fix.
  - `test_any_navigation_markup_gives_content`, a Hypothesis test that feeds the random-markup strategy into `nav_entries`.
- **M4, unbounded tags.** A new constant, `MAX_TAGS = 200`, caps the tags one element carries, its ancestors' tags included. An element's own tags are cut to the room that is left, and once an element is full its descendants share the same tuple. 200 keeps `MAX_TAGGED = 100` meaningful, since each nested element usually adds one or two tags.

  `_resolve_links` used to copy every run's tags. It now rebuilds only the runs that hold a link placeholder.

  Test: `test_many_tokens_on_many_elements_stay_small_and_fast`. It uses your case: 100,000 `epub:type` tokens plus 100,000 `role` tokens on a `div` with 2,000 `span`s. It asserts a run time under 10 s, a `tracemalloc` peak under 100 MB, and exactly 200 tags per run. It now runs in about 0.7 s, with tracemalloc on.

  This is a new limit next to the D-315 limits. The coordinator may want a line under D-315 for it.

## Should fix: the mutants

I ran each of these as a mutant against the three test files. Each one is now killed.

1. `_fold` stripping only ASCII spaces. Test: `test_no_break_spaces_at_the_ends_are_kept`, which covers a line and `dc:title`.
2. `MAX_TAGGED` 100 → 101. The deep-nesting test now asserts the literal `("div",) * 100`.
3. The line feed right after `<pre>`. This mutant is **equivalent**, so I removed the rule and `after_pre_start`. A leading `\n` only produces an empty first piece, and `flush` never records an empty line, so the output is the same either way. The golden file and all tests are unchanged.
4. UTF-16/32 declared without a byte-order mark. Test: `test_utf_16_or_32_declared_without_a_byte_order_mark_reads_as_utf_8`, for utf-16, UTF-32 and utf-16-le.
5. The NCX level cap. Test: `test_a_deeply_nested_ncx_stops_at_level_fifteen` uses 2,000 levels. With the mutant it fails with `RecursionError`.
6. The JPEG third signature byte. `\xff\xd8\x00…` must not count as a JPEG; the test also checks a damaged eighth byte of the PNG signature.
7. `_clean` refusing `../`. Test: `test_no_path_above_the_zip_root_is_ever_read`. The zip stores a member `../outside.xhtml`, and the test checks two things:
   - a manifest item at `../../outside.xhtml` is never read (in the spine, it gives "names 'out', which it does not list");
   - an `<img src="../../secret.png">` keeps its source as stored.
8. Anchors after the last item. The links test now links to `c2.xhtml#end` and to a trailing `<span id="last">`, and both must give `link:p2`.
9. to 11. `test_the_limits_are_the_decided_ones` asserts the decided values of `MAX_MEMBER`, `MAX_TOTAL`, `MAX_SPINE`, `MAX_COVER`, `MAX_TAGGED`, `MAX_TAGS` and `MAX_OUTLINE_LEVEL`.

## Checks on 1e17652

- `ruff check`, `ruff format --check` and `deptry src` are clean.
- `lint-imports`: 3 contracts kept.
- Fast suite: 2306 passed, 19 subtests, 55 snapshots. The golden file is unchanged.
- Nightly Hypothesis profile on the three test files: 117 passed.
