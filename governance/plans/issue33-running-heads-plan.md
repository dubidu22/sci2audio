# Issue #33: body-size repeated lines taken for running heads (plan)

Thread: "Fix running heads taken from body lines". Lane: layout, after #36 (PR #128, merged as
5bf1264), before #58. Critical by the coordinator's call (furniture rules and golden files), so
no code before approval. Base: main at 5bf1264; fast suite green there (2139 passed, 54
snapshots).

## 1. Today's rule

`layout/furniture.py` marks a line RUNNING_HEAD when all of these hold:

- it stands in the top or bottom edge band (`edge_band` 0.1 of the page height);
- it is set no larger than `head_size` (1.05) times the body size;
- it is "loose": set smaller than `small` (0.95) times the body size, **or** apart from the
  body by at least `apart` (1 em) of white;
- its *shape* (text casefolded, spaces removed, every number turned into `#`) stands at the
  same height (± `head_drift` 0.5 em) on at least `repeat_pages` (2) pages.

A body-size line passes on "apart" alone, so "Algorithm 1" and "Algorithm 2" at the top of two
pages (same shape `algorithm#`) with 10 pt of white below both become furniture, and so does a
table header repeated at the top of two pages. Both then drop out of the listening script.

## 2. What the corpus shows (measured on main after #36)

I listed every line in the edge bands of the 7 corpus papers (193 lines), with its size against
the body, whether it is apart, on how many pages its shape repeats, and its role today.

- **Every running head in the corpus is set smaller than the body**: the two JOSS footers
  (Waskom, Biggs), 0.80 of the body size, 16 lines on 8 pages. They are also the only
  `running-head` items in the truth files. The ACL and arXiv papers print no running heads.
- **No body-size line in the corpus is a running head**, and none is taken for one today. The
  only body-size-or-larger edge lines that are apart and not page numbers are Liu's title (1.20
  of the body, above `head_size`, so never a candidate).
- Page numbers are their own lines in every corpus file (PDFium splits them off the head by the
  gap), so a head's text does not change from page to page.

So the corpus cannot choose the new thresholds (there is nothing on either side of them), but
it does prove the change cannot touch it: **the golden files and truth tests should come out
unchanged**. Section 8 of the #36 plan asked #33 to rebuild its golden after #36 and to match
repeated text as extraction now records it; main already has #128's rebuilt goldens, I will
rebuild them again on my branch and explain any diff (I expect none).

The thresholds are therefore chosen from how running heads are set (LaTeX `article`/`book`
headings style, `fancyhdr`, journal classes) and pinned with made-up pages in unit tests.

## 3. Proposal

Two tiers, by size.

**Tier 1, set smaller than the body** (`< small` × body): unchanged. Shape match on
`repeat_pages` pages, as today. All corpus running heads are here.

**Tier 2, body size** (from `small` to `head_size` × body) **and apart** (as today): a running
head only with stronger evidence, both of:

