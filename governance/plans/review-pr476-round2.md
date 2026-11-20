# Review PR #476, round 2 (sentence-boundary batch PR 2, #454)

Head reviewed: 8c22c49, one fix commit on edc2df6. Main is 1c45cab, which is the merge base, so the branch is up to date. Round 1: plans/review-pr476-round1.md.

**Verdict: not approvable yet, one should-fix (tests only).**

S1, S2 and S3 of round 1 are fixed, the corpus reading is now right, and every heavy check is green. But four guards of the new rules have no test that would fail without them. The final-round mutation run left them alive, and each has a concrete counterexample, so the fix is four tests with no source change. Round 3 is then expected to be approvable.

## Round 1 findings
- **S1, fixed.** In rows set flush right or centred, a change between italic and upright now ends the paragraph. A row counts as italic when most of its letters are italic.
  - Liu: the affiliation is one block and the date is its own block.
  - `test_liu_s_list…` is back to blocks 52 to 132 (133 blocks).
  - New test: `test_an_upright_line_under_centred_italic_lines_starts_a_paragraph`.
- **S2, fixed.** `_goes_on` now cancels only the short-line break. Indent and outdent still split unless `_aligned` finds a shape.
  - The poem test's third line is at the left.
  - New tests: the indented "pandas" paragraph and the outdented "van Dijk" entry each stay apart.
  - The plan's PR 2 wording is amended to match.
- **S3, fixed.** `_LETTERED_ITEM` (`^(?:[ivxl]{1,4}|[a-z])[.)]\s`) stops the join.
  - New test: `test_items_lettered_with_a_full_stop_stay_apart` ("i./ii./iii." and "a./b./c.").

## Heavy checks on 8c22c49
- **Corpus block diff against main** (`/home/user/probe/p476/dump.py`, all 13 corpus files). Only two places change:
  - nowak: the link `https://github.com/rycolab/` + `prefix-parsing` becomes one block (right: one link, now dropped whole instead of half read);
  - liu: the two italic affiliation lines become one block (right: one affiliation), and the upright date stays its own block.

  This is byte-identical to the variant I tried in round 1.
- **Probes** (synthetic, run on main and on the PR):

  | case | result on the PR |
  |---|---|
  | "i./ii./iii." items | stay apart |
  | indented lower-case paragraph | stays apart |
  | "van Dijk" entry | stays apart |
  | capitalised poem | stays apart |
  | "a)" items | stay apart (as on main) |
  | an unindented lower-case paragraph start with no extra white after an unpunctuated line | joins (the plan's accepted risk) |
  | code lines without a caption | join (note from round 1) |

- **Sentence gate:** 33 passed. The natural sets are unchanged: en P 0.9967 R 0.9900, de P 0.9874 R 0.9916.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, `-n 4`): 6709 passed, 2 skipped.
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`, `--hypothesis-seed` 2024 and 123456, on `test_layout.py`, `test_layout_paragraphs.py`, `test_layout_headings.py` and `test_layout_split.py`): 150 passed each.
- **Three systems:** I re-added `ci:full` (D-714). The run on 8c22c49 is green: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser, lint and layers, licences, security, and `CI passed`. The author's earlier run on this head was green too.
- **Mutation of the new rules:** `/home/user/probe/m476/run.py`.
  - Method: each mutant is applied to a copy of src and tests. The tests run are `test_layout.py`, `test_layout_paragraphs.py`, `test_layout_headings.py`, `test_layout_captions.py`, `test_layout_code.py`, `test_layout_footnotes.py`, `test_layout_formulas.py`, `test_layout_graphics.py`, `test_layout_corpus.py`, `test_textprep_rules_corpus.py` and `test_textprep_citations_links_corpus.py`. The baseline passes: 564 passed.
  - Result: of 32 mutants, 21 are killed and 11 survive.
  - The counterexamples are in `/home/user/probe/m476/test_gaps476.py`. Each passes on the head and fails on its mutant (`/home/user/probe/m476/gaps.py`).

| # | mutant | survives because | verdict |
|---|---|---|---|
| 24 | right edges at two places count as flush right | no test has rows that start at three places but end at two edges | **counterexample: an indented row in such rows must still split** |
| 25 | middles at two places count as centred | no test has such rows | **counterexample: the same with two middles** |
| 6 | italic = any italic run | no test has a centred upright row with one italic word | **counterexample: a centred affiliation line with an italic journal name must not break** |
| 20 | `_LETTERED_ITEM` without `\s` | no test has a line starting "e.g." or "i.e." (the docstring promises they go on) | **counterexample: a short line followed by "e.g. …" / "i.e. …" goes on** |
| 21 | window of 2 rows allowed | equivalent: two rows give at most two left places, so the next check returns None | equivalent |
| 31 | `_places` with `>=` | only differs at an exact float tie of edge distance and reach | equivalent in practice |
| 4 | italic at exactly half | a tie between equal italic and upright letter counts; neither reading is more right | note, no test asked |
| 19 | `[.)]` → `[.]` | "a)"/"i)" items are split again by `lists.py` | note |
| 28 | the row before is not checked for standing right above | only reachable across a column or page break | note |
| 29 | `_aligned` does not first check the two rows stand stacked | same: only reachable across a column or page break | note |
| 30 | `reach` by the smallest size | rows in one window differ in size by under 8% (a larger change ends the paragraph first) | note |

## Fix list

### Should-fix

**S1. Add four tests that pin the guards, without changing any source.** Base them on `plans/review-pr476-round2-tests.py` (a copy of my probe file); rename them to match the file's style. All four pass on 8c22c49.
1. **Two right edges are no flush-right block.** Rows start at x0 = L, L+8, L+20, L but end at x1 = 450, 450, 400, 400, under three full body lines. The third row starts a paragraph. This kills mutant 24.
2. **Two middles are no centred block.** Rows at (L, 450), (L+10, 440), (L+30, 380), (L, 410). The last two rows are their own paragraph. This kills mutant 25.
3. **One italic word leaves a centred row upright.** Three centred rows, the second "for the *Journal* of Sound, Town", above the body, give one paragraph plus the body. This kills mutant 6.
4. **A short line goes on with "e.g." and "i.e.".** A full line, then "we read the papers aloud" ending at L+150, then "e.g. the ones on the shelf." (and the "i.e." variant) ending at L+300. They give one paragraph. This kills mutant 20.

## Round 3
- One fix commit with only `tests/unit/test_layout_paragraphs.py` changed.
- I check that the four tests kill mutants 6, 20, 24 and 25 and that the source diff is unchanged.
- I rerun the paragraph tests and read the three-system run on the new head (`ci:full` stays on the PR, so the push runs all three systems).
- If main has not moved, I then squash-merge pinned to that head on the coordinator's standing go.
