# Review PR #559 round 2

Head reviewed: 41a1a44a77c4e0afc45fdd53c298daf7bf01b249 (one fix commit on 0fb3ade). Answer: plans/answer-pr559-round2.md is plans/answer-pr559-round1.md.

## Verdict: APPROVED

- M1 fixed exactly as asked: `_Line.accepts` compares angles around the circle (`min(turn, math.tau - turn) > 0.01`). New test `test_slightly_skewed_words_on_either_side_of_level_read_as_one_line[0, 90, 270]` is the review probe; it does not rely on the snap in `_Frame.angle`.
- The diff of the fix commit touches only that line and the test; PR body names the upright case as an older bug with the same cause (no golden moves; checked in round 1 with this exact change: 77 snapshots unchanged).
- Main since review: d2ffcac (#556) touches isolate.py and its test only, no file of this PR, so no branch update (MRG-03).
- Merge on "CI passed" green on 41a1a44 (Linux; non-critical PR).