- **(a) Exact text.** The line's text, with whitespace removed and casefolded but numbers kept,
  stands at the same height (± `head_drift`) in the same band on at least `repeat_pages` pages.
  "Algorithm 1" and "Algorithm 2" no longer match. Removing all whitespace means the match does
  not depend on a space that extraction keeps on one page and not on another (#36 note).
- **(b) Covers most of the document.** Counting every tier-2 line that passed (a) in that band
  at that height (± `head_drift`), whatever its text, they stand on at least `head_pages` (3)
  pages **and** on at least `head_share` (0.5) of the document's pages. Pooling the texts
  makes alternating heads (author on even pages, title on odd pages) and per-chapter heads in
  a book count together, as one running-head position; a table header repeated on two pages
  of a ten-page paper does not reach it.

Two new settings in `LayoutSettings`, with comments like the others:

```python
head_pages: int = 3      # a body-size running head stands on at least this many pages ...
head_share: float = 0.5  # ... and on at least this share of the document's pages
```

A rule (drawn line) between the line and the body is **not** used as evidence (question 4).

### Residual cases (written into the PR and the code comment)

- A table header repeated word for word at the top of 3 or more pages that are at least half
  the document, with 1 em of white under it (for example 3 pages of a 4-page paper), still
  becomes a running head. Rare: a continued table header usually sits close to its first row.
- A document of fewer than 3 pages (or with a body-size head on fewer than 3 pages) keeps its
  body-size heads as text, so the listener hears them. Nothing is lost (faithful text, D-57).
- A body-size head that holds its own page number in the same line ("4 · Chapter 1") no longer
  matches exactly and stays text. In the corpus PDFium always splits the page number off; a
  smaller head still matches by shape.

## 4. Code shape

`layout/furniture.py` only (about 50 lines changed), plus `layout/settings.py` (two fields).
No change to core, to any layer contract, or to other layout modules.

- Measure the pages first (`_Page` objects, which already compute `apart`), then collect the
  head candidates from them, so tier 2 can use `apart`.
- `_running_heads` keeps the tier-1 table (shape) and adds a tier-2 table keyed by
  (band, exact text); a new `_body_heads(...)` returns the set of tier-2 line ids that pass
  (a) and (b).
- `_Page.furniture` asks tier 1 or tier 2 by the line's size. The page-number and footer rules
  are not touched.
- Module docstring and the `LayoutSettings` comments say what each tier needs.

## 5. Tests (written first, failing on main where they should)

Unit tests in `tests/unit/test_layout.py` with the existing page helpers:

1. "Algorithm 1" / "Algorithm 2" at the top of two pages of a 6-page document, body size, 10 pt
   of white below: both stay text (fails on main).
2. A table header ("Model Accuracy F1"), body size, repeated word for word at the top of 2 pages
   of a 6-page document with 1.2 em of white and no rule below: stays text (fails on main).
3. Body-size alternating heads (author on even pages, title on odd pages from page 2) on a
   7-page document: all furniture with role running-head (pooled count 6 of 7).
4. A body-size head on both pages of a 2-page document stays text (`head_pages`), while the
   same head set at 0.8 of the body is a running head (tier 1 unchanged).
5. The existing tests stay as they are: `test_running_heads_and_page_numbers_...` (body-size
   head on 3 of 3 pages, still furniture) and `test_chapter_headings_and_a_continued_table_...`.
6. Threshold edges: a body-size head on exactly `head_share` of the pages is furniture, one page
   fewer is not.

Hypothesis: the existing "layout never fails and keeps every line" property covers the new code;
I add one property: a body-size edge line whose text differs on every page is never a running
head, whatever its height and white.

Corpus: truth tests (furniture in both directions, roles) and golden files run unchanged.
Before the PR: fast suite, nightly Hypothesis profile on `tests/unit/test_layout*.py`, layer
check, ruff, deptry; a threshold sweep of `head_pages`/`head_share` on the corpus (no change
expected anywhere) and a mutation check (remove (a), then (b): a test must fail each time).

## 6. Questions (numbered, with my recommendation)

1. **Evidence for a body-size running head.** Options: (A) exact text alone; (B) exact text
   plus coverage of most of the document, pooled over texts at one height; (C) a rule between
   the line and the body; (D) coverage alone, by shape. **Recommend B.** A alone still takes the
   repeated table header of the issue; C is what booktabs prints under every table header
   (`\midrule`), so it would take continued table headers; D still takes "Algorithm 1/2" on a
   short paper.
2. **What "exact" means.** Options: the text as extraction records it, spaces included; or
   whitespace removed and casefolded, numbers kept. **Recommend the second**: after #36 spaces
   come only where printed, but a stray space must not split one head into two texts; case is
   folded as the tier-1 shape already does.
3. **Thresholds.** **Recommend `head_pages` = 3 and `head_share` = 0.5** of the document's pages
   (pages with a size, as `find_furniture` already counts), new `LayoutSettings` fields. Two
   pages is what a continued table or two algorithms give; half the pages is "most pages" of
   the issue with room for a title page and alternating heads.
4. **A rule below the line.** **Recommend not using it in v1.0** (see 1); the option stays open
   as a later setting, no issue needed unless a real file needs it.
5. **Smaller-than-body heads.** **Recommend keeping today's rule** (shape on 2 pages): all
   corpus heads are there, and a line set smaller than the body at the page edge is strong
   evidence already.
6. **Scope.** The per-page FOOTER rule (bottom 6 %, loose) and the page-number rules stay as
   they are; heads with their page number in the same line stay text when body-size. **Recommend
   no follow-up issue** for either: neither occurs in the corpus, and both fail safe (read, not
   dropped). Say so in the PR.

## 7. KB

After the code PR, a KB PR in `sci2audio-design/docs/kb` with the decisions the coordinator
assigns (one row per question, newest first, "Decided (Claude)", Colin-informed time from the
coordinator), linking Issue #33 and the code PR with plain links.

## 8. Size

About 50 lines of code, 150 lines of tests, the two settings and docstrings. One PR.

## 9. Decisions (coordinator, 13 Nov 2026 13:26 UTC, under D-80)

Approved as recommended, questions 1 to 6:

- **D-322** (q1): a body-size running head needs exact text plus coverage of most pages, pooled
  per height (option B).
- **D-323** (q2): "exact" means whitespace removed and casefolded, numbers kept.
- **D-324** (q3): `head_pages` = 3 and `head_share` = 0.5, new `LayoutSettings` fields.
- **D-325** (q4): a rule below the line is not evidence in v1.0; the option stays open as a later
  setting.
- **D-326** (q5): heads set smaller than the body keep today's rule (shape on `repeat_pages`).
- **D-327** (q6): footer and page-number rules unchanged; no follow-up issues; said in the PR.
- **D-328** (review round 1 of PR #149, F1; coordinator 13:45 UTC, Colin informed 13:45:04 UTC):
  lines set smaller than the body keep the tier-1 shape rule in v1.0; continued `\small` table
  headers and algorithm captions are tracked for v1.1 in Issue #156.
