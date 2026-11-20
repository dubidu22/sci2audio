# Answer to the review of PR #558, round 1

Review: `plans/review-pr558-round1.md` (head c27ce9d). One test-only fix commit: **8f147ce** on `layout/contents-labels-529-535`. No code changed. S1 fixed in full; N1 and N2 noted, no action (as the review says).

## S1 (fixed): three behaviours of `_left_entries` had no test

All in `tests/unit/test_layout_contents_labels.py`. Each was run against its mutant (hand-applied to `furniture.py`); each mutant fails exactly the named test and no other test of the file.

| item | mutant | new test (fails on the mutant) |
|---|---|---|
| (a) two entries on one page | 32: `int(number) >= last` → `>` | `test_two_entries_on_one_page_are_both_entries`: entries for pages 4, 4, 9; title and every row are `contents`. |
| (b) a lone number row after the title | 21: `len(row) > 1` → `>= 1` | `test_a_lone_number_after_the_title_is_no_entry`: title, a row holding only "3", two rows at the entry indent, body: no furniture role at all. |
| (c) jitter and indent drift | 40: the indent follows the latest entry | `test_entries_whose_indent_drifts_away_from_the_first_end_the_contents`: entries for pages 3, 5, 7, 9 whose text indent creeps 8 pt per entry; the fourth stands 24 pt from the first (more than `contents_reach`, 20 pt at 10 pt type) but 8 pt from the third, so the contents end before it with the rule and run on with the mutant. |
| (c) jitter as printed | none (guard) | `test_jittered_numbers_and_indents_as_printed_are_still_entries`: the German page's measured x positions: numbers right-aligned ("4" and "9" at 58.9, "17" and "30" at 53.9, shifted to the fixture's left edge), entry texts at 87.4 to 88.6, a run-on row at 89.1: every row is `contents`, the body after it is text. |

One change from the wording of (c): a creep of about 1.5 pt per entry cannot put the fourth entry more than `contents_reach` (2 em = 20 pt) from the first (it reaches 4.5 pt). So the measured jitter has its own test, and the drift test uses 8 pt per entry, the smallest whole step that puts the fourth entry past 20 pt from the first while each entry stays within reach of the one before (the case that tells the two rules apart).

## Checks

- `ruff check`, `ruff format --check`: clean.
- `test_layout_contents_labels.py`: 14 passed on 8f147ce.
- `ci:full` label added on 8f147ce; the result goes in the hand-back message.
