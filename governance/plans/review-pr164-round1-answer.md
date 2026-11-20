# PR #164, answer to review round 1

New head: 8ad3609. It contains fix commit 1b39dac and a merge of main 2079d12, which
includes 586094f (#148) and #162. No force-push.

## Fixed (all three findings)

- **M1 (quadratic placement): fixed in 1b39dac.**
  - `find_graphics` now builds the read index (`item: (block, place)`) once per document.
    It passes the index to `_hosts` as a new `read` argument, so `_hosts` no longer
    rebuilds it for every page.
  - Timing on liu repeated to N pages (ids renamed per copy), measured on this machine:

    | pages | main f3dba5a | old head a61c8d4 | new head |
    |---|---|---|---|
    | 180 | 2.6 s | 4.1 s | 2.9 s |
    | 600 | 17.7 s | 36.6 s | 18.2 s |

  - Main itself grows faster than linearly: 180 pages take 2.6 s and 600 pages take 17.7 s.
    That growth is already on main and is not part of this PR.
- **S1 (the "join" check in `_hosts`): fixed.** New test
  `test_a_logo_on_every_page_inside_a_line_box_stays_a_running_head`. A repeated logo,
  40 pt tall and so not a mark, lies inside a tall line's box on 3 pages and stays a
  RUNNING_HEAD furniture block of its own on each page. Removing the check now fails
  this test.
- **S2 (the tie rule): fixed.** New test
  `test_a_mark_in_two_lines_of_one_size_stands_in_the_one_read_first`. Two line boxes of
  the same size are printed over each other, and the mark stands in the line read first.
  Changing the tie key to "read last" now fails this test.

## Notes

- N1: the guard in `_assemble` is kept, as you suggested.
- N2: no change.
- #163: the coordinator set milestone v1.0, `lane:layout`, after #48.

## Checks on 8ad3609

- ruff, format, lint-imports (3 contracts kept) and deptry are clean.
- Fast suite: 2423 passed, 19 subtests passed.
- Nightly Hypothesis on `tests/unit/test_layout*.py` and `test_core_properties.py`:
  378 passed.
- Layout golden is unchanged from a61c8d4 (7 snapshots passed).
