# PR #620, round 1: what the fix commit does

Fix commit **4e24dea** (tests, one code comment, CHANGELOG). No change to code behaviour. `ci:full` label set again for the final round.

| Item | Fixed by | Mutants it kills (hand run on 4e24dea, tests/unit/test_layout.py) |
|---|---|---|
| T1 | `test_a_small_header_apart_from_its_rows_on_three_of_ten_pages_is_text`: 10 pages, header 12 pt above its rows on pages 2 to 4 | m04, mutmut `_small_heads_64` |
| T2 | `test_pages_near_counts_the_pages_as_repeated_does_for_each_height`: Hypothesis, pages 1–6, heights on an integer grid 0–20, query heights in any order, drift from {0, 0.5, 5}; three `@example`s (two places of one page and one leaves, heights out of order, exactly `drift` apart) | `_pages_near_16` `_18` `_24` `_26` `_36`, m14, m15 |
| T3 | `test_small_heads_a_little_higher_or_lower_on_each_page_are_running_heads`: 7 pages, author/title alternating at y 40 + 2·(n mod 3); and 2 of 2 pages at y 40 and 42 | `_small_heads_6`, m17 |
| T4 | `test_a_small_line_listed_before_the_small_head_of_its_page_does_not_hide_it`: a 9 pt "n = 12" mid-page, listed first | `_small_heads_41` (continue → break) |
| T5 | `test_an_edge_line_at_exactly_small_times_the_body_is_judged_as_body_size`: 9.5 pt on 2 of 2 pages is text, 9.4 pt is a head | m02, `_small_heads_15` |
| T6 | Both kept, each now decided alone: `test_a_captioned_figure_s_labels_count_neither_for_the_share_nor_for_the_fill` with helper `framed_in_a_column`. Page 1: a framed diagram in the left column under 20 lines of text, two short columns beside and under it hold 7 % of the page's text (39 % with the labels): one column. Page 2: table cells beside it hold over half the text but leave white, while the labels fill the left column: one column | m21 (page 1 only), m20 (page 2 only) |
| T7 (a) | `test_a_captioned_table_s_cells_still_count_as_columns_if_they_fill_them`: the diagram page under "Table 1: The results." counts its three columns (#238 takes figures only; a table's cells are judged by `_filled` as before) | m22 |
| T7 (b) | Stated, with a comment in `columns_per_page`: in positioned content only a caption's float takes lines. An uncaptioned figure is made of graphics alone: `graphics._groups` takes `item.line is None` only, `build._block` builds a FIGURE from `element.graphics`, the loose graphics in `build.units` are graphics, and `graphics._place`'s leftover block holds only parts of "join" blocks, which are those graphic blocks. The tagged path (`build_tagged`, whose svg FIGURE units do hold lines) is taken only when no item has a position, and there `_Layout.read` has no boxed line to count. So m23 stays equivalent. The uncaptioned test's docstring now says only "Without a caption no figure holds the labels, and their three columns count." | m23 equivalent (survives, as expected) |
| T7 (c) | `test_the_figures_whose_text_is_not_counted_are_found_with_the_settings_given`: with `caption_reach` 1 em the caption 10 pt under the frame names nothing: 3 columns; default: 1 | `columns_per_page_5`, `_7` |
| N1 | CHANGELOG: "Small lines at the top of a page, and small caption lines at the foot, are read unless they really are running heads (#156): …" | |

Hand run: 15 of the 16 listed mutants fail a test, and m23 survives as stated. Fast suite on 4e24dea: 7910 passed, 8 skipped, 6 xfailed; ruff, lint-imports and deptry are clean.

A note for the round 2 mutant re-run: when a hand mutant keeps the file's length (`mine` → `band`) and runs in the same second as the last write, Python can load the stale `__pycache__` bytecode and run the unmutated code. I hit this while probing T6. Run with `PYTHONDONTWRITEBYTECODE=1` and clear `src/sci2audio/layout/__pycache__` after each mutant (mutmut is not affected).
