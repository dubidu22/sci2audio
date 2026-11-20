# Review of PR #620, round 1 (#156, #238; layout B13 PR 1, critical)

Reviewer: B13 review thread, 19 Nov 2026. Pinned head **1134ed5**, base main b6355cc (unchanged since the PR opened). Verdict: **changes requested, tests only** (no code defect found). One fix commit, on this list only.

## What was checked

| Check | Result |
|---|---|
| CI on 1134ed5 | `CI passed` green; `tests (ubuntu/macos/windows-latest)` all success (ci:full run), browser Chromium 1/2 and 2/2, lint and layers, licences, security, CodeQL green |
| Plan claim "furniture identical line by line on all 8 papers" | **confirmed**: main vs PR, `find_furniture` dicts equal on all 8 papers, and every block (kind, text, parts, `describes`) equal on all 8 (script `plans/b13-review/dump.py`) |
| Columns | only `arxiv2017-maass-privacyscore` p3 changes, 3 → 1 (truth 1); the other 7 papers' counts unchanged. `NOT_YET_COLUMNS` empty, as #238's AC and plan 238.3 ask (note: D-793's line "maass p3 keeps NOT_YET_COLUMNS" contradicts the plan and the AC; the PR is right) |
| No golden moves | no snapshot, truth or regression file in the diff |
| Plan adherence | 156.1–156.4, 238.1–238.3 as planned. One narrowing, named in the PR body with its reason: the coverage / short-document rules apply to the top band only; the bottom band keeps the shape rule plus the new label guard (footers close under notes, review of #530 F1). Accepted |
| Probe: small table header apart from its rows on 3 of 10 pages (top) | text on the PR (correct), furniture with the `head_share` term removed: untested, see T1 (`plans/b13-review/probe1.py`) |
| Nightly property tests (nightly.yml, property only) on 1134ed5 | run 44476075598: success |
| Hand mutants, 25 (`plans/b13-review/mut.py`, run in the PR checkout on 1134ed5 with tests/unit/test_layout.py, test_layout_corpus.py, test_corpus_truth.py, test_layout_contents_labels.py, test_layout_tagged.py, test_layout_graphics.py, test_layout_code.py, test_textprep_furniture.py; the unmutated set passes, 468 tests) | 16 killed, 9 survived (below) |
| mutmut (mutation.yml run 44476061464, 3 runners, globs `x__small_heads*`, `x__pages_near*`, `x_reading_order*`, `x_columns_per_page*`, `x_starts_with_label*`, tests test_layout.py, test_layout_corpus.py, test_corpus_truth.py) | 241 killed, 2 timeout, 27 survived; analysed below |

## Fix list (one commit; tests unless stated)

**T1. The coverage rule's `head_share` term is untested.** Hand m04 (`most = settings.head_pages`) and mutmut `x__small_heads__mutmut_64` (`head_share / page_count`) survive. Add: a 10-page document, a small table header apart from its rows (at least 1 em of white) at the top of 3 pages is text (3 ≥ `head_pages` but < `head_share` × 10).

**T2. `_pages_near` has no test of its own.** Survivors: mutmut `x__pages_near__mutmut_16`, `_18` (heights not sorted), `_24` (`<= y + drift` → `<`), `_26` (`+= 1` → `= 1`), `_36` (`< y - drift` → `<=`); hand m14, m15. Add a Hypothesis property test: for random places (page numbers 1–6, several places per page, heights on an integer grid so places exactly `drift` apart occur) and random query heights in any order, `_pages_near(places, heights, drift)[k] == _repeated(places, heights[k], drift)` for every k, with drift drawn from {0, 0.5, 5}. This pins "the same answer as `_repeated`" and kills all six.

**T3. The height window of the small-head rules is untested.** mutmut `x__small_heads__mutmut_6` (`head_drift / size`) and hand m17 (short-document rule with drift 0) survive. Add: small heads whose height moves by 2 pt from page to page (10 pt body, `head_drift` 0.5 em = 5 pt) stay furniture, once through coverage (heads on most pages of a 7-page document, texts alternating) and once through the short-document rule (same text on 2 of 2 pages, apart).

**T4. Order of a page's lines.** mutmut `x__small_heads__mutmut_41` (the shape check's `continue` → `break`) survives: no test has a small line outside the bands, or one whose shape does not repeat, listed before a small head on the same page. Add: a page whose `lines` list a small line in the middle of the page (a small table cell) before its small running head; the head stays furniture.

**T5. The size boundary.** Hand m02 and mutmut `x__small_heads__mutmut_15` (`>= small × size` → `>`) survive. Add: a 2-page document whose edge line stands at exactly `small` × body (9.5 pt at 10 pt), apart, same text on both pages, is text (it is judged by the body-size rule, which needs `head_pages`), as the same line at 9.4 pt is furniture by the short-document rule.

**T6. #238: the band-level counting is tested only as a pair.** Hand m20 (`_filled(band, …)` instead of `_filled(mine, …)`) and m21 (`_text(band)` instead of `_text(mine)`) each survive alone; together they fail `test_text_inside_a_captioned_figure_is_not_counted_as_columns` and the PrivacyScore truth. Either add a test that fails with m20 alone and one that fails with m21 alone, or keep only the one the corpus needs, say in the PR body why the other is not needed, and make the `reading_order` docstring ("neither their text nor their fill counts") match what is left.

**T7. #238: the three conditions in `columns_per_page`.**
- (a) `block.kind is BlockKind.FIGURE` (hand m22 survives): captioned TABLE blocks hold lines on chi, hardt and arsiwalla, and leaving them uncounted changes nothing in the tests. Add a test where a captioned table's cells would count otherwise, or state in the PR body why a table's lines can never change the count (`_filled`), with the code reference.
- (b) `b.describes is not None` (hand m23, `named = list(doc.blocks)`, survives): no FIGURE block without a caption holds lines in the corpus, and the "without a caption" case in the new test never makes a FIGURE block of the labels at all, so it does not reach this condition. Add a case where an uncaptioned FIGURE block holds lines (graphics.py `_join` leftovers, line 574, if that can carry lines) and is still counted, or state in the PR body that layout never puts lines into an uncaptioned FIGURE, with the code reference, and reword the test's docstring so it claims only what it tests.
- (c) `build_document(content, settings)` (mutmut `x_columns_per_page__mutmut_5`, `_7`: settings → None) survives: add one call of `columns_per_page` with non-default settings whose answer depends on the settings reaching `build_document` (a setting that changes which lines the captioned figure takes).

**N1. CHANGELOG** (text, same commit): "Small lines at the top or bottom of a page are read unless they really are running heads" overstates the bottom, where only caption labels change. Suggested: "Small lines at the top of a page, and small caption lines at the foot, are read unless they really are running heads (#156): …" (rest unchanged).

## Survivors not on the list (equivalent or pre-existing)

- mutmut `x__small_heads__mutmut_11` (stamps **and** notes) and hand m01 (skip removed): `_Page.furniture` assigns stamps and skips notes before it reads `heads`, and neither stands in the top band (a side stamp spans the page; notes stand under a rule in the lower half), so they lend no pages. Equivalent.
- mutmut `x__small_heads__mutmut_28`, `_30` (`shapes.get(…, None)`): for a line in a band its own shape is always in `shapes`; for band "" the `not band` test short-circuits first. Equivalent.
- mutmut `x__small_heads__mutmut_69/72/73/94/97/98`, `x_columns_per_page__mutmut_35/38/39` (`zip(strict=…)`): both sides have the same length by construction. Equivalent.
- mutmut `x__pages_near__mutmut_12` (`[1] * len`): every entry is written. Equivalent. `_30`, `_44` time out (killed).
- mutmut `x_reading_order__mutmut_3`, `_45`, `_68`: lines or comparisons that were there before this PR (`wide` boundary, `across(…)`, the `column_text` boundary). Pre-existing, not this PR's.

## Noted, no change asked

- The short-document rule ignores the #458 page-number offset, so a 3-page document with small heads printing their page number on pages 2–3 now reads them aloud (main dropped them). This is the plan's stated trade (reading a head aloud loses nothing; dropping a "Step 1" line does), approved in D-793.
- #238's AC reads "a captioned figure (or a drawn frame of a figure)"; the PR takes the captioned case only, as plan 238.1 says. Within the AC.

Round 2 will re-run the 9 hand survivors and the 27 mutmut survivors on the fix commit, the three-system CI (ci:full) and the nightly property run, then merge on a green main if clean.
