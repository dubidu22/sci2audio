# Review of PR #179 (issue #136, time estimate), round 2

Head reviewed: d2a8f78. It includes merge commit 94a8931, which brings in main at 955fea1, with no force-push. 13 Nov 2026.

## Round 1 items

- **M1, fixed (D-384).** The chunks still to speak are now a `Counter` of lengths. `seconds_left()` uses the curve up to the longest measured length L, and beyond L it uses model(L) / L per character. That is the cap I asked for. There is no zero-length risk: L is at least 1 whenever a model exists, because `speed()` is None when no characters are measured, and the plan only holds non-pause utterances with text. I checked the new tests against the round 1 code by putting 70491ed's `estimate.py` back. `test_the_curve_is_not_used_beyond_the_longest_measured_chunk` fails there (error 31 % against the ±25 % bound). `test_chunks_up_to_the_longest_measured_one_use_the_curve` fails there too, because it gets the curve beyond L. Both pass on d2a8f78. The Hypothesis property now checks that the time left equals the capped sum. One existing test changed: `test_a_fixed_cost_per_call_is_found` now leaves chunks of 20, 200 and 5 characters instead of 20, 280 and 5. That follows from D-384: 280 is beyond the longest measured chunk (210), so a pure per-call cost is scaled per character there. The test is not weakened, because it still checks a fixed cost per call within the measured range. D-384 is named in the docstrings of `estimate.py` and `audio.py`, in `docs/baseline.md` and in the PR body.
- **S1, fixed.** The `estimate.py` docstring and the PR body now say that the "no better than the rate" fallback only catches a cost that is exactly per character. They also name the real short-run guards: `MIN_CHUNKS`, the 3-lengths rule and the cap.
- **S2, fixed.** Both job tests now use the literal 4 and assert `WARM_UP_CALLS == 4` (D-381).

## Checks on d2a8f78

- ruff, format, lint-imports (3 contracts kept) and deptry are clean.
- Fast suite: 2786 passed, 1 skipped (Windows only). Estimate tests with `HYPOTHESIS_PROFILE=nightly`: 16 passed.
- Golden files compared with main (955fea1): only `tests/unit/__snapshots__/test_app_audio_job.ambr` differs, in one line (`characters_per_second` 21.0 → None). The layout snapshot changes in the diff come from #164 through the merge of main, not from this PR.
- Replay on my own runs from round 1, with the cap: pymedphys 15 % and hardt 9 %. These are the same as without the cap.

## Verdict

Nothing left to fix. A wording nit that needs no change: the PR body's first estimate.py bullet still opens with "running sums ... of the chunks still to speak", but the same paragraph then says they are counted by length. Merge once all required checks are green on d2a8f78.
