# Answer to review round 1 of PR #559

Fix commit 41a1a44 on 0fb3ade (one commit, no main merge).

- **M1 fixed.** `_Line.accepts` (extraction/pdf.py) compares angles around the circle:
  `turn = abs(char.angle - last.angle)`, `min(turn, math.tau - turn) > 0.01` starts a new line.
  New test `test_slightly_skewed_words_on_either_side_of_level_read_as_one_line[0, 90, 270]`
  (the probe's three words, +0.2°, −0.2°, +0.2°) in tests/unit/test_extraction_pdf.py; all
  three cases fail without the fix and pass with it. The test does not depend on the snap in
  `_Frame.angle`, which stays (it keeps angles of level turned text at exactly 0). The PR body
  names the upright fix as an older bug with the same cause.
- Fast suite locally on 41a1a44: 7165 passed, 1 failed:
  `test_extraction_pdf_progress.py::test_a_sigint_to_the_child_leaves_the_cancel_to_the_parent[while-starting]`,
  which fails on main 1797ceb in the same container too (container restarted 21:07Z;
  environment, not this diff). Linux CI is the judge.
- N1, N2: nothing to do.
